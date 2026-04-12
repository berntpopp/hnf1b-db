"""Tests for credential token repository."""

from datetime import timedelta

import pytest
import pytest_asyncio

from app.auth.credential_tokens import CredentialTokenService


@pytest_asyncio.fixture
async def token_service(db_session):
    """Create a CredentialTokenService with test session."""
    return CredentialTokenService(db_session)


@pytest.mark.asyncio
async def test_create_token_returns_raw_token(token_service):
    """create_token returns the raw URL-safe token (not the hash)."""
    raw_token, db_token = await token_service.create_token(
        purpose="invite",
        email="test@example.com",
        metadata={"role": "curator"},
    )
    assert len(raw_token) > 30  # secrets.token_urlsafe(32) is ~43 chars
    assert db_token.token_sha256 != raw_token  # stored hash != raw
    assert db_token.purpose == "invite"
    assert db_token.email == "test@example.com"
    assert db_token.metadata_ == {"role": "curator"}
    assert db_token.used_at is None


@pytest.mark.asyncio
async def test_create_token_with_user_id(token_service, db_session):
    """create_token can bind to an existing user."""
    from app.auth.password import get_password_hash
    from app.models.user import User

    user = User(
        username="verifyuser",
        email="verify@example.com",
        hashed_password=get_password_hash("TestPass!2026"),
        role="viewer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    raw_token, db_token = await token_service.create_token(
        purpose="verify",
        email="verify@example.com",
        user_id=user.id,
    )
    assert db_token.user_id == user.id


@pytest.mark.asyncio
async def test_verify_and_consume_valid_token(token_service):
    """verify_and_consume succeeds for valid, unused, unexpired token."""
    raw_token, _ = await token_service.create_token(
        purpose="reset",
        email="reset@example.com",
    )
    consumed = await token_service.verify_and_consume(raw_token, purpose="reset")
    assert consumed is not None
    assert consumed.email == "reset@example.com"
    assert consumed.used_at is not None


@pytest.mark.asyncio
async def test_verify_and_consume_rejects_wrong_purpose(token_service):
    """verify_and_consume returns None if purpose doesn't match."""
    raw_token, _ = await token_service.create_token(
        purpose="invite",
        email="test@example.com",
    )
    result = await token_service.verify_and_consume(raw_token, purpose="reset")
    assert result is None


@pytest.mark.asyncio
async def test_verify_and_consume_rejects_already_used(token_service):
    """verify_and_consume returns None for already-consumed tokens."""
    raw_token, _ = await token_service.create_token(
        purpose="reset",
        email="test@example.com",
    )
    await token_service.verify_and_consume(raw_token, purpose="reset")
    result = await token_service.verify_and_consume(raw_token, purpose="reset")
    assert result is None


@pytest.mark.asyncio
async def test_verify_and_consume_rejects_expired(token_service):
    """verify_and_consume returns None for expired tokens."""
    raw_token, _ = await token_service.create_token(
        purpose="reset",
        email="test@example.com",
        expires_in=timedelta(seconds=-1),
    )
    result = await token_service.verify_and_consume(raw_token, purpose="reset")
    assert result is None


@pytest.mark.asyncio
async def test_invalidate_by_email_and_purpose(token_service):
    """invalidate_by_email_and_purpose marks existing tokens as used."""
    raw1, _ = await token_service.create_token(
        purpose="reset", email="test@example.com"
    )
    raw2, _ = await token_service.create_token(
        purpose="reset", email="test@example.com"
    )

    count = await token_service.invalidate_by_email_and_purpose(
        email="test@example.com", purpose="reset"
    )
    assert count == 2

    assert await token_service.verify_and_consume(raw1, purpose="reset") is None
    assert await token_service.verify_and_consume(raw2, purpose="reset") is None
