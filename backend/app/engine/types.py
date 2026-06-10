"""引擎类型定义：枚举、基类、注册表。"""
from __future__ import annotations

from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.yaml_parser import StepDefinition


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# 步骤处理器注册表
_step_handlers: dict[str, type["StepHandler"]] = {}


class StepHandler:
    """步骤处理器基类。"""

    async def execute(
        self, step: StepDefinition, context: dict[str, Any], db: AsyncSession
    ) -> dict[str, Any]:
        raise NotImplementedError


def register_handler(step_type: str):
    """装饰器：注册步骤处理器。"""
    def decorator(cls):
        _step_handlers[step_type] = cls
        return cls
    return decorator
