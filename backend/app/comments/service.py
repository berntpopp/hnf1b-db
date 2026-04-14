"""CommentsService — all mutating paths for the D.2 comments feature."""
from __future__ import annotations

import uuid
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.comments.models import Comment, CommentEdit, CommentMention
from app.models.user import User
from app.phenopackets.models import Phenopacket


class CommentsService:
    """All comment operations. Single-transaction, commit at the end of each method."""

    class RecordNotFound(Exception):
        """(record_type, record_id) does not resolve to a real record (C3)."""

    class MentionUnknownUser(Exception):
        """One or more mention_user_ids is not a known active curator/admin."""

    class NotAuthor(Exception):
        """The actor is not the comment's author."""

    class NotAuthorOrAdmin(Exception):
        """The actor is neither the comment's author nor an admin."""

    class AlreadyResolved(Exception):
        """resolve called on an already-resolved comment."""

    class NotResolved(Exception):
        """unresolve called on a non-resolved comment."""

    class SoftDeleted(Exception):
        """Write attempted on a soft-deleted comment (C6)."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise with an async database session."""
        self.db = db

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _check_record_exists(
        self, record_type: str, record_id: uuid.UUID
    ) -> None:
        """C3 — verify target record is not hard-deleted (soft-deleted is OK).

        The global soft-delete ORM filter (app.database._register_soft_delete_filter)
        would exclude soft-deleted Phenopacket rows from the count query. We bypass
        it via ``include_deleted=True`` so that soft-deleted records are still valid
        comment targets (spec invariant C3).
        """
        if record_type != "phenopacket":
            raise self.RecordNotFound(f"Unsupported record_type {record_type!r}")
        stmt = select(func.count()).select_from(Phenopacket).where(
            Phenopacket.id == record_id
        )
        count = int(
            (
                await self.db.execute(
                    stmt,
                    execution_options={"include_deleted": True},
                )
            ).scalar()
            or 0
        )
        if count == 0:
            raise self.RecordNotFound(f"No phenopacket with id {record_id}")

    async def _validate_mentions(
        self, mention_user_ids: Sequence[int]
    ) -> List[int]:
        """Dedup + verify each id points to an active curator/admin."""
        if not mention_user_ids:
            return []
        deduped = list(dict.fromkeys(mention_user_ids))
        stmt = select(User.id).where(
            User.id.in_(deduped),
            User.is_active.is_(True),
            User.role.in_(("curator", "admin")),
        )
        valid = {row[0] for row in (await self.db.execute(stmt)).all()}
        missing = [uid for uid in deduped if uid not in valid]
        if missing:
            raise self.MentionUnknownUser(
                f"users not found or not mentionable: {missing}"
            )
        return deduped

    async def _load_for_response(self, comment_id: int) -> Comment:
        """Load a comment with the actor relationships eager for response building."""
        stmt = (
            select(Comment)
            .where(Comment.id == comment_id)
            .options(
                selectinload(Comment.author),
                selectinload(Comment.resolved_by),
                selectinload(Comment.deleted_by),
            )
        )
        return (await self.db.execute(stmt)).scalar_one()

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        *,
        record_type: str,
        record_id: uuid.UUID,
        body_markdown: str,
        mention_user_ids: Sequence[int],
        actor: User,
    ) -> Comment:
        """Insert a new comment and its mention rows atomically."""
        await self._check_record_exists(record_type, record_id)
        validated_mentions = await self._validate_mentions(mention_user_ids)

        comment = Comment(
            record_type=record_type,
            record_id=record_id,
            author_id=actor.id,
            body_markdown=body_markdown,
        )
        self.db.add(comment)
        await self.db.flush()  # obtain comment.id

        for uid in validated_mentions:
            self.db.add(CommentMention(comment_id=comment.id, user_id=uid))

        await self.db.commit()
        return await self._load_for_response(comment.id)

    # ------------------------------------------------------------------
    # List / detail
    # ------------------------------------------------------------------

    async def list_for_record(
        self,
        *,
        record_type: str,
        record_id: uuid.UUID,
        page_number: int,
        page_size: int,
        include_deleted: bool,
        resolved_filter: Optional[bool],
    ) -> Tuple[List[Comment], int]:
        """Return (rows, total_count) ordered by created_at ASC."""
        base = select(Comment).where(
            Comment.record_type == record_type,
            Comment.record_id == record_id,
        )
        if not include_deleted:
            base = base.where(Comment.deleted_at.is_(None))
        if resolved_filter is True:
            base = base.where(Comment.resolved_at.is_not(None))
        elif resolved_filter is False:
            base = base.where(Comment.resolved_at.is_(None))

        count = int(
            (await self.db.execute(
                select(func.count()).select_from(base.subquery())
            )).scalar() or 0
        )

        stmt = (
            base.options(
                selectinload(Comment.author),
                selectinload(Comment.resolved_by),
                selectinload(Comment.deleted_by),
            )
            .order_by(Comment.created_at.asc(), Comment.id.asc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return list(rows), count

    async def get_by_id(
        self, comment_id: int, *, include_deleted: bool = False
    ) -> Optional[Comment]:
        """Return a single comment by id, or None if not found / soft-deleted."""
        stmt = (
            select(Comment)
            .where(Comment.id == comment_id)
            .options(
                selectinload(Comment.author),
                selectinload(Comment.resolved_by),
                selectinload(Comment.deleted_by),
            )
        )
        if not include_deleted:
            stmt = stmt.where(Comment.deleted_at.is_(None))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_edits(self, comment_id: int) -> List[CommentEdit]:
        """Return all edit-log rows for a comment, newest first."""
        stmt = (
            select(CommentEdit)
            .where(CommentEdit.comment_id == comment_id)
            .options(selectinload(CommentEdit.editor))
            .order_by(CommentEdit.edited_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def load_mentions(self, comment_ids: Sequence[int]) -> dict[int, List[User]]:
        """Bulk-load mentions for a set of comments. Used by the router."""
        if not comment_ids:
            return {}
        stmt = (
            select(CommentMention)
            .where(CommentMention.comment_id.in_(list(comment_ids)))
            .options(selectinload(CommentMention.user))
        )
        out: dict[int, List[User]] = {cid: [] for cid in comment_ids}
        for mention in (await self.db.execute(stmt)).scalars().all():
            out[mention.comment_id].append(mention.user)
        return out

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    async def _fetch_live_or_404(self, comment_id: int) -> Comment:
        """Lock FOR UPDATE; raise SoftDeleted (→ 404) if already removed."""
        stmt = (
            select(Comment)
            .where(Comment.id == comment_id)
            .with_for_update()
        )
        comment = (await self.db.execute(stmt)).scalar_one_or_none()
        if comment is None:
            raise self.SoftDeleted(f"comment {comment_id} not found")
        if comment.deleted_at is not None:
            raise self.SoftDeleted(f"comment {comment_id} is soft-deleted")
        return comment

    async def update_body(
        self,
        *,
        comment_id: int,
        body_markdown: str,
        mention_user_ids: Sequence[int],
        actor: User,
    ) -> Comment:
        """PATCH body (author-only). Writes comment_edits + replaces mentions."""
        comment = await self._fetch_live_or_404(comment_id)
        if comment.author_id != actor.id:
            raise self.NotAuthor(
                f"actor {actor.id} is not comment author {comment.author_id}"
            )
        validated = await self._validate_mentions(mention_user_ids)

        # 1. Edit-log snapshot
        self.db.add(
            CommentEdit(
                comment_id=comment.id,
                editor_id=actor.id,
                prev_body=comment.body_markdown,
            )
        )
        # 2. Overwrite body + bump updated_at
        comment.body_markdown = body_markdown
        comment.updated_at = func.now()
        # 3. Replace mentions
        await self.db.execute(
            delete(CommentMention).where(
                CommentMention.comment_id == comment.id
            )
        )
        for uid in validated:
            self.db.add(CommentMention(comment_id=comment.id, user_id=uid))

        await self.db.commit()
        return await self._load_for_response(comment.id)

    async def resolve(self, *, comment_id: int, actor: User) -> Comment:
        """Mark a comment resolved; raises AlreadyResolved if already so."""
        comment = await self._fetch_live_or_404(comment_id)
        if comment.resolved_at is not None:
            raise self.AlreadyResolved(f"comment {comment_id} already resolved")
        comment.resolved_at = func.now()
        comment.resolved_by_id = actor.id
        comment.updated_at = func.now()
        await self.db.commit()
        return await self._load_for_response(comment_id)

    async def unresolve(self, *, comment_id: int, actor: User) -> Comment:
        """Clear the resolved flag; raises NotResolved if not currently resolved."""
        comment = await self._fetch_live_or_404(comment_id)
        if comment.resolved_at is None:
            raise self.NotResolved(f"comment {comment_id} is not resolved")
        comment.resolved_at = None
        comment.resolved_by_id = None
        comment.updated_at = func.now()
        await self.db.commit()
        return await self._load_for_response(comment_id)

    async def soft_delete(self, *, comment_id: int, actor: User) -> None:
        """Soft-delete a comment (author or admin only). Terminal write (C6)."""
        comment = await self._fetch_live_or_404(comment_id)
        is_admin = actor.role == "admin"
        if comment.author_id != actor.id and not is_admin:
            raise self.NotAuthorOrAdmin(
                f"actor {actor.id} is not author and not admin"
            )
        comment.deleted_at = func.now()
        comment.deleted_by_id = actor.id
        comment.updated_at = func.now()
        await self.db.commit()
