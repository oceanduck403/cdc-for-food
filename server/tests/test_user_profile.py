"""患者资料编辑与头像上传回归测试。"""
from io import BytesIO
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from PIL import Image

from app.core.security import create_access_token
from app.models.user import User
from app.services.media_service import delete_managed_media, media_path_for_reference

pytestmark = pytest.mark.asyncio


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (640, 400), "#7cb8d0").save(buffer, "PNG")
    return buffer.getvalue()


async def patient_session(db):
    user = User(openid=f"test-profile-{uuid4().hex}", role="patient", nickname="旧昵称")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(subject=str(user.id), extra={"role": "patient"})
    return user, {"Authorization": f"Bearer {token}"}


async def test_edit_nickname_and_avatar_persists(client, db):
    user, headers = await patient_session(db)
    avatar_reference = None
    try:
        updated = await client.put("/api/v1/users/me", json={"nickname": "  新昵称  "}, headers=headers)
        assert updated.status_code == 200
        assert updated.json()["nickname"] == "新昵称"

        upload = await client.post(
            "/api/v1/users/me/avatar",
            files={"file": ("avatar.png", png_bytes(), "application/octet-stream")},
            headers=headers,
        )
        assert upload.status_code == 200
        avatar = upload.json()["avatar"]
        assert avatar.startswith("/api/v1/media/avatar/")
        signed = urlsplit(avatar)
        query = parse_qs(signed.query)
        assert set(query) == {"expires", "sig"}
        await db.refresh(user)
        avatar_reference = user.avatar
        assert avatar_reference and avatar_reference.startswith("media:avatar:")
        avatar_path = media_path_for_reference(avatar_reference)
        assert avatar_path and avatar_path.is_file()

        public_image = await client.get(avatar)
        assert public_image.status_code == 200
        assert public_image.headers["content-type"].startswith("image/jpeg")
        with Image.open(BytesIO(public_image.content)) as image:
            assert image.format == "JPEG"
            assert image.size == (512, 512)

        # The opaque path is not public: removing or changing the signature fails.
        assert (await client.get(signed.path)).status_code == 422
        tampered = f"{signed.path}?expires={query['expires'][0]}&sig={'0' * 64}"
        assert (await client.get(tampered)).status_code == 403

        reloaded = await client.get("/api/v1/users/me", headers=headers)
        assert reloaded.status_code == 200
        assert reloaded.json()["nickname"] == "新昵称"
        assert reloaded.json()["avatar"] == avatar

    finally:
        delete_managed_media(avatar_reference)


async def test_avatar_requires_patient_and_real_image(client, db):
    user, headers = await patient_session(db)
    no_auth = await client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("avatar.png", png_bytes(), "image/png")},
    )
    assert no_auth.status_code == 401

    fake = await client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("avatar.png", b"not an image", "image/png")},
        headers=headers,
    )
    assert fake.status_code == 400

    too_large = await client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("avatar.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")},
        headers=headers,
    )
    assert too_large.status_code == 400

    user.role = "doctor"
    await db.commit()
    forbidden = await client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("avatar.png", png_bytes(), "image/png")},
        headers=headers,
    )
    assert forbidden.status_code == 403


async def test_avatar_cannot_be_set_as_arbitrary_url_in_profile(client, db):
    _, headers = await patient_session(db)
    response = await client.put(
        "/api/v1/users/me",
        json={"avatar": "https://example.invalid/imposter.jpg", "nickname": "安全昵称"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["avatar"] is None
    invalid = await client.put("/api/v1/users/me", json={"nickname": "<script>"}, headers=headers)
    assert invalid.status_code == 400


async def test_public_nickname_uses_content_security(client, db, monkeypatch):
    from app.services import user_service
    from app.services.wechat_content_security import (
        ContentSecurityRejected,
        ContentSecurityUnavailable,
    )

    _, headers = await patient_session(db)

    async def rejected(_content, _openid):
        raise ContentSecurityRejected("昵称含有不适合公开展示的内容，请修改后再试")

    monkeypatch.setattr(user_service, "check_public_text", rejected)
    response = await client.put(
        "/api/v1/users/me", json={"nickname": "待审核昵称"}, headers=headers
    )
    assert response.status_code == 400

    async def unavailable(_content, _openid):
        raise ContentSecurityUnavailable("微信内容安全服务暂时不可用")

    monkeypatch.setattr(user_service, "check_public_text", unavailable)
    response = await client.put(
        "/api/v1/users/me", json={"nickname": "正常昵称"}, headers=headers
    )
    assert response.status_code == 503
