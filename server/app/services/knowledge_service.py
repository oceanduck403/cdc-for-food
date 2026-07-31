"""知识库与毒蘑菇 GIS 数据访问"""
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeArticle, MushroomRisk


async def list_articles(
    db: AsyncSession,
    category: str,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[dict], int]:
    stmt = select(KnowledgeArticle).where(KnowledgeArticle.category == category)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(KnowledgeArticle.title.like(like) | KnowledgeArticle.summary.like(like))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(stmt.order_by(KnowledgeArticle.id.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = [_article_to_item(a) for a in rows]
    return items, int(total or 0)


async def get_article(db: AsyncSession, article_id: str) -> Optional[dict]:
    try:
        aid = int(article_id)
    except ValueError:
        return None
    a = await db.get(KnowledgeArticle, aid)
    if not a:
        return None
    item = _article_to_item(a)
    item["contentHtml"] = a.content_html
    return item


async def list_mushroom_risk(db: AsyncSession, city: str) -> list[dict]:
    stmt = select(MushroomRisk).where(MushroomRisk.city == city)
    rows = (await db.execute(stmt)).scalars().all()
    return [_mushroom_to_item(r) for r in rows]


async def get_mushroom_risk(db: AsyncSession, item_id: str) -> Optional[dict]:
    try:
        mid = int(item_id)
    except ValueError:
        return None
    r = await db.get(MushroomRisk, mid)
    return _mushroom_to_item(r) if r else None


def _article_to_item(a: KnowledgeArticle) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "summary": a.summary,
        "category": a.category,
        "source": a.source,
        "updatedAt": (a.updated_at or datetime.now(tz=timezone.utc)).isoformat(),
    }


def _mushroom_to_item(r: MushroomRisk) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "species": r.species,
        "lat": r.lat,
        "lng": r.lng,
        "level": r.level,
        "period": r.period,
        "description": r.description,
    }