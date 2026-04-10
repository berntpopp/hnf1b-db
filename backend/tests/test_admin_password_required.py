"""Tests for ADMIN_PASSWORD startup validation.

Mirrors the JWT_SECRET validation pattern: the application must fail
fast on startup if ADMIN_PASSWORD is empty or unset, rather than silently
running with the historical default that leaked in git history.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_admin_password_required_raises_when_empty(monkeypatch):
    """Empty ADMIN_PASSWORD must raise ValidationError at Settings init."""
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    monkeypatch.setenv("JWT_SECRET", "0" * 64)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5433/test"
    )

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    errors = exc_info.value.errors()
    password_errors = [e for e in errors if "ADMIN_PASSWORD" in str(e)]
    assert len(password_errors) >= 1, (
        f"Expected ADMIN_PASSWORD error, got errors: {errors}"
    )


def test_admin_password_accepts_non_empty_value(monkeypatch):
    """A non-empty ADMIN_PASSWORD must allow Settings to construct."""
    monkeypatch.setenv("ADMIN_PASSWORD", "SomeStrongPassword!2026")
    monkeypatch.setenv("JWT_SECRET", "0" * 64)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5433/test"
    )

    settings = Settings(_env_file=None)
    assert settings.ADMIN_PASSWORD == "SomeStrongPassword!2026"
