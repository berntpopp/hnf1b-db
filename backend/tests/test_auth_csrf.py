"""Tests for auth cookie helpers and CSRF validation."""

from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.auth import dependencies as auth_dependencies
from app.auth.dependencies import (
    get_best_effort_user,
    require_csrf_token,
    require_session_then_csrf,
)
from app.auth.session_cookies import clear_auth_cookies, set_auth_cookies
from app.core.config import Settings, settings


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


@pytest.mark.asyncio
async def test_get_best_effort_user_handles_missing_credentials_from_security(
    monkeypatch,
):
    """Best-effort auth returns None if optional security yields no credentials."""
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v2/auth/logout",
            "headers": [(b"authorization", b"Bearer token")],
        }
    )

    async def fake_optional_security(_request):
        return None

    monkeypatch.setattr(auth_dependencies, "_optional_security", fake_optional_security)

    assert await get_best_effort_user(request, db=None) is None


async def test_cors_preflight_allows_csrf_header(async_client):
    """CORS preflight admits the double-submit CSRF header."""
    response = await async_client.options(
        "/api/v2/auth/refresh",
        headers={
            "Origin": settings.get_cors_origins_list()[0],
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-token",
        },
    )

    assert response.status_code == 200
    allow_headers = response.headers["access-control-allow-headers"].lower()
    assert "content-type" in allow_headers
    assert "x-csrf-token" in allow_headers


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


# ----- require_session_then_csrf (issue #288) -----


def _request_with_cookies(*, refresh: str | None, csrf_cookie: str | None, csrf_header: str | None) -> Request:
    """Build a Starlette request with optional refresh cookie + CSRF pair."""
    cookie_parts: list[str] = []
    if refresh is not None:
        cookie_parts.append(f"refresh_token={refresh}")
    if csrf_cookie is not None:
        cookie_parts.append(f"csrf_token={csrf_cookie}")

    headers: list[tuple[bytes, bytes]] = []
    if cookie_parts:
        headers.append((b"cookie", "; ".join(cookie_parts).encode()))
    if csrf_header is not None:
        headers.append((b"x-csrf-token", csrf_header.encode()))

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v2/auth/refresh",
        "headers": headers,
    }
    return Request(scope)


async def test_require_session_then_csrf_returns_401_when_no_session_cookie():
    """Anonymous bootstrap probe (no refresh cookie) returns 401, not 403."""
    request = _request_with_cookies(refresh=None, csrf_cookie=None, csrf_header=None)

    try:
        await require_session_then_csrf(request)
    except Exception as exc:  # noqa: BLE001
        assert getattr(exc, "status_code", None) == 401
        assert "no active session" in str(getattr(exc, "detail", "")).lower()
    else:  # pragma: no cover - red phase guard
        raise AssertionError("Expected 401 when refresh cookie is absent")


async def test_require_session_then_csrf_returns_403_when_session_present_but_csrf_missing():
    """With a refresh session cookie but no CSRF header, fall through to 403."""
    request = _request_with_cookies(
        refresh="rt-xyz", csrf_cookie="csrf-abc", csrf_header=None
    )

    try:
        await require_session_then_csrf(request)
    except Exception as exc:  # noqa: BLE001
        assert getattr(exc, "status_code", None) == 403
        assert "csrf" in str(getattr(exc, "detail", "")).lower()
    else:  # pragma: no cover - red phase guard
        raise AssertionError("Expected 403 when CSRF header is missing despite session cookie")


async def test_require_session_then_csrf_accepts_full_session_with_matching_csrf():
    """Refresh cookie + matching CSRF cookie/header pair is accepted (returns None)."""
    request = _request_with_cookies(
        refresh="rt-xyz", csrf_cookie="csrf-abc", csrf_header="csrf-abc"
    )

    assert await require_session_then_csrf(request) is None
