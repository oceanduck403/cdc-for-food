"""SQLAlchemy 异步会话与引擎"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# 开发期使用 SQLite，生产前切换 postgresql+asyncpg
if settings.database_url.startswith("sqlite"):
    async_url = settings.database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
else:
    async_url = settings.database_url

engine = create_async_engine(async_url, future=True, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """首次启动创建表（生产前请改用 Alembic）"""
    from app.models import Base  # noqa: F401  ensure models imported
    from app.models.base import Base as _Base

    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)