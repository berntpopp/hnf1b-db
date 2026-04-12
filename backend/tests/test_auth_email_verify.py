"""Tests for email verification endpoints."""

import logging

import pytest
import pytest_asyncio

from app.core.cache import cache


@pytest_asyncio.fixture(autouse=True)
async def _clear_rate_limit_cache():
    """Clear rate-limit cache before each test to avoid cross-test pollution."""
    cache.use_fallback_only()
    cache.clear_fallback()
    yield
    cache.clear_fallback()


@pytest.mark.asyncio
async def test_admin_create_user_dispatches_verify_email(
    async_client, admin_headers, caplog
):
    """POST /auth/users (admin create) auto-dispatches verification email."""
    with caplog.at_level(logging.INFO, logger="app.auth.email"):
        resp = await async_client.post(
            "/api/v2/auth/users",
            json={
                "username": "verifytest",
                "email": "verifytest@example.com",
                "password": "VerifyTest!2026",
                "full_name": "Verify Test",
                "role": "viewer",
            },
            headers=admin_headers,
        )
    assert resp.status_code == 201
    assert resp.json()["is_verified"] is False
    assert "verifytest@example.com" in caplog.text


@pytest.mark.asyncio
async def test_verify_email_sets_verified(async_client, admin_headers, db_session):
    """POST /auth/verify-email/{token} sets is_verified=True."""
    from app.auth.credential_tokens import CredentialTokenService

    # Create user
    create_resp = await async_client.post(
        "/api/v2/auth/users",
        json={
            "username": "verifyable",
            "email": "verifyable@example.com",
            "password": "VerifyMe!2026",
            "full_name": "Verifyable User",
            "role": "viewer",
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    # Create a verify token directly (the auto-dispatched one isn't returned in create response)
    svc = CredentialTokenService(db_session)
    raw_token, _ = await svc.create_token(
        purpose="verify",
        email="verifyable@example.com",
        user_id=user_id,
    )

    resp = await async_client.post(f"/api/v2/auth/verify-email/{raw_token}")
    assert resp.status_code == 200

    user_resp = await async_client.get(
        f"/api/v2/auth/users/{user_id}",
        headers=admin_headers,
    )
    assert user_resp.json()["is_verified"] is True


@pytest.mark.asyncio
async def test_verify_email_rejects_invalid_token(async_client):
    """Invalid verify token returns 400."""
    resp = await async_client.post("/api/v2/auth/verify-email/invalid-token-xyz")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_single_use(async_client, db_session):
    """Verify token can only be used once."""
    from app.auth.credential_tokens import CredentialTokenService
    from app.auth.password import get_password_hash
    from app.models.user import User

    user = User(
        username="singleuse",
        email="singleuse@example.com",
        hashed_password=get_password_hash("TestPass!2026"),
        role="viewer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    svc = CredentialTokenService(db_session)
    raw_token, _ = await svc.create_token(
        purpose="verify", email="singleuse@example.com", user_id=user.id
    )

    resp1 = await async_client.post(f"/api/v2/auth/verify-email/{raw_token}")
    assert resp1.status_code == 200

    resp2 = await async_client.post(f"/api/v2/auth/verify-email/{raw_token}")
    assert resp2.status_code == 400


@pytest.mark.asyncio
async def test_verify_resend_creates_new_token(async_client, db_session):
    """POST /auth/verify-email/resend creates a new verify token."""
    from app.auth.password import get_password_hash
    from app.auth.tokens import create_access_token
    from app.models.user import User

    user = User(
        username="resenduser",
        email="resend@example.com",
        hashed_password=get_password_hash("TestPass!2026"),
        role="viewer",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    access_token = create_access_token(user.username, user.role, user.get_permissions())
    headers = {"Authorization": f"Bearer {access_token}"}

    resp = await async_client.post(
        "/api/v2/auth/verify-email/resend",
        headers=headers,
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_verify_resend_rejects_already_verified(async_client, admin_headers):
    """Resend returns 400 if user is already verified."""
    # Admin fixture user is already verified
    resp = await async_client.post(
        "/api/v2/auth/verify-email/resend",
        headers=admin_headers,
    )
    assert resp.status_code == 400
