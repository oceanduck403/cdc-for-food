"""日志配置（loguru）"""
import sys
from loguru import logger

from app.config import settings


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
    )
    logger.add(
        "logs/app.log",
        rotation="20 MB",
        retention="30 days",
        enqueue=True,
        level=settings.log_level,
        encoding="utf-8",
    )


__all__ = ["logger", "setup_logging"]