"""Wave 5b Task 11: pwdlib verify-and-rehash for legacy bcrypt users."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Pre-computed with passlib CryptContext(schemes=["bcrypt"]).hash("LegacyPass!2026")
LEGACY_BCRYPT_HASH = "$2b$12$HAjY/fojLu5IZlgsTKepQOVKf3nK8rIxBaE9sxYgb3o104/XEaoCO"


@pytest.mark.asyncio
async def test_legacy_bcrypt_login_succeeds(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A user seeded with a legacy $2b$ hash can still log in."""
    await db_session.execute(
        text("""
            INSERT INTO users (
                email, username, hashed_password, role,
                is_active, is_verified, is_fixture_user,
                failed_login_attempts, created_at
            )
            VALUES (
                'legacy@hnf1b-db.local', 'wave5b-legacy-user',
                :hash, 'viewer', true, true, false, 0, NOW()
            )
            ON CONFLICT (username) DO UPDATE SET hashed_password = :hash
        """),
        {"hash": LEGACY_BCRYPT_HASH},
    )
    await db_session.commit()

    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": "wave5b-legacy-user", "password": "LegacyPass!2026"},
    )
    assert response.status_code == 200, response.text
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_legacy_bcrypt_rehashes_to_argon2id_on_login(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """After login, the stored hash should be Argon2id, not bcrypt."""
    await db_session.execute(
        text("""
            INSERT INTO users (
                email, username, hashed_password, role,
                is_active, is_verified, is_fixture_user,
                failed_login_attempts, created_at
            )
            VALUES (
                'rehash@hnf1b-db.local', 'wave5b-rehash-user',
                :hash, 'viewer', true, true, false, 0, NOW()
            )
            ON CONFLICT (username) DO UPDATE SET hashed_password = :hash
        """),
        {"hash": LEGACY_BCRYPT_HASH},
    )
    await db_session.commit()

    # Login triggers verify-and-rehash
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": "wave5b-rehash-user", "password": "LegacyPass!2026"},
    )
    assert response.status_code == 200

    # Verify the stored hash is now Argon2id
    row = (
        await db_session.execute(
            text(
                "SELECT hashed_password FROM users"
                " WHERE username = 'wave5b-rehash-user'"
            )
        )
    ).fetchone()
    assert row is not None
    assert row.hashed_password.startswith("$argon2id$"), (
        f"Hash did not upgrade on login. Still: {row.hashed_password[:20]}..."
    )


@pytest.mark.asyncio
async def test_new_user_hash_is_argon2id(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
) -> None:
    """A freshly-created user has an Argon2id hash from the start."""
    response = await async_client.post(
        "/api/v2/auth/users",
        json={
            "username": "wave5b-new-argon",
            "email": "new-argon@hnf1b-db.example.com",
            "password": "FreshPass!2026",
            "full_name": "Fresh User",
            "role": "viewer",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text

    # Verify the stored hash is Argon2id
    row = (
        await db_session.execute(
            text(
                "SELECT hashed_password FROM users WHERE username = 'wave5b-new-argon'"
            )
        )
    ).fetchone()
    assert row is not None
    assert row.hashed_password.startswith("$argon2id$")
