#!/bin/bash
# Agent Orchestrator 启动脚本

echo "🚀 启动 Agent Orchestrator..."

# 启动后端
echo "📦 启动后端 (FastAPI)..."
cd "$(dirname "$0")/backend"
python -m uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# 启动前端
echo "🎨 启动前端 (Next.js)..."
cd "$(dirname "$0")/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Agent Orchestrator 已启动！"
echo "   前端: http://localhost:3000"
echo "   后端: http://localhost:8000"
echo "   API 文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" SIGINT SIGTERM
wait
