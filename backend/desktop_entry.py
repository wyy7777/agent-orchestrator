"""Agent Orchestrator 桌面端入口 - Tauri sidecar 专用"""

import os
import sys
import signal
import socket
import threading
import uvicorn
import typer
from pathlib import Path


def _find_free_port(preferred: int = 8000) -> int:
    """检测端口是否可用，不可用则自动递增"""
    port = preferred
    while port < preferred + 100:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            port += 1
    return preferred


def _resolve_static_dir() -> Path:
    """定位前端静态文件目录（兼容 PyInstaller 打包和开发模式）"""
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后，static 在 exe 同级目录
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    static_dir = base / "static"
    return static_dir


def main():
    """启动 Agent Orchestrator 桌面端服务"""
    port = _find_free_port(8000)
    static_dir = _resolve_static_dir()

    # 设置数据库路径
    data_dir = Path.home() / ".agent-orch"
    data_dir.mkdir(exist_ok=True)
    db_path = str(data_dir / "data.db")
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

    # 确保静态文件目录存在
    if static_dir.exists():
        os.environ["AGENT_ORCH_STATIC_DIR"] = str(static_dir)

    # 通过 stdout 输出就绪信号，Tauri 侧监听此信号
    print(f"AGENT_ORCH_PORT={port}", flush=True)
    print(f"AGENT_ORCH_READY=http://localhost:{port}", flush=True)

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
