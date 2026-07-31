"""膳食分析（拍照）"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_id, get_db
from app.core.errors import BusinessError
from app.services.meal_service import analyze_meal, get_meal_report

router = APIRouter()


class AnalyzeMealRequest(BaseModel):
    imageBase64: str


@router.post("/analyze")
async def analyze(
    body: AnalyzeMealRequest,
    user_id: str = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not body.imageBase64:
        raise BusinessError("EMPTY_IMAGE", "图片不能为空")
    return await analyze_meal(db, user_id=user_id, image_b64=body.imageBase64)


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