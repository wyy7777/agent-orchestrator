# 任务规划 — Agent Orchestrator 全面升级

> **目标**：在 MVP 基础上，覆盖质量与可靠性、企业安全合规、产品体验、多 Agent 协作四个方向。
> **策略**：增量演进，每阶段可独立交付，不破坏现有功能；每项任务有可量化的验收标准。
> **创建时间**：2025-01-22

---

## 总体路线

```
Phase 2a ──── Phase 2b ──── Phase 2c ──── Phase 2d
质量可靠性     企业安全合规    产品体验       多Agent协作
(3-4周)        (3-4周)        (2-3周)        (4-5周)
```

---

## 验收总则

| 级别 | 含义 | 形式 |
|------|------|------|
| 🟢 **自动化** | 跑命令即验证 | `pytest` / `curl` / `lighthouse` |
| 🟡 **半自动** | 人工触发 + 工具检查 | 页面操作 + 浏览器 DevTools / DB 查询 |
| 🔴 **人工** | 需要人眼判断 | 代码审查 / 交互体验 / 设计评审 |

---

## Phase 2a: 质量与可靠性增强

> 目标：让 Agent 执行结果可量化、可复现、可信任。

### 2a.1 AI 质量自动评分

- [x] 新增 `QualityEvaluator` 服务，对 execute/review 步骤的输出做 AI 自评
  - 评分维度：正确性、完整性、安全性、代码风格（每个 1-10 分）
  - 集成到 `step_executor.py`，在步骤完成后异步触发
  - 评分结果写入 `step_execution.quality_score` JSON 字段
- [x] 新增 10 个单元测试，quality_evaluator.py 覆盖率达 100%
- [ ] 仪表盘新增"质量趋势"图表
- [ ] 任务详情页展示每步质量评分

**验收方式** 🟢

```bash
# 1. 数据库迁移已执行
sqlite3 agent_orchestrator.db ".schema step_executions" | grep quality_score

# 2. 执行一个含 execute 步骤的任务后，检查评分字段非空
curl -s http://localhost:8000/api/tasks/{task_id} | jq '.step_executions[].quality_score'

# 3. 仪表盘 API 返回质量趋势数据
curl -s http://localhost:8000/api/dashboard/quality-trends | jq '.trends[0]'

# 4. 评分值在 1-10 范围内
curl -s http://localhost:8000/api/tasks/{task_id} | jq '.step_executions[0].quality_score.correctness' # 应输出 1-10 的数字
```

---

### 2a.2 测试体系完善

- [ ] 核心引擎单元测试：补充并行步骤失败回滚、嵌套子任务、循环超限、条件分支全覆盖
- [ ] AI Agent Mock 测试：不依赖真实 API 的 handler 测试（mock `BaseAgent.run`）
- [ ] API 集成测试：补充审批通过→恢复、回滚→重新执行、WebSocket 推送等关键路径
- [ ] E2E 冒烟测试：全自动 `test_full.py` 级别流程，无需人工干预
- [ ] CI 配置（GitHub Actions）：lint(ruff) + test(pytest) + build

**验收方式** 🟢

```bash
# 1. 覆盖率 ≥ 80%（核心引擎模块）
cd backend
pytest --cov=app/engine --cov=app/agents --cov-report=term -v
# 期望: engine/ 覆盖率 ≥ 85%, agents/ 覆盖率 ≥ 80%

# 2. 所有测试通过（无需真实 AI API）
pytest -v --ignore=tests/test_api.py  # 单元测试不依赖网络
# 期望: 全部 passed

# 3. CI 配置可运行
# .github/workflows/ci.yml 存在，包含 lint + test + build 三步

# 4. Mock 测试验证 AI handler 逻辑
pytest tests/test_agents.py -v
# 期望: 每个 handler 至少 1 个 mock 测试
```

---

### 2a.3 执行结果可复现性

- [ ] 任务创建时，从 `workflow.yaml_definition` 复制到 `task.workflow_snapshot`
- [ ] 新增 `POST /api/tasks/{task_id}/steps/{step_index}/replay` 重放端点
- [ ] 上下文快照在每步完成后序列化存储到 `step_execution.context_snapshot`

**验收方式** 🟢

```bash
# 1. 修改工作流 YAML 后，已有任务不受影响
curl -X PUT http://localhost:8000/api/workflows/{wf_id} -d '{"yaml_definition":"..."}'
curl -s http://localhost:8000/api/tasks/{task_id} | jq '.workflow_snapshot'
# 期望: snapshot 仍是旧版本 YAML

# 2. 重放端点返回相同上下文
curl -X POST http://localhost:8000/api/tasks/{task_id}/steps/0/replay | jq '.output'
# 期望: 输出结构与原步骤一致

# 3. context_snapshot 不为空
curl -s http://localhost:8000/api/tasks/{task_id} | jq '.step_executions[0].context_snapshot'
# 期望: 包含 task_id, results, git_repo 等字段
```

---

### 2a.4 错误处理与韧性

- [ ] 定义 `StepResult` 数据类：`{status, output, error, tokens_used}`，所有 handler 统一返回
- [ ] 步骤超时验证：在 YAML 中设 `timeout: 5` 后超时会标记 failed
- [ ] AI 不可用时，`analyze` 步骤 fallback 到规则引擎（正则/静态分析）
- [ ] 断路器：同一工作流类型连续失败 5 次后，自动暂停新任务

**验收方式** 🟢🟡

```bash
# 1. StepResult 统一返回（代码审查）
grep -r "return {" backend/app/agents/executor.py | wc -l
# 期望: 0（全部改用 StepResult）

# 2. 超时触发（手动：设 timeout=1, 调用慢模型）
# 期望: 步骤状态变为 failed, error_message 包含 "超时"

# 3. Fallback 触发（设置无效 API Key 后创建 analyze 任务）
curl -s http://localhost:8000/api/tasks/{task_id} | jq '.step_executions[0].status'
# 期望: completed（而非 failed）, output 包含 fallback 标记

# 4. 断路器触发
for i in {1..5}; do
  curl -X POST http://localhost:8000/api/tasks -d '{"workflow_id":"broken_wf"}' && \
  curl -X POST http://localhost:8000/api/tasks/{id}/start
done
curl -X POST http://localhost:8000/api/tasks -d '{"workflow_id":"broken_wf"}'
# 期望: 第 6 次创建时返回 429 或 error "断路器已打开"
```

---

## Phase 2b: 企业级安全合规

> 目标：满足金融/医疗行业的合规要求。

### 2b.1 RBAC 权限控制

- [ ] 角色定义：admin / manager / operator / viewer（User 模型已有 role 字段）
- [ ] 装饰器 `@require_role("admin", "manager")` 用于 API 路由
- [ ] 权限矩阵：

| 操作 | admin | manager | operator | viewer |
|------|-------|---------|----------|--------|
| 创建/编辑工作流 | ✅ | ✅ | ✅ | ❌ |
| 删除工作流 | ✅ | ✅ | ❌ | ❌ |
| 启动任务 | ✅ | ✅ | ✅ | ❌ |
| 审批 | ✅ | ✅ | ✅ | ❌ |
| 查看仪表盘 | ✅ | ✅ | ✅ | ✅ |
| 管理用户 | ✅ | ❌ | ❌ | ❌ |

**验收方式** 🟢

```bash
# 1. 各角色 token 访问受限资源
# viewer 尝试创建工作流
curl -X POST http://localhost:8000/api/workflows \
  -H "Authorization: Bearer $(get_token viewer@test.com)" \
  -d '{"name":"test","yaml_definition":"..."}'
# 期望: 403 Forbidden

# 2. manager 可以审批
curl -X POST http://localhost:8000/api/approvals/{id}/approve \
  -H "Authorization: Bearer $(get_token manager@test.com)"
# 期望: 200 OK

# 3. 前端按钮根据角色显示/隐藏（手动验收）
# viewer 登录后不显示"新建工作流"按钮
```

---

### 2b.2 高级审批规则

- [ ] 新增 `approval_policy` 表和 CRUD API
- [ ] 条件语法：`step_type == "execute" && risk_level >= "high"`
- [ ] 多人会签：`approvers: [user1, user2]` + `quorum: 2`
- [ ] 审批超时：`timeout_minutes: 60` → 自动拒绝并通知
- [ ] 审批面板增加：批量审批、审批历史时间线

**验收方式** 🟢🟡

```bash
# 1. 创建审批策略
curl -X POST http://localhost:8000/api/approval-policies \
  -d '{"name":"高管审批","condition":"step_type==\"execute\"","approvers":["admin"],"quorum":1}'
# 期望: 201 Created

# 2. 策略触发：execute 步骤需审批
curl -X POST http://localhost:8000/api/tasks/{id}/start
sleep 5
curl -s http://localhost:8000/api/tasks/{id} | jq '.status'
# 期望: paused, 且有 approval 记录

# 3. 超时自动拒绝（设 timeout_minutes=1）
# 1 分钟后检查
curl -s http://localhost:8000/api/approvals?status=rejected | jq '.[0].status'
# 期望: rejected, reason 包含 "超时"

# 4. 批量审批
curl -X POST http://localhost:8000/api/approvals/batch \
  -d '{"ids":["id1","id2"],"action":"approve"}'
# 期望: 200, 两条审批记录更新
```

---

### 2b.3 合规审计报告

- [ ] `POST /api/audit/report` 生成 CSV/PDF 报告
- [ ] 报告含 SHA-256 签名，存储到 `audit_reports` 表
- [ ] 定时任务：每月 1 日自动生成上月报告并邮件发送
- [ ] 报告内容：任务执行时间线、每步 I/O、Token 消耗、审批链、操作人

**验收方式** 🟢

```bash
# 1. CSV 报告下载
curl -X POST http://localhost:8000/api/audit/report \
  -d '{"start_date":"2025-01-01","end_date":"2025-01-31","format":"csv"}' \
  -o report.csv
head -5 report.csv
# 期望: 含表头 task_id, workflow_name, status, started_at, completed_at, tokens...

# 2. 报告签名验证
curl -s http://localhost:8000/api/audit/reports | jq '.[0].sha256'
sha256sum report.csv
# 期望: 两个哈希值一致

# 3. 报告不可篡改
curl -X DELETE http://localhost:8000/api/audit/reports/{id}
# 期望: 405 Method Not Allowed 或 403
```

---

### 2b.4 SSO / LDAP 集成

- [ ] OAuth2 通用流程：配置 `OAUTH2_CLIENT_ID/SECRET/AUTHORIZE_URL/TOKEN_URL`
- [ ] 预置 Google / GitHub / Microsoft 三个 Provider
- [ ] 前端登录页增加"使用 Google 登录"等按钮
- [ ] LDAP：配置 `LDAP_SERVER/BIND_DN/BASE_DN`，登录时优先 LDAP 再 fallback 本地

**验收方式** 🟡

```bash
# 1. OAuth2 配置端点正常
curl -s http://localhost:8000/api/auth/oauth2/providers | jq
# 期望: 列出已配置的 provider

# 2. 登录页出现 SSO 按钮（手动）
# 访问 http://localhost:8000/login
# 期望: 看到 "使用 GitHub 登录" 按钮

# 3. LDAP 绑定测试
ldapsearch -x -H ldap://localhost -D "cn=admin,dc=test" -w admin -b "dc=test" "(uid=testuser)"
# 然后用 testuser 登录
curl -X POST http://localhost:8000/api/auth/login -d '{"username":"testuser","password":"..."}'
# 期望: 200 返回 token
```

---

### 2b.5 数据安全增强

- [ ] 敏感配置字段（API Key 等）加密存储，使用 AES-256-GCM
- [ ] 数据保留策略：`DATA_RETENTION_DAYS=90`，定时清理过期执行日志
- [ ] 审计日志表设置 `read_only` 权限（应用层禁止 DELETE/UPDATE）
- [ ] IP 白名单中间件：`ALLOWED_IPS=10.0.0.0/8,172.16.0.0/12`

**验收方式** 🟢

```bash
# 1. 数据库中的 API Key 为密文
sqlite3 agent_orchestrator.db "SELECT github_token FROM user_settings LIMIT 1"
# 期望: 非明文（不以 ghp_/sk- 开头）

# 2. 数据清理
# 手动创建 91 天前的任务记录，启动清理任务
curl -X POST http://localhost:8000/api/admin/cleanup
# 期望: 91 天前的 task/step_execution 记录被删除

# 3. 审计日志不可删除
curl -X DELETE http://localhost:8000/api/audit/logs/{id}
# 期望: 405 / 403

# 4. IP 白名单
curl -H "X-Forwarded-For: 1.2.3.4" http://localhost:8000/api/health
# 期望: 403（如果 ALLOWED_IPS 不含此 IP）
```

---

## Phase 2c: 产品化与体验打磨

> 目标：从开发者工具升级为可销售的产品。

### 2c.1 i18n 国际化完善

- [ ] 前端：提取所有硬编码中文到 `locales/zh.json` 和 `locales/en.json`
- [ ] 后端：`APIException` 支持 i18n key，根据 `Accept-Language` 返回对应语言
- [ ] 模板库：每个模板 `description` 字段中英双语

**验收方式** 🟡

```bash
# 1. 语言文件完整
cat frontend/locales/zh.json | jq 'keys | length'
cat frontend/locales/en.json | jq 'keys | length'
# 期望: 两个文件 key 数量相同，差值 = 0

# 2. 页面切换无残留中文
# 浏览器切换为英文 → 访问所有页面
# 期望: 不存在中文字符串（或全部在 i18n 文件中）

# 3. API 错误多语言
curl -H "Accept-Language: en" http://localhost:8000/api/workflows/xxx
# 期望: {"detail": "Workflow not found"}（非中文）
```

---

### 2c.2 Onboarding 引导

- [ ] 首次登录弹出 3 步向导：（1）选择模板（2）一键运行 Demo（3）查看结果
- [ ] 空状态页面（无工作流/无任务时）显示快速操作入口
- [ ] Demo 模式增强：预置已完成任务的示例数据（可重置）

**验收方式** 🔴

```
手动验收清单：
□ 清除浏览器 localStorage（模拟首次访问）
□ 登录后看到引导弹窗，3 步可走完
□ 空工作流列表页有"从模板创建"按钮 + 示例卡片
□ Demo 模式下仪表盘有数据（非全 0）
□ 引导可跳过，之后不再显示
```

---

### 2c.3 工作流可视化编辑器

- [ ] 基于 React Flow 的拖拽式编辑器
- [ ] 左侧步骤面板（按类型分组），拖入画布创建步骤
- [ ] 步骤间连线表示执行顺序
- [ ] 点击步骤弹出配置面板（类型/Provider/超时/条件等）
- [ ] YAML 预览面板（实时同步，双向绑定）

**验收方式** 🟡

```
验收步骤：
1. 打开 /workflows/new → 默认显示可视化编辑器（非 YAML 文本框）
2. 从左侧拖入 "analyze" 步骤 → 画布出现节点
3. 拖入 "approval" 步骤 → 连线自动建立
4. 点击 "analyze" 节点 → 右侧出现配置表单
5. 切换到 YAML 标签 → 显示对应的 YAML，语法正确
6. 在 YAML 中修改步骤名 → 切回可视化，节点名已更新
```

---

### 2c.4 性能优化

- [ ] 前端代码分割：`next/dynamic` 懒加载图表、编辑器等重型组件
- [ ] 任务列表/审计日志 API 分页（offset/limit）
- [ ] 仪表盘 API 增加 Redis 缓存（可选）或内存缓存（TTL 30s）
- [ ] 数据库索引审查：`task.status`、`task.created_at`、`step_execution.task_id`

**验收方式** 🟢

```bash
# 1. Lighthouse 评分
npx lighthouse http://localhost:8000 --output json | jq '.categories.performance.score'
# 期望: ≥ 0.90

# 2. API 分页
curl -s "http://localhost:8000/api/tasks?offset=0&limit=10" | jq '.items | length'
# 期望: ≤ 10

# 3. 数据库索引
sqlite3 agent_orchestrator.db "SELECT name FROM sqlite_master WHERE type='index'"
# 期望: 至少包含 idx_tasks_status, idx_tasks_created_at, idx_step_executions_task_id

# 4. 首屏 JS 大小
ls -lh frontend/out/_next/static/chunks/framework-*.js
# 期望: < 200KB（gzip 后）
```

---

### 2c.5 错误处理 UX

- [ ] 统一错误页面：`pages/404.tsx`、`pages/500.tsx`、`pages/403.tsx`
- [ ] API 错误 toast 使用中文消息（从后端 `error_code` 映射）
- [ ] WebSocket 断开时页面顶部出现重连提示条
- [ ] 危险操作确认弹窗：删除工作流、强制终止任务、回滚

**验收方式** 🔴

```
手动验收清单：
□ 访问 /nonexistent → 显示 404 页面（非 JSON）
□ API 返回错误时 toast 显示中文消息（非英文/技术错误码）
□ 杀死后端进程 → 页面顶部出现"连接断开，正在重连..."黄色提示条
□ 删除工作流 → 弹出确认框"确定删除工作流 XXX？此操作不可恢复"
□ 所有表单有输入校验提示（红色错误文字）
```

---

### 2c.6 Tauri 桌面端

- [ ] `desktop-tauri/` 目录可构建：`npm run tauri build`
- [ ] 应用窗口 1200×800，带菜单栏
- [ ] 系统 Tray 图标 + 右键菜单（显示/退出）
- [ ] 内嵌后端启动：应用启动时自动 `agent-orch start` 并加载前端
- [ ] Windows .msi / macOS .dmg / Linux .AppImage 打包

**验收方式** 🟡

```bash
# 1. 构建成功
cd desktop-tauri
npm run tauri build
# 期望: 生成 src-tauri/target/release/bundle/ 下的安装包

# 2. 安装后启动
# Windows: 安装 .msi → 双击桌面图标 → 浏览器窗口打开 localhost:8000
# 期望: Dashboard 正常显示

# 3. Tray 图标
# 右键 Tray 图标 → 选择"退出" → 应用关闭
```

---

## Phase 2d: 多 Agent 协作 + 平台化

> 目标：不同步骤可由不同 Agent 执行，支持协作模式。

### 2d.1 多 Agent 架构

- [x] `AgentConfig` 模型：`{name, display_name, capabilities[], provider, model, api_key_ref, max_tokens, timeout}`
- [x] Agent CRUD API + 前端管理页面
- [x] 步骤 YAML 支持 `config.agent: "code-reviewer"`（优先级高于 `config.provider`）
- [x] 步骤创建时校验 Agent 能力是否匹配步骤类型

**验收方式** 🟢

```bash
# 1. 创建 Agent
curl -X POST http://localhost:8000/api/agents \
  -d '{"name":"code-reviewer","capabilities":["review","analyze"],"provider":"deepseek","model":"deepseek-chat"}'
# 期望: 201 Created

# 2. 使用 Agent 创建工作流
yaml='name:test
steps:
  - name:审查
    type:review
    config:
      agent:code-reviewer'
curl -X POST http://localhost:8000/api/workflows -d "{\"name\":\"test\",\"yaml_definition\":\"$yaml\"}"
# 期望: 201 Created

# 3. Agent 执行任务
# 启动任务后，检查步骤执行的 agent 字段
curl -s http://localhost:8000/api/tasks/{id} | jq '.step_executions[0].agent_name'
# 期望: "code-reviewer"
```

---

### 2d.2 Agent 间通信

- [x] 步骤间传递结构化 `Message`：`{from_step, to_step, type: "feedback"|"handoff"|"query", payload}`
- [x] 新增步骤类型 `handoff`：将一个 Agent 的输出传递给另一个 Agent
- [x] 协作流水线模板：`analyst → developer → reviewer → tester`

**验收方式** 🟢

```bash
# 1. Handoff 步骤正常流转
# 定义工作流: analyze → handoff → execute
# handoff config: { from_step: "分析", to_step: "执行", mapping: { analysis: "plan" } }
curl -s http://localhost:8000/api/tasks/{id} | jq '.step_executions[2].input'
# 期望: 包含上一步的 analysis 数据

# 2. Review→Execute 反馈回路
# 定义工作流: execute → review → condition (通过则合并, 否则回 execute)
# 模拟 review 输出 {approved: false, feedback: "..."}
# 期望: 任务回到 execute 步骤（revision 模式），context 中有 feedback
```

---

### 2d.3 插件市场

- [x] 插件注册表 API：`GET/POST /api/plugins/marketplace`
- [x] CLI：`agent-orch plugin install <url>` 和 `agent-orch plugin uninstall <name>`
- [x] 前端插件市场页面：浏览/搜索/一键安装
- [x] 插件 Manifest 规范：`plugin.yaml` 包含 name/version/compatibility/schema

**验收方式** 🟢🟡

```bash
# 1. CLI 安装插件
agent-orch plugin install https://example.com/plugins/slack-notify.zip
# 期望: "插件 slack-notify v1.0.0 已安装"

# 2. 列出已安装插件
agent-orch plugin list
# 期望: 列出至少 1 个已安装插件

# 3. 前端市场页面
curl -s http://localhost:8000/plugins | head -20
# 期望: 页面包含插件卡片（名称/描述/安装按钮）

# 4. 插件 schema 生成表单
# 在步骤编辑中选择插件类型 → 自动生成配置表单
# 期望: 表单字段与 plugin.yaml schema 一致
```

---

### 2d.4 第三方集成扩展

- [x] Jira 集成：从 Issue 创建任务、同步状态
- [x] Linear 集成：同上
- [x] Confluence 集成：将执行报告发布为 Confluence 页面
- [x] Prometheus metrics 端点：`GET /metrics`

**验收方式** 🟢🟡

```bash
# 1. Prometheus 指标端点
curl -s http://localhost:8000/metrics | grep agent_orchestrator
# 期望: 包含任务计数、步骤耗时、Token 消耗等指标

# 2. Jira Issue 触发
# 在 Jira 中创建 Issue → Webhook 推送 → 自动创建任务
curl -s http://localhost:8000/api/tasks?trigger_type=jira | jq '.items | length'
# 期望: ≥ 1

# 3. Confluence 发布
# 任务完成后触发 Confluence 发布步骤
curl -s http://localhost:8000/api/tasks/{id} | jq '.step_executions[-1].output.confluence_url'
# 期望: 含 confluence 页面 URL
```

---

## 遇到的错误

| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|

（执行过程中记录）
