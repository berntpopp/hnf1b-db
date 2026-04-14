"""Full clone-cycle lifecycle: clone → submit → approve → publish + republish."""
import pytest

from app.phenopackets.services.state_service import PhenopacketStateService


@pytest.mark.asyncio
async def test_full_clone_cycle_republish(
    db_session, published_record, curator_user, admin_user
):
    """Clone, submit, approve, publish — and head-published pointer advances."""
    pp = published_record
    original_head_id = pp.head_published_revision_id
    svc = PhenopacketStateService(db_session)

    # Clone
    pp = await svc.edit_record(
        pp.id,
        new_content={"subject": {"id": "new-head"}},
        change_reason="fix typo",
        expected_revision=pp.revision,
        actor=curator_user,
    )
    # Submit
    pp, _ = await svc.transition(
        pp.id, to_state="in_review", reason="r", expected_revision=pp.revision, actor=curator_user
    )
    # Approve
    pp, _ = await svc.transition(
        pp.id, to_state="approved", reason="ok", expected_revision=pp.revision, actor=admin_user
    )
    # Publish
    pp, rev = await svc.transition(
        pp.id, to_state="published", reason="shipping", expected_revision=pp.revision, actor=admin_user
    )

    # Record-level state converges
    assert pp.state == "published"
    # Head pointer advanced to the new row
    assert pp.head_published_revision_id == rev.id
    assert pp.head_published_revision_id != original_head_id
    # Editing pointer cleared (§6.2)
    assert pp.editing_revision_id is None
    # Owner cleared (I5)
    assert pp.draft_owner_id is None
    # Public content converges
    assert pp.phenopacket["subject"]["id"] == "new-head"
