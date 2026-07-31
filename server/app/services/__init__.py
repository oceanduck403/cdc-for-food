"""业务服务层"""
from app.services.user_service import (
    ensure_user,
    get_profile,
    update_profile,
    get_daily_quota,
)
from app.services.meal_service import (
    analyze_meal,
    get_meal_report,
    daily_summary,
)
from app.services.knowledge_service import (
    list_articles,
    get_article,
    list_mushroom_risk,
    get_mushroom_risk,
)
from app.services.vision_service import recognize_dish
from app.services.nutrition_service import compute_tdee, generate_advice

__all__ = [
    "ensure_user",
    "get_profile",
    "update_profile",
    "get_daily_quota",
    "analyze_meal",
    "get_meal_report",
    "daily_summary",
    "list_articles",
    "get_article",
    "list_mushroom_risk",
    "get_mushroom_risk",
    "recognize_dish",
    "compute_tdee",
    "generate_advice",
]