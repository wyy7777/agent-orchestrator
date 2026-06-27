from datetime import datetime

from pydantic import BaseModel


class ScheduleCreate(BaseModel):
    workflow_id: str
    cron_expr: str
    payload: dict | None = None


class ScheduleResponse(BaseModel):
    id: str
    workflow_id: str
    cron_expr: str
    payload: dict
    enabled: bool
    created_at: datetime
    last_triggered_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScheduleListResponse(BaseModel):
    items: list[ScheduleResponse]
    total: int
