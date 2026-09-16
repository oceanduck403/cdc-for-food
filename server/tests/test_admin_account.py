"""管理员自助修改登录账号和密码。"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.security import admin_auth_fingerprint, create_access_token, hash_password, verify_password
from app.db.session import ensure_admin_token_version_column
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _login(client, username, password, role="admin"):
    return await client.post(
        "/api/v1/auth/account-login",
        json={"username": username, "password": password, "role": role},
    )


def _headers(user):
    extra = {"role": user.role}
    if user.role == "admin":
        extra["admin_auth"] = admin_auth_fingerprint(user)
    return {"Authorization": f"Bearer {create_access_token(str(user.id), extra=extra)}"}


async def test_admin_can_change_username_password_or_both(client, db):
    admin = User(role="admin", username="account_change_admin", password_hash=hash_password("Original-123"))
    db.add(admin)
    await db.commit()
    original_hash = admin.password_hash
    login = await _login(client, "account_change_admin", "Original-123")
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    username_only = await client.post(
        "/api/v1/admin/account",
        json={"current_password": "Original-123", "new_username": "account_renamed_admin"},
        headers=headers,
    )
    assert username_only.status_code == 200, username_only.text
    assert username_only.json()["username"] == "account_renamed_admin"
    await db.refresh(admin)
    assert admin.password_hash == original_hash
    assert admin.token_version == 1
    assert (await _login(client, "account_change_admin", "Original-123")).status_code == 404
    renamed_login = await _login(client, "account_renamed_admin", "Original-123")
    assert renamed_login.status_code == 200
    for url in (
        "/api/v1/admin/stats",
        "/api/v1/appointments/dispatch",
        "/api/v1/survey/admin/templates",
        "/api/v1/community/moderation/reports",
    ):
        assert (await client.get(url, headers=headers)).status_code == 401, url
    headers = {"Authorization": f"Bearer {renamed_login.json()['token']}"}

    password_only = await client.post(
        "/api/v1/admin/account",
        json={"current_password": "Original-123", "new_password": "New-password-456"},
        headers=headers,
    )
    assert password_only.status_code == 200, password_only.text
    await db.refresh(admin)
    assert admin.password_hash != original_hash
    assert admin.token_version == 2
    assert verify_password("New-password-456", admin.password_hash)
    assert (await _login(client, "account_renamed_admin", "Original-123")).status_code == 401
    password_login = await _login(client, "account_renamed_admin", "New-password-456")
    assert password_login.status_code == 200
    assert (await client.get("/api/v1/admin/stats", headers=headers)).status_code == 401
    headers = {"Authorization": f"Bearer {password_login.json()['token']}"}

    both = await client.post(
        "/api/v1/admin/account",
        json={
            "current_password": "New-password-456",
            "new_username": "account_final_admin",
            "new_password": "Final-password-789",
        },
        headers=headers,
    )
    assert both.status_code == 200, both.text
    assert (await _login(client, "account_renamed_admin", "Final-password-789")).status_code == 404
    assert (await _login(client, "account_final_admin", "New-password-456")).status_code == 401
    assert (await _login(client, "account_final_admin", "Final-password-789")).status_code == 200
    assert (await client.get("/api/v1/admin/stats", headers=headers)).status_code == 401

    final_login = await _login(client, "account_final_admin", "Final-password-789")
    final_headers = {"Authorization": f"Bearer {final_login.json()['token']}"}
    revert = await client.post(
        "/api/v1/admin/account",
        json={"current_password": "Final-password-789", "new_username": "account_change_admin"},
        headers=final_headers,
    )
    assert revert.status_code == 200, revert.text
    await db.refresh(admin)
    assert admin.token_version == 4
    # 即使用户名恢复原样，最早的 JWT 也不能重新变有效。
    assert (await client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {login.json()['token']}"})).status_code == 401


async def test_admin_account_rejects_invalid_changes_without_mutation(client, db):
    admin = User(role="admin", username="account_guard_admin", password_hash=hash_password("Original-123"))
    taken = User(role="doctor", username="account_taken_doctor", password_hash=hash_password("Doctor-123"))
    db.add_all([admin, taken])
    await db.commit()
    initial_hash = admin.password_hash
    headers = _headers(admin)

    invalid_bodies = [
        ({"current_password": "wrong", "new_username": "new_admin_name"}, 400),
        ({"current_password": "Original-123"}, 400),
        ({"current_password": "Original-123", "new_username": "bad name"}, 400),
        ({"current_password": "Original-123", "new_username": "account_taken_doctor"}, 409),
        ({"current_password": "Original-123", "new_password": "short"}, 400),
        ({"current_password": "Original-123", "new_password": "Original-123"}, 400),
        ({"current_password": "Original-123", "new_password": " leading-123"}, 400),
        ({"current_password": "Original-123", "new_password": "x" * 73}, 400),
    ]
    for body, expected in invalid_bodies:
        response = await client.post("/api/v1/admin/account", json=body, headers=headers)
        assert response.status_code == expected, (body, response.text)
        await db.refresh(admin)
        assert admin.username == "account_guard_admin"
        assert admin.password_hash == initial_hash
        assert admin.token_version == 0


async def test_admin_account_is_admin_only(client, db):
    doctor = User(role="doctor", username="account_guard_doctor", password_hash=hash_password("Doctor-123"))
    patient = User(role="patient", nickname="Account guard patient")
    disabled = User(role="admin", username="account_disabled_admin", password_hash=hash_password("Original-123"), is_active=False)
    db.add_all([doctor, patient, disabled])
    await db.commit()
    body = {"current_password": "Original-123", "new_password": "New-password-456"}
    assert (await client.post("/api/v1/admin/account", json=body)).status_code == 401
    for user in (doctor, patient, disabled):
        headers = _headers(user)
        response = await client.post("/api/v1/admin/account", json=body, headers=headers)
        expected = 401 if user is disabled else 403
        assert response.status_code == expected, response.text

    legacy_headers = {"Authorization": f"Bearer {create_access_token(str(disabled.id))}"}
    assert (await client.get("/api/v1/admin/stats", headers=legacy_headers)).status_code == 401


async def test_existing_user_table_gets_token_version_without_losing_accounts():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(64))"))
            await conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'existing_admin')"))
            await ensure_admin_token_version_column(conn)
            await ensure_admin_token_version_column(conn)
            row = (await conn.execute(text("SELECT username, token_version FROM users WHERE id = 1"))).one()
            assert row == ("existing_admin", 0)
    finally:
        await engine.dispose()
