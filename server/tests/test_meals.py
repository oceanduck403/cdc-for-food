"""膳食分析 & 报告"""
import base64
import pytest

pytestmark = pytest.mark.asyncio


async def _login(client) -> str:
    r = await client.post("/api/v1/auth/wechat", json={"code": "MEAL-CODE"})
    return r.json()["token"]


async def test_analyze_meal_returns_items(client):
    token = await _login(client)
    fake = base64.b64encode(b"fake-image-bytes").decode("ascii")
    r = await client.post(
        "/api/v1/meals/analyze",
        json={"imageBase64": fake},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["items"]
    assert "totalKcal" in data


async def test_latest_report(client):
    token = await _login(client)
    r = await client.get(
        "/api/v1/meals/latest/report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "structure" in body and "advice" in body