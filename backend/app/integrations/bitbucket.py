"""Bitbucket 集成：分支创建、文件写入、PR 创建。"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BITBUCKET_API = "https://api.bitbucket.org/2.0"

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=10),
        )
    return _client


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.BITBUCKET_TOKEN}",
        "Content-Type": "application/json",
    }


def _parse_repo(git_repo: str) -> tuple[str, str]:
    """从 Bitbucket URL 解析 workspace/repo_slug。"""
    repo = git_repo.rstrip("/").rstrip(".git")
    if repo.startswith("https://bitbucket.org/"):
        repo = repo.replace("https://bitbucket.org/", "")
    parts = repo.split("/")
    if len(parts) < 2:
        raise ValueError(f"无法解析仓库: {git_repo}")
    return parts[-2], parts[-1]


async def get_repository(workspace: str, repo_slug: str) -> dict:
    """获取仓库信息。"""
    client = _get_client()
    resp = await client.get(
        f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}",
        headers=_headers(),
    )
    resp.raise_for_status()
    return resp.json()


async def get_default_branch(workspace: str, repo_slug: str) -> str:
    """获取默认分支名。"""
    repo = await get_repository(workspace, repo_slug)
    return repo.get("mainbranch", {}).get("name", "main")


async def get_branch_tip(workspace: str, repo_slug: str, branch: str) -> str:
    """获取分支最新 commit hash。"""
    client = _get_client()
    resp = await client.get(
        f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/refs/branches/{branch}",
        headers=_headers(),
    )
    resp.raise_for_status()
    return resp.json()["target"]["hash"]


async def create_branch(
    workspace: str,
    repo_slug: str,
    branch_name: str,
    source_branch: str = "main",
) -> dict:
    """创建新分支。"""
    client = _get_client()
    resp = await client.post(
        f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/refs/branches",
        headers=_headers(),
        json={
            "name": branch_name,
            "target": {"hash": source_branch},
        },
    )
    resp.raise_for_status()
    logger.info(f"Bitbucket 分支已创建: {branch_name}")
    return resp.json()


async def create_or_update_file(
    workspace: str,
    repo_slug: str,
    branch: str,
    file_path: str,
    content: str,
    commit_message: str = "Agent: 更新文件",
) -> dict:
    """创建或更新文件。"""
    client = _get_client()

    # 检查文件是否存在
    try:
        resp = await client.get(
            f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/src/{branch}/{file_path}",
            headers=_headers(),
        )
        exists = resp.status_code == 200
    except Exception:
        exists = False

    if exists:
        # 更新文件
        resp = await client.put(
            f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/src",
            headers=_headers(),
            data={
                "branch": branch,
                "message": commit_message,
                file_path: content,
            },
        )
    else:
        # 创建文件
        resp = await client.post(
            f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/src",
            headers=_headers(),
            data={
                "branch": branch,
                "message": commit_message,
                file_path: content,
            },
        )

    resp.raise_for_status()
    logger.info(f"Bitbucket 文件已更新: {file_path}")
    return {"status": "ok", "file_path": file_path}


async def create_pull_request(
    workspace: str,
    repo_slug: str,
    source_branch: str,
    target_branch: str,
    title: str,
    description: str = "",
) -> dict:
    """创建 Pull Request。"""
    client = _get_client()
    resp = await client.post(
        f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/pullrequests",
        headers=_headers(),
        json={
            "title": title,
            "description": description,
            "source": {
                "branch": {"name": source_branch},
            },
            "destination": {
                "branch": {"name": target_branch},
            },
        },
    )
    resp.raise_for_status()
    pr = resp.json()
    logger.info(f"Bitbucket PR 已创建: {pr['links']['html']['href']}")
    return pr
