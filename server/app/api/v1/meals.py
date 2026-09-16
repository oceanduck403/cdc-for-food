"""膳食分析（拍照）"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_id, get_db
from app.services.meal_service import get_meal_report

router = APIRouter()


@router.get("/{meal_id}/report")
async def report(
    meal_id: str,
    user_id: str = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_meal_report(db, user_id=user_id, meal_id=meal_id)


@router.get("/latest/report")
async def latest_report(
    user_id: str = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_meal_report(db, user_id=user_id, meal_id="latest")
