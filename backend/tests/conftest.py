import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

# 确保所有模型被导入（用于表创建）
from app.models import User, Workflow, Task, StepExecution, Approval, ApprovalPolicy, AuditLog, AuditReport, AgentConfig, Webhook  # noqa: F401

TEST_DB_URL = "sqlite+aiosqlite:///./test.db"
test_engine = create_async_engine(TEST_DB_URL, echo=False)
test_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    # 重置速率限制器，避免跨测试的 429 错误
    from app.main import _rate_store
    _rate_store.clear()

    # 覆盖全局 async_session，使 _execute_workflow 等后台任务也使用测试数据库
    import app.database
    original_session = app.database.async_session
    app.database.async_session = test_session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    app.database.async_session = original_session


@pytest_asyncio.fixture
async def db():
    async with test_session() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    async def override_get_db():
        async with test_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
