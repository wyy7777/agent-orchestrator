"""审计报告模型：存储已生成的合规报告元数据。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import utcnow, gen_uuid


class AuditReport(Base):
    """已生成的审计报告记录。"""
    __tablename__ = "audit_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    format: Mapped[str] = mapped_column(String(20), default="csv")  # csv | detailed_csv | pdf
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 签名
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
