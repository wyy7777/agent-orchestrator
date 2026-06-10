from __future__ import annotations

import asyncio
import logging
import operator
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.services.notifier import notifier
from app.models.approval import Approval
from app.models.step_execution import StepExecution
from app.models.task import Task
from app.models.workflow import Workflow
from app.engine.plugin import get_plugin
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

    # 条件表达式运算符映射
    _OPERATORS = {
        ">": operator.gt,
        ">=": operator.ge,
        "<": operator.lt,
        "<=": operator.le,
        "==": operator.eq,
        "!=": operator.ne,
    }

    def _evaluate_condition(self, condition: str, context: dict[str, Any]) -> bool:
        """
        评估条件表达式。

        支持的语法:
        - 比较: {result.score} > 80
        - 存在性: {result.pr_url}
        - 布尔: {result.approved} == true
        - 复合: {result.score} > 80 and {result.approved} == true
        """
        if not condition:
            return True

        # 替换上下文变量 {key.path}
        def resolve_var(match: re.Match) -> str:
            var_path = match.group(1).strip()
            value = context
            for key in var_path.split("."):
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    value = None
                    break
            if value is None:
                return "None"
            if isinstance(value, bool):
                return str(value).lower()
            if isinstance(value, (int, float)):
                return str(value)
            if isinstance(value, str):
                return f'"{value}"'
            return str(value)

        expr = re.sub(r"\{([^}]+)\}", resolve_var, condition)

        # 处理复合条件 (and/or)
        if " and " in expr:
            parts = expr.split(" and ")
            return all(self._evaluate_single_condition(p.strip()) for p in parts)
        if " or " in expr:
            parts = expr.split(" or ")
            return any(self._evaluate_single_condition(p.strip()) for p in parts)

        return self._evaluate_single_condition(expr)

    def _evaluate_single_condition(self, expr: str) -> bool:
        """评估单个条件表达式。"""
        expr = expr.strip()

        # 尝试解析比较表达式（优先于存在性检查）
        for op_str, op_func in self._OPERATORS.items():
            if op_str in expr:
                left, right = expr.split(op_str, 1)
                left = left.strip().strip('"')
                right = right.strip().strip('"')
                try:
                    left_val = float(left) if left != "None" else None
                    right_val = float(right) if right != "None" else None
                    if left_val is not None and right_val is not None:
                        return op_func(left_val, right_val)
                except (ValueError, TypeError):
                    pass
                # 字符串比较
                if left == "None":
                    return right == "None"
                if right == "None":
                    return False
                return op_func(left, right)

        # 存在性检查 (truthy)
        if expr.lower() == "true":
            return True
        if expr.lower() in ("false", "none", "null", "0", "no", ""):
            return False
        if expr.startswith('"') and expr.endswith('"'):
            return bool(expr[1:-1])

        # 默认为真（非空字符串）
        return bool(expr)

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

        # 通知：任务开始
        await notifier.notify_task_started(task_id, workflow_def.name)

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

    async def _execute_single_step(
        self,
        step_exec: StepExecution,
        step_def: StepDefinition,
        task: Task,
        context: dict[str, Any],
        db: AsyncSession,
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
        await notifier.notify_step_completed(context["task_id"], step_exec.step_name)
        return output

    async def _execute_subtask_step(
        self,
        step_def: StepDefinition,
        context: dict[str, Any],
        db: AsyncSession,
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
        await self._execute_workflow(child_task.id, child_workflow_def)

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

    async def _execute_loop_step(
        self,
        step_def: StepDefinition,
        task: Task,
        context: dict[str, Any],
        db: AsyncSession,
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
                    step_index=-1,  # 循环子步骤无固定索引
                    step_name=f"{step_def.name}[{idx}].{sub_def.name}",
                    step_type=sub_def.type,
                    status=StepStatus.RUNNING.value,
                    started_at=datetime.now(timezone.utc),
                )
                db.add(sub_step_exec)
                await db.flush()

                try:
                    output = await self._execute_single_step(
                        sub_step_exec, sub_def, task, iteration_context, db
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

    async def _execute_workflow(self, task_id: str, workflow_def: WorkflowDefinition):
        """核心执行循环。支持并行步骤、子任务和循环步骤。"""
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

                # 将步骤分组：连续的并行步骤归为一组，其余单独为组
                # 同时检查条件步骤
                step_groups: list[list[tuple[StepExecution, StepDefinition]]] = []
                current_group: list[tuple[StepExecution, StepDefinition]] = []

                for step_exec in steps:
                    step_def = workflow_def.steps[step_exec.step_index]

                    if step_exec.status == StepStatus.COMPLETED.value:
                        # 已完成步骤：清空当前组（之前步骤都已完成）
                        current_group = []
                        continue

                    # 条件检查
                    if step_def.condition:
                        condition_result = self._evaluate_condition(step_def.condition, context)
                        if not condition_result:
                            # 条件不满足，跳过此步骤
                            step_exec.status = StepStatus.SKIPPED.value
                            step_exec.output_data = {"skipped": True, "reason": f"条件不满足: {step_def.condition}"}
                            step_exec.completed_at = datetime.now(timezone.utc)
                            logger.info(f"步骤 '{step_exec.step_name}' 被跳过 (条件不满足: {step_def.condition})")

                            # 执行 else 分支（如果有）
                            if step_def.else_steps:
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
                                        output = await self._execute_single_step(
                                            else_exec, else_step_def, task, context, db
                                        )
                                        context["results"][else_exec.step_name] = output
                                    except Exception as e:
                                        else_exec.status = StepStatus.FAILED.value
                                        else_exec.error_message = str(e)
                                        else_exec.completed_at = datetime.now(timezone.utc)
                                        logger.error(f"else 分支步骤 '{else_step_def.name}' 失败: {e}")
                            continue

                    if step_def.parallel and current_group and workflow_def.steps[current_group[-1][0].step_index].parallel:
                        # 前一个也是并行步骤，归入同一组
                        current_group.append((step_exec, step_def))
                    else:
                        # 非并行或并行序列的开始
                        if current_group:
                            step_groups.append(current_group)
                        current_group = [(step_exec, step_def)]

                if current_group:
                    step_groups.append(current_group)

                # 逐组执行
                for group in step_groups:
                    # 检查 token 限额
                    if task.total_tokens_used >= settings.MAX_TOKENS_PER_TASK:
                        raise RuntimeError(
                            f"Token 消耗已达上限 ({settings.MAX_TOKENS_PER_TASK})"
                        )

                    # 审批检查（审批步骤不参与并行）
                    for step_exec, step_def in group:
                        if step_def.type == "approval":
                            step_exec.status = StepStatus.WAITING_APPROVAL.value
                            step_exec.started_at = datetime.now(timezone.utc)
                            task.status = TaskStatus.PAUSED.value
                            task.current_step_index = step_exec.step_index

                            approval = Approval(
                                step_execution_id=step_exec.id,
                                status="pending",
                            )
                            db.add(approval)
                            await db.commit()
                            logger.info(f"任务 {task_id} 在步骤 '{step_exec.step_name}' 等待审批")
                            await notifier.notify_approval_needed(task_id, step_exec.step_name)
                            return

                    # 标记组内所有步骤为 running
                    for step_exec, step_def in group:
                        step_exec.status = StepStatus.RUNNING.value
                        step_exec.started_at = datetime.now(timezone.utc)
                        task.current_step_index = step_exec.step_index
                    await db.commit()

                    try:
                        if len(group) == 1:
                            # 单步骤，直接执行
                            step_exec, step_def = group[0]

                            if step_def.type == "subtask":
                                output = await self._execute_subtask_step(step_def, context, db)
                                step_exec.status = StepStatus.COMPLETED.value
                                step_exec.output_data = output
                                step_exec.completed_at = datetime.now(timezone.utc)
                                step_exec.token_usage = {"tokens": 0}
                                context["results"][step_exec.step_name] = output
                                logger.info(f"子任务步骤 '{step_exec.step_name}' 完成")
                                await notifier.notify_step_completed(task_id, step_exec.step_name)
                            elif step_def.type == "loop":
                                output = await self._execute_loop_step(step_def, task, context, db)
                                step_exec.status = StepStatus.COMPLETED.value
                                step_exec.output_data = output
                                step_exec.completed_at = datetime.now(timezone.utc)
                                step_exec.token_usage = {"tokens": 0}
                                context["results"][step_exec.step_name] = output
                                logger.info(f"循环步骤 '{step_exec.step_name}' 完成, 迭代 {output.get('iterations', 0)} 次")
                                await notifier.notify_step_completed(task_id, step_exec.step_name)
                            else:
                                await self._execute_single_step(
                                    step_exec, step_def, task, context, db
                                )
                        else:
                            # 多步骤并行
                            logger.info(f"并行执行 {len(group)} 个步骤: {[s[1].name for s in group]}")

                            async def _run_parallel_step(
                                se: StepExecution, sd: StepDefinition
                            ) -> dict[str, Any]:
                                return await self._execute_single_step(
                                    se, sd, task, context, db
                                )

                            await asyncio.gather(
                                *[_run_parallel_step(se, sd) for se, sd in group]
                            )

                    except asyncio.TimeoutError:
                        # 标记组内所有未完成步骤为 failed
                        for step_exec, step_def in group:
                            if step_exec.status != StepStatus.COMPLETED.value:
                                step_exec.status = StepStatus.FAILED.value
                                step_exec.error_message = f"步骤超时（>{step_def.timeout}s）"
                                step_exec.completed_at = datetime.now(timezone.utc)
                        task.status = TaskStatus.FAILED.value
                        task.error_message = f"步骤组超时"
                        task.completed_at = datetime.now(timezone.utc)
                        await db.commit()
                        failed_names = [sd.name for se, sd in group if se.status == StepStatus.FAILED.value]
                        logger.error(f"步骤组超时: {failed_names}")
                        for name in failed_names:
                            await notifier.notify_step_failed(task_id, name, "超时")
                        await notifier.notify_task_failed(task_id, workflow_def.name, "步骤组超时")
                        return
                    except Exception as e:
                        for step_exec, step_def in group:
                            if step_exec.status != StepStatus.COMPLETED.value:
                                step_exec.status = StepStatus.FAILED.value
                                step_exec.error_message = str(e)
                                step_exec.completed_at = datetime.now(timezone.utc)
                        task.status = TaskStatus.FAILED.value
                        task.error_message = f"步骤失败: {e}"
                        task.completed_at = datetime.now(timezone.utc)
                        await db.commit()
                        failed_names = [sd.name for se, sd in group if se.status == StepStatus.FAILED.value]
                        logger.error(f"步骤组失败: {failed_names}, 错误: {e}")
                        for name in failed_names:
                            await notifier.notify_step_failed(task_id, name, str(e))
                        await notifier.notify_task_failed(task_id, workflow_def.name, str(e))
                        return

                    await db.commit()

                # 所有步骤完成
                task.status = TaskStatus.COMPLETED.value
                task.completed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info(f"任务 {task_id} 完成")
                await notifier.notify_task_completed(task_id, workflow_def.name)

        except Exception as e:
            logger.error(f"工作流执行异常: {e}", exc_info=True)
            try:
                async with async_session() as db:
                    result = await db.execute(
                        select(Task).where(Task.id == task_id)
                    )
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
