"""Clone-cycle withdraw — returns effective state to 'draft', pp.state stays 'published'.

Spec invariants I8 + I9:
  I8 — pp.state does not advance for previously-published records.
  I9 — effective state is authoritative for all decisions (reads the
       in-flight revision row's state when editing_revision_id is set).

After clone → submit (draft→in_review) → withdraw (in_review→draft):
  - pp.state               = 'published'   (I8: sticky)
  - revision row .state    = 'draft'        (withdraw re-opens for editing)
  - revision row .from_state = 'in_review'
  - revision row .to_state   = 'draft'
  - _effective_state(pp)   = 'draft'        (I9: reads revision row)

Spec reference:
  docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §3 I8/I9.
"""
import pytest


@pytest.mark.asyncio
async def test_clone_cycle_withdraw_keeps_pp_state(
    db_session, published_record, curator_user
):
    """Withdraw during clone-cycle returns effective state to 'draft', pp.state='published'."""
    from app.phenopackets.services.state_service import PhenopacketStateService

    svc = PhenopacketStateService(db_session)
    pp = published_record

    # Step 1 — clone-to-draft (pp.state stays 'published')
    pp = await svc.edit_record(
        pp.id,
        new_content={"subject": {"id": "c"}},
        change_reason="r",
        expected_revision=pp.revision,
        actor=curator_user,
    )

    # Step 2 — submit: effective draft→in_review
    pp, _ = await svc.transition(
        pp.id,
        to_state="in_review",
        reason="r",
        expected_revision=pp.revision,
        actor=curator_user,
    )

    # Step 3 — withdraw: effective in_review→draft
    # curator_user is the owner (set by edit_record), so this is permitted
    # by the guard rule ("in_review", "draft"): requires_ownership_or_admin=True.
    pp, rev = await svc.transition(
        pp.id,
        to_state="draft",
        reason="withdraw",
        expected_revision=pp.revision,
        actor=curator_user,
    )

    # I8: pp.state is unchanged (still 'published')
    assert pp.state == "published", (
        f"I8 violated: pp.state={pp.state!r} after withdraw"
    )

    # Revision row records the withdraw event
    assert rev.state == "draft"
    assert rev.from_state == "in_review"
    assert rev.to_state == "draft"

    # I9: effective state re-reads the revision row → 'draft'
    assert await svc._effective_state(pp) == "draft", (
        "I9 violated: effective state should be 'draft' after withdraw"
    )
