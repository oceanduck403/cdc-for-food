"""聊天 API：自动分配医生、消息收发、会诊邀请"""
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import settings
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
from app.services.media_service import (
    MediaStorageError,
    delete_managed_media,
    read_normalized_image,
    signed_media_url,
    store_chat_image,
)
from app.services.wechat_content_security import (
    ContentSecurityRejected,
    ContentSecurityUnavailable,
    check_uploaded_image,
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


def _require_assignment_access(
    user: User,
    assignment: ConsultAssignment,
    *,
    require_active: bool = False,
) -> None:
    """Allow only the patient or primary doctor bound to this conversation."""
    allowed = (
        (user.role == "patient" and assignment.patient_id == user.id)
        or (user.role == "doctor" and assignment.doctor_id == user.id)
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="无权访问该聊天会话")
    if require_active and assignment.status != "active":
        raise HTTPException(status_code=409, detail="会话已结束或已改派，请刷新预约状态")


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
            "avatar": signed_media_url(doctor.avatar),
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

    _require_assignment_access(user, assignment, require_active=True)
    if body.msg_type != "text" or body.image_url:
        raise HTTPException(status_code=400, detail="图片消息必须通过图片上传接口发送")
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    if len(content) > 4000:
        raise HTTPException(status_code=400, detail="单条消息不能超过 4000 字")

    # 患者首次聊天时确保 first_chat_at 写入（auto_assign 已处理）
    msg = await send_message(
        db,
        assignment_id=body.assignment_id,
        sender_role=user.role,
        sender_id=uid,
        content=content,
        msg_type="text",
        image_url=None,
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

    _require_assignment_access(user, assignment)

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
                "image_url": signed_media_url(m.image_url),
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
    assignment = await get_assignment(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="聊天会话不存在")
    _require_assignment_access(user, assignment)
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
            "avatar": signed_media_url(patient.avatar),
        },
    }


# ────────────────────────────────────────────────────────────────────
# 图片上传并发送（聊天图片）
# ────────────────────────────────────────────────────────────────────

@router.post("/upload-image")
async def upload_image(
    assignment_id: int = Form(...),
    file: UploadFile = File(...),
    sub: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """校验图片和会话权限后，原子式创建一条图片消息。"""
    uid = _uid(sub)
    user = await _get_user(db, uid)
    assignment = await get_assignment(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="聊天会话不存在")
    _require_assignment_access(user, assignment, require_active=True)

    normalized = await read_normalized_image(
        file,
        max_bytes=settings.chat_image_max_bytes,
    )
    try:
        await check_uploaded_image(normalized)
    except ContentSecurityRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ContentSecurityUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        stored = await asyncio.to_thread(store_chat_image, normalized, assignment_id)
    except MediaStorageError:
        logger.exception(
            "chat image storage failed: assignment_id={assignment_id}",
            assignment_id=assignment_id,
        )
        raise HTTPException(status_code=503, detail="图片暂时无法保存，请稍后重试") from None
    try:
        message = await send_message(
            db,
            assignment_id=assignment_id,
            sender_role=user.role,
            sender_id=uid,
            content="[图片]",
            msg_type="image",
            image_url=stored.reference,
        )
    except Exception:
        try:
            await asyncio.to_thread(delete_managed_media, stored.reference)
        except (OSError, MediaStorageError):
            logger.exception(
                "failed to clean uncommitted chat image: assignment_id={assignment_id}",
                assignment_id=assignment_id,
            )
        raise
    return {
        "id": message.id,
        "url": signed_media_url(stored.reference),
        "size": stored.size,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


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
