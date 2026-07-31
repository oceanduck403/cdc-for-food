"""依赖注入：数据库会话、当前用户等"""
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_subject
from app.db.session import SessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def current_user_id(subject: str = Depends(get_current_subject)) -> str:
    return subject


__all__ = ["get_db", "current_user_id"]