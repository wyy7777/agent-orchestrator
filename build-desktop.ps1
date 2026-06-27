# Agent Orchestrator Desktop Build Script (Windows)
# 构建前端 → 打包后端 → 构建桌面应用

$ErrorActionPreference = "Stop"
$VERSION = "1.2.0"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Agent Orchestrator Desktop v${VERSION}" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 构建前端
Write-Host "[1/4] 构建前端..." -ForegroundColor Yellow
Push-Location frontend
npm run build
Pop-Location
Write-Host "✅ 前端构建完成" -ForegroundColor Green

# 2. 复制前端静态文件到后端
Write-Host "[2/4] 复制前端静态文件..." -ForegroundColor Yellow
if (Test-Path backend/static) { Remove-Item -Recurse -Force backend/static }
Copy-Item -Recurse frontend/out backend/static
Write-Host "✅ 静态文件已复制到 backend/static" -ForegroundColor Green

# 3. 打包后端为 sidecar 二进制
Write-Host "[3/4] 打包后端 sidecar..." -ForegroundColor Yellow
Push-Location backend
if (Get-Command pyinstaller -ErrorAction SilentlyContinue) {
    pyinstaller agent-orch-backend.spec --clean --onefile --distpath dist
    Write-Host "✅ 后端 sidecar 打包完成" -ForegroundColor Green
} else {
    Write-Host "⚠️  pyinstaller 未安装，跳过 sidecar 打包" -ForegroundColor DarkYellow
    Write-Host "   安装: pip install pyinstaller" -ForegroundColor DarkYellow
}
Pop-Location

# 4. 复制 sidecar 到 Tauri 目录
Write-Host "[4/4] 复制 sidecar 到桌面应用..." -ForegroundColor Yellow
if (Test-Path "backend/dist/agent-orch-backend.exe") {
    Copy-Item backend/dist/agent-orch-backend.exe desktop-tauri/src-tauri/binaries/agent-orch-backend-x86_64-pc-windows-msvc.exe -Force
    Write-Host "✅ sidecar 已复制" -ForegroundColor Green
} else {
    Write-Host "⚠️  sidecar 未找到，请手动构建" -ForegroundColor DarkYellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  构建准备完成！" -ForegroundColor Green
Write-Host ""
Write-Host "  下一步：" -ForegroundColor White
Write-Host "  cd desktop-tauri; npm run tauri build" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor Cyan
