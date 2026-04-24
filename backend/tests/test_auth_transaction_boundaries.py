"""Tests for auth transaction ownership in credential flows."""

import hashlib

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select

from app.auth import verify_password
from app.auth.credential_tokens import CredentialTokenService
from app.auth.password import get_password_hash
from app.auth.tokens import create_access_token
from app.core.cache import cache
from app.core.config import settings
from app.database import async_session_maker
from app.models.credential_token import CredentialToken
from app.models.user import User
from app.repositories.user_repository import UserRepository


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


async def _get_user_fresh(user_id: int) -> User | None:
    """Load a user through a fresh database session."""
    async with async_session_maker() as fresh_session:
        repo = UserRepository(fresh_session)
        return await repo.get_by_id(user_id)


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


@pytest.mark.asyncio
async def test_admin_create_user_rolls_back_user_if_verify_token_creation_fails(
    async_client, admin_headers, db_session, monkeypatch
):
    """Admin create-user should not persist the user before verify-token work succeeds."""

    async def _boom(*args, **kwargs):
        raise HTTPException(status_code=503, detail="verify token creation failed")

    monkeypatch.setattr(
        "app.auth.credential_tokens.CredentialTokenService.create_token",
        _boom,
    )

    response = await async_client.post(
        "/api/v2/auth/users",
        json={
            "username": "atomic-create-failure",
            "email": "atomic-create-failure@example.com",
            "password": "AtomicCreate!2026",
            "full_name": "Atomic Create Failure",
            "role": "viewer",
        },
        headers=admin_headers,
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "verify token creation failed"

    async with async_session_maker() as fresh_session:
        repo = UserRepository(fresh_session)
        assert await repo.get_by_username("atomic-create-failure") is None
        assert await repo.get_by_email("atomic-create-failure@example.com") is None


@pytest.mark.asyncio
async def test_change_password_rolls_back_password_if_refresh_revocation_fails(
    async_client, db_session, monkeypatch
):
    """Password change should remain atomic with refresh-capability revocation."""
    original_password = "AtomicPassword!2026"
    new_password = "AtomicPasswordNew!2026"
    user = User(
        username="atomic-password-user",
        email="atomic-password-user@example.com",
        hashed_password=get_password_hash(original_password),
        role="viewer",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user_id = user.id
    username = user.username

    login_resp = await async_client.post(
        "/api/v2/auth/login",
        json={"username": user.username, "password": original_password},
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]

    async def _boom(*args, **kwargs):
        raise HTTPException(status_code=503, detail="refresh revoke failed")

    monkeypatch.setattr(
        "app.api.auth_endpoints._revoke_all_refresh_capability_in_transaction",
        _boom,
    )

    response = await async_client.post(
        "/api/v2/auth/change-password",
        json={
            "current_password": original_password,
            "new_password": new_password,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "refresh revoke failed"

    updated_user = await _get_user_fresh(user_id)
    assert updated_user is not None
    assert verify_password(original_password, updated_user.hashed_password)
    assert not verify_password(new_password, updated_user.hashed_password)

    old_login = await async_client.post(
        "/api/v2/auth/login",
        json={"username": username, "password": original_password},
    )
    assert old_login.status_code == 200

    new_login = await async_client.post(
        "/api/v2/auth/login",
        json={"username": username, "password": new_password},
    )
    assert new_login.status_code == 401


@pytest.mark.asyncio
async def test_admin_deactivate_rolls_back_user_state_if_refresh_revocation_fails(
    async_client, admin_headers, db_session, monkeypatch
):
    """Admin deactivation should not persist if refresh-session revocation fails."""
    create_resp = await async_client.post(
        "/api/v2/auth/users",
        json={
            "username": "atomic-deactivate-user",
            "email": "atomic-deactivate-user@example.com",
            "password": "AtomicDeactivate!2026",
            "full_name": "Atomic Deactivate User",
            "role": "viewer",
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    login_resp = await async_client.post(
        "/api/v2/auth/login",
        json={"username": "atomic-deactivate-user", "password": "AtomicDeactivate!2026"},
    )
    assert login_resp.status_code == 200
    refresh_cookie = login_resp.cookies["refresh_token"]
    csrf_cookie = login_resp.cookies["csrf_token"]

    async def _boom(*args, **kwargs):
        raise HTTPException(status_code=503, detail="refresh revoke failed")

    monkeypatch.setattr(
        "app.api.auth_endpoints._revoke_all_refresh_capability_in_transaction",
        _boom,
    )

    response = await async_client.put(
        f"/api/v2/auth/users/{user_id}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "refresh revoke failed"

    updated_user = await _get_user_fresh(user_id)
    assert updated_user is not None
    assert updated_user.is_active is True

    refresh_resp = await async_client.post(
        "/api/v2/auth/refresh",
        headers={
            "x-csrf-token": csrf_cookie,
            "cookie": f"refresh_token={refresh_cookie}; csrf_token={csrf_cookie}",
        },
    )
    assert refresh_resp.status_code == 200


@pytest.mark.asyncio
async def test_failed_login_commits_attempts_and_lockout_state_on_401(
    async_client, db_session
):
    """Wrong-password logins should persist failed-attempt counters before the 401."""
    user = User(
        username="failed-login-boundary",
        email="failed-login-boundary@example.com",
        hashed_password=get_password_hash("CorrectPass!2026"),
        role="viewer",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user_id = user.id

    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        response = await async_client.post(
            "/api/v2/auth/login",
            json={"username": user.username, "password": "WrongPass!2026"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username or password"

    updated_user = await _get_user_fresh(user_id)
    assert updated_user is not None
    assert updated_user.failed_login_attempts == settings.MAX_LOGIN_ATTEMPTS
    assert updated_user.locked_until is not None
