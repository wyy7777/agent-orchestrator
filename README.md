# Agent Orchestrator

企业级 AI Agent 工作流编排平台 — 让 AI Agent 可靠、可控、可审计。

> 像 GitHub Actions 编排 CI/CD 一样，编排 AI Agent 的每一步执行。

## 核心特性

- **YAML 工作流定义** — 声明式定义多步骤 AI 工作流
- **人工审批门控** — 关键步骤需人工审批，防止 AI 失控
- **一键回滚** — 出问题可回退到任意已完成步骤
- **实时状态追踪** — WebSocket 实时推送任务状态变更
- **Token 预算控制** — 每个任务独立 Token 上限，防止成本失控
- **多 AI 模型支持** — DeepSeek / OpenAI / Claude 自由切换
- **一键启动** — `pip install` 后一条命令启动完整服务（前端 + 后端）

## 快速开始

### 安装

```bash
git clone https://github.com/wyy7777/agent-orchestrator.git
cd agent-orchestrator/backend
pip install -e .
```

### 配置

创建 `.env` 文件：

```env
# DeepSeek（推荐，性价比高）
OPENAI_API_KEY=sk-your-deepseek-api-key
OPENAI_BASE_URL=https://api.deepseek.com
DEFAULT_AI_PROVIDER=deepseek
DEFAULT_AI_MODEL=deepseek-chat

# 或 OpenAI
# OPENAI_API_KEY=sk-your-openai-key
# DEFAULT_AI_PROVIDER=openai
# DEFAULT_AI_MODEL=gpt-4o

# 或 Claude
# ANTHROPIC_API_KEY=sk-ant-your-key
# DEFAULT_AI_PROVIDER=claude
```

### 启动

```bash
agent-orch start
```

浏览器打开 `http://localhost:8000` 即可使用。

### 命令行选项

```bash
agent-orch start --port 9000          # 自定义端口
agent-orch start --db-path ./data.db   # 自定义数据库路径
agent-orch start --reload              # 开发模式（代码变更自动重启）
agent-orch init                        # 生成示例工作流文件
agent-orch version                     # 查看版本
```

## 使用流程

1. 在「工作流」页面创建 YAML 工作流定义
2. 点击「立即执行」触发任务
3. AI 自动执行分析/执行/审查步骤
4. 遇到审批节点时，在「审批」页面批准或拒绝
5. 在「任务详情」页面查看全链路执行结果

## 工作流示例

```yaml
name: 代码审查助手
description: 自动分析代码问题并生成修复建议

settings:
  max_tokens: 4000

steps:
  - name: 代码分析
    type: analyze
    config:
      provider: deepseek
      model: deepseek-chat

  - name: 人工审批
    type: approval

  - name: 代码修改
    type: execute
    config:
      provider: deepseek

  - name: 审查报告
    type: review
    config:
      provider: deepseek
```

### 步骤类型

| 类型 | 说明 |
|------|------|
| `analyze` | AI 分析输入，输出结构化结果 |
| `execute` | 根据分析结果执行操作（生成代码等） |
| `review` | AI 审查执行结果，生成质量报告 |
| `approval` | 人工审批门控 |
| `merge` | 合并结果（如创建 Git PR） |
| `script` | 执行自定义脚本 |

## 架构

```
┌─────────────────────────────────────────┐
│          前端 (Next.js 静态文件)          │
│   Dashboard │ 工作流 │ 任务 │ 审批       │
└────────────────────┬────────────────────┘
                     │ HTTP / WebSocket
┌────────────────────┴────────────────────┐
│         FastAPI 后端 (单进程)             │
│                                         │
│  REST API ── WebSocket ── 状态机引擎     │
│       │                     │           │
│       └── 步骤处理器 ───────┘           │
│           (analyze/execute/review)       │
│                  │                       │
│           AI 代理层                       │
│       DeepSeek / OpenAI / Claude         │
│                  │                       │
│           SQLite 数据库                   │
└─────────────────────────────────────────┘
```

## 技术栈

| 层 | 选型 |
|----|------|
| 前端 | Next.js (Pages Router) + Ant Design |
| 后端 | Python FastAPI |
| 数据库 | SQLite（零配置） |
| 执行引擎 | 自研 asyncio 状态机 |
| AI API | DeepSeek / OpenAI / Claude |
| CLI | Typer + Uvicorn |

## 项目结构

```
agent-orchestrator/
├── backend/
│   ├── app/
│   │   ├── api/           # REST API 路由
│   │   ├── agents/        # AI 模型集成
│   │   ├── engine/        # 工作流引擎
│   │   ├── models/        # 数据库模型
│   │   ├── services/      # WebSocket 管理
│   │   ├── config.py      # 配置
│   │   ├── database.py    # 数据库初始化
│   │   └── main.py        # FastAPI 入口
│   ├── cli.py             # CLI 入口
│   ├── static/            # 前端构建产物
│   └── pyproject.toml
├── frontend/
│   ├── pages/             # 页面
│   ├── components/        # 组件
│   ├── lib/               # API 客户端
│   └── next.config.ts
├── docs/                  # 产品文档
├── build.sh               # 一键构建脚本
└── README.md
```

## 开发

```bash
# 后端开发模式
cd backend
agent-orch start --reload

# 前端开发模式（独立端口，代理到后端 API）
cd frontend
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

# 重新构建前端并打包
bash build.sh
```

## API 文档

启动后访问 `http://localhost:8000/docs` 查看 Swagger 文档。

## 许可证

MIT License
