"""审计日志模型。"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import utcnow, gen_uuid


class AuditLog(Base):
    """审计日志：记录所有关键操作。"""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    username: Mapped[str | None] = mapped_column(String(50))

    # 操作信息
    action: Mapped[str] = mapped_column(String(50), index=True)  # create/start/approve/reject/rollback/delete/update
    resource_type: Mapped[str] = mapped_column(String(50), index=True)  # workflow/task/approval/user/settings
    resource_id: Mapped[str | None] = mapped_column(String(36), index=True)
    resource_name: Mapped[str | None] = mapped_column(String(200))

    # 详情
    details: Mapped[str | None] = mapped_column(Text)  # JSON 格式的额外信息
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_audit_logs_timestamp_action", "timestamp", "action"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )
