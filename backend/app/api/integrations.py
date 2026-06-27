"""第三方集成：Jira / Linear / Confluence。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.auth import require_role
from app.config import settings
from app.database import get_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User

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
async def jira_webhook(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Jira Webhook 回调：Issue 创建/更新时自动触发关联工作流。"""
    issue = body.get("issue", {})
    issue_key = issue.get("key")
    if not issue_key:
        return {"status": "ignored"}

    webhook_event = body.get("webhookEvent", "")
    logger.info(f"Jira webhook: {issue_key} - {webhook_event}")

    # 只处理 Issue 创建和更新事件
    if webhook_event not in ("jira:issue_created", "jira:issue_updated"):
        return {"status": "ignored", "reason": "event not handled"}

    # 查找匹配的 workflow（按 project key 或 label 匹配）
    from app.engine.yaml_parser import parse_workflow_yaml
    from app.models.task import Task
    from app.models.workflow import Workflow

    project_key = issue_key.split("-")[0] if "-" in issue_key else ""

    # 查找包含 jira_project 配置的工作流
    result = await db.execute(select(Workflow))
    workflows = result.scalars().all()

    matched_workflow = None
    for wf in workflows:
        try:
            wf_def = parse_workflow_yaml(wf.yaml_definition)
            # 检查工作流 settings 中是否有 jira_project 匹配
            wf_project = wf_def.settings.get("jira_project", "")
            if wf_project and wf_project.upper() == project_key.upper():
                matched_workflow = wf
                break
            # 也检查 description 中是否包含 project key
            if project_key.upper() in (wf.description or "").upper():
                matched_workflow = wf
                break
        except Exception:
            continue

    if not matched_workflow:
        logger.info(f"Jira webhook: 未找到匹配 project '{project_key}' 的工作流")
        return {"status": "received", "issue_key": issue_key, "workflow_triggered": False}

    # 自动创建任务
    task = Task(
        workflow_id=matched_workflow.id,
        trigger_type="webhook",
        trigger_payload={
            "source": "jira",
            "issue_key": issue_key,
            "issue_summary": issue.get("fields", {}).get("summary", ""),
            "issue_body": issue.get("fields", {}).get("description", ""),
            "issue_status": issue.get("fields", {}).get("status", {}).get("name", ""),
            "event": webhook_event,
        },
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    logger.info(f"Jira webhook: 已创建任务 {task.id} (工作流: {matched_workflow.name})")
    return {
        "status": "received",
        "issue_key": issue_key,
        "workflow_triggered": True,
        "workflow_name": matched_workflow.name,
        "task_id": task.id,
    }


@router.post("/linear/webhook")
async def linear_webhook(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Linear Webhook 回调：Issue 创建时自动触发关联工作流。"""
    action = body.get("action", "")
    issue_data = body.get("data", {})
    issue_id = issue_data.get("identifier", "")
    issue_title = issue_data.get("title", "")

    if not issue_id:
        return {"status": "ignored"}

    logger.info(f"Linear webhook: {issue_id} - {action}")

    # 只处理 Issue 创建事件
    if action != "create":
        return {"status": "received", "issue_id": issue_id, "workflow_triggered": False}

    # 查找匹配的 workflow
    from app.engine.yaml_parser import parse_workflow_yaml
    from app.models.task import Task
    from app.models.workflow import Workflow

    team_key = issue_id.split("-")[0] if "-" in issue_id else ""

    result = await db.execute(select(Workflow))
    workflows = result.scalars().all()

    matched_workflow = None
    for wf in workflows:
        try:
            wf_def = parse_workflow_yaml(wf.yaml_definition)
            wf_team = wf_def.settings.get("linear_team", "")
            if wf_team and wf_team.upper() == team_key.upper():
                matched_workflow = wf
                break
        except Exception:
            continue

    if not matched_workflow:
        return {"status": "received", "issue_id": issue_id, "workflow_triggered": False}

    task = Task(
        workflow_id=matched_workflow.id,
        trigger_type="webhook",
        trigger_payload={
            "source": "linear",
            "issue_id": issue_id,
            "issue_summary": issue_title,
            "issue_body": issue_data.get("description", ""),
            "event": action,
        },
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    logger.info(f"Linear webhook: 已创建任务 {task.id} (工作流: {matched_workflow.name})")
    return {
        "status": "received",
        "issue_id": issue_id,
        "workflow_triggered": True,
        "workflow_name": matched_workflow.name,
        "task_id": task.id,
    }


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
    from sqlalchemy.orm import selectinload

    from app.models.task import Task
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
