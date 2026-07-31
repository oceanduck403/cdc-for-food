"""商用菜品识别 API 中转（带 mock，方便开发）

生产环境支持：
  - baidu   百度智能云菜品识别（默认）
  - mock    本地 mock（开发联调）

接入方式：
  1. 百度智能云 → 图像识别 → 菜品识别 → 创建应用 → 拿 API Key / Secret Key
  2. 填入 .env：VISION_PROVIDER=baidu, VISION_API_KEY=..., VISION_API_SECRET=...
  3. 用云函数中转代理密钥 → 前端永远拿不到明文

百度文档：https://cloud.baidu.com/doc/IMAGERECOGNITION/index
"""
import hashlib
import time
from typing import List, Optional

import httpx
from loguru import logger

from app.config import settings

# ────────────────────────────────────────────────────────────────────
# Mock 数据（开发环境使用）
# ────────────────────────────────────────────────────────────────────

MOCK_DISHES = [
    {"name": "宫保鸡丁", "grams": 180, "kcal": 320, "protein": 22, "fat": 18, "carbs": 16, "sodium": 720, "confidence": 0.92},
    {"name": "米饭", "grams": 150, "kcal": 195, "protein": 4, "fat": 0.5, "carbs": 43, "sodium": 5, "confidence": 0.97},
    {"name": "清炒时蔬", "grams": 120, "kcal": 80, "protein": 3, "fat": 4, "carbs": 8, "sodium": 280, "confidence": 0.85},
]


async def _mock_recognize(image_b64: str) -> List[dict]:
    if not image_b64:
        return []
    digest = hashlib.sha1(image_b64[:512].encode("utf-8")).hexdigest()
    seed = int(digest[:4], 16) % 3
    items = MOCK_DISHES[: max(1, 3 - seed)]
    return items


# ────────────────────────────────────────────────────────────────────
# 百度智能云菜品识别
# ────────────────────────────────────────────────────────────────────

_BAIDU_TOKEN_CACHE: dict = {}


async def _get_baidu_access_token() -> str:
    """获取百度 access_token（含简单内存缓存）"""
    cached = _BAIDU_TOKEN_CACHE.get("token")
    if cached and cached["expires_at"] > time.time() + 60:
        return cached["token"]

    if not settings.vision_api_key or not settings.vision_api_secret:
        raise RuntimeError("VISION_API_KEY / VISION_API_SECRET 未配置")

    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": settings.vision_api_key,
        "client_secret": settings.vision_api_secret,
    }
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.post(url, params=params)
        data = resp.json()

    if "access_token" not in data:
        logger.error("baidu token failed: {}", data)
        raise RuntimeError(f"百度鉴权失败：{data.get('error_description', data)}")

    _BAIDU_TOKEN_CACHE["token"] = {
        "token": data["access_token"],
        "expires_at": time.time() + int(data.get("expires_in", 2592000)),
    }
    return data["access_token"]


async def _baidu_recognize(image_b64: str) -> List[dict]:
    """调用百度菜品识别 API

    返回结构示例：
    {
      "result": [
        {"name": "宫保鸡丁", "calorie": 320, "probability": "0.92", "baike_info": {...}},
        ...
      ]
    }
    """
    token = await _get_baidu_access_token()
    url = f"https://aip.baidubce.com/rest/2.0/image-classify/v2/dish?access_token={token}"

    payload = {
        "image": image_b64,
        "top_num": 5,           # 返回 top-5 菜品
        "filter_threshold": "0.1",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
        data = resp.json()

    if "error_code" in data:
        logger.error("baidu vision failed: {}", data)
        raise RuntimeError(f"百度识别失败：{data.get('error_msg', data)} (code={data.get('error_code')})")

    items: List[dict] = []
    for raw in data.get("result", []):
        # 百度返回字段：name / calorie / probability / baike_info
        try:
            confidence = float(raw.get("probability", 0))
        except (TypeError, ValueError):
            confidence = 0.0
        try:
            kcal = float(raw.get("calorie", 0)) if raw.get("calorie") not in (None, "", "0") else 0
        except (TypeError, ValueError):
            kcal = 0.0

        # 克重估算：百度返回的 calorie 是每 100g 的热量；我们反推常见克重
        # 这里用 200g 作为默认估值（可被业务方覆盖）
        grams = 200
        items.append({
            "name": raw.get("name", "未知菜品"),
            "grams": grams,
            "kcal": round(kcal, 1),
            "protein": None,      # 百度不直接给出，nutrition_service 会查食物成分表补全
            "fat": None,
            "carbs": None,
            "sodium": None,
            "confidence": round(confidence, 3),
            "source": "baidu",
        })
    return items


# ────────────────────────────────────────────────────────────────────
# 统一入口
# ────────────────────────────────────────────────────────────────────

async def recognize_dish(user_id: str, image_b64: str) -> List[dict]:
    """返回识别出的菜品列表（每项已估算克重与营养素）

    生产环境：通过 settings.vision_provider 切换 mock / baidu
    """
    if not image_b64:
        return []

    provider = (settings.vision_provider or "mock").lower()

    if provider == "baidu":
        if not settings.vision_api_key or not settings.vision_api_secret:
            logger.warning("VISION_API_KEY 未配置，降级为 mock（仅开发期）")
            items = await _mock_recognize(image_b64)
        else:
            try:
                items = await _baidu_recognize(image_b64)
            except Exception as exc:
                logger.error("baidu recognize exception, fallback to mock: {}", exc)
                items = await _mock_recognize(image_b64)
    elif provider == "mock":
        items = await _mock_recognize(image_b64)
    else:
        logger.warning("未知 VISION_PROVIDER={}, 降级 mock", provider)
        items = await _mock_recognize(image_b64)

    logger.info("vision provider={} user={} items={}", provider, user_id, len(items))
    return items


async def health_check() -> dict:
    """健康检查：返回当前 provider 状态"""
    provider = (settings.vision_provider or "mock").lower()
    return {
        "provider": provider,
        "configured": provider == "mock" or (bool(settings.vision_api_key) and bool(settings.vision_api_secret)),
    }