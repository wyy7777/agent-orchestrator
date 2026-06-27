"""断路器测试。"""
from __future__ import annotations

import time

from app.engine.circuit_breaker import CircuitBreaker


class TestCircuitBreaker:
    """断路器核心逻辑测试。"""

    def test_init_defaults(self):
        cb = CircuitBreaker()
        assert cb._threshold == 5
        assert cb._window == 300

    def test_init_custom(self):
        cb = CircuitBreaker(failure_threshold=3, window_seconds=60)
        assert cb._threshold == 3
        assert cb._window == 60

    def test_not_open_initially(self):
        cb = CircuitBreaker()
        assert cb.is_open("wf-123") is False

    async def test_record_single_failure_does_not_open(self):
        cb = CircuitBreaker(failure_threshold=3)
        await cb.record_failure("wf-123")
        assert cb.is_open("wf-123") is False

    async def test_record_threshold_failures_opens(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            await cb.record_failure("wf-123")
        assert cb.is_open("wf-123") is True

    async def test_record_success_resets(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            await cb.record_failure("wf-123")
        assert cb.is_open("wf-123") is True
        await cb.record_success("wf-123")
        assert cb.is_open("wf-123") is False

    async def test_reset_manual(self):
        cb = CircuitBreaker(failure_threshold=2)
        await cb.record_failure("wf-1")
        await cb.record_failure("wf-1")
        assert cb.is_open("wf-1") is True
        cb.reset("wf-1")
        assert cb.is_open("wf-1") is False

    async def test_multiple_workflows_independent(self):
        cb = CircuitBreaker(failure_threshold=2)
        # 工作流 A 失败 2 次
        await cb.record_failure("wf-a")
        await cb.record_failure("wf-a")
        assert cb.is_open("wf-a") is True
        # 工作流 B 仅失败 1 次，不应触发
        await cb.record_failure("wf-b")
        assert cb.is_open("wf-b") is False

    async def test_window_expiration(self):
        cb = CircuitBreaker(failure_threshold=2, window_seconds=1)
        for _ in range(2):
            await cb.record_failure("wf-x")
        assert cb.is_open("wf-x") is True
        # 等待窗口过期
        time.sleep(1.5)
        assert cb.is_open("wf-x") is False

    async def test_old_failures_expire_from_window(self):
        cb = CircuitBreaker(failure_threshold=3, window_seconds=1)
        await cb.record_failure("wf-y")
        time.sleep(0.3)
        await cb.record_failure("wf-y")
        time.sleep(0.8)  # 第一批失败过期
        await cb.record_failure("wf-y")
        # 此时仅剩最近 1 次失败（在窗口内）
        assert cb.is_open("wf-y") is False

    def test_get_status_initial(self):
        cb = CircuitBreaker()
        status = cb.get_status("wf-new")
        assert status["workflow_id"] == "wf-new"
        assert status["is_open"] is False
        assert status["failure_count"] == 0
        assert status["threshold"] == 5

    async def test_get_status_open(self):
        cb = CircuitBreaker(failure_threshold=2)
        await cb.record_failure("wf-z")
        await cb.record_failure("wf-z")
        status = cb.get_status("wf-z")
        assert status["is_open"] is True
        assert status["failure_count"] == 2
        assert status["cooldown_remaining_seconds"] > 0

    async def test_get_status_after_reset(self):
        cb = CircuitBreaker(failure_threshold=2)
        await cb.record_failure("wf-r")
        await cb.record_failure("wf-r")
        cb.reset("wf-r")
        status = cb.get_status("wf-r")
        assert status["is_open"] is False
        assert status["failure_count"] == 0
        assert status["cooldown_remaining_seconds"] == 0

    def test_singleton_instance(self):
        from app.engine.circuit_breaker import circuit_breaker
        assert isinstance(circuit_breaker, CircuitBreaker)
