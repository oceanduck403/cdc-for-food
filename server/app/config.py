"""应用配置（从环境变量加载）"""
from functools import lru_cache
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

    wechat_appid: str = ""
    wechat_secret: str = ""

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()