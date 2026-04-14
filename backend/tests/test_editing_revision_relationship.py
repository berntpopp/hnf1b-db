"""Verify the Phenopacket.editing_revision relationship resolves correctly.

Wave 7 D.2 Task 1: sanity tests for the new ORM relationship.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.phenopackets.models import Phenopacket, PhenopacketRevision


@pytest.mark.asyncio
async def test_editing_revision_lazy_none_when_id_null(db_session, admin_user):
    """With editing_revision_id NULL, editing_revision is None (no query needed)."""
    pp = Phenopacket(
        phenopacket_id="d2-task1-null-rev",
        phenopacket={"id": "d2-task1-null-rev"},
        state="published",
        revision=1,
        created_by_id=admin_user.id,
        # editing_revision_id stays NULL
    )
    db_session.add(pp)
    await db_session.commit()
    await db_session.refresh(pp)

    stmt = (
        select(Phenopacket)
        .where(Phenopacket.id == pp.id)
        .options(selectinload(Phenopacket.editing_revision))
    )
    result = (await db_session.execute(stmt)).scalar_one()
    assert result.editing_revision_id is None
    assert result.editing_revision is None


@pytest.mark.asyncio
async def test_editing_revision_resolves_when_set(db_session, admin_user):
    """With editing_revision_id set, eager load populates the relationship."""
    pp = Phenopacket(
        phenopacket_id="d2-task1-with-rev",
        phenopacket={"id": "d2-task1-with-rev"},
        state="published",
        revision=1,
        created_by_id=admin_user.id,
    )
    db_session.add(pp)
    await db_session.flush()

    rev = PhenopacketRevision(
        record_id=pp.id,
        revision_number=2,
        state="draft",
        content_jsonb={"id": "d2-task1-with-rev"},
        change_reason="clone-to-draft",
        actor_id=admin_user.id,
        from_state="published",
        to_state="draft",
        is_head_published=False,
    )
    db_session.add(rev)
    await db_session.flush()

    pp.editing_revision_id = rev.id
    await db_session.commit()

    stmt = (
        select(Phenopacket)
        .where(Phenopacket.id == pp.id)
        .options(selectinload(Phenopacket.editing_revision))
    )
    result = (await db_session.execute(stmt)).scalar_one()
    assert result.editing_revision is not None
    assert result.editing_revision.id == rev.id
    assert result.editing_revision.state == "draft"
