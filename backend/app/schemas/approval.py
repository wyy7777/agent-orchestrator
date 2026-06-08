from datetime import datetime
from pydantic import BaseModel


class ApprovalCreate(BaseModel):
    status: str  # approved / rejected
    approver: str | None = None
    comment: str | None = None


class ApprovalResponse(BaseModel):
    id: str
    step_execution_id: str
    status: str
    approver: str | None = None
    comment: str | None = None
    decided_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalListResponse(BaseModel):
    items: list[ApprovalResponse]
    total: int
