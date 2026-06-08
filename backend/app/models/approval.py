from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import utcnow, gen_uuid


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (
        Index("ix_approvals_step_execution_id", "step_execution_id"),
        Index("ix_approvals_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    step_execution_id: Mapped[str] = mapped_column(String(36), ForeignKey("step_executions.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    approver: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
