"""鉴权：微信 code 换 session、手机号绑定、当前用户信息、医生/管理员登录"""
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_id, get_db
from app.config import settings
from app.core.security import admin_auth_fingerprint, create_access_token, verify_password
from app.models.user import User
from app.services.user_service import ensure_user, get_profile

router = APIRouter()


# ────────────────────────────────────────────────────────────────────
# 微信登录（患者）
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
    role: str = "patient"


class WxSessionResponse(BaseModel):
    """微信 jscode2session 原始响应"""
    openid: str
    session_key: str
    unionid: Optional[str] = None
    errcode: int = 0
    errmsg: str = "ok"


async def _code2session(code: str) -> WxSessionResponse:
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
    """患者微信登录"""
    if settings.wechat_appid and settings.wechat_secret:
        wx = await _code2session(body.code)
        openid = wx.openid
        unionid = wx.unionid
    elif settings.app_env == "development":
        logger.warning("WECHAT_APPID 未配置，使用 mock openid（仅限开发环境）")
        openid = f"mock-openid-{body.code[:8]}" if body.code else "mock-openid-anonymous"
        unionid = None
    else:
        raise HTTPException(status_code=503, detail="微信登录服务配置不完整")

    user = await ensure_user(db, openid=openid, nickname=body.nickname, avatar=body.avatar)
    profile = await get_profile(db, user.id)
    token = create_access_token(subject=str(user.id), extra={"role": "patient", "openid": openid})
    return WechatLoginResponse(token=token, profile=profile, openid=openid, unionid=unionid, role="patient")


# ────────────────────────────────────────────────────────────────────
# 手机号验证码登录（患者）
# ────────────────────────────────────────────────────────────────────

class PhoneLoginRequest(BaseModel):
    phone: str
    code: str  # 验证码（开发期固定为 123456）


class PhoneLoginResponse(BaseModel):
    token: str
    profile: dict
    role: str = "patient"


@router.post("/phone-login", response_model=PhoneLoginResponse)
async def phone_login(body: PhoneLoginRequest, db: AsyncSession = Depends(get_db)) -> PhoneLoginResponse:
    """患者通过手机号 + 验证码登录

    开发期验证码固定为 123456，生产环境接入短信网关。
    """
    if settings.app_env != "development":
        raise HTTPException(status_code=503, detail="手机号验证码登录暂未开放")
    if body.code != "123456":
        raise HTTPException(status_code=400, detail="验证码错误（开发期固定为 123456）")

    # 查找现有手机号用户
    stmt = select(User).where(User.phone == body.phone)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        # 自动创建患者账号
        user = User(phone=body.phone, role="patient", nickname=f"用户{body.phone[-4:]}")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    profile = await get_profile(db, user.id)
    token = create_access_token(subject=str(user.id), extra={"role": "patient", "phone": body.phone})
    return PhoneLoginResponse(token=token, profile=profile, role="patient")


# ────────────────────────────────────────────────────────────────────
# 账号密码登录（医生 / 管理员）
# ────────────────────────────────────────────────────────────────────

class AccountLoginRequest(BaseModel):
    username: str
    password: str
    role: str = "doctor"  # 期望的角色


class AccountLoginResponse(BaseModel):
    token: str
    profile: dict
    role: str


@router.post("/account-login", response_model=AccountLoginResponse)
async def account_login(body: AccountLoginRequest, db: AsyncSession = Depends(get_db)) -> AccountLoginResponse:
    """医生/管理员账号密码登录

    - 医生：管理员分配账号后才能登录
    - 管理员：首次生产部署由安全环境变量引导创建
    """
    stmt = select(User).where(User.username == body.username, User.role == body.role)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail=f"账号不存在或角色错误（{body.role}）")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
    if not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误")

    # 角色不匹配
    if user.role != body.role:
        raise HTTPException(status_code=403, detail=f"该账号不是{body.role}角色")

    token_extra = {"role": user.role, "username": user.username}
    if user.role == "admin":
        token_extra["admin_auth"] = admin_auth_fingerprint(user)
    token = create_access_token(subject=str(user.id), extra=token_extra)

    profile = {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "real_name": user.real_name,
        "avatar": user.avatar,
        "role": user.role,
    }
    if user.role == "doctor":
        profile.update({
            "department": user.department,
            "title": user.title,
            "intro": user.intro,
            "is_available": user.is_available,
        })

    return AccountLoginResponse(token=token, profile=profile, role=user.role)


# ────────────────────────────────────────────────────────────────────
# 手机号绑定
# ────────────────────────────────────────────────────────────────────

class BindPhoneRequest(BaseModel):
    code: str  # 手机号 getPhoneNumber 返回的 code


class BindPhoneResponse(BaseModel):
    phone: str


async def _get_phone_number(code: str) -> str:
    if not settings.wechat_appid or not settings.wechat_secret:
        raise HTTPException(status_code=503, detail="WECHAT_APPID / WECHAT_SECRET 未配置")

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
    from app.services.user_service import update_phone

    phone = await _get_phone_number(body.code)
    await update_phone(db, int(user_id), phone)
    return BindPhoneResponse(phone=phone)


# ────────────────────────────────────────────────────────────────────
# 当前用户信息（含角色判断）
# ────────────────────────────────────────────────────────────────────

@router.get("/me")
async def me(user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_db)) -> dict:
    """返回当前登录用户的角色与基本信息"""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="无效的登录态")

    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return {
        "id": user.id,
        "role": user.role,
        "username": user.username,
        "nickname": user.nickname,
        "real_name": user.real_name,
        "avatar": user.avatar,
        "phone": user.phone,
        "department": user.department,
        "title": user.title,
        "intro": user.intro,
        "is_available": user.is_available,
        "is_active": user.is_active,
    }


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
