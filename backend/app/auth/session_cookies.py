"""Helpers for auth cookies used by the browser refresh flow."""

from __future__ import annotations

from starlette.responses import Response

from app.core.config import settings


def set_auth_cookies(
    response: Response, *, refresh_token: str, csrf_token: str
) -> None:
    """Attach refresh and CSRF cookies to a response."""
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path=settings.AUTH_COOKIE_PATH,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path=settings.CSRF_COOKIE_PATH,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


def clear_auth_cookies(response: Response) -> None:
    """Expire both auth cookies on a response."""
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.AUTH_COOKIE_PATH,
    )
    response.delete_cookie(
        key=settings.CSRF_COOKIE_NAME,
        path=settings.CSRF_COOKIE_PATH,
    )
