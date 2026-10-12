"""AI provider credentials stay server-side and endpoints require a real user."""
import base64
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
import json

import httpx
import pytest
from PIL import Image

from app.core.errors import BusinessError
from app.core.security import create_access_token
from app.models.user import User


pytestmark = pytest.mark.asyncio


def food_image_base64() -> str:
    buffer = BytesIO()
    Image.new("RGB", (64, 48), "#e4f0da").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


@pytest.fixture
def install_qwen_transport(monkeypatch):
    """Exercise the real gateway payload without contacting a paid provider."""
    from app.services import qwen_service

    real_client = httpx.AsyncClient
    monkeypatch.setattr(qwen_service.settings, "qwen_api_key", "server-only-test-key")
    monkeypatch.setattr(qwen_service.settings, "qwen_base_url", "https://provider.example/compatible-mode/v1/")
    monkeypatch.setattr(qwen_service.settings, "qwen_model", "qwen3.8-27b")

    def install(handler):
        requests = []

        def capture(request):
            requests.append(request)
            return handler(request)

        def mock_client(*args, **kwargs):
            return real_client(*args, transport=httpx.MockTransport(capture), **kwargs)

        monkeypatch.setattr(qwen_service.httpx, "AsyncClient", mock_client)
        return requests

    return install


@pytest.mark.parametrize("operation", ["chat", "food", "survey", "daily"])
async def test_qwen38_operations_use_shared_non_thinking_gateway(operation, install_qwen_transport):
    from app.services import qwen_service

    content = '{"foods":[]}' if operation == "food" else "（AI生成）均衡搭配日常饮食。"
    requests = install_qwen_transport(
        lambda _request: httpx.Response(200, json={
            "choices": [{"message": {"content": content, "reasoning_content": "private reasoning"}}],
        })
    )
    if operation == "chat":
        result = await qwen_service.chat("怎么搭配早餐？", "health_consult", [])
    elif operation == "food":
        result = await qwen_service.analyze_food(food_image_base64())
    elif operation == "survey":
        result = await qwen_service.analyze_survey("healthy_lifestyle_self_check", {"breakfast": "每天"})
    else:
        result = await qwen_service.daily_suggestion({"water": 1200}, {})

    assert result == ([] if operation == "food" else content)
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://provider.example/compatible-mode/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer server-only-test-key"
    payload = json.loads(request.content)
    assert payload["model"] == "qwen3.8-27b"
    assert payload["enable_thinking"] is False
    assert not payload.get("stream", False)
    assert "server-only-test-key" not in request.content.decode()
    assert "private reasoning" not in str(result)
    if operation == "food":
        assert payload["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        assert payload["max_tokens"] == 900
    elif operation == "chat":
        assert payload["messages"][-1] == {"role": "user", "content": "怎么搭配早餐？"}
        assert payload["max_tokens"] == 1000


@pytest.mark.parametrize("model, expected", [
    ("qwen3.8-max", False),
    ("qwen3.8-max-0902", False),
    ("qwen3.8-flash", False),
    ("qwen-vl-plus", None),
    ("qwen-vl-max", None),
    ("qwen3.8-2.4t-a95b", None),
    ("qwen3.8-omni-flash", None),
])
async def test_gateway_thinking_extension_preserves_other_model_protocols(
    model, expected, monkeypatch, install_qwen_transport,
):
    from app.services import qwen_service

    requests = install_qwen_transport(
        lambda _request: httpx.Response(200, json={"choices": [{"message": {"content": "答复"}}]})
    )
    monkeypatch.setattr(qwen_service.settings, "qwen_model", model)
    assert await qwen_service.chat("你好", "health_consult", []) == "答复"
    payload = json.loads(requests[0].content)
    if expected is None:
        assert "enable_thinking" not in payload
    else:
        assert payload["enable_thinking"] is expected


@pytest.mark.parametrize("mode", ["health_consult", "diet_guide"])
async def test_label_question_grounds_real_provider_with_verified_sources_and_corrects_history(
    mode, install_qwen_transport,
):
    from app.services import qwen_service

    provider_answer = "（AI生成）本次由模型结合您提供的标签回答。"
    requests = install_qwen_transport(
        lambda _request: httpx.Response(200, json={"choices": [{"message": {"content": provider_answer}}]})
    )
    history = [
        {"role": "user", "content": "买食品怎么看营养成分表？"},
        {"role": "assistant", "content": "钠低于400mg/100g就是低钠，营养成分排前三位说明含量高。"},
    ]
    question = "营养成分表每份钠120mg算低钠吗？碳水化合物是不是糖，排前三的都高吗？"
    reply = await qwen_service.chat(question, mode, history)

    # The gateway still calls the actual completion path and returns its answer;
    # these references are provider context, not a canned replacement response.
    assert len(requests) == 1
    assert reply == provider_answer
    payload = json.loads(requests[0].content)
    system = payload["messages"][0]["content"]
    assert "钠≤120 mg/100 g或100 mL" in system
    assert "包含等于120" in system
    assert "不能用每份钠≤120 mg直接判定符合" in system
    assert "个人每日摄入上限" in system
    assert "先统一计量基准" in system and "实际含量和NRV%" in system
    assert "不是该营养素占食品重量的比例" in system
    assert "行顺序按标准排列，不代表含量高低" in system
    assert "配料排名不能直接给出脂肪、糖或钠的含量" in system
    assert "碳水化合物包括糖、寡糖和多糖" in system
    assert "不能把“碳水化合物”数值直接当成糖或添加糖的含量" in system
    assert "缺少计量基准或具体数值" in system and "不能猜测" in system
    assert "以这些资料为准并简短纠正此前错误" in system
    assert "附上支持相关结论的官方来源链接" in system
    assert "https://www.nhc.gov.cn/ewebeditor/uploadfile/2013/06/20130605104041625.pdf" in system
    assert "https://www.nhc.gov.cn/zwgk/zcjd/201402/6f68ec6692594cf28d190cb47b770c11.shtml" in system
    assert "400mg" not in system
    assert payload["messages"][1:3] == history
    assert payload["messages"][-1] == {"role": "user", "content": question}
    assert payload["temperature"] == 0.2
    assert payload["enable_thinking"] is False and payload["max_tokens"] == 1000
    assert "server-only-test-key" not in reply


@pytest.mark.parametrize("question", [
    "营养标签怎么读？", "食品标签怎么看？", "营养成分表需要注意什么？",
    "配料表和营养表一样吗？", "nrv%是什么意思？", "低钠的条件是什么？", "低盐食品怎么选？",
])
async def test_label_terms_select_verified_context(question, install_qwen_transport):
    from app.services import qwen_service

    requests = install_qwen_transport(
        lambda _request: httpx.Response(200, json={"choices": [{"message": {"content": "模型答复"}}]})
    )
    await qwen_service.chat(question, "health_consult", [])
    payload = json.loads(requests[0].content)
    assert "GB 28050-2011" in payload["messages"][0]["content"]
    assert payload["temperature"] == 0.2


async def test_unrelated_chat_does_not_inherit_label_context_from_old_history(install_qwen_transport):
    from app.services import qwen_service

    requests = install_qwen_transport(
        lambda _request: httpx.Response(200, json={"choices": [{"message": {"content": "新的模型答复"}}]})
    )
    history = [{"role": "user", "content": "配料表怎么看？"}]
    assert await qwen_service.chat("每天散步怎么安排？", "health_consult", history) == "新的模型答复"
    payload = json.loads(requests[0].content)
    assert payload["messages"][0]["content"] == qwen_service.SYSTEM_PROMPTS["health_consult"]
    assert "nhc.gov.cn" not in payload["messages"][0]["content"]
    assert payload["temperature"] == 0.6
    assert payload["messages"][1] == history[0]


@pytest.mark.parametrize("failure", ["unauthorized", "timeout"])
async def test_upstream_failures_do_not_expose_credentials_to_client(
    failure, client, db, monkeypatch, install_qwen_transport,
):
    from app.api.v1 import ai

    user = User(openid=f"ai-secret-{failure}", role="patient", is_active=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(str(user.id), {"role": "patient"})

    async def no_limit(_db, _user_id):
        return None

    def provider(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("provider echoed server-only-test-key", request=request)
        return httpx.Response(401, json={"error": {"message": "invalid key server-only-test-key"}})

    monkeypatch.setattr(ai.ai_quota, "reserve", no_limit)
    install_qwen_transport(provider)
    response = await client.post(
        "/api/v1/ai/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "怎么搭配早餐？"},
    )
    assert response.status_code == 502
    assert response.json() == {
        "code": "AI_UPSTREAM_ERROR", "message": "AI 服务暂时不可用，请稍后重试", "data": None,
    }
    assert "server-only-test-key" not in response.text
    assert "provider.example" not in response.text


async def test_original_survey_analysis_sends_source_questions_and_answers(install_qwen_transport):
    from app.services import qwen_service

    requests = install_qwen_transport(
        lambda _request: httpx.Response(200, json={"choices": [{"message": {"content": "（AI生成）建议逐步改善习惯。"}}]})
    )
    # Deliberately reverse input order and include an unrecognised legacy field.
    reply = await qwen_service.analyze_survey("weight_anti_obesity", {
        "ao36": "是", "unknown_legacy_id": "must-not-be-interpreted", "ao1": "否", "ao2": "",
    })
    assert reply == "（AI生成）建议逐步改善习惯。"
    payload = json.loads(requests[0].content)
    system, user = payload["messages"]
    assert "未提供评分规则" in system["content"]
    assert "不得编造分数、权重、阈值" in system["content"]
    context = json.loads(user["content"].split("\n", 1)[0].split("：", 1)[1])
    assert context["surveyName"] == "体重管理门诊防肥分数自测表"
    assert context["scoringRules"] is None
    assert context["answeredQuestions"] == [
        {"questionId": "ao1", "questionNumber": 1, "section": "一、有关饮品",
         "originalQuestion": "不喝甜饮料和奶茶等甜味饮品，用白水、淡茶水、淡柠檬水等替代", "answer": "否"},
        {"questionId": "ao36", "questionNumber": 36, "section": "十一、有关身体管理和自我感觉",
         "originalQuestion": "注意衣服松紧程度的变化、体力的上升和面容气色的变化", "answer": "是"},
    ]
    assert 2 in context["unansweredQuestionNumbers"]
    assert context["unknownQuestionIds"] == ["unknown_legacy_id"]
    assert "must-not-be-interpreted" not in user["content"]
    assert payload["temperature"] == 0.4 and payload["max_tokens"] == 1400
    assert payload["enable_thinking"] is False


async def test_original_survey_analysis_preserves_matrix_context_and_units(install_qwen_transport):
    from app.services import qwen_service

    requests = install_qwen_transport(
        lambda _request: httpx.Response(200, json={"choices": [{"message": {"content": "（AI生成）按所填信息记录。"}}]})
    )
    await qwen_service.analyze_survey("weight_clinic_first", {
        "fv15_hypertension": "已有药物记录", "fv33": "50",
    })
    payload = json.loads(requests[0].content)
    context = json.loads(payload["messages"][1]["content"].split("\n", 1)[0].split("：", 1)[1])
    medications, alcohol = context["answeredQuestions"]
    assert medications["originalQuestion"] == "用药情况"
    assert "高血压" in medications["hint"]
    assert medications["section"] == "健康与病史"
    assert alcohol["originalQuestion"] == "平均每次大概喝酒"
    assert alcohol["unit"] == "ml" and alcohol["answer"] == "50"


async def test_unknown_survey_does_not_guess_question_ids(install_qwen_transport):
    from app.services import qwen_service

    requests = install_qwen_transport(
        lambda _request: httpx.Response(200, json={"choices": [{"message": {"content": "尚无可对应原题的信息。"}}]})
    )
    assert await qwen_service.analyze_survey("unknown_survey", {"q1": "private-unlabelled-value"}) == "尚无可对应原题的信息。"
    payload = json.loads(requests[0].content)
    message = payload["messages"][1]["content"]
    context = json.loads(message.split("\n", 1)[0].split("：", 1)[1])
    assert context["answeredQuestions"] == []
    assert context["unknownQuestionIds"] == ["q1"]
    assert "private-unlabelled-value" not in message
    assert "信息不足，不生成个人评估" in message


async def test_oversized_survey_is_rejected_without_partial_provider_analysis(monkeypatch):
    from app.services import qwen_service

    async def must_not_call(*_args, **_kwargs):
        pytest.fail("Oversized answers must not be silently truncated and sent upstream")

    monkeypatch.setattr(qwen_service, "_completion", must_not_call)
    with pytest.raises(BusinessError) as raised:
        await qwen_service.analyze_survey("weight_anti_obesity", {"ao1": "较长的说明" * 3000})
    assert raised.value.code == "AI_SURVEY_TOO_LARGE"


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

    async def fake_reserve(_db, user_id):
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


async def test_ai_quota_is_persisted_and_failed_call_releases(client, db, monkeypatch):
    from app.api.v1 import ai
    from app.models.ai_usage import AiUsageEvent
    from sqlalchemy import func, select

    user = User(openid="ai-quota-user", role="patient", is_active=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(str(user.id), {"role": "patient"})

    async def provider_failure(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(ai.qwen_service, "chat", provider_failure)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        await client.post(
            "/api/v1/ai/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "怎么搭配早餐？", "history": []},
        )
    remaining = await db.scalar(
        select(func.count(AiUsageEvent.id)).where(AiUsageEvent.user_id == user.id)
    )
    assert remaining == 0


async def test_quota_endpoint_counts_usage_events_not_last_active_date(client, db):
    from app.config import settings
    from app.models.ai_usage import AiUsageEvent

    user = User(
        openid="quota-read-user",
        role="patient",
        is_active=True,
        # This field belongs to the retired payment limiter and must not make a
        # user appear to have consumed the whole day's AI allowance.
        last_active_on=date.today(),
    )
    db.add(user)
    await db.flush()
    db.add_all(
        [
            AiUsageEvent(user_id=user.id),
            AiUsageEvent(user_id=user.id),
            AiUsageEvent(
                user_id=user.id,
                created_at=datetime.now(timezone.utc) - timedelta(days=2),
            ),
        ]
    )
    await db.commit()
    token = create_access_token(str(user.id), {"role": "patient"})

    response = await client.get(
        "/api/v1/users/me/quota",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "used": 2,
        "remaining": settings.daily_analysis_limit_per_user - 2,
        "limit": settings.daily_analysis_limit_per_user,
        "is_vip": False,
        "expire_at": None,
    }


async def test_ai_daily_limit_rejects_before_provider_call(client, db, monkeypatch):
    from app.api.v1 import ai
    from app.models.ai_usage import AiUsageEvent

    user = User(openid="quota-limit-user", role="patient", is_active=True)
    db.add(user)
    await db.flush()
    db.add_all([AiUsageEvent(user_id=user.id), AiUsageEvent(user_id=user.id)])
    await db.commit()
    token = create_access_token(str(user.id), {"role": "patient"})
    monkeypatch.setattr(ai.ai_quota.settings, "daily_analysis_limit_per_user", 2)

    provider_called = False

    async def provider(*_args, **_kwargs):
        nonlocal provider_called
        provider_called = True
        return "不应调用"

    monkeypatch.setattr(ai.qwen_service, "chat", provider)
    response = await client.post(
        "/api/v1/ai/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "还能继续吗？", "history": []},
    )
    assert response.status_code == 429, response.text
    assert provider_called is False


async def test_food_gateway_parses_and_limits_provider_result(monkeypatch):
    from app.services import qwen_service

    async def fake_completion(*_args, **_kwargs):
        return '```json\n{"foods":[{"name":"米饭","grams":150},{"name":"青菜","grams":80}]}\n```'

    monkeypatch.setattr(qwen_service, "_completion", fake_completion)
    foods = await qwen_service.analyze_food(food_image_base64())
    assert foods == [
        {"name": "米饭", "grams": 150, "kcal": 0.0, "protein": 0.0, "fat": 0.0,
         "carbs": 0.0, "sodium": 0.0, "confidence": 0.0},
        {"name": "青菜", "grams": 80, "kcal": 0.0, "protein": 0.0, "fat": 0.0,
         "carbs": 0.0, "sodium": 0.0, "confidence": 0.0},
    ]


async def test_food_gateway_reencodes_image_without_metadata(monkeypatch):
    from app.services import qwen_service

    captured = {}

    async def fake_completion(messages, **_kwargs):
        captured["url"] = messages[0]["content"][1]["image_url"]["url"]
        return '{"foods":[]}'

    source = BytesIO()
    Image.new("RGBA", (1800, 900), (80, 160, 90, 128)).save(
        source,
        format="PNG",
        pnginfo=None,
    )
    monkeypatch.setattr(qwen_service, "_completion", fake_completion)

    assert await qwen_service.analyze_food(base64.b64encode(source.getvalue()).decode("ascii")) == []
    assert captured["url"].startswith("data:image/jpeg;base64,")
    normalized = base64.b64decode(captured["url"].split(",", 1)[1], validate=True)
    with Image.open(BytesIO(normalized)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert image.size == (1600, 800)
        assert not image.getexif()


@pytest.mark.parametrize(
    "payload",
    [
        "not-valid-base64!",
        base64.b64encode(b"not an image").decode("ascii"),
        "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==",
    ],
)
async def test_food_gateway_rejects_invalid_or_unsupported_images(payload):
    from app.services import qwen_service

    with pytest.raises(BusinessError) as raised:
        await qwen_service.analyze_food(payload)
    assert raised.value.code == "INVALID_IMAGE"


async def test_food_endpoint_persists_meal_for_report(client, db, monkeypatch):
    from app.api.v1 import ai
    from app.models.meal import Meal, MealItem
    from sqlalchemy import select

    user = User(openid="food-analysis-user", role="patient", is_active=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(str(user.id), {"role": "patient"})

    async def no_limit(_db, _user_id):
        return None

    async def analyzed(_image):
        return [{"name": "米饭", "grams": 150, "kcal": 195, "protein": 4,
                 "fat": 0.5, "carbs": 42, "sodium": 3, "confidence": 0}]

    monkeypatch.setattr(ai.ai_quota, "reserve", no_limit)
    monkeypatch.setattr(ai.qwen_service, "analyze_food", analyzed)
    response = await client.post(
        "/api/v1/ai/food-analysis",
        headers={"Authorization": f"Bearer {token}"},
        json={"imageBase64": "a" * 32},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mealId"] and payload["totalKcal"] == 195
    meal = await db.get(Meal, payload["mealId"])
    item = (await db.execute(select(MealItem).where(MealItem.meal_id == meal.id))).scalar_one()
    assert meal.user_id == user.id and item.name == "米饭"
