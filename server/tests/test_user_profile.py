"""患者资料编辑与头像上传回归测试。"""
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image

from app.core.security import create_access_token
from app.models.user import User
from app.services.user_service import ensure_user

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
    avatar_path = None
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
        assert avatar.startswith(f"/uploads/avatars/{user.id}-")
        avatar_path = Path("uploads") / avatar.removeprefix("/uploads/")
        assert avatar_path.is_file()

        public_image = await client.get(avatar)
        assert public_image.status_code == 200
        with Image.open(BytesIO(public_image.content)) as image:
            assert image.format == "JPEG"
            assert image.size == (512, 512)

        reloaded = await client.get("/api/v1/users/me", headers=headers)
        assert reloaded.status_code == 200
        assert reloaded.json()["nickname"] == "新昵称"
        assert reloaded.json()["avatar"] == avatar

        # 微信再次授权返回旧资料时，不应覆盖用户自行修改的昵称与头像。
        await db.refresh(user)
        await ensure_user(db, user.openid, nickname="旧微信昵称", avatar="/old-avatar.jpg")
        reloaded = await client.get("/api/v1/users/me", headers=headers)
        assert reloaded.json()["nickname"] == "新昵称"
        assert reloaded.json()["avatar"] == avatar
    finally:
        if avatar_path:
            avatar_path.unlink(missing_ok=True)


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
