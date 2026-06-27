import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# 登录失败记录（IP -> 失败次数和时间）
_login_failures: dict[str, list[float]] = {}
MAX_LOGIN_FAILURES = 5
LOCKOUT_SECONDS = 900  # 15 分钟


async def hash_password(password: str) -> str:
    """使用 bcrypt 哈希密码（在线程池中执行以避免阻塞事件循环）。"""
    return await asyncio.to_thread(_hash_password_sync, password)


def _hash_password_sync(password: str) -> str:
    """同步 bcrypt 哈希（在线程池中调用）。"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码（在线程池中执行以避免阻塞事件循环）。"""
    return await asyncio.to_thread(_verify_password_sync, plain_password, hashed_password)


def _verify_password_sync(plain_password: str, hashed_password: str) -> bool:
    """同步 bcrypt 验证（在线程池中调用）。"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """创建 JWT access token。"""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(data: dict) -> str:
    """创建 refresh token（有效期 30 天）。"""
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=30)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def check_login_rate_limit(ip: str) -> bool:
    """检查登录频率限制，返回 True 表示允许登录。"""
    import time
    now = time.time()

    if ip not in _login_failures:
        _login_failures[ip] = []

    # 清理过期记录
    _login_failures[ip] = [t for t in _login_failures[ip] if now - t < LOCKOUT_SECONDS]

    return not len(_login_failures[ip]) >= MAX_LOGIN_FAILURES


def record_login_failure(ip: str):
    """记录登录失败。"""
    import time
    if ip not in _login_failures:
        _login_failures[ip] = []
    _login_failures[ip].append(time.time())


def clear_login_failures(ip: str):
    """清除登录失败记录（登录成功时调用）。"""
    _login_failures.pop(ip, None)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前认证用户。支持单用户模式（无 token 时使用默认用户）。"""
    # 如果有 token，验证 token
    if credentials:
        token = credentials.credentials
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id: str | None = payload.get("sub")
            if user_id:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user and user.is_active:
                    return user
        except JWTError:
            pass

    # 单用户模式：返回或创建默认用户
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()

    if not user:
        # 自动创建默认本地用户
        user = User(
            username="local",
            email="local@agent-orchestrator",
            hashed_password=await hash_password("local"),
            is_active=True,
            is_admin=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("单用户模式：已创建默认本地用户 'local'")

    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求管理员权限。"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user


# 角色层级：admin > manager > operator > viewer
ROLE_HIERARCHY = {
    "admin": 4,
    "manager": 3,
    "operator": 2,
    "viewer": 1,
}


def require_role(*allowed_roles: str):
    """
    角色权限依赖工厂。
    用法: Depends(require_role("admin", "manager"))
    """
    async def checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        user_role = current_user.role or "operator"
        # 管理员始终放行
        if current_user.is_admin or user_role == "admin":
            return current_user
        # 检查角色是否在允许列表
        if user_role not in allowed_roles:
            # 检查层级：如果用户角色层级 >= 任一允许角色的层级，放行
            user_level = ROLE_HIERARCHY.get(user_role, 0)
            max_allowed_level = max(ROLE_HIERARCHY.get(r, 0) for r in allowed_roles)
            if user_level < max_allowed_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"权限不足，需要角色: {'/'.join(allowed_roles)}",
                )
        return current_user
    return checker


def ensure_secret_key():
    """确保 SECRET_KEY 已配置。未配置时自动生成并保存到 .env。"""
    if not settings.SECRET_KEY:
        new_key = secrets.token_hex(32)
        logger.warning("SECRET_KEY 未配置，已自动生成（请勿泄露）")
        # 尝试写入 .env 文件
        try:
            from pathlib import Path
            env_path = Path(__file__).parent.parent / ".env"
            if env_path.exists():
                content = env_path.read_text()
                if "SECRET_KEY" not in content:
                    content += f"\nSECRET_KEY={new_key}\n"
                    env_path.write_text(content)
                    logger.info("SECRET_KEY 已保存到 .env 文件")
        except Exception as e:
            logger.warning(f"无法保存 SECRET_KEY 到 .env: {e}")
        # 更新 settings
        settings.SECRET_KEY = new_key


async def verify_ws_token(token: str | None, db: AsyncSession) -> User | None:
    """验证 WebSocket 连接的 JWT token。

    用于 WebSocket 端点认证：WebSocket 握手不支持自定义 HTTP header，
    所以 token 通过查询参数传递（如 ?token=xxx）。

    返回:
        User 对象（验证成功），或 None（单用户模式或无 token）。
    """
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id: str | None = payload.get("sub")
            if user_id:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user and user.is_active:
                    return user
        except JWTError:
            logger.warning("WebSocket token 验证失败")

    # 单用户模式：返回默认用户
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    if user and user.is_active:
        return user
    return None


# ── OAuth2 / SSO ──

OAUTH2_PROVIDERS = {
    "google": {
        "name": "Google",
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scope": "openid email profile",
    },
    "github": {
        "name": "GitHub",
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scope": "user:email",
    },
    "microsoft": {
        "name": "Microsoft",
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "scope": "openid email profile",
    },
}


def get_oauth2_available_providers() -> list[dict]:
    available = []
    for key, info in OAUTH2_PROVIDERS.items():
        client_id = getattr(settings, f"OAUTH2_{key.upper()}_CLIENT_ID", "")
        if client_id:
            available.append({"id": key, "name": info["name"]})
    return available


# OAuth2 state store for CSRF protection: state -> (provider, expiry_timestamp)
_oauth2_states: dict[str, tuple[str, float]] = {}
_OAUTH2_STATE_TTL = 600  # 10 分钟


def get_oauth2_authorize_url(provider: str, state: str = "") -> str:
    import time as _time
    import urllib.parse
    info = OAUTH2_PROVIDERS.get(provider)
    if not info:
        raise ValueError(f"未知的 OAuth2 provider: {provider}")
    client_id = getattr(settings, f"OAUTH2_{provider.upper()}_CLIENT_ID", "")
    if not client_id:
        raise ValueError(f"{provider} OAuth2 未配置")
    redirect_uri = f"{settings.OAUTH2_REDIRECT_BASE}/api/auth/oauth2/callback/{provider}"
    state_token = state or secrets.token_hex(16)
    # 存储 state 用于后续验证
    _oauth2_states[state_token] = (provider, _time.time() + _OAUTH2_STATE_TTL)
    # 清理过期 state
    now = _time.time()
    expired = [k for k, v in _oauth2_states.items() if v[1] < now]
    for k in expired:
        del _oauth2_states[k]
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": info["scope"],
        "state": state_token,
    }
    return f"{info['authorize_url']}?{urllib.parse.urlencode(params)}"


async def handle_oauth2_callback(provider: str, code: str, db: AsyncSession, state: str = "") -> str:
    import time as _time

    import httpx
    info = OAUTH2_PROVIDERS.get(provider)
    if not info:
        raise ValueError(f"未知的 OAuth2 provider: {provider}")

    # 验证 state 参数（CSRF 防护）
    if state:
        stored = _oauth2_states.pop(state, None)
        if stored is None:
            raise ValueError("无效的 OAuth2 state 参数（可能为 CSRF 攻击）")
        stored_provider, expiry = stored
        if _time.time() > expiry:
            raise ValueError("OAuth2 state 已过期，请重新登录")
        if stored_provider != provider:
            raise ValueError("OAuth2 state 与 provider 不匹配")
    else:
        logger.warning("OAuth2 回调缺少 state 参数，跳过 CSRF 验证（不安全）")
    client_id = getattr(settings, f"OAUTH2_{provider.upper()}_CLIENT_ID", "")
    client_secret = getattr(settings, f"OAUTH2_{provider.upper()}_CLIENT_SECRET", "")
    redirect_uri = f"{settings.OAUTH2_REDIRECT_BASE}/api/auth/oauth2/callback/{provider}"

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(info["token_url"], data={
            "client_id": client_id, "client_secret": client_secret,
            "code": code, "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        }, headers={"Accept": "application/json"}, timeout=30)
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError(f"OAuth2 token 交换失败: {token_data}")

        user_resp = await client.get(info["userinfo_url"],
            headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
        user_data = user_resp.json()

    email = user_data.get("email", "")
    username = user_data.get("login") or user_data.get("name") or email.split("@")[0]
    if not email:
        email = f"{username}@{provider}.user"

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        user = User(username=username, email=email,
            hashed_password=await hash_password(secrets.token_hex(32)),
            is_active=True, role="operator")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return create_access_token({"sub": user.id})
