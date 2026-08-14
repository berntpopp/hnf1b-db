"""Independent-review policy tests against real revision rows."""

from __future__ import annotations

from typing import Any

import pytest

from app.phenopackets.models import Phenopacket, PhenopacketRevision
from app.phenopackets.review.policy import ReviewPolicy, ReviewPolicyError


async def _review_candidate(
    db_session: Any,
    *,
    owner_id: int | None,
    submitter_id: int,
    contributor_id: int | None = None,
    contributor_event: str = "draft_saved",
    effective_state: str = "in_review",
) -> tuple[Phenopacket, PhenopacketRevision]:
    """Persist one active review cycle and return its submitted candidate."""
    record = Phenopacket(
        phenopacket_id=f"review-policy-{owner_id}-{submitter_id}-{contributor_id}",
        phenopacket={"id": "review-policy"},
        state="draft",
        revision=0,
        draft_owner_id=owner_id,
        created_by_id=owner_id,
    )
    db_session.add(record)
    await db_session.flush()

    parent_id = None
    if contributor_id is not None:
        contribution = PhenopacketRevision(
            record_id=record.id,
            revision_number=1,
            state="draft",
            content_jsonb={"id": "review-policy", "saved": True},
            change_reason="content contribution",
            actor_id=contributor_id,
            from_state="draft",
            to_state="draft",
            event_type=contributor_event,
        )
        db_session.add(contribution)
        await db_session.flush()
        parent_id = contribution.id

    candidate = PhenopacketRevision(
        record_id=record.id,
        parent_revision_id=parent_id,
        revision_number=2 if contributor_id is not None else 1,
        state="in_review",
        content_jsonb={"id": "review-policy", "saved": contributor_id is not None},
        change_reason="submit for review",
        actor_id=submitter_id,
        from_state="draft",
        to_state="in_review",
        event_type="state_transition",
    )
    db_session.add(candidate)
    await db_session.flush()

    record.state = effective_state
    record.revision = candidate.revision_number
    if owner_id is not None:
        record.editing_revision_id = candidate.id
    await db_session.flush()
    return record, candidate


def _capability(capabilities: Any, action: str) -> Any:
    """Select an action capability without deriving its expected result."""
    return next(item for item in capabilities.actions if item.action == action)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "is_owner", "submitted", "contributed", "allowed", "code"),
    [
        ("curator", False, False, False, True, None),
        ("admin", False, False, False, True, None),
        ("curator", True, False, True, False, "self_review_forbidden"),
        ("admin", False, True, False, False, "reviewer_submitted"),
        ("admin", False, False, True, False, "reviewer_contributed"),
    ],
)
async def test_review_eligibility_matrix(
    db_session,
    curator_user,
    another_curator,
    admin_user,
    role,
    is_owner,
    submitted,
    contributed,
    allowed,
    code,
):
    """Owner, submitter, and contributor status cannot be bypassed by admins."""
    actor = admin_user if role == "admin" else another_curator
    owner_id = actor.id if is_owner else curator_user.id
    submitter_id = actor.id if submitted else curator_user.id
    contributor_id = actor.id if contributed else None
    record, candidate = await _review_candidate(
        db_session,
        owner_id=owner_id,
        submitter_id=submitter_id,
        contributor_id=contributor_id,
    )

    capabilities = await ReviewPolicy.evaluate(
        db_session,
        record,
        candidate,
        actor,
        unresolved_count=0,
    )
    approve = _capability(capabilities, "approve")

    assert approve.allowed is allowed
    assert (approve.blocked_by[0] if approve.blocked_by else None) == code
    if is_owner and contributed:
        assert approve.blocked_by == [
            "self_review_forbidden",
            "reviewer_contributed",
        ]


@pytest.mark.asyncio
async def test_null_owner_fails_closed(db_session, curator_user, another_curator):
    """A missing owner is uncertainty, never proof of reviewer independence."""
    record, candidate = await _review_candidate(
        db_session,
        owner_id=None,
        submitter_id=curator_user.id,
    )

    capabilities = await ReviewPolicy.evaluate(
        db_session,
        record,
        candidate,
        another_curator,
        unresolved_count=0,
    )

    assert _capability(capabilities, "approve").blocked_by == ["review_author_unknown"]
    with pytest.raises(ReviewPolicyError) as exc_info:
        await ReviewPolicy.require_independent_reviewer(
            db_session,
            record,
            candidate,
            another_curator,
            unresolved_count=0,
            action="approve",
        )
    assert exc_info.value.code == "review_author_unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event_type", "allowed"),
    [
        ("created", False),
        ("draft_created", False),
        ("draft_saved", False),
        ("state_transition", True),
    ],
)
async def test_only_content_events_create_contributor_blockers(
    db_session,
    curator_user,
    another_curator,
    event_type,
    allowed,
):
    """Discussion and lifecycle events never turn an actor into a contributor."""
    record, candidate = await _review_candidate(
        db_session,
        owner_id=curator_user.id,
        submitter_id=curator_user.id,
        contributor_id=another_curator.id,
        contributor_event=event_type,
    )

    capabilities = await ReviewPolicy.evaluate(
        db_session,
        record,
        candidate,
        another_curator,
        unresolved_count=0,
    )

    approve = _capability(capabilities, "approve")
    assert approve.allowed is allowed
    assert approve.blocked_by == ([] if allowed else ["reviewer_contributed"])


@pytest.mark.asyncio
async def test_viewer_has_no_review_actions(db_session, curator_user, viewer_user):
    """Active viewers receive no private review mutation capabilities."""
    record, candidate = await _review_candidate(
        db_session,
        owner_id=curator_user.id,
        submitter_id=curator_user.id,
    )

    capabilities = await ReviewPolicy.evaluate(
        db_session,
        record,
        candidate,
        viewer_user,
        unresolved_count=0,
    )

    assert capabilities.actions == []


@pytest.mark.asyncio
async def test_unresolved_issues_block_only_approval(
    db_session, curator_user, another_curator
):
    """An eligible reviewer may request changes despite unresolved issues."""
    record, candidate = await _review_candidate(
        db_session,
        owner_id=curator_user.id,
        submitter_id=curator_user.id,
    )

    capabilities = await ReviewPolicy.evaluate(
        db_session,
        record,
        candidate,
        another_curator,
        unresolved_count=3,
    )

    assert _capability(capabilities, "request_changes").allowed is True
    assert _capability(capabilities, "request_changes").blocked_by == []
    assert _capability(capabilities, "approve").allowed is False
    assert _capability(capabilities, "approve").blocked_by == [
        "unresolved_review_issues"
    ]

    with pytest.raises(ReviewPolicyError) as exc_info:
        await ReviewPolicy.require_independent_reviewer(
            db_session,
            record,
            candidate,
            another_curator,
            unresolved_count=3,
            action="approve",
        )
    assert exc_info.value.context == {"unresolved_count": 3}


@pytest.mark.asyncio
async def test_contributor_scope_begins_after_published_head(
    db_session, curator_user, another_curator
):
    """Content work at or before the public head does not poison a new cycle."""
    record = Phenopacket(
        phenopacket_id="review-policy-published-boundary",
        phenopacket={"id": "review-policy-published-boundary"},
        state="draft",
        revision=1,
        draft_owner_id=curator_user.id,
        created_by_id=curator_user.id,
    )
    db_session.add(record)
    await db_session.flush()
    old_head = PhenopacketRevision(
        record_id=record.id,
        revision_number=1,
        state="published",
        content_jsonb={"id": "review-policy-published-boundary"},
        change_reason="old cycle contribution",
        actor_id=another_curator.id,
        from_state="draft",
        to_state="published",
        event_type="draft_saved",
    )
    db_session.add(old_head)
    await db_session.flush()
    record.state = "published"
    record.head_published_revision_id = old_head.id
    await db_session.flush()

    contribution = PhenopacketRevision(
        record_id=record.id,
        parent_revision_id=old_head.id,
        revision_number=2,
        state="draft",
        content_jsonb={"id": "wave7-published-1", "changed": True},
        change_reason="new cycle edit",
        actor_id=curator_user.id,
        from_state="published",
        to_state="draft",
        event_type="draft_created",
    )
    db_session.add(contribution)
    await db_session.flush()
    candidate = PhenopacketRevision(
        record_id=record.id,
        parent_revision_id=contribution.id,
        revision_number=3,
        state="in_review",
        content_jsonb=contribution.content_jsonb,
        change_reason="submit",
        actor_id=curator_user.id,
        from_state="draft",
        to_state="in_review",
        event_type="state_transition",
    )
    db_session.add(candidate)
    await db_session.flush()
    record.editing_revision_id = candidate.id
    record.revision = 3
    await db_session.flush()

    capabilities = await ReviewPolicy.evaluate(
        db_session,
        record,
        candidate,
        another_curator,
        unresolved_count=0,
    )

    assert _capability(capabilities, "approve").allowed is True


@pytest.mark.asyncio
async def test_closed_candidate_has_stable_review_closed_blocker(
    db_session, curator_user, another_curator
):
    """A stale candidate is denied without exposing its content."""
    record, candidate = await _review_candidate(
        db_session,
        owner_id=curator_user.id,
        submitter_id=curator_user.id,
        effective_state="changes_requested",
    )
    closed = PhenopacketRevision(
        record_id=record.id,
        parent_revision_id=candidate.id,
        revision_number=2,
        state="changes_requested",
        content_jsonb=candidate.content_jsonb,
        change_reason="review closed",
        actor_id=another_curator.id,
        from_state="in_review",
        to_state="changes_requested",
        event_type="state_transition",
    )
    db_session.add(closed)
    await db_session.flush()
    record.revision = 2
    record.editing_revision_id = closed.id
    await db_session.flush()

    capabilities = await ReviewPolicy.evaluate(
        db_session,
        record,
        candidate,
        another_curator,
        unresolved_count=0,
    )

    assert _capability(capabilities, "approve").blocked_by == ["review_closed"]


@pytest.mark.asyncio
async def test_approved_capabilities_allow_reopen_and_admin_publish(
    db_session, curator_user, another_curator, admin_user
):
    """Approved candidates may be reopened; publication stays admin-only."""
    record, candidate = await _review_candidate(
        db_session,
        owner_id=curator_user.id,
        submitter_id=curator_user.id,
    )
    approved = PhenopacketRevision(
        record_id=record.id,
        parent_revision_id=candidate.id,
        revision_number=2,
        state="approved",
        content_jsonb=candidate.content_jsonb,
        change_reason="approve",
        actor_id=admin_user.id,
        from_state="in_review",
        to_state="approved",
        event_type="state_transition",
    )
    db_session.add(approved)
    await db_session.flush()
    record.state = "approved"
    record.revision = 2
    record.editing_revision_id = approved.id
    await db_session.flush()

    curator_capabilities = await ReviewPolicy.evaluate(
        db_session,
        record,
        candidate,
        another_curator,
        unresolved_count=0,
    )
    admin_capabilities = await ReviewPolicy.evaluate(
        db_session,
        record,
        candidate,
        admin_user,
        unresolved_count=0,
    )

    assert [item.action for item in curator_capabilities.actions] == ["request_changes"]
    assert _capability(curator_capabilities, "request_changes").allowed is True
    assert [item.action for item in admin_capabilities.actions] == [
        "request_changes",
        "publish",
    ]
    assert _capability(admin_capabilities, "publish").allowed is True
