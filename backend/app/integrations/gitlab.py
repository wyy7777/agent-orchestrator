"""GitLab 集成：项目信息获取、分支创建、文件写入、MR 创建。"""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GITLAB_API = "https://gitlab.com/api/v4"

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
        "Authorization": f"Bearer {settings.GITLAB_TOKEN}",
        "Content-Type": "application/json",
    }


def _parse_repo(git_repo: str) -> str:
    """从 GitLab URL 解析项目路径（URL encoded）。"""
    repo = git_repo.rstrip("/").removesuffix(".git")
    if repo.startswith("https://gitlab.com/"):
        repo = repo.replace("https://gitlab.com/", "", 1)
    return repo.replace("/", "%2F")


def _validate_file_path(file_path: str) -> str:
    """校验文件路径，防止路径穿越。"""
    if not file_path or ".." in file_path or file_path.startswith("/"):
        raise ValueError(f"不安全的文件路径: {file_path}")
    return file_path


async def get_project(git_repo: str) -> dict:
    """获取项目信息。"""
    project_id = _parse_repo(git_repo)
    client = _get_client()
    resp = await client.get(
        f"{GITLAB_API}/projects/{project_id}",
        headers=_headers(),
    )
    resp.raise_for_status()
    return resp.json()


async def get_default_branch(git_repo: str) -> str:
    """获取默认分支名。"""
    project = await get_project(git_repo)
    return project.get("default_branch", "main")


async def create_branch(git_repo: str, branch_name: str, ref: str = "main") -> dict:
    """创建新分支。"""
    project_id = _parse_repo(git_repo)
    client = _get_client()
    resp = await client.post(
        f"{GITLAB_API}/projects/{project_id}/repository/branches",
        headers=_headers(),
        json={"branch": branch_name, "ref": ref},
    )
    resp.raise_for_status()
    logger.info(f"GitLab 分支已创建: {branch_name}")
    return resp.json()


async def create_file(
    git_repo: str,
    branch: str,
    file_path: str,
    content: str,
    commit_message: str = "Agent: 更新文件",
) -> dict:
    """创建或更新文件。"""
    file_path = _validate_file_path(file_path)
    project_id = _parse_repo(git_repo)
    client = _get_client()

    # 检查文件是否存在
    try:
        resp = await client.get(
            f"{GITLAB_API}/projects/{project_id}/repository/files/{file_path.replace('/', '%2F')}",
            headers=_headers(),
            params={"ref": branch},
        )
        exists = resp.status_code == 200
    except Exception:
        exists = False

    data = {
        "branch": branch,
        "content": content,
        "commit_message": commit_message,
    }

    if exists:
        resp = await client.put(
            f"{GITLAB_API}/projects/{project_id}/repository/files/{file_path.replace('/', '%2F')}",
            headers=_headers(),
            json=data,
        )
    else:
        data["file_path"] = file_path
        resp = await client.post(
            f"{GITLAB_API}/projects/{project_id}/repository/files/{file_path.replace('/', '%2F')}",
            headers=_headers(),
            json=data,
        )

    resp.raise_for_status()
    logger.info(f"GitLab 文件已更新: {file_path}")
    return resp.json()


async def create_merge_request(
    git_repo: str,
    source_branch: str,
    target_branch: str,
    title: str,
    description: str = "",
) -> dict:
    """创建 Merge Request。"""
    project_id = _parse_repo(git_repo)
    client = _get_client()
    resp = await client.post(
        f"{GITLAB_API}/projects/{project_id}/merge_requests",
        headers=_headers(),
        json={
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": description,
        },
    )
    resp.raise_for_status()
    mr = resp.json()
    logger.info(f"GitLab MR 已创建: {mr['web_url']}")
    return mr
