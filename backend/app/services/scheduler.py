"""简单的工作流 Cron 调度器，基于 asyncio 实现。"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from croniter import croniter

logger = logging.getLogger(__name__)


@dataclass
class Schedule:
    id: str
    workflow_id: str
    cron_expr: str
    payload: dict
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_triggered_at: datetime | None = None


class WorkflowScheduler:
    """基于 asyncio 的 Cron 调度器，用于定时触发工作流任务。"""

    def __init__(self):
        self._schedules: dict[str, Schedule] = {}
        self._task: asyncio.Task | None = None
        self._running = False

    def add_schedule(
        self, workflow_id: str, cron_expr: str, payload: dict | None = None
    ) -> Schedule:
        """添加一条调度配置。"""
        if not croniter.is_valid(cron_expr):
            raise ValueError(f"无效的 cron 表达式: {cron_expr}")

        schedule_id = uuid.uuid4().hex[:12]
        schedule = Schedule(
            id=schedule_id,
            workflow_id=workflow_id,
            cron_expr=cron_expr,
            payload=payload or {},
        )
        self._schedules[schedule_id] = schedule
        logger.info(f"已添加调度 {schedule_id}: workflow={workflow_id}, cron={cron_expr}")
        return schedule

    def remove_schedule(self, schedule_id: str) -> bool:
        """移除一条调度配置。"""
        removed = self._schedules.pop(schedule_id, None)
        if removed:
            logger.info(f"已移除调度 {schedule_id}")
            return True
        return False

    def toggle_schedule(self, schedule_id: str, enabled: bool) -> Schedule | None:
        """启用/禁用一条调度配置。"""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return None
        schedule.enabled = enabled
        logger.info(f"调度 {schedule_id} 已{'启用' if enabled else '禁用'}")
        return schedule

    def list_schedules(self) -> list[Schedule]:
        """列出所有调度配置。"""
        return list(self._schedules.values())

    def get_schedule(self, schedule_id: str) -> Schedule | None:
        return self._schedules.get(schedule_id)

    def start_scheduler(self):
        """启动调度循环。"""
        if self._running:
            logger.warning("调度器已在运行中")
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("调度器已启动")

    def stop_scheduler(self):
        """停止调度循环。"""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("调度器已停止")

    async def _run_loop(self):
        """主调度循环：每 30 秒检查一次是否有任务需要触发。"""
        while self._running:
            now = datetime.now(timezone.utc)
            for schedule in list(self._schedules.values()):
                if not schedule.enabled:
                    continue
                try:
                    cron = croniter(schedule.cron_expr, now)
                    prev_fire = cron.get_prev(datetime)
                    # 如果上次触发时间在 30 秒窗口内且尚未触发过
                    diff = (now - prev_fire).total_seconds()
                    if diff < 30 and (
                        schedule.last_triggered_at is None
                        or schedule.last_triggered_at < prev_fire
                    ):
                        await self._trigger_schedule(schedule)
                except Exception as e:
                    logger.error(f"调度 {schedule.id} 检查失败: {e}")

            await asyncio.sleep(30)

    async def _trigger_schedule(self, schedule: Schedule):
        """触发一次调度：创建任务并启动执行。"""
        from app.database import async_session
        from app.models.task import Task
        from app.engine.state_machine import ExecutionEngine
        from app.main import _engine_event_handler

        logger.info(
            f"触发调度 {schedule.id}: workflow={schedule.workflow_id}"
        )
        schedule.last_triggered_at = datetime.now(timezone.utc)

        try:
            async with async_session() as db:
                task = Task(
                    workflow_id=schedule.workflow_id,
                    trigger_type="cron",
                    trigger_payload=schedule.payload,
                )
                db.add(task)
                await db.flush()
                await db.refresh(task)

                engine = ExecutionEngine(db, on_event=_engine_event_handler)
                await engine.start_task(task.id)
                logger.info(f"调度 {schedule.id} 已创建并启动任务 {task.id}")
        except Exception as e:
            logger.error(f"调度 {schedule.id} 触发失败: {e}")


# 全局单例
scheduler = WorkflowScheduler()
