"""毒蘑菇 GIS 风险地图"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.knowledge_service import list_mushroom_risk, get_mushroom_risk

router = APIRouter()


@router.get("/mushroom-risk")
async def list_risk(
    city: str = Query("chengdu"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = await list_mushroom_risk(db, city=city)
    return {"items": items}


@router.get("/mushroom-risk/{item_id}")
async def detail(item_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    item = await get_mushroom_risk(db, item_id)
    if not item:
        return {"id": item_id, "name": "占位风险点", "level": "中"}
    return item