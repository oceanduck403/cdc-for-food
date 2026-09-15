"""用户档案与配额"""
from datetime import date
import re
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import BusinessError
from app.models.user import User
from app.services.nutrition_service import compute_tdee


async def ensure_user(db: AsyncSession, openid: str, nickname: Optional[str] = None, avatar: Optional[str] = None) -> User:
    stmt = select(User).where(User.openid == openid)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if user:
        # 用户主动编辑后的资料不能在下次微信登录时被旧授权资料覆盖。
        if nickname and not user.nickname:
            user.nickname = nickname
        if avatar and not user.avatar:
            user.avatar = avatar
        await db.commit()
        return user
    user = User(openid=openid, nickname=nickname, avatar=avatar)
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
    """返回当前用户今日已使用次数（成本闸口）"""
    try:
        uid = int(user_id)
    except ValueError:
        return {"used": 0, "remaining": 20, "limit": 20, "is_vip": False}

    user = await db.get(User, uid)
    if not user:
        return {"used": 0, "remaining": 20, "limit": 20, "is_vip": False}

    today = date.today()

    # VIP用户
    if user.is_vip and user.vip_expire_at and user.vip_expire_at >= today:
        return {
            "used": 0,
            "remaining": user.purchased_analysis_count,
            "limit": user.purchased_analysis_count,
            "is_vip": True,
            "expire_at": user.vip_expire_at.isoformat(),
        }

    # 免费用户：每日限制
    if user.last_active_on == today:
        return {
            "used": settings.daily_analysis_limit_per_user,
            "remaining": 0,
            "limit": settings.daily_analysis_limit_per_user,
            "is_vip": False,
            "expire_at": None,
        }

    return {
        "used": 0,
        "remaining": settings.daily_analysis_limit_per_user,
        "limit": settings.daily_analysis_limit_per_user,
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
        "avatar": user.avatar,
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
