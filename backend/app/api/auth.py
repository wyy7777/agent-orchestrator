from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    check_login_rate_limit,
    clear_login_failures,
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    record_login_failure,
    require_admin,
    verify_password,
)
from app.database import get_db
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["认证"])


@router.post("/api/auth/register", response_model=UserResponse, status_code=201)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    # 检查用户名重复
    exists = await db.execute(select(User).where(User.username == body.username))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 检查邮箱重复
    exists = await db.execute(select(User).where(User.email == body.email))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    # 第一个用户自动成为管理员
    count = (await db.execute(select(func.count(User.id)))).scalar() or 0

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=await hash_password(body.password),
        is_admin=(count == 0),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.post("/api/auth/login", response_model=Token)
async def login(body: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    # 登录频率限制
    client_ip = request.client.host if request.client else "unknown"
    if not check_login_rate_limit(client_ip):
        logger.warning(f"登录频率限制: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="登录尝试次数过多，请 15 分钟后再试",
        )

    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not await verify_password(body.password, user.hashed_password):
        record_login_failure(client_ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    # 登录成功，清除失败记录
    clear_login_failures(client_ip)

    user.last_login = datetime.now(timezone.utc)

    # 根据 remember_me 设置 token 有效期
    if body.remember_me:
        access_token = create_access_token(
            {"sub": user.id},
            expires_delta=None,  # 使用默认有效期
        )
        refresh_token = create_refresh_token({"sub": user.id})
    else:
        access_token = create_access_token({"sub": user.id})
        refresh_token = None

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
    }


@router.post("/api/auth/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
):
    """使用 refresh token 获取新的 access token。"""
    from jose import JWTError, jwt
    from app.config import settings

    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="无效的 refresh token")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="无效的 refresh token")
    except JWTError:
        raise HTTPException(status_code=401, detail="refresh token 已过期或无效")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已被禁用")

    new_access_token = create_access_token({"sub": user.id})
    new_refresh_token = create_refresh_token({"sub": user.id})

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "refresh_token": new_refresh_token,
    }


@router.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/api/auth/me", response_model=UserResponse)
async def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.email is not None:
        exists = await db.execute(
            select(User).where(User.email == body.email, User.id != current_user.id)
        )
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="邮箱已被注册")
        current_user.email = body.email

    if body.password is not None:
        current_user.hashed_password = await hash_password(body.password)

    await db.flush()
    await db.refresh(current_user)
    return current_user


@router.get("/api/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.put("/api/users/{user_id}/admin", response_model=UserResponse)
async def set_admin(
    user_id: str,
    is_admin: bool = True,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_admin = is_admin
    await db.flush()
    await db.refresh(user)
    return user


# ── OAuth2 / SSO ──

from fastapi.responses import RedirectResponse
from app.auth import (
    get_oauth2_available_providers,
    get_oauth2_authorize_url,
    handle_oauth2_callback,
)


@router.get("/oauth2/providers")
async def list_oauth2_providers():
    """列出已配置的 OAuth2 提供商。"""
    return {"providers": get_oauth2_available_providers()}


@router.get("/oauth2/login/{provider}")
async def oauth2_login(provider: str):
    """OAuth2 登录：重定向到提供商授权页。"""
    try:
        url = get_oauth2_authorize_url(provider)
        return RedirectResponse(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/oauth2/callback/{provider}")
async def oauth2_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query("", description="OAuth2 state 参数（CSRF 防护）"),
    db: AsyncSession = Depends(get_db),
):
    """OAuth2 回调：验证 state，兑换 token，返回 JWT。"""
    try:
        token = await handle_oauth2_callback(provider, code, db, state=state)
        return {"access_token": token, "token_type": "bearer"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
