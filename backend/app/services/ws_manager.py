from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器，支持心跳检测和死连接清理。"""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._global_connections: list[WebSocket] = []
        # 反向索引：WebSocket -> set of task_ids（用于 O(1) 清理）
        self._ws_to_tasks: dict[WebSocket, set[str]] = {}

    async def connect(self, websocket: WebSocket, task_id: str | None = None):
        await websocket.accept()
        if task_id:
            self._connections.setdefault(task_id, []).append(websocket)
            self._ws_to_tasks.setdefault(websocket, set()).add(task_id)
        else:
            self._global_connections.append(websocket)

    def disconnect(self, websocket: WebSocket, task_id: str | None = None):
        if task_id and task_id in self._connections:
            self._connections[task_id] = [
                ws for ws in self._connections[task_id] if ws != websocket
            ]
            if websocket in self._ws_to_tasks:
                self._ws_to_tasks[websocket].discard(task_id)
                if not self._ws_to_tasks[websocket]:
                    del self._ws_to_tasks[websocket]
        self._global_connections = [
            ws for ws in self._global_connections if ws != websocket
        ]

    def _remove_ws_from_all(self, ws: WebSocket):
        """使用反向索引 O(1) 清理死连接。"""
        self._global_connections = [w for w in self._global_connections if w != ws]
        if ws in self._ws_to_tasks:
            for tid in self._ws_to_tasks[ws]:
                if tid in self._connections:
                    self._connections[tid] = [w for w in self._connections[tid] if w != ws]
                    if not self._connections[tid]:
                        del self._connections[tid]
            del self._ws_to_tasks[ws]

    async def _safe_send(self, ws: WebSocket, message: str) -> bool:
        """安全发送，失败时返回 False。"""
        try:
            await ws.send_text(message)
            return True
        except Exception:
            return False

    async def broadcast_task_update(self, task_id: str, data: dict[str, Any]):
        message = json.dumps({"type": "task_update", "task_id": task_id, "data": data}, ensure_ascii=False)
        targets = self._connections.get(task_id, []) + self._global_connections
        dead = []
        for ws in targets:
            if not await self._safe_send(ws, message):
                dead.append(ws)
        # 批量清理死连接
        for ws in dead:
            self._remove_ws_from_all(ws)

    async def broadcast_approval_update(self, data: dict[str, Any]):
        message = json.dumps({"type": "approval_update", "data": data}, ensure_ascii=False)
        dead = []
        for ws in self._global_connections:
            if not await self._safe_send(ws, message):
                dead.append(ws)
        for ws in dead:
            self._remove_ws_from_all(ws)

    @property
    def connection_count(self) -> int:
        return len(self._global_connections) + sum(len(v) for v in self._connections.values())


ws_manager = ConnectionManager()
