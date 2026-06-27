"""AI Handler mock 测试：不依赖真实 API 测试所有处理器逻辑。"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.base import AgentResponse
from app.agents.executor import (
    AnalyzeHandler,
    ConditionHandler,
    ExecuteHandler,
    LoopHandler,
    MergeHandler,
    ReviewHandler,
    ScriptHandler,
    SubtaskHandler,
)
from app.engine.types import StepResult
from app.engine.yaml_parser import StepDefinition

# ── 辅助函数 ──

def make_step(name: str, type_: str, **kwargs) -> StepDefinition:
    """快速创建 StepDefinition。"""
    return StepDefinition(name=name, type=type_, **kwargs)


def make_agent_response(content: str, parsed: dict | None = None, tokens: int = 100):
    """创建模拟 Agent 响应。"""
    return AgentResponse(
        content=content,
        tokens_used=tokens,
        model="test-model",
        parsed=parsed,
    )


# ── AnalyzeHandler ──


class TestAnalyzeHandler:
    @pytest.mark.asyncio
    async def test_analyze_basic(self):
        handler = AnalyzeHandler()
        step = make_step("分析", "analyze", config={"provider": "deepseek"})
        context = {"trigger_payload": {"issue_body": "bug: login fails", "code_context": "def login(): pass"}}

        mock_resp = make_agent_response(
            '{"analysis":"fixed","root_cause":"typo","solution":"fix typo","files_to_modify":[],'
            '"risk_assessment":"low","estimated_effort":"small"}',
            parsed={"analysis": "fixed"},
        )

        with patch("app.agents.executor.get_agent") as mock_get:
            mock_agent = AsyncMock()
            mock_agent.run.return_value = mock_resp
            mock_get.return_value = mock_agent

            result = await handler.execute(step, context, None)

        assert isinstance(result, StepResult)
        assert result.status == "completed"
        assert "analysis" in result.output
        assert result.tokens_used == 100
        assert result.model == "test-model"

    @pytest.mark.asyncio
    async def test_analyze_default_provider_on_missing(self):
        handler = AnalyzeHandler()
        step = make_step("分析", "analyze")  # 无 config
        context = {"trigger_payload": {"input": "test"}}

        mock_resp = make_agent_response(
            '{"analysis":"ok","root_cause":"x","solution":"y","files_to_modify":[],'
            '"risk_assessment":"low","estimated_effort":"small"}'
        )

        with patch("app.agents.executor.get_agent") as mock_get:
            mock_agent = AsyncMock()
            mock_agent.run.return_value = mock_resp
            mock_get.return_value = mock_agent

            result = await handler.execute(step, context, None)

        # 默认 provider 被调用
        mock_get.assert_called_once()
        assert isinstance(result, StepResult)

    @pytest.mark.asyncio
    async def test_analyze_with_prompt_template(self):
        handler = AnalyzeHandler()
        step = make_step("分析", "analyze", prompt_template="## Issue\n{issue}\n\n## Code\n{code}")
        context = {"trigger_payload": {"issue_body": "bug", "code_context": "code"}}

        mock_resp = make_agent_response(
            '{"analysis":"ok","root_cause":"x","solution":"y","files_to_modify":[],'
            '"risk_assessment":"low","estimated_effort":"small"}'
        )

        with patch("app.agents.executor.get_agent") as mock_get:
            mock_agent = AsyncMock()
            mock_agent.run.return_value = mock_resp
            mock_get.return_value = mock_agent

            await handler.execute(step, context, None)

        # 验证 prompt 中包含我们的模板内容
        call_args = mock_agent.run.call_args
        user_prompt = call_args[0][1]
        assert "## Issue" in user_prompt
        assert "bug" in user_prompt

    @pytest.mark.asyncio
    async def test_analyze_ai_failure_fallback(self):
        """AI 失败时应回退到规则引擎。"""
        handler = AnalyzeHandler()
        step = make_step("分析", "analyze")
        context = {"trigger_payload": {"issue_body": "bug: login fails", "code_context": "TODO: fix this\neval(x)"}}

        with patch("app.agents.executor.get_agent") as mock_get:
            mock_agent = AsyncMock()
            mock_agent.run.side_effect = RuntimeError("AI unavailable")
            mock_get.return_value = mock_agent

            result = await handler.execute(step, context, None)

        assert isinstance(result, StepResult)
        assert result.status == "completed"  # fallback 成功
        assert result.output.get("fallback") is True
        assert "analysis" in result.output


# ── ExecuteHandler ──


class TestExecuteHandler:
    @pytest.mark.asyncio
    async def test_execute_basic(self):
        handler = ExecuteHandler()
        step = make_step("执行", "execute", config={"provider": "deepseek"})
        context = {
            "results": {"analyze": {"analysis": {"analysis": "fix bug"}}},
            "trigger_payload": {"code_context": "code here"},
        }

        mock_resp = make_agent_response(
            '{"changes":[],"summary":"fixed"}',
            parsed={"changes": [], "summary": "fixed"},
        )

        with patch("app.agents.executor.get_agent") as mock_get:
            mock_agent = AsyncMock()
            mock_agent.run.return_value = mock_resp
            mock_get.return_value = mock_agent

            result = await handler.execute(step, context, None)

        assert isinstance(result, StepResult)
        assert result.status == "completed"
        assert "changes" in result.output
        assert result.tokens_used == 100

    @pytest.mark.asyncio
    async def test_execute_no_git_repo(self):
        """无 git_repo 时不调用 GitHub API，正常返回 changes。"""
        handler = ExecuteHandler()
        step = make_step("执行", "execute", config={"provider": "deepseek"})
        context = {"results": {}, "trigger_payload": {}}

        mock_resp = make_agent_response(
            '{"changes":[],"summary":"ok"}',
            parsed={"changes": [], "summary": "ok"},
        )

        with patch("app.agents.executor.get_agent") as mock_get:
            mock_agent = AsyncMock()
            mock_agent.run.return_value = mock_resp
            mock_get.return_value = mock_agent

            result = await handler.execute(step, context, None)

        assert isinstance(result, StepResult)
        assert result.output["written_files"] == []


# ── ReviewHandler ──


class TestReviewHandler:
    @pytest.mark.asyncio
    async def test_review_basic(self):
        handler = ReviewHandler()
        step = make_step("审查", "review", config={"provider": "deepseek"})
        context = {"results": {"execute": {"changes": {"changes": [{"file": "x.py"}]}}}}

        mock_resp = make_agent_response(
            '{"verdict":"approve","score":90,"summary":"looks good","issues":[],"positive":["clean"]}',
            parsed={"verdict": "approve", "score": 90},
        )

        with patch("app.agents.executor.get_agent") as mock_get:
            mock_agent = AsyncMock()
            mock_agent.run.return_value = mock_resp
            mock_get.return_value = mock_agent

            result = await handler.execute(step, context, None)

        assert isinstance(result, StepResult)
        assert result.status == "completed"
        assert "review" in result.output
        assert result.output["review"]["verdict"] == "approve"

    @pytest.mark.asyncio
    async def test_review_request_changes(self):
        handler = ReviewHandler()
        step = make_step("审查", "review")
        context = {"results": {"execute": {"changes": {}}}}

        mock_resp = make_agent_response(
            '{"verdict":"request_changes","score":40,"summary":"needs work","issues":[],"positive":[]}',
            parsed={"verdict": "request_changes", "score": 40},
        )

        with patch("app.agents.executor.get_agent") as mock_get:
            mock_agent = AsyncMock()
            mock_agent.run.return_value = mock_resp
            mock_get.return_value = mock_agent

            result = await handler.execute(step, context, None)

        assert isinstance(result, StepResult)
        assert result.output["review"]["verdict"] == "request_changes"
        assert result.output["review"]["score"] == 40


# ── ConditionHandler ──


class TestConditionHandler:
    @pytest.mark.asyncio
    async def test_condition_no_condition(self):
        handler = ConditionHandler()
        step = make_step("判断", "condition")
        result = await handler.execute(step, {}, None)
        assert isinstance(result, StepResult)
        assert result.output["evaluated"] is True
        assert result.output["result"] is True

    @pytest.mark.asyncio
    async def test_condition_true(self):
        handler = ConditionHandler()
        step = make_step("判断", "condition", condition="{score} > 80")
        result = await handler.execute(step, {"score": 90}, None)
        assert isinstance(result, StepResult)
        assert result.output["result"] is True

    @pytest.mark.asyncio
    async def test_condition_false(self):
        handler = ConditionHandler()
        step = make_step("判断", "condition", condition="{score} > 80")
        result = await handler.execute(step, {"score": 50}, None)
        assert isinstance(result, StepResult)
        assert result.output["result"] is False


# ── MergeHandler ──


class TestMergeHandler:
    @pytest.mark.asyncio
    async def test_merge_no_git_repo(self):
        handler = MergeHandler()
        step = make_step("合并", "merge")
        context = {"git_repo": None}
        result = await handler.execute(step, context, None)
        assert isinstance(result, StepResult)
        assert result.status == "skipped"
        assert "未配置 git_repo" in result.error

    @pytest.mark.asyncio
    async def test_merge_no_github_token(self):
        handler = MergeHandler()
        step = make_step("合并", "merge")
        context = {"git_repo": "owner/repo"}
        with patch("app.agents.executor.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = None
            result = await handler.execute(step, context, None)
        assert isinstance(result, StepResult)
        assert result.status == "skipped"
        assert "GITHUB_TOKEN" in result.error


# ── ScriptHandler ──


class TestScriptHandler:
    @pytest.mark.asyncio
    async def test_script_no_command(self):
        handler = ScriptHandler()
        step = make_step("脚本", "script")
        result = await handler.execute(step, {}, None)
        assert isinstance(result, StepResult)
        # 脚本无命令时结果为 skipped（exit_code=-1）
        assert result.output["exit_code"] == -1

    @pytest.mark.asyncio
    async def test_script_success(self):
        handler = ScriptHandler()
        step = make_step("脚本", "script", config={"command": "echo hello"})
        result = await handler.execute(step, {}, None)
        assert isinstance(result, StepResult)
        assert result.output["exit_code"] == 0
        assert "hello" in result.output["output"]

    @pytest.mark.asyncio
    async def test_script_failure(self):
        handler = ScriptHandler()
        step = make_step("脚本", "script", config={"command": "exit 1"})
        result = await handler.execute(step, {}, None)
        assert isinstance(result, StepResult)
        assert result.output["exit_code"] == 1

    @pytest.mark.asyncio
    async def test_script_variable_substitution(self):
        handler = ScriptHandler()
        step = make_step("脚本", "script", config={"command": "echo {name}"})
        context = {"name": "world"}
        result = await handler.execute(step, context, None)
        assert isinstance(result, StepResult)
        assert "world" in result.output["output"]


# ── SubtaskHandler (stub) ──


class TestSubtaskHandler:
    @pytest.mark.asyncio
    async def test_subtask_stub(self):
        handler = SubtaskHandler()
        step = make_step("子任务", "subtask")
        result = await handler.execute(step, {}, None)
        assert isinstance(result, StepResult)
        assert result.status == "completed"
        assert "尚未实现" in result.output["message"]


# ── LoopHandler (stub) ──


class TestLoopHandler:
    @pytest.mark.asyncio
    async def test_loop_stub(self):
        handler = LoopHandler()
        step = make_step("循环", "loop")
        result = await handler.execute(step, {}, None)
        assert isinstance(result, StepResult)
        assert result.status == "completed"
        assert "尚未实现" in result.output["message"]
