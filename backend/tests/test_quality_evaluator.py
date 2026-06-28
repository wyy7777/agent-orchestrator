"""QualityEvaluator 测试：AI 质量评分服务。

覆盖场景：
- 支持分析的步骤类型评分
- 不支持的步骤类型跳过
- Agent 调用失败时的容错
- 评分范围验证（0-10）
- JSON 解析边界情况
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.quality_evaluator import QualityEvaluator


@pytest.fixture
def evaluator() -> QualityEvaluator:
    return QualityEvaluator()


@pytest.mark.asyncio
class TestQualityEvaluator:
    """AI 质量评分器测试。"""

    async def test_evaluate_execute_step(self, evaluator: QualityEvaluator):
        """execute 步骤应正确评分。"""
        mock_agent = AsyncMock()
        mock_agent.run.return_value.content = """{
            "correctness": 8,
            "completeness": 7,
            "security": 9,
            "style": 6,
            "summary": "代码质量良好，安全性高。"
        }"""

        with patch("app.services.quality_evaluator.get_agent", return_value=mock_agent):
            result = await evaluator.evaluate(
                step_type="execute",
                output={"result": "ok", "code": "def foo(): pass"},
                context={"task_id": "123"},
            )

        assert result["correctness"] == 8
        assert result["completeness"] == 7
        assert result["security"] == 9
        assert result["style"] == 6
        assert "代码质量良好" in result["summary"]

    async def test_evaluate_review_step(self, evaluator: QualityEvaluator):
        """review 步骤应正确评分。"""
        mock_agent = AsyncMock()
        mock_agent.run.return_value.content = """{
            "correctness": 10,
            "completeness": 10,
            "security": 10,
            "style": 10,
            "summary": "完美"
        }"""

        with patch("app.services.quality_evaluator.get_agent", return_value=mock_agent):
            result = await evaluator.evaluate(
                step_type="review",
                output={"findings": ["typo", "bug"]},
                context={"task_id": "456"},
            )

        assert result["correctness"] == 10
        assert result["summary"] == "完美"

    async def test_skip_unsupported_step_type(self, evaluator: QualityEvaluator):
        """不支持的步骤类型应返回 skipped。"""
        result = await evaluator.evaluate(
            step_type="notify",
            output={},
            context={},
        )

        assert result["skipped"] is True
        assert "不需要评分" in result["reason"]

    async def test_skip_script_step_type(self, evaluator: QualityEvaluator):
        """script 步骤也应跳过。"""
        result = await evaluator.evaluate(
            step_type="script",
            output={"stdout": "done"},
            context={},
        )

        assert result["skipped"] is True

    async def test_agent_call_failure(self, evaluator: QualityEvaluator):
        """Agent 调用失败应返回 -1 评分和错误信息。"""
        mock_agent = AsyncMock()
        mock_agent.run.side_effect = RuntimeError("API 不可用")

        with patch("app.services.quality_evaluator.get_agent", return_value=mock_agent):
            result = await evaluator.evaluate(
                step_type="execute",
                output={"result": "data"},
                context={"task_id": "789"},
            )

        assert result["correctness"] == -1
        assert result["completeness"] == -1
        assert result["security"] == -1
        assert result["style"] == -1
        assert "API 不可用" in result["error"]

    async def test_invalid_json_response(self, evaluator: QualityEvaluator):
        """Agent 返回非法 JSON 应返回 -1 评分。"""
        mock_agent = AsyncMock()
        mock_agent.run.return_value.content = "不是 JSON"

        with patch("app.services.quality_evaluator.get_agent", return_value=mock_agent):
            result = await evaluator.evaluate(
                step_type="execute",
                output={"result": "data"},
                context={"task_id": "abc"},
            )

        assert result["correctness"] == -1
        assert result["error"] != ""

    async def test_out_of_range_scores_are_clamped(self, evaluator: QualityEvaluator):
        """超出 0-10 范围的评分应被钳制为 -1。"""
        mock_agent = AsyncMock()
        mock_agent.run.return_value.content = """{
            "correctness": 15,
            "completeness": -2,
            "security": 0,
            "style": 10,
            "summary": "评分异常"
        }"""

        with patch("app.services.quality_evaluator.get_agent", return_value=mock_agent):
            result = await evaluator.evaluate(
                step_type="execute",
                output={"result": "data"},
                context={"task_id": "abc"},
            )

        assert result["correctness"] == -1  # 15 > 10
        assert result["completeness"] == -1  # -2 < 0
        assert result["security"] == 0  # 0 在范围内
        assert result["style"] == 10  # 10 在范围内

    async def test_missing_summary_field(self, evaluator: QualityEvaluator):
        """缺少 summary 字段应填充空字符串。"""
        mock_agent = AsyncMock()
        mock_agent.run.return_value.content = """{
            "correctness": 7,
            "completeness": 6,
            "security": 8,
            "style": 5
        }"""

        with patch("app.services.quality_evaluator.get_agent", return_value=mock_agent):
            result = await evaluator.evaluate(
                step_type="execute",
                output={"result": "data"},
                context={"task_id": "xyz"},
            )

        assert result["correctness"] == 7
        assert result["summary"] == ""

    async def test_summary_truncated(self, evaluator: QualityEvaluator):
        """summary 超过 500 字符应截断。"""
        long_summary = "a" * 1000
        mock_agent = AsyncMock()
        mock_agent.run.return_value.content = f"""{{
            "correctness": 5,
            "completeness": 5,
            "security": 5,
            "style": 5,
            "summary": "{long_summary}"
        }}"""

        with patch("app.services.quality_evaluator.get_agent", return_value=mock_agent):
            result = await evaluator.evaluate(
                step_type="execute",
                output={"result": "data"},
                context={"task_id": "xyz"},
            )

        assert len(result["summary"]) == 500

    async def test_analyze_step_also_scored(self, evaluator: QualityEvaluator):
        """analyze 步骤也应支持评分。"""
        mock_agent = AsyncMock()
        mock_agent.run.return_value.content = """{
            "correctness": 9,
            "completeness": 8,
            "security": 7,
            "style": 6,
            "summary": "分析全面"
        }"""

        with patch("app.services.quality_evaluator.get_agent", return_value=mock_agent):
            result = await evaluator.evaluate(
                step_type="analyze",
                output={"analysis": "test"},
                context={"task_id": "xyz"},
            )

        assert result["correctness"] == 9
        assert "分析全面" in result["summary"]
