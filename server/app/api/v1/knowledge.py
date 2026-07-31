"""营养与食品安全知识库"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, current_user_id
from app.services.knowledge_service import list_articles, get_article

router = APIRouter()


@router.get("")
async def list_kb(
    category: str = Query(..., description="guide/mushroom/safety/disease"),
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
) -> dict:
    items, total = await list_articles(db, category=category, keyword=q, page=page, page_size=page_size)
    return {"items": items, "total": total, "page": page, "pageSize": page_size}


@router.get("/{article_id}")
async def detail(article_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    article = await get_article(db, article_id)
    if not article:
        return {"id": article_id, "title": "占位文章", "contentHtml": "<p>详细内容待运营录入</p>"}
    return article