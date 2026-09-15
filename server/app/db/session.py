"""SQLAlchemy 异步会话与引擎"""
from typing import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# 开发期使用 SQLite，生产前切换 postgresql+asyncpg
if settings.database_url.startswith("sqlite"):
    async_url = settings.database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
else:
    async_url = settings.database_url

engine = create_async_engine(async_url, future=True, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """首次启动创建表（生产前请改用 Alembic）"""
    from app.models import Base  # noqa: F401  ensure models imported
    from app.models.base import Base as _Base

    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
        # create_all 不会为已有 SQLite/PostgreSQL 用户表补充新字段。
        await ensure_admin_token_version_column(conn)


async def ensure_admin_token_version_column(conn) -> None:
    columns = await conn.run_sync(
        lambda sync_conn: {column["name"] for column in inspect(sync_conn).get_columns("users")}
    )
    if "token_version" not in columns:
        await conn.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"))
