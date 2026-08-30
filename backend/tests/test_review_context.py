"""Coherent server review-context and semantic comparison tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.comments.models import Comment, CommentResolutionEvent
from app.database import async_session_maker
from app.phenopackets.models import Phenopacket, PhenopacketRevision
from app.phenopackets.review.repository import ReviewRepository
from app.phenopackets.review.service import ReviewService
from tests.test_review_queue import _headers_for, _seed_queue_record


def test_semantic_changes_are_sectioned_literal_and_identity_aware() -> None:
    """Nested/object/array/extension changes use deterministic semantic entries."""
    baseline = {
        "id": "case-1",
        "subject": {"id": "S1", "sex": "UNKNOWN_SEX"},
        "phenotypicFeatures": [
            {"type": {"id": "HP:1", "label": "Old label"}},
            {"type": {"id": "HP:2", "label": "Removed"}},
        ],
        "diseases": [{"term": {"id": "MONDO:1", "label": "Disease"}}],
        "measurements": [{"id": "m1", "value": {"quantity": {"value": 1}}}],
        "metaData": {"createdBy": "curator-a"},
        "unknownExtension": {"nested": ["old", "removed"]},
    }
    candidate = {
        "id": "case-1",
        "subject": {"id": "S1", "sex": "FEMALE"},
        "phenotypicFeatures": [
            {"type": {"id": "HP:1", "label": "New label"}},
            {"type": {"id": "HP:3", "label": "Added"}},
        ],
        "interpretations": [{"id": "i1", "progressStatus": "SOLVED"}],
        "measurements": [{"id": "m1", "value": {"quantity": {"value": 2}}}],
        "metaData": {"createdBy": "curator-b"},
        "unknownExtension": {"nested": ["old", "added"]},
    }

    changes = [
        item.model_dump(mode="json")
        for item in ReviewService.semantic_changes(baseline, candidate)
    ]

    assert changes == [
        {
            "section": "Subject",
            "operation": "changed",
            "path": "/subject/sex",
            "before": "UNKNOWN_SEX",
            "after": "FEMALE",
        },
        {
            "section": "Phenotypes",
            "operation": "changed",
            "path": "/phenotypicFeatures/0/type/label",
            "before": "Old label",
            "after": "New label",
        },
        {
            "section": "Phenotypes",
            "operation": "removed",
            "path": "/phenotypicFeatures/1",
            "before": {"type": {"id": "HP:2", "label": "Removed"}},
            "after": None,
        },
        {
            "section": "Phenotypes",
            "operation": "added",
            "path": "/phenotypicFeatures/1",
            "before": None,
            "after": {"type": {"id": "HP:3", "label": "Added"}},
        },
        {
            "section": "Diseases",
            "operation": "removed",
            "path": "/diseases/0",
            "before": {"term": {"id": "MONDO:1", "label": "Disease"}},
            "after": None,
        },
        {
            "section": "Variants/Interpretations",
            "operation": "added",
            "path": "/interpretations/0",
            "before": None,
            "after": {"id": "i1", "progressStatus": "SOLVED"},
        },
        {
            "section": "Measurements",
            "operation": "changed",
            "path": "/measurements/0/value/quantity/value",
            "before": 1,
            "after": 2,
        },
        {
            "section": "Metadata",
            "operation": "changed",
            "path": "/metaData/createdBy",
            "before": "curator-a",
            "after": "curator-b",
        },
        {
            "section": "Metadata",
            "operation": "changed",
            "path": "/unknownExtension/nested/1",
            "before": "removed",
            "after": "added",
        },
    ]


def test_new_record_semantic_changes_are_candidate_values_added() -> None:
    """A missing immutable public baseline never becomes a fake empty document."""
    candidate = {
        "id": "new-case",
        "subject": {"id": "new-subject"},
        "phenotypicFeatures": [{"type": {"id": "HP:1"}}],
        "customExtension": {"preserved": True},
    }

    changes = [
        item.model_dump(mode="json")
        for item in ReviewService.semantic_changes(None, candidate)
    ]

    assert changes == [
        {
            "section": "Subject",
            "operation": "added",
            "path": "/subject",
            "before": None,
            "after": {"id": "new-subject"},
        },
        {
            "section": "Phenotypes",
            "operation": "added",
            "path": "/phenotypicFeatures",
            "before": None,
            "after": [{"type": {"id": "HP:1"}}],
        },
        {
            "section": "Metadata",
            "operation": "added",
            "path": "/customExtension",
            "before": None,
            "after": {"preserved": True},
        },
        {
            "section": "Metadata",
            "operation": "added",
            "path": "/id",
            "before": None,
            "after": "new-case",
        },
    ]


@pytest.mark.asyncio
async def test_review_context_non_disclosure_and_strict_optional_auth(
    async_client, viewer_headers
):
    """Private context has the same anonymous/viewer/bad-token boundary as queue."""
    url = "/api/v2/phenopackets/not-present/review-context"
    assert (await async_client.get(url)).status_code == 404
    assert (await async_client.get(url, headers=viewer_headers)).status_code == 404
    invalid = await async_client.get(
        url, headers={"Authorization": "Bearer invalid-review-token"}
    )
    assert invalid.status_code == 401


@pytest.mark.asyncio
async def test_context_uses_only_immutable_public_head_and_exposes_exact_candidate(
    async_client,
    db_session,
    curator_user,
    another_curator,
):
    """The mutable working copy cannot replace the immutable baseline."""
    submitted_at = datetime(2026, 8, 13, 9, tzinfo=timezone.utc)
    record, candidate = await _seed_queue_record(
        db_session,
        slug="context-replacement",
        owner=curator_user,
        submitter=curator_user,
        published=True,
        submitted_at=submitted_at,
    )
    await db_session.commit()
    headers = await _headers_for(async_client, another_curator.username)

    response = await async_client.get(
        f"/api/v2/phenopackets/{record.phenopacket_id}/review-context",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["record_id"] == str(record.id)
    assert body["phenopacket_id"] == "context-replacement"
    assert body["physical_state"] == "published"
    assert body["effective_state"] == "in_review"
    assert body["record_revision"] == record.revision
    assert body["candidate"] == {
        "id": candidate.id,
        "revision_number": candidate.revision_number,
        "state": "in_review",
        "content_sha256": candidate.content_sha256,
        "created_at": submitted_at.isoformat().replace("+00:00", "Z"),
        "actor": {
            "id": curator_user.id,
            "username": curator_user.username,
            "display_name": curator_user.full_name,
        },
        "actor_role": curator_user.role,
        "actor_role_at_decision_recorded": True,
        "content": candidate.content_jsonb,
    }
    assert body["baseline"]["id"] == record.head_published_revision_id
    assert body["baseline"]["content"]["subject"]["id"] == "context-replacement-old"
    assert body["baseline"]["content"] != record.phenopacket
    assert body["approved"] is None
    assert body["has_published_head"] is True
    assert body["audit"]["submission"]["id"] == candidate.id
    assert body["audit"]["publication"]["id"] == record.head_published_revision_id
    assert body["audit"]["approval"] is None
    assert body["capabilities"] == [
        {"action": "create_issue", "allowed": True, "blocked_by": []},
        {"action": "request_changes", "allowed": True, "blocked_by": []},
        {"action": "approve", "allowed": True, "blocked_by": []},
    ]
    assert any(
        item
        == {
            "section": "Subject",
            "operation": "changed",
            "path": "/subject/id",
            "before": "context-replacement-old",
            "after": "context-replacement-subject",
        }
        for item in body["semantic_changes"]
    )


@pytest.mark.asyncio
async def test_context_new_record_has_no_baseline_and_owner_blockers(
    async_client, db_session, curator_user
):
    """Owners can inspect their own row but review/create actions fail closed."""
    record, candidate = await _seed_queue_record(
        db_session,
        slug="new-context",
        owner=curator_user,
        submitter=curator_user,
    )
    await db_session.commit()

    response = await async_client.get(
        f"/api/v2/phenopackets/{record.phenopacket_id}/review-context",
        headers=(await _headers_for(async_client, curator_user.username)),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["baseline"] is None
    assert body["candidate"]["id"] == candidate.id
    assert body["semantic_changes"]
    assert {change["operation"] for change in body["semantic_changes"]} == {"added"}
    assert body["capabilities"][0] == {
        "action": "create_issue",
        "allowed": False,
        "blocked_by": [
            "self_review_forbidden",
            "reviewer_submitted",
            "reviewer_contributed",
        ],
    }
    assert body["capabilities"][-1] == {
        "action": "withdraw",
        "allowed": True,
        "blocked_by": [],
    }


@pytest.mark.asyncio
async def test_context_withdraw_capability_is_owner_or_admin_only(
    async_client,
    db_session,
    curator_user,
    another_curator,
    admin_headers,
):
    """Context capabilities preserve the same owner/admin withdrawal authority."""
    record, _candidate = await _seed_queue_record(
        db_session,
        slug="withdraw-context",
        owner=curator_user,
        submitter=curator_user,
    )
    await db_session.commit()
    url = f"/api/v2/phenopackets/{record.phenopacket_id}/review-context"

    owner = await async_client.get(
        url, headers=(await _headers_for(async_client, curator_user.username))
    )
    reviewer = await async_client.get(
        url, headers=(await _headers_for(async_client, another_curator.username))
    )
    admin = await async_client.get(url, headers=admin_headers)

    assert owner.status_code == 200, owner.text
    assert reviewer.status_code == 200, reviewer.text
    assert admin.status_code == 200, admin.text
    owner_actions = owner.json()["capabilities"]
    reviewer_actions = reviewer.json()["capabilities"]
    admin_actions = admin.json()["capabilities"]
    assert owner_actions[-1] == {
        "action": "withdraw",
        "allowed": True,
        "blocked_by": [],
    }
    assert all(item["action"] != "withdraw" for item in reviewer_actions)
    assert admin_actions[-1] == {
        "action": "withdraw",
        "allowed": True,
        "blocked_by": [],
    }


@pytest.mark.asyncio
async def test_context_projects_recorded_and_historical_actor_roles_without_inference(
    async_client,
    db_session,
    curator_user,
    another_curator,
):
    """Stored decision roles survive while historical nulls stay explicitly unknown."""
    record, candidate = await _seed_queue_record(
        db_session,
        slug="actor-role-audit",
        owner=curator_user,
        submitter=curator_user,
        effective_state="approved",
        published=True,
        historical_publication_role_missing=True,
    )
    baseline = await db_session.get(
        PhenopacketRevision, record.head_published_revision_id
    )
    assert baseline is not None
    await db_session.commit()

    response = await async_client.get(
        f"/api/v2/phenopackets/{record.phenopacket_id}/review-context",
        headers=(await _headers_for(async_client, another_curator.username)),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["candidate"]["id"] == candidate.id
    assert body["candidate"]["actor_role"] == curator_user.role
    assert body["candidate"]["actor_role_at_decision_recorded"] is True
    assert body["approved"]["actor_role"] == curator_user.role
    assert body["approved"]["actor_role_at_decision_recorded"] is True
    assert body["audit"]["submission"]["actor_role"] == curator_user.role
    assert body["audit"]["submission"]["actor_role_at_decision_recorded"] is True
    assert body["audit"]["approval"]["actor_role"] == curator_user.role
    assert body["audit"]["approval"]["actor_role_at_decision_recorded"] is True
    assert body["baseline"]["actor_role"] is None
    assert body["baseline"]["actor_role_at_decision_recorded"] is False
    assert body["audit"]["publication"]["actor_role"] is None
    assert body["audit"]["publication"]["actor_role_at_decision_recorded"] is False


@pytest.mark.asyncio
async def test_context_issues_are_unresolved_first_with_events_and_capabilities(
    async_client,
    db_session,
    curator_user,
    another_curator,
):
    """Issue history is append-only, bulk-loaded, and never offers deletion."""
    record, candidate = await _seed_queue_record(
        db_session,
        slug="context-issues",
        owner=curator_user,
        submitter=curator_user,
    )
    open_issue = Comment(
        record_type="phenopacket",
        record_id=record.id,
        author_id=another_curator.id,
        body_markdown="Still open",
        review_revision_id=candidate.id,
    )
    resolved_issue = Comment(
        record_type="phenopacket",
        record_id=record.id,
        author_id=another_curator.id,
        body_markdown="Already handled",
        review_revision_id=candidate.id,
    )
    ordinary = Comment(
        record_type="phenopacket",
        record_id=record.id,
        author_id=curator_user.id,
        body_markdown="Ordinary discussion",
    )
    db_session.add_all([resolved_issue, open_issue, ordinary])
    await db_session.flush()
    db_session.add(
        CommentResolutionEvent(
            comment_id=resolved_issue.id,
            action="resolved",
            disposition="addressed",
            rationale="Verified in candidate",
            actor_id=another_curator.id,
            actor_role=another_curator.role,
            created_at=datetime(2026, 8, 13, 10, tzinfo=timezone.utc),
        )
    )
    await db_session.commit()
    headers = await _headers_for(async_client, another_curator.username)

    response = await async_client.get(
        f"/api/v2/phenopackets/{record.phenopacket_id}/review-context",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert [issue["id"] for issue in body["issues"]] == [
        open_issue.id,
        resolved_issue.id,
    ]
    assert body["issues"][0]["capabilities"] == [
        {"action": "resolve", "allowed": True, "blocked_by": []}
    ]
    assert body["issues"][1]["capabilities"] == [
        {"action": "reopen", "allowed": True, "blocked_by": []}
    ]
    assert all(
        capability["action"] != "delete"
        for issue in body["issues"]
        for capability in issue["capabilities"]
    )
    assert body["issues"][1]["resolution_events"][0]["rationale"] == (
        "Verified in candidate"
    )
    assert body["discussion_summary"] == {
        "total_comments": 3,
        "ordinary_comments": 1,
        "blocking_issues": 2,
        "open_blocking_issues": 1,
    }
    approve = next(item for item in body["capabilities"] if item["action"] == "approve")
    assert approve == {
        "action": "approve",
        "allowed": False,
        "blocked_by": ["unresolved_review_issues"],
    }


@pytest.mark.asyncio
async def test_context_read_holds_share_lock_until_transaction_end(
    db_session, curator_user, another_curator
):
    """A Task-5 writer cannot interleave after context selects its record."""
    record, _candidate = await _seed_queue_record(
        db_session,
        slug="coherent-lock",
        owner=curator_user,
        submitter=curator_user,
    )
    record_id = record.id
    await db_session.commit()

    context = await ReviewRepository(db_session).get_context(
        str(record_id), another_curator
    )
    assert context is not None

    async with async_session_maker() as writer:
        with pytest.raises(DBAPIError):
            await writer.execute(
                select(Phenopacket)
                .where(Phenopacket.id == record_id)
                .with_for_update(nowait=True)
            )
        await writer.rollback()
