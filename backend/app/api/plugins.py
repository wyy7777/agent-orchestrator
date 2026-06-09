"""插件 API：列出、查看和测试步骤插件。"""
from __future__ import annotations

import time
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.engine.plugin import get_plugin, list_plugins, _plugins

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


class PluginTestRequest(BaseModel):
    config: dict = {}
    context: dict = {}


@router.get("")
async def list_all_plugins():
    """列出所有可用插件。"""
    return list_plugins()


@router.get("/{name}")
async def get_plugin_detail(name: str):
    """获取插件详情和配置 schema。"""
    plugin = get_plugin(name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"插件 '{name}' 不存在")
    return {
        "name": plugin.name,
        "description": plugin.description,
        "schema": plugin.get_schema(),
    }


@router.post("/{name}/test")
async def test_plugin(name: str, body: PluginTestRequest):
    """测试插件执行。"""
    plugin = get_plugin(name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"插件 '{name}' 不存在")

    start = time.time()
    try:
        result = await plugin.execute(body.config, body.context)
        elapsed = round(time.time() - start, 3)
        return {
            "success": True,
            "plugin": name,
            "elapsed_seconds": elapsed,
            "result": result,
        }
    except Exception as e:
        elapsed = round(time.time() - start, 3)
        logger.warning(f"插件 '{name}' 测试执行失败: {e}")
        return {
            "success": False,
            "plugin": name,
            "elapsed_seconds": elapsed,
            "error": str(e),
        }
