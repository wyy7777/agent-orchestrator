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
