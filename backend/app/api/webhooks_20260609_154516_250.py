import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
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


# ---------- 签名与认证 ----------


def _verify_github_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    """验证 GitHub X-Hub-Signature-256 签名。"""
    if not signature or not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _verify_webhook_auth(
    request: Request,
    webhook: Webhook,
    body: bytes,
) -> None:
    """验证 webhook 请求认证（api_key 或 hmac）。auth_type=none 时直接拒绝。"""
    if webhook.auth_type == "none":
        logger.warning(f"Webhook {webhook.id}: auth_type=none，请求被拒绝")
        raise HTTPException(status_code=401, detail="未配置认证方式")

    if webhook.auth_type == "api_key":
        api_key = request.headers.get("X-API-Key")
        expected_key = (webhook.auth_config or {}).get("api_key", "")
        if not api_key or not hmac.compare_digest(api_key, expected_key):
            logger.warning(f"Webhook {webhook.id}: API Key 验证失败")
            raise HTTPException(status_code=401, detail="认证失败")

    elif webhook.auth_type == "hmac":
        signature = request.headers.get("X-Signature-256")
        secret = (webhook.auth_config or {}).get("secret", "")
        if not _verify_github_signature(body, signature, secret):
            logger.warning(f"Webhook {webhook.id}: HMAC 签名验证失败")
            raise HTTPException(status_code=401, detail="认证失败")

    else:
        logger.warning(f"Webhook {webhook.id}: 未知 auth_type={webhook.auth_type}")
        raise HTTPException(status_code=401, detail="认证失败")


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
        logger.warning("GitHub Webhook 请求被拒绝：未配置")
        raise HTTPException(status_code=404, detail="请求的资源不存在")

    # 签名验证（GitHub 固定使用 HMAC）
    secret = webhook.secret or settings.GITHUB_WEBHOOK_SECRET
    if secret and not _verify_github_signature(body, x_hub_signature_256, secret):
        logger.warning("GitHub Webhook: 签名验证失败")
        raise HTTPException(status_code=403, detail="认证失败")

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
        logger.error(f"GitHub Webhook {webhook.id}: 目标工作流 {webhook.target_workflow_id} 不存在")
        raise HTTPException(status_code=500, detail="请求处理失败")

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
    """接收任意 JSON payload，根据配置创建工作流任务。需通过 webhook 配置的认证方式。"""
    body = await request.body()
    payload = await request.json()

    # 从 payload 中获取 webhook_id 或 workflow_id
    webhook_id = payload.pop("_webhook_id", None)
    workflow_id = payload.pop("_workflow_id", None)

    if webhook_id:
        result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
        webhook = result.scalar_one_or_none()
        if not webhook:
            logger.warning(f"Generic Webhook: webhook_id={webhook_id} 不存在")
            raise HTTPException(status_code=404, detail="请求的资源不存在")
        _verify_webhook_auth(request, webhook, body)
        target_wf_id = webhook.target_workflow_id
    elif workflow_id:
        wf_result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
        if not wf_result.scalar_one_or_none():
            logger.warning(f"Generic Webhook: workflow_id={workflow_id} 不存在")
            raise HTTPException(status_code=404, detail="请求的资源不存在")
        target_wf_id = workflow_id
    else:
        raise HTTPException(
            status_code=400,
            detail="payload 中必须包含 _webhook_id 或 _workflow_id",
        )

    # 验证目标工作流存在
    wf_result = await db.execute(select(Workflow).where(Workflow.id == target_wf_id))
    if not wf_result.scalar_one_or_none():
        logger.error(f"Generic Webhook: 目标工作流 {target_wf_id} 不存在")
        raise HTTPException(status_code=500, detail="请求处理失败")

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


VALID_SORT_FIELDS = {
    "created_at": Webhook.created_at,
    "name": Webhook.name,
}

VALID_WEBHOOK_TYPES = {"github", "generic"}
VALID_AUTH_TYPES = {"none", "api_key", "hmac"}


@router.get("", response_model=WebhookListResponse)
async def list_webhooks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向"),
    db: AsyncSession = Depends(get_db),
):
    if sort_by not in VALID_SORT_FIELDS:
        raise HTTPException(status_code=400, detail=f"无效排序字段: {sort_by}")
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="排序方向只能是 asc 或 desc")

    total_result = await db.execute(select(func.count(Webhook.id)))
    total = total_result.scalar() or 0

    order_column = VALID_SORT_FIELDS[sort_by]
    order = order_column.asc() if sort_order == "asc" else order_column.desc()

    offset = (page - 1) * page_size
    result = await db.execute(
        select(Webhook).order_by(order).offset(offset).limit(page_size)
    )
    items = result.scalars().all()
    return WebhookListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=WebhookResponse, status_code=201)
async def create_webhook(body: WebhookCreate, db: AsyncSession = Depends(get_db)):
    if body.webhook_type not in VALID_WEBHOOK_TYPES:
        raise HTTPException(status_code=400, detail="无效的 webhook 类型")
    if body.auth_type not in VALID_AUTH_TYPES:
        raise HTTPException(status_code=400, detail="无效的认证类型")

    # 验证目标工作流存在
    wf_result = await db.execute(
        select(Workflow).where(Workflow.id == body.target_workflow_id)
    )
    if not wf_result.scalar_one_or_none():
        logger.warning(f"创建 Webhook 失败: 目标工作流 {body.target_workflow_id} 不存在")
        raise HTTPException(status_code=404, detail="请求的资源不存在")

    webhook = Webhook(
        name=body.name,
        webhook_type=body.webhook_type,
        target_workflow_id=body.target_workflow_id,
        auth_type=body.auth_type,
        auth_config=body.auth_config,
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
        raise HTTPException(status_code=404, detail="请求的资源不存在")
    await db.delete(webhook)