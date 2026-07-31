"""用户：档案、每日配额"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_id, get_db
from app.core.errors import BusinessError
from app.services.user_service import get_profile, update_profile, get_daily_quota

router = APIRouter()


@router.get("/me")
async def me(user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)) -> dict:
    return await get_profile(db, user_id)


@router.put("/me")
async def update_me(
    payload: dict,
    user_id: str = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    profile = await update_profile(db, user_id, payload)
    if not profile:
        raise BusinessError("USER_NOT_FOUND", "用户不存在", status_code=404)
    return profile


@router.get("/me/quota")
async def quota(user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)) -> dict:
    return await get_daily_quota(db, user_id)