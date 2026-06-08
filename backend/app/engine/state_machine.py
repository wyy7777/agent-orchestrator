from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.approval import Approval
from app.models.step_execution import StepExecution
from app.models.task import Task
from app.models.workflow import Workflow
from app.engine.yaml_parser import StepDefinition, WorkflowDefinition, parse_workflow_yaml

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# 步骤处理器注册表
_step_handlers: dict[str, type["StepHandler"]] = {}


class StepHandler:
    """步骤处理器基类。"""

    async def execute(
        self, step: StepDefinition, context: dict[str, Any], db: AsyncSession
    ) -> dict[str, Any]:
        raise NotImplementedError


def register_handler(step_type: str):
    """装饰器：注册步骤处理器。"""
    def decorator(cls):
        _step_handlers[step_type] = cls
        return cls
    return decorator


class ExecutionEngine:
    """
    自研工作流执行引擎。
    基于 asyncio 的状态机，逐步执行工作流步骤。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._running_tasks: dict[str, asyncio.Task] = {}

    async def start_task(self, task_id: str) -> Task:
        """启动一个任务的执行。"""
        task = await self._load_task(task_id)
        if task.status not in (TaskStatus.PENDING.value, TaskStatus.FAILED.value):
            raise ValueError(f"任务 {task_id} 当前状态为 {task.status}，无法启动")

        workflow_def = parse_workflow_yaml(task.workflow.yaml_definition)

        # 创建步骤执行记录
        existing_steps = await self.db.execute(
            select(StepExecution).where(StepExecution.task_id == task_id)
        )
        if not existing_steps.scalars().all():
            for i, step_def in enumerate(workflow_def.steps):
                step_exec = StepExecution(
                    task_id=task_id,
                    step_index=i,
                    step_name=step_def.name,
                    step_type=step_def.type,
                    status=StepStatus.PENDING.value,
                )
                self.db.add(step_exec)

        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.now(timezone.utc)
        task.current_step_index = 0
        await self.db.commit()

        # 异步执行
        async_task = asyncio.create_task(self._execute_workflow(task_id, workflow_def))
        self._running_tasks[task_id] = async_task

        return task

    async def resume_task(self, task_id: str) -> Task:
        """从暂停状态恢复任务（审批通过后调用）。"""
        task = await self._load_task(task_id)
        if task.status != TaskStatus.PAUSED.value:
            raise ValueError(f"任务 {task_id} 当前状态为 {task.status}，不是暂停状态")

        workflow_def = parse_workflow_yaml(task.workflow.yaml_definition)
        task.status = TaskStatus.RUNNING.value
        await self.db.commit()

        async_task = asyncio.create_task(self._execute_workflow(task_id, workflow_def))
        self._running_tasks[task_id] = async_task

        return task

    async def rollback_task(self, task_id: str, target_step_index: int) -> Task:
        """回滚任务到指定步骤。"""
        task = await self._load_task(task_id)

        if target_step_index < 0 or target_step_index >= len(task.step_executions):
            raise ValueError(f"无效的步骤索引: {target_step_index}")

        # 将目标步骤之后的所有步骤状态重置
        for step_exec in task.step_executions:
            if step_exec.step_index >= target_step_index:
                step_exec.status = StepStatus.PENDING.value
                step_exec.output_data = None
                step_exec.error_message = None
                step_exec.started_at = None
                step_exec.completed_at = None

        task.status = TaskStatus.PAUSED.value
        task.current_step_index = target_step_index
        task.error_message = None
        await self.db.commit()

        return task

    async def _execute_workflow(self, task_id: str, workflow_def: WorkflowDefinition):
        """核心执行循环。"""
        try:
            # 重新加载 task（在新 session 中）
            from app.database import async_session

            async with async_session() as db:
                result = await db.execute(
                    select(Task)
                    .options(selectinload(Task.step_executions))
                    .where(Task.id == task_id)
                )
                task = result.scalar_one()

                steps = sorted(task.step_executions, key=lambda s: s.step_index)
                context: dict[str, Any] = {
                    "task_id": task_id,
                    "trigger_payload": task.trigger_payload or {},
                    "git_repo": task.git_repo,
                    "git_branch": task.git_branch,
                    "results": {},
                }

                for step_exec in steps:
                    if step_exec.status == StepStatus.COMPLETED.value:
                        continue  # 已完成的步骤跳过

                    # 检查 token 限额
                    if task.total_tokens_used >= settings.MAX_TOKENS_PER_TASK:
                        raise RuntimeError(
                            f"Token 消耗已达上限 ({settings.MAX_TOKENS_PER_TASK})"
                        )

                    step_def = workflow_def.steps[step_exec.step_index]
                    task.current_step_index = step_exec.step_index

                    # 审批步骤
                    if step_def.type == "approval":
                        step_exec.status = StepStatus.WAITING_APPROVAL.value
                        step_exec.started_at = datetime.now(timezone.utc)
                        task.status = TaskStatus.PAUSED.value

                        approval = Approval(
                            step_execution_id=step_exec.id,
                            status="pending",
                        )
                        db.add(approval)
                        await db.commit()
                        logger.info(f"任务 {task_id} 在步骤 '{step_exec.step_name}' 等待审批")
                        return  # 暂停，等待外部审批信号

                    # 执行普通步骤
                    step_exec.status = StepStatus.RUNNING.value
                    step_exec.started_at = datetime.now(timezone.utc)
                    await db.commit()

                    try:
                        handler = _step_handlers.get(step_def.type)
                        if handler is None:
                            # 无处理器的步骤类型自动完成（如 merge）
                            output = {"status": "auto_completed"}
                        else:
                            output = await handler().execute(step_def, context, db)

                        step_exec.status = StepStatus.COMPLETED.value
                        step_exec.output_data = output
                        step_exec.completed_at = datetime.now(timezone.utc)

                        # 累计 token
                        tokens = output.get("tokens_used", 0)
                        task.total_tokens_used += tokens
                        step_exec.token_usage = {"tokens": tokens}

                        context["results"][step_exec.step_name] = output
                        logger.info(f"步骤 '{step_exec.step_name}' 完成, tokens={tokens}")

                    except Exception as e:
                        step_exec.status = StepStatus.FAILED.value
                        step_exec.error_message = str(e)
                        step_exec.completed_at = datetime.now(timezone.utc)
                        task.status = TaskStatus.FAILED.value
                        task.error_message = f"步骤 '{step_exec.step_name}' 失败: {e}"
                        task.completed_at = datetime.now(timezone.utc)
                        await db.commit()
                        logger.error(f"步骤 '{step_exec.step_name}' 失败: {e}")
                        return

                    await db.commit()

                # 所有步骤完成
                task.status = TaskStatus.COMPLETED.value
                task.completed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info(f"任务 {task_id} 完成")

        except Exception as e:
            logger.error(f"工作流执行异常: {e}")
        finally:
            self._running_tasks.pop(task_id, None)

    async def _load_task(self, task_id: str) -> Task:
        result = await self.db.execute(
            select(Task)
            .options(selectinload(Task.step_executions), selectinload(Task.workflow))
            .where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        return task
