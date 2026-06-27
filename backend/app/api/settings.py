"""全局 API 设置端点 — 管理 API Key、默认 Provider/Model。"""

import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])

# 支持的 AI Provider 列表
PROVIDERS = [
    {
        "name": "deepseek",
        "display_name": "DeepSeek",
        "env_key": "OPENAI_API_KEY",
        "base_url_key": "OPENAI_BASE_URL",
        "default_base_url": "https://api.deepseek.com",
        "models": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
    },
    {
        "name": "openai",
        "display_name": "OpenAI",
        "env_key": "OPENAI_API_KEY",
        "base_url_key": "OPENAI_BASE_URL",
        "default_base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    {
        "name": "claude",
        "display_name": "Claude (Anthropic)",
        "env_key": "ANTHROPIC_API_KEY",
        "base_url_key": "",
        "default_base_url": "",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"],
    },
]


def _mask_key(key: str) -> str | None:
    """将 API Key 掩码为 sk-***xyz 格式。"""
    if not key or key.startswith("your-"):
        return None
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-3:]}"


def _get_env_path() -> Path:
    """获取 .env 文件路径。"""
    import os
    dotenv_path = os.environ.get("AGENT_ORCH_DOTENV")
    if dotenv_path:
        return Path(dotenv_path)
    return Path(__file__).parent.parent / ".env"


def _read_env_var(key: str) -> str:
    """从 .env 文件读取变量值。"""
    env_path = _get_env_path()
    if not env_path.exists():
        return ""
    content = env_path.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(key)}=(.*)$", content, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _write_env_var(key: str, value: str):
    """写入或更新 .env 文件中的变量。"""
    env_path = _get_env_path()
    if not env_path.exists():
        env_path.write_text(f"{key}={value}\n", encoding="utf-8")
        return

    content = env_path.read_text(encoding="utf-8")
    pattern = rf"^{re.escape(key)}=.*$"
    if re.search(pattern, content, re.MULTILINE):
        content = re.sub(pattern, f"{key}={value}", content, flags=re.MULTILINE)
    else:
        content = content.rstrip() + f"\n{key}={value}\n"
    env_path.write_text(content, encoding="utf-8")


class ApiKeyUpdate(BaseModel):
    provider: str
    api_key: str
    base_url: str | None = None


class DefaultsUpdate(BaseModel):
    default_provider: str
    default_model: str


class TestConnectionRequest(BaseModel):
    provider: str
    api_key: str | None = None


@router.get("/api-keys")
async def get_api_keys():
    """获取所有 API Key 的配置状态（掩码）。"""
    providers = []
    for p in PROVIDERS:
        raw_key = _read_env_var(p["env_key"])
        base_url = _read_env_var(p["base_url_key"]) or p["default_base_url"]
        providers.append({
            "name": p["name"],
            "display_name": p["display_name"],
            "key_configured": bool(raw_key) and not raw_key.startswith("your-"),
            "key_preview": _mask_key(raw_key),
            "base_url": base_url,
            "models": p["models"],
        })

    return {
        "providers": providers,
        "default_provider": settings.DEFAULT_AI_PROVIDER,
        "default_model": settings.DEFAULT_AI_MODEL,
    }


@router.put("/api-keys")
async def update_api_key(body: ApiKeyUpdate):
    """更新指定 Provider 的 API Key。"""
    provider_info = None
    for p in PROVIDERS:
        if p["name"] == body.provider:
            provider_info = p
            break

    if not provider_info:
        raise HTTPException(status_code=400, detail=f"不支持的 Provider: {body.provider}")

    # 写入 API Key
    _write_env_var(provider_info["env_key"], body.api_key)

    # 写入 Base URL（如果有）
    if body.base_url and provider_info["base_url_key"]:
        _write_env_var(provider_info["base_url_key"], body.base_url)

    # 动态更新运行时 settings
    if provider_info["name"] in ("deepseek", "openai"):
        settings.OPENAI_API_KEY = body.api_key
        if body.base_url:
            settings.OPENAI_BASE_URL = body.base_url
    elif provider_info["name"] == "claude":
        settings.ANTHROPIC_API_KEY = body.api_key

    logger.info(f"API Key 已更新: {body.provider}")
    return {"status": "ok", "provider": body.provider, "key_preview": _mask_key(body.api_key)}


@router.post("/test-connection")
async def test_connection(body: TestConnectionRequest):
    """测试 API 连通性。"""
    import httpx

    provider_info = None
    for p in PROVIDERS:
        if p["name"] == body.provider:
            provider_info = p
            break

    if not provider_info:
        raise HTTPException(status_code=400, detail=f"不支持的 Provider: {body.provider}")

    api_key = body.api_key or _read_env_var(provider_info["env_key"])
    if not api_key or api_key.startswith("your-"):
        return {"success": False, "message": "未配置 API Key"}

    base_url = _read_env_var(provider_info["base_url_key"]) or provider_info["default_base_url"]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            if body.provider in ("deepseek", "openai"):
                resp = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code == 200:
                    return {"success": True, "message": f"{provider_info['display_name']} 连接成功"}
                elif resp.status_code == 401:
                    return {"success": False, "message": "API Key 无效 (401 Unauthorized)"}
                else:
                    return {"success": False, "message": f"连接失败: HTTP {resp.status_code}"}
            elif body.provider == "claude":
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )
                if resp.status_code in (200, 400):
                    return {"success": True, "message": "Claude 连接成功"}
                elif resp.status_code == 401:
                    return {"success": False, "message": "API Key 无效 (401 Unauthorized)"}
                else:
                    return {"success": False, "message": f"连接失败: HTTP {resp.status_code}"}
    except httpx.ConnectError:
        return {"success": False, "message": f"无法连接到 {base_url}"}
    except httpx.TimeoutException:
        return {"success": False, "message": "连接超时 (15s)"}
    except Exception as e:
        return {"success": False, "message": f"测试失败: {e}"}


@router.get("")
async def get_defaults():
    """获取全局默认 Provider/Model。"""
    return {
        "default_provider": settings.DEFAULT_AI_PROVIDER,
        "default_model": settings.DEFAULT_AI_MODEL,
    }


@router.put("")
async def update_defaults(body: DefaultsUpdate):
    """更新全局默认 Provider/Model。"""
    valid_providers = [p["name"] for p in PROVIDERS]
    if body.default_provider not in valid_providers:
        raise HTTPException(status_code=400, detail=f"不支持的 Provider: {body.default_provider}")

    _write_env_var("DEFAULT_AI_PROVIDER", body.default_provider)
    _write_env_var("DEFAULT_AI_MODEL", body.default_model)

    # 动态更新运行时
    settings.DEFAULT_AI_PROVIDER = body.default_provider
    settings.DEFAULT_AI_MODEL = body.default_model

    logger.info(f"默认模型已更新: {body.default_provider}/{body.default_model}")
    return {"status": "ok", "default_provider": body.default_provider, "default_model": body.default_model}
