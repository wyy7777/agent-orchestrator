"""步骤执行器测试：重试、超时、fallback 逻辑。"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engine.step_executor import (
    _execute_with_retry,
    execute_single_step,
    execute_loop_step,
    execute_subtask_step,
)
from app.engine.types import StepHandler, StepStatus
from app.engine.yaml_parser import StepDefinition, RetryConfig


# ── Retry 逻辑 ──


class TestRetryWithBackoff:
    @pytest.mark.asyncio
    async def test_first_attempt_succeeds(self):
        async def make_call():
            return "ok"

        step_def = StepDefinition(
            name="test", type="analyze",
            retry=RetryConfig(max_attempts=3, backoff="linear", backoff_seconds=0.01, on_failure="fail"),
        )
        step_exec = MagicMock()

        result = await _execute_with_retry(make_call, step_def, step_exec)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retry_then_succeed(self):
        call_count = 0

        async def make_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "recovered"

        step_def = StepDefinition(
            name="test", type="analyze",
            retry=RetryConfig(max_attempts=3, backoff="linear", backoff_seconds=0.01, on_failure="fail"),
        )
        step_exec = MagicMock()

        result = await _execute_with_retry(make_call, step_def, step_exec)
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises(self):
        async def make_call():
            raise ValueError("always fail")

        step_def = StepDefinition(
            name="test", type="analyze",
            retry=RetryConfig(max_attempts=1, backoff="linear", backoff_seconds=0.01, on_failure="fail"),
        )
        step_exec = MagicMock()

        with pytest.raises(ValueError, match="always fail"):
            await _execute_with_retry(make_call, step_def, step_exec)

    @pytest.mark.asyncio
    async def test_retry_on_failure_skip(self):
        call_count = 0

        async def make_call():
            nonlocal call_count
            call_count += 1
            raise ValueError("skip me")

        step_def = StepDefinition(
            name="test",
            type="analyze",
            retry=RetryConfig(max_attempts=2, backoff="linear", backoff_seconds=0.01, on_failure="skip"),
        )
        step_exec = MagicMock()

        result = await _execute_with_retry(make_call, step_def, step_exec)
        assert result["status"] == "skipped"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_failure_fallback(self):
        async def make_call():
            raise ValueError("fallback me")

        step_def = StepDefinition(
            name="test",
            type="analyze",
            retry=RetryConfig(max_attempts=1, backoff="linear", backoff_seconds=0.01, on_failure="fallback"),
        )
        step_exec = MagicMock()

        result = await _execute_with_retry(make_call, step_def, step_exec)
        assert result["status"] == "fallback"


# ── execute_single_step ──


class TestExecuteSingleStep:
    @pytest.mark.asyncio
    async def test_no_handler_no_plugin(self):
        """无 handler 且无 plugin 时返回 auto_completed。"""
        from app.engine.types import _step_handlers

        step_def = StepDefinition(name="test", type="unknown_type")
        step_exec = MagicMock()
        step_exec.step_name = "test"
        task = MagicMock()
        task.total_tokens_used = 0
        context = {"task_id": "task-1", "results": {}}
        db = AsyncMock()

        assert "unknown_type" not in _step_handlers

        result = await execute_single_step(step_exec, step_def, task, context, db)
        assert result == {"status": "auto_completed"}

    @pytest.mark.asyncio
    async def test_register_and_execute_handler(self):
        """注册一个假 handler 类（非实例）并验证调用。"""
        from app.engine.types import _step_handlers

        class FakeHandler(StepHandler):
            async def execute(self, step, ctx, db):
                return {"fake": True, "tokens_used": 10}

        _step_handlers["fake_type"] = FakeHandler  # 注册类，不是实例

        try:
            step_def = StepDefinition(name="test", type="fake_type")
            step_exec = MagicMock()
            step_exec.step_name = "test"
            task = MagicMock()
            task.total_tokens_used = 0
            context = {"task_id": "task-1", "results": {}}
            db = AsyncMock()

            result = await execute_single_step(step_exec, step_def, task, context, db)
            assert result == {"fake": True, "tokens_used": 10}
        finally:
            del _step_handlers["fake_type"]


# ── 超时 ──


class TestStepTimeout:
    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        """步骤超时应该抛出 asyncio.TimeoutError。"""
        from app.engine.types import _step_handlers

        class SlowHandler(StepHandler):
            async def execute(self, step, ctx, db):
                await asyncio.sleep(10)
                return {"done": True}

        _step_handlers["slow_type"] = SlowHandler  # 注册类，不是实例

        try:
            step_def = StepDefinition(name="test", type="slow_type", timeout=0.1)
            step_exec = MagicMock()
            step_exec.step_name = "test"
            task = MagicMock()
            task.total_tokens_used = 0
            context = {"task_id": "task-1", "results": {}}
            db = AsyncMock()

            with pytest.raises(asyncio.TimeoutError):
                await execute_single_step(step_exec, step_def, task, context, db)
        finally:
            del _step_handlers["slow_type"]


# ── execute_loop_step ──


class TestLoopStep:
    @pytest.mark.asyncio
    async def test_loop_no_items_key(self):
        """循环步骤 items_key 不存在于 context 时抛出异常。"""
        step_def = StepDefinition(
            name="循环",
            type="loop",
            config={"items_key": "missing_items"},
            steps=[StepDefinition(name="sub1", type="script", config={"command": "echo x"})],
        )
        task = MagicMock()
        context = {"task_id": "task-1", "results": {}}
        db = AsyncMock()

        with pytest.raises(ValueError, match="未找到或不是列表"):
            await execute_loop_step(step_def, task, context, db)

    @pytest.mark.asyncio
    async def test_loop_empty_list(self):
        """空列表应返回 0 次迭代。"""
        step_def = StepDefinition(
            name="循环",
            type="loop",
            config={"items_key": "items"},
            steps=[StepDefinition(name="sub1", type="script", config={"command": "echo x"})],
        )
        task = MagicMock()
        context = {"task_id": "task-1", "results": {}, "items": []}
        db = AsyncMock()

        result = await execute_loop_step(step_def, task, context, db)
        assert result["status"] == "loop_completed"
        assert result["iterations"] == 0

    @pytest.mark.asyncio
    async def test_loop_no_sub_steps(self):
        """无子步骤时抛出异常。"""
        step_def = StepDefinition(
            name="循环",
            type="loop",
            config={"items_key": "items"},
            steps=None,
        )
        task = MagicMock()
        context = {"task_id": "task-1", "items": [1, 2, 3]}
        db = AsyncMock()

        with pytest.raises(ValueError, match="未定义子步骤"):
            await execute_loop_step(step_def, task, context, db)


# ── execute_subtask_step ──


class TestSubtaskStep:
    @pytest.mark.asyncio
    async def test_subtask_missing_child_workflow_id(self):
        step_def = StepDefinition(name="子任务", type="subtask", config={})
        context = {"task_id": "parent-1"}
        db = AsyncMock()

        with pytest.raises(ValueError, match="缺少 config.child_workflow_id"):
            await execute_subtask_step(step_def, context, db, None)

    @pytest.mark.asyncio
    async def test_subtask_workflow_not_found(self):
        step_def = StepDefinition(
            name="子任务",
            type="subtask",
            config={"child_workflow_id": "nonexistent"},
        )
        context = {"task_id": "parent-1"}
        db = AsyncMock()
        db.get.return_value = None  # workflow not found

        with pytest.raises(ValueError, match="不存在"):
            await execute_subtask_step(step_def, context, db, None)
