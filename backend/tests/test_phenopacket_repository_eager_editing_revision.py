"""PhenopacketRepository eager-loads editing_revision."""
import pytest

from app.phenopackets.repositories.phenopacket_repository import PhenopacketRepository


@pytest.mark.asyncio
async def test_get_by_id_returns_editing_revision_when_set(
    db_session, published_record, admin_user
):
    """get_by_id eager-loads editing_revision; no lazy-load IO required."""
    from app.phenopackets.models import PhenopacketRevision

    pp = published_record
    rev = PhenopacketRevision(
        record_id=pp.id,
        revision_number=99,
        state="draft",
        content_jsonb={"id": pp.phenopacket_id, "a": 2},
        change_reason="editing",
        actor_id=admin_user.id,
        from_state="published",
        to_state="draft",
        is_head_published=False,
    )
    db_session.add(rev)
    await db_session.flush()
    pp.editing_revision_id = rev.id
    await db_session.commit()

    # Capture id before expire_all() so attribute access doesn't trigger a
    # synchronous lazy-load on the expired instance.
    phenopacket_id = pp.phenopacket_id
    # Expire to force a fresh load
    db_session.expire_all()

    repo = PhenopacketRepository(db_session)
    loaded = await repo.get_by_id(phenopacket_id)
    assert loaded is not None
    # Access without awaiting a query (already eager-loaded)
    assert loaded.editing_revision is not None
    assert loaded.editing_revision.state == "draft"


@pytest.mark.asyncio
async def test_get_by_id_editing_revision_none_when_unset(
    db_session, published_record
):
    """get_by_id handles NULL editing_revision_id cleanly (no extra query)."""
    repo = PhenopacketRepository(db_session)
    loaded = await repo.get_by_id(published_record.phenopacket_id)
    assert loaded is not None
    assert loaded.editing_revision is None
