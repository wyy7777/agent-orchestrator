"""桌面端启动入口 — Tauri sidecar 模式"""
import os
import sys

# PyInstaller 打包后的临时解压目录
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
    os.chdir(base_dir)
    sys.path.insert(0, base_dir)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    sys.path.insert(0, base_dir)

import uvicorn

# 固定端口，Tauri 前端连接此端口
HOST = "127.0.0.1"
PORT = 18000

# 输出启动信号，Tauri 通过此判断后端就绪
print(f"Agent Orchestrator 后端启动: http://{HOST}:{PORT}", flush=True)

uvicorn.run(
    "app.main:app",
    host=HOST,
    port=PORT,
    log_level="warning",
    access_log=False,
    reload=False,
)
