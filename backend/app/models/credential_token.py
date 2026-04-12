"""Credential token model for identity lifecycle flows.

Stores SHA-256 hashed single-use tokens for invite, password reset,
and email verification. Raw tokens are never persisted.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CredentialToken(Base):
    """Single-use credential token for invite, reset, and verify flows."""

    __tablename__ = "credential_tokens"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('reset', 'invite', 'verify')",
            name="purpose",
        ),
        Index("ix_credential_tokens_email_purpose", "email", "purpose"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    purpose: Mapped[str] = mapped_column(String(10), nullable=False)
    token_sha256: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
