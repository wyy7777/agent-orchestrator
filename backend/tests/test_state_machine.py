"""状态机单元测试。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engine.state_machine import (
    ExecutionEngine,
    StepHandler,
    StepStatus,
    TaskStatus,
    _step_handlers,
    register_handler,
)
from app.engine.yaml_parser import StepDefinition, WorkflowDefinition


# ---------- 测试 register_handler ----------


class TestRegisterHandler:
    """测试步骤处理器注册。"""

    def test_register_handler(self):
        """装饰器应正确注册处理器。"""
        @register_handler("test_type")
        class TestHandler(StepHandler):
            async def execute(self, step, context, db):
                return {}

        assert "test_type" in _step_handlers
        assert _step_handlers["test_type"] == TestHandler

        # 清理
        del _step_handlers["test_type"]

    def test_register_multiple_handlers(self):
        """应支持注册多个不同类型处理器。"""
        @register_handler("type_a")
        class HandlerA(StepHandler):
            async def execute(self, step, context, db):
                return {}

        @register_handler("type_b")
        class HandlerB(StepHandler):
            async def execute(self, step, context, db):
                return {}

        assert "type_a" in _step_handlers
        assert "type_b" in _step_handlers
        assert _step_handlers["type_a"] != _step_handlers["type_b"]

        # 清理
        del _step_handlers["type_a"]
        del _step_handlers["type_b"]


# ---------- 测试 StepStatus / TaskStatus ----------


class TestEnums:
    """测试枚举值。"""

    def test_task_status_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.PAUSED.value == "paused"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.ROLLED_BACK.value == "rolled_back"

    def test_step_status_values(self):
        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.RUNNING.value == "running"
        assert StepStatus.WAITING_APPROVAL.value == "waiting_approval"
        assert StepStatus.COMPLETED.value == "completed"
        assert StepStatus.FAILED.value == "failed"
        assert StepStatus.SKIPPED.value == "skipped"


# ---------- 测试 ExecutionEngine ----------


class TestExecutionEngine:
    """测试执行引擎核心逻辑。"""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库 session。"""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def engine(self, mock_db):
        """创建引擎实例。"""
        return ExecutionEngine(mock_db)

    def test_engine_init(self, engine):
        """引擎应正确初始化。"""
        assert engine._running_tasks == {}

    @pytest.mark.asyncio
    async def test_load_task_not_found(self, engine, mock_db):
        """加载不存在的任务应抛出异常。"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="不存在"):
            await engine._load_task("nonexistent-id")

    def test_running_tasks_dict(self, engine):
        """_running_tasks 应为字典。"""
        assert isinstance(engine._running_tasks, dict)
        assert len(engine._running_tasks) == 0


# ---------- 测试 StepDefinition ----------


class TestStepDefinition:
    """测试步骤定义数据类。"""

    def test_basic_step(self):
        """基本步骤定义。"""
        step = StepDefinition(
            name="test",
            type="analyze",
            timeout=120,
            config={"provider": "deepseek"},
        )
        assert step.name == "test"
        assert step.type == "analyze"
        assert step.timeout == 120
        assert step.config == {"provider": "deepseek"}

    def test_parallel_step(self):
        """并行步骤定义。"""
        step = StepDefinition(
            name="parallel_step",
            type="execute",
            parallel=True,
        )
        assert step.parallel is True

    def test_subtask_step(self):
        """子任务步骤定义。"""
        step = StepDefinition(
            name="subtask",
            type="subtask",
            subtask_workflow="wf-123",
        )
        assert step.type == "subtask"
        assert step.subtask_workflow == "wf-123"

    def test_condition_step(self):
        """条件步骤定义。"""
        step = StepDefinition(
            name="conditional",
            type="execute",
            condition="{result.score} > 80",
        )
        assert step.condition == "{result.score} > 80"

    def test_loop_step(self):
        """循环步骤定义。"""
        step = StepDefinition(
            name="loop_step",
            type="loop",
            loop_items="files",
            max_iterations=5,
        )
        assert step.loop_items == "files"
        assert step.max_iterations == 5

    def test_default_values(self):
        """默认值应正确。"""
        step = StepDefinition(name="test", type="analyze")
        assert step.parallel is False
        assert step.condition is None
        assert step.else_steps == []
        assert step.loop_items is None
        assert step.max_iterations == 10
        assert step.subtask_workflow is None
        assert step.timeout == 300  # 默认超时 300 秒
        assert step.config == {}
        assert step.prompt_template is None

    def test_else_steps(self):
        """else 分支步骤定义。"""
        else_step = StepDefinition(name="else_action", type="execute")
        step = StepDefinition(
            name="conditional",
            type="condition",
            condition="{result.score} > 80",
            else_steps=[else_step],
        )
        assert len(step.else_steps) == 1
        assert step.else_steps[0].name == "else_action"


# ---------- 测试条件评估 ----------


class TestConditionEvaluation:
    """测试条件表达式评估。"""

    @pytest.fixture
    def engine(self):
        """创建引擎实例。"""
        db = AsyncMock()
        return ExecutionEngine(db)

    def test_empty_condition(self, engine):
        """空条件应返回 True。"""
        assert engine._evaluate_condition("", {}) is True
        assert engine._evaluate_condition(None, {}) is True

    def test_simple_comparison(self, engine):
        """简单比较。"""
        context = {"result": {"score": 85}}
        assert engine._evaluate_condition("{result.score} > 80", context) is True
        assert engine._evaluate_condition("{result.score} > 90", context) is False

    def test_equality(self, engine):
        """相等比较。"""
        context = {"result": {"status": "approved"}}
        assert engine._evaluate_condition('{result.status} == "approved"', context) is True
        assert engine._evaluate_condition('{result.status} == "rejected"', context) is False

    def test_inequality(self, engine):
        """不等比较。"""
        context = {"result": {"score": 85}}
        assert engine._evaluate_condition("{result.score} != 0", context) is True
        assert engine._evaluate_condition("{result.score} != 85", context) is False

    def test_less_than(self, engine):
        """小于比较。"""
        context = {"result": {"score": 50}}
        assert engine._evaluate_condition("{result.score} < 80", context) is True
        assert engine._evaluate_condition("{result.score} < 30", context) is False

    def test_boolean_condition(self, engine):
        """布尔条件。"""
        context = {"result": {"approved": True}}
        assert engine._evaluate_condition("{result.approved}", context) is True

        context = {"result": {"approved": False}}
        assert engine._evaluate_condition("{result.approved}", context) is False

    def test_and_condition(self, engine):
        """复合条件 (and)。"""
        context = {"result": {"score": 85, "approved": True}}
        assert engine._evaluate_condition("{result.score} > 80 and {result.approved} == true", context) is True
        assert engine._evaluate_condition("{result.score} > 90 and {result.approved} == true", context) is False

    def test_or_condition(self, engine):
        """复合条件 (or)。"""
        context = {"result": {"score": 50, "approved": True}}
        assert engine._evaluate_condition("{result.score} > 80 or {result.approved} == true", context) is True
        assert engine._evaluate_condition("{result.score} > 80 or {result.approved} == false", context) is False

    def test_nested_key(self, engine):
        """嵌套 key。"""
        context = {"data": {"metrics": {"accuracy": 95.5}}}
        assert engine._evaluate_condition("{data.metrics.accuracy} > 90", context) is True

    def test_missing_key(self, engine):
        """缺失的 key 应返回 None。"""
        context = {"result": {}}
        # 缺失的 key 解析为 None，与 None 比较
        assert engine._evaluate_condition("{result.missing} == None", context) is True

    def test_string_comparison(self, engine):
        """字符串比较。"""
        context = {"result": {"verdict": "approve"}}
        assert engine._evaluate_condition('{result.verdict} == "approve"', context) is True
        assert engine._evaluate_condition('{result.verdict} == "reject"', context) is False
