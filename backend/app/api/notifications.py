import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.notifier import build_notification_manager, notifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

# 通知历史（内存存储，进程重启后清空）
_notification_history: list[dict] = []
MAX_HISTORY = 200


# ---------- Schemas ----------


class NotificationConfig(BaseModel):
    slack_webhook_url: str = ""
    dingtalk_webhook_url: str = ""
    notify_on_task_complete: bool = True
    notify_on_task_fail: bool = True
    notify_on_approval_needed: bool = True


class NotificationConfigResponse(NotificationConfig):
    console_enabled: bool = True
    slack_enabled: bool = False
    dingtalk_enabled: bool = False


class TestNotificationRequest(BaseModel):
    channel: str = "all"  # all / slack / dingtalk / console
    message: str = "这是一条来自 Agent Orchestrator 的测试通知"


class NotificationHistoryItem(BaseModel):
    id: str
    channel: str
    event_type: str
    title: str
    status: str
    error_message: str | None = None
    created_at: str


class NotificationHistoryResponse(BaseModel):
    items: list[NotificationHistoryItem]
    total: int


# ---------- 内部工具 ----------


def _record_history(level: str, message: str, channel: str, event_type: str = "test", title: str = "") -> None:
    _notification_history.insert(0, {
        "id": str(uuid.uuid4()),
        "channel": channel,
        "event_type": event_type,
        "title": title or message,
        "status": "success" if level != "error" else "failed",
        "error_message": message if level == "error" else None,
        "created_at": datetime.now(UTC).isoformat(),
    })
    if len(_notification_history) > MAX_HISTORY:
        _notification_history.pop()


# ---------- Routes ----------


def _mask_url(url: str) -> str:
    """对 webhook URL 进行脱敏，只保留前 10 个字符 + ***。"""
    if not url:
        return ""
    if len(url) <= 10:
        return url + "***"
    return url[:10] + "***"


@router.get("/config", response_model=NotificationConfigResponse)
async def get_notification_config():
    """获取当前通知配置。"""
    return NotificationConfigResponse(
        slack_webhook_url=_mask_url(settings.SLACK_WEBHOOK_URL),
        dingtalk_webhook_url=_mask_url(settings.DINGTALK_WEBHOOK_URL),
        notify_on_task_complete=settings.NOTIFY_ON_TASK_COMPLETE,
        notify_on_task_fail=settings.NOTIFY_ON_TASK_FAIL,
        notify_on_approval_needed=settings.NOTIFY_ON_APPROVAL_NEEDED,
        console_enabled=True,
        slack_enabled=bool(settings.SLACK_WEBHOOK_URL),
        dingtalk_enabled=bool(settings.DINGTALK_WEBHOOK_URL),
    )


@router.put("/config", response_model=NotificationConfigResponse)
async def update_notification_config(body: NotificationConfig):
    """更新通知配置。修改运行时内存中的 settings 并重建通知管理器。"""
    global notifier

    settings.SLACK_WEBHOOK_URL = body.slack_webhook_url
    settings.DINGTALK_WEBHOOK_URL = body.dingtalk_webhook_url
    settings.NOTIFY_ON_TASK_COMPLETE = body.notify_on_task_complete
    settings.NOTIFY_ON_TASK_FAIL = body.notify_on_task_fail
    settings.NOTIFY_ON_APPROVAL_NEEDED = body.notify_on_approval_needed

    # 重建全局通知管理器，使新配置立即生效
    new_manager = build_notification_manager()
    notifier.notifiers = new_manager.notifiers

    logger.info("通知配置已更新")

    return NotificationConfigResponse(
        slack_webhook_url=settings.SLACK_WEBHOOK_URL,
        dingtalk_webhook_url=settings.DINGTALK_WEBHOOK_URL,
        notify_on_task_complete=settings.NOTIFY_ON_TASK_COMPLETE,
        notify_on_task_fail=settings.NOTIFY_ON_TASK_FAIL,
        notify_on_approval_needed=settings.NOTIFY_ON_APPROVAL_NEEDED,
        console_enabled=True,
        slack_enabled=bool(settings.SLACK_WEBHOOK_URL),
        dingtalk_enabled=bool(settings.DINGTALK_WEBHOOK_URL),
    )


@router.post("/test")
async def test_notification(body: TestNotificationRequest):
    """发送测试通知，验证通知渠道是否正常。"""
    results: dict[str, bool] = {}

    for n in notifier.notifiers:
        name = n.__class__.__name__

        # 按 channel 过滤
        if body.channel != "all":
            channel_map = {
                "slack": "SlackNotifier",
                "dingtalk": "DingTalkNotifier",
                "console": "ConsoleNotifier",
            }
            if name != channel_map.get(body.channel):
                continue

        ok = await n.send(body.message, "info")
        results[name] = ok
        _record_history("info", body.message, name)

    if not results:
        raise HTTPException(status_code=400, detail=f"未找到匹配的通知渠道: {body.channel}")

    return {"results": results}


@router.get("/history", response_model=NotificationHistoryResponse)
async def get_notification_history(skip: int = 0, limit: int = 50):
    """获取通知发送历史。"""
    items = _notification_history[skip: skip + limit]
    return NotificationHistoryResponse(
        items=[NotificationHistoryItem(**item) for item in items],
        total=len(_notification_history),
    )
