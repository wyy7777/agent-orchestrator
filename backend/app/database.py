import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event

from app.config import settings

logger = logging.getLogger(__name__)

_is_postgres = "postgresql" in settings.DATABASE_URL

# 根据数据库类型配置引擎参数
engine_kwargs = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}

if _is_postgres:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,
    })
else:
    engine_kwargs.update({
        "connect_args": {"check_same_thread": False},
    })

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    async with engine.begin() as conn:
        if _is_postgres:
            # PostgreSQL 优化
            await conn.exec_driver_sql("SET statement_timeout = '30s'")
            await conn.exec_driver_sql("SET lock_timeout = '10s'")
        else:
            # SQLite WAL 模式
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        await conn.run_sync(Base.metadata.create_all)
    logger.info(f"数据库初始化完成 ({'PostgreSQL' if _is_postgres else 'SQLite'})")
