"""Tests for password change invalidation semantics."""

from __future__ import annotations

import pytest

from app.core.config import settings


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
async def test_change_password_invalidates_existing_refresh_cookie(
    async_client, test_user, db_session
):
    """A refresh cookie minted before password change cannot refresh afterward."""
    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    cookies = _auth_cookies(login_response)
    access_token = login_response.json()["access_token"]
    original_version = test_user.session_version

    change_response = await async_client.post(
        "/api/v2/auth/change-password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "current_password": "TestPass123!",
            "new_password": "NewPass456!",
        },
    )
    assert change_response.status_code == 200

    await db_session.refresh(test_user)
    assert test_user.session_version == original_version + 1

    refresh_response = await async_client.post(
        "/api/v2/auth/refresh",
        headers=_cookie_headers(cookies),
    )

    assert refresh_response.status_code == 401
    assert "invalid" in refresh_response.json()["detail"].lower()
