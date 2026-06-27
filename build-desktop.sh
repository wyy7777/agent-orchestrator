#!/bin/bash
# Agent Orchestrator Desktop Build Script
# 构建前端 → 打包后端 → 构建桌面应用

set -e

VERSION="1.2.0"
echo "=========================================="
echo "  Agent Orchestrator Desktop v${VERSION}"
echo "=========================================="
echo ""

# 1. 构建前端
echo "[1/4] 构建前端..."
cd frontend
npm run build
cd ..
echo "✅ 前端构建完成"

# 2. 复制前端静态文件到后端
echo "[2/4] 复制前端静态文件..."
rm -rf backend/static
cp -r frontend/out backend/static
echo "✅ 静态文件已复制到 backend/static"

# 3. 打包后端为 sidecar 二进制
echo "[3/4] 打包后端 sidecar..."
cd backend
if command -v pyinstaller &> /dev/null; then
    pyinstaller agent-orch-backend.spec --clean --onefile --distpath dist
    echo "✅ 后端 sidecar 打包完成"
else
    echo "⚠️  pyinstaller 未安装，跳过 sidecar 打包"
    echo "   安装: pip install pyinstaller"
fi
cd ..

# 4. 复制 sidecar 到 Tauri 目录
echo "[4/4] 复制 sidecar 到桌面应用..."
if [ -f "backend/dist/agent-orch-backend.exe" ]; then
    cp backend/dist/agent-orch-backend.exe desktop-tauri/src-tauri/binaries/agent-orch-backend-x86_64-pc-windows-msvc.exe
    echo "✅ sidecar 已复制"
else
    echo "⚠️  sidecar 未找到，请手动构建"
fi

echo ""
echo "=========================================="
echo "  构建准备完成！"
echo ""
echo "  下一步："
echo "  cd desktop-tauri && npm run tauri build"
echo "=========================================="
