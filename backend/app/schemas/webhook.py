from datetime import datetime

from pydantic import BaseModel


class WebhookCreate(BaseModel):
    name: str
    webhook_type: str  # github / generic
    target_workflow_id: str
    auth_type: str = "api_key"  # none / api_key / hmac
    auth_config: dict | None = None
    secret: str | None = None
    config: dict | None = None


class WebhookResponse(BaseModel):
    id: str
    name: str
    webhook_type: str
    target_workflow_id: str
    auth_type: str
    auth_config: dict | None = None
    config: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookListResponse(BaseModel):
    items: list[WebhookResponse]
    total: int
