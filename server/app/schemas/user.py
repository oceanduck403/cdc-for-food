"""用户档案 schemas"""
from typing import Optional
from pydantic import BaseModel, Field


class UserProfileOut(BaseModel):
    id: int
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    heightCm: Optional[float] = Field(default=None, alias="heightCm")
    weightKg: Optional[float] = Field(default=None, alias="weightKg")
    activityLevel: Optional[str] = None
    healthNotes: Optional[str] = None
    tdee: Optional[int] = None

    class Config:
        populate_by_name = True


class UserProfileUpdate(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    heightCm: Optional[float] = None
    weightKg: Optional[float] = None
    activityLevel: Optional[str] = None
    healthNotes: Optional[str] = None