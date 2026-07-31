"""视觉识别（商用菜品识别 API 中转 + OSS 直传）"""
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import current_user_id
from app.services import oss_service, vision_service

router = APIRouter()


class VisionRequest(BaseModel):
    imageBase64: str


class UploadTokenRequest(BaseModel):
    contentType: str = "image/jpeg"


class UploadTokenResponse(BaseModel):
    provider: str
    uploadUrl: str = ""
    key: str = ""
    publicUrl: str = ""
    expiresIn: int = 600
    headers: dict = {}
    mode: str  # "direct" 上传后 PUT, "inline" 直接传 base64


@router.post("/dish")
async def dish(payload: VisionRequest, user_id: str = Depends(current_user_id)) -> List[dict]:
    """菜品识别（支持 inline base64 或 OSS key 两种模式）"""
    return await vision_service.recognize_dish(user_id=user_id, image_b64=payload.imageBase64)


@router.post("/upload-token", response_model=UploadTokenResponse)
async def upload_token(
    payload: UploadTokenRequest,
    user_id: str = Depends(current_user_id),
) -> UploadTokenResponse:
    """获取图片上传签名

    流程：
      1. 前端调用本接口 → 拿到 uploadUrl + key
      2. 前端把图片 PUT 到 uploadUrl（**不经过服务器**）
      3. 上传成功后，前端把 key 传给 /dish 接口
      4. 识别完成后，前端可使用 publicUrl 在小程序中展示

    开发环境（未配置 OSS）→ 返回 mode=inline，前端直接传 base64 给 /dish
    """
    # 不直接接收图片本身，只生成签名；图片在前端压缩后 PUT
    # 这里用 user_id 占位，避免每次签名都重新算 hash
    fake_b64 = f"{user_id}-{int(__import__('time').time())}"
    token = oss_service.build_upload_token(user_id=user_id, image_b64=fake_b64, content_type=payload.contentType)
    return UploadTokenResponse(**token)