"""管理后台（用户/知识库/识别日志/统计）"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

router = APIRouter()


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)) -> dict:
    """占位：返回基础统计"""
    return {
        "users": 0,
        "meals_today": 0,
        "knowledge_items": 0,
        "mushroom_markers": 0,
    }