"""初始化脚本：建表 + 灌入演示数据"""
import asyncio

from app.db.session import SessionLocal, init_db
from app.models import KnowledgeArticle, MushroomRisk, User


async def seed() -> None:
    await init_db()

    async with SessionLocal() as db:
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


if __name__ == "__main__":
    asyncio.run(seed())
    print("seed done")