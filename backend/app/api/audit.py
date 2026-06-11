"""审计日志 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.auth import require_admin

router = APIRouter(prefix="/api/audit", tags=["审计日志"])


@router.get("")
async def list_audit_logs(
    action: str | None = Query(None, description="操作类型筛选"),
    resource_type: str | None = Query(None, description="资源类型筛选"),
    user_id: str | None = Query(None, description="用户ID筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """获取审计日志列表（需管理员权限）。"""
    query = select(AuditLog)

    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)

    # 计数
    count_query = select(func.count(AuditLog.id))
    if action:
        count_query = count_query.where(AuditLog.action == action)
    if resource_type:
        count_query = count_query.where(AuditLog.resource_type == resource_type)
    if user_id:
        count_query = count_query.where(AuditLog.user_id == user_id)
    total = (await db.execute(count_query)).scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(page_size)
    )
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "user_id": log.user_id,
                "username": log.username,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "resource_name": log.resource_name,
                "details": log.details,
                "ip_address": log.ip_address,
            }
            for log in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
