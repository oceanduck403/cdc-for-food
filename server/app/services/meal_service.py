"""膳食业务：调用视觉识别、保存 Meal、生成报告"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessError
from app.models.meal import Meal, MealItem
from app.models.user import User
from app.services.nutrition_service import generate_advice
from app.services.vision_service import recognize_dish


async def analyze_meal(db: AsyncSession, user_id: str, image_b64: str) -> dict:
    user = await _load_user(db, user_id)
    items = await recognize_dish(user_id=user_id, image_b64=image_b64)

    meal = Meal(
        user_id=user.id,
        image_url=None,
        total_kcal=sum(i["kcal"] for i in items),
        protein=sum(i["protein"] for i in items),
        fat=sum(i["fat"] for i in items),
        carbs=sum(i["carbs"] for i in items),
        sodium=sum(i["sodium"] for i in items),
        captured_at=datetime.now(tz=timezone.utc),
    )
    db.add(meal)
    await db.flush()
    for i in items:
        db.add(MealItem(meal_id=meal.id, **i))
    await db.commit()
    await db.refresh(meal)

    return {
        "mealId": meal.id,
        "items": items,
        "totalKcal": meal.total_kcal,
        "totalProtein": meal.protein,
        "totalFat": meal.fat,
        "totalCarbs": meal.carbs,
        "totalSodium": meal.sodium,
    }


async def get_meal_report(db: AsyncSession, user_id: str, meal_id: str) -> dict:
    user = await _load_user(db, user_id)
    meal: Optional[Meal] = None
    if meal_id == "latest":
        stmt = select(Meal).where(Meal.user_id == user.id).order_by(Meal.captured_at.desc()).limit(1)
        meal = (await db.execute(stmt)).scalar_one_or_none()
        if not meal:
            return _empty_report()
    else:
        try:
            meal = await db.get(Meal, int(meal_id))
        except ValueError:
            raise BusinessError("BAD_MEAL_ID", "无效的膳食 ID")
        if not meal or meal.user_id != user.id:
            raise BusinessError("MEAL_NOT_FOUND", "膳食不存在", status_code=404)

    return _to_report(meal)


async def daily_summary(db: AsyncSession, user_id: str, day: date) -> dict:
    user = await _load_user(db, user_id)
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    stmt = select(
        func.coalesce(func.sum(Meal.total_kcal), 0),
    ).where(
        Meal.user_id == user.id,
        Meal.captured_at >= start,
        Meal.captured_at < end,
    )
    total = (await db.execute(stmt)).scalar_one()
    target = _tdee_target(user)
    return {"calories": float(total or 0), "target": target}


async def _load_user(db: AsyncSession, user_id: str) -> User:
    try:
        uid = int(user_id)
    except ValueError:
        raise BusinessError("BAD_USER_ID", "无效的用户 ID")
    user = await db.get(User, uid)
    if not user:
        raise BusinessError("USER_NOT_FOUND", "用户不存在", status_code=404)
    return user


def _to_report(meal: Meal) -> dict:
    total = max(meal.total_kcal, 1e-3)
    structure = [
        {"name": "蛋白质", "percent": round(meal.protein * 4 / total * 100, 1)},
        {"name": "脂肪", "percent": round(meal.fat * 9 / total * 100, 1)},
        {"name": "碳水", "percent": round(meal.carbs * 4 / total * 100, 1)},
    ]
    advice = generate_advice(
        kcal=meal.total_kcal,
        protein=meal.protein,
        fat=meal.fat,
        carbs=meal.carbs,
        sodium=meal.sodium,
    )
    return {
        "mealId": meal.id,
        "totalKcal": meal.total_kcal,
        "protein": meal.protein,
        "fat": meal.fat,
        "carbs": meal.carbs,
        "sodium": meal.sodium,
        "structure": structure,
        "advice": advice,
    }


def _empty_report() -> dict:
    return {
        "mealId": None,
        "totalKcal": 0,
        "protein": 0,
        "fat": 0,
        "carbs": 0,
        "sodium": 0,
        "structure": [
            {"name": "蛋白质", "percent": 0},
            {"name": "脂肪", "percent": 0},
            {"name": "碳水", "percent": 0},
        ],
        "advice": ["暂无记录，可点击首页拍照开始评估。"],
    }


def _tdee_target(user: User) -> int:
    from app.services.nutrition_service import compute_tdee
    tdee = compute_tdee(
        sex=user.sex,
        weight_kg=user.weight_kg,
        height_cm=user.height_cm,
        age=user.age,
        activity_level=user.activity_level,
    )
    return tdee or 2000