"""Credential token service for identity lifecycle flows.

Handles creation, verification, consumption, and invalidation of
single-use tokens for invite, password reset, and email verification.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credential_token import CredentialToken

DEFAULT_EXPIRY = timedelta(hours=24)


def _hash_token(raw_token: str) -> str:
    """Compute SHA-256 hex hash of a raw token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class CredentialTokenService:
    """Service for credential token CRUD operations."""

    def __init__(self, db: AsyncSession):
        """Initialize with an async database session."""
        self.db = db

    async def create_token(
        self,
        *,
        purpose: str,
        email: str,
        user_id: int | None = None,
        metadata: dict | None = None,
        expires_in: timedelta = DEFAULT_EXPIRY,
    ) -> tuple[str, CredentialToken]:
        """Create a new credential token.

        Returns:
            Tuple of (raw_token, db_token). Raw token is sent to user;
            db_token has the SHA-256 hash.
        """
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        now = datetime.now(timezone.utc)

        db_token = CredentialToken(
            user_id=user_id,
            purpose=purpose,
            token_sha256=token_hash,
            email=email,
            expires_at=now + expires_in,
            metadata_=metadata,
        )
        self.db.add(db_token)
        await self.db.commit()
        await self.db.refresh(db_token)

        return raw_token, db_token

    async def verify_and_consume(
        self, raw_token: str, *, purpose: str
    ) -> CredentialToken | None:
        """Verify a token and mark it as consumed.

        Returns the consumed token row, or None if invalid/expired/used.
        Uses hmac.compare_digest for defense in depth (spec R1).
        """
        token_hash = _hash_token(raw_token)
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(CredentialToken).where(
                CredentialToken.token_sha256 == token_hash,
                CredentialToken.purpose == purpose,
            )
        )
        db_token = result.scalar_one_or_none()

        if db_token is None:
            return None

        if not hmac.compare_digest(db_token.token_sha256, token_hash):
            return None

        if db_token.used_at is not None:
            return None

        if db_token.expires_at <= now:
            return None

        db_token.used_at = now
        await self.db.commit()
        await self.db.refresh(db_token)

        return db_token

    async def invalidate_by_email_and_purpose(self, *, email: str, purpose: str) -> int:
        """Mark all unused tokens for an email+purpose as consumed.

        Returns number of tokens invalidated.
        """
        now = datetime.now(timezone.utc)
        result: CursorResult = await self.db.execute(  # type: ignore[assignment]
            update(CredentialToken)
            .where(
                CredentialToken.email == email,
                CredentialToken.purpose == purpose,
                CredentialToken.used_at.is_(None),
            )
            .values(used_at=now)
        )
        await self.db.commit()
        return result.rowcount
