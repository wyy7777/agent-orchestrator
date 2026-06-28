"""Shared API dependencies and utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.state_machine import ExecutionEngine


def get_engine(db: AsyncSession) -> ExecutionEngine:
    """Create an engine instance with event callbacks."""
    from app.main import _engine_event_handler

    return ExecutionEngine(db, on_event=_engine_event_handler)
