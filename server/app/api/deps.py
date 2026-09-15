"""依赖注入：数据库会话、当前用户等"""
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_subject
from app.db.session import get_db
from app.models.user import User


async def current_user_id(subject: str = Depends(get_current_subject)) -> str:
    return subject


async def current_admin(
    subject: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated administrator from the database.

    Authorization is based on the persisted role instead of a role claim supplied
    by the client. Disabled administrators lose access immediately.
    """
    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="无效的登录态") from exc

    user = await db.get(User, user_id)
    if not user or user.role != "admin" or not user.is_active:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


__all__ = ["get_db", "current_user_id", "current_admin"]
