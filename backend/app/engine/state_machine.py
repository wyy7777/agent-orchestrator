"""工作流执行引擎：核心状态机。"""
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
from app.engine.step_executor import execute_single_step, execute_subtask_step, execute_loop_step
from app.engine.types import StepHandler, StepStatus, TaskStatus, _step_handlers, register_handler  # noqa: F401
from app.engine.yaml_parser import StepDefinition, WorkflowDefinition, parse_workflow_yaml
from app.models.approval import Approval
from app.models.step_execution import StepExecution
from app.models.task import Task

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    自研工作流执行引擎。
    基于 asyncio 的状态机，逐步执行工作流步骤。
    """

    def __init__(self, db: AsyncSession, on_event=None):
        self.db = db
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._on_event = on_event  # 事件回调，解耦 notifier

    async def _emit(self, event: str, *args):
        """发送事件（如果有回调）。"""
        if self._on_event:
            try:
                await self._on_event(event, *args)
            except Exception as e:
                logger.warning(f"事件回调失败: {e}")

    async def recover_orphaned_tasks(self):
        """启动时恢复：将所有 running 状态的任务标记为 failed。"""
        result = await self.db.execute(
            select(Task).where(Task.status == TaskStatus.RUNNING.value)
        )
        orphaned = result.scalars().all()
        for task in orphaned:
            task.status = TaskStatus.FAILED.value
            task.error_message = "进程重启导致任务中断"
            task.completed_at = datetime.now(timezone.utc)
        if orphaned:
            await self.db.commit()
            logger.warning(f"已恢复 {len(orphaned)} 个孤儿任务")

    async def start_task(self, task_id: str) -> Task:
        """启动一个任务的执行。"""
        task = await self._load_task(task_id)
        if task.status not in (TaskStatus.PENDING.value, TaskStatus.FAILED.value):
            raise ValueError(f"任务 {task_id} 当前状态为 {task.status}，无法启动")

        # 断路器检查
        from app.engine.circuit_breaker import circuit_breaker
        if circuit_breaker.is_open(task.workflow_id):
            raise ValueError("断路器已打开，该工作流连续失败次数过多，请稍后再试")

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

        # 如果配置了 GitHub 仓库，创建沙箱分支
        if task.git_repo and settings.GITHUB_TOKEN and not task.sandbox_branch:
            try:
                from app.integrations.github import _parse_repo, create_branch, get_default_branch

                owner, repo = _parse_repo(task.git_repo)
                base_branch = task.git_branch or await get_default_branch(owner, repo)
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
                branch_name = f"agent-fix/{timestamp}"
                await create_branch(owner, repo, branch_name, base_branch)
                task.sandbox_branch = branch_name
                task.git_branch = task.git_branch or base_branch
                logger.info(f"沙箱分支 {branch_name} 已创建")
            except Exception as e:
                logger.warning(f"创建沙箱分支失败: {e}")

        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.now(timezone.utc)
        task.current_step_index = 0
        await self.db.commit()

        # 异步执行
        async_task = asyncio.create_task(self._execute_workflow(task_id, workflow_def))
        self._running_tasks[task_id] = async_task

        await self._emit("task_started", task_id, workflow_def.name)

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
        """核心执行循环。支持并行步骤、子任务和循环步骤。

        注意：此方法使用独立的 async_session（非注入的 request-scoped session），
        因为它作为 asyncio.create_task 在后台运行，生命周期与 HTTP 请求无关。
        这是后台任务的正确模式——请求通过 self.db 处理，长时间运行的工作流自行管理事务。
        """
        try:
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
                    "sandbox_branch": task.sandbox_branch,
                    "results": {},
                }

                # 分组步骤
                step_groups = await self._group_steps(steps, workflow_def, context, db, task_id)

                # 逐组执行
                for group in step_groups:
                    if task.total_tokens_used >= settings.MAX_TOKENS_PER_TASK:
                        raise RuntimeError(f"Token 消耗已达上限 ({settings.MAX_TOKENS_PER_TASK})")

                    # 审批检查
                    approval_result = await self._check_approval(group, task, db, task_id)
                    if approval_result == "paused":
                        return

                    # 标记组内所有步骤为 running
                    for step_exec, step_def in group:
                        step_exec.status = StepStatus.RUNNING.value
                        step_exec.started_at = datetime.now(timezone.utc)
                        task.current_step_index = step_exec.step_index
                    await db.commit()

                    try:
                        await self._execute_step_group(group, task, context, db, task_id)
                    except asyncio.TimeoutError:
                        await self._handle_group_failure(
                            group, task, db, task_id, workflow_def.name,
                            error_msg="步骤组超时", timeout=True,
                        )
                        return
                    except Exception as e:
                        await self._handle_group_failure(
                            group, task, db, task_id, workflow_def.name,
                            error_msg=str(e),
                        )
                        return

                    await db.commit()

                # 所有步骤完成
                task.status = TaskStatus.COMPLETED.value
                task.completed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info(f"任务 {task_id} 完成")
                await self._emit("task_completed", task_id, workflow_def.name)

                # 断路器：记录成功
                from app.engine.circuit_breaker import circuit_breaker
                await circuit_breaker.record_success(task.workflow_id, db=db)

        except Exception as e:
            logger.error(f"工作流执行异常: {e}", exc_info=True)
            try:
                async with async_session() as db:
                    result = await db.execute(select(Task).where(Task.id == task_id))
                    task = result.scalar_one_or_none()
                    if task and task.status == TaskStatus.RUNNING.value:
                        task.status = TaskStatus.FAILED.value
                        task.error_message = f"执行异常: {e}"
                        task.completed_at = datetime.now(timezone.utc)
                        await db.commit()
            except Exception as inner_e:
                logger.error(f"更新失败任务状态异常: {inner_e}")
        finally:
            self._running_tasks.pop(task_id, None)

    async def _group_steps(
        self,
        steps: list[StepExecution],
        workflow_def: WorkflowDefinition,
        context: dict[str, Any],
        db: AsyncSession,
        task_id: str,
    ) -> list[list[tuple[StepExecution, StepDefinition]]]:
        """将步骤分组：连续的并行步骤归为一组，其余单独为组。已完成的步骤跳过，条件不满足的步骤跳过。"""
        step_groups: list[list[tuple[StepExecution, StepDefinition]]] = []
        current_group: list[tuple[StepExecution, StepDefinition]] = []

        for step_exec in steps:
            step_def = workflow_def.steps[step_exec.step_index]

            if step_exec.status == StepStatus.COMPLETED.value:
                current_group = []
                continue

            # 条件检查
            if step_def.condition:
                should_continue = await self._handle_condition(step_exec, step_def, context, db, task_id)
                if should_continue:
                    continue

            if step_def.parallel and current_group and workflow_def.steps[current_group[-1][0].step_index].parallel:
                current_group.append((step_exec, step_def))
            else:
                if current_group:
                    step_groups.append(current_group)
                current_group = [(step_exec, step_def)]

        if current_group:
            step_groups.append(current_group)

        return step_groups

    async def _handle_condition(
        self,
        step_exec: StepExecution,
        step_def: StepDefinition,
        context: dict[str, Any],
        db: AsyncSession,
        task_id: str,
    ) -> bool:
        """处理条件步骤。返回 True 表示应跳过此步骤（continue）。"""
        condition_result = evaluate_condition(step_def.condition, context)
        if condition_result:
            return False  # 条件满足，不跳过

        step_exec.status = StepStatus.SKIPPED.value
        step_exec.output_data = {"skipped": True, "reason": f"条件不满足: {step_def.condition}"}
        step_exec.completed_at = datetime.now(timezone.utc)
        logger.info(f"步骤 '{step_exec.step_name}' 被跳过 (条件不满足: {step_def.condition})")

        # 执行 else 分支
        if step_def.else_steps:
            await self._execute_else_steps(step_exec, step_def, context, db, task_id)

        return True  # 跳过此步骤

    async def _execute_else_steps(
        self,
        step_exec: StepExecution,
        step_def: StepDefinition,
        context: dict[str, Any],
        db: AsyncSession,
        task_id: str,
    ):
        """执行条件步骤的 else 分支。"""
        logger.info(f"执行步骤 '{step_exec.step_name}' 的 else 分支")
        for else_step_def in step_def.else_steps:
            else_exec = StepExecution(
                task_id=task_id,
                step_index=-1,
                step_name=f"{step_exec.step_name}.else.{else_step_def.name}",
                step_type=else_step_def.type,
                status=StepStatus.RUNNING.value,
                started_at=datetime.now(timezone.utc),
            )
            db.add(else_exec)
            await db.flush()
            try:
                output = await execute_single_step(
                    else_exec, else_step_def, context, db,
                    on_step_complete=self._emit_step_completed
                )
                context["results"][else_exec.step_name] = output
            except Exception as e:
                else_exec.status = StepStatus.FAILED.value
                else_exec.error_message = str(e)
                else_exec.completed_at = datetime.now(timezone.utc)
                logger.error(f"else 分支步骤 '{else_step_def.name}' 失败: {e}")

    async def _check_approval(
        self,
        group: list[tuple[StepExecution, StepDefinition]],
        task: Task,
        db: AsyncSession,
        task_id: str,
    ) -> str | None:
        """检查审批。返回 'paused' 表示任务已暂停，None 表示继续。"""
        for step_exec, step_def in group:
            if step_def.type == "approval":
                step_exec.status = StepStatus.WAITING_APPROVAL.value
                step_exec.started_at = datetime.now(timezone.utc)
                task.status = TaskStatus.PAUSED.value
                task.current_step_index = step_exec.step_index

                approval = Approval(step_execution_id=step_exec.id, status="pending")
                db.add(approval)
                await db.commit()
                logger.info(f"任务 {task_id} 在步骤 '{step_exec.step_name}' 等待审批")
                await self._emit("approval_needed", task_id, step_exec.step_name)
                return "paused"
        return None

    async def _execute_step_group(
        self,
        group: list[tuple[StepExecution, StepDefinition]],
        task: Task,
        context: dict[str, Any],
        db: AsyncSession,
        task_id: str,
    ):
        """执行单个步骤组（单步或并行）。"""
        if len(group) == 1:
            step_exec, step_def = group[0]
            if step_def.type == "subtask":
                output = await execute_subtask_step(step_def, context, db, self._execute_workflow)
                step_exec.status = StepStatus.COMPLETED.value
                step_exec.output_data = output
                step_exec.completed_at = datetime.now(timezone.utc)
                step_exec.token_usage = {"tokens": 0}
                context["results"][step_exec.step_name] = output
                logger.info(f"子任务步骤 '{step_exec.step_name}' 完成")
                await self._emit_step_completed(task_id, step_exec.step_name)
            elif step_def.type == "loop":
                output = await execute_loop_step(step_def, task, context, db, self._emit_step_completed)
                step_exec.status = StepStatus.COMPLETED.value
                step_exec.output_data = output
                step_exec.completed_at = datetime.now(timezone.utc)
                step_exec.token_usage = {"tokens": 0}
                context["results"][step_exec.step_name] = output
                logger.info(f"循环步骤 '{step_exec.step_name}' 完成, 迭代 {output.get('iterations', 0)} 次")
                await self._emit_step_completed(task_id, step_exec.step_name)
            else:
                await execute_single_step(step_exec, step_def, task, context, db, self._emit_step_completed)
        else:
            logger.info(f"并行执行 {len(group)} 个步骤: {[s[1].name for s in group]}")
            await asyncio.gather(
                *[execute_single_step(se, sd, task, context, db, self._emit_step_completed) for se, sd in group]
            )

    async def _handle_group_failure(
        self,
        group: list[tuple[StepExecution, StepDefinition]],
        task: Task,
        db: AsyncSession,
        task_id: str,
        workflow_name: str,
        error_msg: str,
        timeout: bool = False,
    ):
        """处理步骤组失败（超时或异常）。"""
        for step_exec, step_def in group:
            if step_exec.status != StepStatus.COMPLETED.value:
                step_exec.status = StepStatus.FAILED.value
                step_exec.error_message = f"步骤超时（>{step_def.timeout}s）" if timeout else error_msg
                step_exec.completed_at = datetime.now(timezone.utc)
        task.status = TaskStatus.FAILED.value
        task.error_message = "步骤组超时" if timeout else f"步骤失败: {error_msg}"
        task.completed_at = datetime.now(timezone.utc)
        await db.commit()
        failed_names = [sd.name for se, sd in group if se.status == StepStatus.FAILED.value]
        label = "超时" if timeout else "失败"
        logger.error(f"步骤组{label}: {failed_names}" + (f", 错误: {error_msg}" if not timeout else ""))
        for name in failed_names:
            await self._emit("step_failed", task_id, name, "超时" if timeout else error_msg)
        await self._emit("task_failed", task_id, workflow_name, task.error_message)

        # 断路器：记录失败
        from app.engine.circuit_breaker import circuit_breaker
        await circuit_breaker.record_failure(task.workflow_id, db=db)

    async def _emit_step_completed(self, task_id: str, step_name: str):
        """步骤完成事件。"""
        await self._emit("step_completed", task_id, step_name)

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
