"""Tests for authentication endpoints."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import AsyncClient

from app.auth.tokens import create_refresh_token, verify_token
from app.core.config import settings


def _auth_cookies(response) -> dict[str, str]:
    """Extract auth cookies from a login or refresh response."""
    return {
        settings.REFRESH_COOKIE_NAME: response.cookies[settings.REFRESH_COOKIE_NAME],
        settings.CSRF_COOKIE_NAME: response.cookies[settings.CSRF_COOKIE_NAME],
    }


def _csrf_headers(cookies: dict[str, str]) -> dict[str, str]:
    """Build the CSRF header expected by cookie-authenticated routes."""
    return {"x-csrf-token": cookies[settings.CSRF_COOKIE_NAME]}


def _cookie_headers(cookies: dict[str, str]) -> dict[str, str]:
    """Build a Cookie header for explicit per-request auth-cookie control."""
    return {
        "cookie": "; ".join(f"{name}={value}" for name, value in cookies.items()),
    }


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, test_user):
    """Login returns an access token and sets auth cookies."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" not in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800

    cookies = _auth_cookies(response)
    refresh_payload = verify_token(
        cookies[settings.REFRESH_COOKIE_NAME], token_type="refresh"
    )
    assert refresh_payload["sub"] == test_user.username
    assert "jti" in refresh_payload
    assert cookies[settings.CSRF_COOKIE_NAME]


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

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_token_refresh_uses_cookie_and_rotates_session(
    async_client: AsyncClient, test_user
):
    """Refresh reads the refresh token from the cookie and rotates it."""
    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    login_cookies = _auth_cookies(login_response)
    original_refresh = login_cookies[settings.REFRESH_COOKIE_NAME]

    response = await async_client.post(
        "/api/v2/auth/refresh",
        headers=_csrf_headers(login_cookies) | _cookie_headers(login_cookies),
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" not in data

    rotated_cookies = _auth_cookies(response)
    assert rotated_cookies[settings.REFRESH_COOKIE_NAME] != original_refresh


@pytest.mark.asyncio
async def test_token_refresh_rejects_missing_csrf(async_client: AsyncClient, test_user):
    """Refresh requires the CSRF header when the refresh cookie is present."""
    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )

    response = await async_client.post(
        "/api/v2/auth/refresh",
        headers=_cookie_headers(_auth_cookies(login_response)),
    )

    assert response.status_code == 403
    assert "csrf" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_token_refresh_rejects_inactive_account(
    async_client: AsyncClient, test_user, db_session
):
    """Test refresh rejects a token for an inactive account."""
    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    cookies = _auth_cookies(login_response)

    test_user.is_active = False
    await db_session.commit()

    response = await async_client.post(
        "/api/v2/auth/refresh",
        headers=_csrf_headers(cookies) | _cookie_headers(cookies),
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
    cookies = _auth_cookies(login_response)

    test_user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    await db_session.commit()

    response = await async_client.post(
        "/api/v2/auth/refresh",
        headers=_csrf_headers(cookies) | _cookie_headers(cookies),
    )

    assert response.status_code == 423
    assert "locked" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_refresh_cookie_uses_current_session_version(
    async_client: AsyncClient, test_user, db_session
):
    """Login mints a refresh cookie with the user's current session version."""
    test_user.session_version = 4
    await db_session.commit()

    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )

    assert response.status_code == 200
    payload = verify_token(
        response.cookies[settings.REFRESH_COOKIE_NAME], token_type="refresh"
    )
    assert payload["sv"] == 4


@pytest.mark.asyncio
async def test_refresh_rotation_preserves_current_session_version(
    async_client: AsyncClient, test_user, db_session
):
    """Refresh rotation keeps the user's current session version in the new token."""
    test_user.session_version = 6
    await db_session.commit()

    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    cookies = _auth_cookies(login_response)

    response = await async_client.post(
        "/api/v2/auth/refresh",
        headers=_csrf_headers(cookies) | _cookie_headers(cookies),
    )

    assert response.status_code == 200
    payload = verify_token(
        response.cookies[settings.REFRESH_COOKIE_NAME], token_type="refresh"
    )
    assert payload["sv"] == 6


@pytest.mark.asyncio
async def test_refresh_reuse_revokes_session_family(
    async_client: AsyncClient, test_user
):
    """Reusing a rotated refresh cookie should be treated as suspicious."""
    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    original_cookies = _auth_cookies(login_response)

    refresh_response = await async_client.post(
        "/api/v2/auth/refresh",
        headers=_csrf_headers(original_cookies) | _cookie_headers(original_cookies),
    )
    assert refresh_response.status_code == 200

    reuse_response = await async_client.post(
        "/api/v2/auth/refresh",
        headers=_csrf_headers(original_cookies) | _cookie_headers(original_cookies),
    )

    assert reuse_response.status_code == 401
    assert "invalid" in reuse_response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_rejects_access_token_in_refresh_cookie(
    async_client: AsyncClient, test_user
):
    """The cookie-backed refresh endpoint rejects access tokens."""
    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    cookies = _auth_cookies(login_response)
    cookies[settings.REFRESH_COOKIE_NAME] = login_response.json()["access_token"]

    response = await async_client.post(
        "/api/v2/auth/refresh",
        headers=_csrf_headers(cookies) | _cookie_headers(cookies),
    )

    assert response.status_code == 401
    assert "token type" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_rejects_signed_refresh_cookie_without_backing_session(
    async_client: AsyncClient, test_user
):
    """The cookie-backed refresh endpoint rejects orphaned refresh JWTs."""
    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    cookies = _auth_cookies(login_response)
    cookies[settings.REFRESH_COOKIE_NAME] = create_refresh_token(
        test_user.username, session_version=test_user.session_version
    )

    response = await async_client.post(
        "/api/v2/auth/refresh",
        headers=_csrf_headers(cookies) | _cookie_headers(cookies),
    )

    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_logout_clears_auth_cookies_without_access_token(
    async_client: AsyncClient, test_user
):
    """Logout can revoke the cookie-backed session without an access token."""
    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    cookies = _auth_cookies(login_response)

    response = await async_client.post(
        "/api/v2/auth/logout",
        headers=_csrf_headers(cookies) | _cookie_headers(cookies),
    )

    assert response.status_code == 200
    assert "Successfully logged out" in response.json()["message"]

    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(settings.REFRESH_COOKIE_NAME in header for header in set_cookie_headers)
    assert any(settings.CSRF_COOKIE_NAME in header for header in set_cookie_headers)


@pytest.mark.asyncio
async def test_logout_clears_auth_cookies_with_expired_access_token(
    async_client: AsyncClient, test_user
):
    """Logout still clears cookies when a stale bearer token is present."""
    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    cookies = _auth_cookies(login_response)
    expired_access_token = jwt.encode(
        {
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=2),
            "sub": test_user.username,
            "jti": "expired-access-token",
            "type": "access",
            "role": test_user.role,
            "permissions": test_user.get_permissions(),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    response = await async_client.post(
        "/api/v2/auth/logout",
        headers={
            **_csrf_headers(cookies),
            **_cookie_headers(cookies),
            "Authorization": f"Bearer {expired_access_token}",
        },
    )

    assert response.status_code == 200
    assert "Successfully logged out" in response.json()["message"]
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(settings.REFRESH_COOKIE_NAME in header for header in set_cookie_headers)
    assert any(settings.CSRF_COOKIE_NAME in header for header in set_cookie_headers)


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
