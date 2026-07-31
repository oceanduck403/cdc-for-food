"""v1 路由聚合"""
from fastapi import APIRouter

from app.api.v1 import admin, auth, gis, knowledge, meals, reports, users, vision

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(meals.router, prefix="/meals", tags=["meals"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(gis.router, prefix="/gis", tags=["gis"])
api_router.include_router(vision.router, prefix="/vision", tags=["vision"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])