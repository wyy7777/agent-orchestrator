import asyncio
from datetime import datetime, timedelta, timezone
import logging
import secrets

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
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
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(data: dict) -> str:
    """创建 refresh token（有效期 30 天）。"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=30)
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

    if len(_login_failures[ip]) >= MAX_LOGIN_FAILURES:
        return False

    return True


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


def ensure_secret_key():
    """确保 SECRET_KEY 已配置。未配置时自动生成并保存到 .env。"""
    if not settings.SECRET_KEY:
        new_key = secrets.token_hex(32)
        logger.warning(f"SECRET_KEY 未配置，已自动生成: {new_key[:8]}...")
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
