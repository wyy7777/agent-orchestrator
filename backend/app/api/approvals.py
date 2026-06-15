import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models.approval import Approval
from app.models.step_execution import StepExecution
from app.models.task import Task
from app.models.user import User
from app.auth import require_role
from app.schemas.approval import ApprovalCreate, ApprovalListResponse, ApprovalResponse
from app.engine.state_machine import ExecutionEngine
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


def _get_engine(db: AsyncSession) -> ExecutionEngine:
    """创建带事件回调的引擎实例。"""
    from app.main import _engine_event_handler
    return ExecutionEngine(db, on_event=_engine_event_handler)


@router.get("", response_model=ApprovalListResponse)
async def list_approvals(
    status: str = "pending",
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(
        select(func.count(Approval.id)).where(Approval.status == status)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(Approval)
        .where(Approval.status == status)
        .order_by(Approval.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.scalars().all()
    return ApprovalListResponse(items=items, total=total)


@router.post("/{approval_id}/decide", response_model=ApprovalResponse)
async def decide_approval(
    approval_id: str, body: ApprovalCreate, db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager", "operator")),
):
    """审批决策（通过/拒绝）。审计日志为 append-only，不可删除。"""
    if body.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status 必须是 approved 或 rejected")

    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="审批记录不存在")
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="该审批已处理")

    approval.status = body.status
    approval.approver = body.approver
    approval.comment = body.comment
    approval.decided_at = datetime.now(timezone.utc)

    # 更新关联的步骤状态
    step_result = await db.execute(
        select(StepExecution).where(StepExecution.id == approval.step_execution_id)
    )
    step_exec = step_result.scalar_one_or_none()

    if body.status == "approved" and step_exec:
        step_exec.status = "completed"
        step_exec.completed_at = datetime.now(timezone.utc)
        task_id = step_exec.task_id

        await db.commit()

        # 同步等待任务恢复完成，确保异常被捕获和记录
        try:
            await _resume_task(task_id)
        except Exception as e:
            logger.error(f"恢复任务 {task_id} 失败: {e}", exc_info=True)

    elif body.status == "rejected" and step_exec:
        step_exec.status = "failed"
        step_exec.error_message = body.comment or "审批被拒绝"
        step_exec.completed_at = datetime.now(timezone.utc)

        task_result = await db.execute(select(Task).where(Task.id == step_exec.task_id))
        task = task_result.scalar_one_or_none()
        if task:
            task.status = "failed"
            task.error_message = f"步骤 '{step_exec.step_name}' 审批被拒绝"
            task.completed_at = datetime.now(timezone.utc)

        await db.commit()

    else:
        await db.commit()

    await ws_manager.broadcast_approval_update({
        "approval_id": approval.id,
        "status": approval.status,
    })
    return approval


class BatchDecision(BaseModel):
    ids: list[str]
    action: str  # "approve" | "reject"
    comment: str | None = None


@router.post("/batch")
async def batch_decide(
    body: BatchDecision,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager", "operator")),
):
    """批量审批：一次处理多个审批。"""
    if body.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action 必须是 approve 或 reject")

    results = []
    for aid in body.ids:
        result = await db.execute(select(Approval).where(Approval.id == aid))
        approval = result.scalar_one_or_none()
        if not approval or approval.status != "pending":
            results.append({"id": aid, "status": "skipped", "reason": "不存在或已处理"})
            continue

        approval.status = "approved" if body.action == "approve" else "rejected"
        approval.approver = _user.username
        approval.comment = body.comment
        approval.decided_at = datetime.now(timezone.utc)

        # 更新关联步骤
        step_result = await db.execute(
            select(StepExecution).where(StepExecution.id == approval.step_execution_id)
        )
        step_exec = step_result.scalar_one_or_none()
        if step_exec:
            if body.action == "approve":
                step_exec.status = "completed"
                step_exec.completed_at = datetime.now(timezone.utc)
            else:
                step_exec.status = "failed"
                step_exec.error_message = body.comment or "批量审批拒绝"

        results.append({"id": aid, "status": body.action})

    await db.commit()
    return {"processed": len(results), "results": results}


class RevokeRequest(BaseModel):
    reason: str | None = None


@router.post("/{approval_id}/revoke", response_model=ApprovalResponse)
async def revoke_approval(
    approval_id: str,
    body: RevokeRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager")),
):
    """撤销已决定的审批：将关联任务恢复为 pending 状态。"""
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="审批记录不存在")

    if approval.status == "pending":
        raise HTTPException(status_code=400, detail="待处理的审批无需撤销")

    if approval.revoked_at:
        raise HTTPException(status_code=400, detail="该审批已被撤销")

    # 获取关联步骤和任务
    step_result = await db.execute(
        select(StepExecution).where(StepExecution.id == approval.step_execution_id)
    )
    step_exec = step_result.scalar_one_or_none()

    if step_exec:
        task_result = await db.execute(select(Task).where(Task.id == step_exec.task_id))
        task = task_result.scalar_one_or_none()
        if task and task.status in ("completed", "failed"):
            # 将任务恢复为 pending，步骤恢复为 pending
            task.status = "pending"
            task.error_message = None
            task.completed_at = None
            step_exec.status = "pending"
            step_exec.error_message = None
            step_exec.completed_at = None

    # 撤销审批
    approval.status = "revoked"
    approval.revoked_at = datetime.now(timezone.utc)
    approval.revoke_reason = body.reason or "审批已撤销"

    await db.commit()

    # 尝试恢复任务执行
    if step_exec:
        task_id = step_exec.task_id
        try:
            await _resume_task(task_id)
        except Exception as e:
            logger.error(f"撤销后恢复任务 {task_id} 失败: {e}", exc_info=True)

    await ws_manager.broadcast_approval_update({
        "approval_id": approval.id,
        "status": "revoked",
    })

    return approval


async def _resume_task(task_id: str):
    """在新的数据库 session 中恢复任务执行。"""
    async with async_session() as db:
        engine = _get_engine(db)
        task = await engine.resume_task(task_id)
        await ws_manager.broadcast_task_update(task_id, {"status": task.status})
