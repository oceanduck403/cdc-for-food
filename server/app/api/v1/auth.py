"""鉴权：微信 code 换 session、手机号绑定、当前用户信息"""
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_id, get_db
from app.config import settings
from app.core.security import create_access_token
from app.services.user_service import ensure_user, get_profile

router = APIRouter()


# ────────────────────────────────────────────────────────────────────
# 微信登录
# ────────────────────────────────────────────────────────────────────

class WechatLoginRequest(BaseModel):
    code: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class WechatLoginResponse(BaseModel):
    token: str
    profile: dict
    openid: str
    unionid: Optional[str] = None


class WxSessionResponse(BaseModel):
    """微信 jscode2session 原始响应"""
    openid: str
    session_key: str
    unionid: Optional[str] = None
    errcode: int = 0
    errmsg: str = "ok"


async def _code2session(code: str) -> WxSessionResponse:
    """调用微信 jscode2session 换取 openid / session_key

    文档：https://developers.weixin.qq.com/miniprogram/dev/api-backend/open-api/login/auth.code2Session.html
    """
    if not settings.wechat_appid or not settings.wechat_secret:
        raise HTTPException(
            status_code=503,
            detail="WECHAT_APPID / WECHAT_SECRET 未配置；请在 .env 中填入小程序 AppID 与 AppSecret",
        )

    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.wechat_appid,
        "secret": settings.wechat_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.error("jscode2session http error: {}", exc)
        raise HTTPException(status_code=502, detail="调用微信 jscode2session 失败") from exc

    if data.get("errcode"):
        logger.warning("jscode2session failed: {}", data)
        raise HTTPException(
            status_code=400,
            detail=f"微信登录失败：{data.get('errmsg', 'unknown')} (errcode={data.get('errcode')})",
        )

    return WxSessionResponse(**data)


@router.post("/wechat", response_model=WechatLoginResponse)
async def login_with_wechat(body: WechatLoginRequest, db: AsyncSession = Depends(get_db)) -> WechatLoginResponse:
    """生产环境：通过 jscode2session 换取真实 openid

    开发环境降级：未配置 AppID/Secret 时，使用 mock openid，便于本地联调
    """
    if settings.wechat_appid and settings.wechat_secret:
        wx = await _code2session(body.code)
        openid = wx.openid
        unionid = wx.unionid
    else:
        # 开发期降级
        logger.warning("WECHAT_APPID 未配置，使用 mock openid（仅限开发环境）")
        openid = f"mock-openid-{body.code[:8]}" if body.code else "mock-openid-anonymous"
        unionid = None

    user = await ensure_user(db, openid=openid, nickname=body.nickname, avatar=body.avatar)
    profile = await get_profile(db, user.id)
    token = create_access_token(subject=str(user.id), extra={"openid": openid, "unionid": unionid})
    return WechatLoginResponse(token=token, profile=profile, openid=openid, unionid=unionid)


# ────────────────────────────────────────────────────────────────────
# 手机号绑定
# ────────────────────────────────────────────────────────────────────

class BindPhoneRequest(BaseModel):
    code: str  # 手机号 getPhoneNumber 返回的 code


class BindPhoneResponse(BaseModel):
    phone: str


async def _get_phone_number(code: str) -> str:
    """调用 getuserphonenumber 获取用户手机号

    文档：https://developers.weixin.qq.com/miniprogram/dev/api-backend/open-api/user-info/phonenumber.getPhoneNumber.html
    """
    if not settings.wechat_appid or not settings.wechat_secret:
        raise HTTPException(status_code=503, detail="WECHAT_APPID / WECHAT_SECRET 未配置")

    # 第一步：用 AppID + AppSecret 换 access_token
    token_url = "https://api.weixin.qq.com/cgi-bin/token"
    token_params = {
        "grant_type": "client_credential",
        "appid": settings.wechat_appid,
        "secret": settings.wechat_secret,
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            token_resp = await client.get(token_url, params=token_params)
            token_data = token_resp.json()
        if token_data.get("errcode"):
            raise HTTPException(status_code=400, detail=f"获取 access_token 失败：{token_data}")
        access_token = token_data["access_token"]
    except httpx.HTTPError as exc:
        logger.error("get wx token http error: {}", exc)
        raise HTTPException(status_code=502, detail="调用微信接口失败") from exc

    # 第二步：用 access_token + code 换手机号
    phone_url = "https://api.weixin.qq.com/wxa/business/getuserphonenumber"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            phone_resp = await client.post(
                phone_url,
                params={"access_token": access_token},
                json={"code": code},
            )
            phone_data = phone_resp.json()
    except httpx.HTTPError as exc:
        logger.error("get phone http error: {}", exc)
        raise HTTPException(status_code=502, detail="调用微信接口失败") from exc

    if phone_data.get("errcode"):
        logger.warning("getuserphonenumber failed: {}", phone_data)
        raise HTTPException(
            status_code=400,
            detail=f"获取手机号失败：{phone_data.get('errmsg', 'unknown')} (errcode={phone_data.get('errcode')})",
        )

    phone_info = phone_data.get("phone_info") or {}
    phone = phone_info.get("phoneNumber")
    if not phone:
        raise HTTPException(status_code=400, detail="微信未返回手机号")
    return phone


@router.post("/bind-phone", response_model=BindPhoneResponse)
async def bind_phone(
    body: BindPhoneRequest,
    user_id: str = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
) -> BindPhoneResponse:
    """绑定手机号：通过 wx.getPhoneNumber 的 code 调用微信接口"""
    from app.services.user_service import update_phone  # 避免循环导入

    phone = await _get_phone_number(body.code)
    await update_phone(db, int(user_id), phone)
    return BindPhoneResponse(phone=phone)


# ────────────────────────────────────────────────────────────────────
# 健康检查（供小程序后台填写服务器可用性测试 URL）
# ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}