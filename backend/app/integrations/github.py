"""GitHub 集成：分支创建、文件写入、commit、PR 创建。"""

import asyncio
import base64
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

# 全局共享 httpx 客户端
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
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _parse_repo(git_repo: str) -> tuple[str, str]:
    """从 git_repo URL 解析 owner/repo。"""
    repo = git_repo.rstrip("/").rstrip(".git")
    if repo.startswith("https://"):
        parts = repo.replace("https://github.com/", "").split("/")
    else:
        parts = repo.split("/")
    if len(parts) < 2:
        raise ValueError(f"无法解析仓库: {git_repo}")
    return parts[-2], parts[-1]


# 兼容旧代码的别名
parse_repo_url = _parse_repo


def _validate_file_path(file_path: str) -> str:
    """校验文件路径，防止路径穿越。"""
    if not file_path or ".." in file_path or file_path.startswith("/"):
        raise ValueError(f"不安全的文件路径: {file_path}")
    if not re.match(r'^[a-zA-Z0-9_\-./]+$', file_path):
        raise ValueError(f"文件路径包含非法字符: {file_path}")
    if len(file_path) > 256:
        raise ValueError(f"文件路径过长: {len(file_path)} > 256")
    return file_path


async def _retry_request(method: str, url: str, max_retries: int = 3, **kwargs) -> httpx.Response:
    """带重试的 HTTP 请求。"""
    last_error = None
    for attempt in range(max_retries):
        try:
            client = _get_client()
            resp = await client.request(method, url, **kwargs)
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
                from datetime import datetime
                wait = max(min(reset_time - int(datetime.now().timestamp()), 60), 5)
                logger.warning(f"GitHub API 限流，等待 {wait}s")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500 and attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(f"GitHub API 服务端错误 {e.response.status_code}，{wait}s 后重试")
                await asyncio.sleep(wait)
                last_error = e
                continue
            raise
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(f"GitHub API 连接失败: {e}，{wait}s 后重试")
                await asyncio.sleep(wait)
                last_error = e
                continue
            raise
    raise last_error


async def get_default_branch(owner: str, repo: str) -> str:
    resp = await _retry_request("GET", f"{GITHUB_API}/repos/{owner}/{repo}")
    return resp.json()["default_branch"]


async def get_main_sha(owner: str, repo: str, branch: str) -> str:
    resp = await _retry_request("GET", f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch}")
    return resp.json()["object"]["sha"]


async def create_branch(owner: str, repo: str, branch_name: str, base_branch: str) -> str:
    sha = await get_main_sha(owner, repo, base_branch)
    resp = await _retry_request(
        "POST",
        f"{GITHUB_API}/repos/{owner}/{repo}/git/refs",
        json={"ref": f"refs/heads/{branch_name}", "sha": sha},
    )
    logger.info(f"分支 {branch_name} 已创建")
    return resp.json()["ref"]


async def get_file(owner: str, repo: str, file_path: str, ref: str = "main") -> dict:
    """获取文件信息。"""
    resp = await _retry_request(
        "GET",
        f"{GITHUB_API}/repos/{owner}/{repo}/contents/{file_path}",
        params={"ref": ref},
    )
    return resp.json()


async def write_file(
    owner: str,
    repo: str,
    branch: str,
    file_path: str,
    content: str,
    commit_message: str = "Agent: 更新文件",
) -> dict:
    """写入或更新文件到指定分支。"""
    file_path = _validate_file_path(file_path)

    sha = None
    try:
        existing = await get_file(owner, repo, file_path, ref=branch)
        sha = existing.get("sha")
    except Exception:
        pass

    body = {
        "message": commit_message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    resp = await _retry_request(
        "PUT",
        f"{GITHUB_API}/repos/{owner}/{repo}/contents/{file_path}",
        json=body,
    )
    logger.info(f"文件 {file_path} 已写入分支 {branch}")
    return resp.json()


async def create_pr(
    owner: str,
    repo: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str = "",
) -> dict:
    resp = await _retry_request(
        "POST",
        f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
        json={
            "title": title,
            "head": head_branch,
            "base": base_branch,
            "body": body,
        },
    )
    pr_url = resp.json()["html_url"]
    logger.info(f"PR 已创建: {pr_url}")
    return resp.json()


class GitHubClient:
    """GitHub API 客户端封装类，兼容旧代码。"""

    def __init__(self, token: str | None = None):
        self.token = token or settings.GITHUB_TOKEN

    async def get_repo(self, owner: str, repo: str) -> dict:
        resp = await _retry_request("GET", f"{GITHUB_API}/repos/{owner}/{repo}")
        return resp.json()

    async def get_branch(self, owner: str, repo: str, branch: str) -> dict:
        resp = await _retry_request("GET", f"{GITHUB_API}/repos/{owner}/{repo}/branches/{branch}")
        return resp.json()

    async def create_branch(self, owner: str, repo: str, branch: str, sha: str) -> dict:
        resp = await _retry_request(
            "POST",
            f"{GITHUB_API}/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": sha},
        )
        return resp.json()

    async def get_file(self, owner: str, repo: str, path: str, ref: str = "main") -> dict:
        return await get_file(owner, repo, path, ref)

    async def create_or_update_file(
        self, owner: str, repo: str, path: str, content: str,
        message: str, branch: str, sha: str | None = None,
    ) -> dict:
        return await write_file(owner, repo, branch, path, content, message)

    async def create_pull_request(
        self, owner: str, repo: str, title: str,
        head: str, base: str, body: str = "",
    ) -> dict:
        return await create_pr(owner, repo, head, base, title, body)
