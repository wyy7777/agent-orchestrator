from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器，用于实时推送任务状态更新。"""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._global_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket, task_id: str | None = None):
        await websocket.accept()
        if task_id:
            self._connections.setdefault(task_id, []).append(websocket)
        else:
            self._global_connections.append(websocket)

    def disconnect(self, websocket: WebSocket, task_id: str | None = None):
        if task_id and task_id in self._connections:
            self._connections[task_id] = [
                ws for ws in self._connections[task_id] if ws != websocket
            ]
        self._global_connections = [
            ws for ws in self._global_connections if ws != websocket
        ]

    async def broadcast_task_update(self, task_id: str, data: dict[str, Any]):
        message = json.dumps({"type": "task_update", "task_id": task_id, "data": data})
        targets = self._connections.get(task_id, []) + self._global_connections
        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                pass

    async def broadcast_approval_update(self, data: dict[str, Any]):
        message = json.dumps({"type": "approval_update", "data": data})
        for ws in self._global_connections:
            try:
                await ws.send_text(message)
            except Exception:
                pass


ws_manager = ConnectionManager()
