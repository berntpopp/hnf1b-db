"""Tests for admin user-management endpoints.

Wave 5b Task 14: covers the ``_system_migration_`` guards, role-filter
on list, full CRUD round-trip, and self-delete protection.
"""

from __future__ import annotations

import pytest

from app.auth.password import get_password_hash
from app.models.user import User


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
async def test_deactivate_system_migration_user_forbidden(
    async_client, admin_headers, db_session
):
    """PUT with is_active=False on ``_system_migration_`` returns 400."""
    placeholder = await _seed_system_migration(db_session)

    response = await async_client.put(
        f"/api/v2/auth/users/{placeholder.id}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "_system_migration_" in response.json()["detail"]


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
