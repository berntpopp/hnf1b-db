"""Tests for the Wave 5a dev-only quick-login router.

These tests exercise ``app/api/dev_endpoints.py`` via the ``dev_auth_client``
fixture, which flips the ``enable_dev_auth`` / ``environment`` settings,
imports the module past its hard assert, and mounts the router on the
shared FastAPI app for the duration of the test.

The tests cover the three guard clauses of the endpoint:

1. ``is_fixture_user=False`` -> 404 (the real admin is NOT hijackable).
2. ``is_fixture_user=True``  -> 200 with access + refresh tokens.
3. ``is_fixture_user=True`` but ``is_active=False`` -> 403.

Loopback enforcement is covered implicitly: httpx's ASGI transport sets
``request.client.host`` to ``"testclient"``, which is inside the
allow-list, so the happy-path test reaching 200 proves the guard did not
fire. Direct coverage of the 403 branch would require spoofing
``client.host``; that is deferred to Task 10's integration test where a
fake scope is easier to construct.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.auth.password import get_password_hash
from app.models.user import User


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
    """A fixture user gets freshly minted access + refresh tokens."""
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
        assert isinstance(payload["refresh_token"], str)
        assert payload["access_token"]  # non-empty
        assert payload["refresh_token"]  # non-empty
        assert payload["expires_in"] > 0

        # The refresh token must have been persisted so /auth/refresh works.
        await db_session.refresh(fixture)
        assert fixture.refresh_token == payload["refresh_token"]
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
