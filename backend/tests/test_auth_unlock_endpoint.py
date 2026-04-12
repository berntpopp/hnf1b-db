"""Wave 5b Task 6: PATCH /api/v2/auth/users/{id}/unlock clears lockout state."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_unlock_clears_failed_attempts_and_locked_until(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
):
    """Seed a locked user, hit the unlock endpoint, verify fields reset."""
    # Seed a locked curator
    await db_session.execute(
        text("""
            INSERT INTO users (
                email, username, hashed_password, role,
                is_active, is_verified, is_fixture_user,
                failed_login_attempts, locked_until, created_at
            )
            VALUES (
                'locked-curator@hnf1b-db.local',
                'wave5b-locked-curator',
                '$2b$12$placeholder.not.used.not.used.not.used.not.used.xx',
                'curator',
                true,
                true,
                false,
                5,
                :locked_until,
                NOW()
            )
            ON CONFLICT (username) DO UPDATE SET
                failed_login_attempts = 5,
                locked_until = :locked_until
            RETURNING id
        """),
        {"locked_until": datetime.now(timezone.utc) + timedelta(minutes=15)},
    )
    await db_session.commit()

    # Look up the user id
    result = await db_session.execute(
        text("SELECT id FROM users WHERE username = 'wave5b-locked-curator'")
    )
    user_id = result.scalar_one()

    # Hit the unlock endpoint
    response = await async_client.patch(
        f"/api/v2/auth/users/{user_id}/unlock",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text

    # Verify the row was reset
    row = (
        await db_session.execute(
            text("""
            SELECT failed_login_attempts, locked_until
            FROM users
            WHERE username = 'wave5b-locked-curator'
        """)
        )
    ).fetchone()
    assert row is not None
    assert row.failed_login_attempts == 0
    assert row.locked_until is None


@pytest.mark.asyncio
async def test_unlock_non_admin_forbidden(
    async_client: AsyncClient,
    curator_headers: dict,
):
    """A curator cannot unlock other users — 403."""
    response = await async_client.patch(
        "/api/v2/auth/users/1/unlock",
        headers=curator_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unlock_missing_user_404(
    async_client: AsyncClient,
    admin_headers: dict,
):
    """Unlocking a nonexistent user returns 404."""
    response = await async_client.patch(
        "/api/v2/auth/users/999999/unlock",
        headers=admin_headers,
    )
    assert response.status_code == 404
