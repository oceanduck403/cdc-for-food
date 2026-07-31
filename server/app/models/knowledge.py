"""知识库文章与毒蘑菇风险点"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class KnowledgeArticle(Base, TimestampMixin):
    __tablename__ = "knowledge_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(32), index=True)  # guide/mushroom/safety/disease
    title: Mapped[str] = mapped_column(String(256))
    summary: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content_html: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MushroomRisk(Base, TimestampMixin):
    __tablename__ = "mushroom_risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city: Mapped[str] = mapped_column(String(32), index=True, default="chengdu")
    name: Mapped[str] = mapped_column(String(128))
    species: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    level: Mapped[str] = mapped_column(String(16))  # 高/中/低
    period: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)