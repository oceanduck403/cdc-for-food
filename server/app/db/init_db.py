"""初始化脚本：开发种子数据与生产管理员引导。"""
import asyncio

from sqlalchemy import select

from app.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal, init_db
from app.db.survey_defaults import ensure_public_survey_templates
from app.models import KnowledgeArticle, MushroomRisk, User
from app.models.base import Base


async def ensure_production_admin(db) -> User:
    """在空生产库中创建一次性引导管理员，绝不使用演示密码。"""
    existing = (
        await db.execute(
            select(User).where(User.role == "admin", User.is_active.is_(True)).limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    username = settings.admin_bootstrap_username.strip()
    password = settings.admin_bootstrap_password
    if not username or not password:
        raise RuntimeError(
            "生产数据库尚无管理员，请配置 ADMIN_BOOTSTRAP_USERNAME 与 "
            "ADMIN_BOOTSTRAP_PASSWORD 后重新部署"
        )

    collision = (
        await db.execute(select(User).where(User.username == username).limit(1))
    ).scalar_one_or_none()
    if collision:
        raise RuntimeError("ADMIN_BOOTSTRAP_USERNAME 已被其他账号占用")

    admin = User(
        role="admin",
        username=username,
        password_hash=hash_password(password),
        nickname="系统管理员",
        real_name="系统管理员",
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


async def seed() -> None:
    # 先确保所有表都已 import（关键：chat 模型要进 Base.metadata）
    from app.models import chat, knowledge, meal, user, survey  # noqa: F401
    # 强制 Base.metadata 知道所有表
    _ = Base.metadata.tables
    # 生产环境先执行 alembic，再引导管理员和按版本补齐原始表单；
    # 不使用 create_all 绕过迁移，也不插入开发演示内容。
    if settings.app_env == "production":
        async with SessionLocal() as db:
            await ensure_production_admin(db)
            await ensure_public_survey_templates(db)
        return

    await init_db()

    async with SessionLocal() as db:
        await ensure_public_survey_templates(db)

        db.add_all([
            KnowledgeArticle(
                category="guide",
                title="中国居民膳食指南（2022）核心要点",
                summary="食物多样、谷类为主，多吃蔬果、奶类、大豆，适量鱼禽蛋瘦肉，少盐少油。",
                content_html="<h3>核心推荐</h3><ul><li>每天 12 种以上食物</li><li>餐餐有蔬菜，天天有水果</li></ul>",
                source="国家卫生健康委",
                version=1,
            ),
            KnowledgeArticle(
                category="mushroom",
                title="川西常见毒蘑菇：鹅膏属",
                summary="含致命鹅膏毒素，主要分布于川西山区雨季。",
                content_html="<p>误食 6-24 小时后出现肝肾损害。</p>",
                source="四川省疾控中心",
                version=1,
            ),
        ])
        db.add_all([
            MushroomRisk(city="chengdu", name="都江堰山区", species="致命鹅膏", lat=30.99, lng=103.62, level="高", period="6-9 月", description="雨季高发，野外勿采勿食。"),
            MushroomRisk(city="chengdu", name="彭州白水河", species="黄盖鹅膏", lat=31.10, lng=103.83, level="中", period="7-8 月"),
        ])

        await db.commit()

        # 开发环境也不创建任何固定口令账号。确有管理端联调需要时，
        # 由开发者在本地 .env 显式设置一次性引导账号。
        if settings.admin_bootstrap_username and settings.admin_bootstrap_password:
            await ensure_production_admin(db)


if __name__ == "__main__":
    asyncio.run(seed())
    print("seed done")
