const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `请求失败: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// === Workflow ===
export interface WorkflowItem {
  id: string;
  name: string;
  description: string | null;
  yaml_definition: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface WorkflowListResponse {
  items: WorkflowItem[];
  total: number;
}

export const workflowApi = {
  list: (skip = 0, limit = 20) =>
    request<WorkflowListResponse>(`/api/workflows?skip=${skip}&limit=${limit}`),
  get: (id: string) => request<WorkflowItem>(`/api/workflows/${id}`),
  create: (data: { name: string; description?: string; yaml_definition: string }) =>
    request<WorkflowItem>("/api/workflows", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (id: string, data: Partial<WorkflowItem>) =>
    request<WorkflowItem>(`/api/workflows/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/api/workflows/${id}`, { method: "DELETE" }),
  validate: (yaml_content: string) =>
    request<{ valid: boolean; error: string | null }>("/api/workflows/validate", {
      method: "POST",
      body: JSON.stringify({ yaml_content }),
    }),
};

// === Task ===
export interface StepExecution {
  id: string;
  step_index: number;
  step_name: string;
  step_type: string;
  status: string;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  ai_model: string | null;
  token_usage: Record<string, number> | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface TaskItem {
  id: string;
  workflow_id: string;
  status: string;
  trigger_type: string | null;
  trigger_payload: Record<string, unknown> | null;
  git_repo: string | null;
  git_branch: string | null;
  sandbox_branch: string | null;
  current_step_index: number;
  total_tokens_used: number;
  error_message: string | null;
  pr_url: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  step_executions: StepExecution[];
}

export interface TaskListResponse {
  items: TaskItem[];
  total: number;
}

export const taskApi = {
  list: (params?: { workflow_id?: string; status?: string; skip?: number; limit?: number }) => {
    const sp = new URLSearchParams();
    if (params?.workflow_id) sp.set("workflow_id", params.workflow_id);
    if (params?.status) sp.set("status", params.status);
    if (params?.skip) sp.set("skip", String(params.skip));
    if (params?.limit) sp.set("limit", String(params.limit));
    return request<TaskListResponse>(`/api/tasks?${sp}`);
  },
  get: (id: string) => request<TaskItem>(`/api/tasks/${id}`),
  create: (data: {
    workflow_id: string;
    trigger_type?: string;
    trigger_payload?: Record<string, unknown>;
    git_repo?: string;
    git_branch?: string;
  }) =>
    request<TaskItem>("/api/tasks", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  start: (id: string) =>
    request<TaskItem>(`/api/tasks/${id}/start`, { method: "POST" }),
  rollback: (id: string, stepIndex: number) =>
    request<TaskItem>(`/api/tasks/${id}/rollback?target_step_index=${stepIndex}`, {
      method: "POST",
    }),
  resume: (id: string) =>
    request<TaskItem>(`/api/tasks/${id}/resume`, { method: "POST" }),
};

// === Approval ===
export interface ApprovalItem {
  id: string;
  step_execution_id: string;
  status: string;
  approver: string | null;
  comment: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface ApprovalListResponse {
  items: ApprovalItem[];
  total: number;
}

export const approvalApi = {
  list: (status = "pending", skip = 0, limit = 20) =>
    request<ApprovalListResponse>(
      `/api/approvals?status=${status}&skip=${skip}&limit=${limit}`
    ),
  decide: (id: string, data: { status: string; approver?: string; comment?: string }) =>
    request<ApprovalItem>(`/api/approvals/${id}/decide`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// === Dashboard ===
export interface DashboardStatsData {
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  running_tasks: number;
  pending_approvals: number;
  success_rate: number;
  total_tokens_used: number;
  avg_approval_pass_rate: number;
}

export const dashboardApi = {
  stats: () => request<DashboardStatsData>("/api/dashboard/stats"),
};
