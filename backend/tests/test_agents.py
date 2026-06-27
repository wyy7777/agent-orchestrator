"""Agent mock 测试。"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.agents.base import AgentResponse, BaseAgent, _retry_with_backoff, get_agent

# ---------- 测试 AgentResponse ----------


class TestAgentResponse:
    """测试 Agent 响应数据类。"""

    def test_basic_response(self):
        """基本响应。"""
        resp = AgentResponse(
            content='{"score": 85}',
            tokens_used=100,
            model="deepseek-chat",
        )
        assert resp.content == '{"score": 85}'
        assert resp.tokens_used == 100
        assert resp.model == "deepseek-chat"

    def test_parsed_json(self):
        """解析 JSON。"""
        resp = AgentResponse(
            content='{"score": 85}',
            tokens_used=100,
            model="test",
            parsed={"score": 85},
        )
        assert resp.parsed == {"score": 85}

    def test_parsed_none(self):
        """未解析时 parsed 为 None。"""
        resp = AgentResponse(content="raw text", tokens_used=50, model="test")
        assert resp.parsed is None


# ---------- 测试 get_agent ----------


class TestGetAgent:
    """测试 Agent 工厂函数。"""

    def test_get_deepseek_agent(self):
        """获取 DeepSeek Agent。"""
        agent = get_agent("deepseek", "deepseek-chat")
        assert agent is not None

    def test_get_openai_agent(self):
        """获取 OpenAI Agent。"""
        agent = get_agent("openai", "gpt-4o")
        assert agent is not None

    def test_get_claude_agent(self):
        """获取 Claude Agent。"""
        agent = get_agent("claude", "claude-3-sonnet")
        assert agent is not None

    def test_get_unknown_agent(self):
        """未知 provider 应返回默认 Agent 或抛出异常。"""
        # get_agent 可能返回默认 agent 或抛出异常
        try:
            agent = get_agent("unknown_provider")
            # 如果返回了 agent，验证它是有效的
            assert agent is not None
        except (ValueError, KeyError):
            pass  # 预期行为


# ---------- 测试重试机制 ----------


class TestRetryWithBackoff:
    """测试指数退避重试。"""

    @pytest.mark.asyncio
    async def test_success_first_try(self):
        """首次成功应直接返回。"""
        mock_coro = AsyncMock(return_value="success")
        result = await _retry_with_backoff(mock_coro, max_retries=3)
        assert result == "success"
        assert mock_coro.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """失败后应重试。"""
        mock_coro = AsyncMock(
            side_effect=[Exception("fail"), Exception("fail"), "success"]
        )
        result = await _retry_with_backoff(mock_coro, max_retries=3)
        assert result == "success"
        assert mock_coro.call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_retries(self):
        """重试耗尽应抛出异常。"""
        mock_coro = AsyncMock(side_effect=Exception("always fail"))
        with pytest.raises(Exception, match="always fail"):
            await _retry_with_backoff(mock_coro, max_retries=2)
        assert mock_coro.call_count == 3  # 初始 + 2 次重试

    @pytest.mark.asyncio
    async def test_no_retries_explicit(self):
        """显式设置 max_retries=1 时尝试 1 次 + 1 次重试 = 2 次。"""
        mock_coro = AsyncMock(side_effect=Exception("fail"))
        with pytest.raises(Exception, match="fail"):
            # max_retries=1 表示 1 次重试，总共 2 次尝试
            await _retry_with_backoff(mock_coro, max_retries=1)
        assert mock_coro.call_count == 2


# ---------- 测试 BaseAgent ----------


class TestBaseAgent:
    """测试 BaseAgent 基类。"""

    @pytest.mark.asyncio
    async def test_base_agent_run(self):
        """BaseAgent.run 应调用 _call_api。"""

        class MockAgent(BaseAgent):
            async def _call_api(self, system_prompt, user_prompt, max_tokens=None):
                return AgentResponse(
                    content="mock response",
                    tokens_used=50,
                    model="test-model",
                )

        agent = MockAgent()
        resp = await agent.run("system", "user")
        assert resp.content == "mock response"
        assert resp.tokens_used == 50

    @pytest.mark.asyncio
    async def test_base_agent_with_json(self):
        """BaseAgent 应能返回 JSON 解析结果。"""

        class MockAgent(BaseAgent):
            async def _call_api(self, system_prompt, user_prompt, max_tokens=None):
                return AgentResponse(
                    content='{"result": "ok"}',
                    tokens_used=30,
                    model="test",
                    parsed={"result": "ok"},
                )

        agent = MockAgent()
        resp = await agent.run("system", "user")
        assert resp.parsed == {"result": "ok"}


# ---------- 测试 Ollama Agent ----------


class TestOllamaAgent:
    """测试 Ollama Agent 工厂函数。"""

    def test_get_ollama_agent(self):
        """获取 Ollama Agent。"""
        agent = get_agent("ollama", "qwen2.5-coder:7b")
        assert agent is not None
        assert agent.model == "qwen2.5-coder:7b"

    def test_get_ollama_default_model(self):
        """Ollama Agent 默认模型。"""
        agent = get_agent("ollama")
        assert agent.model == "qwen2.5-coder:7b"

    def test_provider_strings(self):
        """所有支持的 provider 应返回有效 agent。"""
        for provider in ["deepseek", "openai", "claude", "ollama"]:
            agent = get_agent(provider)
            assert agent is not None, f"Provider {provider} 应返回有效 agent"
