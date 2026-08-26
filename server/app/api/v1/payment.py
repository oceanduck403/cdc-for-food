"""支付：微信支付统一下单、查询、回调"""
from datetime import datetime
from typing import Optional
import hashlib
import time
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import current_user_id, get_db
from app.config import settings
from app.models.user import User

router = APIRouter()


# ────────────────────────────────────────────────────────────────────
# 微信支付配置
# ────────────────────────────────────────────────────────────────────

def get_wechat_mchid() -> str:
    return getattr(settings, 'wechat_mchid', '')

def get_wechat_mchkey() -> str:
    return getattr(settings, 'wechat_mchkey', '')

def get_wechat_notify_url() -> str:
    return getattr(settings, 'wechat_notify_url', 'https://api.example.com/api/v1/payment/notify')


# ────────────────────────────────────────────────────────────────────
# 统一下单请求/响应
# ────────────────────────────────────────────────────────────────────

class CreatePaymentRequest(BaseModel):
    package_id: int  # 套餐ID


class PaymentPackage(BaseModel):
    id: int
    name: str
    description: str
    analysis_count: int        # 分析次数
    price_yuan: int           # 价格（分）
    valid_days: int           # 有效期（天）


# 可用套餐列表
PAYMENT_PACKAGES = [
    PaymentPackage(id=1, name="月度会员", description="30天内有效，每天20次", analysis_count=600, price_yuan=3000, valid_days=30),
    PaymentPackage(id=2, name="季度会员", description="90天内有效，每天20次", analysis_count=1800, price_yuan=8000, valid_days=90),
    PaymentPackage(id=3, name="年度会员", description="365天内有效，每天20次", analysis_count=7300, price_yuan=26800, valid_days=365),
]


class CreatePaymentResponse(BaseModel):
    order_id: str
    payment_params: dict  # 微信支付调起参数


# ────────────────────────────────────────────────────────────────────
# 签名工具
# ────────────────────────────────────────────────────────────────────

def make_sign(params: dict, sign_type: str = "MD5") -> str:
    """生成微信支付签名"""
    # 1. 字典排序
    sorted_keys = sorted([k for k in params if k != 'sign' and params[k] is not None])
    # 2. URL编码
    string_a = '&'.join(f"{k}={params[k]}" for k in sorted_keys)
    # 3. 拼接key
    string_sign_temp = f"{string_a}&key={get_wechat_mchkey()}"
    # 4. MD5/SHA256签名
    if sign_type == "HMAC-SHA256":
        sign = hashlib.sha256(string_sign_temp.encode()).hexdigest().upper()
    else:
        sign = hashlib.md5(string_sign_temp.encode()).hexdigest().upper()
    return sign


def verify_sign(params: dict) -> bool:
    """验证微信支付回调签名"""
    received_sign = params.get('sign', '')
    if not received_sign:
        return False
    calculated_sign = make_sign(params)
    return received_sign == calculated_sign


# ────────────────────────────────────────────────────────────────────
# 微信支付 API
# ────────────────────────────────────────────────────────────────────

async def _get_access_token() -> str:
    """获取微信 access_token"""
    if not settings.wechat_appid or not settings.wechat_secret:
        raise HTTPException(status_code=503, detail="微信配置未完成")

    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": settings.wechat_appid,
        "secret": settings.wechat_appid,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    if data.get("errcode"):
        raise HTTPException(status_code=400, detail=f"获取access_token失败: {data.get('errmsg')}")

    return data["access_token"]


async def _unified_order(
    openid: str,
    body: str,
    out_trade_no: str,
    total_fee: int,
    notify_url: str,
) -> dict:
    """统一下单接口"""
    if not settings.wechat_appid:
        raise HTTPException(status_code=503, detail="微信配置未完成")

    access_token = await _get_access_token()
    url = f"https://api.weixin.qq.com/digital能力/pay/unifiedorder"

    params = {
        "appid": settings.wechat_appid,
        "mch_id": get_wechat_mchid(),
        "nonce_str": uuid.uuid4().hex,
        "body": body,
        "out_trade_no": out_trade_no,
        "total_fee": total_fee,
        "spbill_create_ip": "127.0.0.1",  # 正式环境替换为用户真实IP
        "notify_url": notify_url,
        "trade_type": "JSAPI",
        "openid": openid,
    }
    params["sign"] = make_sign(params)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=params)
        result = resp.json()

    if result.get("result_code") != "SUCCESS":
        logger.error(f"统一下单失败: {result}")
        raise HTTPException(status_code=400, detail=f"下单失败: {result.get('err_code_des', 'unknown')}")

    return result


# ────────────────────────────────────────────────────────────────────
# API 接口
# ────────────────────────────────────────────────────────────────────

@router.get("/packages", response_model=list[PaymentPackage])
async def list_packages():
    """获取可用套餐列表"""
    return [p.model_dump() for p in PAYMENT_PACKAGES]


@router.post("/create", response_model=CreatePaymentResponse)
async def create_payment(
    body: CreatePaymentRequest,
    user_id: str = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """创建支付订单"""
    # 查找套餐
    package = next((p for p in PAYMENT_PACKAGES if p.id == body.package_id), None)
    if not package:
        raise HTTPException(status_code=400, detail="无效的套餐")

    # 获取用户openid
    try:
        uid = int(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的用户")

    user = await db.get(User, uid)
    if not user or not user.openid:
        raise HTTPException(status_code=401, detail="请先登录")

    openid = user.openid

    # 生成订单号
    order_id = f"CDC{int(time.time())}{uid:04d}"

    # 如果未配置微信支付，返回模拟支付参数（开发环境）
    if not get_wechat_mchid() or not get_wechat_mchkey():
        logger.warning("微信支付未配置，返回模拟支付参数")
        return CreatePaymentResponse(
            order_id=order_id,
            payment_params={
                "mock": True,
                "order_id": order_id,
                "package_name": package.name,
                "price": package.price_yuan,
            }
        )

    try:
        # 调用微信统一下单
        result = await _unified_order(
            openid=openid,
            body=f"营养AI-{package.name}",
            out_trade_no=order_id,
            total_fee=package.price_yuan,
            notify_url=get_wechat_notify_url(),
        )

        prepay_id = result.get("prepay_id", "")
        if not prepay_id:
            raise HTTPException(status_code=400, detail="预支付会话失败")

        # 构建调起支付的参数
        timestamp = str(int(time.time()))
        noncestr = uuid.uuid4().hex

        pay_params = {
            "appId": settings.wechat_appid,
            "timeStamp": timestamp,
            "nonceStr": noncestr,
            "package": f"prepay_id={prepay_id}",
            "signType": "MD5",
        }
        pay_params["paySign"] = make_sign(pay_params)

        return CreatePaymentResponse(
            order_id=order_id,
            payment_params=pay_params,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建支付订单异常: {e}")
        raise HTTPException(status_code=500, detail="支付服务异常")


@router.post("/notify")
async def payment_notify(db: AsyncSession = Depends(get_db)):
    """微信支付回调通知"""
    # 实际环境中这里需要：
    # 1. 解析XML请求体
    # 2. 验证签名
    # 3. 处理订单状态
    # 4. 更新用户配额
    # 5. 返回SUCCESS
    return {"code": "SUCCESS", "message": "成功"}


@router.get("/query/{order_id}")
async def query_payment(
    order_id: str,
    user_id: str = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """查询订单状态"""
    try:
        uid = int(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的用户")

    # 这里应该查询真实订单表，暂时返回模拟状态
    return {
        "order_id": order_id,
        "status": "PAID",  # PAID / UNPAID / REFUND
        "paid_at": datetime.now().isoformat() if True else None,
    }
