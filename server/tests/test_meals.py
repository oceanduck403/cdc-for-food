"""膳食分析 & 报告"""
import pytest

pytestmark = pytest.mark.asyncio


async def _login(client, monkeypatch) -> str:
    from app.api.v1 import auth
    async def fake_exchange(code):
        assert code == 'MEAL-CODE'
        return auth.WxSessionResponse(openid='test-openid-meal', session_key='test-session')
    monkeypatch.setattr(auth, '_code2session', fake_exchange)
    r = await client.post("/api/v1/auth/wechat", json={"code": "MEAL-CODE"})
    return r.json()["token"]


async def test_qwen_food_analysis_persists_items(client, monkeypatch):
    from app.services import qwen_service

    async def fake_food(_image):
        return [{
            "name": "测试餐",
            "grams": 180,
            "kcal": 320,
            "protein": 20,
            "fat": 8,
            "carbs": 42,
            "sodium": 360,
            "confidence": 0.96,
        }]

    monkeypatch.setattr(qwen_service, "analyze_food", fake_food)
    token = await _login(client, monkeypatch)
    r = await client.post(
        "/api/v1/ai/food-analysis",
        json={"imageBase64": "data:image/jpeg;base64,ZmFrZS1pbWFnZQ=="},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["items"]
    assert "totalKcal" in data


async def test_latest_report(client, monkeypatch):
    token = await _login(client, monkeypatch)
    r = await client.get(
        "/api/v1/meals/latest/report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "structure" in body and "advice" in body
