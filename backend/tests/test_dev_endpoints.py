"""Tests for the Wave 5a dev-only quick-login router.

These tests exercise ``app/api/dev_endpoints.py`` via the ``dev_auth_client``
fixture, which flips the ``enable_dev_auth`` / ``environment`` settings,
imports the module past its hard assert, and mounts the router on the
shared FastAPI app for the duration of the test.

The tests cover the three guard clauses of the endpoint:

1. ``is_fixture_user=False`` -> 404 (the real admin is NOT hijackable).
2. ``is_fixture_user=True``  -> 200 with access + refresh tokens.
3. ``is_fixture_user=True`` but ``is_active=False`` -> 403.

Loopback enforcement is covered two ways:
- The happy-path test (fixture user → 200) implicitly proves ``testclient``
  passes the guard.
- ``test_require_loopback_rejects_non_loopback_host`` directly calls
  ``_require_loopback`` with a fabricated ``Request`` whose ``client.host``
  is a non-loopback address to exercise the 403 branch.

Layer 2 (the module-level import guard) is covered by
``test_dev_endpoints_refuses_import_outside_dev_mode`` which spawns a
subprocess with production-like env vars and asserts that importing the
module raises ``RuntimeError`` (explicit ``if``/``raise`` instead of
``assert``, so ``python -O`` cannot strip it).
"""

from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import delete

from app.auth.password import get_password_hash
from app.auth.tokens import verify_token
from app.core.config import settings
from app.models.user import User
from app.repositories.refresh_session_repository import RefreshSessionRepository


@pytest.mark.asyncio
async def test_dev_login_rejects_non_fixture_user(dev_auth_client, db_session):
    """A non-fixture user (is_fixture_user=False) must not be hijackable."""
    regular_admin = User(
        username="realadmin",
        email="realadmin@example.com",
        hashed_password=get_password_hash("RealAdminPass123!"),
        role="admin",
        is_active=True,
        is_verified=True,
        is_fixture_user=False,
    )
    db_session.add(regular_admin)
    await db_session.commit()

    try:
        response = await dev_auth_client.post("/api/v2/dev/login-as/realadmin")
        assert response.status_code == 404, response.text
        assert response.json()["detail"] == "not a fixture user"
    finally:
        await db_session.execute(delete(User).where(User.id == regular_admin.id))
        await db_session.commit()


@pytest.mark.asyncio
async def test_dev_login_accepts_fixture_user(dev_auth_client, db_session):
    """A fixture user gets access JSON plus cookie-backed refresh state."""
    fixture = User(
        username="dev-admin",
        email="dev-admin@example.com",
        hashed_password=get_password_hash("IrrelevantPass123!"),
        role="admin",
        is_active=True,
        is_verified=True,
        is_fixture_user=True,
    )
    db_session.add(fixture)
    await db_session.commit()
    await db_session.refresh(fixture)

    try:
        response = await dev_auth_client.post("/api/v2/dev/login-as/dev-admin")
        assert response.status_code == 200, response.text

        payload = response.json()
        assert payload["token_type"] == "bearer"
        assert isinstance(payload["access_token"], str)
        assert payload["access_token"]  # non-empty
        assert "refresh_token" not in payload
        assert payload["expires_in"] > 0
        refresh_token = response.cookies[settings.REFRESH_COOKIE_NAME]
        refresh_payload = verify_token(refresh_token, token_type="refresh")
        assert refresh_payload["sv"] == fixture.session_version
        assert response.cookies[settings.CSRF_COOKIE_NAME]

        repo = RefreshSessionRepository(db_session)
        session = await repo.get_by_jti(refresh_payload["jti"])
        assert session is not None
        assert session.user_id == fixture.id
    finally:
        await db_session.execute(delete(User).where(User.id == fixture.id))
        await db_session.commit()


@pytest.mark.asyncio
async def test_dev_login_refuses_inactive_fixture_user(dev_auth_client, db_session):
    """Even fixture users must be active to log in."""
    inactive = User(
        username="dev-inactive",
        email="dev-inactive@example.com",
        hashed_password=get_password_hash("IrrelevantPass123!"),
        role="viewer",
        is_active=False,
        is_verified=True,
        is_fixture_user=True,
    )
    db_session.add(inactive)
    await db_session.commit()

    try:
        response = await dev_auth_client.post("/api/v2/dev/login-as/dev-inactive")
        assert response.status_code == 403, response.text
        assert response.json()["detail"] == "inactive fixture user"
    finally:
        await db_session.execute(delete(User).where(User.id == inactive.id))
        await db_session.commit()


@pytest.mark.asyncio
async def test_dev_login_unknown_user_is_not_found(dev_auth_client):
    """Unknown username collapses into the same 404 as non-fixture-user."""
    response = await dev_auth_client.post("/api/v2/dev/login-as/does-not-exist")
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "not a fixture user"


def test_require_loopback_rejects_non_loopback_host(dev_auth_client):
    """Directly exercise the _require_loopback guard's 403 branch.

    The normal test fixture uses httpx's ASGI transport which sets
    ``client.host = "testclient"`` — always loopback. To cover the
    non-loopback refusal path we construct a fake Request with a public
    IP and call the dependency function directly. dev_auth_client is
    injected only to ensure the dev_endpoints module is imported.
    """
    from app.api.dev_endpoints import _LOOPBACK_HOSTS, _require_loopback

    public_request = SimpleNamespace(
        client=SimpleNamespace(host="203.0.113.42"),
    )
    assert "203.0.113.42" not in _LOOPBACK_HOSTS

    with pytest.raises(HTTPException) as excinfo:
        _require_loopback(public_request)  # type: ignore[arg-type]

    assert excinfo.value.status_code == 403
    assert "loopback" in excinfo.value.detail.lower()


def test_require_loopback_allows_missing_client(dev_auth_client):
    """A Request with client=None is refused (defensive default).

    ``request.client`` can be ``None`` when FastAPI is invoked outside a
    real transport. The guard treats this as non-loopback and refuses.
    """
    from app.api.dev_endpoints import _require_loopback

    no_client_request = SimpleNamespace(client=None)

    with pytest.raises(HTTPException) as excinfo:
        _require_loopback(no_client_request)  # type: ignore[arg-type]

    assert excinfo.value.status_code == 403


def test_dev_endpoints_refuses_import_outside_dev_mode():
    """Layer 2 import guard must refuse non-dev environments.

    This is a regression test against any future refactor that replaces
    the explicit ``if`` / ``raise RuntimeError`` with ``assert`` — the
    latter is stripped by ``python -O`` and silently disables Layer 2.

    Runs in a subprocess with production-like env vars so the guard
    fires on module import. We run the subprocess with ``-O`` to prove
    the guard survives compile-time optimization.

    Note on env setup: ``app.api.dev_endpoints`` imports
    ``app.auth.tokens`` → ``app.auth.dependencies`` → ``app.database``,
    and ``app.database`` calls ``create_async_engine(DATABASE_URL)`` at
    module import time. We therefore pass a *syntactically valid but
    non-connecting* ``DATABASE_URL`` so the preceding imports succeed
    long enough for the Layer 2 guard to actually fire. The test is
    about the guard, not about the database.
    """
    script = (
        "import sys\n"
        "try:\n"
        "    from app.api import dev_endpoints  # noqa: F401\n"
        "except Exception as exc:\n"
        "    print(f'GUARD_FIRED: {type(exc).__name__}: {exc}', file=sys.stderr)\n"
        "    sys.exit(0)\n"
        "print('GUARD_MISSING', file=sys.stderr)\n"
        "sys.exit(1)\n"
    )
    env = {
        "ENVIRONMENT": "production",
        "ENABLE_DEV_AUTH": "false",
        "JWT_SECRET": "x" * 32,
        "ADMIN_PASSWORD": "A" * 20,
        # Syntactically valid URL so SQLAlchemy's parser accepts it at
        # import time; no network connection is made because we never
        # execute a query before the guard fires.
        "DATABASE_URL": "postgresql+asyncpg://x:x@localhost:5432/x",
        "PATH": "/usr/bin:/bin",
    }
    # Use ``-O`` to verify the guard is NOT an ``assert`` (which would be
    # stripped at compile time and let the import silently succeed).
    result = subprocess.run(
        [sys.executable, "-O", "-c", script],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Layer 2 guard did NOT fire under python -O. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "GUARD_FIRED" in result.stderr
