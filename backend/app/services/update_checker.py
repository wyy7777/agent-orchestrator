"""版本检查与更新服务：检查 GitHub 仓库最新版本。"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GITHUB_REPO = "wyy7777/agent-orchestrator"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


async def check_for_updates() -> dict[str, Any]:
    """检查 GitHub 仓库是否有新版本。

    返回:
        {
            "current_version": "1.2.0",
            "latest_version": "1.3.0",
            "update_available": True,
            "release_url": "https://...",
            "release_notes": "...",
            "published_at": "2026-..."
        }
    """
    current = settings.APP_VERSION

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                GITHUB_API,
                headers={"Accept": "application/vnd.github.v3+json"},
            )

        if resp.status_code != 200:
            logger.warning(f"GitHub API 返回 {resp.status_code}")
            return {
                "current_version": current,
                "latest_version": current,
                "update_available": False,
                "error": f"GitHub API 不可用 ({resp.status_code})",
            }

        data = resp.json()
        latest = data.get("tag_name", "").lstrip("v")

        # 简单的语义版本比较
        update_available = _compare_versions(latest, current) > 0

        return {
            "current_version": current,
            "latest_version": latest,
            "update_available": update_available,
            "release_url": data.get("html_url", ""),
            "release_notes": (data.get("body") or "")[:2000],
            "published_at": data.get("published_at", ""),
        }

    except Exception as e:
        logger.warning(f"检查更新失败: {e}")
        return {
            "current_version": current,
            "latest_version": current,
            "update_available": False,
            "error": str(e)[:200],
        }


def _compare_versions(v1: str, v2: str) -> int:
    """比较两个语义版本号。返回 >0 如果 v1 > v2。"""
    try:
        parts1 = [int(x) for x in v1.split(".")]
        parts2 = [int(x) for x in v2.split(".")]
    except ValueError:
        return 0

    # 补齐长度
    while len(parts1) < len(parts2):
        parts1.append(0)
    while len(parts2) < len(parts1):
        parts2.append(0)

    for a, b in zip(parts1, parts2, strict=True):
        if a != b:
            return a - b
    return 0
