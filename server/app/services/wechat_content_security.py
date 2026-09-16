"""微信小程序用户内容安全检查。

公开评论和昵称在写入数据库前调用微信 ``wxa/msg_sec_check``，用户头像
与咨询图片在保存前调用同步图片检查接口。生产环境遇到上游异常时保持
关闭，避免未经审核的用户内容进入系统；开发和测试环境不访问微信接口，
便于离线调试。
"""
from __future__ import annotations

import asyncio
from io import BytesIO
import time
from dataclasses import dataclass

import httpx
from loguru import logger
from PIL import Image

from app.config import settings


STABLE_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/stable_token"
TEXT_CHECK_URL = "https://api.weixin.qq.com/wxa/msg_sec_check"
IMAGE_CHECK_URL = "https://api.weixin.qq.com/wxa/img_sec_check"
_TOKEN_REFRESH_ERRORS = {40001, 40014, 42001}
_IMAGE_REJECTED_ERROR = 87014


class ContentSecurityUnavailable(RuntimeError):
    """微信内容安全服务当前不可用，调用方应提示稍后重试。"""


class ContentSecurityRejected(ValueError):
    """文本被微信判定为需要复核或存在风险。"""


@dataclass
class _TokenCache:
    value: str = ""
    expires_at: float = 0.0


_token_cache = _TokenCache()
_token_lock = asyncio.Lock()


async def _request_access_token(*, force_refresh: bool = False) -> str:
    now = time.monotonic()
    if not force_refresh and _token_cache.value and _token_cache.expires_at > now:
        return _token_cache.value

    async with _token_lock:
        now = time.monotonic()
        if not force_refresh and _token_cache.value and _token_cache.expires_at > now:
            return _token_cache.value
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(
                    STABLE_TOKEN_URL,
                    json={
                        "grant_type": "client_credential",
                        "appid": settings.wechat_appid,
                        "secret": settings.wechat_secret,
                        "force_refresh": force_refresh,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("unexpected token response")
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("获取微信接口调用凭证失败: {}", type(exc).__name__)
            raise ContentSecurityUnavailable("微信内容安全服务暂时不可用") from exc

        token = payload.get("access_token")
        if not token:
            logger.warning("微信接口调用凭证返回异常，errcode={}", payload.get("errcode"))
            raise ContentSecurityUnavailable("微信内容安全服务暂时不可用")
        try:
            expires_in = max(int(payload.get("expires_in", 7200)), 300)
        except (TypeError, ValueError) as exc:
            logger.warning("微信接口调用凭证有效期格式异常")
            raise ContentSecurityUnavailable("微信内容安全服务暂时不可用") from exc
        _token_cache.value = str(token)
        # 提前两分钟刷新，避免请求途中恰好过期。
        _token_cache.expires_at = time.monotonic() + max(expires_in - 120, 60)
        return _token_cache.value


async def _call_text_check(content: str, openid: str, *, force_refresh: bool = False) -> dict:
    token = await _request_access_token(force_refresh=force_refresh)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                TEXT_CHECK_URL,
                params={"access_token": token},
                json={"content": content, "version": 2, "scene": 2, "openid": openid},
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("unexpected security response")
            return payload
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("微信文本内容安全检查失败: {}", type(exc).__name__)
        raise ContentSecurityUnavailable("微信内容安全服务暂时不可用") from exc


def _build_image_check_copy(content: bytes) -> bytes:
    """Build the bounded JPEG accepted by WeChat's synchronous image check."""
    with Image.open(BytesIO(content)) as source:
        source.load()
        image = source.convert("RGB")
        image.thumbnail((750, 1334), Image.Resampling.LANCZOS)
        encoded = BytesIO()
        image.save(encoded, format="JPEG", quality=82, optimize=True)
        result = encoded.getvalue()
        if len(result) > 1024 * 1024:
            encoded = BytesIO()
            image.save(encoded, format="JPEG", quality=68, optimize=True)
            result = encoded.getvalue()
        if not result or len(result) > 1024 * 1024:
            raise ValueError("image security copy is too large")
        return result


async def _call_image_check(content: bytes, *, force_refresh: bool = False) -> dict:
    token = await _request_access_token(force_refresh=force_refresh)
    try:
        review_copy = await asyncio.to_thread(_build_image_check_copy, content)
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(
                IMAGE_CHECK_URL,
                params={"access_token": token},
                files={"media": ("upload.jpg", review_copy, "image/jpeg")},
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("unexpected image security response")
            return payload
    except (httpx.HTTPError, OSError, ValueError) as exc:
        logger.warning("微信图片内容安全检查失败: {}", type(exc).__name__)
        raise ContentSecurityUnavailable("微信内容安全服务暂时不可用") from exc


async def check_public_text(content: str, openid: str | None) -> None:
    """检查即将公开展示的用户文本，无返回值表示可以发布。"""
    if settings.app_env != "production":
        return
    if not openid:
        raise ContentSecurityUnavailable("当前账号缺少微信身份，请重新登录后再试")

    payload = await _call_text_check(content, openid)
    try:
        errcode = int(payload.get("errcode", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise ContentSecurityUnavailable("微信内容安全服务暂时不可用") from exc
    if errcode in _TOKEN_REFRESH_ERRORS:
        _token_cache.value = ""
        _token_cache.expires_at = 0.0
        payload = await _call_text_check(content, openid, force_refresh=True)
        try:
            errcode = int(payload.get("errcode", 0) or 0)
        except (TypeError, ValueError) as exc:
            raise ContentSecurityUnavailable("微信内容安全服务暂时不可用") from exc
    if errcode:
        logger.warning("微信文本内容安全接口返回错误: errcode={}", errcode)
        raise ContentSecurityUnavailable("微信内容安全服务暂时不可用")

    suggest = (payload.get("result") or {}).get("suggest")
    if suggest == "pass":
        return
    if suggest in {"review", "risky", "block"}:
        raise ContentSecurityRejected("评论含有不适合公开展示的内容，请修改后再试")
    logger.warning("微信文本内容安全接口缺少有效结论")
    raise ContentSecurityUnavailable("微信内容安全服务暂时不可用")


async def check_uploaded_image(content: bytes) -> None:
    """Reject unsafe user-uploaded images before they reach private storage."""
    if settings.app_env != "production":
        return

    payload = await _call_image_check(content)
    try:
        errcode = int(payload.get("errcode", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise ContentSecurityUnavailable("微信内容安全服务暂时不可用") from exc
    if errcode in _TOKEN_REFRESH_ERRORS:
        _token_cache.value = ""
        _token_cache.expires_at = 0.0
        payload = await _call_image_check(content, force_refresh=True)
        try:
            errcode = int(payload.get("errcode", 0) or 0)
        except (TypeError, ValueError) as exc:
            raise ContentSecurityUnavailable("微信内容安全服务暂时不可用") from exc
    if errcode == 0:
        return
    if errcode == _IMAGE_REJECTED_ERROR:
        raise ContentSecurityRejected("图片含有不适合展示的内容，请重新选择")
    logger.warning("微信图片内容安全接口返回错误: errcode={}", errcode)
    raise ContentSecurityUnavailable("微信内容安全服务暂时不可用")
