"""Original Word form installation, administrator control and access boundaries."""
import json

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.security import admin_auth_fingerprint, create_access_token, hash_password
from app.db.survey_catalog import (
    CATALOG_REVISION,
    DEMO_LIFESTYLE_TYPE,
    ORIGINAL_SURVEY_CATALOG,
    ORIGINAL_SURVEY_TYPES,
)
from app.db.survey_defaults import ensure_public_survey_templates, ensure_registration_template
from app.models.base import Base
from app.models.survey import SurveyResponse, SurveyTemplate
from app.models.user import User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def engine():
    """Catalog correction must not depend on data left by another test module."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def test_restore_five_original_forms_idempotently_and_retire_demo(client, db):
    legacy = [
        SurveyTemplate(type=kind, name="旧近似模板", questions="[]", is_active=False)
        for kind in sorted(ORIGINAL_SURVEY_TYPES)
    ]
    custom = SurveyTemplate(type="custom_food_safety", name="管理员食品安全问卷", questions="[]")
    demo = SurveyTemplate(type=DEMO_LIFESTYLE_TYPE, name="健康生活方式自测", questions="[]")
    db.add_all([*legacy, custom, demo])
    await db.commit()
    old_ids = {template.type: template.id for template in legacy}

    await ensure_public_survey_templates(db)
    await ensure_registration_template(db)
    await ensure_public_survey_templates(db)
    rows = (await db.execute(select(SurveyTemplate))).scalars().all()
    assert len(rows) == 7
    for source in ORIGINAL_SURVEY_CATALOG:
        restored = next(t for t in rows if t.type == source["type"])
        assert restored.id == old_ids[source["type"]]
        assert restored.name == source["name"]
        assert restored.is_active is True
        assert restored.catalog_revision == CATALOG_REVISION
        assert json.loads(restored.questions) == source["questions"]
    await db.refresh(demo)
    await db.refresh(custom)
    assert demo.is_active is False
    assert demo.catalog_revision == CATALOG_REVISION
    assert custom.name == "管理员食品安全问卷" and custom.is_active is True
    assert custom.catalog_revision == 0
    response = await client.get("/api/v1/survey/templates")
    assert response.status_code == 200
    assert DEMO_LIFESTYLE_TYPE not in {t["type"] for t in response.json()}
    assert ORIGINAL_SURVEY_TYPES.issubset(t["type"] for t in response.json())


async def test_first_install_creates_only_original_forms_in_source_order(client, db):
    await ensure_public_survey_templates(db)
    catalogue = await client.get("/api/v1/survey/templates")
    assert catalogue.status_code == 200
    assert [t["name"] for t in catalogue.json()] == [
        "体重管理门诊就诊信息登记表",
        "体重管理门诊病历首页",
        "体重管理门诊首诊评估表",
        "体重管理门诊防肥分数自测表",
        "体重管理门诊复诊评估表",
    ]
    assert [len(t["questions"]) for t in catalogue.json()] == [10, 21, 50, 36, 26]


async def test_catalog_revision_preserves_later_admin_edits_and_disabling(db):
    await ensure_public_survey_templates(db)
    template = await db.scalar(select(SurveyTemplate).where(SurveyTemplate.type == "weight_clinic_first"))
    edited_questions = [{"id": "admin-edit", "step": 0, "type": "textarea", "title": "管理员调整的字段"}]
    template.name = "管理员定制首诊表"
    template.description = "管理员编辑的说明"
    template.questions = json.dumps(edited_questions)
    template.is_active = False
    template.sort_order = 99
    await db.commit()
    await ensure_public_survey_templates(db)
    await ensure_registration_template(db)
    await db.refresh(template)
    assert template.name == "管理员定制首诊表"
    assert template.description == "管理员编辑的说明"
    assert json.loads(template.questions) == edited_questions
    assert template.is_active is False
    assert template.sort_order == 99


async def test_restore_freezes_old_question_wording_without_changing_answers(client, db):
    patient = User(role="patient", nickname="历史记录用户")
    old_questions = [{"id": "fv15", "step": 0, "type": "textarea", "title": "旧合并用药情况"}]
    template = SurveyTemplate(type="weight_clinic_first", name="旧近似首诊表", questions=json.dumps(old_questions))
    demo_questions = [{"id": "ls1", "type": "radio", "title": "原示范题", "options": ["经常做到", "有时做到"]}]
    demo = SurveyTemplate(type=DEMO_LIFESTYLE_TYPE, name="健康生活方式自测", questions=json.dumps(demo_questions))
    db.add_all([patient, template, demo])
    await db.flush()
    original_response = SurveyResponse(
        template_id=template.id, user_id=patient.id, template_type=template.type,
        answers=json.dumps({"fv15": "旧答案"}), total_score=0,
    )
    demo_response = SurveyResponse(
        template_id=demo.id, user_id=patient.id, template_type=demo.type,
        answers=json.dumps({"ls1": "有时做到"}), total_score=0,
    )
    already_frozen = SurveyResponse(
        template_id=template.id, user_id=patient.id, template_type=template.type,
        answers="{}", questions_snapshot='[{"id":"older","title":"更早的题目"}]', total_score=0,
    )
    db.add_all([original_response, demo_response, already_frozen])
    await db.commit()
    await ensure_public_survey_templates(db)
    await ensure_public_survey_templates(db)

    await db.refresh(original_response)
    await db.refresh(demo_response)
    await db.refresh(already_frozen)
    assert json.loads(original_response.questions_snapshot) == old_questions
    assert json.loads(original_response.answers) == {"fv15": "旧答案"}
    assert original_response.total_score == 0
    assert json.loads(demo_response.questions_snapshot) == demo_questions
    assert json.loads(already_frozen.questions_snapshot) == [{"id": "older", "title": "更早的题目"}]
    header = {"Authorization": f"Bearer {create_access_token(str(patient.id))}"}
    history = await client.get(f"/api/v1/survey/my-responses/{original_response.id}", headers=header)
    assert history.status_code == 200 and history.json()["questions"] == old_questions
    assert (await client.get(f"/api/v1/survey/templates/{demo.id}")).status_code == 404
    assert (await client.post("/api/v1/survey/responses", json={"template_id": demo.id}, headers=header)).status_code == 404
    saved_demo = await client.get(f"/api/v1/survey/my-responses/{demo_response.id}", headers=header)
    assert saved_demo.status_code == 200 and saved_demo.json()["questions"] == demo_questions


@pytest.mark.parametrize("template_type", sorted(ORIGINAL_SURVEY_TYPES))
async def test_original_form_roundtrip_never_invents_a_score(template_type, client, db):
    patient = User(role="patient", nickname="原表填写用户")
    db.add(patient)
    await db.commit()
    await ensure_public_survey_templates(db)
    template = await db.scalar(select(SurveyTemplate).where(SurveyTemplate.type == template_type))
    questions = json.loads(template.questions)
    answers = {
        q["id"]: ([q["options"][0]] if q["type"] == "checkbox" else q["options"][0])
        if q.get("options") else "原表填写内容"
        for q in questions
    }
    header = {"Authorization": f"Bearer {create_access_token(str(patient.id))}"}
    detail = await client.get(f"/api/v1/survey/templates/{template.id}")
    assert detail.status_code == 200 and detail.json()["questions"] == questions
    submitted = await client.post(
        "/api/v1/survey/responses",
        json={"template_id": template.id, "answers": answers, "total_score": 99, "user_name": "原表填写"},
        headers=header,
    )
    assert submitted.status_code == 200
    saved = await client.get(f'/api/v1/survey/my-responses/{submitted.json()["id"]}', headers=header)
    assert saved.status_code == 200
    assert saved.json()["answers"] == answers
    assert saved.json()["questions"] == questions
    assert saved.json()["total_score"] is None


async def test_survey_access_boundaries_and_admin_record_lookup(client, db):
    patient = User(role="patient", nickname="自测用户")
    other_patient = User(role="patient", nickname="另一位用户")
    admin = User(role="admin", username="survey_admin", password_hash=hash_password("Admin-test-123"))
    db.add_all([patient, other_patient, admin])
    await db.commit()
    await ensure_public_survey_templates(db)
    template = await db.scalar(select(SurveyTemplate).where(SurveyTemplate.type == "weight_visit_registration"))
    header = {"Authorization": f"Bearer {create_access_token(str(patient.id), extra={'role': 'admin'})}"}
    other_header = {"Authorization": f"Bearer {create_access_token(str(other_patient.id))}"}
    admin_header = {"Authorization": f"Bearer {create_access_token(str(admin.id), extra={'role': 'admin', 'admin_auth': admin_auth_fingerprint(admin)})}"}
    payload = {"template_id": template.id, "answers": {"name": "原表填写"}, "user_name": "原表填写"}
    assert (await client.get("/api/v1/survey/templates/NaN")).status_code == 422
    assert (await client.get("/api/v1/survey/templates/999999")).status_code == 404
    assert (await client.post("/api/v1/survey/responses", json=payload)).status_code == 401
    assert (await client.post("/api/v1/survey/responses", json={}, headers=header)).status_code == 400
    submitted = await client.post("/api/v1/survey/responses", json=payload, headers=header)
    response_id = submitted.json()["id"]
    assert (await client.get("/api/v1/survey/my-responses")).status_code == 401
    for non_owner in [other_header, admin_header]:
        assert (await client.get(f"/api/v1/survey/my-responses/{response_id}", headers=non_owner)).status_code == 404
    assert (await client.get("/api/v1/survey/my-responses", headers=other_header)).json() == []
    records = await client.get(
        "/api/v1/survey/admin/responses", params={"template_type": template.type, "keyword": "原表填写"}, headers=admin_header
    )
    assert records.status_code == 200 and [r["id"] for r in records.json()] == [response_id]
    template.is_active = False
    await db.commit()
    assert (await client.get(f"/api/v1/survey/templates/{template.id}")).status_code == 404
    assert (await client.post("/api/v1/survey/responses", json=payload, headers=header)).status_code == 404


async def test_patient_cannot_access_any_survey_admin_endpoint(client, db):
    patient = User(role="patient", nickname="越权测试用户")
    db.add(patient)
    await db.commit()
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
