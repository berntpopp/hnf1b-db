"""Tests for authentication endpoints."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, test_user):
    """Test successful login."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800  # 30 minutes


@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client: AsyncClient, test_user):
    """Test login with invalid credentials."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "WrongPassword"},
    )

    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client: AsyncClient):
    """Test login with nonexistent user."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": "nonexistent", "password": "password"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_locked_account_is_rejected(
    async_client: AsyncClient, test_user, db_session
):
    """Test login rejects an account that is currently locked."""
    test_user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    await db_session.commit()
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )

    assert response.status_code == 423
    assert "locked" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_current_user(async_client: AsyncClient, auth_headers):
    """Test getting current user info."""
    response = await async_client.get("/api/v2/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["role"] == "viewer"
    assert "phenopackets:read" in data["permissions"]


@pytest.mark.asyncio
async def test_get_current_user_no_token(async_client: AsyncClient):
    """Test accessing protected endpoint without token."""
    response = await async_client.get("/api/v2/auth/me")

    assert response.status_code == 401  # No token provided (HTTPBearer returns 401)


@pytest.mark.asyncio
async def test_token_refresh(async_client: AsyncClient, test_user):
    """Test token refresh."""
    # Login first
    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    refresh_token = login_response.json()["refresh_token"]

    # Refresh token
    response = await async_client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Should get new refresh token (rotation)
    assert data["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_token_refresh_rejects_inactive_account(
    async_client: AsyncClient, test_user, db_session
):
    """Test refresh rejects a token for an inactive account."""
    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    refresh_token = login_response.json()["refresh_token"]

    test_user.is_active = False
    await db_session.commit()

    response = await async_client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_token_refresh_rejects_locked_account(
    async_client: AsyncClient, test_user, db_session
):
    """Test refresh rejects a token for a locked account."""
    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    refresh_token = login_response.json()["refresh_token"]

    test_user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    await db_session.commit()

    response = await async_client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 423
    assert "locked" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_logout(async_client: AsyncClient, auth_headers):
    """Test logout."""
    response = await async_client.post("/api/v2/auth/logout", headers=auth_headers)

    assert response.status_code == 200
    assert "Successfully logged out" in response.json()["message"]


@pytest.mark.asyncio
async def test_change_password(async_client: AsyncClient, auth_headers):
    """Test password change."""
    response = await async_client.post(
        "/api/v2/auth/change-password",
        headers=auth_headers,
        json={
            "current_password": "TestPass123!",
            "new_password": "NewPass456!",
        },
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_change_password_invalidates_previous_refresh_token(
    async_client: AsyncClient, test_user
):
    """Test password rotation clears the existing refresh capability."""
    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    refresh_token = login_response.json()["refresh_token"]

    change_response = await async_client.post(
        "/api/v2/auth/change-password",
        headers={"Authorization": f"Bearer {login_response.json()['access_token']}"},
        json={
            "current_password": "TestPass123!",
            "new_password": "NewPass456!",
        },
    )
    assert change_response.status_code == 200

    refresh_response = await async_client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert refresh_response.status_code == 401
    assert "invalid" in refresh_response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_roles(async_client: AsyncClient, auth_headers):
    """Test listing roles."""
    response = await async_client.get("/api/v2/auth/roles", headers=auth_headers)

    assert response.status_code == 200
    roles = response.json()
    assert len(roles) == 3
    role_names = [r["role"] for r in roles]
    assert "admin" in role_names
    assert "curator" in role_names
    assert "viewer" in role_names


# Admin-only endpoint tests


@pytest.mark.asyncio
async def test_create_user_admin(async_client: AsyncClient, admin_headers, db_session):
    """Test creating user as admin."""
    # Pre-cleanup: Remove any leftover newuser from failed previous runs
    from sqlalchemy import delete

    try:
        await db_session.execute(delete(User).where(User.email == "new@example.com"))
        await db_session.commit()
    except Exception:
        await db_session.rollback()

    response = await async_client.post(
        "/api/v2/auth/users",
        headers=admin_headers,
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "NewPass123!",
            "role": "curator",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["role"] == "curator"

    # Cleanup: Remove the created user
    try:
        await db_session.execute(delete(User).where(User.email == "new@example.com"))
        await db_session.commit()
    except Exception:
        await db_session.rollback()


@pytest.mark.asyncio
async def test_create_user_non_admin(async_client: AsyncClient, auth_headers):
    """Test creating user as non-admin (should fail)."""
    response = await async_client.post(
        "/api/v2/auth/users",
        headers=auth_headers,
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "NewPass123!",
            "role": "curator",
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_users_admin(async_client: AsyncClient, admin_headers):
    """Test listing users as admin."""
    response = await async_client.get("/api/v2/auth/users", headers=admin_headers)

    assert response.status_code == 200
    users = response.json()
    assert isinstance(users, list)
    assert len(users) >= 1  # At least admin user


@pytest.mark.asyncio
async def test_delete_user_self(async_client: AsyncClient, admin_headers, admin_user):
    """Test deleting own account (should fail)."""
    response = await async_client.delete(
        f"/api/v2/auth/users/{admin_user.id}",
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert "Cannot delete your own account" in response.json()["detail"]
