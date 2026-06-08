import logging
import os
from pathlib import Path

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db
from app.api import workflows, tasks, approvals, dashboard
from app.services.ws_manager import ws_manager

# 确保 agent handlers 被注册
import app.agents.executor  # noqa: F401

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 前端静态文件目录：优先读环境变量，否则相对路径（兼容开发和打包）
STATIC_DIR = Path(os.environ.get("AGENT_ORCH_STATIC_DIR", "")) if os.environ.get("AGENT_ORCH_STATIC_DIR") else Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("正在初始化数据库...")
    await init_db()
    logger.info("数据库初始化完成")
    yield


app = FastAPI(
    title="Agent Orchestrator",
    description="企业级 AI Agent 工作流编排平台",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workflows.router)
app.include_router(tasks.router)
app.include_router(approvals.router)
app.include_router(dashboard.router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, task_id: str | None = None):
    await ws_manager.connect(websocket, task_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, task_id)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# 静态前端文件服务（放在所有 API 路由之后）
if STATIC_DIR.exists():
    # Next.js 静态资源 (_next 目录)
    next_static = STATIC_DIR / "_next"
    if next_static.exists():
        app.mount("/_next", StaticFiles(directory=str(next_static)), name="next-static")

    # 其他静态文件（favicon, 图片等）
    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        # 先尝试匹配静态文件
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        # 兜底返回 index.html（SPA 路由）
        return FileResponse(str(STATIC_DIR / "index.html"))
