"""Tests for invite endpoints."""

import logging

import pytest

from app.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_rate_limit_cache():
    """Clear in-memory rate-limit counters between tests."""
    cache.clear_fallback()
    yield
    cache.clear_fallback()


@pytest.mark.asyncio
async def test_admin_can_create_invite(async_client, admin_headers):
    """POST /auth/users/invite creates an invite token."""
    resp = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "newcurator@example.com", "role": "curator"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newcurator@example.com"
    assert data["role"] == "curator"
    assert "expires_at" in data
    assert "token" in data  # Dev mode includes raw token


@pytest.mark.asyncio
async def test_invite_accept_creates_user(async_client, admin_headers):
    """POST /auth/invite/accept/{token} creates a user."""
    invite_resp = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "accept@example.com", "role": "curator"},
        headers=admin_headers,
    )
    assert invite_resp.status_code == 201
    token = invite_resp.json()["token"]

    accept_resp = await async_client.post(
        f"/api/v2/auth/invite/accept/{token}",
        json={
            "username": "accepted-user",
            "password": "SecurePass!2026",
            "full_name": "Accepted User",
        },
    )
    assert accept_resp.status_code == 201
    user = accept_resp.json()
    assert user["email"] == "accept@example.com"
    assert user["username"] == "accepted-user"
    assert user["role"] == "curator"
    assert user["is_verified"] is True


@pytest.mark.asyncio
async def test_invite_accept_rejects_duplicate_username(async_client, admin_headers):
    """Invite accept with existing username returns 409."""
    invite1 = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "user1@example.com", "role": "viewer"},
        headers=admin_headers,
    )
    invite2 = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "user2@example.com", "role": "viewer"},
        headers=admin_headers,
    )

    await async_client.post(
        f"/api/v2/auth/invite/accept/{invite1.json()['token']}",
        json={
            "username": "samename",
            "password": "SecurePass!2026",
            "full_name": "User 1",
        },
    )

    resp = await async_client.post(
        f"/api/v2/auth/invite/accept/{invite2.json()['token']}",
        json={
            "username": "samename",
            "password": "SecurePass!2026",
            "full_name": "User 2",
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_invite_accept_rejects_expired_token(async_client, db_session):
    """Expired invite token is rejected."""
    from datetime import timedelta

    from app.auth.credential_tokens import CredentialTokenService

    svc = CredentialTokenService(db_session)
    raw_token, _ = await svc.create_token(
        purpose="invite",
        email="expired@example.com",
        metadata={"role": "viewer"},
        expires_in=timedelta(seconds=-1),
    )
    await db_session.commit()

    resp = await async_client.post(
        f"/api/v2/auth/invite/accept/{raw_token}",
        json={
            "username": "expireduser",
            "password": "SecurePass!2026",
            "full_name": "Expired",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_invite_accept_rejects_already_used_token(async_client, admin_headers):
    """Already-used invite token is rejected on second use."""
    invite_resp = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "once@example.com", "role": "viewer"},
        headers=admin_headers,
    )
    token = invite_resp.json()["token"]

    await async_client.post(
        f"/api/v2/auth/invite/accept/{token}",
        json={
            "username": "firstuse",
            "password": "SecurePass!2026",
            "full_name": "First",
        },
    )

    resp = await async_client.post(
        f"/api/v2/auth/invite/accept/{token}",
        json={
            "username": "seconduse",
            "password": "SecurePass!2026",
            "full_name": "Second",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reinvite_invalidates_old_token(async_client, admin_headers):
    """Re-inviting the same email invalidates the old token."""
    invite1 = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "reinvite@example.com", "role": "viewer"},
        headers=admin_headers,
    )
    token1 = invite1.json()["token"]

    invite2 = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "reinvite@example.com", "role": "curator"},
        headers=admin_headers,
    )
    token2 = invite2.json()["token"]

    # Old token invalid
    resp1 = await async_client.post(
        f"/api/v2/auth/invite/accept/{token1}",
        json={
            "username": "oldtoken",
            "password": "SecurePass!2026",
            "full_name": "Old",
        },
    )
    assert resp1.status_code == 400

    # New token works
    resp2 = await async_client.post(
        f"/api/v2/auth/invite/accept/{token2}",
        json={
            "username": "newtoken",
            "password": "SecurePass!2026",
            "full_name": "New",
        },
    )
    assert resp2.status_code == 201
    assert resp2.json()["role"] == "curator"


@pytest.mark.asyncio
async def test_invite_logs_via_console_sender(async_client, admin_headers, caplog):
    """ConsoleEmailSender logs the invite email."""
    with caplog.at_level(logging.INFO, logger="app.auth.email"):
        await async_client.post(
            "/api/v2/auth/users/invite",
            json={"email": "logged@example.com", "role": "viewer"},
            headers=admin_headers,
        )
    assert "logged@example.com" in caplog.text


@pytest.mark.asyncio
async def test_non_admin_cannot_invite(async_client, viewer_headers):
    """Non-admin user gets 403 on invite endpoint."""
    resp = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "hacker@example.com", "role": "admin"},
        headers=viewer_headers,
    )
    assert resp.status_code == 403
