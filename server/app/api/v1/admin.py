"""管理后台：医生账号管理、患者管理、聊天记录查看"""
import re
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_db
from app.core.security import get_current_subject, hash_password, verify_password
from app.models.chat import ConsultAssignment, Consultation
from app.models.user import User
from app.services.media_service import signed_media_url

router = APIRouter()


def _validate_managed_password(password: str) -> None:
    """Apply one production password policy to administrator and doctor accounts."""
    strong = (
        12 <= len(password.encode("utf-8")) <= 72
        and password == password.strip()
        and re.search(r"[a-z]", password)
        and re.search(r"[A-Z]", password)
        and re.search(r"\d", password)
        and re.search(r"[^A-Za-z0-9]", password)
    )
    if not strong:
        raise HTTPException(
            status_code=400,
            detail="密码须为12至72字节，并包含大小写字母、数字和符号",
        )


def _uid(sub: str) -> int:
    try:
        return int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="无效的登录态")


async def _require_admin(db: AsyncSession, sub: str) -> User:
    uid = _uid(sub)
    user = await db.get(User, uid)
    if not user or user.role != "admin" or not user.is_active:
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    return user


class ChangeAccountRequest(BaseModel):
    current_password: str
    new_username: Optional[str] = None
    new_password: Optional[str] = None


@router.post("/account")
async def change_account(
    body: ChangeAccountRequest,
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """管理员验证原密码后修改自己的登录账号和/或密码。"""
    admin = await _require_admin(db, sub)
    if not admin.password_hash or not verify_password(body.current_password, admin.password_hash):
        # 401 会被小程序当作过期登录态清除；这里属于表单校验失败。
        raise HTTPException(status_code=400, detail="原密码错误")
    username_changed = body.new_username is not None and body.new_username != admin.username
    password_changed = body.new_password is not None
    if not username_changed and not password_changed:
        raise HTTPException(status_code=400, detail="请填写新的账号或密码")

    if username_changed:
        new_username = body.new_username
        if not re.fullmatch(r"[A-Za-z0-9_]{3,64}", new_username):
            raise HTTPException(status_code=400, detail="账号须为3至64位英文字母、数字或下划线")
        taken = await db.scalar(select(User.id).where(User.username == new_username, User.id != admin.id))
        if taken is not None:
            raise HTTPException(status_code=409, detail="账号已被使用")
        admin.username = new_username

    if password_changed:
        new_password = body.new_password
        _validate_managed_password(new_password)
        if verify_password(new_password, admin.password_hash):
            raise HTTPException(status_code=400, detail="新密码不能与原密码相同")
        admin.password_hash = hash_password(new_password)

    admin.token_version += 1
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="账号已被使用") from exc
    return {"message": "账号信息修改成功", "username": admin.username}


# ────────────────────────────────────────────────────────────────────
# 仪表盘统计
# ────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def stats(
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """仪表盘统计"""
    await _require_admin(db, sub)

    # 患者总数
    pat_stmt = select(func.count(User.id)).where(User.role == "patient")
    pat_res = await db.execute(pat_stmt)
    total_patients = pat_res.scalar() or 0

    # 医生总数
    doc_stmt = select(func.count(User.id)).where(User.role == "doctor")
    doc_res = await db.execute(doc_stmt)
    total_doctors = doc_res.scalar() or 0

    # 活跃分配数
    a_stmt = select(func.count(ConsultAssignment.id)).where(ConsultAssignment.status == "active")
    a_res = await db.execute(a_stmt)
    active_assignments = a_res.scalar() or 0

    # 总聊天消息数
    m_stmt = select(func.count(Consultation.id))
    m_res = await db.execute(m_stmt)
    total_messages = m_res.scalar() or 0

    return {
        "total_patients": total_patients,
        "total_doctors": total_doctors,
        "active_assignments": active_assignments,
        "total_messages": total_messages,
    }


# ────────────────────────────────────────────────────────────────────
# 医生账号管理
# ────────────────────────────────────────────────────────────────────

class CreateDoctorRequest(BaseModel):
    username: str
    password: str
    real_name: str
    nickname: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
    intro: Optional[str] = None
    is_available: bool = True


class UpdateDoctorRequest(BaseModel):
    real_name: Optional[str] = None
    nickname: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
    intro: Optional[str] = None
    is_available: Optional[bool] = None
    is_active: Optional[bool] = None
    new_password: Optional[str] = None


def _doctor_to_dict(d: User) -> dict:
    return {
        "id": d.id,
        "username": d.username,
        "real_name": d.real_name,
        "nickname": d.nickname,
        "department": d.department,
        "title": d.title,
        "intro": d.intro,
        "is_available": d.is_available,
        "is_active": d.is_active,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.get("/doctors")
async def list_doctors(
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
    keyword: Optional[str] = None,
) -> dict:
    """列出所有医生账号（管理员）"""
    await _require_admin(db, sub)
    stmt = select(User).where(User.role == "doctor")
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                User.username.like(kw),
                User.real_name.like(kw),
                User.nickname.like(kw),
                User.department.like(kw),
            )
        )
    stmt = stmt.order_by(desc(User.id))
    res = await db.execute(stmt)
    doctors = res.scalars().all()
    return {"doctors": [_doctor_to_dict(d) for d in doctors]}


@router.post("/doctors")
async def create_doctor(
    body: CreateDoctorRequest,
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """管理员创建医生账号"""
    await _require_admin(db, sub)

    if not re.fullmatch(r"[A-Za-z0-9_]{3,64}", body.username):
        raise HTTPException(status_code=400, detail="账号须为3至64位英文字母、数字或下划线")
    _validate_managed_password(body.password)

    # 校验用户名重复
    stmt = select(User).where(User.username == body.username)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    doctor = User(
        role="doctor",
        username=body.username,
        password_hash=hash_password(body.password),
        real_name=body.real_name,
        nickname=body.nickname or body.real_name,
        department=body.department,
        title=body.title,
        intro=body.intro,
        is_available=body.is_available,
        is_active=True,
    )
    db.add(doctor)
    await db.commit()
    await db.refresh(doctor)
    return _doctor_to_dict(doctor)


@router.put("/doctors/{doctor_id}")
async def update_doctor(
    doctor_id: int,
    body: UpdateDoctorRequest,
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """管理员修改医生账号"""
    await _require_admin(db, sub)

    doctor = await db.get(User, doctor_id)
    if not doctor or doctor.role != "doctor":
        raise HTTPException(status_code=404, detail="医生不存在")

    for field in ["real_name", "nickname", "department", "title", "intro", "is_available", "is_active"]:
        val = getattr(body, field)
        if val is not None:
            setattr(doctor, field, val)
    if body.new_password:
        _validate_managed_password(body.new_password)
        doctor.password_hash = hash_password(body.new_password)
        doctor.token_version += 1

    await db.commit()
    await db.refresh(doctor)
    return _doctor_to_dict(doctor)


@router.delete("/doctors/{doctor_id}")
async def delete_doctor(
    doctor_id: int,
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """管理员删除医生账号（软删除：禁用）"""
    await _require_admin(db, sub)
    doctor = await db.get(User, doctor_id)
    if not doctor or doctor.role != "doctor":
        raise HTTPException(status_code=404, detail="医生不存在")
    doctor.is_active = False
    await db.commit()
    return {"ok": True}


# ────────────────────────────────────────────────────────────────────
# 患者管理
# ────────────────────────────────────────────────────────────────────

def _patient_to_dict(p: User) -> dict:
    return {
        "id": p.id,
        "phone": p.phone,
        "nickname": p.nickname,
        "real_name": p.real_name,
        "avatar": signed_media_url(p.avatar),
        "age": p.age,
        "sex": p.sex,
        "height_cm": p.height_cm,
        "weight_kg": p.weight_kg,
        "health_notes": p.health_notes,
        "is_vip": p.is_vip,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("/patients")
async def list_patients(
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
    keyword: Optional[str] = None,
) -> dict:
    """查看所有患者"""
    await _require_admin(db, sub)
    stmt = select(User).where(User.role == "patient")
    if keyword:
        kw = f"%{keyword}%"
        try:
            kid = int(keyword)
            stmt = stmt.where(
                or_(
                    User.id == kid,
                    User.phone.like(kw),
                    User.real_name.like(kw),
                    User.nickname.like(kw),
                )
            )
        except ValueError:
            stmt = stmt.where(
                or_(
                    User.phone.like(kw),
                    User.real_name.like(kw),
                    User.nickname.like(kw),
                )
            )
    stmt = stmt.order_by(desc(User.id)).limit(500)
    res = await db.execute(stmt)
    patients = res.scalars().all()
    return {"patients": [_patient_to_dict(p) for p in patients]}


# ────────────────────────────────────────────────────────────────────
# 医患分配管理
# ────────────────────────────────────────────────────────────────────

class AssignRequest(BaseModel):
    patient_id: int
    doctor_id: int


@router.post("/assignments")
async def create_assignment(
    body: AssignRequest,
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """管理员手动分配医生给患者"""
    await _require_admin(db, sub)

    patient = await db.get(User, body.patient_id)
    doctor = await db.get(User, body.doctor_id)
    if not patient or patient.role != "patient":
        raise HTTPException(status_code=404, detail="患者不存在")
    if not doctor or doctor.role != "doctor":
        raise HTTPException(status_code=404, detail="医生不存在")

    from app.services.appointment_service import lock_patient, assign
    from app.models.appointment import Appointment
    await lock_patient(db, body.patient_id)
    appointment = (await db.execute(select(Appointment).where(Appointment.patient_id == body.patient_id))).scalar_one_or_none()
    if appointment is None:
        appointment = Appointment(patient_id=body.patient_id, status='waiting')
        db.add(appointment)
    await assign(db, appointment, body.doctor_id)
    await db.commit()
    return {"assignment_id": appointment.assignment_id}


@router.get("/assignments")
async def list_assignments(
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """管理员查看所有医患分配"""
    await _require_admin(db, sub)
    stmt = (
        select(ConsultAssignment, User, User)
        .join(User, User.id == ConsultAssignment.patient_id)
        .order_by(desc(ConsultAssignment.last_message_at))
    )
    res = await db.execute(stmt)
    rows = res.all()

    # 获取所有医生映射
    doc_ids = {a.doctor_id for a, _, _ in rows}
    doc_map = {}
    if doc_ids:
        d_stmt = select(User).where(User.id.in_(doc_ids))
        d_res = await db.execute(d_stmt)
        for d in d_res.scalars().all():
            doc_map[d.id] = d

    items = []
    for a, patient, _ in rows:
        doc = doc_map.get(a.doctor_id)
        items.append({
            "assignment_id": a.id,
            "patient_id": patient.id,
            "patient_name": patient.real_name or patient.nickname or f"患者{patient.id}",
            "doctor_id": a.doctor_id,
            "doctor_name": (doc.real_name or doc.nickname) if doc else f"医生{a.doctor_id}",
            "department": doc.department if doc else None,
            "status": a.status,
            "last_message_at": a.last_message_at.isoformat() if a.last_message_at else None,
            "last_message_preview": a.last_message_preview,
        })
    return {"assignments": items}


# ────────────────────────────────────────────────────────────────────
# 聊天记录查看
# ────────────────────────────────────────────────────────────────────

@router.get("/chats")
async def list_chats(
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
    patient_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    limit: int = 100,
) -> dict:
    """管理员查看聊天记录"""
    await _require_admin(db, sub)

    stmt = select(Consultation)
    if patient_id is not None:
        stmt = stmt.where(Consultation.patient_id == patient_id)
    if doctor_id is not None:
        stmt = stmt.where(Consultation.doctor_id == doctor_id)
    stmt = stmt.order_by(desc(Consultation.id)).limit(limit)
    res = await db.execute(stmt)
    msgs = res.scalars().all()

    return {
        "messages": [
            {
                "id": m.id,
                "assignment_id": m.assignment_id,
                "patient_id": m.patient_id,
                "doctor_id": m.doctor_id,
                "sender_role": m.sender_role,
                "sender_id": m.sender_id,
                "msg_type": m.msg_type,
                "content": m.content,
                "image_url": signed_media_url(m.image_url),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ]
    }
