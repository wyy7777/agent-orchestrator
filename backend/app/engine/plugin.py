"""插件系统：提供可扩展的步骤插件接口和注册表。"""
from __future__ import annotations

import importlib.util
import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# 插件注册表
_plugins: dict[str, StepPlugin] = {}

# 外部插件目录
PLUGIN_DIR = Path(__file__).parent.parent.parent / "plugins"


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
            "source": getattr(p, "_source", "builtin"),
        }
        for p in _plugins.values()
    ]


def load_external_plugins(plugin_dir: str | Path | None = None):
    """从外部目录加载插件 Python 文件。

    插件文件需在模块级别调用 @register_plugin("name") 装饰器。
    """
    dir_path = Path(plugin_dir) if plugin_dir else PLUGIN_DIR
    if not dir_path.exists():
        logger.debug(f"外部插件目录不存在: {dir_path}")
        return

    loaded = 0
    for py_file in dir_path.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"plugins.{py_file.stem}", str(py_file)
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                loaded += 1
                logger.info(f"已加载外部插件: {py_file.name}")
        except Exception as e:
            logger.error(f"加载外部插件失败 {py_file.name}: {e}")

    # 标记外部插件来源
    for _, plugin in _plugins.items():
        if not hasattr(plugin, "_source"):
            plugin._source = "builtin"

    if loaded:
        logger.info(f"共加载 {loaded} 个外部插件")


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

    # 危险命令黑名单（子串匹配，不区分大小写）
    _DANGEROUS_PATTERNS = (
        "rm -rf",
        "rm -fr",
        "mkfs",
        "dd if=",
        ":(){ :|:& };:",
        "chmod -r 777",
        "chmod 777 /",
        "> /dev/sda",
        "wget -o",
        "curl -o",
        "> /etc/",
        "rm -f /",
        "shutdown",
        "reboot",
        "halt",
        "init 0",
        "init 6",
    )

    async def execute(self, config: dict, context: dict) -> dict:
        import asyncio

        command = config["command"]
        cwd = config.get("cwd")
        timeout = config.get("timeout", 60)

        command = _resolve_template(command, context)

        # 命令长度限制
        if len(command) > 1000:
            return {"exit_code": -1, "stdout": "", "stderr": "命令长度超过 1000 字符限制"}

        # 危险命令检查
        command_lower = command.lower()
        for pattern in self._DANGEROUS_PATTERNS:
            if pattern.lower() in command_lower:
                return {"exit_code": -1, "stdout": "", "stderr": f"命令包含危险操作，已被拒绝: {pattern}"}

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
        except TimeoutError:
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
