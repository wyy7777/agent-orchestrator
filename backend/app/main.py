import logging
import uuid
import time
from pathlib import Path
from collections import defaultdict

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.database import init_db
from app.logging_config import setup_logging
from app.api import workflows, tasks, approvals, dashboard, webhooks, schedules, notifications, plugins
from app.services.ws_manager import ws_manager
from app.services.scheduler import scheduler

# 确保 agent handlers 被注册
import app.agents.executor  # noqa: F401

# 配置日志（控制台 + 文件旋转）
setup_logging(log_level="DEBUG" if settings.DEBUG else "INFO")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "static"


async def _create_demo_data():
    """Demo 模式：创建示例工作流。"""
    from app.database import async_session
    from app.models.workflow import Workflow
    from app.api.workflows import _load_templates
    from sqlalchemy import select, func

    async with async_session() as db:
        count = (await db.execute(select(func.count(Workflow.id)))).scalar() or 0
        if count > 0:
            return  # 已有数据，跳过

        templates = _load_templates()
        for tpl in templates[:3]:  # 导入前 3 个模板
            wf = Workflow(name=tpl["name"], description=tpl["description"], yaml_definition=tpl["yaml_definition"])
            db.add(wf)
        await db.commit()
        logger.info(f"Demo 模式：已导入 {min(3, len(templates))} 个工作流模板")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("正在初始化数据库...")
    await init_db()

    # 崩溃恢复：标记孤儿任务为 failed
    from app.database import async_session
    from app.engine.state_machine import ExecutionEngine
    async with async_session() as db:
        engine = ExecutionEngine(db)
        await engine.recover_orphaned_tasks()

    # 加载外部插件
    from app.engine.plugin import load_external_plugins
    load_external_plugins()

    logger.info(f"Agent Orchestrator 已启动: http://{settings.HOST}:{settings.PORT}")

    # Demo 模式：自动创建示例数据
    import os
    if os.environ.get("DEMO_MODE") == "true":
        await _create_demo_data()

    scheduler.start_scheduler()

    yield

    scheduler.stop_scheduler()


app = FastAPI(
    title="Agent Orchestrator",
    description="企业级 AI Agent 工作流编排平台",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workflows.router)
app.include_router(tasks.router)
app.include_router(approvals.router)
app.include_router(dashboard.router)
app.include_router(webhooks.router)
app.include_router(schedules.router)
app.include_router(notifications.router)
app.include_router(plugins.router)


# 简单的内存 Rate Limiter（每 IP 每分钟 60 次请求）
_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 60
RATE_WINDOW = 60  # 秒


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # 跳过 WebSocket 和静态文件
    if request.url.path.startswith("/ws") or request.url.path.startswith("/_next"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - RATE_WINDOW

    # 清理过期记录
    _rate_store[client_ip] = [t for t in _rate_store[client_ip] if t > window_start]

    if len(_rate_store[client_ip]) >= RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "请求过于频繁，请稍后再试"},
        )

    _rate_store[client_ip].append(now)
    return await call_next(request)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, task_id: str | None = None):
    await ws_manager.connect(websocket, task_id)
    try:
        while True:
            data = await websocket.receive_text()
            # 心跳回复
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, task_id)
    except Exception:
        ws_manager.disconnect(websocket, task_id)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "0.2.0",
        "debug": settings.DEBUG,
        "ws_connections": ws_manager.connection_count,
    }


# 静态前端文件服务（放在所有 API 路由之后）
if STATIC_DIR.exists():
    next_static = STATIC_DIR / "_next"
    if next_static.exists():
        app.mount("/_next", StaticFiles(directory=str(next_static)), name="next-static")

    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(STATIC_DIR / "index.html"))
