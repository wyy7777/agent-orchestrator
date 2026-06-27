"""ARQ 持久化任务队列：基于 Redis 的异步任务队列。

Phase 3 P0 项：提供任务持久化、崩溃恢复、进度可观察。
在 arq 之上封装了一层，便于与现有引擎集成。

用法：
    # 启动 worker
    python -m app.services.arq_queue

    # 在代码中入队
    from app.services.arq_queue import enqueue_task
    await enqueue_task("execute_workflow", workflow_id="xxx", task_id="yyy")
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings as ArqRedisSettings
from arq.worker import Worker, WorkerSettings

from app.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

# ── Redis 连接池 ──


@asynccontextmanager
async def get_arq_redis() -> AsyncGenerator[ArqRedis, None]:
    """获取 ARQ Redis 连接池。"""
    if not settings.REDIS_URL:
        raise RuntimeError("REDIS_URL 未配置，无法使用任务队列")
    pool = await create_pool(ArqRedisSettings.from_dsn(settings.REDIS_URL))
    try:
        yield pool
    finally:
        await pool.close(close_connection_pool=True)


# ── 任务函数 ──


async def execute_workflow(ctx: dict[str, Any], workflow_id: str, task_id: str) -> dict[str, Any]:
    """执行工作流（作为 ARQ 后台任务）。"""
    logger.info(f"[ARQ] 执行工作流: workflow_id={workflow_id}, task_id={task_id}")
    from app.database import async_session
    from app.engine.state_machine import ExecutionEngine
    from app.engine.yaml_parser import parse_workflow_yaml

    async with async_session() as db:
        engine = ExecutionEngine(db)
        task = await engine.start_task(task_id)
        workflow_def = parse_workflow_yaml(task.workflow.yaml_definition)
        await engine._execute_workflow(task_id, workflow_def)

    return {"status": "completed", "task_id": task_id, "workflow_id": workflow_id}


async def recover_interrupted_tasks(ctx: dict[str, Any]) -> dict[str, Any]:
    """恢复中断的任务（启动时调用）。"""
    logger.info("[ARQ] 恢复中断任务")
    from app.database import async_session
    from app.engine.state_machine import ExecutionEngine

    async with async_session() as db:
        engine = ExecutionEngine(db)
        await engine.recover_orphaned_tasks()
    return {"status": "recovered"}


async def cleanup_expired_data(ctx: dict[str, Any]) -> dict[str, Any]:
    """清理过期数据。"""
    if settings.DATA_RETENTION_DAYS <= 0:
        return {"status": "skipped", "reason": "DATA_RETENTION_DAYS=0"}
    logger.info(f"[ARQ] 清理 {settings.DATA_RETENTION_DAYS} 天前的数据")
    cutoff = datetime.now(UTC)
    from sqlalchemy import delete

    from app.database import async_session
    from app.models.step_execution import StepExecution
    from app.models.task import Task

    async with async_session() as db:
        cutoff_ts = cutoff.timestamp()
        await db.execute(
            delete(StepExecution).where(StepExecution.completed_at < cutoff_ts)
        )
        await db.execute(
            delete(Task).where(Task.completed_at < cutoff_ts)
        )
        await db.commit()
    return {"status": "cleaned", "cutoff": cutoff.isoformat()}


# ── Worker 配置 ──


class WorkerSettings(WorkerSettings):
    """ARQ Worker 配置。"""
    functions = [execute_workflow, recover_interrupted_tasks, cleanup_expired_data]
    redis_settings = ArqRedisSettings.from_dsn(settings.REDIS_URL) if settings.REDIS_URL else None
    poll_delay = 1.0  # 轮询间隔（秒）
    max_burst_jobs = 10
    keep_result = 3600  # 保留结果 1 小时
    keep_result_failed = 86400  # 保留失败结果 1 天


# ── 公开 API ──


async def enqueue_job(job_name: str, **kwargs: Any) -> str | None:
    """将任务入队。返回 job_id。"""
    if not settings.REDIS_URL:
        logger.warning("REDIS_URL 未配置，任务无法入队")
        return None
    async with get_arq_redis() as redis:
        job = await redis.enqueue_job(job_name, **kwargs)
        job_id = job.job_id if job else None
        logger.info(f"[ARQ] 任务入队: {job_name}({kwargs}) → job_id={job_id}")
        return job_id


async def get_job_status(job_id: str) -> dict[str, Any] | None:
    """查询任务状态。"""
    if not settings.REDIS_URL:
        return None
    async with get_arq_redis() as redis:
        job = await redis.get_job(job_id)
        if job is None:
            return None
        result = await job.result(pole_delay=0)
        return {
            "job_id": job_id,
            "status": job.status.name if hasattr(job.status, "name") else str(job.status),
            "result": result,
            "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "score": job.score,
        }


def run_worker():
    """启动 ARQ Worker（阻塞）。"""
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="arq")
    worker = Worker(WorkerSettings)
    logger.info("ARQ Worker 已启动，等待任务...")
    worker.run()


# ── CLI 入口 ──
if __name__ == "__main__":
    run_worker()
