"""Small Redis-backed cost and burst guard for AI endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger
from redis.asyncio import from_url

from app.config import settings
from app.core.errors import BusinessError


async def reserve(user_id: str) -> tuple[str, str] | None:
    """Reserve one daily call and one burst slot.

    Development remains usable without Redis. Production fails closed so a
    missing limiter cannot create an unbounded provider bill.
    """
    now = datetime.now()
    daily_key = f"ai:day:{user_id}:{now:%Y%m%d}"
    minute_key = f"ai:minute:{user_id}:{now:%Y%m%d%H%M}"
    client = from_url(settings.redis_url, decode_responses=True)
    try:
        pipe = client.pipeline(transaction=True)
        pipe.incr(daily_key)
        pipe.expire(daily_key, int((datetime.combine(now.date() + timedelta(days=1), datetime.min.time()) - now).total_seconds()) + 60)
        pipe.incr(minute_key)
        pipe.expire(minute_key, 120)
        daily_count, _, minute_count, _ = await pipe.execute()
        if int(minute_count) > 6:
            await client.decr(daily_key)
            raise BusinessError("AI_TOO_MANY_REQUESTS", "操作太频繁，请稍后再试", status_code=429)
        if int(daily_count) > settings.daily_analysis_limit_per_user:
            await client.decr(daily_key)
            raise BusinessError("AI_DAILY_LIMIT", "今日 AI 使用次数已用完，请明天再试", status_code=429)
        return daily_key, minute_key
    except BusinessError:
        raise
    except Exception as exc:
        logger.warning("AI quota backend unavailable: {}", type(exc).__name__)
        if settings.app_env.lower() == "production":
            raise BusinessError("AI_LIMITER_UNAVAILABLE", "AI 服务暂时不可用，请稍后重试", status_code=503) from exc
        return None
    finally:
        await client.aclose()


async def release(reservation: tuple[str, str] | None) -> None:
    if not reservation:
        return
    client = from_url(settings.redis_url, decode_responses=True)
    try:
        await client.decr(reservation[0])
    except Exception as exc:
        logger.warning("Unable to release AI quota: {}", type(exc).__name__)
    finally:
        await client.aclose()
