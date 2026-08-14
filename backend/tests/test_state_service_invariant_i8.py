"""I8 — pp.state is sticky post-first-publish.

After a published record enters the clone-cycle, pp.state must never leave
the 'published' (or 'archived') set regardless of which effective state the
in-flight revision row reaches.

Spec reference:
  docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §3 I8.
"""

import pytest

from app.phenopackets.models import ApprovalAttestation, PhenopacketRevision


@pytest.mark.parametrize(
    "to_state",
    ["in_review", "changes_requested", "approved", "published"],
)
@pytest.mark.asyncio
async def test_pp_state_never_exits_published_or_archived_post_first_publish(
    db_session, published_record, curator_user, admin_user, to_state
):
    """Through the whole cycle, pp.state stays in the sticky set.

    For each ``to_state`` target we drive the clone-cycle revision row to that
    state via the minimal legal transition sequence, then assert that
    ``pp.state`` is still ``'published'`` (never updated by the I8 gate in
    ``_simple_transition``).
    """
    from app.phenopackets.services.state_service import PhenopacketStateService

    svc = PhenopacketStateService(db_session)
    pp = published_record

    # Clone-to-draft: creates a revision row in state='draft'; pp.state stays 'published'.
    pp = await svc.edit_record(
        pp.id,
        new_content={"subject": {"id": "iter"}},
        change_reason="r",
        expected_revision=pp.revision,
        actor=curator_user,
    )

    # Minimal transition sequences to reach each target state.
    # curator_user owns the draft (set by edit_record); admin_user performs
    # admin-only steps (approve, changes_requested, publish).
    sequence_to_target: dict[str, list[tuple[str, object]]] = {
        "in_review": [
            ("in_review", curator_user),
        ],
        "changes_requested": [
            ("in_review", curator_user),
            ("changes_requested", admin_user),
        ],
        "approved": [
            ("in_review", curator_user),
            ("approved", admin_user),
        ],
        "published": [
            ("in_review", curator_user),
            ("approved", admin_user),
            ("published", admin_user),
        ],
    }

    candidate: PhenopacketRevision | None = None
    approved: PhenopacketRevision | None = None
    for state_target, actor in sequence_to_target[to_state]:
        exact_fields = {}
        if state_target == "approved":
            assert candidate is not None
            exact_fields = {
                "candidate_revision_id": candidate.id,
                "candidate_content_sha256": candidate.content_sha256,
                "attestation": ApprovalAttestation(
                    independent_review=True,
                    no_unmanaged_conflict=True,
                ),
            }
        elif state_target == "published":
            assert approved is not None
            exact_fields = {
                "approved_revision_id": approved.id,
                "approved_content_sha256": approved.content_sha256,
            }
        pp, transition_revision = await svc.transition(
            pp.id,
            to_state=state_target,
            reason="r",
            expected_revision=pp.revision,
            actor=actor,  # type: ignore[arg-type]
            **exact_fields,
        )
        if state_target == "in_review":
            candidate = transition_revision
        elif state_target == "approved":
            approved = transition_revision

    # I8: pp.state must never advance for a previously-published record
    # (unless the transition is 'archived', which is terminal).
    assert pp.state in ("published", "archived"), (
        f"I8 violated: pp.state={pp.state!r} after driving revision to {to_state!r}"
    )
