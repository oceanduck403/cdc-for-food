"""Public comments must pass WeChat's text content security check in production."""
import pytest

from app.services import wechat_content_security as security


pytestmark = pytest.mark.asyncio


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _Client:
    def __init__(self, responses, calls, **_kwargs):
        self.responses = responses
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _Response(self.responses.pop(0))


async def test_text_security_passes_openid_and_content(monkeypatch):
    responses = [
        {"access_token": "temporary-token", "expires_in": 7200},
        {"errcode": 0, "result": {"suggest": "pass"}},
    ]
    calls = []
    monkeypatch.setattr(security.settings, "app_env", "production")
    monkeypatch.setattr(security.settings, "wechat_appid", "wx-test")
    monkeypatch.setattr(security.settings, "wechat_secret", "secret-test")
    monkeypatch.setattr(security.httpx, "AsyncClient", lambda **kw: _Client(responses, calls, **kw))
    security._token_cache.value = ""
    security._token_cache.expires_at = 0

    await security.check_public_text("清淡饮食很实用", "openid-test")

    assert len(calls) == 2
    assert calls[1][1]["json"] == {
        "content": "清淡饮食很实用",
        "version": 2,
        "scene": 2,
        "openid": "openid-test",
    }


async def test_text_security_rejects_risky_content(monkeypatch):
    responses = [{"errcode": 0, "result": {"suggest": "risky"}}]
    calls = []
    monkeypatch.setattr(security.settings, "app_env", "production")
    monkeypatch.setattr(security.httpx, "AsyncClient", lambda **kw: _Client(responses, calls, **kw))
    security._token_cache.value = "cached-token"
    security._token_cache.expires_at = security.time.monotonic() + 300

    with pytest.raises(security.ContentSecurityRejected):
        await security.check_public_text("风险文本", "openid-test")


async def test_text_security_rejects_blocked_content(monkeypatch):
    responses = [{"errcode": 0, "result": {"suggest": "block"}}]
    calls = []
    monkeypatch.setattr(security.settings, "app_env", "production")
    monkeypatch.setattr(security.httpx, "AsyncClient", lambda **kw: _Client(responses, calls, **kw))
    security._token_cache.value = "cached-token"
    security._token_cache.expires_at = security.time.monotonic() + 300

    with pytest.raises(security.ContentSecurityRejected):
        await security.check_public_text("禁止展示的文本", "openid-test")


async def test_text_security_fails_closed_without_openid(monkeypatch):
    monkeypatch.setattr(security.settings, "app_env", "production")
    with pytest.raises(security.ContentSecurityUnavailable):
        await security.check_public_text("公开评论", None)


async def test_text_security_refreshes_expired_token_once(monkeypatch):
    responses = [
        {"errcode": 40001, "errmsg": "invalid credential"},
        {"access_token": "fresh-token", "expires_in": 7200},
        {"errcode": 0, "result": {"suggest": "pass"}},
    ]
    calls = []
    monkeypatch.setattr(security.settings, "app_env", "production")
    monkeypatch.setattr(
        security.httpx, "AsyncClient", lambda **kw: _Client(responses, calls, **kw)
    )
    security._token_cache.value = "expired-token"
    security._token_cache.expires_at = security.time.monotonic() + 300

    await security.check_public_text("正常健康评论", "openid-test")

    assert len(calls) == 3
    assert calls[0][1]["params"]["access_token"] == "expired-token"
    assert calls[1][1]["json"]["force_refresh"] is True
    assert calls[2][1]["params"]["access_token"] == "fresh-token"


async def test_text_security_fails_closed_on_malformed_response(monkeypatch):
    responses = [["not", "an", "object"]]
    calls = []
    monkeypatch.setattr(security.settings, "app_env", "production")
    monkeypatch.setattr(
        security.httpx, "AsyncClient", lambda **kw: _Client(responses, calls, **kw)
    )
    security._token_cache.value = "cached-token"
    security._token_cache.expires_at = security.time.monotonic() + 300

    with pytest.raises(security.ContentSecurityUnavailable):
        await security.check_public_text("公开评论", "openid-test")


async def test_image_security_sends_bounded_jpeg(monkeypatch):
    from io import BytesIO

    from PIL import Image

    source = BytesIO()
    Image.new("RGB", (1600, 2400), "#d7eef8").save(source, format="JPEG")
    responses = [{"errcode": 0, "errmsg": "ok"}]
    calls = []
    monkeypatch.setattr(security.settings, "app_env", "production")
    monkeypatch.setattr(
        security.httpx, "AsyncClient", lambda **kw: _Client(responses, calls, **kw)
    )
    security._token_cache.value = "cached-token"
    security._token_cache.expires_at = security.time.monotonic() + 300

    await security.check_uploaded_image(source.getvalue())

    assert len(calls) == 1
    assert calls[0][0] == security.IMAGE_CHECK_URL
    filename, checked, content_type = calls[0][1]["files"]["media"]
    assert filename == "upload.jpg"
    assert content_type == "image/jpeg"
    assert len(checked) <= 1024 * 1024
    with Image.open(BytesIO(checked)) as reviewed:
        assert reviewed.width <= 750
        assert reviewed.height <= 1334


async def test_image_security_rejects_risky_image(monkeypatch):
    from io import BytesIO

    from PIL import Image

    source = BytesIO()
    Image.new("RGB", (32, 32), "white").save(source, format="JPEG")
    responses = [{"errcode": 87014, "errmsg": "risky content"}]
    calls = []
    monkeypatch.setattr(security.settings, "app_env", "production")
    monkeypatch.setattr(
        security.httpx, "AsyncClient", lambda **kw: _Client(responses, calls, **kw)
    )
    security._token_cache.value = "cached-token"
    security._token_cache.expires_at = security.time.monotonic() + 300

    with pytest.raises(security.ContentSecurityRejected):
        await security.check_uploaded_image(source.getvalue())
