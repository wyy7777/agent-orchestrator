from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.task import Task
from app.models.workflow import Workflow
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse
from app.engine.state_machine import ExecutionEngine
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

VALID_SORT_FIELDS = {
    "created_at": Task.created_at,
    "started_at": Task.started_at,
    "completed_at": Task.completed_at,
    "tokens_used": Task.total_tokens_used,
}

VALID_STATUSES = {"pending", "running", "completed", "failed", "paused"}


def _build_task_filters(
    query,
    *,
    q: str | None = None,
    status: str | None = None,
    workflow_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(
                Task.id.like(pattern),
                Task.error_message.like(pattern),
                Task.workflow.has(Workflow.name.like(pattern)),
            )
        )
    if status:
        query = query.where(Task.status == status)
    if workflow_id:
        query = query.where(Task.workflow_id == workflow_id)
    if date_from:
        query = query.where(Task.created_at >= date_from)
    if date_to:
        query = query.where(Task.created_at <= date_to)
    return query


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    q: str | None = Query(None, description="关键词搜索（任务ID、工作流名称、错误信息）"),
    status: str | None = Query(None, description="状态筛选"),
    workflow_id: str | None = Query(None, description="工作流ID筛选"),
    date_from: datetime | None = Query(None, description="起始日期"),
    date_to: datetime | None = Query(None, description="截止日期"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"无效状态: {status}，可选值: {VALID_STATUSES}")
    if sort_by not in VALID_SORT_FIELDS:
        raise HTTPException(status_code=400, detail=f"无效排序字段: {sort_by}，可选值: {set(VALID_SORT_FIELDS)}")
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="排序方向只能是 asc 或 desc")

    filter_kwargs = dict(q=q, status=status, workflow_id=workflow_id, date_from=date_from, date_to=date_to)

    # 计数查询
    count_query = select(func.count(Task.id))
    count_query = _build_task_filters(count_query, **filter_kwargs)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 数据查询
    query = select(Task)
    query = _build_task_filters(query, **filter_kwargs)

    order_column = VALID_SORT_FIELDS[sort_by]
    order = order_column.asc() if sort_order == "asc" else order_column.desc()

    offset = (page - 1) * page_size
    result = await db.execute(
        query.options(selectinload(Task.step_executions))
        .order_by(order)
        .offset(offset)
        .limit(page_size)
    )
    items = result.scalars().all()
    return TaskListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(body: TaskCreate, db: AsyncSession = Depends(get_db)):
    # 验证 workflow 存在
    wf_result = await db.execute(select(Workflow).where(Workflow.id == body.workflow_id))
    if not wf_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="工作流不存在")

    task = Task(
        workflow_id=body.workflow_id,
        trigger_type=body.trigger_type,
        trigger_payload=body.trigger_payload,
        git_repo=body.git_repo,
        git_branch=body.git_branch,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task, attribute_names=["step_executions"])
    return task


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.step_executions))
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/{task_id}/start", response_model=TaskResponse)
async def start_task(task_id: str, db: AsyncSession = Depends(get_db)):
    engine = ExecutionEngine(db)
    try:
        task = await engine.start_task(task_id)
        await db.refresh(task, attribute_names=["step_executions"])
        await ws_manager.broadcast_task_update(task_id, {"status": task.status})
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{task_id}/rollback", response_model=TaskResponse)
async def rollback_task(
    task_id: str,
    target_step_index: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    engine = ExecutionEngine(db)
    try:
        task = await engine.rollback_task(task_id, target_step_index)
        await db.refresh(task, attribute_names=["step_executions"])
        await ws_manager.broadcast_task_update(task_id, {"status": task.status})
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{task_id}/resume", response_model=TaskResponse)
async def resume_task(task_id: str, db: AsyncSession = Depends(get_db)):
    engine = ExecutionEngine(db)
    try:
        task = await engine.resume_task(task_id)
        await db.refresh(task, attribute_names=["step_executions"])
        await ws_manager.broadcast_task_update(task_id, {"status": task.status})
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
