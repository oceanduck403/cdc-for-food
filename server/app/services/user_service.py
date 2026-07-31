"""用户档案与配额"""
from datetime import date
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.services.nutrition_service import compute_tdee


async def ensure_user(db: AsyncSession, openid: str, nickname: Optional[str] = None, avatar: Optional[str] = None) -> User:
    stmt = select(User).where(User.openid == openid)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if user:
        if nickname and user.nickname != nickname:
            user.nickname = nickname
        if avatar and user.avatar != avatar:
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
    mapping = {
        "nickname": "nickname",
        "avatar": "avatar",
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
    # 这里简单返回 0；真实实现可基于 Redis 计数器
    return {"used": 0, "limit": settings.daily_analysis_limit_per_user}


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
        "nickname": user.nickname,
        "avatar": user.avatar,
        "age": user.age,
        "sex": user.sex,
        "heightCm": user.height_cm,
        "weightKg": user.weight_kg,
        "activityLevel": user.activity_level,
        "healthNotes": user.health_notes,
        "tdee": tdee,
    }