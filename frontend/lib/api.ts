const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:18000";

const REQUEST_TIMEOUT = 30000; // 30 秒

/** 友好的错误提示 */
function getFriendlyError(status: number, detail: string): string {
  if (status === 401) return "认证失败，请重新登录";
  if (status === 403) return "权限不足，请联系管理员";
  if (status === 404) return "请求的资源不存在";
  if (status === 422) return "请求参数错误，请检查输入";
  if (status === 429) return "请求过于频繁，请稍后再试";
  if (status >= 500) return "服务器错误，请稍后再试";
  return detail || `请求失败: ${status}`;
}

async function request<T>(
  path: string,
  options?: RequestInit & { signal?: AbortSignal }
): Promise<T> {
  const externalSignal = options?.signal;
  const controller = new AbortController();

  // 外部 signal abort 时联动取消
  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort(externalSignal.reason);
    } else {
      externalSignal.addEventListener("abort", () => controller.abort(externalSignal.reason), {
        once: true,
      });
    }
  }

  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...options?.headers },
      signal: controller.signal,
      ...options,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(getFriendlyError(res.status, err.detail));
    }
    if (res.status === 204) return undefined as T;
    return res.json();
  } finally {
    clearTimeout(timeoutId);
  }
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
  list: (skip = 0, limit = 20, signal?: AbortSignal) =>
    request<WorkflowListResponse>(`/api/workflows?skip=${skip}&limit=${limit}`, { signal }),
  get: (id: string, signal?: AbortSignal) =>
    request<WorkflowItem>(`/api/workflows/${id}`, { signal }),
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
  templates: (signal?: AbortSignal) =>
    request<Array<{ name: string; description: string; yaml_definition: string }>>(
      "/api/workflows/templates", { signal }
    ),
  importTemplate: (index: number) =>
    request<WorkflowItem>(`/api/workflows/templates/${index}`, { method: "POST" }),
  share: (id: string) =>
    request<{ workflow_id: string; name: string; share_code: string; share_url: string }>(
      `/api/workflows/${id}/share`
    ),
  importShare: (share_code: string) =>
    request<WorkflowItem>("/api/workflows/import-share", {
      method: "POST",
      body: JSON.stringify({ share_code }),
    }),
  export: (id: string) =>
    request<{ name: string; yaml: string; filename: string }>(
      `/api/workflows/export/${id}`
    ),
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
  list: (params?: {
    workflow_id?: string;
    status?: string;
    q?: string;
    date_from?: string;
    date_to?: string;
    sort_by?: string;
    sort_order?: string;
    page?: number;
    page_size?: number;
    signal?: AbortSignal;
  }) => {
    const { signal } = params || {};
    const sp = new URLSearchParams();
    if (params?.workflow_id) sp.set("workflow_id", params.workflow_id);
    if (params?.status) sp.set("status", params.status);
    if (params?.q) sp.set("q", params.q);
    if (params?.date_from) sp.set("date_from", params.date_from);
    if (params?.date_to) sp.set("date_to", params.date_to);
    if (params?.sort_by) sp.set("sort_by", params.sort_by);
    if (params?.sort_order) sp.set("sort_order", params.sort_order);
    if (params?.page) sp.set("page", String(params.page));
    if (params?.page_size) sp.set("page_size", String(params.page_size));
    return request<TaskListResponse>(`/api/tasks?${sp}`, { signal });
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
  list: (status = "pending", skip = 0, limit = 20, signal?: AbortSignal) =>
    request<ApprovalListResponse>(
      `/api/approvals?status=${status}&skip=${skip}&limit=${limit}`, { signal }
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
  stats: (signal?: AbortSignal) => request<DashboardStatsData>("/api/dashboard/stats", { signal }),
};

// === Notification ===
export interface NotificationConfig {
  slack_webhook_url: string;
  dingtalk_webhook_url: string;
  notify_on_task_complete: boolean;
  notify_on_task_fail: boolean;
  notify_on_approval_needed: boolean;
}

export interface NotificationHistoryItem {
  id: string;
  channel: string;
  event_type: string;
  title: string;
  status: string;
  error_message: string | null;
  created_at: string;
}

export interface NotificationHistoryResponse {
  items: NotificationHistoryItem[];
  total: number;
}

export const notificationApi = {
  getConfig: () => request<NotificationConfig>("/api/notifications/config"),
  updateConfig: (data: NotificationConfig) =>
    request<NotificationConfig>("/api/notifications/config", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  testSlack: () =>
    request<{ success: boolean; message: string }>("/api/notifications/test/slack", {
      method: "POST",
    }),
  testDingtalk: () =>
    request<{ success: boolean; message: string }>("/api/notifications/test/dingtalk", {
      method: "POST",
    }),
  history: (limit = 50) =>
    request<NotificationHistoryResponse>(`/api/notifications/history?limit=${limit}`),
};
