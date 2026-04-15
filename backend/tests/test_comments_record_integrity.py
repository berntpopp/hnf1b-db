"""C3 — comments can be attached to soft-deleted records.

The service's _check_record_exists uses a count() query without filtering
on deleted_at, so soft-deleted phenopackets are still valid comment targets.
Hard-deleted (row-gone) records must still raise RecordNotFound.

Spec reference:
  docs/superpowers/specs/
  2026-04-14-wave-7-d2-comments-and-clone-advancement-design.md §5.2 C3.
"""

import pytest
from sqlalchemy.sql import func


@pytest.mark.asyncio
async def test_create_against_soft_deleted_phenopacket_succeeds(
    db_session, published_record, curator_user
):
    """C3: a soft-deleted record can still have comments added."""
    from app.comments.service import CommentsService

    # Soft-delete the record directly (simulate a lifecycle deletion)
    published_record.deleted_at = func.now()
    await db_session.commit()
    await db_session.refresh(published_record)

    # Creating a comment must succeed — the phenopacket row still exists
    svc = CommentsService(db_session)
    c = await svc.create(
        record_type="phenopacket",
        record_id=published_record.id,
        body_markdown="rip",
        mention_user_ids=[],
        actor=curator_user,
    )
    assert c.id is not None, "C3: comment creation on soft-deleted record must succeed"
    assert c.body_markdown == "rip"
