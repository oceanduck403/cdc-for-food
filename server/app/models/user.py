"""用户模型"""
from datetime import date
from typing import Optional
from sqlalchemy import String, Integer, Float, Date, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    openid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    unionid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    nickname: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    avatar: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # 健康档案
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sex: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    height_cm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    activity_level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    health_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 会员状态
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False)
    vip_expire_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    total_analysis_count: Mapped[int] = mapped_column(Integer, default=0)  # 累计使用次数
    purchased_analysis_count: Mapped[int] = mapped_column(Integer, default=0)  # 已购买次数

    last_active_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)