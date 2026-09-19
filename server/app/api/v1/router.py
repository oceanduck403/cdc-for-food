"""v1 路由聚合"""
from fastapi import APIRouter

from app.api.v1 import admin, ai, auth, community, gis, knowledge, meals, media, reports, survey, users
from app.config import settings


def create_api_router(enable_clinical_services: bool | None = None) -> APIRouter:
    """Build the public API, omitting every clinical route unless explicitly enabled."""
    clinical_enabled = (
        settings.enable_clinical_services
        if enable_clinical_services is None
        else enable_clinical_services
    )

    api_router = APIRouter()
    api_router.include_router(community.router, prefix="/community", tags=["community"])
    api_router.include_router(ai.router, prefix="/ai", tags=["AI 科普"])
    api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
    api_router.include_router(users.router, prefix="/users", tags=["users"])
    api_router.include_router(meals.router, prefix="/meals", tags=["meals"])
    api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
    api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
    api_router.include_router(gis.router, prefix="/gis", tags=["gis"])
    api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
    api_router.include_router(media.router, prefix="/media", tags=["media"])
    api_router.include_router(survey.router, prefix="/survey", tags=["问卷管理"])

    if clinical_enabled:
        from app.api.v1 import appointments, chat

        api_router.include_router(
            appointments.router,
            prefix="/appointments",
            tags=["免费预约"],
        )
        api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
        api_router.include_router(
            admin.clinical_router,
            prefix="/admin",
            tags=["admin"],
        )
        api_router.include_router(
            media.clinical_router,
            prefix="/media",
            tags=["media"],
        )

    return api_router
