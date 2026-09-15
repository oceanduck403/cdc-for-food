"""聊天 API：自动分配医生、消息收发、会诊邀请"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import get_current_subject
from app.models.chat import ConsultAssignment, Consultation
from app.models.user import User
from app.services.chat_service import (
    auto_assign_doctor,
    create_consult_invite,
    get_assignment,
    get_doctor_patients,
    get_unread_count,
    list_available_doctors,
    list_messages,
    mark_read,
    respond_consult_invite,
    search_doctor_patients,
    send_message,
)

router = APIRouter()


def _uid(sub: str) -> int:
    try:
        return int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="无效的登录态")


async def _get_user(db: AsyncSession, uid: int) -> User:
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用")
    return user


# ────────────────────────────────────────────────────────────────────
# 患者：获取 / 分配我的医生
# ────────────────────────────────────────────────────────────────────

@router.get("/my-doctor")
async def my_doctor(
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取当前患者的医生（如未分配则自动分配）"""
    uid = _uid(sub)
    user = await _get_user(db, uid)
    if user.role != "patient":
        raise HTTPException(status_code=403, detail="仅患者可调用")

    assignment = await auto_assign_doctor(db, uid)
    if not assignment:
        raise HTTPException(status_code=503, detail="暂无可用医生，请稍后再试")

    doctor = await _get_user(db, assignment.doctor_id)
    return {
        "assignment_id": assignment.id,
        "doctor": {
            "id": doctor.id,
            "name": doctor.real_name or doctor.nickname,
            "department": doctor.department,
            "title": doctor.title,
            "intro": doctor.intro,
            "avatar": doctor.avatar,
        },
        "patient": {
            "id": user.id,
            "name": user.real_name or user.nickname,
        },
    }


# ────────────────────────────────────────────────────────────────────
# 患者 / 医生：发送消息
# ────────────────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    assignment_id: int
    content: str
    msg_type: str = "text"  # text/image
    image_url: Optional[str] = None


@router.post("/send")
async def api_send_message(
    body: SendMessageRequest,
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """发送一条聊天消息"""
    uid = _uid(sub)
    user = await _get_user(db, uid)

    assignment = await get_assignment(db, body.assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="聊天会话不存在")

    # 权限校验：必须是该会话的患者或医生
    if user.role == "patient" and assignment.patient_id != uid:
        raise HTTPException(status_code=403, detail="无权发送")
    if user.role == "doctor" and assignment.doctor_id != uid:
        raise HTTPException(status_code=403, detail="无权发送")

    if not user.is_active or user.role not in ('patient', 'doctor'):
        raise HTTPException(status_code=403, detail="无权发送")
    if assignment.status != 'active':
        raise HTTPException(status_code=409, detail="会话已结束或已改派，请刷新预约状态")

    # 患者首次聊天时确保 first_chat_at 写入（auto_assign 已处理）
    msg = await send_message(
        db,
        assignment_id=body.assignment_id,
        sender_role=user.role,
        sender_id=uid,
        content=body.content,
        msg_type=body.msg_type,
        image_url=body.image_url,
    )
    return {"id": msg.id, "created_at": msg.created_at.isoformat() if msg.created_at else None}


# ────────────────────────────────────────────────────────────────────
# 患者 / 医生：拉取聊天记录
# ────────────────────────────────────────────────────────────────────

@router.get("/messages")
async def api_list_messages(
    assignment_id: int,
    limit: int = 50,
    before_id: Optional[int] = None,
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """拉取聊天记录"""
    uid = _uid(sub)
    user = await _get_user(db, uid)

    assignment = await get_assignment(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="聊天会话不存在")

    if user.role == "patient" and assignment.patient_id != uid:
        raise HTTPException(status_code=403, detail="无权访问")
    if user.role == "doctor" and assignment.doctor_id != uid:
        raise HTTPException(status_code=403, detail="无权访问")

    msgs = await list_messages(db, assignment_id, limit=limit, before_id=before_id)
    msgs.reverse()  # 倒序转正序

    return {
        "messages": [
            {
                "id": m.id,
                "sender_role": m.sender_role,
                "sender_id": m.sender_id,
                "msg_type": m.msg_type,
                "content": m.content,
                "image_url": m.image_url,
                "consult_target_doctor_id": m.consult_target_doctor_id,
                "consult_target_doctor_name": m.consult_target_doctor_name,
                "consult_status": m.consult_status,
                "consult_note": m.consult_note,
                "is_read": m.is_read,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ],
        "unread": await get_unread_count(db, assignment_id, user.role),
    }


@router.post("/read")
async def api_mark_read(
    assignment_id: int,
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """标记消息已读"""
    uid = _uid(sub)
    user = await _get_user(db, uid)
    count = await mark_read(db, assignment_id, user.role)
    return {"marked": count}


# ────────────────────────────────────────────────────────────────────
# 医生：患者列表 + 搜索
# ────────────────────────────────────────────────────────────────────

@router.get("/doctor/patients")
async def api_doctor_patients(
    keyword: Optional[str] = None,
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """医生查看自己的患者列表（支持按 ID/姓名/手机号搜索）"""
    uid = _uid(sub)
    user = await _get_user(db, uid)
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail="仅医生可调用")

    if keyword:
        patients = await search_doctor_patients(db, uid, keyword)
    else:
        patients = await get_doctor_patients(db, uid)
    return {"patients": patients}


@router.get("/doctor/patient-detail/{patient_id}")
async def api_patient_detail(
    patient_id: int,
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """医生查看患者详细信息（仅限分配给自己的患者）"""
    uid = _uid(sub)
    user = await _get_user(db, uid)
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail="仅医生可调用")

    # 校验该患者是否分配给了此医生
    stmt = select(ConsultAssignment).where(
        ConsultAssignment.doctor_id == uid,
        ConsultAssignment.patient_id == patient_id,
        ConsultAssignment.status == "active",
    ).order_by(ConsultAssignment.id.desc()).limit(1)
    res = await db.execute(stmt)
    assignment = res.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=403, detail="该患者未分配给您")

    patient = await _get_user(db, patient_id)
    return {
        "assignment_id": assignment.id,
        "patient": {
            "id": patient.id,
            "name": patient.real_name or patient.nickname,
            "phone": patient.phone,
            "age": patient.age,
            "sex": patient.sex,
            "height_cm": patient.height_cm,
            "weight_kg": patient.weight_kg,
            "health_notes": patient.health_notes,
            "activity_level": patient.activity_level,
            "avatar": patient.avatar,
        },
    }


# ────────────────────────────────────────────────────────────────────
# 图片上传（聊天图片）
# ────────────────────────────────────────────────────────────────────

import os
import uuid as _uuid
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
from app.core.security import get_current_subject

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    sub: str = Depends(get_current_subject),
):
    """上传一张图片，返回可访问的 URL"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件")

    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    name = f"{_uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_DIR, name)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片不能超过 10MB")
    with open(save_path, "wb") as f:
        f.write(content)
    # 通过 /uploads/{name} 暴露
    return {"url": f"/uploads/{name}", "filename": name, "size": len(content)}


# ────────────────────────────────────────────────────────────────────
# 会诊邀请
# ────────────────────────────────────────────────────────────────────

class ConsultInviteRequest(BaseModel):
    assignment_id: int
    target_doctor_id: int
    note: str = ""


@router.post("/consult/invite")
async def api_consult_invite(
    body: ConsultInviteRequest,
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """医生邀请另一医生进行会诊"""
    uid = _uid(sub)
    user = await _get_user(db, uid)
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail="仅医生可邀请会诊")

    assignment = await get_assignment(db, body.assignment_id)
    if not assignment or assignment.doctor_id != uid:
        raise HTTPException(status_code=403, detail="无权操作该会话")

    msg = await create_consult_invite(
        db, body.assignment_id, uid, body.target_doctor_id, body.note
    )
    if not msg:
        raise HTTPException(status_code=400, detail="邀请失败，目标医生不存在")
    return {"id": msg.id}


class ConsultRespondRequest(BaseModel):
    message_id: int
    accept: bool


@router.post("/consult/respond")
async def api_consult_respond(
    body: ConsultRespondRequest,
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """被邀请医生接受或拒绝会诊"""
    uid = _uid(sub)
    msg = await db.get(Consultation, body.message_id)
    if not msg or msg.msg_type != "consult_invite":
        raise HTTPException(status_code=404, detail="邀请消息不存在")
    if msg.consult_target_doctor_id != uid:
        raise HTTPException(status_code=403, detail="这条邀请不是发给您的")

    updated = await respond_consult_invite(db, body.message_id, body.accept)
    return {
        "id": updated.id,
        "consult_status": updated.consult_status,
        "content": updated.content,
    }


@router.get("/consult/available-doctors")
async def api_available_doctors(
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取可供会诊邀请的医生列表"""
    uid = _uid(sub)
    user = await _get_user(db, uid)
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail="仅医生可调用")
    doctors = await list_available_doctors(db, exclude_id=uid)
    return {"doctors": doctors}
