"""登录与档案"""
import pytest

pytestmark = pytest.mark.asyncio


async def test_wechat_login_then_me(client, monkeypatch):
    from app.api.v1 import auth
    async def fake_exchange(code):
        assert code == 'TEST-CODE'
        return auth.WxSessionResponse(openid='test-openid-auth', session_key='test-session')
    monkeypatch.setattr(auth, '_code2session', fake_exchange)
    r = await client.post("/api/v1/auth/wechat", json={"code": "TEST-CODE"})
    assert r.status_code == 200
    token = r.json()["token"]
    assert token

    r2 = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert "id" in r2.json()
