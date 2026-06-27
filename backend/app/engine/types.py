"""引擎类型定义：枚举、基类、注册表。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.engine.yaml_parser import StepDefinition


@dataclass
class StepResult:
    """统一的步骤执行结果。"""
    status: str  # "completed" | "failed" | "skipped" | "fallback"
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    tokens_used: int = 0
    model: str = ""


@dataclass
class HandoffMessage:
    """Agent 间通信消息。"""
    from_step: str
    to_step: str
    type: str = "data"  # data | instruction | feedback
    payload: dict[str, Any] = field(default_factory=dict)
    mapping: dict[str, str] = field(default_factory=dict)  # 源字段 -> 目标字段映射


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# 步骤处理器注册表
_step_handlers: dict[str, type[StepHandler]] = {}


class StepHandler:
    """步骤处理器基类。"""

    async def execute(
        self, step: StepDefinition, context: dict[str, Any], db: AsyncSession
    ) -> StepResult:
        raise NotImplementedError


def register_handler(step_type: str):
    """装饰器：注册步骤处理器。"""
    def decorator(cls):
        _step_handlers[step_type] = cls
        return cls
    return decorator
