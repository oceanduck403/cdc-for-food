"""FastAPI 应用对象与中间件"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.db.session import SessionLocal, init_db
from app.db.survey_defaults import ensure_registration_template


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    Path("logs").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)
    if settings.app_env != "production":
        await init_db()
    async with SessionLocal() as db:
        await ensure_registration_template(db)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="营养健康 AI 小助手 API",
        version="0.1.0",
        description="为成都市疾控中心「营养与食品安全 AI 小助手」微信小程序提供后端服务",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(api_router, prefix="/api/v1")

    static_dir = Path("app/static")
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # 上传的图片（聊天用）
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
