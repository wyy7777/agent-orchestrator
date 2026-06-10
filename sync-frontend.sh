#!/usr/bin/env bash
# 前端同步脚本 - 构建前端并复制到后端静态目录
# 用法: bash sync-frontend.sh

set -e

echo "=== 前端同步 ==="

# 1. 构建前端
echo "[1/2] 构建前端..."
cd frontend
rm -rf .next out
npm run build
cd ..

# 2. 同步到后端
echo "[2/2] 同步到 backend/static/..."
rm -rf backend/static/*
cp -r frontend/out/* backend/static/

echo ""
echo "=== 同步完成 ==="
echo "刷新浏览器即可看到最新更改"
