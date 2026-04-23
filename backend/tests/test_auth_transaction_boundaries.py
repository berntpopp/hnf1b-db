"""Tests for auth transaction ownership in credential flows."""

import hashlib

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.auth.credential_tokens import CredentialTokenService
from app.auth.password import get_password_hash
from app.auth.tokens import create_access_token
from app.core.cache import cache
from app.models.credential_token import CredentialToken
from app.models.user import User


@pytest_asyncio.fixture(autouse=True)
async def _clear_rate_limit_cache():
    """Clear rate-limit cache before each test."""
    cache.use_fallback_only()
    cache.clear_fallback()
    yield
    cache.clear_fallback()


def _token_hash(raw_token: str) -> str:
    """Return the stored hash for a raw credential token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def _get_token(db_session, raw_token: str) -> CredentialToken:
    """Load a credential token row by raw token value."""
    result = await db_session.execute(
        select(CredentialToken).where(
            CredentialToken.token_sha256 == _token_hash(raw_token)
        )
    )
    token = result.scalar_one_or_none()
    assert token is not None
    return token


@pytest.mark.asyncio
async def test_invite_accept_duplicate_username_does_not_consume_token(
    async_client, admin_headers, db_session
):
    """Invite acceptance failures should not burn the invite token."""
    invite_resp = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "duplicate-invite@example.com", "role": "viewer"},
        headers=admin_headers,
    )
    assert invite_resp.status_code == 201
    token = invite_resp.json()["token"]

    first_accept = await async_client.post(
        f"/api/v2/auth/invite/accept/{token}",
        json={
            "username": "shared-name",
            "password": "SecurePass!2026",
            "full_name": "First User",
        },
    )
    assert first_accept.status_code == 201

    second_invite = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "second-duplicate@example.com", "role": "viewer"},
        headers=admin_headers,
    )
    assert second_invite.status_code == 201
    second_token = second_invite.json()["token"]

    duplicate_resp = await async_client.post(
        f"/api/v2/auth/invite/accept/{second_token}",
        json={
            "username": "shared-name",
            "password": "SecurePass!2026",
            "full_name": "Second User",
        },
    )
    assert duplicate_resp.status_code == 409

    db_token = await _get_token(db_session, second_token)
    assert db_token.used_at is None


@pytest.mark.asyncio
async def test_password_reset_missing_user_does_not_consume_token(
    async_client, admin_headers, db_session
):
    """Password reset confirm should roll back token consumption on invalid token state."""
    me_resp = await async_client.get("/api/v2/auth/me", headers=admin_headers)
    admin_email = me_resp.json()["email"]
    token_svc = CredentialTokenService(db_session)
    token, _ = await token_svc.create_token(
        purpose="reset",
        email=admin_email,
    )
    await db_session.commit()

    confirm_resp = await async_client.post(
        f"/api/v2/auth/password-reset/confirm/{token}",
        json={"new_password": "NewSecurePass!2026"},
    )
    assert confirm_resp.status_code == 400

    db_token = await _get_token(db_session, token)
    assert db_token.used_at is None


@pytest.mark.asyncio
async def test_verify_email_missing_user_does_not_consume_token(
    async_client, db_session
):
    """Email verification should roll back token consumption on invalid token state."""
    user = User(
        username="verify-missing",
        email="verify-missing@example.com",
        hashed_password=get_password_hash("VerifyPass!2026"),
        role="viewer",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token_svc = CredentialTokenService(db_session)
    token, _ = await token_svc.create_token(
        purpose="verify",
        email=user.email,
    )
    await db_session.commit()

    verify_resp = await async_client.post(f"/api/v2/auth/verify-email/{token}")
    assert verify_resp.status_code == 400

    db_token = await _get_token(db_session, token)
    assert db_token.used_at is None


@pytest.mark.asyncio
async def test_create_invite_rolls_back_old_token_invalidation_on_failure(
    async_client, admin_headers, db_session, monkeypatch
):
    """Invite replacement should leave the old token valid if new creation fails."""
    first_resp = await async_client.post(
        "/api/v2/auth/users/invite",
        json={"email": "reinvite-failure@example.com", "role": "viewer"},
        headers=admin_headers,
    )
    assert first_resp.status_code == 201
    first_token = first_resp.json()["token"]

    async def _boom(*args, **kwargs):
        raise RuntimeError("create token failed")

    monkeypatch.setattr(
        "app.auth.credential_tokens.CredentialTokenService.create_token",
        _boom,
    )

    with pytest.raises(RuntimeError, match="create token failed"):
        await async_client.post(
            "/api/v2/auth/users/invite",
            json={"email": "reinvite-failure@example.com", "role": "curator"},
            headers=admin_headers,
        )

    db_token = await _get_token(db_session, first_token)
    assert db_token.used_at is None


@pytest.mark.asyncio
async def test_password_reset_request_rolls_back_old_token_invalidation_on_failure(
    async_client, admin_headers, db_session, monkeypatch
):
    """Reset request should leave prior token valid if replacement creation fails."""
    me_resp = await async_client.get("/api/v2/auth/me", headers=admin_headers)
    admin_email = me_resp.json()["email"]

    first_resp = await async_client.post(
        "/api/v2/auth/password-reset/request",
        json={"email": admin_email},
    )
    assert first_resp.status_code == 202
    first_token = first_resp.json()["token"]

    async def _boom(*args, **kwargs):
        raise RuntimeError("create token failed")

    monkeypatch.setattr(
        "app.auth.credential_tokens.CredentialTokenService.create_token",
        _boom,
    )

    with pytest.raises(RuntimeError, match="create token failed"):
        await async_client.post(
            "/api/v2/auth/password-reset/request",
            json={"email": admin_email},
        )

    db_token = await _get_token(db_session, first_token)
    assert db_token.used_at is None


@pytest.mark.asyncio
async def test_verify_resend_rolls_back_old_token_invalidation_on_failure(
    async_client, db_session, monkeypatch
):
    """Verification resend should leave the prior token valid if creation fails."""
    user = User(
        username="verify-resend-failure",
        email="verify-resend-failure@example.com",
        hashed_password=get_password_hash("VerifyPass!2026"),
        role="viewer",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token_svc = CredentialTokenService(db_session)
    first_token, _ = await token_svc.create_token(
        purpose="verify",
        email=user.email,
        user_id=user.id,
    )
    await db_session.commit()

    access_token = create_access_token(user.username, user.role, user.get_permissions())
    headers = {"Authorization": f"Bearer {access_token}"}

    async def _boom(*args, **kwargs):
        raise RuntimeError("create token failed")

    monkeypatch.setattr(
        "app.auth.credential_tokens.CredentialTokenService.create_token",
        _boom,
    )

    with pytest.raises(RuntimeError, match="create token failed"):
        await async_client.post(
            "/api/v2/auth/verify-email/resend",
            headers=headers,
        )

    db_token = await _get_token(db_session, first_token)
    assert db_token.used_at is None
