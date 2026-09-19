"""Keep the first-release public survey catalogue non-clinical and deterministic."""
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.survey import SurveyTemplate


LIFESTYLE_TYPE = "healthy_lifestyle_self_check"
LIFESTYLE_QUESTIONS = [
    {
        "id": "ls1",
        "step": 0,
        "type": "radio",
        "title": "您通常能按相对固定的时间吃一日三餐吗？",
        "options": ["经常做到", "有时做到", "较少做到"],
    },
    {
        "id": "ls2",
        "step": 0,
        "type": "radio",
        "title": "您每天会吃多种蔬菜，并适量吃新鲜水果吗？",
        "options": ["经常做到", "有时做到", "较少做到"],
    },
    {
        "id": "ls3",
        "step": 0,
        "type": "radio",
        "title": "您会用全谷物、杂豆或薯类替代一部分精制米面吗？",
        "options": ["经常做到", "有时做到", "较少做到"],
    },
    {
        "id": "ls4",
        "step": 0,
        "type": "radio",
        "title": "您会少喝含糖饮料，少吃高盐、高油或高糖食品吗？",
        "options": ["经常做到", "有时做到", "较少做到"],
    },
    {
        "id": "ls5",
        "step": 0,
        "type": "radio",
        "title": "您每天会主动、分次饮用白水吗？",
        "options": ["经常做到", "有时做到", "较少做到"],
    },
    {
        "id": "ls6",
        "step": 1,
        "type": "radio",
        "title": "您每周会安排多次步行、骑行或健身操等身体活动吗？",
        "options": ["经常做到", "有时做到", "较少做到"],
    },
    {
        "id": "ls7",
        "step": 1,
        "type": "radio",
        "title": "久坐时，您会每隔一段时间起身活动吗？",
        "options": ["经常做到", "有时做到", "较少做到"],
    },
    {
        "id": "ls8",
        "step": 1,
        "type": "radio",
        "title": "您通常能保持较规律的作息，并获得充足睡眠吗？",
        "options": ["经常做到", "有时做到", "较少做到"],
    },
    {
        "id": "ls9",
        "step": 2,
        "type": "radio",
        "title": "处理食物和进餐前，您会认真洗手吗？",
        "options": ["经常做到", "有时做到", "较少做到"],
    },
    {
        "id": "ls10",
        "step": 2,
        "type": "radio",
        "title": "准备食物时，您会将生熟食材、刀具和容器分开吗？",
        "options": ["经常做到", "有时做到", "较少做到"],
    },
    {
        "id": "ls11",
        "step": 2,
        "type": "radio",
        "title": "剩余食物会及时冷藏，并在再次食用前彻底加热吗？",
        "options": ["经常做到", "有时做到", "较少做到"],
    },
    {
        "id": "ls12",
        "step": 2,
        "type": "radio",
        "title": "您会查看食品来源、保质期和储存条件，并避免食用来源不明的野生食物吗？",
        "options": ["经常做到", "有时做到", "较少做到"],
    },
]

LIFESTYLE_TEMPLATE = {
    "name": "健康生活方式自测",
    "description": "从饮食、饮水、运动、睡眠和食品安全习惯了解日常生活方式，结果仅供健康科普与自我记录，不作为医疗结论。",
    "category": "健康生活",
    "questions": json.dumps(LIFESTYLE_QUESTIONS, ensure_ascii=False),
    "is_active": True,
    "sort_order": 0,
}

# These templates are retained for historical responses and administrator
# records, but are never exposed in the first-release public catalogue.
DISABLED_DEFAULT_TEMPLATE_TYPES = frozenset(
    {
        "weight_visit_registration",
        "weight_basic_info",
        "weight_clinic_first",
        "weight_clinic_follow",
        "weight_anti_obesity",
    }
)


async def _apply_public_defaults(db: AsyncSession) -> None:
    legacy_templates = (
        await db.execute(
            select(SurveyTemplate).where(
                SurveyTemplate.type.in_(DISABLED_DEFAULT_TEMPLATE_TYPES)
            )
        )
    ).scalars().all()
    for template in legacy_templates:
        template.is_active = False

    lifestyle = await db.scalar(
        select(SurveyTemplate).where(SurveyTemplate.type == LIFESTYLE_TYPE)
    )
    if lifestyle is None:
        lifestyle = SurveyTemplate(type=LIFESTYLE_TYPE)
        db.add(lifestyle)
    for field, value in LIFESTYLE_TEMPLATE.items():
        setattr(lifestyle, field, value)


async def ensure_public_survey_templates(db: AsyncSession) -> None:
    """Create the safe public template and deactivate legacy clinical defaults."""
    try:
        await _apply_public_defaults(db)
        await db.commit()
    except IntegrityError:
        # Multiple workers can race to create the unique lifestyle type. The
        # winner's row is reused, then the complete desired state is applied.
        await db.rollback()
        if await db.scalar(
            select(SurveyTemplate.id).where(SurveyTemplate.type == LIFESTYLE_TYPE)
        ) is None:
            raise
        await _apply_public_defaults(db)
        await db.commit()


async def ensure_registration_template(db: AsyncSession) -> None:
    """Backward-compatible entry point for older deployment scripts."""
    await ensure_public_survey_templates(db)
