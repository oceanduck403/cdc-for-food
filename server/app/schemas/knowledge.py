"""知识库 schemas"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class KnowledgeListItem(BaseModel):
    id: int
    title: str
    summary: Optional[str] = None
    category: str
    source: Optional[str] = None
    updatedAt: Optional[datetime] = None


class KnowledgeDetail(KnowledgeListItem):
    contentHtml: str


class MushroomRiskItem(BaseModel):
    id: int
    name: str
    species: Optional[str] = None
    lat: float
    lng: float
    level: str
    period: Optional[str] = None
    description: Optional[str] = None