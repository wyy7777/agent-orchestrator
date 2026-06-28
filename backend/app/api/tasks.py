import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_engine
from app.auth import require_role
from app.database import get_db
from app.models.task import Task
from app.models.user import User
from app.models.workflow import Workflow
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)


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

    filter_kwargs = {"q": q, "status": status, "workflow_id": workflow_id, "date_from": date_from, "date_to": date_to}

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
async def create_task(body: TaskCreate, db: AsyncSession = Depends(get_db), _user: User = Depends(require_role("admin", "manager", "operator"))):
    # 验证 workflow 存在
    wf_result = await db.execute(select(Workflow).where(Workflow.id == body.workflow_id))
    workflow = wf_result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    # 验证步骤 Agent 能力匹配
    from app.engine.yaml_parser import parse_workflow_yaml
    from app.models.agent_config import AgentConfig
    try:
        workflow_def = parse_workflow_yaml(workflow.yaml_definition)
        for step_def in workflow_def.steps:
            agent_name = step_def.config.get("agent")
            if agent_name:
                agent_result = await db.execute(
                    select(AgentConfig).where(AgentConfig.name == agent_name)
                )
                agent = agent_result.scalar_one_or_none()
                if not agent:
                    raise HTTPException(
                        status_code=400,
                        detail=f"步骤 '{step_def.name}' 指定的 Agent '{agent_name}' 不存在",
                    )
                if not agent.matches_step_type(step_def.type):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Agent '{agent.display_name}' 不支持步骤类型 '{step_def.type}'，"
                               f"其能力为: {agent.capabilities or '通用'}",
                    )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"工作流 YAML 解析失败: {e}")

    task = Task(
        workflow_id=body.workflow_id,
        trigger_type=body.trigger_type,
        trigger_payload=body.trigger_payload,
        git_repo=body.git_repo,
        git_branch=body.git_branch,
        workflow_snapshot=workflow.yaml_definition,
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
async def start_task(task_id: str, db: AsyncSession = Depends(get_db), _user: User = Depends(require_role("admin", "manager", "operator"))):
    # 当 Redis 可用时使用 ARQ 持久化队列，否则使用直接异步执行
    from app.config import settings
    if settings.REDIS_URL:
        from app.services.arq_queue import enqueue_job
        # 先初始化任务步骤记录
        engine = get_engine(db)
        task = await engine.start_task(task_id)
        await db.refresh(task, attribute_names=["step_executions"])
        # 入队到 ARQ 持久化队列
        job_id = await enqueue_job("execute_workflow", workflow_id=task.workflow_id, task_id=task_id)
        if job_id:
            logger.info(f"任务 {task_id} 已入队 ARQ: job_id={job_id}")
        await ws_manager.broadcast_task_update(task_id, {"status": task.status})
        return task
    else:
        engine = get_engine(db)
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
    _user: User = Depends(require_role("admin", "manager")),
):
    engine = get_engine(db)
    try:
        task = await engine.rollback_task(task_id, target_step_index)
        await db.refresh(task, attribute_names=["step_executions"])
        await ws_manager.broadcast_task_update(task_id, {"status": task.status})
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{task_id}/resume", response_model=TaskResponse)
async def resume_task(task_id: str, db: AsyncSession = Depends(get_db), _user: User = Depends(require_role("admin", "manager", "operator"))):
    engine = get_engine(db)
    try:
        task = await engine.resume_task(task_id)
        await db.refresh(task, attribute_names=["step_executions"])
        await ws_manager.broadcast_task_update(task_id, {"status": task.status})
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{task_id}/steps/{step_index}/replay")
async def replay_step(
    task_id: str,
    step_index: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager", "operator")),
):
    """重放指定步骤：使用快照上下文真正重新执行。"""
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.step_executions), selectinload(Task.workflow))
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    step_exec = next(
        (s for s in task.step_executions if s.step_index == step_index), None
    )
    if not step_exec:
        raise HTTPException(status_code=404, detail=f"步骤 {step_index} 不存在")

    yaml_text = task.workflow_snapshot or task.workflow.yaml_definition
    from app.engine.yaml_parser import parse_workflow_yaml

    workflow_def = parse_workflow_yaml(yaml_text)
    if step_index >= len(workflow_def.steps):
        raise HTTPException(status_code=400, detail="步骤索引超出范围")

    step_def = workflow_def.steps[step_index]

    # 从快照恢复执行上下文
    snapshot = step_exec.context_snapshot or {}
    context = {
        "task_id": task_id,
        "trigger_payload": snapshot.get("trigger_payload") or task.trigger_payload or {},
        "git_repo": snapshot.get("git_repo") or task.git_repo,
        "git_branch": snapshot.get("git_branch") or task.git_branch,
        "sandbox_branch": snapshot.get("sandbox_branch") or task.sandbox_branch,
        "results": snapshot.get("results") or {},
    }

    # 创建新的 StepExecution 记录用于重放结果
    from app.engine.step_executor import execute_single_step
    from app.models.step_execution import StepExecution as StepExecModel

    replay_exec = StepExecModel(
        task_id=task_id,
        step_index=step_index,
        step_name=f"{step_exec.step_name} [replay]",
        step_type=step_exec.step_type,
        status="running",
    )
    db.add(replay_exec)
    await db.flush()

    try:
        output = await execute_single_step(
            replay_exec, step_def, task, context, db,
        )
        await db.commit()

        return {
            "task_id": task_id,
            "step_index": step_index,
            "step_name": step_exec.step_name,
            "replay_execution_id": replay_exec.id,
            "original_output": step_exec.output_data,
            "original_status": step_exec.status,
            "replay_output": output,
            "replay_status": replay_exec.status,
            "message": "重放执行完成",
        }
    except Exception as e:
        replay_exec.status = "failed"
        replay_exec.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"重放执行失败: {e}")
