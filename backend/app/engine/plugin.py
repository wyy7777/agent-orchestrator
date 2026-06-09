"""插件系统：提供可扩展的步骤插件接口和注册表。"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)

# 插件注册表
_plugins: dict[str, "StepPlugin"] = {}


class StepPlugin(ABC):
    """步骤插件基类。所有自定义插件需继承此类。"""

    name: str
    description: str

    @abstractmethod
    async def execute(self, config: dict, context: dict) -> dict:
        ...

    def get_schema(self) -> dict:
        """返回配置 schema（JSON Schema 格式），用于前端表单生成。"""
        return {}


def register_plugin(name: str):
    """装饰器：将插件类实例注册到全局注册表。"""
    def decorator(cls):
        _plugins[name] = cls()
        return cls
    return decorator


def get_plugin(name: str) -> StepPlugin | None:
    """按名称获取已注册的插件实例。"""
    return _plugins.get(name)


def list_plugins() -> list[dict]:
    """列出所有已注册插件的摘要信息。"""
    return [
        {
            "name": p.name,
            "description": p.description,
            "schema": p.get_schema(),
        }
        for p in _plugins.values()
    ]


# ---------- 内置插件 ----------


@register_plugin("http_request")
class HttpRequestPlugin(StepPlugin):
    """发送 HTTP 请求。"""

    name = "http_request"
    description = "发送 HTTP 请求并返回响应"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["url"],
            "properties": {
                "url": {"type": "string", "description": "请求地址"},
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                    "default": "GET",
                    "description": "HTTP 方法",
                },
                "headers": {"type": "object", "description": "请求头"},
                "body": {"description": "请求体（POST/PUT/PATCH 时使用）"},
                "timeout": {
                    "type": "integer",
                    "default": 30,
                    "description": "请求超时秒数",
                },
            },
        }

    async def execute(self, config: dict, context: dict) -> dict:
        url = config["url"]
        method = config.get("method", "GET").upper()
        headers = config.get("headers", {})
        body = config.get("body")
        timeout = config.get("timeout", 30)

        # 支持从 context 中做简单模板替换（{results.xxx} 格式）
        url = _resolve_template(url, context)
        if isinstance(body, str):
            body = _resolve_template(body, context)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=body if isinstance(body, (dict, list)) else None,
                content=body if isinstance(body, str) else None,
            )

        result: dict = {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
        }
        try:
            result["body"] = resp.json()
        except Exception:
            result["body"] = resp.text

        return result


@register_plugin("shell_command")
class ShellCommandPlugin(StepPlugin):
    """执行 shell 命令（谨慎使用）。"""

    name = "shell_command"
    description = "在沙箱环境中执行 shell 命令"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["command"],
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "cwd": {"type": "string", "description": "工作目录"},
                "timeout": {
                    "type": "integer",
                    "default": 60,
                    "description": "超时秒数",
                },
            },
        }

    async def execute(self, config: dict, context: dict) -> dict:
        import asyncio

        command = config["command"]
        cwd = config.get("cwd")
        timeout = config.get("timeout", 60)

        command = _resolve_template(command, context)

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            return {"exit_code": -1, "stdout": "", "stderr": "命令超时"}

        return {
            "exit_code": proc.returncode,
            "stdout": stdout.decode(errors="replace").strip(),
            "stderr": stderr.decode(errors="replace").strip(),
        }


@register_plugin("transform")
class TransformPlugin(StepPlugin):
    """对上下文数据做简单转换。"""

    name = "transform"
    description = "对上下文数据进行提取或转换"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "extract": {
                    "type": "object",
                    "description": "从 context.results 中提取字段，键为目标字段名，值为 JSONPath（点分隔）",
                },
                "set": {
                    "type": "object",
                    "description": "设置固定值到输出中",
                },
            },
        }

    async def execute(self, config: dict, context: dict) -> dict:
        output: dict = {}

        # 固定值
        for key, value in config.get("set", {}).items():
            output[key] = value

        # 从 context 中提取
        for target_key, path in config.get("extract", {}).items():
            output[target_key] = _deep_get(context, path)

        return output


# ---------- 辅助函数 ----------


def _resolve_template(text: str, context: dict) -> str:
    """简单模板替换：将 {key.subkey} 替换为 context 中对应值。"""
    import re

    def _replacer(match: re.Match) -> str:
        path = match.group(1)
        value = _deep_get(context, path)
        if value is None:
            return match.group(0)
        return str(value)

    return re.sub(r"\{([^}]+)\}", _replacer, text)


def _deep_get(obj: dict, path: str):
    """按点分隔路径从嵌套字典中取值。"""
    current = obj
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current
