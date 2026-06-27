"""桌面端启动入口 — Tauri sidecar 模式"""
import os
import sys
import tempfile

# PyInstaller 打包后的临时解压目录
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
    os.chdir(base_dir)
    sys.path.insert(0, base_dir)

    # 数据库和日志必须写到可写目录（_MEIPASS 在 Windows 上只读）
    data_dir = os.path.join(os.environ.get("APPDATA", tempfile.gettempdir()), "AgentOrchestrator")
    os.makedirs(data_dir, exist_ok=True)
    os.environ["AGENT_ORCH_DATA_DIR"] = data_dir

    # 如果有 .env 文件，重写 DATABASE_URL 到可写目录
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            env_content = f.read()
        env_content = env_content.replace(
            "sqlite+aiosqlite:///./agent_orchestrator.db",
            f"sqlite+aiosqlite:///{data_dir.replace(os.sep, '/')}/agent_orchestrator.db"
        )
        # 写到可写数据目录，让 config.py 从那里读取
        writable_env = os.path.join(data_dir, ".env")
        with open(writable_env, "w", encoding="utf-8") as f:
            f.write(env_content)
        os.environ["AGENT_ORCH_DOTENV"] = writable_env
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    sys.path.insert(0, base_dir)

import uvicorn

HOST = "127.0.0.1"
PORT = int(os.environ.get("AGENT_ORCH_PORT", "18000"))

print(f"Agent Orchestrator 后端启动: http://{HOST}:{PORT}", flush=True)

uvicorn.run(
    "app.main:app",
    host=HOST,
    port=PORT,
    log_level="warning",
    access_log=False,
    reload=False,
)
