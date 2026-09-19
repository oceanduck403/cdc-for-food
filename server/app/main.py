"""FastAPI 应用对象与中间件"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import create_api_router
from app.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.db.session import SessionLocal, init_db
from app.db.survey_defaults import ensure_public_survey_templates
from app.services.media_service import ensure_media_directories


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_dir = Path(settings.app_log_dir).expanduser().resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    setup_logging()
    Path("data").mkdir(exist_ok=True)
    ensure_media_directories()
    if settings.app_env != "production":
        await init_db()
    async with SessionLocal() as db:
        await ensure_public_survey_templates(db)
    yield


def create_app(enable_clinical_services: bool | None = None) -> FastAPI:
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

    app.include_router(
        create_api_router(enable_clinical_services),
        prefix="/api/v1",
    )

    static_dir = Path("app/static")
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
