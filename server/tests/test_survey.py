"""公开健康生活方式自测、历史问卷及访问边界回归（隔离内存数据库）。"""
import json

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.security import admin_auth_fingerprint, create_access_token, hash_password
from app.db.survey_defaults import (
    DISABLED_DEFAULT_TEMPLATE_TYPES,
    LIFESTYLE_QUESTIONS,
    LIFESTYLE_TEMPLATE,
    LIFESTYLE_TYPE,
    ensure_public_survey_templates,
    ensure_registration_template,
)
from app.models.base import Base
from app.models.survey import SurveyResponse, SurveyTemplate
from app.models.user import User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def engine():
    """默认目录初始化会修改模板，不能依赖其他测试留下的共享数据。"""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def test_lifestyle_questionnaire_has_twelve_non_clinical_questions():
    assert len(LIFESTYLE_QUESTIONS) == 12
    assert len({q["id"] for q in LIFESTYLE_QUESTIONS}) == 12
    assert [sum(q["step"] == step for q in LIFESTYLE_QUESTIONS) for step in range(3)] == [5, 3, 4]
    assert all(q["type"] == "radio" and q["title"] for q in LIFESTYLE_QUESTIONS)
    assert all(q["options"] == ["经常做到", "有时做到", "较少做到"] for q in LIFESTYLE_QUESTIONS)
    titles = " ".join(q["title"] for q in LIFESTYLE_QUESTIONS)
    for topic in ["蔬菜", "白水", "身体活动", "睡眠", "生熟", "保质期"]:
        assert topic in titles
    assert "不作为医疗结论" in LIFESTYLE_TEMPLATE["description"]
    assert not {"visit_date", "follow_up_date", "doctor", "name", "phone"}.intersection(
        q["id"] for q in LIFESTYLE_QUESTIONS
    )


async def test_public_defaults_are_idempotent_and_disable_legacy_templates(db):
    legacy_templates = [
        SurveyTemplate(type=kind, name=f"历史模板 {kind}", questions="[]", is_active=True)
        for kind in sorted(DISABLED_DEFAULT_TEMPLATE_TYPES)
    ]
    custom = SurveyTemplate(type="custom_food_safety", name="管理员食品安全问卷", questions="[]")
    db.add_all([*legacy_templates, custom])
    await db.commit()

    await ensure_public_survey_templates(db)
    # Older deployment scripts retain this entry point and must get the same catalogue.
    await ensure_registration_template(db)
    await ensure_public_survey_templates(db)

    templates = (await db.execute(select(SurveyTemplate))).scalars().all()
    lifestyle = [t for t in templates if t.type == LIFESTYLE_TYPE]
    assert len(lifestyle) == 1
    assert lifestyle[0].is_active is True
    assert json.loads(lifestyle[0].questions) == LIFESTYLE_QUESTIONS
    assert len(templates) == len(legacy_templates) + 2
    for template in legacy_templates:
        await db.refresh(template)
        assert template.is_active is False
        assert template.name == f"历史模板 {template.type}"
    await db.refresh(custom)
    assert custom.name == "管理员食品安全问卷"
    assert custom.is_active is True


async def test_public_defaults_restore_canonical_self_check_only(db):
    await ensure_public_survey_templates(db)
    lifestyle = await db.scalar(select(SurveyTemplate).where(SurveyTemplate.type == LIFESTYLE_TYPE))
    lifestyle.name = "过期默认模板"
    lifestyle.description = "过期说明"
    lifestyle.questions = "[]"
    lifestyle.is_active = False
    custom = SurveyTemplate(
        type="custom_disabled", name="管理员停用的问卷", description="保留管理员设置", questions="[]", is_active=False
    )
    db.add(custom)
    await db.commit()

    await ensure_public_survey_templates(db)
    await db.refresh(lifestyle)
    await db.refresh(custom)
    assert lifestyle.name == LIFESTYLE_TEMPLATE["name"]
    assert lifestyle.description == LIFESTYLE_TEMPLATE["description"]
    assert json.loads(lifestyle.questions) == LIFESTYLE_QUESTIONS
    assert lifestyle.is_active is True
    assert custom.description == "保留管理员设置"
    assert custom.is_active is False


async def test_lifestyle_roundtrip_and_response_access_boundaries(client, db):
    patient = User(role="patient", nickname="自测用户")
    other_patient = User(role="patient", nickname="另一位用户")
    admin = User(role="admin", nickname="测试管理员", username="survey_admin", password_hash=hash_password("Admin-test-123"))
    db.add_all([patient, other_patient, admin])
    await db.commit()
    await ensure_public_survey_templates(db)

    response = await client.get("/api/v1/survey/templates")
    assert response.status_code == 200
    assert len(response.json()) == 1
    template = response.json()[0]
    assert template["type"] == LIFESTYLE_TYPE
    assert template["name"] == "健康生活方式自测"
    assert template["questions"] == LIFESTYLE_QUESTIONS
    detail = await client.get(f'/api/v1/survey/templates/{template["id"]}')
    assert detail.status_code == 200
    assert detail.json() == template
    assert (await client.get("/api/v1/survey/templates/NaN")).status_code == 422
    assert (await client.get("/api/v1/survey/templates/999999")).status_code == 404

    answers = {q["id"]: q["options"][i % 3] for i, q in enumerate(LIFESTYLE_QUESTIONS)}
    # A signed token carrying a forged role cannot override the stored patient role.
    header = {"Authorization": f"Bearer {create_access_token(str(patient.id), extra={'role': 'admin'})}"}
    other_header = {"Authorization": f"Bearer {create_access_token(str(other_patient.id))}"}
    admin_token = create_access_token(str(admin.id), extra={"role": "admin", "admin_auth": admin_auth_fingerprint(admin)})
    admin_header = {"Authorization": f"Bearer {admin_token}"}
    payload = dict(template_id=template["id"], answers=answers, user_name="自测填写", submitted_at="2026-10-12")
    assert (await client.post("/api/v1/survey/responses", json=payload)).status_code == 401
    assert (await client.post("/api/v1/survey/responses", json={}, headers=header)).status_code == 400
    submitted = await client.post("/api/v1/survey/responses", json=payload, headers=header)
    assert submitted.status_code == 200
    response_id = submitted.json()["id"]

    saved = await client.get(f"/api/v1/survey/my-responses/{response_id}", headers=header)
    assert saved.status_code == 200
    assert saved.json()["answers"] == answers
    assert saved.json()["questions"] == LIFESTYLE_QUESTIONS
    assert saved.json()["template_name"] == template["name"]
    assert (await client.get("/api/v1/survey/my-responses")).status_code == 401
    assert (await client.get(f"/api/v1/survey/my-responses/{response_id}")).status_code == 401
    for non_owner in [other_header, admin_header]:
        assert (await client.get(f"/api/v1/survey/my-responses/{response_id}", headers=non_owner)).status_code == 404
    assert (await client.get("/api/v1/survey/my-responses", headers=other_header)).json() == []
    history = await client.get("/api/v1/survey/my-responses", headers=header)
    assert history.status_code == 200
    assert [r["id"] for r in history.json()] == [response_id]
    assert (await client.get("/api/v1/survey/admin/templates", headers=header)).status_code == 403
    records = await client.get(
        "/api/v1/survey/admin/responses", params={"template_type": LIFESTYLE_TYPE, "keyword": "自测填写"}, headers=admin_header
    )
    assert records.status_code == 200
    assert [r["id"] for r in records.json()] == [response_id]
    assert records.json()[0]["answers"] == answers


async def test_disabled_legacy_hidden_but_historical_response_remains_readable(client, db):
    patient = User(role="patient", nickname="历史记录用户")
    questions = [{"id": "old1", "type": "text", "title": "历史题目"}]
    legacy = SurveyTemplate(type="weight_visit_registration", name="旧登记表", questions=json.dumps(questions), is_active=True)
    db.add_all([patient, legacy])
    await db.flush()
    historical = SurveyResponse(
        template_id=legacy.id, user_id=patient.id, template_type=legacy.type, answers=json.dumps({"old1": "历史答案"})
    )
    db.add(historical)
    await db.commit()
    await ensure_public_survey_templates(db)
    header = {"Authorization": f"Bearer {create_access_token(str(patient.id))}"}

    catalogue = await client.get("/api/v1/survey/templates")
    assert catalogue.status_code == 200
    assert [t["type"] for t in catalogue.json()] == [LIFESTYLE_TYPE]
    assert (await client.get(f"/api/v1/survey/templates/{legacy.id}")).status_code == 404
    submit = await client.post("/api/v1/survey/responses", json={"template_id": legacy.id, "answers": {}}, headers=header)
    assert submit.status_code == 404
    detail = await client.get(f"/api/v1/survey/my-responses/{historical.id}", headers=header)
    assert detail.status_code == 200
    assert detail.json()["template_name"] == "旧登记表"
    assert detail.json()["answers"] == {"old1": "历史答案"}
    assert detail.json()["questions"] == questions
    assert await db.scalar(select(SurveyResponse.id).where(SurveyResponse.id == historical.id)) == historical.id


async def test_patient_cannot_access_any_survey_admin_endpoint(client, db):
    patient = User(role="patient", nickname="越权测试患者")
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    header = {"Authorization": f"Bearer {create_access_token(str(patient.id))}"}

    requests = [
        ("GET", "/api/v1/survey/admin/templates", None),
        ("POST", "/api/v1/survey/admin/templates", {"name": "越权", "type": "forbidden"}),
        ("PUT", "/api/v1/survey/admin/templates/1", {"name": "越权"}),
        ("DELETE", "/api/v1/survey/admin/templates/1", None),
        ("GET", "/api/v1/survey/admin/responses", None),
        ("GET", "/api/v1/survey/admin/responses/1", None),
    ]

    for method, url, payload in requests:
        response = await client.request(method, url, json=payload, headers=header)
        assert response.status_code == 403, (method, url, response.text)
        assert response.json()["detail"] == "需要管理员权限"
