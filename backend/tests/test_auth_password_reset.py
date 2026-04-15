"""Tests for password reset endpoints."""

import pytest

from app.core.cache import cache
from app.core.config import settings
from app.models.user import User


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


@pytest.fixture(autouse=True)
def _clear_rate_limit_cache():
    """Clear in-memory rate-limit counters between tests."""
    cache.clear_fallback()
    yield
    cache.clear_fallback()


@pytest.mark.asyncio
async def test_reset_request_returns_202_for_existing_email(
    async_client, admin_headers
):
    """POST /auth/password-reset/request returns 202 when email exists."""
    me_resp = await async_client.get("/api/v2/auth/me", headers=admin_headers)
    admin_email = me_resp.json()["email"]

    resp = await async_client.post(
        "/api/v2/auth/password-reset/request",
        json={"email": admin_email},
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_reset_request_returns_202_for_nonexistent_email(async_client):
    """POST /auth/password-reset/request returns 202 even when email doesn't exist."""
    resp = await async_client.post(
        "/api/v2/auth/password-reset/request",
        json={"email": "nonexistent@example.com"},
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_reset_confirm_changes_password(async_client, admin_headers):
    """Full reset flow: request -> get token -> confirm -> login with new password."""
    me_resp = await async_client.get("/api/v2/auth/me", headers=admin_headers)
    admin_email = me_resp.json()["email"]
    admin_username = me_resp.json()["username"]

    reset_resp = await async_client.post(
        "/api/v2/auth/password-reset/request",
        json={"email": admin_email},
    )
    assert reset_resp.status_code == 202
    token = reset_resp.json().get("token")
    assert token is not None  # Dev mode includes token

    confirm_resp = await async_client.post(
        f"/api/v2/auth/password-reset/confirm/{token}",
        json={"new_password": "NewSecurePass!2026"},
    )
    assert confirm_resp.status_code == 200

    login_resp = await async_client.post(
        "/api/v2/auth/login",
        json={"username": admin_username, "password": "NewSecurePass!2026"},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_reset_confirm_invalidates_existing_refresh_token(
    async_client, admin_headers, db_session
):
    """Password rotation should retire the previous refresh token."""
    me_resp = await async_client.get("/api/v2/auth/me", headers=admin_headers)
    admin_email = me_resp.json()["email"]
    admin_username = me_resp.json()["username"]
    admin_id = me_resp.json()["id"]

    login_resp = await async_client.post(
        "/api/v2/auth/login",
        json={"username": admin_username, "password": "AdminPass123!"},
    )
    assert login_resp.status_code == 200
    cookies = _auth_cookies(login_resp)

    reset_resp = await async_client.post(
        "/api/v2/auth/password-reset/request",
        json={"email": admin_email},
    )
    token = reset_resp.json().get("token")
    assert token is not None  # Dev mode includes token

    confirm_resp = await async_client.post(
        f"/api/v2/auth/password-reset/confirm/{token}",
        json={"new_password": "NewSecurePass!2026"},
    )
    assert confirm_resp.status_code == 200

    admin_user = await db_session.get(User, admin_id)
    assert admin_user is not None
    assert admin_user.session_version == 2

    refresh_resp = await async_client.post(
        "/api/v2/auth/refresh",
        headers=_cookie_headers(cookies),
    )
    assert refresh_resp.status_code == 401
    assert "invalid" in refresh_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reset_confirm_rejects_invalid_token(async_client):
    """Invalid token returns 400."""
    resp = await async_client.post(
        "/api/v2/auth/password-reset/confirm/invalid-token-xyz",
        json={"new_password": "NewSecurePass!2026"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_confirm_invalidates_old_tokens(async_client, admin_headers):
    """After successful reset, prior tokens for same email are invalidated."""
    me_resp = await async_client.get("/api/v2/auth/me", headers=admin_headers)
    admin_email = me_resp.json()["email"]

    resp1 = await async_client.post(
        "/api/v2/auth/password-reset/request", json={"email": admin_email}
    )
    token1 = resp1.json()["token"]

    resp2 = await async_client.post(
        "/api/v2/auth/password-reset/request", json={"email": admin_email}
    )
    token2 = resp2.json()["token"]

    await async_client.post(
        f"/api/v2/auth/password-reset/confirm/{token2}",
        json={"new_password": "NewSecurePass!2026"},
    )

    resp = await async_client.post(
        f"/api/v2/auth/password-reset/confirm/{token1}",
        json={"new_password": "AnotherPass!2026"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_confirm_rejects_already_used_token(async_client, admin_headers):
    """Token can only be used once."""
    me_resp = await async_client.get("/api/v2/auth/me", headers=admin_headers)
    admin_email = me_resp.json()["email"]

    resp = await async_client.post(
        "/api/v2/auth/password-reset/request", json={"email": admin_email}
    )
    token = resp.json()["token"]

    await async_client.post(
        f"/api/v2/auth/password-reset/confirm/{token}",
        json={"new_password": "NewSecurePass!2026"},
    )

    resp2 = await async_client.post(
        f"/api/v2/auth/password-reset/confirm/{token}",
        json={"new_password": "AnotherPass!2026"},
    )
    assert resp2.status_code == 400
