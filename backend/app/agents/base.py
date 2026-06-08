from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class AgentResponse:
    def __init__(
        self,
        content: str,
        parsed: dict[str, Any] | None = None,
        tokens_used: int = 0,
        model: str = "",
    ):
        self.content = content
        self.parsed = parsed or {}
        self.tokens_used = tokens_used
        self.model = model

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "parsed": self.parsed,
            "tokens_used": self.tokens_used,
            "model": self.model,
        }


class BaseAgent(ABC):
    """Agent 基类，统一 Claude 和 OpenAI 的调用接口。"""

    @abstractmethod
    async def run(self, system_prompt: str, user_prompt: str) -> AgentResponse:
        raise NotImplementedError


class ClaudeAgent(BaseAgent):
    def __init__(self, model: str | None = None):
        self.model = model or settings.DEFAULT_AI_MODEL

    async def run(self, system_prompt: str, user_prompt: str) -> AgentResponse:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        content = response.content[0].text
        tokens_used = response.usage.input_tokens + response.usage.output_tokens

        parsed = None
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            pass

        return AgentResponse(
            content=content,
            parsed=parsed,
            tokens_used=tokens_used,
            model=self.model,
        )


class OpenAIAgent(BaseAgent):
    def __init__(self, model: str = "gpt-4o", base_url: str | None = None):
        self.model = model
        self.base_url = base_url

    async def run(self, system_prompt: str, user_prompt: str) -> AgentResponse:
        import openai

        client = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=self.base_url,
        )
        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0

        parsed = None
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            pass

        return AgentResponse(
            content=content,
            parsed=parsed,
            tokens_used=tokens_used,
            model=self.model,
        )


class DeepSeekAgent(OpenAIAgent):
    """DeepSeek Agent — 使用 OpenAI 兼容 API，指向 DeepSeek 端点。"""

    def __init__(self, model: str = "deepseek-chat"):
        super().__init__(
            model=model,
            base_url=settings.OPENAI_BASE_URL or "https://api.deepseek.com",
        )


def get_agent(provider: str | None = None, model: str | None = None) -> BaseAgent:
    """工厂方法：根据 provider 返回对应的 Agent。默认使用 settings.DEFAULT_AI_PROVIDER。"""
    provider = provider or settings.DEFAULT_AI_PROVIDER

    if provider == "deepseek":
        return DeepSeekAgent(model=model or settings.DEFAULT_AI_MODEL)
    elif provider == "openai":
        return OpenAIAgent(model=model or "gpt-4o")
    elif provider == "claude":
        return ClaudeAgent(model=model or settings.DEFAULT_AI_MODEL)
    else:
        # 未知 provider，默认使用 DeepSeek
        return DeepSeekAgent(model=model or settings.DEFAULT_AI_MODEL)
