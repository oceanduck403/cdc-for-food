"""生产配置、登录降级和管理员引导的发布回归测试。"""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.core.security import verify_password
from app.models import Base
from app.models.user import User


def production_settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "jwt_secret": "6hd!QvP2zN8#rL4xT7mK9sW3cF5aJ1uB",
        "database_url": "postgresql://user:password@postgres:5432/nutrition",
        "wechat_appid": "wx1234567890abcdef",
        "wechat_secret": "a" * 32,
        "qwen_api_key": "server-only-qwen-key",
        "media_storage_backend": "cos",
        "media_cos_secret_id": "AKID" + "a" * 32,
        "media_cos_secret_key": "b" * 32,
        "media_cos_region": "ap-chengdu",
        "media_cos_bucket": "nutrition-private-1250000000",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_settings_normalize_railway_postgres_url():
    configured = production_settings()
    assert configured.database_url.startswith("postgresql+asyncpg://")


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://user:password@postgres:5432/nutrition?sslmode=require",
        "postgres://user:password@postgres:5432/nutrition?connect_timeout=10&sslmode=require",
        "postgresql+asyncpg://user:password@postgres:5432/nutrition?sslmode=require",
    ],
)
def test_production_settings_normalize_cloudbase_sslmode(database_url):
    configured = production_settings(database_url=database_url)
    assert "sslmode=" not in configured.database_url
    assert "ssl=require" in configured.database_url


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"jwt_secret": "change-me"}, "JWT_SECRET"),
        ({"database_url": "sqlite:///./data/app.db"}, "DATABASE_URL"),
        ({"wechat_secret": ""}, "WECHAT_APPID"),
        ({"qwen_api_key": ""}, "QWEN_API_KEY"),
        ({"media_storage_backend": "local"}, "MEDIA_STORAGE_BACKEND"),
        ({"media_cos_bucket": ""}, "MEDIA_COS_BUCKET"),
        ({"admin_bootstrap_username": "admin", "admin_bootstrap_password": "weak"},
         "ADMIN_BOOTSTRAP_PASSWORD"),
        ({"admin_bootstrap_username": "admin"}, "必须同时配置"),
    ],
)
def test_production_settings_reject_unsafe_values(overrides, message):
    with pytest.raises(ValidationError, match=message):
        production_settings(**overrides)


@pytest.mark.asyncio
async def test_production_disables_mock_wechat_and_has_no_fixed_phone_code(client, monkeypatch):
    from app.api.v1 import auth

    monkeypatch.setattr(
        auth,
        "settings",
        SimpleNamespace(app_env="production", wechat_appid="", wechat_secret=""),
    )
    wechat = await client.post("/api/v1/auth/wechat", json={"code": "forged-code"})
    phone = await client.post("/api/v1/auth/phone-login", json={})
    assert wechat.status_code == 503
    assert phone.status_code == 404


@pytest.mark.asyncio
async def test_production_bootstrap_creates_one_strong_admin(monkeypatch):
    init_module = importlib.import_module("app.db.init_db")
    monkeypatch.setattr(
        init_module,
        "settings",
        SimpleNamespace(
            admin_bootstrap_username="release_admin",
            admin_bootstrap_password="Strong!Release123",
        ),
    )
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as db:
            first = await init_module.ensure_production_admin(db)
            second = await init_module.ensure_production_admin(db)
            count = await db.scalar(
                select(func.count(User.id)).where(User.role == "admin")
            )
            assert first.id == second.id
            assert count == 1
            assert verify_password("Strong!Release123", first.password_hash)
    finally:
        await engine.dispose()


def test_railway_container_uses_safe_context_port_and_healthcheck():
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (root / ".dockerignore").read_text(encoding="utf-8")
    railway = json.loads((root / "railway.json").read_text(encoding="utf-8"))

    assert "COPY server/requirements.txt" in dockerfile
    assert "COPY server/ ./server/" not in dockerfile
    assert "${PORT:-8000}" in dockerfile
    assert "alembic upgrade head" in dockerfile
    assert dockerignore.splitlines()[0] == "**"
    assert "!server/app/**" in dockerignore
    assert railway["deploy"]["healthcheckPath"] == "/health"
    assert "${PORT:-8000}" in railway["deploy"]["startCommand"]
    assert "alembic upgrade head" in railway["deploy"]["startCommand"]
