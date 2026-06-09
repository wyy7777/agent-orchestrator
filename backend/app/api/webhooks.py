import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.task import Task
from app.models.webhook import Webhook
from app.models.workflow import Workflow
from app.schemas.webhook import WebhookCreate, WebhookListResponse, WebhookResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


# ---------- 签名验证 ----------


def _verify_github_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    """验证 GitHub X-Hub-Signature-256 签名。"""
    if not signature or not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------- GitHub Webhook ----------


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: str | None = Header(None, alias="X-GitHub-Event"),
    db: AsyncSession = Depends(get_db),
):
    """接收 GitHub Webhook 事件（issue_comment / pull_request），自动创建任务。"""
    body = await request.body()

    # 查找匹配的 webhook 配置（取第一个 github 类型且有 secret 的）
    result = await db.execute(select(Webhook).where(Webhook.webhook_type == "github"))
    webhook = result.scalars().first()

    if not webhook:
        raise HTTPException(status_code=404, detail="未配置 GitHub Webhook")

    # 签名验证
    secret = webhook.secret or settings.GITHUB_WEBHOOK_SECRET
    if secret and not _verify_github_signature(body, x_hub_signature_256, secret):
        raise HTTPException(status_code=403, detail="签名验证失败")

    payload = await request.json()

    # 根据事件类型决定是否创建任务
    action = payload.get("action")
    issue = payload.get("issue") or payload.get("pull_request")

    trigger_payload = {
        "event": x_github_event,
        "action": action,
        "issue": issue,
        "repository": payload.get("repository", {}).get("full_name"),
    }

    # 仅处理 issue_comment 和 pull_request 事件
    should_create = False
    if x_github_event == "issue_comment" and action == "created":
        # 检查评论中是否包含触发关键词
        comment_body = (
            payload.get("comment", {}).get("body", "").lower()
        )
        if any(kw in comment_body for kw in ["@agent", "/fix", "/review"]):
            should_create = True
    elif x_github_event == "pull_request" and action in ("opened", "synchronize"):
        should_create = True

    if not should_create:
        return {"status": "ignored", "event": x_github_event, "action": action}

    # 验证目标工作流存在
    wf_result = await db.execute(
        select(Workflow).where(Workflow.id == webhook.target_workflow_id)
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(status_code=500, detail="目标工作流不存在")

    task = Task(
        workflow_id=webhook.target_workflow_id,
        trigger_type="github_webhook",
        trigger_payload=trigger_payload,
        git_repo=trigger_payload.get("repository"),
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    logger.info(f"GitHub Webhook 创建任务: {task.id} (event={x_github_event})")
    return {"status": "task_created", "task_id": task.id}


# ---------- 通用 Webhook ----------


@router.post("/generic")
async def generic_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """接收任意 JSON payload，根据配置创建工作流任务。"""
    payload = await request.json()

    # 从 payload 中获取 webhook_id 或 workflow_id
    webhook_id = payload.pop("_webhook_id", None)
    workflow_id = payload.pop("_workflow_id", None)

    if webhook_id:
        result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
        webhook = result.scalar_one_or_none()
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook 不存在")
        target_wf_id = webhook.target_workflow_id
    elif workflow_id:
        wf_result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
        if not wf_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="工作流不存在")
        target_wf_id = workflow_id
    else:
        raise HTTPException(
            status_code=400,
            detail="payload 中必须包含 _webhook_id 或 _workflow_id",
        )

    task = Task(
        workflow_id=target_wf_id,
        trigger_type="generic_webhook",
        trigger_payload=payload,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    logger.info(f"通用 Webhook 创建任务: {task.id}")
    return {"status": "task_created", "task_id": task.id}


# ---------- CRUD ----------


@router.get("", response_model=WebhookListResponse)
async def list_webhooks(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(Webhook.id)))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(Webhook).order_by(Webhook.created_at.desc()).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return WebhookListResponse(items=items, total=total)


@router.post("", response_model=WebhookResponse, status_code=201)
async def create_webhook(body: WebhookCreate, db: AsyncSession = Depends(get_db)):
    if body.webhook_type not in ("github", "generic"):
        raise HTTPException(status_code=400, detail="webhook_type 必须是 github 或 generic")

    # 验证目标工作流存在
    wf_result = await db.execute(
        select(Workflow).where(Workflow.id == body.target_workflow_id)
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="目标工作流不存在")

    webhook = Webhook(
        name=body.name,
        webhook_type=body.webhook_type,
        target_workflow_id=body.target_workflow_id,
        secret=body.secret,
        config=body.config,
    )
    db.add(webhook)
    await db.flush()
    await db.refresh(webhook)
    return webhook


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(webhook_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook 不存在")
    await db.delete(webhook)
