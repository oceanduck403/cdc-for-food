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

    redis_url: str = "redis://localhost:6379/0"

    # 生成式 AI 仅由服务端调用，密钥绝不能下发到小程序。
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-vl-plus"

    wechat_appid: str = ""
    wechat_secret: str = ""

    # 首次生产部署的管理员引导账号。仅在数据库尚无管理员时使用。
    admin_bootstrap_username: str = ""
    admin_bootstrap_password: str = ""

    # 微信支付配置
    wechat_mchid: str = ""
    wechat_mchkey: str = ""
    wechat_notify_url: str = ""

    vision_provider: str = "baidu"
    vision_api_key: str = ""
    vision_api_secret: str = ""
    vision_daily_limit: int = 10000

    oss_bucket: str = ""
    oss_access_key: str = ""
    oss_secret_key: str = ""
    oss_endpoint: str = ""

    daily_analysis_limit_per_user: int = 20
    image_max_bytes: int = 1024 * 1024

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        """阻止生产环境带着开发默认值启动。"""
        self.app_env = self.app_env.strip().lower()
        if self.app_env not in {"development", "test", "production"}:
            raise ValueError("APP_ENV 只能是 development、test 或 production")

        # Railway PostgreSQL 提供的 DATABASE_URL 通常使用同步驱动前缀；
        # SQLAlchemy AsyncEngine 必须显式选择 asyncpg。
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace(
                "postgres://", "postgresql+asyncpg://", 1
            )
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
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
        if self.redis_url.startswith("redis://localhost") or self.redis_url.startswith("redis://127.0.0.1"):
            errors.append("REDIS_URL 生产环境必须指向可用的独立 Redis")

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
