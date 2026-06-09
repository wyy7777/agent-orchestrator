from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import utcnow, gen_uuid


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    webhook_type: Mapped[str] = mapped_column(String(20), nullable=False)  # github / generic
    target_workflow_id: Mapped[str] = mapped_column(String(36), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(20), nullable=False, default="api_key")  # none / api_key / hmac
    auth_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
