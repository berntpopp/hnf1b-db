"""build_phenopacket_response populates effective_state correctly."""

import pytest

from app.phenopackets.query_builders import build_phenopacket_response


@pytest.mark.asyncio
async def test_effective_state_mirrors_pp_state_when_no_editing(
    db_session, published_record
):
    """effective_state == pp.state when no in-flight edit exists (spec §4.2.4)."""
    pp = published_record
    assert pp.editing_revision_id is None
    resp = build_phenopacket_response(pp, include_state=True)
    assert resp.effective_state == "published"


@pytest.mark.asyncio
async def test_effective_state_reads_revision_when_editing(
    db_session, published_record, admin_user
):
    """effective_state == editing_revision.state when an edit is in progress."""
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
    # Refresh to reload scalar columns after commit; then re-attach the
    # in-memory revision object to simulate what the eager-load selectinload
    # would provide at runtime (build_phenopacket_response is sync and must
    # not trigger lazy IO).
    await db_session.refresh(pp)
    pp.editing_revision = rev  # simulate eager-load

    resp = build_phenopacket_response(pp, include_state=True)
    assert resp.effective_state == "draft"


@pytest.mark.asyncio
async def test_effective_state_none_when_include_state_false(
    db_session, published_record
):
    """effective_state is None for non-curator callers (include_state=False)."""
    resp = build_phenopacket_response(published_record, include_state=False)
    assert resp.effective_state is None
