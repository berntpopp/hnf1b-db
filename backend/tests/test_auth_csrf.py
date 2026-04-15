"""Tests for auth cookie helpers and CSRF validation."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response

from app.auth.dependencies import require_csrf_token
from app.auth.session_cookies import clear_auth_cookies, set_auth_cookies
from app.core.config import Settings


def _request_with_csrf(*, cookie: str | None, header: str | None) -> Request:
    """Build a Starlette request with optional CSRF cookie and header."""
    headers: list[tuple[bytes, bytes]] = []
    if cookie is not None:
        headers.append((b"cookie", f"csrf_token={cookie}".encode()))
    if header is not None:
        headers.append((b"x-csrf-token", header.encode()))

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v2/auth/refresh",
        "headers": headers,
    }
    return Request(scope)


def test_set_auth_cookies_sets_refresh_and_csrf_cookies():
    """Cookie helper sets both refresh and CSRF cookies with auth flags."""
    response = Response()

    set_auth_cookies(response, refresh_token="refresh-token", csrf_token="csrf-token")

    set_cookie_headers = response.headers.getlist("set-cookie")
    assert any("refresh_token=refresh-token" in header for header in set_cookie_headers)
    assert any(
        "HttpOnly" in header and "refresh_token=" in header
        for header in set_cookie_headers
    )
    assert any("csrf_token=csrf-token" in header for header in set_cookie_headers)
    assert any("SameSite=lax" in header for header in set_cookie_headers)
    assert any(
        "refresh_token=refresh-token" in header and "Path=/api/v2" in header
        for header in set_cookie_headers
    )
    assert any(
        "csrf_token=csrf-token" in header and "Path=/" in header
        for header in set_cookie_headers
    )


def test_clear_auth_cookies_expires_refresh_and_csrf_cookies():
    """Cookie helper clears both auth cookies."""
    response = Response()

    clear_auth_cookies(response)

    set_cookie_headers = response.headers.getlist("set-cookie")
    assert any(
        'refresh_token=""' in header or "refresh_token=" in header
        for header in set_cookie_headers
    )
    assert any(
        'csrf_token=""' in header or "csrf_token=" in header
        for header in set_cookie_headers
    )
    assert all("Max-Age=0" in header for header in set_cookie_headers)


async def test_require_csrf_token_rejects_missing_header():
    """Missing CSRF header is rejected."""
    request = _request_with_csrf(cookie="csrf-token", header=None)

    try:
        await require_csrf_token(request)
    except Exception as exc:  # noqa: BLE001
        assert getattr(exc, "status_code", None) == 403
        assert "csrf" in str(getattr(exc, "detail", "")).lower()
    else:  # pragma: no cover - red phase guard
        raise AssertionError("Expected missing CSRF header to be rejected")


async def test_require_csrf_token_rejects_mismatched_header():
    """Mismatched CSRF cookie/header pair is rejected."""
    request = _request_with_csrf(cookie="csrf-token", header="wrong-token")

    try:
        await require_csrf_token(request)
    except Exception as exc:  # noqa: BLE001
        assert getattr(exc, "status_code", None) == 403
        assert "csrf" in str(getattr(exc, "detail", "")).lower()
    else:  # pragma: no cover - red phase guard
        raise AssertionError("Expected mismatched CSRF token to be rejected")


async def test_require_csrf_token_accepts_matching_cookie_and_header():
    """Matching CSRF cookie/header pair is accepted."""
    request = _request_with_csrf(cookie="csrf-token", header="csrf-token")

    assert await require_csrf_token(request) is None


def test_settings_expose_cookie_defaults():
    """Settings expose explicit auth-cookie defaults for the backend contract."""
    settings = Settings(
        JWT_SECRET="test-secret-key-abc123",
        ADMIN_PASSWORD="TestAdminPass!2026",
    )

    assert settings.REFRESH_COOKIE_NAME == "refresh_token"
    assert settings.CSRF_COOKIE_NAME == "csrf_token"
    assert settings.AUTH_COOKIE_PATH == "/api/v2"
    assert settings.CSRF_COOKIE_PATH == "/"
    assert settings.AUTH_COOKIE_SAMESITE == "lax"
