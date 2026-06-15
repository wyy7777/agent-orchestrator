"""Agent 注册中心：管理不同能力的 Agent 配置。"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import utcnow, gen_uuid

logger = logging.getLogger(__name__)


class AgentConfig(Base):
    """已注册的 Agent 配置。"""
    __tablename__ = "agent_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 能力标签：["analyze", "execute", "review", "security", "docs"]
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # AI 配置
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="deepseek")
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="deepseek-chat")
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    temperature: Mapped[float] = mapped_column(default=0.7)

    # 限制
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)
    token_budget: Mapped[int] = mapped_column(Integer, default=0)  # 0=无限制

    # 状态
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "capabilities": self.capabilities or [],
            "provider": self.provider,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout_seconds": self.timeout_seconds,
            "token_budget": self.token_budget,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def matches_step_type(self, step_type: str) -> bool:
        """检查此 Agent 是否能处理指定步骤类型。"""
        caps = self.capabilities or []
        return step_type in caps or len(caps) == 0
