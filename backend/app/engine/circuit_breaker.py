"""断路器：同一工作流连续失败 N 次后自动暂停新任务。
使用数据库持久化状态，内存缓存加速读取。"""
from __future__ import annotations

import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """基于时间窗口的断路器，DB 持久化 + 内存缓存。"""

    def __init__(self, failure_threshold: int = 5, window_seconds: int = 300):
        # 内存缓存（读加速层）
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._threshold = failure_threshold
        self._window = window_seconds
        self._open_until: dict[str, float] = {}
        self._db_restored = False

    async def restore_from_db(self, db):
        """启动时从数据库恢复断路器状态。"""
        try:
            from sqlalchemy import select

            from app.models.circuit_breaker import CircuitBreakerState

            result = await db.execute(select(CircuitBreakerState))
            states = result.scalars().all()
            now = time.time()

            for state in states:
                if state.open_until and state.open_until > now:
                    # 冷却期未结束，恢复 open_until
                    self._open_until[state.workflow_id] = state.open_until
                    logger.info(
                        f"断路器恢复(冷却中): workflow={state.workflow_id}, "
                        f"剩余 {int(state.open_until - now)}s"
                    )
                elif state.failure_count > 0:
                    # 有失败记录但不在冷却期，恢复失败计数
                    # 使用近似时间戳重建时间线
                    self._failures[state.workflow_id] = [now - i * 10 for i in range(state.failure_count)]
                    logger.info(
                        f"断路器恢复: workflow={state.workflow_id}, "
                        f"失败 {state.failure_count} 次"
                    )

            self._db_restored = True
            logger.info(f"断路器状态已从 DB 恢复: {len(states)} 条记录")
        except Exception as e:
            logger.warning(f"断路器 DB 恢复失败（将使用空状态）: {e}")
            self._db_restored = True

    async def record_failure(self, workflow_id: str, db=None):
        """记录一次失败。"""
        now = time.time()
        # 清理过期记录
        self._failures[workflow_id] = [
            t for t in self._failures[workflow_id] if now - t < self._window
        ]
        self._failures[workflow_id].append(now)

        if len(self._failures[workflow_id]) >= self._threshold:
            self._open_until[workflow_id] = now + self._window
            logger.warning(
                f"断路器打开: workflow={workflow_id}, "
                f"失败 {len(self._failures[workflow_id])} 次, "
                f"暂停 {self._window}s"
            )

        # 持久化到 DB
        if db:
            await self._persist(workflow_id, db)

    def is_open(self, workflow_id: str) -> bool:
        """检查断路器是否打开（是否应拒绝新任务）。"""
        now = time.time()

        # 检查是否在冷却期
        if workflow_id in self._open_until:
            if now < self._open_until[workflow_id]:
                return True
            else:
                # 冷却期结束，重置
                del self._open_until[workflow_id]
                self._failures.pop(workflow_id, None)
                logger.info(f"断路器关闭: workflow={workflow_id}")
                return False

        # 检查窗口内失败次数
        self._failures[workflow_id] = [
            t for t in self._failures[workflow_id] if now - t < self._window
        ]
        return len(self._failures[workflow_id]) >= self._threshold

    async def record_success(self, workflow_id: str, db=None):
        """记录成功，重置失败计数。"""
        self._failures.pop(workflow_id, None)
        self._open_until.pop(workflow_id, None)

        # 持久化到 DB
        if db:
            await self._persist(workflow_id, db)

    def reset(self, workflow_id: str):
        """手动重置断路器。"""
        self._failures.pop(workflow_id, None)
        self._open_until.pop(workflow_id, None)
        logger.info(f"断路器手动重置: workflow={workflow_id}")

    def get_status(self, workflow_id: str) -> dict:
        """获取断路器状态。"""
        now = time.time()
        is_open = self.is_open(workflow_id)
        failures = self._failures.get(workflow_id, [])
        remaining = 0
        if workflow_id in self._open_until and now < self._open_until[workflow_id]:
            remaining = int(self._open_until[workflow_id] - now)

        return {
            "workflow_id": workflow_id,
            "is_open": is_open,
            "failure_count": len(failures),
            "threshold": self._threshold,
            "cooldown_remaining_seconds": remaining,
        }

    async def _persist(self, workflow_id: str, db):
        """将当前状态持久化到数据库。"""
        try:
            from sqlalchemy import select

            from app.models.circuit_breaker import CircuitBreakerState

            result = await db.execute(
                select(CircuitBreakerState).where(
                    CircuitBreakerState.workflow_id == workflow_id
                )
            )
            state = result.scalar_one_or_none()

            now = time.time()
            # 清理过期记录
            self._failures[workflow_id] = [
                t for t in self._failures[workflow_id] if now - t < self._window
            ]
            failure_count = len(self._failures[workflow_id])
            open_until = self._open_until.get(workflow_id)

            if state is None:
                state = CircuitBreakerState(
                    workflow_id=workflow_id,
                    failure_count=failure_count,
                    open_until=open_until,
                )
                db.add(state)
            else:
                state.failure_count = failure_count
                state.open_until = open_until

            await db.flush()
        except Exception as e:
            logger.warning(f"断路器持久化失败: {e}")


# 单例
circuit_breaker = CircuitBreaker()
