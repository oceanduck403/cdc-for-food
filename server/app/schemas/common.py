"""通用模型"""
from typing import Generic, List, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class Pagination(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int = 1
    page_size: int = 20


class ResponseEnvelope(BaseModel):
    code: str = "OK"
    message: str = "success"
    data: Optional[dict] = None