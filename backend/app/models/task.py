import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.step_execution import StepExecution
    from app.models.workflow import Workflow


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflows.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending/running/paused/completed/failed/rolled_back
    trigger_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # manual/github_issue/github_webhook
    trigger_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    git_repo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    git_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sandbox_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_step_index: Mapped[int] = mapped_column(default=0)
    total_tokens_used: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="tasks")
    step_executions: Mapped[list["StepExecution"]] = relationship(
        "StepExecution", back_populates="task", cascade="all, delete-orphan",
        order_by="StepExecution.step_index"
    )
