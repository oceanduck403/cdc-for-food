"""免费预约与在线状态；独立建表，不修改既有医患聊天记录。"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class DoctorPresence(Base):
    __tablename__ = 'doctor_presence'
    doctor_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime)


class Appointment(Base, TimestampMixin):
    __tablename__ = 'appointments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey('users.id'), unique=True)
    status: Mapped[str] = mapped_column(String(16), default='waiting')
    assignment_id: Mapped[Optional[int]] = mapped_column(ForeignKey('consult_assignments.id'), nullable=True)
