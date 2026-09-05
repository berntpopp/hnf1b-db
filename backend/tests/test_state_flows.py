"""Integration tests for the four §6 transaction sequences.

Wave 7 D.1 Task 7. Tests cover:
- §6.1 clone-to-draft on a published record
- §6.3 draft edit as an append-only revision
- §6.4 simple state transitions
- §6.2 publish (head-swap)
- Error conditions: EditInProgress, RevisionMismatch, InvalidTransition

Fixtures ``draft_record`` and ``published_record`` are defined in conftest.py
and shared with test_state_invariants.py (Nit #3).
"""

import pytest
from sqlalchemy import select

from app.comments.models import Comment
from app.phenopackets.models import (
    ApprovalAttestation,
    Phenopacket,
    PhenopacketRevision,
)
from app.phenopackets.review.policy import ReviewPolicyError
from app.phenopackets.services.state_service import PhenopacketStateService


def _approval_fields(candidate: PhenopacketRevision) -> dict:
    """Echo the exact candidate identity and affirmative review attestation."""
    return {
        "candidate_revision_id": candidate.id,
        "candidate_content_sha256": candidate.content_sha256,
        "attestation": ApprovalAttestation(
            independent_review=True,
            no_unmanaged_conflict=True,
        ),
    }


def _publication_fields(approved: PhenopacketRevision) -> dict:
    """Echo the exact approved snapshot identity."""
    return {
        "approved_revision_id": approved.id,
        "approved_content_sha256": approved.content_sha256,
    }


# ---------------------------------------------------------------------------
# §6.1 — clone-to-draft on a published record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clone_to_draft_on_published(db_session, published_record, curator_user):
    """§6.1: editing a published record clones a draft; public pointer unchanged."""
    svc = PhenopacketStateService(db_session)
    old_head_id = published_record.head_published_revision_id

    new_content = {"id": "wave7-published-1", "a": 2}
    await svc.edit_record(
        published_record.id,
        new_content=new_content,
        change_reason="fix typo",
        expected_revision=1,
        actor=curator_user,
    )
    # State-service mutators flush internal revision inserts but leave the
    # final working-copy/pointer assignment to the caller's transaction.
    await db_session.flush()
    await db_session.refresh(published_record)

    # working copy updated
    assert published_record.phenopacket["id"] == "wave7-published-1"
    assert published_record.phenopacket["a"] == 2
    # public head pointer UNCHANGED (I1)
    assert published_record.head_published_revision_id == old_head_id
    # edit pointer and owner set
    assert published_record.editing_revision_id is not None
    assert published_record.draft_owner_id == curator_user.id
    # state stays 'published'
    assert published_record.state == "published"
    # revision bumped
    assert published_record.revision == 2

    # a new revision row was created with to_state='draft'
    rows = (
        (
            await db_session.execute(
                select(PhenopacketRevision)
                .where(PhenopacketRevision.record_id == published_record.id)
                .order_by(PhenopacketRevision.revision_number)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert rows[1].to_state == "draft"
    assert rows[1].id != published_record.head_published_revision_id
    assert rows[1].content_jsonb == published_record.phenopacket


@pytest.mark.asyncio
async def test_clone_to_draft_blocks_second_edit(
    db_session, published_record, curator_user, another_curator
):
    """§6.1 / I4: a second curator cannot hijack an in-progress edit.

    After Task 3 (dispatch on effective state): once a clone-to-draft has
    created a draft revision, the effective state becomes 'draft', so a
    second PUT routes to _inplace_save.  _inplace_save then enforces
    ownership, raising ForbiddenNotOwner for a non-owner curator.
    The net effect (second editor blocked with 409) is preserved.
    """
    svc = PhenopacketStateService(db_session)
    await svc.edit_record(
        published_record.id,
        new_content={"id": "wave7-published-1", "a": 2},
        change_reason="first edit",
        expected_revision=1,
        actor=curator_user,
    )

    with pytest.raises(svc.ForbiddenNotOwner):
        await svc.edit_record(
            published_record.id,
            new_content={"id": "wave7-published-1", "a": 3},
            change_reason="second edit",
            expected_revision=2,
            actor=another_curator,
        )


@pytest.mark.asyncio
async def test_clone_revision_mismatch(db_session, published_record, curator_user):
    """§6.1: stale expected_revision raises RevisionMismatch (409)."""
    svc = PhenopacketStateService(db_session)
    with pytest.raises(svc.RevisionMismatch):
        await svc.edit_record(
            published_record.id,
            new_content={"id": "wave7-published-1", "a": 99},
            change_reason="stale edit",
            expected_revision=999,  # wrong
            actor=curator_user,
        )


# ---------------------------------------------------------------------------
# §6.3 — draft edit creates an append-only revision row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_draft_save_appends_revision_row(db_session, draft_record, curator_user):
    """§6.3: a draft save preserves prior revisions and appends one snapshot."""
    svc = PhenopacketStateService(db_session)

    # First transition: submit → in_review (creates row 1)
    await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="go",
        expected_revision=1,
        actor=curator_user,
    )
    # Withdraw → draft (creates row 2)
    await svc.transition(
        draft_record.id,
        to_state="draft",
        reason="back",
        expected_revision=2,
        actor=curator_user,
    )

    rows_before = (
        (
            await db_session.execute(
                select(PhenopacketRevision).where(
                    PhenopacketRevision.record_id == draft_record.id
                )
            )
        )
        .scalars()
        .all()
    )

    # Saving a draft must not mutate the prior transition snapshot.
    await svc.edit_record(
        draft_record.id,
        new_content={"id": "wave7-draft-1", "x": "y"},
        change_reason="tweak",
        expected_revision=3,
        actor=curator_user,
    )

    rows_after = (
        (
            await db_session.execute(
                select(PhenopacketRevision).where(
                    PhenopacketRevision.record_id == draft_record.id
                )
            )
        )
        .scalars()
        .all()
    )

    assert len(rows_after) == len(rows_before) + 1
    assert rows_after[-1].event_type == "draft_saved"
    assert rows_after[-1].parent_revision_id == rows_before[-1].id
    await db_session.flush()
    await db_session.refresh(draft_record)
    assert draft_record.phenopacket["id"] == "wave7-draft-1"
    assert draft_record.phenopacket["x"] == "y"
    assert draft_record.revision == 4  # bumped by save


@pytest.mark.asyncio
async def test_draft_save_leaves_previous_editing_row_immutable(
    db_session, draft_record, curator_user
):
    """§6.3: a later draft save appends instead of rewriting its predecessor."""
    svc = PhenopacketStateService(db_session)
    # submit creates the editing row
    await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="go",
        expected_revision=1,
        actor=curator_user,
    )
    await svc.transition(
        draft_record.id,
        to_state="draft",
        reason="back",
        expected_revision=2,
        actor=curator_user,
    )
    await db_session.flush()
    await db_session.refresh(draft_record)
    editing_id = draft_record.editing_revision_id

    new_content = {"id": "wave7-draft-1", "updated": True}
    await svc.edit_record(
        draft_record.id,
        new_content=new_content,
        change_reason="updated reason",
        expected_revision=3,
        actor=curator_user,
    )

    previous_editing_row = (
        await db_session.execute(
            select(PhenopacketRevision).where(PhenopacketRevision.id == editing_id)
        )
    ).scalar_one()
    await db_session.flush()
    await db_session.refresh(draft_record)
    latest_editing_row = (
        await db_session.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.id == draft_record.editing_revision_id
            )
        )
    ).scalar_one()
    assert latest_editing_row.id != previous_editing_row.id
    assert previous_editing_row.change_reason == "back"
    assert latest_editing_row.change_reason == "updated reason"
    assert latest_editing_row.content_jsonb == draft_record.phenopacket


@pytest.mark.asyncio
async def test_in_place_save_forbidden_non_owner(
    db_session, draft_record, curator_user, another_curator
):
    """§6.3: non-owner curator cannot perform in-place save."""
    svc = PhenopacketStateService(db_session)
    with pytest.raises(svc.ForbiddenNotOwner):
        await svc.edit_record(
            draft_record.id,
            new_content={"id": "wave7-draft-1", "x": 1},
            change_reason="sneaky",
            expected_revision=1,
            actor=another_curator,
        )


@pytest.mark.asyncio
async def test_in_place_save_null_owner_forbidden_for_non_admin(
    db_session, another_curator, admin_user
):
    """§6.3 / Important #1: NULL draft_owner_id is NOT a bypass for non-admin curators.

    Before the fix, ``if not_admin and pp.draft_owner_id and not self._is_owner(pp, actor)``
    would short-circuit on the falsy ``draft_owner_id=None`` and allow the save.
    After the fix, ``_is_owner()`` returns False for None-owner records, so the
    non-admin curator is correctly rejected with ForbiddenNotOwner.

    This test FAILS against the pre-fix code and PASSES after the fix.
    """
    from app.phenopackets.models import Phenopacket

    # Create a draft record with draft_owner_id=None (as might occur for
    # records imported via migration without an explicit owner assignment).
    pp = Phenopacket(
        phenopacket_id="wave7-null-owner-1",
        phenopacket={"id": "wave7-null-owner-1"},
        state="draft",
        revision=1,
        draft_owner_id=None,  # ← the NULL-owner case
        created_by_id=admin_user.id,
    )
    db_session.add(pp)
    await db_session.commit()
    await db_session.refresh(pp)

    svc = PhenopacketStateService(db_session)

    # Non-admin curator must be rejected even though draft_owner_id is NULL.
    with pytest.raises(svc.ForbiddenNotOwner):
        await svc.edit_record(
            pp.id,
            new_content={"id": "wave7-null-owner-1", "x": 1},
            change_reason="should be blocked",
            expected_revision=1,
            actor=another_curator,
        )


# ---------------------------------------------------------------------------
# §6.4 — full lifecycle: draft → in_review → approved → published
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_lifecycle(db_session, draft_record, curator_user, admin_user):
    """Full pipeline: create → submit → approve → publish."""
    svc = PhenopacketStateService(db_session)

    # submit
    _, candidate = await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="ready",
        expected_revision=1,
        actor=curator_user,
    )
    await db_session.flush()
    await db_session.refresh(draft_record)
    assert draft_record.state == "in_review"
    assert draft_record.draft_owner_id == curator_user.id  # preserved through submit

    # approve
    _, approved = await svc.transition(
        draft_record.id,
        to_state="approved",
        reason="ok",
        expected_revision=draft_record.revision,
        actor=admin_user,
        **_approval_fields(candidate),
    )
    await db_session.flush()
    await db_session.refresh(draft_record)
    assert draft_record.state == "approved"

    # publish (head-swap §6.2)
    await svc.transition(
        draft_record.id,
        to_state="published",
        reason="go live",
        expected_revision=draft_record.revision,
        actor=admin_user,
        **_publication_fields(approved),
    )
    await db_session.flush()
    await db_session.refresh(draft_record)
    assert draft_record.state == "published"
    assert draft_record.head_published_revision_id is not None
    assert draft_record.editing_revision_id is None  # cleared on publish
    assert draft_record.draft_owner_id is None  # I5: cleared on publish

    # The record pointer is the sole head authority.
    head = (
        await db_session.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.id == draft_record.head_published_revision_id
            )
        )
    ).scalar_one()
    assert head.record_id == draft_record.id
    assert head.state == "published"


@pytest.mark.asyncio
async def test_archive_is_terminal(db_session, published_record, admin_user):
    """Archived state rejects all further transitions."""
    svc = PhenopacketStateService(db_session)
    await svc.transition(
        published_record.id,
        to_state="archived",
        reason="retire",
        expected_revision=1,
        actor=admin_user,
    )
    await db_session.flush()
    await db_session.refresh(published_record)
    assert published_record.state == "archived"
    assert published_record.draft_owner_id is None  # cleared on archive

    with pytest.raises(svc.InvalidTransition):
        await svc.transition(
            published_record.id,
            to_state="draft",
            reason="revive",
            expected_revision=2,
            actor=admin_user,
        )


@pytest.mark.asyncio
async def test_transition_revision_mismatch(db_session, draft_record, curator_user):
    """§6.4: stale expected_revision raises RevisionMismatch."""
    svc = PhenopacketStateService(db_session)
    with pytest.raises(svc.RevisionMismatch):
        await svc.transition(
            draft_record.id,
            to_state="in_review",
            reason="go",
            expected_revision=999,
            actor=curator_user,
        )


@pytest.mark.asyncio
async def test_direct_transition_cannot_bypass_independent_review(
    db_session, draft_record, curator_user
):
    """The state service rejects an owner's direct self-approval attempt."""
    svc = PhenopacketStateService(db_session)
    # submit first to reach in_review
    _, candidate = await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="go",
        expected_revision=1,
        actor=curator_user,
    )
    with pytest.raises(ReviewPolicyError) as exc_info:
        await svc.transition(
            draft_record.id,
            to_state="approved",
            reason="self-approve",
            expected_revision=2,
            actor=curator_user,
            **_approval_fields(candidate),
        )
    assert exc_info.value.code == "self_review_forbidden"
    assert draft_record.revision == 2


@pytest.mark.asyncio
async def test_eligible_curator_can_request_changes_directly(
    db_session, draft_record, curator_user, another_curator
):
    """A non-contributing curator may make a review decision through the service."""
    svc = PhenopacketStateService(db_session)
    await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="ready",
        expected_revision=1,
        actor=curator_user,
    )

    _, decision = await svc.transition(
        draft_record.id,
        to_state="changes_requested",
        reason="clarify evidence",
        expected_revision=2,
        actor=another_curator,
    )

    assert decision.state == "changes_requested"
    assert decision.actor_id == another_curator.id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("to_state", "extra"),
    [
        ("changes_requested", {}),
        (
            "approved",
            {
                "candidate_revision_id": 1,
                "candidate_content_sha256": "sha256:" + "1" * 64,
                "attestation": ApprovalAttestation(
                    independent_review=True,
                    no_unmanaged_conflict=True,
                ),
            },
        ),
        (
            "published",
            {
                "approved_revision_id": 1,
                "approved_content_sha256": "sha256:" + "1" * 64,
            },
        ),
    ],
)
async def test_direct_transition_rejects_whitespace_rationale_without_mutation(
    db_session,
    draft_record,
    admin_user,
    to_state,
    extra,
):
    """The shared service boundary normalizes rationale before locking/writing."""
    service = PhenopacketStateService(db_session)
    before = (
        draft_record.revision,
        draft_record.editing_revision_id,
        draft_record.head_published_revision_id,
    )

    with pytest.raises(service.InvalidRationale):
        await service.transition(
            draft_record.id,
            to_state=to_state,
            reason=" \t\n ",
            expected_revision=draft_record.revision,
            actor=admin_user,
            **extra,
        )

    assert (
        draft_record.revision,
        draft_record.editing_revision_id,
        draft_record.head_published_revision_id,
    ) == before


@pytest.mark.asyncio
async def test_direct_approval_requires_attestation_without_mutation(
    db_session,
    draft_record,
    admin_user,
):
    """Direct callers receive the dedicated attestation validation failure."""
    service = PhenopacketStateService(db_session)
    before = (
        draft_record.revision,
        draft_record.editing_revision_id,
        draft_record.head_published_revision_id,
    )

    with pytest.raises(service.AttestationRequired):
        await service.transition(
            draft_record.id,
            to_state="approved",
            reason="Exact review",
            expected_revision=draft_record.revision,
            actor=admin_user,
            candidate_revision_id=1,
            candidate_content_sha256="sha256:" + "1" * 64,
            attestation=None,
        )

    assert (
        draft_record.revision,
        draft_record.editing_revision_id,
        draft_record.head_published_revision_id,
    ) == before


@pytest.mark.asyncio
async def test_direct_transition_stores_normalized_rationale(
    db_session,
    draft_record,
    curator_user,
):
    """Audit and decision fields store the shared boundary's stripped text."""
    service = PhenopacketStateService(db_session)

    _, revision = await service.transition(
        draft_record.id,
        to_state="in_review",
        reason="  Ready for exact review. \t",
        expected_revision=draft_record.revision,
        actor=curator_user,
    )

    assert revision.change_reason == "Ready for exact review."


@pytest.mark.asyncio
async def test_unresolved_review_issue_blocks_direct_approval(
    db_session, draft_record, curator_user, another_curator
):
    """The locked service derives the unresolved count from real issue rows."""
    svc = PhenopacketStateService(db_session)
    _, candidate = await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="ready",
        expected_revision=1,
        actor=curator_user,
    )
    db_session.add(
        Comment(
            record_type="phenopacket",
            record_id=draft_record.id,
            author_id=another_curator.id,
            body_markdown="Blocking review issue",
            review_revision_id=candidate.id,
        )
    )
    await db_session.flush()

    with pytest.raises(ReviewPolicyError) as exc_info:
        await svc.transition(
            draft_record.id,
            to_state="approved",
            reason="cannot approve yet",
            expected_revision=2,
            actor=another_curator,
            **_approval_fields(candidate),
        )

    assert exc_info.value.code == "unresolved_review_issues"
    assert exc_info.value.context == {"unresolved_count": 1}


@pytest.mark.asyncio
async def test_approved_candidate_can_be_reopened_by_independent_curator(
    db_session, draft_record, curator_user, another_curator, admin_user
):
    """An eligible independent curator can reopen approval before publication."""
    svc = PhenopacketStateService(db_session)
    _, candidate = await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="ready",
        expected_revision=1,
        actor=curator_user,
    )
    await svc.transition(
        draft_record.id,
        to_state="approved",
        reason="reviewed",
        expected_revision=2,
        actor=admin_user,
        **_approval_fields(candidate),
    )

    _, reopened = await svc.transition(
        draft_record.id,
        to_state="changes_requested",
        reason="new concern",
        expected_revision=3,
        actor=another_curator,
    )

    assert reopened.from_state == "approved"
    assert reopened.to_state == "changes_requested"


async def _approved_chain_with_competing_submission(
    db_session,
    *,
    owner,
    candidate_submitter,
    approver,
    parent_case: str,
):
    """Persist an approved row plus a disconnected, later-numbered submission."""
    record = Phenopacket(
        phenopacket_id=f"approved-parent-{parent_case}",
        phenopacket={"id": f"approved-parent-{parent_case}"},
        state="draft",
        revision=0,
        draft_owner_id=owner.id,
        created_by_id=owner.id,
    )
    db_session.add(record)
    await db_session.flush()

    created = PhenopacketRevision(
        record_id=record.id,
        revision_number=1,
        state="draft",
        content_jsonb=record.phenopacket,
        change_reason="created",
        actor_id=owner.id,
        from_state=None,
        to_state="draft",
        event_type="created",
    )
    db_session.add(created)
    await db_session.flush()
    inspected = PhenopacketRevision(
        record_id=record.id,
        parent_revision_id=created.id,
        revision_number=2,
        state="in_review",
        content_jsonb=record.phenopacket,
        change_reason="actual candidate",
        actor_id=candidate_submitter.id,
        from_state="draft",
        to_state="in_review",
        event_type="state_transition",
    )
    db_session.add(inspected)
    await db_session.flush()
    disconnected = PhenopacketRevision(
        record_id=record.id,
        parent_revision_id=created.id,
        revision_number=3,
        state="in_review",
        content_jsonb=record.phenopacket,
        change_reason="disconnected candidate",
        actor_id=owner.id,
        from_state="draft",
        to_state="in_review",
        event_type="state_transition",
    )
    db_session.add(disconnected)
    await db_session.flush()

    if parent_case == "valid":
        approved_parent_id = inspected.id
    elif parent_case == "missing":
        approved_parent_id = None
    elif parent_case == "wrong_state":
        approved_parent_id = created.id
    elif parent_case == "non_prior":
        non_prior = PhenopacketRevision(
            record_id=record.id,
            parent_revision_id=disconnected.id,
            revision_number=100,
            state="in_review",
            content_jsonb=record.phenopacket,
            change_reason="non-prior parent",
            actor_id=owner.id,
            from_state="draft",
            to_state="in_review",
            event_type="state_transition",
        )
        db_session.add(non_prior)
        await db_session.flush()
        approved_parent_id = non_prior.id
    else:
        raise AssertionError(f"unknown parent case: {parent_case}")

    approved = PhenopacketRevision(
        record_id=record.id,
        parent_revision_id=approved_parent_id,
        revision_number=4,
        state="approved",
        content_jsonb=record.phenopacket,
        change_reason="approved",
        actor_id=approver.id,
        from_state="in_review",
        to_state="approved",
        event_type="state_transition",
    )
    db_session.add(approved)
    await db_session.flush()
    record.state = "approved"
    record.revision = 4
    record.editing_revision_id = approved.id
    await db_session.flush()
    return record


@pytest.mark.asyncio
async def test_approved_reopen_uses_direct_parent_candidate_submitter(
    db_session, curator_user, another_curator, admin_user
):
    """A disconnected later submission cannot hide the inspected submitter."""
    record = await _approved_chain_with_competing_submission(
        db_session,
        owner=curator_user,
        candidate_submitter=admin_user,
        approver=another_curator,
        parent_case="valid",
    )
    svc = PhenopacketStateService(db_session)

    with pytest.raises(ReviewPolicyError) as exc_info:
        await svc.transition(
            record.id,
            to_state="changes_requested",
            reason="attempt submitter reopen",
            expected_revision=4,
            actor=admin_user,
        )

    assert exc_info.value.code == "reviewer_submitted"
    assert record.revision == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("parent_case", ["missing", "wrong_state", "non_prior"])
async def test_approved_reopen_fails_closed_for_invalid_direct_parent(
    db_session,
    curator_user,
    another_curator,
    admin_user,
    parent_case,
):
    """Approved ancestry is never reconstructed from revision ordering."""
    record = await _approved_chain_with_competing_submission(
        db_session,
        owner=curator_user,
        candidate_submitter=curator_user,
        approver=admin_user,
        parent_case=parent_case,
    )
    svc = PhenopacketStateService(db_session)

    with pytest.raises(ReviewPolicyError) as exc_info:
        await svc.transition(
            record.id,
            to_state="changes_requested",
            reason="invalid ancestry",
            expected_revision=4,
            actor=another_curator,
        )

    assert exc_info.value.code == "review_author_unknown"
    assert record.revision == 4


@pytest.mark.asyncio
async def test_simple_transition_creates_revision_row(
    db_session, draft_record, curator_user
):
    """§6.4: each simple transition creates exactly one new revision row."""
    svc = PhenopacketStateService(db_session)
    await svc.transition(
        draft_record.id,
        to_state="in_review",
        reason="submitting",
        expected_revision=1,
        actor=curator_user,
    )
    rows = (
        (
            await db_session.execute(
                select(PhenopacketRevision).where(
                    PhenopacketRevision.record_id == draft_record.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].to_state == "in_review"
    assert rows[0].from_state == "draft"
