"""用户模型"""
from datetime import date
from typing import Optional
from sqlalchemy import String, Integer, Float, Date, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """统一用户表 - 通过 role 区分 patient/doctor/admin"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 角色：patient=患者，doctor=医生，admin=管理员
    role: Mapped[str] = mapped_column(String(16), default="patient", index=True)

    # 患者登录方式（openid 或 phone）
    openid: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, nullable=True)
    unionid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True, index=True, nullable=True)

    # 医生/管理员登录方式（username + password_hash）
    username: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    # 通用字段
    nickname: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    avatar: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    real_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 真实姓名

    # 健康档案（患者使用）
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sex: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    height_cm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    activity_level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    health_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 医生扩展字段
    department: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 科室
    title: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 职称
    intro: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 简介
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否接诊中

    # 会员状态（患者）
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False)
    vip_expire_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    total_analysis_count: Mapped[int] = mapped_column(Integer, default=0)
    purchased_analysis_count: Mapped[int] = mapped_column(Integer, default=0)

    # 启用/禁用（医生/管理员可被禁用）
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    last_active_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
