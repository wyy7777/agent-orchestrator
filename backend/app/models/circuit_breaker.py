from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CircuitBreakerState(Base):
    """断路器持久化状态。"""
    __tablename__ = "circuit_breaker_state"

    workflow_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    open_until: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
