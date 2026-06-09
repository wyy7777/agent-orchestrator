from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    running_tasks: int = 0
    pending_approvals: int = 0
    success_rate: float = 0.0
    total_tokens_used: int = 0
    avg_approval_pass_rate: float = 0.0


class DailyTrend(BaseModel):
    date: str
    task_count: int = 0
    success_rate: float = 0.0
    token_usage: int = 0
    avg_execution_time: float = 0.0


class TrendsResponse(BaseModel):
    days: int
    data: list[DailyTrend]


class TopWorkflow(BaseModel):
    workflow_id: str
    workflow_name: str
    execution_count: int
    success_count: int
    success_rate: float


class ErrorSummary(BaseModel):
    error_type: str
    count: int
    latest_message: str | None = None


class ExportItem(BaseModel):
    id: str
    workflow_id: str | None = None
    workflow_name: str | None = None
    status: str
    trigger_type: str | None = None
    total_tokens_used: int = 0
    error_message: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
