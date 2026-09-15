"""AI provider credentials stay server-side and endpoints require a real user."""
import pytest

from app.core.security import create_access_token
from app.models.user import User


pytestmark = pytest.mark.asyncio


async def test_ai_chat_requires_login(client):
    response = await client.post("/api/v1/ai/chat", json={"message": "怎么搭配早餐？"})
    assert response.status_code == 401


async def test_ai_chat_uses_server_gateway(client, db, monkeypatch):
    from app.api.v1 import ai

    user = User(openid="ai-gateway-user", role="patient", is_active=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(str(user.id), {"role": "patient"})
    captured = {}

    async def fake_reserve(user_id):
        captured["user_id"] = user_id
        return None

    async def fake_chat(message, mode, history):
        captured.update(message=message, mode=mode, history=history)
        return "（AI生成）早餐可搭配全谷物、鸡蛋和蔬菜。"

    monkeypatch.setattr(ai.ai_quota, "reserve", fake_reserve)
    monkeypatch.setattr(ai.qwen_service, "chat", fake_chat)
    response = await client.post(
        "/api/v1/ai/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "怎么搭配早餐？", "history": []},
    )
    assert response.status_code == 200
    assert response.json()["generatedByAi"] is True
    assert captured == {
        "user_id": str(user.id),
        "message": "怎么搭配早餐？",
        "mode": "health_consult",
        "history": [],
    }


async def test_food_gateway_parses_and_limits_provider_result(monkeypatch):
    from app.services import qwen_service

    async def fake_completion(*_args, **_kwargs):
        return '```json\n{"foods":[{"name":"米饭","grams":150},{"name":"青菜","grams":80}]}\n```'

    monkeypatch.setattr(qwen_service, "_completion", fake_completion)
    foods = await qwen_service.analyze_food("a" * 32)
    assert foods == [{"name": "米饭", "grams": 150}, {"name": "青菜", "grams": 80}]
