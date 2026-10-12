"""Submitted answers keep their original questions, without invented scores."""
import json

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.deps import current_admin
from app.core.security import create_access_token
from app.main import app
from app.models.base import Base
from app.models.survey import SurveyResponse, SurveyTemplate
from app.models.user import User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def engine():
    database = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with database.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield database
    await database.dispose()


async def make_patient(db):
    user = User(openid="survey-snapshot-test", role="patient", is_active=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(subject=str(user.id), extra={"role": "patient", "openid": user.openid})
    return {"Authorization": "Bearer " + token}


async def test_original_form_submission_is_unscored_and_keeps_its_question_snapshot(client, db):
    headers = await make_patient(db)
    original = [{"id": "ao1", "title": "原始题干", "type": "radio", "options": ["是", "否"]}]
    template = SurveyTemplate(type="weight_anti_obesity", name="原表", questions=json.dumps(original))
    db.add(template)
    await db.commit()
    await db.refresh(template)
    result = await client.post("/api/v1/survey/responses", headers=headers, json={
        "template_id": template.id, "answers": {"ao1": "是"}, "total_score": 100,
    })
    assert result.status_code == 200
    response_id = result.json()["id"]
    stored = await db.scalar(select(SurveyResponse).where(SurveyResponse.id == response_id))
    assert stored.total_score is None
    assert json.loads(stored.questions_snapshot) == original

    template.questions = json.dumps([{"id": "replacement", "title": "后续修改题目", "type": "input"}])
    template.is_active = False
    await db.commit()
    history = await client.get(f"/api/v1/survey/my-responses/{response_id}", headers=headers)
    assert history.status_code == 200
    assert history.json()["questions"] == original
    assert history.json()["answers"] == {"ao1": "是"}
    assert history.json()["total_score"] is None

    app.dependency_overrides[current_admin] = lambda: object()
    try:
        admin = await client.get(f"/api/v1/survey/admin/responses/{response_id}")
        assert admin.status_code == 200
        assert admin.json()["questions"] == original
    finally:
        app.dependency_overrides.pop(current_admin, None)


async def test_custom_template_distinguishes_a_zero_score_from_no_score(client, db):
    headers = await make_patient(db)
    template = SurveyTemplate(type="custom_scored_form", name="自建表", questions="[]")
    db.add(template)
    await db.commit()
    await db.refresh(template)
    for payload, expected in [({}, None), ({"total_score": 0}, 0)]:
        result = await client.post("/api/v1/survey/responses", headers=headers, json={"template_id": template.id, **payload})
        assert result.status_code == 200
        history = await client.get(f"/api/v1/survey/my-responses/{result.json()['id']}", headers=headers)
        assert history.json()["total_score"] == expected
    for invalid in [True, "50/100"]:
        result = await client.post("/api/v1/survey/responses", headers=headers, json={"template_id": template.id, "total_score": invalid})
        assert result.status_code == 400
