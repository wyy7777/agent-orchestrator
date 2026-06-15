# Agent Orchestrator 全代码全功能自检报告

> 检查时间: 2026-06-14
> 覆盖范围: 后端全模块 (engine/api/models/services/auth)、前端全页面、测试套件
> 测试结果: **184 passed, 0 failed** (74.66s) — 修复前 3 failed

---

## 一、已确认的 Bug（必须修复）

### BUG-1: `create_task` API 使用已消费的 Result 对象（导致 3 个测试失败）

**文件**: `backend/app/api/tasks.py:113-124`

```python
wf_result = await db.execute(select(Workflow).where(Workflow.id == body.workflow_id))
if not wf_result.scalar_one_or_none():          # ← 第一次调用，消耗了 result
    raise HTTPException(status_code=404, detail="工作流不存在")

task = Task(
    ...
    workflow_snapshot=wf_result.scalar_one_or_none().yaml_definition,  # ← 第二次调用 → ResourceClosedError!
)
```

**问题**: `scalar_one_or_none()` 在第一次调用后 Result 对象已关闭，第二次调用抛 `sqlalchemy.exc.ResourceClosedError`。

**修复**: 将查询结果存到变量中复用。

---

### BUG-2: `_execute_else_steps` 从未真正执行（条件分支 else 分支失效）

**文件**: `backend/app/engine/state_machine.py:281-303`

```python
def _handle_condition(self, ...) -> bool:
    ...
    if step_def.else_steps:
        self._execute_else_steps(...)   # ← 同步方法调用异步方法，协程被创建但从未 await！
    return True
```

**问题**: `_handle_condition` 是同步方法，`_execute_else_steps` 是 `async` 方法。直接调用 `self._execute_else_steps(...)` 只创建了一个协程对象，没有 `await`，所以 **else 分支永远不会执行**。

**修复**: 将 `_handle_condition` 改为 `async`，用 `await` 调用 `_execute_else_steps`。

---

### BUG-3: `set_admin` 端点重复检查

**文件**: `backend/app/api/auth.py:175-179`

```python
user = result.scalar_one_or_none()
if not user:
    raise HTTPException(status_code=404, detail="用户不存在")
if not user:                              # ← 重复的检查，死代码
    raise HTTPException(status_code=404, detail="用户不存在")
```

---

### BUG-4: WebSocket 端口硬编码错误

**文件**: `frontend/lib/ws.ts:5`

```typescript
return "ws://127.0.0.1:18000/ws";  // ← 后端默认端口是 8000，不是 18000
```

**影响**: 前端 WebSocket 实时推送在默认配置下无法连接。

---

### BUG-5: `ExecuteHandler` 从错误的 context key 读取分析结果

**文件**: `backend/app/agents/executor.py:202`

```python
analysis = context.get("results", {}).get("analyze", {}).get("analysis", {})
```

**问题**: context 中的 key 是 **步骤名称**（如 `"代码分析"`），不是步骤类型 `"analyze"`。除非用户恰好将步骤命名为 `"analyze"`，否则分析结果读取为空。

---

### BUG-6: `loop` 步骤未将 items 传递给子步骤

**文件**: `backend/app/engine/step_executor.py:268-283`

```python
items = context
for key in items_key.split("."):
    if isinstance(items, dict):
        items = items.get(key)
```

**问题**: 默认 `items_key="items"`，但 context 中不存在 `"items"` 键。循环步骤的 `loop_item` 虽然被注入到 `iteration_context`，但子步骤的执行结果在 `loop_results` 中收集的 key 不匹配（实际存储在 `f"{step_def.name}[{idx}].{sub_def.name}"` 而非 `f"{step_def.name}[{idx}]"`）。

---

### BUG-7: `condition_eval` 的 and/or 分割对含运算符的值不安全

**文件**: `backend/app/engine/condition_eval.py:55-60`

```python
if " and " in expr:
    parts = expr.split(" and ")
```

**问题**: 如果变量值本身包含 `" and "` 或 `" or "`（如字符串值 `"Tom and Jerry"`），会被错误拆分。

---

## 二、安全隐患

### SEC-1: 默认 SECRET_KEY 硬编码

**文件**: `backend/app/config.py:64`

```python
SECRET_KEY: str = "your-secret-key-change-in-production"
```

**风险**: 如果用户未配置 `.env`，所有 JWT token 使用已知密钥签名，攻击者可伪造任意用户 token。虽然有 `ensure_secret_key()` 逻辑，但仅在空值时触发，不会替换默认值。

**修复**: 将默认值改为空字符串，启动时强制生成。

---

### SEC-2: ScriptHandler 缺少注入防护

**文件**: `backend/app/agents/executor.py:460-510`

`ScriptHandler` 直接执行 shell 命令，虽然有超时保护，但：
- 没有命令白名单/黑名单
- 模板变量替换只处理顶层字符串，嵌套值不替换（可能留原样执行 `{key}` 字面量）
- 无沙箱隔离（对比 `ShellCommandPlugin` 有黑名单保护）

---

### SEC-3: 审计报告 API 缺少认证

**文件**: `backend/app/api/audit.py:79`

```python
@router.post("/report")
async def generate_audit_report(...):
```

审计报告生成使用 `require_role("admin", "manager")`，但前端 `auditApi.generateReport()` 使用原生 `fetch()`，**未携带 Authorization header**。

---

### SEC-4: OAuth2 回调未做 state 验证

**文件**: `backend/app/auth.py:261-298`

`handle_oauth2_callback` 接受 code 参数但未验证 `state` 参数，存在 CSRF 风险。

---

## 三、架构问题

### ARCH-1: 内存状态丢失（影响生产可用性）

以下组件的状态全部存储在内存中，进程重启后丢失：

| 组件 | 影响 |
|------|------|
| `CircuitBreaker` | 断路器状态重置，可能在连续失败时继续提交任务 |
| `WorkflowScheduler` | 所有定时调度配置丢失 |
| `_rate_store` (速率限制) | 限流计数器重置 |
| `_login_failures` (登录限制) | 暴力破解计数器重置 |
| `_running_tasks` | 正在执行的任务引用丢失 |

---

### ARCH-2: Session 生命周期竞争

`_evaluate_quality` (fire-and-forget) 使用 `async_session()` 独立 session 写回质量评分，但可能与主流程的 session commit 竞争，导致写入到过时的 StepExecution 行。

---

### ARCH-3: 前后端认证模型不一致

后端支持两种认证模式：
1. JWT Bearer Token
2. API Key (`X-API-Key` header)

但前端 `lib/api.ts` 的 `request()` 函数 **未携带任何认证 header**。单用户模式下靠 `get_current_user` 自动回退到默认用户，但多用户场景完全失效。

---

### ARCH-4: `StepHandler.execute` 签名不一致

`StepHandler` 基类定义为：
```python
async def execute(self, step, context, db) -> StepResult
```

但 `step_executor.py:391` 调用时传入了额外的 `task` 和 `on_step_complete` 参数：
```python
await execute_single_step(step_exec, step_def, task, context, db, self._emit_step_completed)
```

而 `execute_single_step` 内部调用 handler 时只传 3 个参数 `(step_def, context, db)`，这意味着 handler 无法访问 `task` 对象（如更新 `total_tokens_used`）。当前 `total_tokens_used` 由 `execute_single_step` 外层更新，但这导致 handler 无法做 token 预算检查。

---

## 四、代码质量问题

### CODE-1: 测试失败未修复

3 个测试失败都指向同一个 Bug (BUG-1)，说明核心创建任务流程在测试环境中不可用。

### CODE-2: 重复代码

- `GitHubClient` 类 (github.py:190-225) 与模块级函数功能完全重复
- `_get_engine()` 在 `tasks.py` 和 `approvals.py` 中重复定义
- `auth.py:178-179` 重复检查

### CODE-3: `step_executions` 关系缺少级联删除保护

`Task` 模型定义 `cascade="all, delete-orphan"`，但 `StepExecution` 反向关系 `task` 没有设置 `passive_deletes=True`，可能在 PostgreSQL 上触发额外的 SELECT 查询。

### CODE-4: YAML 解析缓存使用 MD5

**文件**: `backend/app/engine/yaml_parser.py:57`

```python
return hashlib.md5(yaml_str.encode("utf-8")).hexdigest()
```

MD5 有碰撞风险（虽然对缓存键影响不大），且 `yaml_str` 可能很长，每次调用都重新 hash。

### CODE-5: 日志文件膨胀

`logs/app.log` 已达 **~400MB**，日志旋转配置可能未生效。`logs/app.log.2026-06-10` 达 112MB。

---

## 五、用户体验问题

### UX-1: 重放功能是空壳

`POST /api/tasks/{id}/steps/{step_index}/replay` 端点只返回原始输出 + 上下文快照，并未实际重新执行步骤。

### UX-2: 前端缺少加载状态和错误恢复

- Dashboard 页面加载 4 个并发 API，任一失败则整体失败
- 工作流编辑器（React Flow）不支持 undo/redo
- 任务详情页的 WebSocket 断连后只有自动重连，无 UI 提示

### UX-3: 国际化不完整

`lib/i18n.ts` 存在但大量中文硬编码在组件中，英文覆盖不完整。

### UX-4: 审批页面无撤销功能

审批一旦 decided (approved/rejected) 不可撤销，在关键工作流中风险较高。

---

## 六、测试覆盖分析

| 模块 | 测试文件 | 覆盖情况 |
|------|---------|---------|
| Agent 基础 | test_agents.py | ✅ 完整 |
| API 路由 | test_api.py | ⚠️ 1/8 失败 |
| 认证 | test_auth.py | ✅ 完整 |
| 断路器 | test_circuit_breaker.py | ✅ 完整 |
| 条件评估 | test_condition_eval.py | ✅ 完整 |
| E2E | test_e2e.py | ❌ 2/5 失败 |
| GitLab | test_gitlab.py | ✅ 完整 |
| Handlers | test_handlers.py | ✅ 完整 |
| 状态机 | test_state_machine.py | ✅ 基本覆盖 |
| 步骤执行器 | test_step_executor.py | ✅ 基本覆盖 |
| YAML 解析 | test_yaml_parser.py | ✅ 完整 |

**缺失测试**: 通知系统、调度器、沙箱、插件系统、前端组件、集成 API (Jira/Linear/Confluence)、WebSocket。

---

## 七、优化方案（按优先级）

### P0 — 立即修复

1. **修复 BUG-1** (create_task): 将 workflow 查询结果存变量
2. **修复 BUG-2** (_execute_else_steps): `_handle_condition` 改为 async
3. **修复 BUG-4** (WS 端口): `ws.ts` 默认端口改为 8000
4. **修复 BUG-5** (ExecuteHandler): 按 step name 而非 type 读取 context

### P1 — 短期优化（1-2 周）

5. **前端认证集成**: `request()` 函数自动附加 JWT token
6. **重放功能实现**: 真正重新执行步骤（使用 context_snapshot）
7. **日志旋转修复**: 确认 `RotatingFileHandler` 配置正确
8. **SECRET_KEY 强化**: 默认值改空，启动时强制生成
9. **补全缺失测试**: 通知、调度器、沙箱、插件

### P2 — 中期改进（1-2 月）

10. **持久化调度配置**: 将 Schedule 存入数据库
11. **断路器持久化**: 失败计数存入数据库
12. **前端国际化完善**: 提取所有硬编码中文
13. **GraphQL API (可选)**: 替代大量 REST 端点的过度获取
14. **工作流版本对比**: diff 两个版本的 YAML
15. **步骤级日志查看**: 在任务详情页展示每步的 AI 输入/输出

### P3 — 长期发展方向

16. **分布式执行**: 当前单进程 asyncio 不适合 CPU 密集型步骤，考虑 Celery/RQ
17. **多租户支持**: User-Workflow 隔离
18. **工作流市场**: 社区共享模板
19. **AI 模型路由**: 根据步骤复杂度自动选择模型
20. **可观测性**: OpenTelemetry 集成，Trace 全链路

---

## 八、发展方向建议

### 短期（MVP 完善）
- 修复所有 P0 Bug，确保测试全部通过
- 实现前端认证流程，支持多用户
- 补全重放功能，让用户可以调试失败步骤

### 中期（产品化）
- 持久化调度和断路器状态，支持生产部署
- 完善可观测性（步骤级日志、Token 消耗分析）
- 构建 CI/CD 流水线（GitHub Actions）

### 长期（商业化）
- 多租户 + RBAC 完善
- 分布式执行引擎
- AI 模型智能路由
- 企业级 SSO 完善（SAML/OIDC）
- 工作流模板市场
