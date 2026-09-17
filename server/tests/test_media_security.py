"""Private media upload, authorization and signed URL regression tests."""
from io import BytesIO
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import select

from app.config import settings
from app.core.security import create_access_token
from app.models.chat import ConsultAssignment, Consultation
from app.models.user import User
from app.services import media_service
from app.services.media_service import (
    delete_chat_assignment_media,
    delete_managed_media,
    ensure_media_directories,
    signed_media_url,
    store_avatar,
    store_chat_image,
)


pytestmark = pytest.mark.asyncio


def png_bytes(size: tuple[int, int] = (1200, 800)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "#4e94b8").save(buffer, "PNG")
    return buffer.getvalue()


def jpeg_bytes(size: tuple[int, int] = (320, 240)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "#4e94b8").save(buffer, "JPEG")
    return buffer.getvalue()


class _FakeCosBody:
    def __init__(self, content: bytes):
        self.content = content

    def get_raw_stream(self) -> BytesIO:
        return BytesIO(self.content)


class _FakeCosClient:
    """Small deterministic COS double; never makes a network request."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.put_calls: list[dict] = []

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        self.objects[Key] = bytes(Body)
        self.put_calls.append({"Bucket": Bucket, "Key": Key, **kwargs})
        return {"ETag": "fake"}

    def get_object(self, *, Bucket, Key):
        assert Bucket == "patient-private-1250000000"
        return {"Body": _FakeCosBody(self.objects[Key])}

    def delete_object(self, *, Bucket, Key):
        assert Bucket == "patient-private-1250000000"
        self.objects.pop(Key, None)
        return {}

    def list_objects(self, *, Bucket, Prefix, Marker, MaxKeys):
        assert Bucket == "patient-private-1250000000"
        assert MaxKeys == 1000
        matches = sorted(key for key in self.objects if key.startswith(Prefix) and key > Marker)
        page = matches[:1]  # Force pagination so cleanup covers that branch.
        return {
            "Contents": [{"Key": key} for key in page],
            "IsTruncated": "true" if len(matches) > len(page) else "false",
            "NextMarker": page[-1] if page else "",
        }


class _FakeCloudBaseResponse:
    def __init__(self, status_code: int, *, content: bytes = b"", payload=None):
        self.status_code = status_code
        self.content = content
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


async def chat_session(db):
    suffix = uuid4().hex
    patient = User(openid=f"media-patient-{suffix}", role="patient", nickname="患者")
    doctor = User(openid=f"media-doctor-{suffix}", role="doctor", nickname="医生")
    outsider = User(openid=f"media-outsider-{suffix}", role="patient", nickname="其他患者")
    db.add_all([patient, doctor, outsider])
    await db.flush()
    assignment = ConsultAssignment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        status="active",
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    def headers(user: User) -> dict[str, str]:
        token = create_access_token(subject=str(user.id), extra={"role": user.role})
        return {"Authorization": f"Bearer {token}"}

    return patient, doctor, outsider, assignment, headers


async def test_chat_image_is_assignment_bound_normalized_and_signed(client, db):
    patient, _, _, assignment, headers = await chat_session(db)
    reference = None
    response = await client.post(
        "/api/v1/chat/upload-image",
        data={"assignment_id": str(assignment.id)},
        # Deliberately misleading name and MIME: actual decoding decides validity.
        files={"file": ("payload.php", png_bytes(), "application/octet-stream")},
        headers=headers(patient),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["url"].startswith(f"/api/v1/media/chat/{assignment.id}/")

    message = await db.get(Consultation, payload["id"])
    assert message and message.msg_type == "image"
    reference = message.image_url
    assert reference and reference.startswith(f"media:chat:{assignment.id}:")
    assert "payload" not in reference

    image = await client.get(payload["url"])
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/jpeg")
    assert image.headers["x-content-type-options"] == "nosniff"
    with Image.open(BytesIO(image.content)) as decoded:
        assert decoded.format == "JPEG"
        assert decoded.width <= 2560 and decoded.height <= 2560

    signed = urlsplit(payload["url"])
    query = parse_qs(signed.query)
    assert (await client.get(signed.path)).status_code == 422
    tampered_path = signed.path.replace(
        f"/chat/{assignment.id}/",
        f"/chat/{assignment.id + 1}/",
    )
    tampered = f"{tampered_path}?expires={query['expires'][0]}&sig={query['sig'][0]}"
    assert (await client.get(tampered)).status_code == 403
    assert (await client.get("/uploads/anything.jpg")).status_code == 404

    # The normal send endpoint cannot persist a client-supplied image URL.
    bypass = await client.post(
        "/api/v1/chat/send",
        json={
            "assignment_id": assignment.id,
            "content": "[图片]",
            "msg_type": "image",
            "image_url": "https://example.invalid/tracker.jpg",
        },
        headers=headers(patient),
    )
    assert bypass.status_code == 400
    delete_managed_media(reference)


async def test_chat_upload_rejects_unauthorized_or_forged_images(client, db):
    patient, _, outsider, assignment, headers = await chat_session(db)

    unauthorized = await client.post(
        "/api/v1/chat/upload-image",
        data={"assignment_id": str(assignment.id)},
        files={"file": ("photo.png", png_bytes(), "image/png")},
        headers=headers(outsider),
    )
    assert unauthorized.status_code == 403

    forged = await client.post(
        "/api/v1/chat/upload-image",
        data={"assignment_id": str(assignment.id)},
        files={"file": ("photo.png", b"not really an image", "image/png")},
        headers=headers(patient),
    )
    assert forged.status_code == 400

    oversized = await client.post(
        "/api/v1/chat/upload-image",
        data={"assignment_id": str(assignment.id)},
        files={"file": ("photo.jpg", b"x" * (settings.chat_image_max_bytes + 1), "image/jpeg")},
        headers=headers(patient),
    )
    assert oversized.status_code == 400

    messages = (
        await db.execute(
            select(Consultation).where(Consultation.assignment_id == assignment.id)
        )
    ).scalars().all()
    assert messages == []


async def test_expired_media_signature_is_rejected(client):
    reference = f"media:avatar:{'a' * 64}.jpg"
    expired = signed_media_url(reference, now=1)
    assert expired
    assert (await client.get(expired)).status_code == 403


async def test_cos_storage_is_private_persistent_and_proxied(
    client,
    monkeypatch,
    tmp_path,
):
    fake = _FakeCosClient()
    monkeypatch.setattr(settings, "media_storage_backend", "cos")
    monkeypatch.setattr(settings, "media_storage_dir", str(tmp_path / "must-not-exist"))
    monkeypatch.setattr(settings, "media_cos_bucket", "patient-private-1250000000")
    monkeypatch.setattr(settings, "media_cos_prefix", "private/user-media")
    monkeypatch.setattr(media_service, "_cos_client", lambda: fake)

    ensure_media_directories()
    assert not (tmp_path / "must-not-exist").exists()

    content = jpeg_bytes()
    stored = store_avatar(content)
    assert stored.path is None
    assert stored.object_key
    assert stored.object_key.startswith("private/user-media/avatar/")
    assert fake.objects[stored.object_key] == content
    assert fake.put_calls[0]["ContentType"] == "image/jpeg"
    assert fake.put_calls[0]["EnableMD5"] is True

    url = signed_media_url(stored.reference)
    assert url and url.startswith("/api/v1/media/avatar/")
    assert stored.object_key not in url
    assert "cos." not in url
    response = await client.get(url)
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"].startswith("image/jpeg")

    delete_managed_media(stored.reference)
    assert stored.object_key not in fake.objects


async def test_cos_chat_cleanup_is_limited_to_assignment_prefix(monkeypatch):
    fake = _FakeCosClient()
    monkeypatch.setattr(settings, "media_storage_backend", "cos")
    monkeypatch.setattr(settings, "media_cos_bucket", "patient-private-1250000000")
    monkeypatch.setattr(settings, "media_cos_prefix", "private/user-media")
    monkeypatch.setattr(media_service, "_cos_client", lambda: fake)

    first = store_chat_image(jpeg_bytes(), 41)
    second = store_chat_image(jpeg_bytes(), 41)
    retained = store_chat_image(jpeg_bytes(), 42)
    delete_chat_assignment_media(41)

    assert first.object_key not in fake.objects
    assert second.object_key not in fake.objects
    assert retained.object_key in fake.objects


async def test_cloudbase_pg_storage_is_private_persistent_and_scoped(
    client,
    monkeypatch,
    tmp_path,
):
    objects: dict[str, bytes] = {}
    calls: list[tuple[str, str]] = []
    bucket_prefix = "/v1/storages/object/user-media/"

    def request(method: str, path: str, **kwargs):
        calls.append((method, path))
        if path == "/v1/storages/object/list/user-media":
            prefix = kwargs["json"]["prefix"]
            matches = sorted(key for key in objects if key.startswith(prefix))
            return _FakeCloudBaseResponse(
                200,
                payload={
                    "objects": [{"key": key} for key in matches],
                    "hasNext": False,
                },
            )
        if path == "/v1/storages/object/user-media" and method == "DELETE":
            for key in kwargs["json"]["prefixes"]:
                objects.pop(key, None)
            return _FakeCloudBaseResponse(200, payload=[])

        assert path.startswith(bucket_prefix)
        key = unquote(path.removeprefix(bucket_prefix))
        if method == "POST":
            assert kwargs["headers"]["Content-Type"] == "image/jpeg"
            objects[key] = bytes(kwargs["content"])
            return _FakeCloudBaseResponse(200, payload={"Key": key})
        if method == "GET":
            if key not in objects:
                return _FakeCloudBaseResponse(404)
            return _FakeCloudBaseResponse(200, content=objects[key])
        if method == "DELETE":
            objects.pop(key, None)
            return _FakeCloudBaseResponse(200, payload={"message": "ok"})
        raise AssertionError(f"unexpected call: {method} {path}")

    monkeypatch.setattr(settings, "media_storage_backend", "cloudbase_pg")
    monkeypatch.setattr(settings, "media_storage_dir", str(tmp_path / "must-not-exist"))
    monkeypatch.setattr(settings, "media_cloudbase_bucket", "user-media")
    monkeypatch.setattr(settings, "media_cos_prefix", "private/user-media")
    monkeypatch.setattr(media_service, "_cloudbase_request", request)

    ensure_media_directories()
    assert not (tmp_path / "must-not-exist").exists()

    content = jpeg_bytes()
    avatar = store_avatar(content)
    first = store_chat_image(content, 41)
    second = store_chat_image(content, 41)
    retained = store_chat_image(content, 42)

    assert avatar.object_key in objects
    assert first.object_key in objects
    assert second.object_key in objects
    assert retained.object_key in objects

    url = signed_media_url(avatar.reference)
    assert url and url.startswith("/api/v1/media/avatar/")
    assert avatar.object_key not in url
    response = await client.get(url)
    assert response.status_code == 200
    assert response.content == content

    delete_managed_media(avatar.reference)
    delete_chat_assignment_media(41)
    assert avatar.object_key not in objects
    assert first.object_key not in objects
    assert second.object_key not in objects
    assert retained.object_key in objects
    assert any(path == "/v1/storages/object/list/user-media" for _, path in calls)
