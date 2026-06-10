"""步骤执行器：单步、子任务、循环。"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.engine.condition_eval import evaluate_condition
from app.engine.plugin import get_plugin
from app.engine.types import StepHandler, StepStatus, TaskStatus, _step_handlers
from app.engine.yaml_parser import StepDefinition, WorkflowDefinition, parse_workflow_yaml
from app.models.approval import Approval
from app.models.step_execution import StepExecution
from app.models.task import Task
from app.models.workflow import Workflow

logger = logging.getLogger(__name__)


async def execute_single_step(
    step_exec: StepExecution,
    step_def: StepDefinition,
    task: Task,
    context: dict[str, Any],
    db: AsyncSession,
    on_step_complete=None,
) -> dict[str, Any]:
    """执行单个步骤，返回输出。超时/异常直接抛出。"""
    handler = _step_handlers.get(step_def.type)
    plugin = get_plugin(step_def.type) if handler is None else None
    if handler is None and plugin is None:
        output: dict[str, Any] = {"status": "auto_completed"}
    elif handler is not None:
        step_timeout = step_def.timeout or settings.STEP_TIMEOUT_SECONDS
        output = await asyncio.wait_for(
            handler().execute(step_def, context, db),
            timeout=step_timeout,
        )
    else:
        step_timeout = step_def.timeout or settings.STEP_TIMEOUT_SECONDS
        output = await asyncio.wait_for(
            plugin.execute(step_def.config or {}, context),
            timeout=step_timeout,
        )

    step_exec.status = StepStatus.COMPLETED.value
    step_exec.output_data = output
    step_exec.completed_at = datetime.now(timezone.utc)

    tokens = output.get("tokens_used", 0)
    task.total_tokens_used += tokens
    step_exec.token_usage = {"tokens": tokens}

    context["results"][step_exec.step_name] = output

    if step_def.type == "merge" and output.get("pr_url"):
        task.pr_url = output["pr_url"]
        logger.info(f"PR 已创建: {task.pr_url}")

    logger.info(f"步骤 '{step_exec.step_name}' 完成, tokens={tokens}")
    if on_step_complete:
        await on_step_complete(context["task_id"], step_exec.step_name)
    return output


async def execute_subtask_step(
    step_def: StepDefinition,
    context: dict[str, Any],
    db: AsyncSession,
    execute_workflow_fn,
) -> dict[str, Any]:
    """执行子任务步骤：启动子工作流，等待完成，合并结果。"""
    from app.database import async_session

    child_workflow_id: str | None = step_def.config.get("child_workflow_id")
    if not child_workflow_id:
        raise ValueError(f"子任务步骤 '{step_def.name}' 缺少 config.child_workflow_id")

    child_workflow = await db.get(Workflow, child_workflow_id)
    if not child_workflow:
        raise ValueError(f"子工作流 {child_workflow_id} 不存在")

    child_workflow_def = parse_workflow_yaml(child_workflow.yaml_definition)

    # 创建子任务记录
    child_task = Task(
        workflow_id=child_workflow_id,
        trigger_type="subtask",
        trigger_payload={
            "parent_task_id": context["task_id"],
            "parent_context": context,
        },
        git_repo=context.get("git_repo"),
        git_branch=context.get("git_branch"),
        sandbox_branch=context.get("sandbox_branch"),
    )
    db.add(child_task)
    await db.flush()

    # 创建子步骤执行记录
    for i, sub_step_def in enumerate(child_workflow_def.steps):
        db.add(
            StepExecution(
                task_id=child_task.id,
                step_index=i,
                step_name=sub_step_def.name,
                step_type=sub_step_def.type,
                status=StepStatus.PENDING.value,
            )
        )

    child_task.status = TaskStatus.RUNNING.value
    child_task.started_at = datetime.now(timezone.utc)
    child_task.current_step_index = 0
    await db.commit()

    logger.info(f"子任务 {child_task.id} 已启动 (父任务 {context['task_id']})")

    # 在新 session 中执行子工作流
    await execute_workflow_fn(child_task.id, child_workflow_def)

    # 加载子任务最终状态
    async with async_session() as read_db:
        result = await read_db.execute(
            select(Task)
            .options(selectinload(Task.step_executions))
            .where(Task.id == child_task.id)
        )
        child_task_final = result.scalar_one()

        if child_task_final.status != TaskStatus.COMPLETED.value:
            raise RuntimeError(
                f"子任务 {child_task.id} 未成功完成，状态: {child_task_final.status}"
            )

        child_results = {}
        for se in child_task_final.step_executions:
            if se.output_data:
                child_results[se.step_name] = se.output_data

    return {
        "status": "subtask_completed",
        "child_task_id": child_task.id,
        "child_results": child_results,
    }


async def execute_loop_step(
    step_def: StepDefinition,
    task: Task,
    context: dict[str, Any],
    db: AsyncSession,
    on_step_complete=None,
) -> dict[str, Any]:
    """执行循环步骤：遍历列表，对每项执行子步骤。"""
    items_key: str = step_def.config.get("items_key", "items")
    max_iterations: int = step_def.config.get("max_iterations", 100)
    sub_step_defs: list[StepDefinition] = step_def.steps

    if not sub_step_defs:
        raise ValueError(f"循环步骤 '{step_def.name}' 未定义子步骤")

    # 从 context 取列表，支持嵌套 key（如 "results.items"）
    items = context
    for key in items_key.split("."):
        if isinstance(items, dict):
            items = items.get(key)
        else:
            items = None
            break

    if not isinstance(items, list):
        raise ValueError(
            f"循环步骤 '{step_def.name}' 的 items_key '{items_key}' "
            f"在 context 中未找到或不是列表"
        )

    items = items[:max_iterations]
    loop_results = []

    for idx, item in enumerate(items):
        logger.info(f"循环 '{step_def.name}' 第 {idx + 1}/{len(items)} 次迭代")
        iteration_context = {**context, "loop_index": idx, "loop_item": item}

        for sub_def in sub_step_defs:
            sub_step_exec = StepExecution(
                task_id=context["task_id"],
                step_index=-1,
                step_name=f"{step_def.name}[{idx}].{sub_def.name}",
                step_type=sub_def.type,
                status=StepStatus.RUNNING.value,
                started_at=datetime.now(timezone.utc),
            )
            db.add(sub_step_exec)
            await db.flush()

            try:
                output = await execute_single_step(
                    sub_step_exec, sub_def, task, iteration_context, db, on_step_complete
                )
                context["results"][sub_step_exec.step_name] = output
            except (asyncio.TimeoutError, Exception) as e:
                sub_step_exec.status = StepStatus.FAILED.value
                sub_step_exec.error_message = str(e)
                sub_step_exec.completed_at = datetime.now(timezone.utc)
                raise

        loop_results.append(
            iteration_context.get("results", {}).get(f"{step_def.name}[{idx}]")
        )

    return {
        "status": "loop_completed",
        "iterations": len(items),
        "results": loop_results,
    }
