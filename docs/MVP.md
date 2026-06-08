# MVP 拆解 & 开发计划

## MVP 范围

> 一个开发者可以定义 YAML 工作流 → Agent 在沙箱中执行 → 关键节点需人工审批 → 自动生成 PR → 全链路日志可见

---

## Sprint 分解（共 6 个 Sprint，每 Sprint 1 周）

### Sprint 1: 项目脚手架 + 工作流定义

**目标**: 能解析 YAML 工作流定义，存到数据库

```
任务：
□ 初始化项目 (Next.js + Express/FastAPI + PostgreSQL)
□ 设计数据库 Schema (Workflow, Task, Step, Execution)
□ 实现 YAML 解析器
□ 实现工作流 CRUD API
□ 前端: 工作流列表页 + 新建页 (YAML 编辑器)

交付物：能创建/编辑/列出工作流
```

### Sprint 2: 执行引擎 MVP

**目标**: 能按工作流定义逐步执行（先不接 Agent）

```
任务：
□ 实现状态机驱动的执行引擎
□ 实现步骤类型: manual (审批), script (跑脚本)
□ 执行日志写入数据库
□ 前端: 任务详情页，实时看到步骤执行

交付物：定义工作流 → 触发执行 → 看到步骤逐个完成
```

### Sprint 3: 接入 AI Agent

**目标**: 把"script"步骤替换为真正的 AI Agent 调用

```
任务：
□ 封装 Claude API / OpenAI API 调用
□ 实现 analyze 步骤（读代码 → 输出方案）
□ 实现 execute 步骤（根据方案修改代码）
□ 实现 review 步骤（审查 diff → 生成报告）
□ Prompt 模板管理

交付物：Agent 能真正分析代码并生成改动方案
```

### Sprint 4: Git 沙箱 + PR

**目标**: Agent 在隔离分支操作，最终产出 PR

```
任务：
□ Docker 沙箱：为每个任务创建临时容器
□ Git 操作：clone → 创建分支 → commit → push
□ PR 创建：对接 GitHub API
□ 沙箱清理：任务结束后销毁容器

交付物：Agent 在沙箱中修改代码，产出真实 PR
```

### Sprint 5: 审批 + 回滚

**目标**: 关键步骤可审批，错误可回滚

```
任务：
□ 审批节点：步骤暂停 → 通知 → 等待决策
□ 审批 API + 前端审批面板
□ 回滚功能：撤销 Git 改动，回到上一步
□ Token 限额：超限自动终止

交付物：完整审批链路 + 一键回滚
```

### Sprint 6: Dashboard + 发布

**目标**: 可视化运营 + 上线

```
任务：
□ 仪表盘：执行统计、成功率、token 消耗
□ 任务时间线视图
□ 历史记录查询/筛选
□ 文档 + Landing Page
□ 部署上线 (Vercel + Railway/Render)

交付物：可公开展示并使用
```

---

## 技术栈选型

| 层 | 选型 | 理由 |
|----|------|------|
| 编排引擎 | [Temporal](https://temporal.io/) | 生产级工作流引擎，自带重试/超时/持久化/审计 |
| 后端 | Node.js (NestJS) 或 Python (FastAPI) | 看团队技术栈 |
| 前端 | Next.js + TailwindCSS | 快出 MVP |
| 数据库 | PostgreSQL | Temporal 原生支持，关系型适合审计日志 |
| Agent API | Claude API / OpenAI API | 直接调 API，不依赖 CrewAI 等不成熟框架 |
| 沙箱 | Docker | 简单够用 |
| 部署 | Vercel (前端) + Railway (后端/Temporal) | 免运维 |
| 代码托管 | GitHub API | 最主流 |

---

## 不做的事情

- ❌ 不自己训练模型
- ❌ 不自己做 Agent 框架（直接用 Claude/OpenAI API）
- ❌ 不做多 Agent 通信（先做好单 Agent 编排）
- ❌ 不做 SaaS 多租户（先服务单团队）
- ❌ 不接 GitLab/Bitbucket（先只接 GitHub）
- ❌ 不做 IDE 插件（先做 Web Dashboard）
