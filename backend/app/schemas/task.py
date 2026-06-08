from datetime import datetime
from pydantic import BaseModel


class StepExecutionResponse(BaseModel):
    id: str
    step_index: int
    step_name: str
    step_type: str
    status: str
    input_data: dict | None = None
    output_data: dict | None = None
    ai_model: str | None = None
    token_usage: dict | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    workflow_id: str
    trigger_type: str = "manual"
    trigger_payload: dict | None = None
    git_repo: str | None = None
    git_branch: str | None = None


class TaskResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    trigger_type: str | None = None
    trigger_payload: dict | None = None
    git_repo: str | None = None
    git_branch: str | None = None
    sandbox_branch: str | None = None
    current_step_index: int = 0
    total_tokens_used: int = 0
    error_message: str | None = None
    pr_url: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    step_executions: list[StepExecutionResponse] = []

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
