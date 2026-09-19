"""Clinical routes must stay unavailable unless deployment explicitly opts in."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.deps import get_db
from app.config import Settings, settings
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User


def test_clinical_services_default_to_disabled(monkeypatch):
    monkeypatch.delenv("ENABLE_CLINICAL_SERVICES", raising=False)
    configured = Settings(_env_file=None)
    assert configured.enable_clinical_services is False


@pytest_asyncio.fixture
async def disabled_client(engine, monkeypatch):
    monkeypatch.setattr(settings, "enable_clinical_services", False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override():
        async with Session() as session:
            yield session

    closed_app = create_app(enable_clinical_services=False)
    closed_app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=closed_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, Session
    closed_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_disabled_clinical_services_fail_closed(disabled_client):
    client, Session = disabled_client
    async with Session() as db:
        doctor = User(
            role="doctor",
            username="disabled_clinical_doctor",
            password_hash=hash_password("Doctor-password-123!"),
        )
        admin = User(
            role="admin",
            username="disabled_clinical_admin",
            password_hash=hash_password("Admin-password-123!"),
        )
        db.add_all([doctor, admin])
        await db.commit()

    doctor_login = await client.post(
        "/api/v1/auth/account-login",
        json={
            "username": "disabled_clinical_doctor",
            "password": "Doctor-password-123!",
            "role": "doctor",
        },
    )
    assert doctor_login.status_code == 403

    admin_login = await client.post(
        "/api/v1/auth/account-login",
        json={
            "username": "disabled_clinical_admin",
            "password": "Admin-password-123!",
            "role": "admin",
        },
    )
    assert admin_login.status_code == 200, admin_login.text
    headers = {"Authorization": f"Bearer {admin_login.json()['token']}"}

    blocked_admin_requests = (
        ("GET", "/api/v1/admin/doctors", None),
        (
            "POST",
            "/api/v1/admin/doctors",
            {
                "username": "should_not_be_created",
                "password": "Doctor-password-456!",
                "real_name": "未开放医生",
            },
        ),
        ("PUT", f"/api/v1/admin/doctors/{doctor.id}", {"real_name": "不可修改"}),
        ("DELETE", f"/api/v1/admin/doctors/{doctor.id}", None),
        ("GET", "/api/v1/admin/assignments", None),
        (
            "POST",
            "/api/v1/admin/assignments",
            {"patient_id": 999, "doctor_id": doctor.id},
        ),
        ("GET", "/api/v1/admin/chats", None),
    )
    for method, url, body in blocked_admin_requests:
        kwargs = {"headers": headers}
        if body is not None:
            kwargs["json"] = body
        response = await client.request(method, url, **kwargs)
        assert response.status_code == 404, (method, url, response.text)

    assert (await client.get("/api/v1/appointments/mine")).status_code == 404
    assert (
        await client.get("/api/v1/chat/messages", params={"assignment_id": 1})
    ).status_code == 404
    assert (
        await client.get(
            "/api/v1/media/chat/1/history.jpg",
            params={"expires": 1, "sig": "invalid"},
        )
    ).status_code == 404

    # Avatar media remains part of the non-clinical user profile flow.
    assert (
        await client.get(
            "/api/v1/media/avatar/profile.jpg",
            params={"expires": 1, "sig": "invalid"},
        )
    ).status_code == 403

    paths = (await client.get("/openapi.json")).json()["paths"]
    assert not any(path.startswith("/api/v1/appointments") for path in paths)
    assert not any(path.startswith("/api/v1/chat") for path in paths)
    assert "/api/v1/admin/doctors" not in paths
    assert "/api/v1/admin/assignments" not in paths
    assert "/api/v1/admin/chats" not in paths

    async with Session() as db:
        # A blocked delete cannot alter the historical doctor record.
        persisted = await db.get(User, doctor.id)
        assert persisted is not None and persisted.is_active is True
