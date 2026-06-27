#!/bin/bash
# Agent Orchestrator 发布脚本
# 用法: ./scripts/publish-release.sh <version>

set -e

VERSION=${1:-"1.2.0"}
REPO="reasonix/agent-orchestrator"

echo "=========================================="
echo "  发布 Agent Orchestrator v${VERSION}"
echo "=========================================="
echo ""

# 1. 构建前端
echo "[1/5] 构建前端..."
cd frontend && npm run build && cd ..
echo "✅ 前端构建完成"

# 2. 复制静态文件
echo "[2/5] 复制静态文件..."
rm -rf backend/static && cp -r frontend/out backend/static
echo "✅ 静态文件已复制"

# 3. 构建后端 sidecar
echo "[3/5] 构建后端 sidecar..."
cd backend
pyinstaller agent-orch-backend.spec --clean --onefile --distpath dist
cd ..
echo "✅ Sidecar 构建完成"

# 4. 复制 sidecar
echo "[4/5] 复制 sidecar..."
cp backend/dist/agent-orch-backend.exe desktop-tauri/src-tauri/binaries/agent-orch-backend-x86_64-pc-windows-msvc.exe
echo "✅ Sidecar 已复制"

# 5. 构建 Tauri 应用
echo "[5/5] 构建 Tauri 应用..."
cd desktop-tauri
cargo tauri build
cd ..
echo "✅ Tauri 应用构建完成"

echo ""
echo "=========================================="
echo "  构建完成！"
echo ""
echo "  安装包位置:"
echo "  - NSIS: desktop-tauri/src-tauri/target/release/bundle/nsis/"
echo "  - MSI:  desktop-tauri/src-tauri/target/release/bundle/msi/"
echo ""
echo "  下一步："
echo "  1. 创建 GitHub Release (tag: v${VERSION})"
echo "  2. 上传安装包和 latest.json"
echo "  3. latest.json 需要签名（使用 tauri signer）"
echo "=========================================="
