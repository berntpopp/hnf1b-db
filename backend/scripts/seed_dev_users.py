"""Seed dev-mode fixture users for Wave 5a quick-login.

Wave 5a Layer 3 of the dev-mode 5-layer defense (review §5.3).

Idempotent: upserts five fixture users with is_fixture_user=True.
Refuses to run outside ENVIRONMENT=development.

Usage:
    make dev-seed-users
    # or
    ENVIRONMENT=development uv run python backend/scripts/seed_dev_users.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import TypedDict

# Ensure the backend app package is importable when running this file directly
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.auth.password import get_password_hash  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.database import async_session_maker  # noqa: E402
from app.models.user import User  # noqa: E402


class FixtureUserSpec(TypedDict):
    """Required fields for one development-only fixture principal."""

    email: str
    username: str
    full_name: str
    role: str
    password: str
    is_active: bool
    is_verified: bool
    is_fixture_user: bool


FIXTURE_USERS: list[FixtureUserSpec] = [
    {
        "email": "dev-admin@hnf1b-db.local",
        "username": "dev-admin",
        "full_name": "Dev Admin",
        "role": "admin",
        "password": "DevAdmin!2026",
        "is_active": True,
        "is_verified": True,
        "is_fixture_user": True,
    },
    {
        "email": "dev-curator@hnf1b-db.local",
        "username": "dev-curator",
        "full_name": "Dev Curator",
        "role": "curator",
        "password": "DevCurator!2026",
        "is_active": True,
        "is_verified": True,
        "is_fixture_user": True,
    },
    {
        "email": "dev-curator-a@hnf1b-db.local",
        "username": "dev-curator-a",
        "full_name": "Dev Curator A",
        "role": "curator",
        "password": "DevCuratorA!2026",
        "is_active": True,
        "is_verified": True,
        "is_fixture_user": True,
    },
    {
        "email": "dev-curator-b@hnf1b-db.local",
        "username": "dev-curator-b",
        "full_name": "Dev Curator B",
        "role": "curator",
        "password": "DevCuratorB!2026",
        "is_active": True,
        "is_verified": True,
        "is_fixture_user": True,
    },
    {
        "email": "dev-viewer@hnf1b-db.local",
        "username": "dev-viewer",
        "full_name": "Dev Viewer",
        "role": "viewer",
        "password": "DevViewer!2026",
        "is_active": True,
        "is_verified": True,
        "is_fixture_user": True,
    },
]


async def _seed() -> None:
    async with async_session_maker() as session:
        for spec in FIXTURE_USERS:
            result = await session.execute(
                select(User).where(User.username == spec["username"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                user = User(
                    email=spec["email"],
                    username=spec["username"],
                    hashed_password=get_password_hash(spec["password"]),
                    full_name=spec["full_name"],
                    role=spec["role"],
                    is_active=spec["is_active"],
                    is_verified=spec["is_verified"],
                    is_fixture_user=spec["is_fixture_user"],
                )
                session.add(user)
                print(f"seeded {spec['username']} ({spec['role']})")
            else:
                existing.is_active = spec["is_active"]
                existing.is_verified = spec["is_verified"]
                existing.is_fixture_user = spec["is_fixture_user"]
                existing.role = spec["role"]
                existing.hashed_password = get_password_hash(spec["password"])
                print(f"refreshed {spec['username']}")
        await session.commit()


def main() -> int:
    """Entry point: refuse unless dev mode, otherwise seed fixture users."""
    if settings.environment != "development":
        print(
            "seed_dev_users refuses to run outside development "
            f"(ENVIRONMENT={settings.environment!r})",
            file=sys.stderr,
        )
        return 1
    asyncio.run(_seed())
    print(
        "Seeded 5 fixture users — dev-admin, dev-curator, "
        "dev-curator-a, dev-curator-b, dev-viewer"
    )
    print(
        "Passwords: DevAdmin!2026 / DevCurator!2026 / "
        "DevCuratorA!2026 / DevCuratorB!2026 / DevViewer!2026"
    )
    print("Use via /api/v2/dev/login-as/<username> (dev mode only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
