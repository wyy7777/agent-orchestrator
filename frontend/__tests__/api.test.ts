/**
 * Tests for the API client module — token management, request helpers, and API functions.
 */
import {
  getToken,
  setToken,
  removeToken,
  isAuthenticated,
} from "@/lib/api";

// Save original fetch
const originalFetch = globalThis.fetch;

beforeEach(() => {
  localStorage.clear();
  jest.restoreAllMocks();
});

afterAll(() => {
  globalThis.fetch = originalFetch;
});

describe("Token management", () => {
  it("getToken returns null when no token is stored", () => {
    expect(getToken()).toBeNull();
  });

  it("setToken stores a token", () => {
    setToken("test-token-123");
    expect(getToken()).toBe("test-token-123");
  });

  it("removeToken clears token and refresh_token", () => {
    localStorage.setItem("token", "test-token");
    localStorage.setItem("refresh_token", "test-refresh");
    removeToken();
    expect(getToken()).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("isAuthenticated returns false when no token", () => {
    expect(isAuthenticated()).toBe(false);
  });

  it("isAuthenticated returns true when token exists", () => {
    setToken("valid-token");
    expect(isAuthenticated()).toBe(true);
  });

  it("setToken and getToken are symmetic", () => {
    setToken("eyJhbGciOiJIUzI1NiJ9.token");
    expect(getToken()).toBe("eyJhbGciOiJIUzI1NiJ9.token");
  });
});

describe("authApi.login", () => {
  it("stores token on successful login", async () => {
    const mockResponse = {
      access_token: "mock-access-token",
      token_type: "bearer",
      refresh_token: "mock-refresh-token",
    };

    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockResponse),
    } as Response);

    // Dynamic import to avoid hoisting issues
    const { authApi } = await import("@/lib/api");
    const result = await authApi.login("admin", "password123");

    expect(result.access_token).toBe("mock-access-token");
    expect(getToken()).toBe("mock-access-token");
    expect(localStorage.getItem("refresh_token")).toBe("mock-refresh-token");
  });

  it("throws on failed login", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      json: () => Promise.resolve({ detail: "Invalid credentials" }),
    } as Response);

    const { authApi } = await import("@/lib/api");
    await expect(authApi.login("admin", "wrong")).rejects.toThrow("认证失败");
  });

  it("throws on network errors with friendly message", async () => {
    globalThis.fetch = jest.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    const { authApi } = await import("@/lib/api");
    await expect(authApi.login("admin", "password")).rejects.toThrow(
      "无法连接到后端服务"
    );
  });
});

describe("authApi.logout", () => {
  it("clears all tokens", () => {
    localStorage.setItem("token", "test-token");
    localStorage.setItem("refresh_token", "test-refresh");

    const { authApi } = require("@/lib/api");
    authApi.logout();

    expect(getToken()).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });
});

describe("authApi.me", () => {
  it("fetches current user info", async () => {
    const mockUser = {
      id: "user-1",
      username: "admin",
      email: "admin@example.com",
      role: "admin",
    };

    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockUser),
    } as Response);

    const { authApi } = await import("@/lib/api");
    const result = await authApi.me();

    expect(result.id).toBe("user-1");
    expect(result.username).toBe("admin");
    expect(result.role).toBe("admin");
  });
});

describe("workflowApi", () => {
  it("workflowApi.list fetches paginated workflows", async () => {
    const mockResponse = {
      items: [
        { id: "wf-1", name: "Test WF", description: null, yaml_definition: "steps: []", version: 1, created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z" },
      ],
      total: 1,
    };

    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockResponse),
    } as Response);

    const { workflowApi } = await import("@/lib/api");
    const result = await workflowApi.list(0, 10);

    expect(result.items).toHaveLength(1);
    expect(result.total).toBe(1);
    expect(result.items[0].name).toBe("Test WF");
  });

  it("workflowApi.list passes query parameters", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [], total: 0 }),
    } as Response);

    const { workflowApi } = await import("@/lib/api");
    await workflowApi.list(5, 10);

    // Check that the correct URL was called
    const calledUrl = (globalThis.fetch as jest.Mock).mock.calls[0][0];
    expect(calledUrl).toContain("skip=5");
    expect(calledUrl).toContain("limit=10");
  });
});

describe("taskApi", () => {
  it("taskApi.list builds query string from params", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [], total: 0 }),
    } as Response);

    const { taskApi } = await import("@/lib/api");
    await taskApi.list({
      status: "running",
      workflow_id: "wf-1",
      sort_by: "created_at",
      sort_order: "desc",
    });

    const calledUrl = (globalThis.fetch as jest.Mock).mock.calls[0][0];
    expect(calledUrl).toContain("status=running");
    expect(calledUrl).toContain("workflow_id=wf-1");
    expect(calledUrl).toContain("sort_by=created_at");
    expect(calledUrl).toContain("sort_order=desc");
  });

  it("taskApi.get fetches a single task", async () => {
    const mockTask = {
      id: "task-1",
      workflow_id: "wf-1",
      status: "running",
      trigger_type: "manual",
      trigger_payload: null,
      git_repo: null,
      git_branch: null,
      sandbox_branch: null,
      current_step_index: 0,
      total_tokens_used: 100,
      error_message: null,
      pr_url: null,
      created_at: "2025-01-01T00:00:00Z",
      started_at: null,
      completed_at: null,
      step_executions: [],
    };

    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockTask),
    } as Response);

    const { taskApi } = await import("@/lib/api");
    const result = await taskApi.get("task-1");
    expect(result.id).toBe("task-1");
    expect(result.status).toBe("running");
  });
});

describe("approvalApi", () => {
  it("approvalApi.list fetches pending approvals", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({
        items: [
          { id: "app-1", step_execution_id: "se-1", status: "pending", approver: null, comment: null, decided_at: null, revoked_at: null, revoke_reason: null, created_at: "2025-01-01T00:00:00Z" },
        ],
        total: 1,
      }),
    } as Response);

    const { approvalApi } = await import("@/lib/api");
    const result = await approvalApi.list("pending");
    expect(result.total).toBe(1);
    expect(result.items[0].status).toBe("pending");
  });

  it("approvalApi.revoke sends revoke request", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: "app-1", status: "revoked", revoked_at: "2025-01-01T00:00:00Z" }),
    } as Response);

    const { approvalApi } = await import("@/lib/api");
    await approvalApi.revoke("app-1", "Made a mistake");

    const callArgs = (globalThis.fetch as jest.Mock).mock.calls[0];
    expect(callArgs[0]).toContain("/api/approvals/app-1/revoke");
    expect(callArgs[1].body).toContain("Made a mistake");
  });
});

describe("auditApi", () => {
  it("auditApi.listReports fetches report list", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({
        items: [
          { id: "rpt-1", start_date: "2025-01-01", end_date: "2025-01-31", format: "csv", sha256: "abc123", size_bytes: 1024, created_at: "2025-02-01T00:00:00Z" },
        ],
      }),
    } as Response);

    const { auditApi } = await import("@/lib/api");
    const result = await auditApi.listReports();
    expect(result.items).toHaveLength(1);
    expect(result.items[0].sha256).toBe("abc123");
  });
});

describe("dashboardApi", () => {
  it("dashboardApi.stats fetches stats", async () => {
    const mockStats = {
      total_tasks: 100,
      completed_tasks: 80,
      failed_tasks: 10,
      running_tasks: 5,
      pending_approvals: 3,
      success_rate: 80,
      total_tokens_used: 50000,
      avg_approval_pass_rate: 90,
    };

    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockStats),
    } as Response);

    const { dashboardApi } = await import("@/lib/api");
    const result = await dashboardApi.stats();
    expect(result.total_tasks).toBe(100);
    expect(result.success_rate).toBe(80);
  });
});

describe("agentApi", () => {
  it("agentApi.list fetches agent list", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve([
        { id: "agent-1", name: "code-reviewer", display_name: "Code Reviewer", capabilities: ["review"], provider: "deepseek", model: "deepseek-chat", max_tokens: 4096, temperature: 0.3, timeout_seconds: 120, token_budget: 100000, enabled: true, created_at: null },
      ]),
    } as Response);

    const { agentApi } = await import("@/lib/api");
    const result = await agentApi.list();
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("code-reviewer");
  });

  it("agentApi.create sends correct payload", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: "agent-2", name: "tester", display_name: "Tester", capabilities: ["execute"], provider: "openai", model: "gpt-4", max_tokens: 4096, temperature: 0.7, timeout_seconds: 120, token_budget: 50000, enabled: true, created_at: null }),
    } as Response);

    const { agentApi } = await import("@/lib/api");
    const result = await agentApi.create({ name: "tester", display_name: "Tester" });

    const callBody = JSON.parse((globalThis.fetch as jest.Mock).mock.calls[0][1].body);
    expect(callBody.name).toBe("tester");
    expect(result.name).toBe("tester");
  });
});

describe("settingsApi", () => {
  it("settingsApi.getApiKeys fetches provider info", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({
        providers: [{ name: "deepseek", display_name: "DeepSeek", key_configured: true, key_preview: "sk-ds****", base_url: "https://api.deepseek.com", models: ["deepseek-chat"] }],
        default_provider: "deepseek",
        default_model: "deepseek-chat",
      }),
    } as Response);

    const { settingsApi } = await import("@/lib/api");
    const result = await settingsApi.getApiKeys();
    expect(result.default_provider).toBe("deepseek");
    expect(result.providers).toHaveLength(1);
  });
});

describe("notificationApi", () => {
  it("notificationApi.getConfig fetches config", async () => {
    const mockConfig = {
      slack_webhook_url: "",
      dingtalk_webhook_url: "",
      notify_on_task_complete: true,
      notify_on_task_fail: true,
      notify_on_approval_needed: true,
    };

    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockConfig),
    } as Response);

    const { notificationApi } = await import("@/lib/api");
    const result = await notificationApi.getConfig();
    expect(result.notify_on_task_complete).toBe(true);
  });

  it("notificationApi.history fetches history", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [], total: 0 }),
    } as Response);

    const { notificationApi } = await import("@/lib/api");
    const result = await notificationApi.history(50);
    expect(result.total).toBe(0);
  });

  it("notificationApi.testSlack sends POST /api/notifications/test with channel=slack", async () => {
    const mockResponse = { results: { SlackNotifier: true } };
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockResponse),
    } as Response);

    const { notificationApi } = await import("@/lib/api");
    const result = await notificationApi.testSlack();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/notifications/test"),
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining('"channel":"slack"'),
      })
    );
    expect(result.results).toEqual({ SlackNotifier: true });
  });

  it("notificationApi.testDingtalk sends POST /api/notifications/test with channel=dingtalk", async () => {
    const mockResponse = { results: { DingTalkNotifier: true } };
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockResponse),
    } as Response);

    const { notificationApi } = await import("@/lib/api");
    const result = await notificationApi.testDingtalk();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/notifications/test"),
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining('"channel":"dingtalk"'),
      })
    );
    expect(result.results).toEqual({ DingTalkNotifier: true });
  });
});
