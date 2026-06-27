"""插件市场 API：管理插件的发布、安装、卸载。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_role
from app.engine.plugin import get_plugin, list_plugins

if TYPE_CHECKING:
    from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plugin-marketplace", tags=["plugins"])


# ── Pydantic schemas ──

class PluginResponse(BaseModel):
    name: str
    description: str
    config_schema: dict[str, Any] = {}
    source: str = "builtin"
    installed: bool = True


class PluginInstall(BaseModel):
    url: str
    name: str | None = None


# ── 内置插件 ──

@router.get("/list")
async def list_marketplace_plugins() -> list[PluginResponse]:
    """列出市场上所有可安装的插件。"""
    plugins = list_plugins()
    return [PluginResponse(
        name=p["name"],
        description=p["description"],
        config_schema=p.get("schema", {}),
        source=p.get("source", "builtin"),
        installed=True,
    ) for p in plugins]


@router.get("/detail/{plugin_name}")
async def get_plugin_detail(plugin_name: str) -> PluginResponse:
    """获取插件详情。"""
    plugin = get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")
    return PluginResponse(
        name=plugin.name,
        description=plugin.description,
        config_schema=plugin.get_schema(),
        source=getattr(plugin, "_source", "builtin"),
        installed=True,
    )


@router.post("/install")
async def install_plugin(
    body: PluginInstall,
    _user: User = Depends(require_role("admin", "manager")),
):
    """从 URL 安装插件（下载到 plugins/ 目录）。"""
    from pathlib import Path

    import httpx

    plugin_dir = Path(__file__).parent.parent.parent / "plugins"
    plugin_dir.mkdir(exist_ok=True)

    # 下载插件文件
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(body.url)
            resp.raise_for_status()
            content = resp.text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"下载插件失败: {e}")

    # 推断文件名
    filename = body.name or body.url.split("/")[-1]
    if not filename.endswith(".py"):
        filename += ".py"

    # 写入文件
    plugin_path = plugin_dir / filename
    plugin_path.write_text(content, encoding="utf-8")

    # 尝试加载
    try:
        from app.engine.plugin import load_external_plugins
        load_external_plugins(plugin_dir)
    except Exception as e:
        plugin_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"插件加载失败: {e}")

    return {"status": "installed", "file": filename}


@router.post("/uninstall/{plugin_name}")
async def uninstall_plugin(
    plugin_name: str,
    _user: User = Depends(require_role("admin")),
):
    """卸载外部插件（删除文件并从注册表移除）。"""
    from pathlib import Path

    plugin = get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")

    if getattr(plugin, "_source", "builtin") == "builtin":
        raise HTTPException(status_code=400, detail="内置插件不可卸载")

    # 删除文件
    plugin_dir = Path(__file__).parent.parent.parent / "plugins"
    for py_file in plugin_dir.glob("*.py"):
        if plugin_name in py_file.stem:
            py_file.unlink()
            break

    # 从注册表移除
    from app.engine.plugin import _plugins
    _plugins.pop(plugin_name, None)

    return {"status": "uninstalled", "name": plugin_name}
