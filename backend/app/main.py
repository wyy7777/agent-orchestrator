import asyncio
import logging
import uuid
import time
from pathlib import Path
from collections import defaultdict
from ipaddress import ip_address, ip_network

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import init_db
from app.logging_config import setup_logging
from app.api import workflows, tasks, approvals, dashboard, webhooks, schedules, notifications, plugins
from app.api import sandboxes
from app.api import audit
from app.api.agents import router as agents_router
from app.api.approval_policies import router as approval_policies_router
from app.api.integrations import router as integrations_router
from app.api.metrics import router as metrics_router
from app.api.plugin_marketplace import router as plugin_marketplace_router
from app.api.auth import router as auth_router
from app.services.ws_manager import ws_manager
from app.services.scheduler import scheduler

# 确保 agent handlers 被注册
import app.agents.executor  # noqa: F401
# 确保 User 模型被注册到 Base.metadata
import app.models.user  # noqa: F401

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


async def _engine_event_handler(event: str, *args):
    """引擎事件回调：解耦 notifier。"""
    from app.services.notifier import notifier
    handlers = {
        "task_started": notifier.notify_task_started,
        "task_completed": notifier.notify_task_completed,
        "task_failed": notifier.notify_task_failed,
        "step_completed": notifier.notify_step_completed,
        "step_failed": notifier.notify_step_failed,
        "approval_needed": notifier.notify_approval_needed,
    }
    handler = handlers.get(event)
    if handler:
        try:
            await handler(*args)
        except Exception as e:
            logger.warning(f"通知发送失败 ({event}): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 确保 SECRET_KEY 已配置
    from app.auth import ensure_secret_key
    ensure_secret_key()

    logger.info("正在初始化数据库...")
    await init_db()

    # 启动速率限制器清理任务
    global _cleanup_task
    _cleanup_task = asyncio.create_task(_cleanup_rate_store())

    # 崩溃恢复：标记孤儿任务为 failed
    from app.database import async_session
    from app.engine.state_machine import ExecutionEngine
    async with async_session() as db:
        engine = ExecutionEngine(db, on_event=_engine_event_handler)
        await engine.recover_orphaned_tasks()

        # 恢复断路器状态
        from app.engine.circuit_breaker import circuit_breaker
        await circuit_breaker.restore_from_db(db)

        # 恢复调度器状态
        await scheduler.load_from_db(db)

    # 加载外部插件
    from app.engine.plugin import load_external_plugins
    load_external_plugins()

    logger.info(f"Agent Orchestrator 已启动: http://{settings.HOST}:{settings.PORT}")

    # Demo 模式：自动创建示例数据
    import os
    if os.environ.get("DEMO_MODE") == "true":
        await _create_demo_data()

    scheduler.start_scheduler()

    # 启动通知 worker
    from app.services.notifier import notifier as _notifier
    await _notifier.start()

    yield

    # 停止速率限制器清理任务
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass

    scheduler.stop_scheduler()

    # 关闭通知器 worker + HTTP 客户端
    await _notifier.close()

    from app.services.sandbox import sandbox_manager

    await sandbox_manager.cleanup_all()


app = FastAPI(
    title="Agent Orchestrator",
    description="企业级 AI Agent 工作流编排平台",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

_cors_origins = settings.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=(_cors_origins != ["*"]),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(workflows.router)
app.include_router(tasks.router)
app.include_router(approvals.router)
app.include_router(dashboard.router)
app.include_router(webhooks.router)
app.include_router(schedules.router)
app.include_router(notifications.router)
app.include_router(plugins.router)
app.include_router(sandboxes.router)
app.include_router(audit.router)
app.include_router(approval_policies_router)
app.include_router(agents_router)
app.include_router(integrations_router)
app.include_router(metrics_router)
app.include_router(plugin_marketplace_router)


# API Key 认证中间件
API_KEY_EXEMPT_PATHS = {"/api/health", "/api/webhooks/github", "/api/auth/register", "/api/auth/login"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if settings.API_KEY and request.url.path.startswith("/api/"):
            # 豁免路径
            if request.url.path in API_KEY_EXEMPT_PATHS:
                return await call_next(request)
            api_key = request.headers.get("X-API-Key")
            if api_key != settings.API_KEY:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "无效或缺失的 API Key"},
                )
        return await call_next(request)


app.add_middleware(APIKeyMiddleware)


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """IP 白名单中间件：ALLOWED_IPS 不为空时只允许白名单 IP。"""

    async def dispatch(self, request: Request, call_next):
        if not settings.ALLOWED_IPS:
            return await call_next(request)
        client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "127.0.0.1")
        client_ip = client_ip.split(",")[0].strip()
        try:
            addr = ip_address(client_ip)
            for cidr in settings.ALLOWED_IPS.split(","):
                if addr in ip_network(cidr.strip()):
                    return await call_next(request)
        except ValueError:
            pass
        return JSONResponse(status_code=403, content={"detail": "IP 不在白名单中"})


app.add_middleware(IPWhitelistMiddleware)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    """记录每个请求的耗时。"""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    # 只记录 API 请求，跳过静态文件
    if request.url.path.startswith("/api/"):
        logger.info(
            f"{request.method} {request.url.path} → {response.status_code} ({duration_ms:.1f}ms)"
        )
    response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"
    return response


# 简单的内存 Rate Limiter
_rate_store: dict[str, list[float]] = defaultdict(list)


async def _cleanup_rate_store():
    """后台任务：定期清理过期的速率限制记录。"""
    while True:
        await asyncio.sleep(60)
        now = time.time()
        window_start = now - settings.RATE_WINDOW
        expired_ips = [
            ip for ip, timestamps in _rate_store.items()
            if not timestamps or all(t <= window_start for t in timestamps)
        ]
        for ip in expired_ips:
            del _rate_store[ip]
        if expired_ips:
            logger.debug(f"速率限制器清理：移除 {len(expired_ips)} 个过期 IP 记录")


_cleanup_task: asyncio.Task | None = None


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # 跳过 WebSocket 和静态文件
    if request.url.path.startswith("/ws") or request.url.path.startswith("/_next"):
        return await call_next(request)

    # 获取客户端 IP：优先检查反向代理 header，并做基本验证
    client_ip = request.client.host if request.client else "unknown"
    forwarded_for = request.headers.get("X-Forwarded-For")
    real_ip = request.headers.get("X-Real-IP")
    if forwarded_for:
        # X-Forwarded-For 可能包含多个 IP，取第一个（最初客户端）
        first_ip = forwarded_for.split(",")[0].strip()
        # 基本 IP 格式验证，防止伪造注入
        if first_ip and all(c in "0123456789.:abcdefABCDEF" for c in first_ip):
            client_ip = first_ip
    elif real_ip and all(c in "0123456789.:abcdefABCDEF" for c in real_ip.strip()):
        client_ip = real_ip.strip()

    now = time.time()
    window_start = now - settings.RATE_WINDOW

    # 清理当前 IP 的过期记录
    _rate_store[client_ip] = [t for t in _rate_store[client_ip] if t > window_start]

    if len(_rate_store[client_ip]) >= settings.RATE_LIMIT:
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
        "version": settings.APP_VERSION,
    }


# 静态前端文件服务（放在所有 API 路由之后）
if STATIC_DIR.exists():
    next_static = STATIC_DIR / "_next"
    if next_static.exists():
        app.mount("/_next", StaticFiles(directory=str(next_static)), name="next-static")

    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        # 排除 API 路由
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "API 路由未找到"})

        file_path = (STATIC_DIR / full_path).resolve()
        if not str(file_path).startswith(str(STATIC_DIR.resolve())):
            return JSONResponse(status_code=403, content={"detail": "访问被拒绝"})
        if file_path.is_file():
            return FileResponse(str(file_path))
        # 尝试添加 .html 后缀
        html_path = (STATIC_DIR / f"{full_path}.html").resolve()
        if html_path.is_file() and str(html_path).startswith(str(STATIC_DIR.resolve())):
            return FileResponse(str(html_path))
        return FileResponse(str(STATIC_DIR / "index.html"))
