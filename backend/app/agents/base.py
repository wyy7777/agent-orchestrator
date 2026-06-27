from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class AgentErrorCode(StrEnum):
    """Agent 调用的结构化错误码。"""
    AUTH_FAILED = "auth_failed"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    MODEL_NOT_FOUND = "model_not_found"
    TOKEN_LIMIT = "token_limit"
    INVALID_OUTPUT = "invalid_output"
    UNKNOWN = "unknown"


class AgentError(Exception):
    """Agent 调用异常，携带结构化错误码。"""

    def __init__(self, code: AgentErrorCode, message: str, original: Exception | None = None):
        self.code = code
        self.message = message
        self.original = original
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.code.value,
            "message": self.message,
            "original_error": str(self.original) if self.original else None,
        }


class AgentResponse:
    def __init__(
        self,
        content: str,
        parsed: dict[str, Any] | None = None,
        tokens_used: int = 0,
        model: str = "",
    ):
        self.content = content
        self.parsed = parsed
        self.tokens_used = tokens_used
        self.model = model

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "parsed": self.parsed,
            "tokens_used": self.tokens_used,
            "model": self.model,
        }


def _try_parse_json(content: str) -> dict[str, Any] | None:
    """尝试解析 JSON，返回 None 表示非 JSON 内容。"""
    try:
        result = json.loads(content)
        if isinstance(result, dict):
            return result
        return None
    except (json.JSONDecodeError, TypeError):
        return None


def classify_error(error: Exception) -> tuple[AgentErrorCode, str]:
    """将技术错误分类为结构化错误码和用户友好的提示。"""
    error_str = str(error).lower()

    if "api key" in error_str or "apikey" in error_str or "unauthorized" in error_str or "401" in error_str:
        return AgentErrorCode.AUTH_FAILED, "API Key 无效或已过期，请在 .env 中更新 OPENAI_API_KEY 或 ANTHROPIC_API_KEY"
    if "rate limit" in error_str or "429" in error_str:
        return AgentErrorCode.RATE_LIMITED, "API 请求频率超限，请稍后再试"
    if "timeout" in error_str or "timed out" in error_str:
        return AgentErrorCode.TIMEOUT, "AI 响应超时，可使用更小的模型或增加超时时间重试"
    if "connection" in error_str or "network" in error_str or "connect" in error_str:
        return AgentErrorCode.NETWORK_ERROR, "无法连接到 AI 服务，请检查网络连接"
    if "model" in error_str and ("not found" in error_str or "does not exist" in error_str):
        return AgentErrorCode.MODEL_NOT_FOUND, "指定的模型不存在，请检查配置中的模型名称"
    if "token" in error_str and ("limit" in error_str or "exceeded" in error_str):
        return AgentErrorCode.TOKEN_LIMIT, "已达到 Token 上限，请升级套餐或等待下月重置"

    return AgentErrorCode.UNKNOWN, f"AI 调用失败: {error}"


def _get_friendly_error(error: Exception) -> str:
    """将技术错误转换为用户友好的提示（保持向后兼容）。"""
    _, message = classify_error(error)
    return message


async def _retry_with_backoff(coro_factory, max_retries: int = 0, label: str = ""):
    """带指数退避的重试包装器。coro_factory 是返回 coroutine 的工厂函数。"""
    max_retries = max_retries or settings.AI_MAX_RETRIES
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                wait = min(2 ** attempt, 30)
                logger.warning(f"[{label}] 第 {attempt+1} 次调用失败: {e}，{wait}s 后重试")
                await asyncio.sleep(wait)
            else:
                logger.error(f"[{label}] {max_retries+1} 次调用均失败: {e}")
    raise last_error


class BaseAgent(ABC):
    """Agent 基类，统一调用接口，内置重试和超时。"""

    @abstractmethod
    async def _call_api(self, system_prompt: str, user_prompt: str) -> AgentResponse:
        """子类实现实际的 API 调用。"""
        raise NotImplementedError

    async def run(self, system_prompt: str, user_prompt: str) -> AgentResponse:
        """带重试和超时的统一入口。"""
        timeout = settings.AI_TIMEOUT_SECONDS

        async def _do_call():
            return await asyncio.wait_for(
                self._call_api(system_prompt, user_prompt),
                timeout=timeout,
            )

        return await _retry_with_backoff(_do_call, label=self.__class__.__name__)


class ClaudeAgent(BaseAgent):
    _client = None

    def __init__(self, model: str | None = None, max_tokens: int | None = None):
        self.model = model or settings.DEFAULT_AI_MODEL
        self.max_tokens = max_tokens or settings.DEFAULT_MAX_TOKENS

    def _get_client(self):
        if ClaudeAgent._client is None:
            import anthropic
            ClaudeAgent._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        return ClaudeAgent._client

    async def _call_api(self, system_prompt: str, user_prompt: str) -> AgentResponse:
        client = self._get_client()
        response = await client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        content = response.content[0].text
        tokens_used = response.usage.input_tokens + response.usage.output_tokens

        return AgentResponse(
            content=content,
            parsed=_try_parse_json(content),
            tokens_used=tokens_used,
            model=self.model,
        )


class OpenAIAgent(BaseAgent):
    _clients: dict[str, Any] = {}

    def __init__(self, model: str = "gpt-4o", base_url: str | None = None, max_tokens: int | None = None):
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens or settings.DEFAULT_MAX_TOKENS

    def _get_client(self):
        key = self.base_url or "default"
        if key not in OpenAIAgent._clients:
            import openai
            OpenAIAgent._clients[key] = openai.AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=self.base_url,
            )
        return OpenAIAgent._clients[key]

    async def _call_api(self, system_prompt: str, user_prompt: str) -> AgentResponse:
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0

        return AgentResponse(
            content=content,
            parsed=_try_parse_json(content),
            tokens_used=tokens_used,
            model=self.model,
        )


class DeepSeekAgent(OpenAIAgent):
    def __init__(self, model: str = "deepseek-chat", max_tokens: int | None = None):
        super().__init__(
            model=model,
            base_url=settings.OPENAI_BASE_URL or "https://api.deepseek.com",
            max_tokens=max_tokens,
        )


class OllamaAgent(OpenAIAgent):
    """Ollama 本地模型 Agent（OpenAI 兼容 API）。"""

    def __init__(self, model: str | None = None, max_tokens: int | None = None):
        super().__init__(
            model=model or settings.OLLAMA_DEFAULT_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            max_tokens=max_tokens,
        )
        # Ollama 不需要 API Key
        import openai
        key = self.base_url or "ollama"
        if key not in self._clients:
            self._clients[key] = openai.AsyncOpenAI(
                api_key="ollama",  # Ollama 忽略 API Key
                base_url=self.base_url,
            )

    async def _call_api(self, system_prompt: str, user_prompt: str) -> AgentResponse:
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0

        return AgentResponse(
            content=content,
            parsed=_try_parse_json(content),
            tokens_used=tokens_used,
            model=self.model,
        )


def get_agent(provider: str | None = None, model: str | None = None, max_tokens: int | None = None) -> BaseAgent:
    provider = provider or settings.DEFAULT_AI_PROVIDER
    if provider == "deepseek":
        return DeepSeekAgent(model=model or settings.DEFAULT_AI_MODEL, max_tokens=max_tokens)
    elif provider == "openai":
        return OpenAIAgent(model=model or "gpt-4o", max_tokens=max_tokens)
    elif provider == "claude":
        return ClaudeAgent(model=model or settings.DEFAULT_AI_MODEL, max_tokens=max_tokens)
    elif provider == "ollama":
        return OllamaAgent(model=model, max_tokens=max_tokens)
    else:
        return DeepSeekAgent(model=model or settings.DEFAULT_AI_MODEL, max_tokens=max_tokens)
