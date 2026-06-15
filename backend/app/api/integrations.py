"""第三方集成：Jira / Linear / Confluence。"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.auth import require_role
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


# ── 配置 ──

class IntegrationConfig(BaseModel):
    provider: str  # jira | linear | confluence
    base_url: str
    api_token: str
    project_key: str | None = None


class IssueLink(BaseModel):
    issue_key: str
    title: str
    url: str
    status: str | None = None


# ── Jira 集成 ──

@router.post("/jira/sync")
async def sync_jira_issues(
    config: IntegrationConfig,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager")),
):
    """从 Jira 同步 Issue 到任务。"""
    import httpx

    if not config.api_token:
        raise HTTPException(status_code=400, detail="Jira API Token 未配置")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{config.base_url}/rest/api/3/search",
                params={"jql": f"project={config.project_key} AND status=To Do", "maxResults": 10},
                headers={"Authorization": f"Bearer {config.api_token}", "Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        issues = []
        for issue in data.get("issues", []):
            issues.append(IssueLink(
                issue_key=issue["key"],
                title=issue["fields"]["summary"],
                url=f"{config.base_url}/browse/{issue['key']}",
                status=issue["fields"]["status"]["name"],
            ))

        return {"synced": len(issues), "issues": [i.model_dump() for i in issues]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Jira 同步失败: {e}")


@router.post("/jira/webhook")
async def jira_webhook(body: dict):
    """Jira Webhook 回调：Issue 更新时触发。"""
    issue_key = body.get("issue", {}).get("key")
    if not issue_key:
        return {"status": "ignored"}

    logger.info(f"Jira webhook: {issue_key} updated")
    # TODO: 触发关联工作流
    return {"status": "received", "issue_key": issue_key}


# ── Linear 集成 ──

@router.post("/linear/sync")
async def sync_linear_issues(
    config: IntegrationConfig,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager")),
):
    """从 Linear 同步 Issue。"""
    import httpx

    if not config.api_token:
        raise HTTPException(status_code=400, detail="Linear API Token 未配置")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.linear.app/graphql",
                json={"query": "{ issues(first: 10) { nodes { identifier title url state { name } } } }"},
                headers={"Authorization": config.api_token},
            )
            resp.raise_for_status()
            data = resp.json()

        issues = []
        for issue in data.get("data", {}).get("issues", {}).get("nodes", []):
            issues.append(IssueLink(
                issue_key=issue["identifier"],
                title=issue["title"],
                url=issue["url"],
                status=issue.get("state", {}).get("name"),
            ))

        return {"synced": len(issues), "issues": [i.model_dump() for i in issues]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Linear 同步失败: {e}")


# ── Confluence 集成 ──

@router.post("/confluence/publish")
async def publish_to_confluence(
    config: IntegrationConfig,
    task_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_role("admin", "manager")),
):
    """将任务执行报告发布到 Confluence。"""
    import httpx

    if not config.api_token:
        raise HTTPException(status_code=400, detail="Confluence API Token 未配置")

    # 获取任务详情
    from app.models.task import Task
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Task).options(selectinload(Task.step_executions)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 生成 Confluence 内容
    content = f"""<h1>Agent Orchestrator 执行报告</h1>
<p><strong>任务 ID:</strong> {task.id}</p>
<p><strong>状态:</strong> {task.status}</p>
<p><strong>Token 消耗:</strong> {task.total_tokens_used}</p>
<h2>步骤执行详情</h2>
<table><tr><th>步骤</th><th>类型</th><th>状态</th><th>Token</th></tr>"""

    for s in task.step_executions:
        content += f"<tr><td>{s.step_name}</td><td>{s.step_type}</td><td>{s.status}</td>"
        content += f"<td>{s.token_usage.get('tokens', 0) if s.token_usage else 0}</td></tr>"
    content += "</table>"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{config.base_url}/rest/api/content",
                json={
                    "type": "page",
                    "title": f"Agent 执行报告 - {task.id}",
                    "space": {"key": config.project_key},
                    "body": {"storage": {"value": content, "representation": "storage"}},
                },
                headers={"Authorization": f"Bearer {config.api_token}", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        return {"status": "published", "url": f"{config.base_url}/wiki{data['_links']['webui']}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Confluence 发布失败: {e}")


# ── 集成状态检查 ──

@router.get("/status")
async def integration_status():
    """返回各集成的配置状态。"""
    return {
        "jira": {"configured": bool(getattr(settings, "JIRA_BASE_URL", ""))},
        "linear": {"configured": bool(getattr(settings, "LINEAR_API_KEY", ""))},
        "confluence": {"configured": bool(getattr(settings, "CONFLUENCE_BASE_URL", ""))},
        "github": {"configured": bool(settings.GITHUB_TOKEN)},
        "gitlab": {"configured": bool(settings.GITLAB_TOKEN)},
    }
