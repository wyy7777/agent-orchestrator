"""GitHub 集成：分支创建、文件写入、commit、PR 创建。"""

import base64
import logging
from datetime import datetime

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _parse_repo(git_repo: str) -> tuple[str, str]:
    """从 git_repo URL 解析 owner/repo。"""
    # 支持: https://github.com/owner/repo.git 或 owner/repo
    repo = git_repo.rstrip("/").rstrip(".git")
    if repo.startswith("https://"):
        parts = repo.replace("https://github.com/", "").split("/")
    else:
        parts = repo.split("/")
    if len(parts) < 2:
        raise ValueError(f"无法解析仓库: {git_repo}")
    return parts[-2], parts[-1]


async def get_default_branch(owner: str, repo: str) -> str:
    """获取仓库的默认分支名。"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()["default_branch"]


async def get_main_sha(owner: str, repo: str, branch: str) -> str:
    """获取分支最新 commit SHA。"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch}",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()["object"]["sha"]


async def create_branch(owner: str, repo: str, branch_name: str, base_branch: str) -> str:
    """创建新分支，返回分支 ref。"""
    sha = await get_main_sha(owner, repo, base_branch)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/refs",
            headers=_headers(),
            json={"ref": f"refs/heads/{branch_name}", "sha": sha},
        )
        resp.raise_for_status()
        logger.info(f"分支 {branch_name} 已创建")
        return resp.json()["ref"]


async def write_file(
    owner: str,
    repo: str,
    branch: str,
    file_path: str,
    content: str,
    commit_message: str = "Agent: 更新文件",
) -> dict:
    """写入或更新文件到指定分支。"""
    async with httpx.AsyncClient() as client:
        # 先尝试获取文件 SHA（如果文件已存在）
        sha = None
        try:
            existing = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/contents/{file_path}",
                headers=_headers(),
                params={"ref": branch},
            )
            if existing.status_code == 200:
                sha = existing.json().get("sha")
        except Exception:
            pass

        body = {
            "message": commit_message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "branch": branch,
        }
        if sha:
            body["sha"] = sha

        resp = await client.put(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{file_path}",
            headers=_headers(),
            json=body,
        )
        resp.raise_for_status()
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
    """创建 Pull Request。"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
            headers=_headers(),
            json={
                "title": title,
                "head": head_branch,
                "base": base_branch,
                "body": body,
            },
        )
        resp.raise_for_status()
        pr_url = resp.json()["html_url"]
        logger.info(f"PR 已创建: {pr_url}")
        return resp.json()
