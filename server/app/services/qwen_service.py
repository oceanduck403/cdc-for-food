"""Server-side Qwen gateway.

The mini-program must never receive the provider credential.  This module owns
the prompts, validates the provider response and exposes only the small result
shape needed by the client.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable

import httpx
from loguru import logger

from app.config import settings
from app.core.errors import BusinessError


SYSTEM_PROMPTS = {
    "health_consult": """你是成都市疾控营养与食品安全科普助手。请使用通俗、克制、适合中老年用户阅读的中文回答。只提供一般健康科普信息，不作诊断、处方或治疗承诺；涉及明显症状、急症、用药或个体化治疗时，明确建议就医。回答先给结论，再列出可执行建议，并标明内容由 AI 生成。""",
    "diet_guide": """你是营养与食品安全科普助手。根据用户提供的信息给出一般性的膳食搭配与食品安全建议，语言简明，避免诊断、治疗承诺和绝对化结论；必要时建议咨询专业人员。标明内容由 AI 生成。""",
    "survey_analyze": """你是健康科普助手。根据问卷答案总结饮食和生活方式特点、可能需要关注的事项及可执行的改善建议。不得作疾病诊断或风险定论，不得替代医生判断。标明内容由 AI 生成。""",
    "checkin_suggest": """你是健康习惯陪伴助手。结合当天打卡给出 100 字以内、容易执行的饮食、运动或饮水建议。不得作诊断和治疗建议。标明内容由 AI 生成。""",
}

FOOD_PROMPT = """你是营养与食品安全科普助手。分析图片中可见的食物，只输出 JSON：
{"foods":[{"name":"中文食物名","grams":100}]}
grams 为大致重量估算。无法可靠识别时返回 {"foods":[]}。不要输出 markdown 或解释。"""


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


async def analyze_food(image_base64: str) -> list[dict[str, Any]]:
    encoded = image_base64.split(",", 1)[-1].strip()
    max_bytes = int(getattr(settings, "image_max_bytes", 1024 * 1024))
    if len(encoded) * 3 // 4 > max_bytes:
        raise BusinessError("IMAGE_TOO_LARGE", "图片过大，请压缩后重试", status_code=413)
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
        try:
            grams = max(1, min(2000, round(float(raw.get("grams") or 100))))
        except (TypeError, ValueError):
            grams = 100
        if name:
            foods.append({"name": name, "grams": grams})
    return foods[:12]
