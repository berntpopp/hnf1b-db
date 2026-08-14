"""SQLAlchemy ORM models for the D.2 comments feature.

Spec reference: docs/superpowers/specs/
2026-04-14-wave-7-d2-comments-and-clone-advancement-design.md §5.1.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import conv
from sqlalchemy.sql import func

from app.database import Base
from app.models.user import User

if TYPE_CHECKING:
    from app.phenopackets.models import PhenopacketRevision


class Comment(Base):
    """Curation-layer comment on a phenopacket (or future record types)."""

    __tablename__ = "comments"
    __table_args__ = (
        Index(
            "ix_comments_live_unresolved_phenopacket_review_issues",
            "record_id",
            "review_revision_id",
            postgresql_where=text(
                "record_type = 'phenopacket' AND "
                "review_revision_id IS NOT NULL AND "
                "resolved_at IS NULL AND deleted_at IS NULL"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    record_type: Mapped[str] = mapped_column(Text, nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    author_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    resolved_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    deleted_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    review_revision_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey(
            "phenopacket_revisions.id",
            name=conv("fk_comments_review_revision"),
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    author: Mapped[User] = relationship("User", foreign_keys=[author_id], viewonly=True)
    resolved_by: Mapped[Optional[User]] = relationship(
        "User", foreign_keys=[resolved_by_id], viewonly=True
    )
    deleted_by: Mapped[Optional[User]] = relationship(
        "User", foreign_keys=[deleted_by_id], viewonly=True
    )
    review_revision: Mapped[Optional["PhenopacketRevision"]] = relationship(
        "PhenopacketRevision", foreign_keys=[review_revision_id], viewonly=True
    )
    resolution_events: Mapped[list["CommentResolutionEvent"]] = relationship(
        "CommentResolutionEvent", back_populates="comment", viewonly=True
    )


class CommentResolutionEvent(Base):
    """Append-only audit event for resolving or reopening a review issue."""

    __tablename__ = "comment_resolution_events"
    __table_args__ = (
        CheckConstraint(
            "(action = 'reopened' AND disposition IS NULL) OR "
            "(action = 'resolved' AND disposition IN "
            "('addressed','accepted_with_rationale','retracted','superseded'))",
            name=conv("ck_comment_resolution_event_action_disposition"),
        ),
        CheckConstraint(
            "char_length(btrim(rationale)) BETWEEN 1 AND 500",
            name=conv("ck_comment_resolution_event_rationale"),
        ),
        CheckConstraint(
            "actor_role IN ('curator', 'admin')",
            name=conv("ck_comment_resolution_event_actor_role"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    comment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("comments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    disposition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_role: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    comment: Mapped[Comment] = relationship(
        "Comment", back_populates="resolution_events", viewonly=True
    )
    actor: Mapped[User] = relationship("User", foreign_keys=[actor_id], viewonly=True)


class CommentEdit(Base):
    """Append-only log of comment body edits (C1)."""

    __tablename__ = "comment_edits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    comment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("comments.id", ondelete="CASCADE"), nullable=False
    )
    editor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    prev_body: Mapped[str] = mapped_column(Text, nullable=False)
    edited_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    editor: Mapped[User] = relationship("User", foreign_keys=[editor_id], viewonly=True)


class CommentMention(Base):
    """Join table of comment → mentioned user."""

    __tablename__ = "comment_mentions"

    comment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("comments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user: Mapped[User] = relationship("User", foreign_keys=[user_id], viewonly=True)
