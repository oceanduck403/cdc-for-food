"""登记表新增、读取、提交及后台查询的回归测试（内存数据库）。"""
import json

import pytest
from sqlalchemy import select

from app.core.security import admin_auth_fingerprint, create_access_token, hash_password
from app.db.survey_defaults import REGISTRATION_QUESTIONS, REGISTRATION_TYPE, ensure_registration_template
from app.models.survey import SurveyTemplate
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def test_registration_roundtrip(client, db):
    old = SurveyTemplate(type="legacy_survey", name="原有问卷", questions="[]")
    patient = User(role="patient", nickname="测试患者")
    admin = User(role="admin", nickname="测试管理员", username="survey_admin", password_hash=hash_password("Admin-test-123"))
    db.add_all([old, patient, admin])
    await db.commit()
    await ensure_registration_template(db)
    await ensure_registration_template(db)
    templates = (await db.execute(select(SurveyTemplate).where(SurveyTemplate.type == REGISTRATION_TYPE))).scalars().all()
    assert len(templates) == 1
    assert (await db.get(SurveyTemplate, old.id)).name == "原有问卷"
    assert [q["title"] for q in REGISTRATION_QUESTIONS] == [
        "就诊日期", "登记号", "姓名", "性别", "年龄", "联系电话", "就诊诉求", "复诊日期", "接诊医生", "备注",
    ]
    response = await client.get("/api/v1/survey/templates")
    assert response.status_code == 200
    template = next(t for t in response.json() if t["type"] == REGISTRATION_TYPE)
    detail = await client.get(f'/api/v1/survey/templates/{template["id"]}')
    assert detail.status_code == 200
    assert detail.json()["questions"] == REGISTRATION_QUESTIONS
    assert (await client.get('/api/v1/survey/templates/NaN')).status_code == 422

    answers = {q["id"]: "测试填写" for q in REGISTRATION_QUESTIONS}
    answers.update(visit_date="2026-09-12", follow_up_date="2026-10-12", sex="女", age="35")
    # Even a signed token carrying a forged role claim cannot override the
    # persisted patient role.
    header = {
        "Authorization": f"Bearer {create_access_token(str(patient.id), extra={'role': 'admin'})}"
    }
    payload = dict(template_id=template["id"], answers=answers, user_name="测试填写", user_phone="028-00000000")
    assert (await client.post('/api/v1/survey/responses', json=payload)).status_code == 401
    submitted = await client.post('/api/v1/survey/responses', json=payload, headers=header)
    assert submitted.status_code == 200
    response_id = submitted.json()["id"]
    saved = await client.get(f'/api/v1/survey/my-responses/{response_id}', headers=header)
    assert saved.status_code == 200
    assert saved.json()["answers"] == answers
    assert saved.json()["questions"] == REGISTRATION_QUESTIONS
    assert saved.json()["template_name"] == template["name"]
    admin_token = create_access_token(str(admin.id), extra={"role": "admin", "admin_auth": admin_auth_fingerprint(admin)})
    other_header = {"Authorization": f"Bearer {admin_token}"}
    assert (await client.get(f'/api/v1/survey/my-responses/{response_id}', headers=other_header)).status_code == 404
    history = await client.get('/api/v1/survey/my-responses', headers=header)
    assert any(r['id'] == response_id for r in history.json())
    records = await client.get('/api/v1/survey/admin/responses', params={"template_type": REGISTRATION_TYPE, "keyword": "测试填写"}, headers=other_header)
    assert records.status_code == 200
    assert [r['id'] for r in records.json()] == [response_id]
    assert records.json()[0]['answers'] == answers


async def test_registration_default_preserves_admin_edits(db):
    await ensure_registration_template(db)
    template = await db.scalar(select(SurveyTemplate).where(SurveyTemplate.type == REGISTRATION_TYPE))
    template.description = "管理员编辑的说明"
    template.is_active = False
    await db.commit()
    await ensure_registration_template(db)
    await db.refresh(template)
    assert template.description == "管理员编辑的说明"
    assert template.is_active is False


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
