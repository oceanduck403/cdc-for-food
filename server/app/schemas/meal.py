"""膳食 schemas"""
from typing import List, Optional
from pydantic import BaseModel


class MealItemOut(BaseModel):
    name: str
    grams: float
    kcal: float
    protein: float
    fat: float
    carbs: float
    sodium: float
    confidence: float = 0.0


class MealAnalysisOut(BaseModel):
    mealId: Optional[int] = None
    items: List[MealItemOut]
    totalKcal: float
    totalProtein: float
    totalFat: float
    totalCarbs: float
    totalSodium: float


class StructureItem(BaseModel):
    name: str
    percent: float


class MealReportOut(BaseModel):
    mealId: Optional[int] = None
    totalKcal: float
    protein: float
    fat: float
    carbs: float
    sodium: float
    structure: List[StructureItem]
    advice: List[str]