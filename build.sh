#!/usr/bin/env bash
# Agent Orchestrator 构建脚本
# 用法: bash build.sh

set -e

echo "=== Agent Orchestrator 构建 ==="

# 1. 构建前端
echo "[1/3] 构建前端..."
cd frontend
rm -rf .next out
npm run build
cd ..

# 2. 复制静态文件到 backend
echo "[2/3] 复制静态文件..."
rm -rf backend/static
cp -r frontend/out backend/static

# 3. 安装/更新依赖
echo "[3/3] 安装依赖..."
cd backend
pip install -e ".[dev]" -q

echo ""
echo "=== 构建完成 ==="
echo ""
echo "启动方式:"
echo "  cd backend && agent-orch start"
echo ""
echo "或开发模式:"
echo "  cd backend && agent-orch start --reload"
