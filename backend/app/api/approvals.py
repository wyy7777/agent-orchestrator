import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db, async_session
from app.models.approval import Approval
from app.models.step_execution import StepExecution
from app.models.task import Task
from app.models.workflow import Workflow
from app.schemas.approval import ApprovalCreate, ApprovalListResponse, ApprovalResponse
from app.engine.state_machine import ExecutionEngine
from app.engine.yaml_parser import parse_workflow_yaml
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


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
    approval_id: str, body: ApprovalCreate, db: AsyncSession = Depends(get_db)
):
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

        # 异步恢复执行（在新的 session 中）
        asyncio.create_task(_resume_task(task_id))

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


async def _resume_task(task_id: str):
    """在新的数据库 session 中恢复任务执行。"""
    try:
        async with async_session() as db:
            engine = ExecutionEngine(db)
            task = await engine.resume_task(task_id)
            await ws_manager.broadcast_task_update(task_id, {"status": task.status})
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"恢复任务 {task_id} 失败: {e}")
