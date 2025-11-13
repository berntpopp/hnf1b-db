"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


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

    assert response.status_code == 403  # No token provided


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
    from app.models.user import User

    try:
        await db_session.execute(
            delete(User).where(User.email == "new@example.com")
        )
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
        await db_session.execute(
            delete(User).where(User.email == "new@example.com")
        )
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
