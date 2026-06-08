from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.task import Task
from app.models.workflow import Workflow
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse
from app.engine.state_machine import ExecutionEngine
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    workflow_id: str | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(Task)
    count_query = select(func.count(Task.id))

    if workflow_id:
        query = query.where(Task.workflow_id == workflow_id)
        count_query = count_query.where(Task.workflow_id == workflow_id)
    if status:
        query = query.where(Task.status == status)
        count_query = count_query.where(Task.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.options(selectinload(Task.step_executions))
        .order_by(Task.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.scalars().all()
    return TaskListResponse(items=items, total=total)


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
    task_id: str, target_step_index: int = 0, db: AsyncSession = Depends(get_db)
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
