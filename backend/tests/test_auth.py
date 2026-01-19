"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_login_valid_credentials_returns_token(
    fixture_async_client: AsyncClient, fixture_test_user
):
    """Test successful login with valid credentials returns access and refresh tokens."""
    response = await fixture_async_client.post(
        "/api/v2/auth/login",
        json={"username": fixture_test_user.username, "password": "TestPass123!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800  # 30 minutes


@pytest.mark.asyncio
async def test_auth_login_wrong_password_returns_401(
    fixture_async_client: AsyncClient, fixture_test_user
):
    """Test login with wrong password returns 401 Unauthorized."""
    response = await fixture_async_client.post(
        "/api/v2/auth/login",
        json={"username": fixture_test_user.username, "password": "WrongPassword"},
    )

    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_auth_login_unknown_user_returns_401(fixture_async_client: AsyncClient):
    """Test login with nonexistent user returns 401 Unauthorized."""
    response = await fixture_async_client.post(
        "/api/v2/auth/login",
        json={"username": "nonexistent", "password": "password"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_valid_token_returns_user_info(
    fixture_async_client: AsyncClient, fixture_auth_headers
):
    """Test getting current user info with valid token returns user details."""
    response = await fixture_async_client.get(
        "/api/v2/auth/me", headers=fixture_auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["role"] == "viewer"
    assert "phenopackets:read" in data["permissions"]


@pytest.mark.asyncio
async def test_auth_me_no_token_returns_403(fixture_async_client: AsyncClient):
    """Test accessing protected endpoint without token returns 403 Forbidden."""
    response = await fixture_async_client.get("/api/v2/auth/me")

    assert response.status_code == 403  # No token provided


@pytest.mark.asyncio
async def test_auth_refresh_valid_token_returns_new_tokens(
    fixture_async_client: AsyncClient, fixture_test_user
):
    """Test token refresh with valid refresh token returns new token pair."""
    # Login first
    login_response = await fixture_async_client.post(
        "/api/v2/auth/login",
        json={"username": fixture_test_user.username, "password": "TestPass123!"},
    )
    refresh_token = login_response.json()["refresh_token"]

    # Refresh token
    response = await fixture_async_client.post(
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
async def test_auth_logout_valid_session_returns_success(
    fixture_async_client: AsyncClient, fixture_auth_headers
):
    """Test logout with valid session returns success message."""
    response = await fixture_async_client.post(
        "/api/v2/auth/logout", headers=fixture_auth_headers
    )

    assert response.status_code == 200
    assert "Successfully logged out" in response.json()["message"]


@pytest.mark.asyncio
async def test_auth_password_change_valid_current_succeeds(
    fixture_async_client: AsyncClient, fixture_auth_headers
):
    """Test password change with valid current password succeeds."""
    response = await fixture_async_client.post(
        "/api/v2/auth/change-password",
        headers=fixture_auth_headers,
        json={
            "current_password": "TestPass123!",
            "new_password": "NewPass456!",
        },
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_auth_roles_authenticated_user_returns_all_roles(
    fixture_async_client: AsyncClient, fixture_auth_headers
):
    """Test listing roles as authenticated user returns all available roles."""
    response = await fixture_async_client.get(
        "/api/v2/auth/roles", headers=fixture_auth_headers
    )

    assert response.status_code == 200
    roles = response.json()
    assert len(roles) == 3
    role_names = [r["role"] for r in roles]
    assert "admin" in role_names
    assert "curator" in role_names
    assert "viewer" in role_names


# Admin-only endpoint tests


@pytest.mark.asyncio
async def test_auth_create_user_admin_role_succeeds(
    fixture_async_client: AsyncClient, fixture_admin_headers, fixture_db_session
):
    """Test creating user as admin succeeds with new user data."""
    # Pre-cleanup: Remove any leftover newuser from failed previous runs
    from sqlalchemy import delete

    from app.models.user import User

    try:
        await fixture_db_session.execute(
            delete(User).where(User.email == "new@example.com")
        )
        await fixture_db_session.commit()
    except Exception:
        await fixture_db_session.rollback()

    response = await fixture_async_client.post(
        "/api/v2/auth/users",
        headers=fixture_admin_headers,
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
        await fixture_db_session.execute(
            delete(User).where(User.email == "new@example.com")
        )
        await fixture_db_session.commit()
    except Exception:
        await fixture_db_session.rollback()


@pytest.mark.asyncio
async def test_auth_create_user_non_admin_returns_403(
    fixture_async_client: AsyncClient, fixture_auth_headers
):
    """Test creating user as non-admin returns 403 Forbidden."""
    response = await fixture_async_client.post(
        "/api/v2/auth/users",
        headers=fixture_auth_headers,
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "NewPass123!",
            "role": "curator",
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_auth_list_users_admin_role_returns_list(
    fixture_async_client: AsyncClient, fixture_admin_headers
):
    """Test listing users as admin returns list of users."""
    response = await fixture_async_client.get(
        "/api/v2/auth/users", headers=fixture_admin_headers
    )

    assert response.status_code == 200
    users = response.json()
    assert isinstance(users, list)
    assert len(users) >= 1  # At least admin user


@pytest.mark.asyncio
async def test_auth_delete_self_returns_400(
    fixture_async_client: AsyncClient, fixture_admin_headers, fixture_admin_user
):
    """Test deleting own account returns 400 Bad Request."""
    response = await fixture_async_client.delete(
        f"/api/v2/auth/users/{fixture_admin_user.id}",
        headers=fixture_admin_headers,
    )

    assert response.status_code == 400
    assert "Cannot delete your own account" in response.json()["detail"]
