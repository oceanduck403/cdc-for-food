"""Restore supplied Word forms once, preserving administrator edits and history."""
import json

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.survey_catalog import (
    CATALOG_REVISION,
    DEMO_LIFESTYLE_TYPE,
    ORIGINAL_SURVEY_CATALOG,
    ORIGINAL_SURVEY_TYPES,
    REGISTRATION_QUESTIONS,
)
from app.models.survey import SurveyResponse, SurveyTemplate


REGISTRATION_TYPE = "weight_visit_registration"


async def _freeze_existing_questions(db: AsyncSession, template: SurveyTemplate) -> None:
    await db.execute(
        update(SurveyResponse)
        .where(
            SurveyResponse.template_id == template.id,
            SurveyResponse.questions_snapshot.is_(None),
        )
        .values(questions_snapshot=template.questions)
    )


async def _apply_source_catalog(db: AsyncSession) -> None:
    types = ORIGINAL_SURVEY_TYPES | {DEMO_LIFESTYLE_TYPE}
    rows = (
        await db.execute(select(SurveyTemplate).where(SurveyTemplate.type.in_(types)))
    ).scalars().all()
    existing = {template.type: template for template in rows}
    for source in ORIGINAL_SURVEY_CATALOG:
        template = existing.get(source["type"])
        if template is not None and template.catalog_revision >= CATALOG_REVISION:
            continue
        if template is None:
            template = SurveyTemplate(type=source["type"])
            db.add(template)
        else:
            # Also protects databases created directly from ORM metadata without
            # an Alembic history; never rewrite an older response's questions.
            await _freeze_existing_questions(db, template)
        for field in ("name", "description", "category", "is_active", "sort_order"):
            setattr(template, field, source[field])
        template.questions = json.dumps(source["questions"], ensure_ascii=False)
        template.catalog_revision = CATALOG_REVISION

    demo = existing.get(DEMO_LIFESTYLE_TYPE)
    if demo is not None and demo.catalog_revision < CATALOG_REVISION:
        await _freeze_existing_questions(db, demo)
        demo.is_active = False
        demo.catalog_revision = CATALOG_REVISION


async def ensure_public_survey_templates(db: AsyncSession) -> None:
    """Install/correct the original forms once per source-catalog revision."""
    try:
        await _apply_source_catalog(db)
        await db.commit()
    except IntegrityError:
        # Workers may race on the unique template type. Only recover when the
        # other transaction installed the complete catalog; unrelated errors
        # must still fail visibly.
        await db.rollback()
        installed = set(
            (await db.execute(
                select(SurveyTemplate.type).where(SurveyTemplate.type.in_(ORIGINAL_SURVEY_TYPES))
            )).scalars().all()
        )
        if installed != ORIGINAL_SURVEY_TYPES:
            raise
        await _apply_source_catalog(db)
        await db.commit()


async def ensure_registration_template(db: AsyncSession) -> None:
    """Compatibility entry point used by older deployment scripts."""
    await ensure_public_survey_templates(db)
