"""Forward clone-cycle: submit/approve/publish from a cloned draft."""
import pytest

from app.phenopackets.services.state_service import PhenopacketStateService


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Task 5 fixes transition() guard to use effective state; "
    "check_transition('published','in_review') raises InvalidTransition until then"
)
async def test_submit_from_clone_cycle_keeps_pp_state_published(
    db_session, published_record, curator_user
):
    """Submit after clone advances revision state but not pp.state.

    Task 4 rewires _simple_transition: from_state = effective_state(pp), and
    pp.state is sticky under I8 (only advances for never-published records OR
    on archive). Task 5 will fix the transition() guard so that check_transition
    receives the effective state instead of pp.state — at that point this test
    will pass and the xfail marker should be removed.
    """
    svc = PhenopacketStateService(db_session)
    pp = published_record

    # Clone to draft
    pp = await svc.edit_record(
        pp.id,
        new_content={"subject": {"id": "clone-1"}},
        change_reason="fix typo",
        expected_revision=pp.revision,
        actor=curator_user,
    )
    assert pp.state == "published"

    # Submit
    pp, rev = await svc.transition(
        pp.id,
        to_state="in_review",
        reason="ready for review",
        expected_revision=pp.revision,
        actor=curator_user,
    )

    # pp.state sticky (I8)
    assert pp.state == "published"
    # Editing pointer advanced to the new in_review row
    assert pp.editing_revision_id == rev.id
    # The in_review row's from_state is 'draft' (effective state before), not 'published'
    assert rev.from_state == "draft"
    assert rev.to_state == "in_review"
    assert rev.state == "in_review"
