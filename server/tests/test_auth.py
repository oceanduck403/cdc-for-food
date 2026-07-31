"""登录与档案"""
import pytest

pytestmark = pytest.mark.asyncio


async def test_wechat_login_then_me(client):
    r = await client.post("/api/v1/auth/wechat", json={"code": "TEST-CODE"})
    assert r.status_code == 200
    token = r.json()["token"]
    assert token

    r2 = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert "id" in r2.json()