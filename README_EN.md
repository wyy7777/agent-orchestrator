# Agent Orchestrator

Enterprise-grade AI Agent workflow orchestration platform — make AI Agents reliable, controllable, and auditable.

> Orchestrate every step of AI Agent execution, just like GitHub Actions orchestrates CI/CD.

[中文文档](./README.md)

## Features

- **YAML Workflow Definitions** — Declaratively define multi-step AI workflows
- **Human Approval Gates** — Critical steps require human approval to prevent AI from going off the rails
- **One-Click Rollback** — Roll back to any completed step if something goes wrong
- **Real-Time Status Tracking** — WebSocket pushes task status changes in real time
- **Token Budget Control** — Per-task token limits to prevent cost overruns
- **Multi AI Model Support** — Seamlessly switch between DeepSeek / OpenAI / Claude
- **Workflow Template Library** — 5 built-in templates to get started quickly
- **Demo Mode** — Zero-config experience with `--demo` flag
- **Dark Mode** — Automatic theme based on system preference
- **Conditional Branching** — if/else conditions to dynamically control workflow execution
- **PostgreSQL Support** — Production-ready PostgreSQL database option
- **Desktop App** — Tauri v2 desktop wrapper with sidecar backend

## Quick Start

### Install

```bash
git clone https://github.com/reasonix/agent-orchestrator.git
cd agent-orchestrator/backend
pip install -e .
```

### Configure

Create a `.env` file:

```env
# DeepSeek (recommended, cost-effective)
OPENAI_API_KEY=sk-your-deepseek-api-key
OPENAI_BASE_URL=https://api.deepseek.com
DEFAULT_AI_PROVIDER=deepseek
DEFAULT_AI_MODEL=deepseek-chat

# Or OpenAI
# OPENAI_API_KEY=sk-your-openai-key
# DEFAULT_AI_PROVIDER=openai
# DEFAULT_AI_MODEL=gpt-4o

# Or Claude
# ANTHROPIC_API_KEY=sk-ant-your-key
# DEFAULT_AI_PROVIDER=claude
```

### Run

```bash
agent-orch start
```

Open `http://localhost:8000` in your browser.

### CLI Options

```bash
agent-orch start --port 9000          # Custom port
agent-orch start --db-path ./data.db   # Custom database path
agent-orch start --reload              # Dev mode (auto-restart on code changes)
agent-orch start --demo                # Demo mode (auto-creates sample workflows)
agent-orch init                        # Generate example workflow file
agent-orch version                     # Show version
```

## Usage Flow

1. Create a YAML workflow definition in the "Workflows" page
2. Click "Run" to trigger a task
3. AI automatically executes analyze/execute/review steps
4. When hitting an approval node, approve or reject in the "Approvals" page
5. View full execution results in the "Task Detail" page

## Workflow Example

```yaml
name: Code Review Assistant
description: Automatically analyze code issues and generate fix suggestions

settings:
  max_tokens: 4000

steps:
  - name: code_analysis
    type: analyze
    config:
      provider: deepseek
      model: deepseek-chat

  - name: human_approval
    type: approval

  - name: code_fix
    type: execute
    config:
      provider: deepseek

  - name: review_report
    type: review
    config:
      provider: deepseek
```

### Conditional Branching Example

```yaml
name: Smart Fix
steps:
  - name: analyze
    type: analyze

  - name: check_severity
    type: condition
    condition: "{results.analyze.analysis.severity} == 'high'"
    else:
      - name: light_fix
        type: execute
        config:
          provider: deepseek

  - name: heavy_fix
    type: execute
    config:
      provider: deepseek
```

### Step Types

| Type | Description |
|------|-------------|
| `analyze` | AI analyzes input, outputs structured results |
| `execute` | Execute actions based on analysis (generate code, etc.) |
| `review` | AI reviews execution results, generates quality report |
| `approval` | Human approval gate |
| `merge` | Merge results (e.g., create Git PR) |
| `condition` | Conditional branching with if/else support |
| `subtask` | Sub-workflow invocation |
| `loop` | Loop execution over sub-steps |
| `script` | Execute custom script |

## Built-in Templates

| Template | Description |
|----------|-------------|
| Bug Auto Fix | Analyze Issue → Generate fix → Human approval → Execute fix → Code review → Create PR |
| PR Auto Review | Auto-review Pull Requests with quality report |
| Security Scan | Scan code for security vulnerabilities |
| Code Refactor | Analyze code structure, propose and execute refactoring |
| Doc Generator | Auto-generate documentation and comments |

## Architecture

```
┌─────────────────────────────────────────┐
│       Frontend (Next.js Static Export)   │
│   Dashboard │ Workflows │ Tasks │ Approvals│
└────────────────────┬────────────────────┘
                     │ HTTP / WebSocket
┌────────────────────┴────────────────────┐
│         FastAPI Backend (Single Process)  │
│                                         │
│  REST API ── WebSocket ── State Machine  │
│       │                     │           │
│       └── Step Handlers ────┘           │
│           (analyze/execute/review)       │
│                  │                       │
│           AI Agent Layer                 │
│       DeepSeek / OpenAI / Claude         │
│                  │                       │
│      SQLite / PostgreSQL Database        │
└─────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js (Pages Router) + Ant Design + Monaco Editor |
| Backend | Python FastAPI |
| Database | SQLite (zero-config) / PostgreSQL (production) |
| Execution Engine | Custom asyncio state machine |
| AI API | DeepSeek / OpenAI / Claude |
| CLI | Typer + Uvicorn |
| Desktop | Tauri v2 (Rust) |

## Development

```bash
# Backend dev mode
cd backend
agent-orch start --reload

# Frontend dev mode (separate port, proxy to backend API)
cd frontend
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

# Run tests
cd backend
pytest -v

# Rebuild frontend and package
bash build.sh
```

## API Documentation

After starting, visit `http://localhost:8000/docs` for Swagger documentation.

## License

MIT License
