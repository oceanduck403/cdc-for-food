"""用户：档案、每日配额"""
from io import BytesIO
import os
from pathlib import Path
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_id, get_db
from app.core.errors import BusinessError
from app.models.user import User
from app.services.user_service import get_profile, update_profile, get_daily_quota

router = APIRouter()
AVATAR_DIR = Path("uploads/avatars")
MAX_AVATAR_BYTES = 5 * 1024 * 1024
MAX_AVATAR_PIXELS = 12 * 1024 * 1024


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

    # wx.uploadFile may label a camera or album image as application/octet-stream.
    # Validate the decoded image below rather than trusting the multipart MIME type.
    try:
        raw = await file.read(MAX_AVATAR_BYTES + 1)
    finally:
        await file.close()
    if not raw or len(raw) > MAX_AVATAR_BYTES:
        raise BusinessError("INVALID_AVATAR", "头像图片不能超过 5 MB")

    try:
        with Image.open(BytesIO(raw)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"} or getattr(source, "is_animated", False):
                raise BusinessError("INVALID_AVATAR", "图片格式不受支持")
            width, height = source.size
            if not width or not height or width * height > MAX_AVATAR_PIXELS:
                raise BusinessError("INVALID_AVATAR", "图片尺寸过大，请换一张")
            source.load()
            upright = ImageOps.exif_transpose(source)
            cropped = ImageOps.fit(upright, (512, 512), method=Image.Resampling.LANCZOS)
            output = Image.new("RGB", cropped.size, "#ffffff")
            if cropped.mode in {"RGBA", "LA"} or (cropped.mode == "P" and "transparency" in cropped.info):
                rgba = cropped.convert("RGBA")
                output.paste(rgba, mask=rgba.getchannel("A"))
            else:
                output.paste(cropped.convert("RGB"))
    except BusinessError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise BusinessError("INVALID_AVATAR", "图片无法识别，请重新选择") from None

    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{user.id}-{uuid4().hex}.jpg"
    target = AVATAR_DIR / filename
    temporary = AVATAR_DIR / f"{filename}.tmp"
    old_avatar = user.avatar
    try:
        output.save(temporary, format="JPEG", quality=84, optimize=True)
        os.replace(temporary, target)
        user.avatar = f"/uploads/avatars/{filename}"
        await db.commit()
        await db.refresh(user)
    except Exception:
        temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        await db.rollback()
        raise

    if old_avatar:
        old_name = old_avatar.removeprefix("/uploads/avatars/")
        if re.fullmatch(rf"{user.id}-[0-9a-f]{{32}}\.jpg", old_name) and old_avatar.startswith("/uploads/avatars/"):
            try:
                (AVATAR_DIR / old_name).unlink(missing_ok=True)
            except OSError:
                # The new avatar is already committed; stale-file cleanup is best effort.
                pass
    return await get_profile(db, str(user.id))


@router.get("/me/quota")
async def quota(user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)) -> dict:
    return await get_daily_quota(db, user_id)
