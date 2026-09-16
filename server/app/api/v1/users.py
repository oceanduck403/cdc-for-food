"""用户：档案、每日配额"""
import asyncio

from fastapi import APIRouter, Depends, File, UploadFile
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_id, get_db
from app.config import settings
from app.core.errors import BusinessError
from app.models.user import User
from app.schemas.user import AccountDeletionRequest
from app.services.account_deletion_service import delete_patient_account
from app.services.media_service import (
    MediaStorageError,
    delete_chat_assignment_media,
    delete_managed_media,
    read_normalized_image,
    store_avatar,
)
from app.services.user_service import get_profile, update_profile, get_daily_quota
from app.services.wechat_content_security import (
    ContentSecurityRejected,
    ContentSecurityUnavailable,
    check_uploaded_image,
)

router = APIRouter()


@router.get("/me")
async def me(user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)) -> dict:
    return await get_profile(db, user_id)


@router.put("/me")
async def update_me(
    payload: dict,
    user_id: str = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    profile = await update_profile(db, user_id, payload)
    if not profile:
        raise BusinessError("USER_NOT_FOUND", "用户不存在", status_code=404)
    return profile


@router.post("/me/avatar")
async def upload_my_avatar(
    file: UploadFile = File(...),
    user_id: str = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """上传患者头像：真实解码、裁方并重编码以清除元数据。"""
    try:
        user = await db.get(User, int(user_id))
    except (TypeError, ValueError):
        user = None
    if not user:
        raise BusinessError("USER_NOT_FOUND", "用户不存在", status_code=404)
    if user.role != "patient" or not user.is_active:
        raise BusinessError("FORBIDDEN", "当前账号不能修改头像", status_code=403)

    # wx.uploadFile may label camera files as octet-stream.  The decoder, pixel
    # limits and full re-encoding below are the source of truth.
    normalized = await read_normalized_image(
        file,
        max_bytes=settings.avatar_max_bytes,
        crop_square=True,
    )
    try:
        await check_uploaded_image(normalized)
    except ContentSecurityRejected as exc:
        raise BusinessError("CONTENT_REJECTED", str(exc), status_code=400) from exc
    except ContentSecurityUnavailable as exc:
        raise BusinessError(
            "CONTENT_SECURITY_UNAVAILABLE", str(exc), status_code=503
        ) from exc
    try:
        stored = await asyncio.to_thread(store_avatar, normalized)
    except MediaStorageError:
        logger.exception("avatar storage failed")
        raise BusinessError(
            "MEDIA_STORAGE_UNAVAILABLE",
            "头像暂时无法保存，请稍后重试",
            status_code=503,
        ) from None
    old_avatar = user.avatar
    try:
        user.avatar = stored.reference
        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        try:
            await asyncio.to_thread(delete_managed_media, stored.reference)
        except (OSError, MediaStorageError):
            logger.exception("failed to clean uncommitted avatar media")
        raise

    try:
        await asyncio.to_thread(delete_managed_media, old_avatar)
    except (OSError, MediaStorageError):
        # The new avatar is already committed; stale-object cleanup is best effort.
        logger.exception("failed to clean replaced avatar media")
    return await get_profile(db, str(user.id))


@router.delete("/me")
async def delete_me(
    body: AccountDeletionRequest,
    user_id: str = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Permanently delete the signed-in patient's account and private avatar."""
    deleted = await delete_patient_account(db, user_id)
    try:
        await asyncio.to_thread(delete_managed_media, deleted.avatar)
    except (OSError, MediaStorageError):
        # Database deletion has committed; stale-object cleanup can be retried later.
        logger.exception("failed to clean deleted account avatar media")
    for assignment_id in deleted.chat_assignment_ids:
        try:
            await asyncio.to_thread(delete_chat_assignment_media, assignment_id)
        except (OSError, MediaStorageError):
            # Database deletion has committed; stale-object cleanup can be retried later.
            logger.exception(
                "failed to clean deleted account chat media: assignment_id={assignment_id}",
                assignment_id=assignment_id,
            )
    return {"deleted": True}


@router.get("/me/quota")
async def quota(user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)) -> dict:
    return await get_daily_quota(db, user_id)
