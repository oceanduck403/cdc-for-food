"""支付服务：订单处理、配额更新"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.user import User
from app.config import settings


# 套餐配置
PACKAGES = {
    1: {"name": "月度会员", "days": 30, "count": 600},
    2: {"name": "季度会员", "days": 90, "count": 1800},
    3: {"name": "年度会员", "days": 365, "count": 7300},
}


async def process_payment_success(
    db: AsyncSession,
    user_id: int,
    package_id: int,
    order_id: str,
) -> dict:
    """支付成功后处理：更新用户配额和VIP状态"""
    user = await db.get(User, user_id)
    if not user:
        logger.error(f"支付回调：用户不存在 user_id={user_id}")
        return {"success": False, "error": "用户不存在"}

    pkg = PACKAGES.get(package_id)
    if not pkg:
        logger.error(f"支付回调：无效套餐 package_id={package_id}")
        return {"success": False, "error": "无效套餐"}

    # 计算VIP有效期
    today = date.today()
    if user.is_vip and user.vip_expire_at and user.vip_expire_at >= today:
        # 顺延VIP有效期
        from datetime import timedelta
        new_expire = user.vip_expire_at + timedelta(days=pkg["days"])
    else:
        new_expire = today + timedelta(days=pkg["days"])

    # 更新用户状态
    user.is_vip = True
    user.vip_expire_at = new_expire
    user.purchased_analysis_count += pkg["count"]
    await db.commit()

    logger.info(
        f"支付成功：user_id={user_id}, package={pkg['name']}, "
        f"order_id={order_id}, expire_at={new_expire}"
    )

    return {
        "success": True,
        "is_vip": True,
        "vip_expire_at": new_expire.isoformat(),
        "remaining_count": user.purchased_analysis_count,
    }


async def check_user_quota(db: AsyncSession, user_id: int) -> dict:
    """检查用户配额"""
    user = await db.get(User, user_id)
    if not user:
        return {"can_use": True, "remaining": 999, "limit": 999}

    today = date.today()

    # VIP用户且在有效期内
    if user.is_vip and user.vip_expire_at and user.vip_expire_at >= today:
        remaining = user.purchased_analysis_count
        return {
            "can_use": remaining > 0,
            "remaining": remaining,
            "limit": user.purchased_analysis_count,
            "is_vip": True,
            "expire_at": user.vip_expire_at.isoformat(),
        }

    # 免费额度（每日限制）
    from datetime import datetime, timedelta
    today_start = datetime.combine(today, datetime.min.time())

    # 这里可以基于 Redis 或数据库记录实际使用次数
    # 简化实现：基于上次访问时间判断
    remaining = max(0, settings.daily_analysis_limit_per_user)
    if user.last_active_on == today:
        remaining = 0  # 今日已用完

    return {
        "can_use": remaining > 0,
        "remaining": remaining,
        "limit": settings.daily_analysis_limit_per_user,
        "is_vip": False,
        "expire_at": None,
    }


async def consume_quota(db: AsyncSession, user_id: int) -> bool:
    """消耗配额，返回是否成功"""
    user = await db.get(User, user_id)
    if not user:
        return False

    today = date.today()

    # VIP用户优先消耗购买次数
    if user.is_vip and user.vip_expire_at and user.vip_expire_at >= today:
        if user.purchased_analysis_count > 0:
            user.purchased_analysis_count -= 1
            user.total_analysis_count += 1
            user.last_active_on = today
            await db.commit()
            return True
        return False

    # 免费用户每日限制
    if user.last_active_on == today:
        return False  # 今日已用完

    user.last_active_on = today
    user.total_analysis_count += 1
    await db.commit()
    return True
