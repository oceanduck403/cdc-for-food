"""对象存储服务（OSS / COS）— 图片直传签名

设计：
  1. 小程序端拍照 → 申请上传签名
  2. 后端用 STS / 临时签名 → 返回 put_url + key
  3. 小程序直接 PUT 到 OSS，**不经过服务器**
  4. 完成后只把 key 传给识别接口，识别结果不入库图片

支持的厂商：
  - 腾讯云 COS（推荐，与小程序生态打通）
  - 阿里云 OSS（备选）
  - mock（开发环境，无真实上传，图片直接传给识别接口）

文档：
  https://cloud.tencent.com/document/product/436/9064
  https://help.aliyun.com/zh/oss/developer-reference/put-object
"""
from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timezone
from typing import Optional, Union

from loguru import logger

from app.config import settings


def _sha1_file_b64(image_b64: str) -> str:
    digest = hashlib.sha1(image_b64[:1024].encode("utf-8")).hexdigest()
    return digest


def is_configured() -> bool:
    """是否配置了 OSS（任一厂商）"""
    return bool(settings.oss_bucket and settings.oss_endpoint and
                settings.oss_access_key and settings.oss_secret_key)


# ────────────────────────────────────────────────────────────────────
# 腾讯云 COS 签名（v5 算法 / PostObject 直传）
# ────────────────────────────────────────────────────────────────────

def _cos_signature_v5(method: str, path: str, params: dict, headers: dict,
                      secret_key: str, secret_id: str) -> str:
    """腾讯云 COS 签名 v5（精简版，仅用于 PUT 单文件上传）

    文档：https://cloud.tencent.com/document/product/436/7778
    """
    # HeaderList / ParameterList（按字典序）
    def _kvc(items: dict) -> str:
        return ";".join(f"{k.lower()}" for k in sorted(items.keys()))

    canonical_headers = ""
    signed_headers = ""
    if headers:
        signed_headers = _kvc(headers)
        canonical_headers = "".join(f"{k.lower()}:{v.strip()}\n" for k, v in sorted(headers.items()))

    canonical_query_string = "&".join(
        f"{k}={params[k]}" for k in sorted(params.keys())
    ) if params else ""

    canonical_request = f"{method}\n{path}\n{canonical_query_string}\n{canonical_headers}\n{signed_headers}\n{hashes_sha1_empty}"

    # StringToSign
    algorithm = "sha1"
    timestamp = int(time.time())
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    credential_scope = f"{date}/cos/cosrequest"
    string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashlib.sha1(canonical_request.encode('utf-8')).hexdigest()}"

    # SigningKey
    secret_date = _hmac_sha1(f"cos{secret_key}", date)
    secret_service = _hmac_sha1(secret_date, "cos")
    secret_request = _hmac_sha1(secret_service, "cosrequest")
    signature = _hmac_sha1_hex(secret_request, string_to_sign)

    return (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


def _hmac_sha1(key: Union[bytes, str], msg: str) -> bytes:
    if isinstance(key, str):
        key = key.encode("utf-8")
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha1).digest()


def _hmac_sha1_hex(key: bytes | str, msg: str) -> str:
    return _hmac_sha1(key, msg).hex()


hashes_sha1_empty = hashlib.sha1(b"").hexdigest()


def cos_put_url(key: str, expires: int = 600) -> str:
    """生成 COS 单次 PUT 上传 URL（带签名）"""
    scheme = "https"
    host = settings.oss_endpoint  # 例如 cos.ap-chengdu.myqcloud.com
    path = f"/{settings.oss_bucket}/{key}"

    ts = int(time.time())
    params = {
        "q-sign-algorithm": "sha1",
        "q-ak": settings.oss_access_key,
        "q-sign-time": f"{ts};{ts + expires}",
    }

    canonical_query = "&".join(f"{k}={params[k]}" for k in sorted(params.keys()))
    canonical_resource = f"{path}"

    string_to_sign = f"put\n{path}\n{canonical_query}\n{canonical_resource}\n"

    sign = _hmac_sha1(settings.oss_secret_key, string_to_sign).hex()
    params["q-signature"] = sign

    query = "&".join(f"{k}={params[k]}" for k in params.keys())
    return f"{scheme}://{host}{path}?{query}"


# ────────────────────────────────────────────────────────────────────
# 统一入口
# ────────────────────────────────────────────────────────────────────

def build_upload_token(user_id: str, image_b64: str, content_type: str = "image/jpeg") -> dict:
    """生成图片上传签名

    返回：
      {
        "provider": "cos" | "mock",
        "upload_url": "https://...",   # 前端 PUT 到这个地址
        "key": "uploads/2026-08-01/xxx.jpg",  # 上传成功后给识别接口用
        "public_url": "https://...",   # 上传后可通过该 URL 访问
        "expires_in": 600,
        "headers": {"Content-Type": "image/jpeg"}  # PUT 时需要的 header
      }
    """
    digest = _sha1_file_b64(image_b64)
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    safe_user = "".join(c for c in user_id if c.isalnum())[:32] or "anon"
    ext = "jpg" if content_type.endswith("jpeg") else content_type.split("/")[-1] or "jpg"
    key = f"uploads/{today}/{safe_user}/{digest}.{ext}"

    if not is_configured():
        # 开发环境：返回 mock，前端不真正上传，识别接口仍接收 base64
        logger.debug("OSS 未配置，返回 mock 上传凭证")
        return {
            "provider": "mock",
            "upload_url": "",
            "key": "",
            "public_url": "",
            "expires_in": 600,
            "headers": {},
            "mode": "inline",
        }

    put_url = cos_put_url(key, expires=600)
    public_url = f"https://{settings.oss_endpoint}/{settings.oss_bucket}/{key}"

    return {
        "provider": "cos",
        "upload_url": put_url,
        "key": key,
        "public_url": public_url,
        "expires_in": 600,
        "headers": {"Content-Type": content_type},
        "mode": "direct",
    }