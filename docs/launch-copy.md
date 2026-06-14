# Agent Orchestrator — 发布文案

## Show HN

### 标题
Show HN: Agent Orchestrator – AI writes code, you approve the PR

### 正文
Hi HN,

I built Agent Orchestrator, an open-source platform that orchestrates AI agent workflows with human approval gates — think "GitHub Actions for AI agents."

**The problem:** AI coding agents (Copilot, Cursor, Devin) can write code, but they operate as black boxes. In team settings, you need:
- Visibility into what the AI is doing at each step
- Human approval before changes land in your repo
- Token budget control to prevent cost surprises
- Audit trails for compliance

**How it works:**
1. Define a workflow in YAML (analyze → human approval → execute → review → PR)
2. Trigger it from a GitHub Issue or manually
3. AI analyzes the problem, proposes a fix, waits for your approval, writes the code, reviews itself, then creates a PR
4. You approve/reject at any gate — the AI pauses and waits

**Key features:**
- YAML workflow definitions (like GitHub Actions)
- Human approval gates at any step
- One-click rollback to any completed step
- Token budget per task (default 500K)
- Multi-model: DeepSeek / OpenAI / Claude
- Real-time WebSocket status updates
- Desktop app (Tauri) + Web UI
- 5 built-in templates: Bug Fix, PR Review, Security Scan, Code Refactor, Doc Generator
- 📋 Audit reports (CSV export, SHA-256 signed) for EU AI Act compliance
- 🔐 RBAC (admin/manager/operator/viewer roles)
- 🌐 Internationalization (中文 / English)

**Tech stack:** Python FastAPI + Next.js + SQLite + Tauri v2

It's MIT licensed: https://github.com/reasonix/agent-orchestrator

Would love feedback on the workflow model — is "human-in-the-loop" the right abstraction for AI coding agents?

---

## Product Hunt

### Tagline
AI writes code, you approve the PR

### Description
Agent Orchestrator is an open-source platform that makes AI coding agents reliable, controllable, and auditable.

Define multi-step AI workflows in YAML — analyze issues, generate fixes, review code, create PRs — with human approval gates at every critical step.

**Why?**
AI agents can write code, but deploying AI-generated code without human review is risky. Agent Orchestrator adds a structured approval pipeline between AI and your codebase.

**Features:**
🔄 YAML workflow definitions (like GitHub Actions)
👤 Human approval gates at any step
⏪ One-click rollback
💰 Token budget control
🤖 DeepSeek / OpenAI / Claude support
📊 Real-time execution tracking
🖥️ Desktop app + Web UI
📋 5 built-in workflow templates
📋 Audit reports with SHA-256 (EU AI Act compliant)
🔐 RBAC roles (admin / manager / operator / viewer)
🌐 i18n (中文 / English)

**Open source. MIT licensed. Self-hosted.**

### Topics
- Developer Tools
- Artificial Intelligence
- Open Source
- Productivity

### Gallery alt text
- Dashboard view showing task statistics and recent executions
- Workflow editor with YAML definition and step visualization
- Task detail page with real-time execution timeline
- Approval queue for pending human decisions

---

## Reddit (r/programming)

### Title
I built an open-source "GitHub Actions for AI agents" — YAML workflows with human approval gates

### Body
After using various AI coding tools, I realized the missing piece isn't better AI — it's better control over AI.

Agent Orchestrator lets you define multi-step AI workflows in YAML, with human approval gates at any step. The AI pauses and waits for your decision before proceeding.

Example workflow:
```
analyze issue → [human approval] → generate fix → code review → [human approval] → create PR
```

Key design decisions:
- **YAML over GUI** for workflow definitions (version-controllable, diffable)
- **Approval gates** are first-class citizens, not afterthoughts
- **Token budgets** per task to prevent cost surprises
- **Sandbox branches** — AI writes to a separate branch, never directly to main
- **Multi-model** — switch between DeepSeek, OpenAI, Claude per step

Tech: Python FastAPI + Next.js + SQLite + Tauri desktop

MIT licensed: https://github.com/reasonix/agent-orchestrator

Feedback welcome — especially on the workflow abstraction model.

---

## Twitter/X Thread

**Tweet 1:**
I built an open-source platform that makes AI coding agents follow a structured workflow with human approval gates.

Think "GitHub Actions, but for AI agents."

AI writes code → you review → AI creates PR.

Thread 🧵

**Tweet 2:**
The problem: AI agents (Copilot, Cursor, Devin) can write code, but they're black boxes.

In teams, you need:
- Visibility at each step
- Human approval before merging
- Token cost control
- Audit trails

**Tweet 3:**
How it works:

1. Define workflow in YAML
2. AI analyzes the issue
3. [Human approval gate]
4. AI generates the fix
5. AI reviews its own code
6. [Human approval gate]
7. AI creates the PR

The AI pauses at each gate and waits for you.

**Tweet 4:**
Key features:
- YAML workflow definitions
- Human approval at any step
- One-click rollback
- Token budget per task
- Multi-model (DeepSeek/OpenAI/Claude)
- Real-time WebSocket updates
- Desktop app + Web UI
- 5 built-in templates
- Audit reports (SHA-256 signed, EU AI Act)
- RBAC (admin/manager/operator/viewer)
- i18n (中文/English)

**Tweet 5:**
Open source, MIT licensed.

GitHub: https://github.com/reasonix/agent-orchestrator

Built with Python FastAPI + Next.js + Tauri v2

Would love your feedback on the "human-in-the-loop" workflow model for AI agents.

---

## V2EX / 掘金

### 标题
开源了一个 AI Agent 工作流编排平台 — 让 AI 写代码，你来审批

### 正文
做了个开源项目：Agent Orchestrator，解决的问题是 AI Agent 写代码时缺乏可控性。

核心思路：用 YAML 定义多步骤工作流，在关键步骤加人工审批门控。AI 分析问题 → 你审批 → AI 写代码 → AI 自审 → 你审批 → 自动创建 PR。

特点：
- YAML 声明式工作流（类似 GitHub Actions）
- 人工审批门控（AI 会暂停等你决定）
- 一键回滚到任意已完成步骤
- Token 预算控制（防成本失控）
- 支持 DeepSeek / OpenAI / Claude
- 实时 WebSocket 状态推送
- 桌面端（Tauri）+ Web 界面
- 5 个内置模板
- 📋 合规审计报告（CSV 导出，SHA-256 签名）— 满足 EU AI Act
- 🔐 RBAC 角色权限（admin/manager/operator/viewer）
- 🌐 国际化（中文 / English）

技术栈：Python FastAPI + Next.js + SQLite + Tauri v2
协议：MIT

GitHub: https://github.com/reasonix/agent-orchestrator

欢迎试用和反馈。
