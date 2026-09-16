"""Database-backed cost and burst guard for AI endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import BusinessError
from app.models.ai_usage import AiUsageEvent
from app.models.user import User


APP_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")


def current_quota_day_start(now: datetime | None = None) -> datetime:
    """Return today's Chengdu midnight as an aware UTC timestamp.

    Cloud containers commonly run in UTC, while the user-facing quota is a
    calendar-day allowance for users in China.  Deriving the boundary in the
    product timezone keeps the limiter and the displayed remaining count in
    sync regardless of the host timezone.
    """
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    local = instant.astimezone(APP_TIMEZONE)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(
        timezone.utc
    )


async def reserve(db: AsyncSession, user_id: str) -> str | None:
    """Atomically reserve one successful-provider slot for this user.

    A user-row lock serializes concurrent quota checks in PostgreSQL. Keeping
    reservations in the primary database means CloudBase needs no separate
    Redis service. Failed provider calls remove the row via ``release``.
    """
    try:
        uid = int(user_id)
    except (TypeError, ValueError) as exc:
        raise BusinessError(
            "INVALID_USER", "登录状态无效，请重新登录", status_code=401
        ) from exc

    now = datetime.now(timezone.utc)
    minute_start = now.replace(second=0, microsecond=0)
    day_start = current_quota_day_start(now)
    retention_start = day_start - timedelta(days=2)
    try:
        user = (
            await db.execute(select(User).where(User.id == uid).with_for_update())
        ).scalar_one_or_none()
        if not user or not user.is_active:
            raise BusinessError(
                "ACCOUNT_UNAVAILABLE", "账号不可用，请重新登录", status_code=401
            )

        await db.execute(
            delete(AiUsageEvent).where(
                AiUsageEvent.user_id == uid,
                AiUsageEvent.created_at < retention_start,
            )
        )
        daily_count = await db.scalar(
            select(func.count(AiUsageEvent.id)).where(
                AiUsageEvent.user_id == uid,
                AiUsageEvent.created_at >= day_start,
            )
        )
        minute_count = await db.scalar(
            select(func.count(AiUsageEvent.id)).where(
                AiUsageEvent.user_id == uid,
                AiUsageEvent.created_at >= minute_start,
            )
        )
        if int(minute_count or 0) >= 6:
            raise BusinessError(
                "AI_TOO_MANY_REQUESTS", "操作太频繁，请稍后再试", status_code=429
            )
        if int(daily_count or 0) >= settings.daily_analysis_limit_per_user:
            raise BusinessError(
                "AI_DAILY_LIMIT", "今日 AI 使用次数已用完，请明天再试", status_code=429
            )

        reservation = AiUsageEvent(user_id=uid, created_at=now)
        db.add(reservation)
        await db.commit()
        return reservation.id
    except BusinessError:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.warning("AI quota database unavailable: {}", type(exc).__name__)
        if settings.app_env.lower() == "production":
            raise BusinessError(
                "AI_LIMITER_UNAVAILABLE", "AI 服务暂时不可用，请稍后重试", status_code=503
            ) from exc
        return None


async def release(db: AsyncSession, reservation: str | None) -> None:
    if not reservation:
        return
    try:
        await db.execute(delete(AiUsageEvent).where(AiUsageEvent.id == reservation))
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.warning("Unable to release AI quota reservation: {}", type(exc).__name__)
