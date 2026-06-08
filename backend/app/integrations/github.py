from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class GitHubClient:
    """GitHub API 客户端，用于创建分支、提交和 PR。"""

    def __init__(self, token: str | None = None):
        self.token = token or settings.GITHUB_TOKEN
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(
        self, method: str, path: str, json_data: dict | None = None
    ) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method,
                f"{self.base_url}{path}",
                headers=self.headers,
                json=json_data,
                timeout=30,
            )
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"GitHub API 错误 ({resp.status_code}): {resp.text}"
                )
            return resp.json()

    async def get_repo(self, owner: str, repo: str) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}")

    async def get_branch(self, owner: str, repo: str, branch: str) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/branches/{branch}")

    async def create_branch(
        self, owner: str, repo: str, branch: str, sha: str
    ) -> dict:
        return await self._request(
            "POST",
            f"/repos/{owner}/{repo}/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": sha},
        )

    async def get_file(
        self, owner: str, repo: str, path: str, ref: str = "main"
    ) -> dict:
        return await self._request(
            "GET", f"/repos/{owner}/{repo}/contents/{path}?ref={ref}"
        )

    async def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: str | None = None,
    ) -> dict:
        import base64

        data: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if sha:
            data["sha"] = sha
        return await self._request(
            "PUT", f"/repos/{owner}/{repo}/contents/{path}", data
        )

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str = "",
    ) -> dict:
        return await self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            {"title": title, "head": head, "base": base, "body": body},
        )


def parse_repo_url(repo_url: str) -> tuple[str, str]:
    """从 GitHub URL 或 'owner/repo' 格式解析出 owner 和 repo。

    支持格式：
    - https://github.com/owner/repo
    - git@github.com:owner/repo.git
    - owner/repo
    """
    url = repo_url.strip().rstrip("/")

    if url.startswith("https://github.com/"):
        url = url.replace("https://github.com/", "")
    elif url.startswith("git@github.com:"):
        url = url.replace("git@github.com:", "")

    url = url.removesuffix(".git")
    parts = url.split("/")
    if len(parts) != 2:
        raise ValueError(f"无法解析仓库地址: {repo_url}")

    return parts[0], parts[1]
