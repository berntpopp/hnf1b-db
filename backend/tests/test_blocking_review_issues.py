"""Blocking review-issue service and API behavior."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import event, select

from app.comments.models import CommentResolutionEvent
from app.comments.schemas import (
    CommentCreate,
    ReviewIssueReopenRequest,
    ReviewIssueResolveRequest,
)
from app.comments.service import CommentsService
from app.models.user import User
from app.phenopackets.models import (
    ApprovalAttestation,
    Phenopacket,
    PhenopacketRevision,
)
from app.phenopackets.review.policy import ReviewPolicyError
from app.phenopackets.services.state_service import PhenopacketStateService


async def _seed_review_cycle(db_session, *, owner, submitter):
    """Persist a never-published active review candidate."""
    record = Phenopacket(
        phenopacket_id=f"blocking-review-{owner.id}-{submitter.id}",
        phenopacket={"id": "blocking-review"},
        state="draft",
        revision=0,
        draft_owner_id=owner.id,
        created_by_id=owner.id,
    )
    db_session.add(record)
    await db_session.flush()
    root = PhenopacketRevision(
        record_id=record.id,
        revision_number=1,
        state="draft",
        content_jsonb=record.phenopacket,
        change_reason="create",
        actor_id=owner.id,
        from_state=None,
        to_state="draft",
        event_type="created",
    )
    db_session.add(root)
    await db_session.flush()
    candidate = PhenopacketRevision(
        record_id=record.id,
        parent_revision_id=root.id,
        revision_number=2,
        state="in_review",
        content_jsonb=record.phenopacket,
        change_reason="submit",
        actor_id=submitter.id,
        from_state="draft",
        to_state="in_review",
        event_type="state_transition",
    )
    db_session.add(candidate)
    await db_session.flush()
    record.state = "in_review"
    record.revision = 2
    record.editing_revision_id = candidate.id
    await db_session.flush()
    return record, candidate


async def _headers_for(client, username: str, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/v2/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.json()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _post_issue(client, headers, record, candidate):
    return await client.post(
        "/api/v2/comments",
        headers=headers,
        json={
            "record_type": "phenopacket",
            "record_id": str(record.id),
            "body_markdown": "Blocking review concern",
            "mention_user_ids": [],
            "record_revision": record.revision,
            "review_revision_id": candidate.id,
        },
    )


def test_review_issue_request_schemas_are_strict_trimmed_and_literal() -> None:
    """Conditional issue inputs reject missing evidence and normalize rationale."""
    resolved = ReviewIssueResolveRequest(
        record_revision=4,
        disposition="retracted",
        rationale="  duplicate concern  ",
    )
    reopened = ReviewIssueReopenRequest(
        record_revision=5,
        rationale="  regression returned  ",
    )

    assert resolved.rationale == "duplicate concern"
    assert reopened.rationale == "regression returned"
    with pytest.raises(ValidationError):
        ReviewIssueResolveRequest(
            record_revision=4,
            disposition="ignored",
            rationale="not allowed",
        )
    with pytest.raises(ValidationError):
        ReviewIssueResolveRequest(
            record_revision=4,
            disposition="addressed",
            rationale="   ",
        )
    with pytest.raises(ValidationError):
        ReviewIssueReopenRequest(record_revision=-1, rationale="valid")


def test_comment_create_accepts_paired_review_issue_identity() -> None:
    """Blocking create can carry exact record and candidate revisions."""
    request = CommentCreate(
        record_type="phenopacket",
        record_id="79e6dd86-e399-48dc-bb20-797231582df7",
        body_markdown="This must be addressed.",
        record_revision=8,
        review_revision_id=11,
    )

    assert request.record_revision == 8
    assert request.review_revision_id == 11


@pytest.mark.asyncio
async def test_blocking_issue_lifecycle_appends_events_and_keeps_identity(
    db_session, curator_user, another_curator
):
    """Resolve, reopen, and retract append evidence before updating projection."""
    record, candidate = await _seed_review_cycle(
        db_session, owner=curator_user, submitter=curator_user
    )
    await db_session.commit()
    service = CommentsService(db_session)
    issue = await service.create(
        record_type="phenopacket",
        record_id=record.id,
        body_markdown="Address this concern.",
        mention_user_ids=[],
        actor=another_curator,
        record_revision=record.revision,
        review_revision_id=candidate.id,
    )

    resolved = await service.resolve(
        comment_id=issue.id,
        actor=another_curator,
        issue_input={
            "record_revision": record.revision,
            "disposition": "addressed",
            "rationale": "  corrected in source  ",
        },
    )
    assert resolved.resolved_at is not None
    assert resolved.review_revision_id == candidate.id

    reopened = await service.unresolve(
        comment_id=issue.id,
        actor=another_curator,
        issue_input={
            "record_revision": record.revision,
            "rationale": "  concern returned  ",
        },
    )
    assert reopened.resolved_at is None
    assert reopened.review_revision_id == candidate.id

    retracted = await service.resolve(
        comment_id=issue.id,
        actor=another_curator,
        issue_input={
            "record_revision": record.revision,
            "disposition": "retracted",
            "rationale": "  report was mistaken  ",
        },
    )
    assert retracted.resolved_at is not None
    assert retracted.deleted_at is None

    events = list(
        (
            await db_session.execute(
                select(CommentResolutionEvent)
                .where(CommentResolutionEvent.comment_id == issue.id)
                .order_by(CommentResolutionEvent.id)
            )
        ).scalars()
    )
    assert [(item.action, item.disposition, item.rationale) for item in events] == [
        ("resolved", "addressed", "corrected in source"),
        ("reopened", None, "concern returned"),
        ("resolved", "retracted", "report was mistaken"),
    ]


@pytest.mark.asyncio
async def test_blocking_issue_rejects_stale_unrelated_and_partial_identity(
    db_session, curator_user, another_curator
):
    """Client-nominated revisions never escape exact locked-record validation."""
    record, candidate = await _seed_review_cycle(
        db_session, owner=curator_user, submitter=curator_user
    )
    other, other_candidate = await _seed_review_cycle(
        db_session, owner=another_curator, submitter=another_curator
    )
    service = CommentsService(db_session)

    with pytest.raises(CommentsService.RevisionMismatch):
        await service.create(
            record_type="phenopacket",
            record_id=record.id,
            body_markdown="stale",
            mention_user_ids=[],
            actor=another_curator,
            record_revision=record.revision - 1,
            review_revision_id=candidate.id,
        )
    with pytest.raises(CommentsService.ReviewRevisionMismatch):
        await service.create(
            record_type="phenopacket",
            record_id=record.id,
            body_markdown="wrong record",
            mention_user_ids=[],
            actor=another_curator,
            record_revision=record.revision,
            review_revision_id=other_candidate.id,
        )
    with pytest.raises(CommentsService.IssueInputInvalid):
        await service.create(
            record_type="phenopacket",
            record_id=record.id,
            body_markdown="partial",
            mention_user_ids=[],
            actor=another_curator,
            review_revision_id=candidate.id,
        )
    assert other.id != record.id


@pytest.mark.asyncio
async def test_blocking_issue_owner_cannot_resolve_reopen_or_delete(
    db_session, curator_user, another_curator, admin_user
):
    """Neither authorship nor admin status bypasses issue policy or deletion ban."""
    record, candidate = await _seed_review_cycle(
        db_session, owner=admin_user, submitter=curator_user
    )
    service = CommentsService(db_session)
    issue = await service.create(
        record_type="phenopacket",
        record_id=record.id,
        body_markdown="independent issue",
        mention_user_ids=[],
        actor=another_curator,
        record_revision=record.revision,
        review_revision_id=candidate.id,
    )

    with pytest.raises(ReviewPolicyError) as exc_info:
        await service.resolve(
            comment_id=issue.id,
            actor=admin_user,
            issue_input={
                "record_revision": record.revision,
                "disposition": "addressed",
                "rationale": "owner attempt",
            },
        )
    assert exc_info.value.code == "self_review_forbidden"

    with pytest.raises(CommentsService.ReviewIssueDeleteForbidden):
        await service.soft_delete(comment_id=issue.id, actor=another_curator)
    with pytest.raises(CommentsService.ReviewIssueDeleteForbidden):
        await service.soft_delete(comment_id=issue.id, actor=admin_user)


@pytest.mark.asyncio
async def test_comment_mutation_lock_order_includes_soft_deleted_owner(
    db_session, published_record, curator_user
):
    """Identity probe precedes record lock and comment lock for every mutation."""
    service = CommentsService(db_session)
    comment = await service.create(
        record_type="phenopacket",
        record_id=published_record.id,
        body_markdown="ordinary",
        mention_user_ids=[],
        actor=curator_user,
    )
    published_record.deleted_at = published_record.created_at
    await db_session.flush()

    statements: list[str] = []

    def capture_statement(_conn, _cursor, statement, _params, _context, _many):
        normalized = " ".join(statement.lower().split())
        if " from comments " in normalized or " from phenopackets " in normalized:
            statements.append(normalized)

    bind = db_session.get_bind()
    event.listen(bind, "before_cursor_execute", capture_statement)
    try:
        await service.resolve(comment_id=comment.id, actor=curator_user)
    finally:
        event.remove(bind, "before_cursor_execute", capture_statement)

    lock_queries = [
        statement
        for statement in statements
        if "where comments.id" in statement or "where phenopackets.id" in statement
    ]
    assert "from comments" in lock_queries[0]
    assert "for update" not in lock_queries[0]
    assert "from phenopackets" in lock_queries[1]
    assert "for update" in lock_queries[1]
    assert "from comments" in lock_queries[2]
    assert "for update" in lock_queries[2]


@pytest.mark.asyncio
async def test_blocking_issue_routes_require_conditional_evidence_and_independence(
    async_client,
    db_session,
    curator_user,
    curator_headers,
    another_curator,
    admin_headers,
):
    """API maps issue validation, policy denial, and deletion uniformly."""
    reviewer_headers = await _headers_for(
        async_client, another_curator.username, "CuratorPass123!"
    )
    record, candidate = await _seed_review_cycle(
        db_session, owner=curator_user, submitter=curator_user
    )
    record_revision = record.revision
    created = await _post_issue(async_client, reviewer_headers, record, candidate)
    assert created.status_code == 201, created.json()
    issue_id = created.json()["id"]

    missing = await async_client.post(
        f"/api/v2/comments/{issue_id}/resolve",
        headers=reviewer_headers,
    )
    assert missing.status_code == 422
    assert missing.json()["detail"]["code"] == "review_issue_input_invalid"

    owner_resolve = await async_client.post(
        f"/api/v2/comments/{issue_id}/resolve",
        headers=curator_headers,
        json={
            "record_revision": record_revision,
            "disposition": "addressed",
            "rationale": "owner cannot do this",
        },
    )
    assert owner_resolve.status_code == 403
    assert owner_resolve.json()["detail"]["code"] == "self_review_forbidden"

    for headers in (curator_headers, reviewer_headers, admin_headers):
        deleted = await async_client.delete(
            f"/api/v2/comments/{issue_id}", headers=headers
        )
        assert deleted.status_code == 409
        assert deleted.json()["detail"]["code"] == "review_issue_delete_forbidden"

    resolved = await async_client.post(
        f"/api/v2/comments/{issue_id}/resolve",
        headers=reviewer_headers,
        json={
            "record_revision": record_revision,
            "disposition": "retracted",
            "rationale": "concern withdrawn",
        },
    )
    assert resolved.status_code == 200, resolved.json()
    assert resolved.json()["resolved_at"] is not None
    assert resolved.json()["deleted_at"] is None

    reopened = await async_client.post(
        f"/api/v2/comments/{issue_id}/unresolve",
        headers=reviewer_headers,
        json={
            "record_revision": record_revision,
            "rationale": "new evidence",
        },
    )
    assert reopened.status_code == 200, reopened.json()
    assert reopened.json()["resolved_at"] is None


@pytest.mark.asyncio
async def test_old_issue_in_current_cycle_remains_actionable_after_resubmit(
    async_client,
    db_session,
    curator_user,
    another_curator,
):
    """Resubmission must not strand an issue linked to the earlier candidate."""
    reviewer_headers = await _headers_for(
        async_client, another_curator.username, "CuratorPass123!"
    )
    record, first_candidate = await _seed_review_cycle(
        db_session, owner=curator_user, submitter=curator_user
    )
    created = await _post_issue(async_client, reviewer_headers, record, first_candidate)
    assert created.status_code == 201, created.json()
    issue_id = created.json()["id"]

    state_service = PhenopacketStateService(db_session)
    record, _ = await state_service.transition(
        record.id,
        to_state="changes_requested",
        reason="address the blocking issue",
        expected_revision=record.revision,
        actor=another_curator,
    )
    record, resubmitted = await state_service.transition(
        record.id,
        to_state="in_review",
        reason="resubmit after changes",
        expected_revision=record.revision,
        actor=curator_user,
    )
    assert resubmitted.id != first_candidate.id

    resolved = await async_client.post(
        f"/api/v2/comments/{issue_id}/resolve",
        headers=reviewer_headers,
        json={
            "record_revision": record.revision,
            "disposition": "addressed",
            "rationale": "fixed during resubmission",
        },
    )
    assert resolved.status_code == 200, resolved.json()
    reopened = await async_client.post(
        f"/api/v2/comments/{issue_id}/unresolve",
        headers=reviewer_headers,
        json={
            "record_revision": record.revision,
            "rationale": "verify one remaining concern",
        },
    )
    assert reopened.status_code == 200, reopened.json()
    resolved_again = await async_client.post(
        f"/api/v2/comments/{issue_id}/resolve",
        headers=reviewer_headers,
        json={
            "record_revision": record.revision,
            "disposition": "accepted_with_rationale",
            "rationale": "remaining concern accepted",
        },
    )
    assert resolved_again.status_code == 200, resolved_again.json()

    record = await db_session.get(Phenopacket, record.id)
    assert record is not None
    approved, _ = await state_service.transition(
        record.id,
        to_state="approved",
        reason="all current-cycle issues handled",
        expected_revision=record.revision,
        actor=another_curator,
        candidate_revision_id=resubmitted.id,
        candidate_content_sha256=resubmitted.content_sha256,
        attestation=ApprovalAttestation(
            independent_review=True,
            no_unmanaged_conflict=True,
        ),
    )
    assert approved.state == "approved"


@pytest.mark.asyncio
async def test_published_cycle_issue_is_non_actionable_and_does_not_gate_next_cycle(
    async_client,
    db_session,
    draft_record,
    curator_user,
    another_curator,
    admin_user,
):
    """A resolved prior-cycle issue cannot reopen or gate the next approval."""
    reviewer_headers = await _headers_for(
        async_client, another_curator.username, "CuratorPass123!"
    )
    state_service = PhenopacketStateService(db_session)
    root = PhenopacketRevision(
        record_id=draft_record.id,
        revision_number=draft_record.revision,
        state="draft",
        content_jsonb=draft_record.phenopacket,
        change_reason="create",
        actor_id=curator_user.id,
        from_state=None,
        to_state="draft",
        event_type="created",
    )
    db_session.add(root)
    await db_session.flush()
    draft_record.editing_revision_id = root.id
    await db_session.flush()
    record, first_candidate = await state_service.transition(
        draft_record.id,
        to_state="in_review",
        reason="first cycle submission",
        expected_revision=draft_record.revision,
        actor=curator_user,
    )
    created = await _post_issue(async_client, reviewer_headers, record, first_candidate)
    assert created.status_code == 201, created.json()
    issue_id = created.json()["id"]
    resolved = await async_client.post(
        f"/api/v2/comments/{issue_id}/resolve",
        headers=reviewer_headers,
        json={
            "record_revision": record.revision,
            "disposition": "addressed",
            "rationale": "first cycle fixed",
        },
    )
    assert resolved.status_code == 200, resolved.json()

    record = await db_session.get(Phenopacket, record.id)
    assert record is not None and first_candidate.content_sha256 is not None
    record, approved = await state_service.transition(
        record.id,
        to_state="approved",
        reason="approve first cycle",
        expected_revision=record.revision,
        actor=another_curator,
        candidate_revision_id=first_candidate.id,
        candidate_content_sha256=first_candidate.content_sha256,
        attestation=ApprovalAttestation(
            independent_review=True,
            no_unmanaged_conflict=True,
        ),
    )
    assert approved.content_sha256 is not None
    record, _ = await state_service.transition(
        record.id,
        to_state="published",
        reason="publish first cycle",
        expected_revision=record.revision,
        actor=admin_user,
        approved_revision_id=approved.id,
        approved_content_sha256=approved.content_sha256,
    )
    record = await state_service.edit_record(
        record.id,
        new_content=record.phenopacket,
        change_reason="open second cycle",
        expected_revision=record.revision,
        actor=curator_user,
    )
    record, next_candidate = await state_service.transition(
        record.id,
        to_state="in_review",
        reason="submit second cycle",
        expected_revision=record.revision,
        actor=curator_user,
    )
    record_id = record.id
    reviewer_id = another_curator.id
    next_candidate_id = next_candidate.id
    next_candidate_digest = next_candidate.content_sha256
    next_record_revision = record.revision
    await db_session.commit()

    historical_reopen = await async_client.post(
        f"/api/v2/comments/{issue_id}/unresolve",
        headers=reviewer_headers,
        json={
            "record_revision": next_record_revision,
            "rationale": "must not reopen a published cycle",
        },
    )
    assert historical_reopen.status_code == 409, historical_reopen.json()
    assert historical_reopen.json()["detail"]["code"] == "review_closed"

    record = await db_session.get(Phenopacket, record_id)
    reviewer = await db_session.get(User, reviewer_id)
    assert record is not None and reviewer is not None
    assert next_candidate_digest is not None
    record, next_approval = await state_service.transition(
        record.id,
        to_state="approved",
        reason="prior-cycle issue is non-gating",
        expected_revision=record.revision,
        actor=reviewer,
        candidate_revision_id=next_candidate_id,
        candidate_content_sha256=next_candidate_digest,
        attestation=ApprovalAttestation(
            independent_review=True,
            no_unmanaged_conflict=True,
        ),
    )
    assert next_approval.state == "approved"
    assert record.editing_revision_id == next_approval.id


@pytest.mark.asyncio
async def test_blocking_issue_create_route_rejects_partial_stale_and_closed_inputs(
    async_client, db_session, curator_user, another_curator
):
    """Create conflict codes distinguish malformed, stale, and closed review input."""
    reviewer_headers = await _headers_for(
        async_client, another_curator.username, "CuratorPass123!"
    )
    record, candidate = await _seed_review_cycle(
        db_session, owner=curator_user, submitter=curator_user
    )
    record_id = record.id
    candidate_id = candidate.id
    record_revision = record.revision
    curator_id = curator_user.id
    await db_session.commit()
    payload = {
        "record_type": "phenopacket",
        "record_id": str(record_id),
        "body_markdown": "Blocking review concern",
        "mention_user_ids": [],
        "record_revision": record_revision,
        "review_revision_id": candidate_id,
    }

    partial = await async_client.post(
        "/api/v2/comments",
        headers=reviewer_headers,
        json={key: value for key, value in payload.items() if key != "record_revision"},
    )
    assert partial.status_code == 422
    assert partial.json()["detail"]["code"] == "review_issue_input_invalid"

    stale = await async_client.post(
        "/api/v2/comments",
        headers=reviewer_headers,
        json={**payload, "record_revision": record_revision - 1},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "revision_mismatch"

    record = await db_session.get(Phenopacket, record_id)
    candidate = await db_session.get(PhenopacketRevision, candidate_id)
    assert record is not None and candidate is not None
    active_draft = PhenopacketRevision(
        record_id=record_id,
        parent_revision_id=candidate_id,
        revision_number=3,
        state="draft",
        content_jsonb=record.phenopacket,
        change_reason="review closed",
        actor_id=curator_id,
        from_state="in_review",
        to_state="draft",
        event_type="state_transition",
    )
    db_session.add(active_draft)
    await db_session.flush()
    record.state = "draft"
    record.revision = 3
    record.editing_revision_id = active_draft.id
    closed_revision = record.revision
    await db_session.commit()
    closed = await async_client.post(
        "/api/v2/comments",
        headers=reviewer_headers,
        json={**payload, "record_revision": closed_revision},
    )
    assert closed.status_code == 409
    assert closed.json()["detail"]["code"] == "review_closed"


@pytest.mark.asyncio
async def test_ordinary_comment_routes_remain_bodyless_and_authorized(
    async_client, curator_headers, admin_headers, published_record
):
    """Legacy ordinary resolve, unresolve, and author/admin delete stay intact."""
    created = await async_client.post(
        "/api/v2/comments",
        headers=curator_headers,
        json={
            "record_type": "phenopacket",
            "record_id": str(published_record.id),
            "body_markdown": "ordinary",
            "mention_user_ids": [],
        },
    )
    assert created.status_code == 201, created.json()
    comment_id = created.json()["id"]
    assert (
        await async_client.post(
            f"/api/v2/comments/{comment_id}/resolve", headers=curator_headers
        )
    ).status_code == 200
    assert (
        await async_client.post(
            f"/api/v2/comments/{comment_id}/unresolve",
            headers=curator_headers,
            json={},
        )
    ).status_code == 200
    assert (
        await async_client.delete(
            f"/api/v2/comments/{comment_id}", headers=admin_headers
        )
    ).status_code == 204
