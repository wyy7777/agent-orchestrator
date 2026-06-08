from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.task import Task
from app.models.approval import Approval
from app.schemas.dashboard import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(Task.id)))).scalar() or 0
    completed = (
        await db.execute(select(func.count(Task.id)).where(Task.status == "completed"))
    ).scalar() or 0
    failed = (
        await db.execute(select(func.count(Task.id)).where(Task.status == "failed"))
    ).scalar() or 0
    running = (
        await db.execute(select(func.count(Task.id)).where(Task.status == "running"))
    ).scalar() or 0
    pending_approvals = (
        await db.execute(
            select(func.count(Approval.id)).where(Approval.status == "pending")
        )
    ).scalar() or 0
    total_tokens = (
        await db.execute(select(func.coalesce(func.sum(Task.total_tokens_used), 0)))
    ).scalar() or 0

    success_rate = (completed / total * 100) if total > 0 else 0.0

    # 审批通过率
    total_decided = (
        await db.execute(
            select(func.count(Approval.id)).where(
                Approval.status.in_(["approved", "rejected"])
            )
        )
    ).scalar() or 0
    approved_count = (
        await db.execute(
            select(func.count(Approval.id)).where(Approval.status == "approved")
        )
    ).scalar() or 0
    approval_rate = (approved_count / total_decided * 100) if total_decided > 0 else 0.0

    return DashboardStats(
        total_tasks=total,
        completed_tasks=completed,
        failed_tasks=failed,
        running_tasks=running,
        pending_approvals=pending_approvals,
        success_rate=round(success_rate, 1),
        total_tokens_used=total_tokens,
        avg_approval_pass_rate=round(approval_rate, 1),
    )
