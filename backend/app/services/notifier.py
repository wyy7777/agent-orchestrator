from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class Notifier(ABC):
    """通知接口抽象基类。"""

    # 共享 HTTP 客户端（由 NotificationManager 统一管理）
    _shared_client: httpx.AsyncClient | None = None

    @abstractmethod
    async def send(self, message: str, level: str = "info") -> bool:
        """发送通知。level: info / warning / error / success"""
        ...

    async def _get_client(self) -> httpx.AsyncClient:
        """获取共享 HTTP 客户端。"""
        if Notifier._shared_client is None or Notifier._shared_client.is_closed:
            Notifier._shared_client = httpx.AsyncClient(
                timeout=10,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return Notifier._shared_client


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
            client = await self._get_client()
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
            client = await self._get_client()
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
            client = await self._get_client()
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
            client = await self._get_client()
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
    """通知管理器，聚合多个 Notifier 实例统一发送。
    使用 asyncio.Queue + worker 实现背压，防止大量通知同时发出。
    """

    def __init__(self, max_workers: int = 2, queue_size: int = 100):
        self.notifiers: list[Notifier] = []
        self._queue: asyncio.Queue[tuple[str, str] | None] = asyncio.Queue(maxsize=queue_size)
        self._workers: list[asyncio.Task] = []
        self._max_workers = max_workers
        self._started = False

    def add_notifier(self, notifier: Notifier) -> None:
        self.notifiers.append(notifier)

    async def start(self):
        """启动 worker 协程（在 lifespan 中调用）。"""
        if self._started:
            return
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker(f"notif-worker-{i}"))
            self._workers.append(task)
        self._started = True

    async def stop(self):
        """停止所有 worker（在 lifespan 中调用）。"""
        for _ in self._workers:
            await self._queue.put(None)  # 发送哨兵值
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._started = False

    async def _worker(self, name: str):
        """后台 worker：从队列取通知并发送。"""
        while True:
            item = await self._queue.get()
            if item is None:  # 哨兵值，退出
                break
            message, level = item
            for n in self.notifiers:
                try:
                    await n.send(message, level)
                except Exception as e:
                    logger.error(f"通知发送异常 ({n.__class__.__name__}): {e}")

    async def close(self):
        """关闭共享 HTTP 客户端和 worker。"""
        await self.stop()
        if Notifier._shared_client and not Notifier._shared_client.is_closed:
            await Notifier._shared_client.aclose()
            Notifier._shared_client = None

    async def notify(self, message: str, level: str = "info") -> None:
        if not self.notifiers:
            return
        try:
            self._queue.put_nowait((message, level))
        except asyncio.QueueFull:
            logger.warning("通知队列已满，丢弃通知")

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
