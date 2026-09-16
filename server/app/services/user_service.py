"""用户档案与配额"""
from datetime import datetime, timezone
import re
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import BusinessError
from app.models.ai_usage import AiUsageEvent
from app.models.user import User
from app.services.ai_quota import current_quota_day_start
from app.services.media_service import signed_media_url
from app.services.nutrition_service import compute_tdee
from app.services.wechat_content_security import (
    ContentSecurityRejected,
    ContentSecurityUnavailable,
    check_public_text,
)


async def ensure_user(db: AsyncSession, openid: str) -> User:
    stmt = select(User).where(User.openid == openid)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if user:
        return user
    # 微信登录只建立平台身份。昵称和头像必须分别经过公开文本检查及
    # 受控图片上传，不接受登录请求携带的客户端资料。
    user = User(openid=openid)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_profile(db: AsyncSession, user_id: str) -> dict:
    try:
        uid = int(user_id)
    except ValueError:
        return {"id": user_id, "nickname": "未登录"}

    user = await db.get(User, uid)
    if not user:
        return {"id": uid}
    return _to_profile(user)


async def update_profile(db: AsyncSession, user_id: str, payload: dict) -> Optional[dict]:
    try:
        uid = int(user_id)
    except ValueError:
        return None
    user = await db.get(User, uid)
    if not user:
        return None
    if "nickname" in payload:
        nickname = payload["nickname"]
        if not isinstance(nickname, str):
            raise BusinessError("INVALID_NICKNAME", "请输入昵称")
        nickname = nickname.strip()
        if not 1 <= len(nickname) <= 20 or re.search(r"[\x00-\x1f<>]", nickname):
            raise BusinessError("INVALID_NICKNAME", "昵称需为 1 到 20 个有效字符")
        if user.role == "patient":
            # Nicknames appear next to public article comments and therefore
            # need the same fail-closed review as comment bodies.
            try:
                await check_public_text(nickname, user.openid)
            except ContentSecurityRejected as exc:
                raise BusinessError(
                    "CONTENT_REJECTED", "昵称含有不适合公开展示的内容，请修改后再试", status_code=400
                ) from exc
            except ContentSecurityUnavailable as exc:
                raise BusinessError(
                    "CONTENT_SECURITY_UNAVAILABLE", str(exc), status_code=503
                ) from exc
        payload = {**payload, "nickname": nickname}
    mapping = {
        "nickname": "nickname",
        "age": "age",
        "sex": "sex",
        "heightCm": "height_cm",
        "weightKg": "weight_kg",
        "activityLevel": "activity_level",
        "healthNotes": "health_notes",
    }
    for src, dest in mapping.items():
        if src in payload:
            setattr(user, dest, payload[src])
    await db.commit()
    await db.refresh(user)
    return _to_profile(user)


async def get_daily_quota(db: AsyncSession, user_id: str) -> dict:
    """返回与 AI 成本闸口使用同一事件表、同一天界线的配额。"""
    limit = settings.daily_analysis_limit_per_user
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return {"used": 0, "remaining": limit, "limit": limit, "is_vip": False, "expire_at": None}

    user = await db.get(User, uid)
    if not user:
        return {"used": 0, "remaining": limit, "limit": limit, "is_vip": False, "expire_at": None}

    used = int(
        await db.scalar(
            select(func.count(AiUsageEvent.id)).where(
                AiUsageEvent.user_id == uid,
                AiUsageEvent.created_at
                >= current_quota_day_start(datetime.now(timezone.utc)),
            )
        )
        or 0
    )

    return {
        "used": used,
        "remaining": max(limit - used, 0),
        "limit": limit,
        "is_vip": False,
        "expire_at": None,
    }


async def update_phone(db: AsyncSession, user_id: int, phone: str) -> None:
    """绑定用户手机号"""
    user = await db.get(User, user_id)
    if not user:
        return
    user.phone = phone
    await db.commit()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """根据主键查询用户"""
    return await db.get(User, user_id)


def _to_profile(user: User) -> dict:
    tdee = compute_tdee(
        sex=user.sex,
        weight_kg=user.weight_kg,
        height_cm=user.height_cm,
        age=user.age,
        activity_level=user.activity_level,
    ) if all([user.sex, user.weight_kg, user.height_cm, user.age]) else None
    return {
        "id": user.id,
        "role": user.role,
        "username": user.username,
        "real_name": user.real_name,
        "nickname": user.nickname,
        "avatar": signed_media_url(user.avatar),
        "phone": user.phone,
        "age": user.age,
        "sex": user.sex,
        "heightCm": user.height_cm,
        "weightKg": user.weight_kg,
        "activityLevel": user.activity_level,
        "healthNotes": user.health_notes,
        "department": user.department,
        "title": user.title,
        "intro": user.intro,
        "is_available": user.is_available,
        "is_active": user.is_active,
        "tdee": tdee,
    }
