"""Tests for refresh-session persistence primitives."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from app.repositories.refresh_session_repository import RefreshSessionRepository


@pytest_asyncio.fixture
async def refresh_session_repo(db_session):
    """Create a RefreshSessionRepository with the test session."""
    return RefreshSessionRepository(db_session)


def _future_time(*, hours: int = 1) -> datetime:
    """Return a timezone-aware timestamp in the future."""
    return datetime.now(timezone.utc) + timedelta(hours=hours)


@pytest.mark.asyncio
async def test_create_and_get_by_jti(refresh_session_repo, test_user):
    """Repository creates a refresh session and can read it back by JTI."""
    created = await refresh_session_repo.create_session(
        user_id=test_user.id,
        token_jti="jti-1",
        token_sha256="sha-1",
        session_version=test_user.session_version,
        expires_at=_future_time(),
    )

    fetched = await refresh_session_repo.get_by_jti("jti-1")

    assert created.id == fetched.id
    assert fetched.user_id == test_user.id
    assert fetched.token_sha256 == "sha-1"
    assert fetched.revoked_at is None


@pytest.mark.asyncio
async def test_revoke_session_marks_session_revoked(refresh_session_repo, test_user):
    """Repository can revoke a single refresh session."""
    session = await refresh_session_repo.create_session(
        user_id=test_user.id,
        token_jti="jti-2",
        token_sha256="sha-2",
        session_version=test_user.session_version,
        expires_at=_future_time(),
    )

    revoked = await refresh_session_repo.revoke_session(session)
    fetched = await refresh_session_repo.get_by_jti("jti-2")

    assert revoked.revoked_at is not None
    assert fetched.revoked_at is not None


@pytest.mark.asyncio
async def test_revoke_family_revokes_rotation_chain(refresh_session_repo, test_user):
    """Revoking a root session revokes the whole rotation family."""
    root = await refresh_session_repo.create_session(
        user_id=test_user.id,
        token_jti="jti-root",
        token_sha256="sha-root",
        session_version=test_user.session_version,
        expires_at=_future_time(),
    )
    child = await refresh_session_repo.create_session(
        user_id=test_user.id,
        token_jti="jti-child",
        token_sha256="sha-child",
        session_version=test_user.session_version,
        expires_at=_future_time(),
        rotated_from_jti=root.token_jti,
    )
    grandchild = await refresh_session_repo.create_session(
        user_id=test_user.id,
        token_jti="jti-grandchild",
        token_sha256="sha-grandchild",
        session_version=test_user.session_version,
        expires_at=_future_time(),
        rotated_from_jti=child.token_jti,
    )

    revoked_count = await refresh_session_repo.revoke_family(root.token_jti)

    refreshed_root = await refresh_session_repo.get_by_jti(root.token_jti)
    refreshed_child = await refresh_session_repo.get_by_jti(child.token_jti)
    refreshed_grandchild = await refresh_session_repo.get_by_jti(grandchild.token_jti)

    assert revoked_count == 3
    assert refreshed_root.revoked_at is not None
    assert refreshed_child.revoked_at is not None
    assert refreshed_grandchild.revoked_at is not None


@pytest.mark.asyncio
async def test_get_valid_session_rejects_old_session_version(
    refresh_session_repo, test_user
):
    """Valid lookup rejects a session once the user's session version changes."""
    await refresh_session_repo.create_session(
        user_id=test_user.id,
        token_jti="jti-stale",
        token_sha256="sha-stale",
        session_version=test_user.session_version,
        expires_at=_future_time(),
    )

    valid_before_bump = await refresh_session_repo.get_valid_session(
        token_jti="jti-stale",
        user_id=test_user.id,
        current_session_version=test_user.session_version,
    )
    await refresh_session_repo.bump_user_session_version(test_user)
    valid_after_bump = await refresh_session_repo.get_valid_session(
        token_jti="jti-stale",
        user_id=test_user.id,
        current_session_version=test_user.session_version,
    )

    assert valid_before_bump is not None
    assert valid_after_bump is None


@pytest.mark.asyncio
async def test_revoke_all_for_user_bumps_version_and_revokes_rows(
    refresh_session_repo, test_user
):
    """Revoke-all invalidates every active session and increments the user version."""
    session_one = await refresh_session_repo.create_session(
        user_id=test_user.id,
        token_jti="jti-a",
        token_sha256="sha-a",
        session_version=test_user.session_version,
        expires_at=_future_time(),
    )
    session_two = await refresh_session_repo.create_session(
        user_id=test_user.id,
        token_jti="jti-b",
        token_sha256="sha-b",
        session_version=test_user.session_version,
        expires_at=_future_time(),
    )

    old_version = test_user.session_version
    revoked_count = await refresh_session_repo.revoke_all_for_user(test_user)
    refreshed_one = await refresh_session_repo.get_by_jti(session_one.token_jti)
    refreshed_two = await refresh_session_repo.get_by_jti(session_two.token_jti)

    assert revoked_count == 2
    assert test_user.session_version == old_version + 1
    assert refreshed_one.revoked_at is not None
    assert refreshed_two.revoked_at is not None
    assert refreshed_one.session_version == old_version
    assert refreshed_two.session_version == old_version
