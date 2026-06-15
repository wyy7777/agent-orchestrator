# 研究发现 — Agent Orchestrator

> 基于代码库全面审查的发现记录。

## 一、项目现状总结

**代码规模**：后端 ~15,000 行 Python / 前端 ~8,000 行 TypeScript / 模板 10 个 YAML

### 1.1 已完成的核心能力

| 模块 | 文件 | 成熟度 | 备注 |
|------|------|--------|------|
| YAML 解析器 | `engine/yaml_parser.py` | ⭐⭐⭐ | 支持 9 种步骤类型，带 MD5 缓存，解析安全 |
| 状态机引擎 | `engine/state_machine.py` | ⭐⭐⭐ | asyncio 自研，支持并行/条件/循环/子任务/重试/回滚 |
| 步骤执行器 | `engine/step_executor.py` | ⭐⭐⭐ | 单步/子任务/循环，超时+重试 |
| AI Agent 层 | `agents/base.py`, `agents/executor.py` | ⭐⭐⭐ | DeepSeek/OpenAI/Claude 统一基类，结构化输出校验 |
| 条件评估 | `engine/condition_eval.py` | ⭐⭐ | 支持比较/存在性/复合(and/or) |
| 插件系统 | `engine/plugin.py` | ⭐⭐ | 3 个内置插件 + 外部加载，有 schema 定义 |
| GitHub 集成 | `integrations/github.py` | ⭐⭐⭐ | 分支/文件写入/commit/PR 全套 |
| GitLab 集成 | `integrations/gitlab.py` | ⭐⭐ | 基本 CRUD |
| Bitbucket 集成 | `integrations/bitbucket.py` | ⭐⭐ | 基本 CRUD |
| 沙箱管理 | `services/sandbox.py` | ⭐⭐ | Docker + 本地双模式 |
| 通知系统 | `services/notifier.py` | ⭐⭐⭐ | 4 通道：Slack/钉钉/企微/飞书 |
| Cron 调度 | `services/scheduler.py` | ⭐⭐ | 基于 croniter，30s 检查间隔 |
| WebSocket | `services/ws_manager.py` | ⭐⭐ | 实时状态推送 |
| 认证 | `api/auth.py`, `auth.py` | ⭐⭐ | JWT + API Key + 速率限制 |
| 审计 | `api/audit.py`, `services/audit.py` | ⭐⭐ | 审计日志 CRUD |
| 仪表盘 | `api/dashboard.py` | ⭐⭐ | 统计/趋势/CSV 导出 |
| 前端 Dashboard | `pages/index.tsx` | ⭐⭐⭐ | Ant Design Charts，统计卡片+图表+用例引导 |
| 前端工作流 | `pages/workflows/` | ⭐⭐⭐ | 列表/新建/编辑/详情/导入 |
| 前端任务 | `pages/tasks/` | ⭐⭐ | 列表/详情 |
| 前端审批 | `pages/approvals/` | ⭐⭐ | 审批面板 |
| 前端触发器 | `pages/triggers/` | ⭐⭐ | Webhook + Cron 管理 |
| CLI | `cli.py` | ⭐⭐ | Typer，start/init/version |

### 1.2 差距分析（对照 PRD）

| PRD 需求 | 当前状态 | 差距 |
|----------|---------|------|
| 质量评分 (P1) | ❌ 未实现 | 需新增 AI 评估步骤或独立评分服务 |
| 高级审批规则 (P1) | ❌ 未实现 | 审批目前无角色/条件限制 |
| 多 Agent 协作 (P2) | ❌ 未实现 | 每步骤单一 Agent，无协作机制 |
| SSO/LDAP (P2) | ❌ 未实现 | 仅有 JWT 本地认证 |
| RBAC (P2) | ❌ 未实现 | 用户模型仅有 role 字段，无实际鉴权 |
| 合规报告 (P2) | ❌ 未实现 | 审计日志有，但无一键报告 |
| 私有部署方案 (P2) | ❌ 未实现 | 仅有 Dockerfile，无完整方案 |
| 插件市场 (P2) | 框架已有 | 加载机制有，缺市场和 UI |
| 多租户 (P2) | ❌ 未实现 | 数据无隔离 |
| 桌面端 (P3) | 骨架已建 | `desktop-tauri/` 目录存在，未见完整实现 |
| i18n 国际化 | 部分有 | 前端有 `useI18n` hook，但不完整 |
| 测试覆盖 | ⚠️ 不足 | 8 个测试文件，核心路径覆盖有限 |

### 1.3 代码质量问题

| 问题 | 严重度 | 位置 |
|------|--------|------|
| 部分 API 缺少输入验证 | 中 | 多处 |
| 错误处理不统一 | 中 | 部分直接 raise，部分返回 error dict |
| 日志级别不一致 | 低 | 混用 info/warning/error |
| 硬编码字符串 | 低 | 部分 status 值 |
| 缺少类型标注 | 低 | 部分 `dict[str, Any]` 过于宽泛 |
| 无集成测试 | 高 | 仅有 `test_full.py` 手动脚本 |

## 二、关键架构决策记录

1. **自研状态机 vs Temporal**：文档设计用 Temporal，实际实现用 asyncio 自研。好处是零外部依赖，代价是缺少持久化执行和自动重试的 Temporal 级别保障。
2. **直接调 API vs Agent 框架**：有意不依赖 CrewAI/AutoGen，用固定 Prompt 模板 + 结构化输出。这是正确的架构选择。
3. **SQLite 默认 + PostgreSQL 可选**：降低入门门槛，生产可切换。
4. **前端打包为静态文件**：Next.js 构建产物直接由 FastAPI 托管，简化部署。
