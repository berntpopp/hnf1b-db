"""Repository helpers for refresh-session persistence."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_session import RefreshSession
from app.models.user import User


class RefreshSessionRepository:
    """Repository for refresh-session persistence and invalidation primitives."""

    def __init__(self, db: AsyncSession):
        """Initialize the repository with an async database session."""
        self.db = db

    async def create_session(
        self,
        *,
        user_id: int,
        token_jti: str,
        token_sha256: str,
        session_version: int,
        expires_at: datetime,
        rotated_from_jti: str | None = None,
    ) -> RefreshSession:
        """Persist a new refresh session."""
        session = RefreshSession(
            user_id=user_id,
            token_jti=token_jti,
            token_sha256=token_sha256,
            session_version=session_version,
            expires_at=expires_at,
            rotated_from_jti=rotated_from_jti,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get_by_jti(self, token_jti: str) -> RefreshSession | None:
        """Fetch a refresh session by JWT ID."""
        result = await self.db.execute(
            select(RefreshSession).where(RefreshSession.token_jti == token_jti)
        )
        return result.scalar_one_or_none()

    async def get_valid_session(
        self, *, token_jti: str, user_id: int, current_session_version: int
    ) -> RefreshSession | None:
        """Fetch an active refresh session matching the user's current version."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(RefreshSession).where(
                RefreshSession.token_jti == token_jti,
                RefreshSession.user_id == user_id,
                RefreshSession.session_version == current_session_version,
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def revoke_session(self, session: RefreshSession) -> RefreshSession:
        """Mark one refresh session as revoked."""
        if session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(session)
        return session

    async def revoke_family(self, token_jti: str) -> int:
        """Revoke a refresh-session rotation chain starting from one JTI."""
        root = await self.get_by_jti(token_jti)
        if root is None:
            return 0

        pending = [root.token_jti]
        seen_jtis: set[str] = set()
        sessions_by_jti: dict[str, RefreshSession] = {}

        while pending:
            current_jti = pending.pop()
            if current_jti in seen_jtis:
                continue
            seen_jtis.add(current_jti)
            result = await self.db.execute(
                select(RefreshSession).where(
                    (RefreshSession.token_jti == current_jti)
                    | (RefreshSession.rotated_from_jti == current_jti)
                )
            )
            for session in result.scalars().all():
                sessions_by_jti.setdefault(session.token_jti, session)
                if session.token_jti != current_jti:
                    pending.append(session.token_jti)

        revoked_at = datetime.now(timezone.utc)
        changed = 0
        for session in sessions_by_jti.values():
            if session.revoked_at is None:
                session.revoked_at = revoked_at
                changed += 1

        await self.db.commit()
        return changed

    async def bump_user_session_version(self, user: User) -> int:
        """Increment and persist the user's refresh session version."""
        user.session_version += 1
        await self.db.commit()
        await self.db.refresh(user)
        return user.session_version

    async def revoke_all_for_user(self, user: User) -> int:
        """Revoke all active refresh sessions for a user and bump the version."""
        current_version = user.session_version
        result = await self.db.execute(
            select(RefreshSession).where(
                RefreshSession.user_id == user.id,
                RefreshSession.session_version == current_version,
                RefreshSession.revoked_at.is_(None),
            )
        )
        sessions = list(result.scalars().all())
        revoked_at = datetime.now(timezone.utc)
        for session in sessions:
            session.revoked_at = revoked_at

        user.session_version += 1
        await self.db.commit()
        await self.db.refresh(user)
        return len(sessions)
