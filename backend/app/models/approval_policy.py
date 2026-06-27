"""审批策略模型：定义何时需要审批以及审批规则。"""
from __future__ import annotations

from datetime import datetime  # noqa: TC003 (SQLAlchemy resolves Mapped[datetime] at runtime)
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.engine.condition_eval import evaluate_condition
from app.models.base import gen_uuid, utcnow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ApprovalPolicy(Base):
    """审批策略：定义何时触发审批、由谁审批。"""

    __tablename__ = "approval_policies"
    __table_args__ = (
        Index("ix_approval_policies_workflow_id", "workflow_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("workflows.id"), nullable=True
    )
    # 条件表达式：step_type == "execute" and risk_level >= "high"
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 审批人列表（JSON 数组）
    approvers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 最少审批人数（会签）
    quorum: Mapped[int] = mapped_column(Integer, default=1)
    # 超时分钟数，0 表示不过期
    timeout_minutes: Mapped[int] = mapped_column(Integer, default=0)
    # 是否启用
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def matches(self, context: dict) -> bool:
        """检查策略是否匹配当前上下文。"""
        if not self.enabled:
            return False
        if not self.condition:
            return True
        return evaluate_condition(self.condition, context)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "workflow_id": self.workflow_id,
            "condition": self.condition,
            "approvers": self.approvers,
            "quorum": self.quorum,
            "timeout_minutes": self.timeout_minutes,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


async def get_matching_policies(
    db: AsyncSession, workflow_id: str, context: dict
) -> list[ApprovalPolicy]:
    """获取匹配当前上下文的所有审批策略。"""
    result = await db.execute(
        select(ApprovalPolicy).where(
            (ApprovalPolicy.workflow_id == workflow_id)
            | (ApprovalPolicy.workflow_id.is_(None))
        )
    )
    policies = result.scalars().all()
    return [p for p in policies if p.matches(context)]
