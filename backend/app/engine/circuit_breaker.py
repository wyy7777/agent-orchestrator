"""断路器：同一工作流连续失败 N 次后自动暂停新任务。"""
from __future__ import annotations

import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """基于时间窗口的断路器。"""

    def __init__(self, failure_threshold: int = 5, window_seconds: int = 300):
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._threshold = failure_threshold
        self._window = window_seconds
        self._open_until: dict[str, float] = {}

    def record_failure(self, workflow_id: str):
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

    def record_success(self, workflow_id: str):
        """记录成功，重置失败计数。"""
        self._failures.pop(workflow_id, None)
        self._open_until.pop(workflow_id, None)

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


# 单例
circuit_breaker = CircuitBreaker()
