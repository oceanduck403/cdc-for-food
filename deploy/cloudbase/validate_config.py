"""Validate CloudBase production values without echoing any secret.

Usage:
    python deploy/cloudbase/validate_config.py environment.local.json \
        --api-base https://real-service.example.com/api/v1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


REQUIRED = {
    "APP_ENV",
    "JWT_SECRET",
    "DATABASE_URL",
    "WECHAT_APPID",
    "WECHAT_SECRET",
    "QWEN_API_KEY",
    "QWEN_BASE_URL",
    "QWEN_MODEL",
    "MEDIA_STORAGE_BACKEND",
    "MEDIA_COS_SECRET_ID",
    "MEDIA_COS_SECRET_KEY",
    "MEDIA_COS_REGION",
    "MEDIA_COS_BUCKET",
    "MEDIA_COS_PREFIX",
    "ADMIN_BOOTSTRAP_USERNAME",
    "ADMIN_BOOTSTRAP_PASSWORD",
}


def is_placeholder(value: object) -> bool:
    text = str(value or "").strip()
    return not text or "__FILL" in text or "<真实" in text or "example" in text.lower()


def validate_url(name: str, value: str, schemes: set[str], errors: list[str]) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in schemes:
        errors.append(f"{name} 协议必须是 {', '.join(sorted(schemes))}")
    if not parsed.hostname:
        errors.append(f"{name} 缺少主机名")
    elif parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
        errors.append(f"{name} 不能指向本机")


def validate(values: dict[str, object], api_base: str | None) -> list[str]:
    errors: list[str] = []
    for name in sorted(REQUIRED):
        if name not in values or is_placeholder(values.get(name)):
            errors.append(f"{name} 尚未填写真实值")

    if str(values.get("APP_ENV", "")).strip().lower() != "production":
        errors.append("APP_ENV 必须为 production")

    jwt_secret = str(values.get("JWT_SECRET", ""))
    if not is_placeholder(jwt_secret) and len(jwt_secret) < 32:
        errors.append("JWT_SECRET 必须至少 32 个字符")

    database_url = str(values.get("DATABASE_URL", ""))
    if not is_placeholder(database_url):
        validate_url(
            "DATABASE_URL",
            database_url,
            {"postgres", "postgresql", "postgresql+asyncpg"},
            errors,
        )

    redis_url = str(values.get("REDIS_URL", ""))
    if redis_url and not is_placeholder(redis_url):
        validate_url("REDIS_URL", redis_url, {"redis", "rediss"}, errors)

    qwen_base_url = str(values.get("QWEN_BASE_URL", ""))
    if not is_placeholder(qwen_base_url):
        validate_url("QWEN_BASE_URL", qwen_base_url, {"https"}, errors)

    appid = str(values.get("WECHAT_APPID", ""))
    if not is_placeholder(appid) and not re.fullmatch(r"wx[A-Za-z0-9]{10,30}", appid):
        errors.append("WECHAT_APPID 格式异常")

    if str(values.get("MEDIA_STORAGE_BACKEND", "")).strip().lower() != "cos":
        errors.append("MEDIA_STORAGE_BACKEND 生产环境必须为 cos")
    cos_region = str(values.get("MEDIA_COS_REGION", "")).strip()
    if not is_placeholder(cos_region) and not re.fullmatch(r"[a-z0-9-]{3,64}", cos_region):
        errors.append("MEDIA_COS_REGION 格式异常")
    cos_bucket = str(values.get("MEDIA_COS_BUCKET", "")).strip()
    if not is_placeholder(cos_bucket) and not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{0,48}-[0-9]{5,20}", cos_bucket
    ):
        errors.append("MEDIA_COS_BUCKET 必须是包含 APPID 的完整桶名")
    cos_prefix = str(values.get("MEDIA_COS_PREFIX", "")).strip().strip("/")
    if not is_placeholder(cos_prefix) and (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,190}", cos_prefix)
        or ".." in cos_prefix.split("/")
    ):
        errors.append("MEDIA_COS_PREFIX 格式异常")

    username = str(values.get("ADMIN_BOOTSTRAP_USERNAME", ""))
    if not is_placeholder(username) and not re.fullmatch(r"[A-Za-z0-9_]{3,64}", username):
        errors.append("ADMIN_BOOTSTRAP_USERNAME 仅支持 3 至 64 位字母、数字或下划线")

    password = str(values.get("ADMIN_BOOTSTRAP_PASSWORD", ""))
    if not is_placeholder(password):
        strong = (
            12 <= len(password.encode("utf-8")) <= 72
            and re.search(r"[a-z]", password)
            and re.search(r"[A-Z]", password)
            and re.search(r"\d", password)
            and re.search(r"[^A-Za-z0-9]", password)
            and password == password.strip()
        )
        if not strong:
            errors.append("ADMIN_BOOTSTRAP_PASSWORD 须为 12 至 72 字节，并包含大小写字母、数字和符号")

    if "PORT" in values:
        errors.append("不要手工设置 PORT；由云托管注入，并在控制台把服务端口设为 8000")

    if api_base:
        if is_placeholder(api_base):
            errors.append("apiBase 尚未填写真实值")
        else:
            parsed = urlparse(api_base)
            if parsed.scheme != "https" or not parsed.hostname:
                errors.append("apiBase 必须是完整的公网 HTTPS 地址")
            elif parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
                errors.append("apiBase 不能指向本机")
            if not parsed.path.rstrip("/").endswith("/api/v1"):
                errors.append("apiBase 路径应以 /api/v1 结尾")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 CloudBase 生产环境变量（不会打印密钥）")
    parser.add_argument("env_json", type=Path, help="由 environment.example.json 复制并填写的本地文件")
    parser.add_argument("--api-base", help="首版 wx.request 使用的真实 HTTPS API 地址")
    args = parser.parse_args()

    try:
        values = json.loads(args.env_json.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"配置文件无法读取：{exc}", file=sys.stderr)
        return 2
    if not isinstance(values, dict):
        print("配置文件顶层必须是 JSON 对象", file=sys.stderr)
        return 2

    errors = validate(values, args.api_base)
    if errors:
        print("CloudBase 配置未通过：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("CloudBase 环境变量静态校验通过；未输出任何配置值。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
