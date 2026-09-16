"""Server-side Qwen gateway.

The mini-program must never receive the provider credential.  This module owns
the prompts, validates the provider response and exposes only the small result
shape needed by the client.
"""
from __future__ import annotations

import base64
import binascii
from io import BytesIO
import json
import re
from typing import Any, Iterable

import httpx
from loguru import logger
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings
from app.core.errors import BusinessError


SYSTEM_PROMPTS = {
    "health_consult": """你是成都市疾控营养与食品安全科普助手。请使用通俗、克制、适合中老年用户阅读的中文回答。只提供一般健康科普信息，不作诊断、处方或治疗承诺；涉及明显症状、急症、用药或个体化治疗时，明确建议就医。回答先给结论，再列出可执行建议，并标明内容由 AI 生成。""",
    "diet_guide": """你是营养与食品安全科普助手。根据用户提供的信息给出一般性的膳食搭配与食品安全建议，语言简明，避免诊断、治疗承诺和绝对化结论；必要时建议咨询专业人员。标明内容由 AI 生成。""",
    "survey_analyze": """你是健康科普助手。根据问卷答案总结饮食和生活方式特点、可能需要关注的事项及可执行的改善建议。不得作疾病诊断或风险定论，不得替代医生判断。标明内容由 AI 生成。""",
    "checkin_suggest": """你是健康习惯陪伴助手。结合当天打卡给出 100 字以内、容易执行的饮食、运动或饮水建议。不得作诊断和治疗建议。标明内容由 AI 生成。""",
}

FOOD_PROMPT = """你是营养与食品安全科普助手。分析图片中可见的食物，只输出 JSON：
{"foods":[{"name":"中文食物名","grams":100,"kcal":130,"protein":2.7,"fat":0.3,"carbs":28.2,"sodium":2}]}
grams 为估算重量，其余营养素均为该份食物的估算总量（单位依次为 kcal、g、g、g、mg）。
无法可靠识别时返回 {"foods":[]}。不要输出 markdown、解释或诊断内容。"""


def _provider_config() -> tuple[str, str, str]:
    api_key = getattr(settings, "qwen_api_key", "").strip()
    base_url = getattr(settings, "qwen_base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
    model = getattr(settings, "qwen_model", "qwen-vl-plus").strip()
    if not api_key:
        raise BusinessError("AI_NOT_CONFIGURED", "AI 服务暂未配置，请稍后再试", status_code=503)
    return api_key, base_url, model


async def _completion(messages: list[dict[str, Any]], *, temperature: float = 0.6, max_tokens: int = 1000) -> str:
    api_key, base_url, model = _provider_config()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
        if response.status_code < 200 or response.status_code >= 300:
            logger.error("Qwen request failed with status {}", response.status_code)
            raise BusinessError("AI_UPSTREAM_ERROR", "AI 服务暂时不可用，请稍后重试", status_code=502)
        data = response.json()
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        if not content:
            raise ValueError("empty model response")
        return content
    except BusinessError:
        raise
    except (httpx.HTTPError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        logger.error("Qwen gateway error: {}", type(exc).__name__)
        raise BusinessError("AI_UPSTREAM_ERROR", "AI 服务暂时不可用，请稍后重试", status_code=502) from exc


def _clean_history(history: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for item in list(history)[-12:]:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            cleaned.append({"role": role, "content": content[:2000]})
    return cleaned


async def chat(message: str, mode: str, history: list[dict[str, str]]) -> str:
    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["health_consult"])
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *_clean_history(history),
        {"role": "user", "content": message.strip()},
    ]
    return await _completion(messages)


async def analyze_survey(survey_type: str, answers: dict[str, Any]) -> str:
    compact = json.dumps(answers, ensure_ascii=False, separators=(",", ":"))
    message = f"问卷类型：{survey_type}\n用户答案：{compact[:12000]}\n请给出总体概述、主要发现和按优先级排列的改善建议。"
    return await _completion(
        [
            {"role": "system", "content": SYSTEM_PROMPTS["survey_analyze"]},
            {"role": "user", "content": message},
        ],
        temperature=0.4,
        max_tokens=1400,
    )


async def daily_suggestion(today_data: dict[str, Any], user_profile: dict[str, Any]) -> str:
    payload = json.dumps(
        {"today": today_data, "profile": user_profile},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return await _completion(
        [
            {"role": "system", "content": SYSTEM_PROMPTS["checkin_suggest"]},
            {"role": "user", "content": payload[:6000]},
        ],
        temperature=0.7,
        max_tokens=300,
    )


def _extract_json(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    raw = (fenced.group(1) if fenced else text).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("model response does not contain JSON")
    value = json.loads(raw[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("model response is not an object")
    return value


def _normalize_food_image(image_base64: str) -> str:
    """Validate, strip metadata and bound a food photo before sending it upstream."""
    value = image_base64.strip()
    if value.startswith("data:"):
        match = re.fullmatch(
            r"data:image/(?:jpeg|jpg|png|webp);base64,([A-Za-z0-9+/=\s]+)",
            value,
            re.IGNORECASE,
        )
        if not match:
            raise BusinessError("INVALID_IMAGE", "图片格式不受支持，请重新选择")
        encoded = match.group(1)
    else:
        encoded = value
    encoded = "".join(encoded.split())
    max_bytes = int(getattr(settings, "image_max_bytes", 1024 * 1024))
    if not encoded or len(encoded) * 3 // 4 > max_bytes + 3:
        raise BusinessError("IMAGE_TOO_LARGE", "图片过大，请压缩后重试", status_code=413)
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise BusinessError("INVALID_IMAGE", "图片无法识别，请重新选择") from exc
    if not raw or len(raw) > max_bytes:
        raise BusinessError("IMAGE_TOO_LARGE", "图片过大，请压缩后重试", status_code=413)

    try:
        with Image.open(BytesIO(raw)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"} or getattr(source, "n_frames", 1) != 1:
                raise BusinessError("INVALID_IMAGE", "仅支持静态 JPG、PNG 或 WEBP 图片")
            width, height = source.size
            if (
                width < 1
                or height < 1
                or width > 12000
                or height > 12000
                or width * height > settings.media_max_pixels
            ):
                raise BusinessError("INVALID_IMAGE", "图片尺寸过大，请换一张")
            source.load()
            image = ImageOps.exif_transpose(source)
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            output = Image.new("RGB", image.size, "#ffffff")
            if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
                rgba = image.convert("RGBA")
                output.paste(rgba, mask=rgba.getchannel("A"))
            else:
                output.paste(image.convert("RGB"))
        destination = BytesIO()
        output.save(destination, format="JPEG", quality=82, optimize=True)
        normalized = destination.getvalue()
    except BusinessError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise BusinessError("INVALID_IMAGE", "图片无法识别，请重新选择") from exc
    if not normalized or len(normalized) > max_bytes:
        raise BusinessError("IMAGE_TOO_LARGE", "图片处理后仍然过大，请换一张", status_code=413)
    return base64.b64encode(normalized).decode("ascii")


async def analyze_food(image_base64: str) -> list[dict[str, Any]]:
    encoded = _normalize_food_image(image_base64)
    content = await _completion(
        [{
            "role": "user",
            "content": [
                {"type": "text", "text": FOOD_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
            ],
        }],
        temperature=0.2,
        max_tokens=900,
    )
    try:
        payload = _extract_json(content)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error("Qwen food response parse failed")
        raise BusinessError("AI_BAD_RESPONSE", "图片识别结果异常，请换一张图片重试", status_code=502) from exc

    foods: list[dict[str, Any]] = []
    for raw in payload.get("foods") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()[:40]
        def number(field: str, default: float, maximum: float) -> float:
            try:
                value = float(raw.get(field, default))
            except (TypeError, ValueError):
                value = default
            if value != value:  # NaN
                value = default
            return round(max(0.0, min(maximum, value)), 1)

        grams = max(1, round(number("grams", 100, 2000)))
        if name:
            foods.append({
                "name": name,
                "grams": grams,
                "kcal": number("kcal", 0, 5000),
                "protein": number("protein", 0, 500),
                "fat": number("fat", 0, 500),
                "carbs": number("carbs", 0, 1000),
                "sodium": number("sodium", 0, 20000),
                "confidence": 0.0,
            })
    return foods[:12]
