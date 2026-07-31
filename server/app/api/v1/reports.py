"""报告：今日汇总"""
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_id, get_db
from app.services.meal_service import daily_summary

router = APIRouter()


@router.get("/today")
async def today(user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)) -> dict:
    summary = await daily_summary(db, user_id=user_id, day=date.today())
    return summary