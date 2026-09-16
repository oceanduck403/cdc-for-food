"""Authenticated AI endpoints backed by the server-side Qwen gateway."""
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_id, get_db
from app.services import ai_quota, qwen_service
from app.services.meal_service import save_analyzed_meal


router = APIRouter()


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    mode: Literal["health_consult", "diet_guide"] = "health_consult"
    history: list[HistoryItem] = Field(default_factory=list, max_length=12)


class SurveyRequest(BaseModel):
    surveyType: str = Field(default="health", min_length=1, max_length=40)
    answers: dict[str, Any]


class DailySuggestionRequest(BaseModel):
    todayData: dict[str, Any]
    userProfile: dict[str, Any] = Field(default_factory=dict)


class FoodRequest(BaseModel):
    imageBase64: str = Field(min_length=16)


async def _run_with_quota(user_id: str, db: AsyncSession, operation):
    reservation = await ai_quota.reserve(db, user_id)
    try:
        return await operation()
    except Exception:
        await ai_quota.release(db, reservation)
        raise


@router.post("/chat")
async def chat(body: ChatRequest, user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)) -> dict:
    async def operation():
        reply = await qwen_service.chat(
            body.message,
            body.mode,
            [item.model_dump() for item in body.history],
        )
        return {"reply": reply, "generatedByAi": True}
    return await _run_with_quota(user_id, db, operation)


@router.post("/survey-analysis")
async def survey_analysis(body: SurveyRequest, user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)) -> dict:
    async def operation():
        reply = await qwen_service.analyze_survey(body.surveyType, body.answers)
        return {"reply": reply, "surveyType": body.surveyType, "generatedByAi": True}
    return await _run_with_quota(user_id, db, operation)


@router.post("/daily-suggestion")
async def daily_suggestion(body: DailySuggestionRequest, user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)) -> dict:
    async def operation():
        reply = await qwen_service.daily_suggestion(body.todayData, body.userProfile)
        return {"reply": reply, "generatedByAi": True}
    return await _run_with_quota(user_id, db, operation)


@router.post("/food-analysis")
async def food_analysis(body: FoodRequest, user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)) -> dict:
    async def operation():
        foods = await qwen_service.analyze_food(body.imageBase64)
        result = await save_analyzed_meal(db, user_id, foods)
        return {**result, "generatedByAi": True}
    return await _run_with_quota(user_id, db, operation)
