"""Regression test: admin script must not echo the password when the user already exists."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import scripts.create_admin_user as admin_script


class _StubResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_existing_admin_branch_does_not_print_password(monkeypatch):
    """When the admin already exists the script must NOT echo the password."""
    secret = "super-secret-rotation-value-9000"
    monkeypatch.setattr(admin_script.settings, "ADMIN_USERNAME", "admin", raising=False)
    monkeypatch.setattr(
        admin_script.settings, "ADMIN_EMAIL", "admin@example.com", raising=False
    )
    monkeypatch.setattr(admin_script.settings, "ADMIN_PASSWORD", secret, raising=False)
    monkeypatch.setattr(
        admin_script.settings, "DATABASE_URL", "postgresql+asyncpg://x/y", raising=False
    )

    existing_admin = MagicMock()
    existing_admin.id = 7

    fake_session = MagicMock()
    fake_session.execute = AsyncMock(return_value=_StubResult(existing_admin))
    fake_session.commit = AsyncMock()
    fake_session.rollback = AsyncMock()

    fake_session_ctx = MagicMock()
    fake_session_ctx.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_ctx.__aexit__ = AsyncMock(return_value=False)

    fake_sessionmaker = MagicMock(return_value=fake_session_ctx)

    fake_engine = MagicMock()
    fake_engine.dispose = AsyncMock()

    with (
        patch.object(admin_script, "create_async_engine", return_value=fake_engine),
        patch.object(
            admin_script, "async_sessionmaker", return_value=fake_sessionmaker
        ),
    ):
        buf = io.StringIO()
        with redirect_stdout(buf):
            await admin_script.create_admin_user()
        output = buf.getvalue()

    assert secret not in output, "ADMIN_PASSWORD must never be echoed on update path"
    assert "Password:" not in output, (
        "Plain 'Password:' label must not appear on update path"
    )


@pytest.mark.asyncio
async def test_creation_branch_still_prints_credentials(monkeypatch):
    """Brand-new admin path keeps printing the credential block (intentional)."""
    secret = "fresh-install-password-9000"
    monkeypatch.setattr(admin_script.settings, "ADMIN_USERNAME", "admin", raising=False)
    monkeypatch.setattr(
        admin_script.settings, "ADMIN_EMAIL", "admin@example.com", raising=False
    )
    monkeypatch.setattr(admin_script.settings, "ADMIN_PASSWORD", secret, raising=False)
    monkeypatch.setattr(
        admin_script.settings, "DATABASE_URL", "postgresql+asyncpg://x/y", raising=False
    )

    fake_session = MagicMock()
    fake_session.execute = AsyncMock(return_value=_StubResult(None))
    fake_session.commit = AsyncMock()
    fake_session.refresh = AsyncMock()
    fake_session.rollback = AsyncMock()
    fake_session.add = MagicMock()

    fake_session_ctx = MagicMock()
    fake_session_ctx.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_ctx.__aexit__ = AsyncMock(return_value=False)

    fake_sessionmaker = MagicMock(return_value=fake_session_ctx)

    fake_engine = MagicMock()
    fake_engine.dispose = AsyncMock()

    with (
        patch.object(admin_script, "create_async_engine", return_value=fake_engine),
        patch.object(
            admin_script, "async_sessionmaker", return_value=fake_sessionmaker
        ),
    ):
        buf = io.StringIO()
        with redirect_stdout(buf):
            await admin_script.create_admin_user()
        output = buf.getvalue()

    assert secret in output, (
        "Creation path is allowed to echo password once for first-run UX"
    )
    assert "Login credentials" in output
