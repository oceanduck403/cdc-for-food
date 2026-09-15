"""聊天相关数据模型"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, ForeignKey, DateTime, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ConsultAssignment(Base, TimestampMixin):
    """医患分配关系（一对一的核心）

    patient_id - 患者
    doctor_id  - 主治医生
    status     - active=进行中，closed=已结束
    """
    __tablename__ = "consult_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/closed
    # 患者首次发起聊天的时间
    first_chat_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 最后一条消息时间
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 最后一条消息预览
    last_message_preview: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        Index("ix_assignment_patient_doctor", "patient_id", "doctor_id"),
    )


class Consultation(Base, TimestampMixin):
    """聊天消息记录"""
    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 关联分配关系
    assignment_id: Mapped[int] = mapped_column(Integer, ForeignKey("consult_assignments.id"), index=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    # 消息发送方：patient=患者，doctor=医生，system=系统消息（如会诊邀请）
    sender_role: Mapped[str] = mapped_column(String(16), index=True)
    sender_id: Mapped[int] = mapped_column(Integer)
    # 消息类型：text/image/consult_invite/consult_accept/consult_refuse
    msg_type: Mapped[str] = mapped_column(String(16), default="text")
    content: Mapped[str] = mapped_column(Text)
    # 图片消息的 URL
    image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # 会诊邀请相关（仅 msg_type=consult_* 时使用）
    consult_target_doctor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    consult_target_doctor_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    consult_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # pending/accepted/refused
    consult_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 是否已读
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
