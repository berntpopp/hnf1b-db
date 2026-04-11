"""Seed dev-mode fixture users for Wave 5a quick-login.

Wave 5a Layer 3 of the dev-mode 5-layer defense (review §5.3).

Idempotent: upserts three fixture users with is_fixture_user=True.
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

# Ensure the backend app package is importable when running this file directly
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.auth.password import get_password_hash  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.database import async_session_maker  # noqa: E402
from app.models.user import User  # noqa: E402

FIXTURE_USERS = [
    {
        "email": "dev-admin@hnf1b-db.local",
        "username": "dev-admin",
        "full_name": "Dev Admin",
        "role": "admin",
        "password": "DevAdmin!2026",
    },
    {
        "email": "dev-curator@hnf1b-db.local",
        "username": "dev-curator",
        "full_name": "Dev Curator",
        "role": "curator",
        "password": "DevCurator!2026",
    },
    {
        "email": "dev-viewer@hnf1b-db.local",
        "username": "dev-viewer",
        "full_name": "Dev Viewer",
        "role": "viewer",
        "password": "DevViewer!2026",
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
                    is_active=True,
                    is_verified=True,
                    is_fixture_user=True,
                )
                session.add(user)
                print(f"seeded {spec['username']} ({spec['role']})")
            else:
                existing.is_active = True
                existing.is_verified = True
                existing.is_fixture_user = True
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
    print("Seeded 3 fixture users — dev-admin, dev-curator, dev-viewer")
    print("Passwords: DevAdmin!2026 / DevCurator!2026 / DevViewer!2026")
    print("Use via /api/v2/dev/login-as/<username> (dev mode only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
