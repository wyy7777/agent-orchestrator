from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class Notifier(ABC):
    """通知接口抽象基类。"""

    @abstractmethod
    async def send(self, message: str, level: str = "info") -> bool:
        """发送通知。level: info / warning / error / success"""
        ...


class SlackNotifier(Notifier):
    """通过 Slack Incoming Webhook 发送通知。"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, message: str, level: str = "info") -> bool:
        emoji_map = {
            "info": ":information_source:",
            "success": ":white_check_mark:",
            "warning": ":warning:",
            "error": ":x:",
        }
        emoji = emoji_map.get(level, ":bell:")
        payload = {"text": f"{emoji} {message}"}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.webhook_url, json=payload)
                if resp.status_code == 200 and resp.text == "ok":
                    return True
                logger.warning(f"Slack 通知返回异常: status={resp.status_code}, body={resp.text}")
                return False
        except Exception as e:
            logger.error(f"Slack 通知发送失败: {e}")
            return False


class DingTalkNotifier(Notifier):
    """通过钉钉机器人 Webhook 发送通知。"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, message: str, level: str = "info") -> bool:
        title_map = {
            "info": "信息通知",
            "success": "执行成功",
            "warning": "警告通知",
            "error": "执行失败",
        }
        title = title_map.get(level, "通知")
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"### {title}\n\n{message}",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.webhook_url, json=payload)
                data = resp.json()
                if data.get("errcode") == 0:
                    return True
                logger.warning(f"钉钉通知返回异常: {data}")
                return False
        except Exception as e:
            logger.error(f"钉钉通知发送失败: {e}")
            return False


class WeChatWorkNotifier(Notifier):
    """通过企业微信机器人 Webhook 发送通知。"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, message: str, level: str = "info") -> bool:
        emoji_map = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
        }
        emoji = emoji_map.get(level, "📢")
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"{emoji} **Agent Orchestrator**\n\n{message}",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.webhook_url, json=payload)
                data = resp.json()
                if data.get("errcode") == 0:
                    return True
                logger.warning(f"企业微信通知返回异常: {data}")
                return False
        except Exception as e:
            logger.error(f"企业微信通知发送失败: {e}")
            return False


class FeishuNotifier(Notifier):
    """通过飞书机器人 Webhook 发送通知。"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, message: str, level: str = "info") -> bool:
        emoji_map = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
        }
        emoji = emoji_map.get(level, "📢")
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"{emoji} Agent Orchestrator"},
                    "template": {"info": "blue", "success": "green", "warning": "orange", "error": "red"}.get(level, "blue"),
                },
                "elements": [
                    {"tag": "markdown", "content": message},
                ],
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.webhook_url, json=payload)
                data = resp.json()
                if data.get("code") == 0 or data.get("StatusCode") == 0:
                    return True
                logger.warning(f"飞书通知返回异常: {data}")
                return False
        except Exception as e:
            logger.error(f"飞书通知发送失败: {e}")
            return False


class ConsoleNotifier(Notifier):
    """将通知打印到控制台（默认实现）。"""

    async def send(self, message: str, level: str = "info") -> bool:
        prefix = {
            "info": "[INFO]",
            "success": "[SUCCESS]",
            "warning": "[WARNING]",
            "error": "[ERROR]",
        }.get(level, "[INFO]")
        print(f"{prefix} {message}")
        return True


class NotificationManager:
    """通知管理器，聚合多个 Notifier 实例统一发送。"""

    def __init__(self):
        self.notifiers: list[Notifier] = []

    def add_notifier(self, notifier: Notifier) -> None:
        self.notifiers.append(notifier)

    async def notify(self, message: str, level: str = "info") -> None:
        if not self.notifiers:
            return
        for notifier in self.notifiers:
            try:
                await notifier.send(message, level)
            except Exception as e:
                logger.error(f"通知发送异常 ({notifier.__class__.__name__}): {e}")

    # ---- 便捷触发方法 ----

    async def notify_task_started(self, task_id: str, workflow_name: str) -> None:
        msg = f"任务已开始 | task_id={task_id} | workflow={workflow_name}"
        await self.notify(msg, "info")

    async def notify_task_completed(self, task_id: str, workflow_name: str) -> None:
        if not settings.NOTIFY_ON_TASK_COMPLETE:
            return
        msg = f"任务已完成 | task_id={task_id} | workflow={workflow_name}"
        await self.notify(msg, "success")

    async def notify_task_failed(self, task_id: str, workflow_name: str, error: str) -> None:
        if not settings.NOTIFY_ON_TASK_FAIL:
            return
        msg = f"任务失败 | task_id={task_id} | workflow={workflow_name}\n错误: {error}"
        await self.notify(msg, "error")

    async def notify_step_completed(self, task_id: str, step_name: str) -> None:
        msg = f"步骤完成 | task_id={task_id} | step={step_name}"
        await self.notify(msg, "info")

    async def notify_step_failed(self, task_id: str, step_name: str, error: str) -> None:
        msg = f"步骤失败 | task_id={task_id} | step={step_name}\n错误: {error}"
        await self.notify(msg, "error")

    async def notify_approval_needed(self, task_id: str, step_name: str) -> None:
        if not settings.NOTIFY_ON_APPROVAL_NEEDED:
            return
        msg = f"需要审批 | task_id={task_id} | step={step_name}"
        await self.notify(msg, "warning")


def build_notification_manager() -> NotificationManager:
    """根据配置构建 NotificationManager 实例。"""
    manager = NotificationManager()

    # 始终添加控制台通知
    manager.add_notifier(ConsoleNotifier())

    if settings.SLACK_WEBHOOK_URL:
        manager.add_notifier(SlackNotifier(settings.SLACK_WEBHOOK_URL))

    if settings.DINGTALK_WEBHOOK_URL:
        manager.add_notifier(DingTalkNotifier(settings.DINGTALK_WEBHOOK_URL))

    if settings.WECHAT_WORK_WEBHOOK_URL:
        manager.add_notifier(WeChatWorkNotifier(settings.WECHAT_WORK_WEBHOOK_URL))

    if settings.FEISHU_WEBHOOK_URL:
        manager.add_notifier(FeishuNotifier(settings.FEISHU_WEBHOOK_URL))

    return manager


# 全局单例
notifier = build_notification_manager()
