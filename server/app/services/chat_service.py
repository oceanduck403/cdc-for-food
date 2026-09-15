"""聊天服务：医患分配、消息收发、会诊邀请"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from loguru import logger
from sqlalchemy import select, desc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ConsultAssignment, Consultation
from app.models.user import User


# ────────────────────────────────────────────────────────────────────
# 自动分配医生
# ────────────────────────────────────────────────────────────────────

async def auto_assign_doctor(db: AsyncSession, patient_id: int) -> Optional[ConsultAssignment]:
    """为患者自动分配一个医生

    策略：
    1. 先查找患者已有的 active 分配，如有则直接返回
    2. 否则查找接诊中(is_available=true)且患者数量最少的医生
    3. 创建新的分配关系

    返回 ConsultAssignment 或 None（无医生可用时）
    """
    from app.services.appointment_service import book
    appointment = await book(db, patient_id)
    return await db.get(ConsultAssignment, appointment.assignment_id) if appointment.assignment_id else None


async def get_assignment(db: AsyncSession, assignment_id: int) -> Optional[ConsultAssignment]:
    return await db.get(ConsultAssignment, assignment_id)


async def get_doctor_patients(db: AsyncSession, doctor_id: int) -> List[Dict[str, Any]]:
    """获取医生的所有患者列表（含最近消息）"""
    stmt = (
        select(ConsultAssignment, User)
        .join(User, User.id == ConsultAssignment.patient_id)
        .where(ConsultAssignment.doctor_id == doctor_id)
        .order_by(desc(ConsultAssignment.last_message_at))
    )
    res = await db.execute(stmt)
    rows = res.all()
    return [
        {
            "assignment_id": a.id,
            "patient_id": u.id,
            "patient_name": u.real_name or u.nickname or f"患者{u.id}",
            "patient_avatar": u.avatar,
            "patient_phone": u.phone,
            "patient_age": u.age,
            "patient_sex": u.sex,
            "patient_health_notes": u.health_notes,
            "status": a.status,
            "last_message_at": a.last_message_at.isoformat() if a.last_message_at else None,
            "last_message_preview": a.last_message_preview,
        }
        for a, u in rows
    ]


async def search_doctor_patients(
    db: AsyncSession, doctor_id: int, keyword: str
) -> List[Dict[str, Any]]:
    """按 ID / 姓名 / 手机号 搜索医生的患者"""
    kw = f"%{keyword}%"
    stmt = (
        select(ConsultAssignment, User)
        .join(User, User.id == ConsultAssignment.patient_id)
        .where(
            ConsultAssignment.doctor_id == doctor_id,
            or_(
                User.real_name.like(kw),
                User.nickname.like(kw),
                User.phone.like(kw),
                User.id == _safe_int(keyword),
            ),
        )
        .order_by(desc(ConsultAssignment.last_message_at))
    )
    res = await db.execute(stmt)
    rows = res.all()
    return [
        {
            "assignment_id": a.id,
            "patient_id": u.id,
            "patient_name": u.real_name or u.nickname or f"患者{u.id}",
            "patient_avatar": u.avatar,
            "patient_phone": u.phone,
            "patient_age": u.age,
            "patient_sex": u.sex,
            "patient_health_notes": u.health_notes,
            "status": a.status,
            "last_message_at": a.last_message_at.isoformat() if a.last_message_at else None,
            "last_message_preview": a.last_message_preview,
        }
        for a, u in rows
    ]


def _safe_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


# ────────────────────────────────────────────────────────────────────
# 消息发送
# ────────────────────────────────────────────────────────────────────

async def send_message(
    db: AsyncSession,
    assignment_id: int,
    sender_role: str,
    sender_id: int,
    content: str,
    msg_type: str = "text",
    image_url: Optional[str] = None,
    consult_target_doctor_id: Optional[int] = None,
    consult_target_doctor_name: Optional[str] = None,
    consult_status: Optional[str] = None,
    consult_note: Optional[str] = None,
) -> Consultation:
    """发一条聊天消息"""
    assignment = await db.get(ConsultAssignment, assignment_id)
    if not assignment:
        raise ValueError(f"分配关系不存在：{assignment_id}")

    msg = Consultation(
        assignment_id=assignment_id,
        patient_id=assignment.patient_id,
        doctor_id=assignment.doctor_id,
        sender_role=sender_role,
        sender_id=sender_id,
        msg_type=msg_type,
        content=content,
        image_url=image_url,
        consult_target_doctor_id=consult_target_doctor_id,
        consult_target_doctor_name=consult_target_doctor_name,
        consult_status=consult_status,
        consult_note=consult_note,
        is_read=False,
    )
    db.add(msg)

    # 更新分配的最后消息时间
    now = datetime.utcnow()
    assignment.last_message_at = now
    if assignment.first_chat_at is None:
        assignment.first_chat_at = now
    assignment.last_message_preview = content[:200]
    await db.commit()
    await db.refresh(msg)
    return msg


async def list_messages(
    db: AsyncSession,
    assignment_id: int,
    limit: int = 50,
    before_id: Optional[int] = None,
) -> List[Consultation]:
    """获取聊天记录（按时间倒序，可选 before_id 分页）"""
    stmt = (
        select(Consultation)
        .where(Consultation.assignment_id == assignment_id)
    )
    if before_id is not None:
        stmt = stmt.where(Consultation.id < before_id)
    stmt = stmt.order_by(desc(Consultation.id)).limit(limit)
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def mark_read(db: AsyncSession, assignment_id: int, reader_role: str) -> int:
    """标记某分配中发给 reader_role 的消息为已读"""
    # reader_role 收到的消息，sender_role 应是对方的角色
    if reader_role == "patient":
        sender_filter = "doctor"
    elif reader_role == "doctor":
        sender_filter = "patient"
    else:
        return 0
    stmt = (
        select(Consultation)
        .where(
            Consultation.assignment_id == assignment_id,
            Consultation.sender_role == sender_filter,
            Consultation.is_read == False,
        )
    )
    res = await db.execute(stmt)
    msgs = res.scalars().all()
    for m in msgs:
        m.is_read = True
    await db.commit()
    return len(msgs)


async def get_unread_count(db: AsyncSession, assignment_id: int, reader_role: str) -> int:
    if reader_role == "patient":
        sender_filter = "doctor"
    elif reader_role == "doctor":
        sender_filter = "patient"
    else:
        return 0
    stmt = (
        select(Consultation.id)
        .where(
            Consultation.assignment_id == assignment_id,
            Consultation.sender_role == sender_filter,
            Consultation.is_read == False,
        )
    )
    res = await db.execute(stmt)
    return len(res.all())


# ────────────────────────────────────────────────────────────────────
# 会诊邀请
# ────────────────────────────────────────────────────────────────────

async def create_consult_invite(
    db: AsyncSession,
    assignment_id: int,
    inviter_doctor_id: int,
    target_doctor_id: int,
    note: str = "",
) -> Optional[Consultation]:
    """医生邀请另一位医生进行会诊（生成 system 消息）"""
    target = await db.get(User, target_doctor_id)
    if not target or target.role != "doctor":
        return None

    inviter = await db.get(User, inviter_doctor_id)
    inviter_name = inviter.real_name or inviter.nickname if inviter else "医生"

    content = f"📋 {inviter_name} 邀请 {target.real_name or target.nickname} 加入会诊"
    if note:
        content += f"\n备注：{note}"

    msg = await send_message(
        db,
        assignment_id=assignment_id,
        sender_role="system",
        sender_id=inviter_doctor_id,
        content=content,
        msg_type="consult_invite",
        consult_target_doctor_id=target_doctor_id,
        consult_target_doctor_name=target.real_name or target.nickname,
        consult_status="pending",
        consult_note=note,
    )
    return msg


async def respond_consult_invite(
    db: AsyncSession,
    message_id: int,
    accept: bool,
) -> Optional[Consultation]:
    """会诊医生对邀请进行回应"""
    msg = await db.get(Consultation, message_id)
    if not msg or msg.msg_type != "consult_invite":
        return None

    target = await db.get(User, msg.consult_target_doctor_id) if msg.consult_target_doctor_id else None
    target_name = target.real_name or target.nickname if target else "医生"

    if accept:
        msg.consult_status = "accepted"
        msg.content = f"✅ {target_name} 已加入会诊"
    else:
        msg.consult_status = "refused"
        msg.content = f"❌ {target_name} 婉拒了会诊邀请"

    await db.commit()
    await db.refresh(msg)
    return msg


async def list_available_doctors(db: AsyncSession, exclude_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """列出所有可会诊的医生（供医生邀请时选择）"""
    stmt = select(User).where(
        User.role == "doctor",
        User.is_active == True,
    )
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    res = await db.execute(stmt.order_by(User.id))
    doctors = res.scalars().all()
    return [
        {
            "id": d.id,
            "name": d.real_name or d.nickname,
            "department": d.department,
            "title": d.title,
            "intro": d.intro,
        }
        for d in doctors
    ]
