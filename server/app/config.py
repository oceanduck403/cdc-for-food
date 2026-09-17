"""应用配置（从环境变量加载）"""
from functools import lru_cache
import re

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_name: str = "nutrition-ai-server"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    database_url: str = "sqlite:///./data/app.db"

    # 生成式 AI 仅由服务端调用，密钥绝不能下发到小程序。
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-vl-plus"

    wechat_appid: str = ""
    wechat_secret: str = ""

    # 首次生产部署的管理员引导账号。仅在数据库尚无管理员时使用。
    admin_bootstrap_username: str = ""
    admin_bootstrap_password: str = ""

    daily_analysis_limit_per_user: int = 20
    image_max_bytes: int = 1024 * 1024

    # 用户媒体。开发/测试默认写入本地私有目录；生产可使用私有 COS，
    # 或 PG 环境内置的 CloudBase Storage API，避免容器重启或扩容丢失文件。
    media_storage_backend: str = "local"
    media_storage_dir: str = "uploads"
    media_url_ttl_seconds: int = 15 * 60
    avatar_max_bytes: int = 5 * 1024 * 1024
    chat_image_max_bytes: int = 8 * 1024 * 1024
    media_max_pixels: int = 24 * 1024 * 1024
    media_cos_secret_id: str = ""
    media_cos_secret_key: str = ""
    media_cos_region: str = ""
    media_cos_bucket: str = ""
    media_cos_token: str = ""
    media_cos_prefix: str = "private/user-media"
    media_cloudbase_env_id: str = ""
    media_cloudbase_api_key: str = ""
    media_cloudbase_bucket: str = "user-media"
    media_cloudbase_timeout_seconds: float = 15.0

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        """阻止生产环境带着开发默认值启动。"""
        self.app_env = self.app_env.strip().lower()
        if self.app_env not in {"development", "test", "production"}:
            raise ValueError("APP_ENV 只能是 development、test 或 production")
        self.media_storage_backend = self.media_storage_backend.strip().lower()
        if self.media_storage_backend not in {"local", "cos", "cloudbase_pg"}:
            raise ValueError("MEDIA_STORAGE_BACKEND 只能是 local、cos 或 cloudbase_pg")
        if not self.media_storage_dir.strip():
            raise ValueError("MEDIA_STORAGE_DIR 不能为空")
        if not 60 <= self.media_url_ttl_seconds <= 3600:
            raise ValueError("MEDIA_URL_TTL_SECONDS 必须在 60 到 3600 秒之间")
        if self.avatar_max_bytes < 1024 or self.chat_image_max_bytes < 1024:
            raise ValueError("用户图片大小上限配置过小")
        if self.media_max_pixels < 1024:
            raise ValueError("MEDIA_MAX_PIXELS 配置过小")
        if not 1 <= self.media_cloudbase_timeout_seconds <= 60:
            raise ValueError("MEDIA_CLOUDBASE_TIMEOUT_SECONDS 必须在 1 到 60 秒之间")
        self.media_cos_prefix = self.media_cos_prefix.strip().strip("/")
        if not self.media_cos_prefix or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._/-]{0,190}", self.media_cos_prefix
        ) or ".." in self.media_cos_prefix.split("/"):
            raise ValueError("MEDIA_COS_PREFIX 格式无效")

        # CloudBase、腾讯云数据库及其他托管平台可能提供同步驱动前缀；
        # SQLAlchemy AsyncEngine 必须显式选择 asyncpg。
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace(
                "postgres://", "postgresql+asyncpg://", 1
            )
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        # PostgreSQL 控制台和 libpq 常返回 ``sslmode=require``。SQLAlchemy
        # 的 asyncpg 方言会把未知的 ``sslmode`` 原样传给 asyncpg.connect，
        # 从而在容器启动迁移时触发 TypeError；asyncpg 使用的参数名是 ssl。
        # 保留其他查询参数及已显式提供的 ssl，仅规范化参数名。
        if self.database_url.startswith("postgresql+asyncpg://"):
            self.database_url = re.sub(
                r"([?&])sslmode=",
                r"\1ssl=",
                self.database_url,
                flags=re.IGNORECASE,
            )

        if self.app_env != "production":
            return self

        errors: list[str] = []
        insecure_jwt_values = {
            "",
            "change-me",
            "replace-me-with-a-long-random-string",
            "dev-secret",
        }
        if self.jwt_secret.strip() in insecure_jwt_values or len(self.jwt_secret) < 32:
            errors.append("JWT_SECRET 必须是至少 32 位的随机字符串，且不能使用示例值")
        if self.jwt_algorithm != "HS256":
            errors.append("JWT_ALGORITHM 生产环境当前仅支持 HS256")
        if self.database_url.startswith("sqlite"):
            errors.append("DATABASE_URL 生产环境必须使用 PostgreSQL")
        elif not self.database_url.startswith("postgresql+asyncpg://"):
            errors.append("DATABASE_URL 必须是 PostgreSQL 连接地址")
        if not self.wechat_appid.strip() or not self.wechat_secret.strip():
            errors.append("WECHAT_APPID 与 WECHAT_SECRET 必须完整配置")
        if not self.qwen_api_key.strip():
            errors.append("QWEN_API_KEY 必须配置在服务端环境变量中")
        if not self.qwen_base_url.startswith("https://"):
            errors.append("QWEN_BASE_URL 必须使用 HTTPS")
        if not self.qwen_model.strip():
            errors.append("QWEN_MODEL 不能为空")
        if self.media_storage_backend == "local":
            errors.append(
                "MEDIA_STORAGE_BACKEND 生产环境必须设为 cos 或 cloudbase_pg，不能依赖容器临时磁盘"
            )
        elif self.media_storage_backend == "cos":
            cos_values = {
                "MEDIA_COS_SECRET_ID": self.media_cos_secret_id,
                "MEDIA_COS_SECRET_KEY": self.media_cos_secret_key,
                "MEDIA_COS_REGION": self.media_cos_region,
                "MEDIA_COS_BUCKET": self.media_cos_bucket,
            }
            for name, value in cos_values.items():
                if not value.strip():
                    errors.append(f"{name} 必须配置")
            if self.media_cos_region and not re.fullmatch(
                r"[a-z0-9-]{3,64}", self.media_cos_region
            ):
                errors.append("MEDIA_COS_REGION 格式无效")
            if self.media_cos_bucket and not re.fullmatch(
                r"[a-z0-9][a-z0-9-]{0,48}-[0-9]{5,20}", self.media_cos_bucket
            ):
                errors.append("MEDIA_COS_BUCKET 必须是包含 APPID 的完整私有存储桶名称")
        elif self.media_storage_backend == "cloudbase_pg":
            cloudbase_values = {
                "MEDIA_CLOUDBASE_ENV_ID": self.media_cloudbase_env_id,
                "MEDIA_CLOUDBASE_API_KEY": self.media_cloudbase_api_key,
                "MEDIA_CLOUDBASE_BUCKET": self.media_cloudbase_bucket,
            }
            for name, value in cloudbase_values.items():
                if not value.strip():
                    errors.append(f"{name} 必须配置")
            if self.media_cloudbase_env_id and not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9-]{2,127}", self.media_cloudbase_env_id
            ):
                errors.append("MEDIA_CLOUDBASE_ENV_ID 格式无效")
            if self.media_cloudbase_bucket and not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", self.media_cloudbase_bucket
            ):
                errors.append("MEDIA_CLOUDBASE_BUCKET 格式无效")
        bootstrap_username = self.admin_bootstrap_username.strip()
        bootstrap_password = self.admin_bootstrap_password
        if bool(bootstrap_username) != bool(bootstrap_password):
            errors.append("ADMIN_BOOTSTRAP_USERNAME 与 ADMIN_BOOTSTRAP_PASSWORD 必须同时配置")
        if bootstrap_username and not re.fullmatch(r"[A-Za-z0-9_]{3,64}", bootstrap_username):
            errors.append("ADMIN_BOOTSTRAP_USERNAME 仅支持 3 至 64 位字母、数字或下划线")
        if bootstrap_password:
            strong_password = (
                len(bootstrap_password) >= 12
                and len(bootstrap_password.encode("utf-8")) <= 72
                and re.search(r"[a-z]", bootstrap_password)
                and re.search(r"[A-Z]", bootstrap_password)
                and re.search(r"\d", bootstrap_password)
                and re.search(r"[^A-Za-z0-9]", bootstrap_password)
                and bootstrap_password == bootstrap_password.strip()
            )
            if not strong_password:
                errors.append(
                    "ADMIN_BOOTSTRAP_PASSWORD 须为 12 至 72 字节，并包含大小写字母、数字和符号"
                )

        if errors:
            raise ValueError("生产配置无效：" + "；".join(errors))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
