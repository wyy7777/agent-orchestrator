"""Prometheus 指标端点：暴露系统监控指标。"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.database import get_db
from app.models.step_execution import StepExecution
from app.models.task import Task
from app.models.workflow import Workflow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def prometheus_metrics(db: AsyncSession = Depends(get_db)):
    """Prometheus 格式的指标端点。"""
    lines = []

    # 任务指标
    total_tasks = (await db.execute(select(func.count(Task.id)))).scalar() or 0
    completed_tasks = (await db.execute(
        select(func.count(Task.id)).where(Task.status == "completed")
    )).scalar() or 0
    failed_tasks = (await db.execute(
        select(func.count(Task.id)).where(Task.status == "failed")
    )).scalar() or 0
    running_tasks = (await db.execute(
        select(func.count(Task.id)).where(Task.status == "running")
    )).scalar() or 0

    lines.append("# HELP agent_orchestrator_tasks_total Total number of tasks")
    lines.append("# TYPE agent_orchestrator_tasks_total gauge")
    lines.append(f"agent_orchestrator_tasks_total {total_tasks}")

    lines.append("# HELP agent_orchestrator_tasks_completed Completed tasks")
    lines.append("# TYPE agent_orchestrator_tasks_completed gauge")
    lines.append(f"agent_orchestrator_tasks_completed {completed_tasks}")

    lines.append("# HELP agent_orchestrator_tasks_failed Failed tasks")
    lines.append("# TYPE agent_orchestrator_tasks_failed gauge")
    lines.append(f"agent_orchestrator_tasks_failed {failed_tasks}")

    lines.append("# HELP agent_orchestrator_tasks_running Running tasks")
    lines.append("# TYPE agent_orchestrator_tasks_running gauge")
    lines.append(f"agent_orchestrator_tasks_running {running_tasks}")

    # Token 指标
    total_tokens = (await db.execute(
        select(func.coalesce(func.sum(Task.total_tokens_used), 0))
    )).scalar() or 0

    lines.append("# HELP agent_orchestrator_tokens_total Total tokens consumed")
    lines.append("# TYPE agent_orchestrator_tokens_total counter")
    lines.append(f"agent_orchestrator_tokens_total {total_tokens}")

    # 工作流指标
    total_workflows = (await db.execute(select(func.count(Workflow.id)))).scalar() or 0

    lines.append("# HELP agent_orchestrator_workflows_total Total workflows")
    lines.append("# TYPE agent_orchestrator_workflows_total gauge")
    lines.append(f"agent_orchestrator_workflows_total {total_workflows}")

    # 步骤执行指标
    total_steps = (await db.execute(select(func.count(StepExecution.id)))).scalar() or 0
    completed_steps = (await db.execute(
        select(func.count(StepExecution.id)).where(StepExecution.status == "completed")
    )).scalar() or 0
    failed_steps = (await db.execute(
        select(func.count(StepExecution.id)).where(StepExecution.status == "failed")
    )).scalar() or 0

    lines.append("# HELP agent_orchestrator_steps_total Total step executions")
    lines.append("# TYPE agent_orchestrator_steps_total gauge")
    lines.append(f"agent_orchestrator_steps_total {total_steps}")

    lines.append("# HELP agent_orchestrator_steps_completed Completed steps")
    lines.append("# TYPE agent_orchestrator_steps_completed gauge")
    lines.append(f"agent_orchestrator_steps_completed {completed_steps}")

    lines.append("# HELP agent_orchestrator_steps_failed Failed steps")
    lines.append("# TYPE agent_orchestrator_steps_failed gauge")
    lines.append(f"agent_orchestrator_steps_failed {failed_steps}")

    # 时间戳
    lines.append("# HELP agent_orchestrator_last_scrape_timestamp Last scrape timestamp")
    lines.append("# TYPE agent_orchestrator_last_scrape_timestamp gauge")
    lines.append(f"agent_orchestrator_last_scrape_timestamp {int(time.time())}")

    return "\n".join(lines) + "\n"
