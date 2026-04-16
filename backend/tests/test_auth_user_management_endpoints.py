"""Tests for admin user-management endpoints.

Wave 5b Task 14: covers the ``_system_migration_`` guards, role-filter
on list, full CRUD round-trip, and self-delete protection.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.password import get_password_hash
from app.core.config import settings
from app.models.user import User
from app.repositories.user_repository import (
    UserEmailConflictError,
    UserRepository,
)
from app.schemas.auth import UserUpdateAdmin


async def _seed_system_migration(db_session) -> User:
    """Seed the ``_system_migration_`` placeholder in a clean DB.

    The autouse ``_isolate_database_between_tests`` truncates ``users``
    before every test, so the placeholder must be freshly inserted in
    each test that needs it.
    """
    placeholder = User(
        username="_system_migration_",
        email="system-migration@example.com",
        hashed_password=get_password_hash("placeholder-not-loginable"),
        full_name="System Migration Placeholder",
        role="viewer",
        is_active=False,
        is_verified=False,
        is_fixture_user=False,
    )
    db_session.add(placeholder)
    await db_session.commit()
    await db_session.refresh(placeholder)
    return placeholder


def _auth_cookies(response) -> dict[str, str]:
    """Extract auth cookies from a login response."""
    return {
        settings.REFRESH_COOKIE_NAME: response.cookies[settings.REFRESH_COOKIE_NAME],
        settings.CSRF_COOKIE_NAME: response.cookies[settings.CSRF_COOKIE_NAME],
    }


def _cookie_headers(cookies: dict[str, str]) -> dict[str, str]:
    """Build request headers for cookie-authenticated routes."""
    return {
        "x-csrf-token": cookies[settings.CSRF_COOKIE_NAME],
        "cookie": "; ".join(f"{name}={value}" for name, value in cookies.items()),
    }


@pytest.mark.asyncio
async def test_list_users_supports_role_filter(async_client, admin_headers):
    """GET /api/v2/auth/users?role=admin returns only admin users."""
    response = await async_client.get(
        "/api/v2/auth/users",
        params={"role": "admin"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 1
    for user in users:
        assert user["role"] == "admin"


@pytest.mark.asyncio
async def test_create_then_update_then_unlock_then_delete_user(
    async_client, admin_headers
):
    """Full CRUD round-trip: create, update, unlock, delete."""
    # CREATE
    create_resp = await async_client.post(
        "/api/v2/auth/users",
        json={
            "username": "crud-probe",
            "email": "crud-probe@example.com",
            "password": "CrudProbe!2026",
            "full_name": "CRUD Probe",
            "role": "viewer",
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    # UPDATE
    update_resp = await async_client.put(
        f"/api/v2/auth/users/{user_id}",
        json={"full_name": "Updated CRUD Probe", "role": "curator"},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["full_name"] == "Updated CRUD Probe"
    assert update_resp.json()["role"] == "curator"

    # UNLOCK (even if not locked, endpoint should succeed)
    unlock_resp = await async_client.patch(
        f"/api/v2/auth/users/{user_id}/unlock",
        headers=admin_headers,
    )
    assert unlock_resp.status_code == 200

    # DELETE
    delete_resp = await async_client.delete(
        f"/api/v2/auth/users/{user_id}",
        headers=admin_headers,
    )
    assert delete_resp.status_code == 204


@pytest.mark.asyncio
async def test_deactivate_user_invalidates_existing_refresh_cookie(
    async_client, admin_headers
):
    """Admin deactivation should revoke the target user's refresh capability."""
    create_resp = await async_client.post(
        "/api/v2/auth/users",
        json={
            "username": "inactive-probe",
            "email": "inactive-probe@example.com",
            "password": "InactiveProbe!2026",
            "full_name": "Inactive Probe",
            "role": "viewer",
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    login_resp = await async_client.post(
        "/api/v2/auth/login",
        json={"username": "inactive-probe", "password": "InactiveProbe!2026"},
    )
    assert login_resp.status_code == 200
    cookies = _auth_cookies(login_resp)

    deactivate_resp = await async_client.put(
        f"/api/v2/auth/users/{user_id}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False

    refresh_resp = await async_client.post(
        "/api/v2/auth/refresh",
        headers=_cookie_headers(cookies),
    )
    assert refresh_resp.status_code == 401
    assert "invalid" in refresh_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_user_rejects_duplicate_email(async_client, admin_headers):
    """PUT /auth/users/{id} returns 409 when email matches another user."""
    first_resp = await async_client.post(
        "/api/v2/auth/users",
        json={
            "username": "duplicate-email-a",
            "email": "duplicate-email-a@example.com",
            "password": "DuplicateEmailA!2026",
            "full_name": "Duplicate Email A",
            "role": "viewer",
        },
        headers=admin_headers,
    )
    assert first_resp.status_code == 201

    second_resp = await async_client.post(
        "/api/v2/auth/users",
        json={
            "username": "duplicate-email-b",
            "email": "duplicate-email-b@example.com",
            "password": "DuplicateEmailB!2026",
            "full_name": "Duplicate Email B",
            "role": "viewer",
        },
        headers=admin_headers,
    )
    assert second_resp.status_code == 201

    response = await async_client.put(
        f"/api/v2/auth/users/{second_resp.json()['id']}",
        json={"email": "duplicate-email-a@example.com"},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_user_repository_normalizes_integrity_error_on_email_update(
    db_session, monkeypatch
):
    """Repository update normalizes a lower-level duplicate-email IntegrityError."""
    existing_user = User(
        username="repo-email-a",
        email="repo-email-a@example.com",
        hashed_password=get_password_hash("RepoEmailA!2026"),
        full_name="Repo Email A",
        role="viewer",
        is_active=True,
        is_verified=False,
    )
    target_user = User(
        username="repo-email-b",
        email="repo-email-b@example.com",
        hashed_password=get_password_hash("RepoEmailB!2026"),
        full_name="Repo Email B",
        role="viewer",
        is_active=True,
        is_verified=False,
    )
    db_session.add_all([existing_user, target_user])
    await db_session.commit()
    await db_session.refresh(existing_user)
    await db_session.refresh(target_user)

    repo = UserRepository(db_session)

    async def fake_commit():
        raise IntegrityError(
            "UPDATE users SET email = ...",
            params={"email": "repo-email-a@example.com"},
            orig=type("FakeOrig", (), {"sqlstate": "23505"})(),
        )

    monkeypatch.setattr(db_session, "commit", fake_commit)

    with pytest.raises(UserEmailConflictError) as excinfo:
        await repo.update(
            target_user, UserUpdateAdmin(email="repo-email-c@example.com")
        )

    assert "already exists" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_user_repository_reraises_non_unique_integrity_error_on_email_update(
    db_session, monkeypatch
):
    """Repository re-raises unrelated IntegrityError values unchanged."""
    target_user = User(
        username="repo-email-non-unique",
        email="repo-email-non-unique@example.com",
        hashed_password=get_password_hash("RepoEmailNonUnique!2026"),
        full_name="Repo Email Non Unique",
        role="viewer",
        is_active=True,
        is_verified=False,
    )
    db_session.add(target_user)
    await db_session.commit()
    await db_session.refresh(target_user)

    repo = UserRepository(db_session)

    async def fake_commit():
        raise IntegrityError(
            "UPDATE users SET full_name = ...",
            params={"full_name": "Updated Name"},
            orig=type("FakeOrig", (), {"sqlstate": "23503"})(),
        )

    monkeypatch.setattr(db_session, "commit", fake_commit)

    with pytest.raises(IntegrityError):
        await repo.update(target_user, UserUpdateAdmin(full_name="Updated Name"))


@pytest.mark.asyncio
async def test_delete_system_migration_user_forbidden(
    async_client, admin_headers, db_session
):
    """DELETE on ``_system_migration_`` placeholder returns 400."""
    placeholder = await _seed_system_migration(db_session)

    response = await async_client.delete(
        f"/api/v2/auth/users/{placeholder.id}",
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "_system_migration_" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_system_migration_user_forbidden(
    async_client, admin_headers, db_session
):
    """ANY mutation on ``_system_migration_`` returns 400 (not just deactivation)."""
    placeholder = await _seed_system_migration(db_session)

    # Deactivation blocked
    resp_deactivate = await async_client.put(
        f"/api/v2/auth/users/{placeholder.id}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert resp_deactivate.status_code == 400
    assert "_system_migration_" in resp_deactivate.json()["detail"]

    # Role escalation blocked
    resp_role = await async_client.put(
        f"/api/v2/auth/users/{placeholder.id}",
        json={"role": "admin"},
        headers=admin_headers,
    )
    assert resp_role.status_code == 400
    assert "_system_migration_" in resp_role.json()["detail"]

    # Email change blocked
    resp_email = await async_client.put(
        f"/api/v2/auth/users/{placeholder.id}",
        json={"email": "hacked@evil.com"},
        headers=admin_headers,
    )
    assert resp_email.status_code == 400
    assert "_system_migration_" in resp_email.json()["detail"]


@pytest.mark.asyncio
async def test_cannot_self_delete(async_client, admin_headers):
    """Admin cannot delete their own account."""
    # Get admin's own ID
    me_resp = await async_client.get("/api/v2/auth/me", headers=admin_headers)
    assert me_resp.status_code == 200
    admin_id = me_resp.json()["id"]

    response = await async_client.delete(
        f"/api/v2/auth/users/{admin_id}",
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "own account" in response.json()["detail"].lower()
