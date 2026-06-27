# Agent Orchestrator 发布脚本 (Windows)
# 用法: .\scripts\publish-release.ps1 -Version "1.2.0"

param(
    [string]$Version = "1.2.0"
)

$ErrorActionPreference = "Stop"
$Repo = "reasonix/agent-orchestrator"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  发布 Agent Orchestrator v${Version}" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 构建前端
Write-Host "[1/5] 构建前端..." -ForegroundColor Yellow
Push-Location frontend
npm run build
Pop-Location
Write-Host "✅ 前端构建完成" -ForegroundColor Green

# 2. 复制静态文件
Write-Host "[2/5] 复制静态文件..." -ForegroundColor Yellow
if (Test-Path backend/static) { Remove-Item -Recurse -Force backend/static }
Copy-Item -Recurse frontend/out backend/static
Write-Host "✅ 静态文件已复制" -ForegroundColor Green

# 3. 构建后端 sidecar
Write-Host "[3/5] 构建后端 sidecar..." -ForegroundColor Yellow
Push-Location backend
if (Get-Command pyinstaller -ErrorAction SilentlyContinue) {
    pyinstaller agent-orch-backend.spec --clean --onefile --distpath dist
} else {
    Write-Host "⚠️  pyinstaller 未安装，跳过 sidecar 构建" -ForegroundColor DarkYellow
    Write-Host "   安装: pip install pyinstaller" -ForegroundColor DarkYellow
}
Pop-Location
Write-Host "✅ Sidecar 构建完成" -ForegroundColor Green

# 4. 复制 sidecar
Write-Host "[4/5] 复制 sidecar..." -ForegroundColor Yellow
if (Test-Path "backend/dist/agent-orch-backend.exe") {
    Copy-Item backend/dist/agent-orch-backend.exe desktop-tauri/src-tauri/binaries/agent-orch-backend-x86_64-pc-windows-msvc.exe -Force
    Write-Host "✅ Sidecar 已复制" -ForegroundColor Green
} else {
    Write-Host "⚠️  Sidecar 未找到，请手动构建" -ForegroundColor DarkYellow
}

# 5. 构建 Tauri 应用
Write-Host "[5/5] 构建 Tauri 应用..." -ForegroundColor Yellow
Push-Location desktop-tauri
cargo tauri build
Pop-Location
Write-Host "✅ Tauri 应用构建完成" -ForegroundColor Green

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  构建完成！" -ForegroundColor Green
Write-Host ""
Write-Host "  安装包位置:" -ForegroundColor White
Write-Host "  - NSIS: desktop-tauri/src-tauri/target/release/bundle/nsis/" -ForegroundColor White
Write-Host "  - MSI:  desktop-tauri/src-tauri/target/release/bundle/msi/" -ForegroundColor White
Write-Host ""
Write-Host "  下一步：" -ForegroundColor White
Write-Host "  1. 创建 GitHub Release (tag: v${Version})" -ForegroundColor White
Write-Host "  2. 上传安装包和 latest.json" -ForegroundColor White
Write-Host "  3. latest.json 需要签名（使用 tauri signer）" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor Cyan
