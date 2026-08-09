"""Database guards for immutable revision content and record-owned pointers."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.phenopackets.models import Phenopacket, PhenopacketRevision


@pytest.mark.asyncio
async def test_database_rejects_mutation_of_inserted_revision(
    db_session, published_record
):
    """The append-only trigger rejects direct content rewrites as a backstop."""
    revision = (
        await db_session.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.id == published_record.head_published_revision_id
            )
        )
    ).scalar_one()
    revision.content_jsonb = {"id": "rewritten"}

    with pytest.raises(DBAPIError, match="append-only"):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_database_rejects_head_pointer_for_another_record(
    db_session, published_record, admin_user
):
    """A head pointer must reference a revision belonging to the same record."""
    other = Phenopacket(
        phenopacket_id="different-record",
        phenopacket={"id": "different-record"},
        state="published",
        revision=1,
        created_by_id=admin_user.id,
    )
    db_session.add(other)
    await db_session.flush()
    other_revision = PhenopacketRevision(
        record_id=other.id,
        revision_number=1,
        state="published",
        content_jsonb={"id": "different-record"},
        change_reason="fixture",
        actor_id=admin_user.id,
        from_state=None,
        to_state="published",
    )
    db_session.add(other_revision)
    await db_session.flush()

    published_record.head_published_revision_id = other_revision.id
    with pytest.raises(DBAPIError, match="must belong to its record"):
        await db_session.commit()
    await db_session.rollback()
