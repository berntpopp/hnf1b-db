"""C5 — DB CHECK constraints reject inconsistent resolved/deleted pairs.

The comments table has two PostgreSQL CHECK constraints:
  chk_resolved_consistency: (resolved_at IS NULL) = (resolved_by_id IS NULL)
  chk_deleted_consistency:  (deleted_at  IS NULL) = (deleted_by_id  IS NULL)

Setting one column without its paired column must raise IntegrityError.

Spec reference:
  docs/superpowers/specs/
  2026-04-14-wave-7-d2-comments-and-clone-advancement-design.md §5.2 C5.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


@pytest.mark.asyncio
async def test_cannot_set_resolved_at_without_resolver(
    db_session, published_record, curator_user
):
    """resolved_at set + resolved_by_id NULL → chk_resolved_consistency violation."""
    from app.comments.service import CommentsService

    svc = CommentsService(db_session)
    c = await svc.create(
        record_type="phenopacket",
        record_id=published_record.id,
        body_markdown="x",
        mention_user_ids=[],
        actor=curator_user,
    )

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("UPDATE comments SET resolved_at = now() WHERE id = :id"),
            {"id": c.id},
        )
        await db_session.commit()

    # Roll back the failed transaction so the session is usable for teardown
    await db_session.rollback()
