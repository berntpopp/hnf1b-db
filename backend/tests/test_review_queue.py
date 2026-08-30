"""Server-driven review queue integration tests against real database rows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import event

import app.database as app_database
from app.comments.models import Comment
from app.phenopackets.models import Phenopacket, PhenopacketRevision
from app.phenopackets.services.revision_ledger import content_sha256

QUEUE_URL = "/api/v2/phenopackets/review-queue"


async def _headers_for(client, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/v2/auth/login",
        json={"username": username, "password": "CuratorPass123!"},
    )
    assert response.status_code == 200, response.json()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _seed_queue_record(
    db_session: Any,
    *,
    slug: str,
    owner: Any,
    submitter: Any,
    effective_state: str = "in_review",
    published: bool = False,
    submitted_at: datetime | None = None,
) -> tuple[Phenopacket, PhenopacketRevision]:
    """Persist one active cycle with literal old-head and candidate content."""
    baseline = {
        "id": slug,
        "subject": {"id": f"{slug}-old", "label": f"Old {slug}"},
        "metaData": {"createdBy": "fixture"},
    }
    candidate_content = {
        "id": slug,
        "subject": {"id": f"{slug}-subject", "label": f"Label {slug}"},
        "metaData": {"createdBy": "fixture", "extension": slug},
    }
    record = Phenopacket(
        phenopacket_id=slug,
        phenopacket=candidate_content,
        state="draft",
        revision=0,
        draft_owner_id=owner.id,
        created_by_id=owner.id,
    )
    db_session.add(record)
    await db_session.flush()

    revision_number = 0
    parent_id = None
    if published:
        revision_number += 1
        head = PhenopacketRevision(
            record_id=record.id,
            revision_number=revision_number,
            state="published",
            content_jsonb=baseline,
            content_sha256=content_sha256(baseline),
            change_patch=[],
            change_reason="published baseline",
            actor_id=owner.id,
            actor_role=owner.role,
            from_state=None,
            to_state="published",
            event_type="published",
            ledger_version=2,
        )
        db_session.add(head)
        await db_session.flush()
        record.head_published_revision_id = head.id
        record.state = "published"
        parent_id = head.id

        revision_number += 1
        draft = PhenopacketRevision(
            record_id=record.id,
            parent_revision_id=parent_id,
            revision_number=revision_number,
            state="draft",
            content_jsonb=candidate_content,
            content_sha256=content_sha256(candidate_content),
            change_patch=[
                {
                    "op": "replace",
                    "path": "/subject/id",
                    "value": f"{slug}-subject",
                }
            ],
            change_reason="open replacement cycle",
            actor_id=owner.id,
            actor_role=owner.role,
            from_state="published",
            to_state="draft",
            event_type="draft_created",
            ledger_version=2,
        )
        db_session.add(draft)
        await db_session.flush()
        parent_id = draft.id
    else:
        revision_number += 1
        root = PhenopacketRevision(
            record_id=record.id,
            revision_number=revision_number,
            state="draft",
            content_jsonb=candidate_content,
            content_sha256=content_sha256(candidate_content),
            change_patch=[{"op": "add", "path": "/subject", "value": {}}],
            change_reason="create draft",
            actor_id=owner.id,
            actor_role=owner.role,
            from_state=None,
            to_state="draft",
            event_type="created",
            ledger_version=2,
        )
        db_session.add(root)
        await db_session.flush()
        parent_id = root.id

    revision_number += 1
    candidate = PhenopacketRevision(
        record_id=record.id,
        parent_revision_id=parent_id,
        revision_number=revision_number,
        state="in_review",
        content_jsonb=candidate_content,
        content_sha256=content_sha256(candidate_content),
        change_patch=[{"op": "replace", "path": "/metaData/extension", "value": slug}],
        change_reason="submit exact candidate",
        actor_id=submitter.id,
        actor_role=submitter.role,
        from_state="draft",
        to_state="in_review",
        event_type="state_transition",
        ledger_version=2,
        created_at=submitted_at,
    )
    db_session.add(candidate)
    await db_session.flush()
    active = candidate

    if effective_state != "in_review":
        revision_number += 1
        active = PhenopacketRevision(
            record_id=record.id,
            parent_revision_id=candidate.id,
            revision_number=revision_number,
            state=effective_state,
            content_jsonb=candidate_content,
            content_sha256=content_sha256(candidate_content),
            change_patch=[],
            change_reason=f"move to {effective_state}",
            actor_id=submitter.id,
            actor_role=submitter.role,
            from_state="in_review",
            to_state=effective_state,
            event_type="state_transition",
            ledger_version=2,
        )
        db_session.add(active)
        await db_session.flush()

    record.revision = revision_number
    record.editing_revision_id = active.id
    if not published:
        record.state = effective_state
    await db_session.flush()
    return record, candidate


@pytest.mark.asyncio
async def test_review_queue_non_disclosure_and_strict_optional_auth(
    async_client, viewer_headers
):
    """Anonymous/viewer discovery is 404 while a supplied bad token stays 401."""
    anonymous = await async_client.get(QUEUE_URL)
    viewer = await async_client.get(QUEUE_URL, headers=viewer_headers)
    invalid = await async_client.get(
        QUEUE_URL, headers={"Authorization": "Bearer definitely-not-a-token"}
    )

    assert anonymous.status_code == 404
    assert viewer.status_code == 404
    assert invalid.status_code == 401


@pytest.mark.asyncio
async def test_queue_projects_physical_and_effective_state_with_literal_row_contract(
    async_client,
    db_session,
    curator_user,
    another_curator,
):
    """A published replacement is filtered by effective in-review state."""
    submitted_at = datetime(2026, 8, 12, 10, 30, tzinfo=timezone.utc)
    record, candidate = await _seed_queue_record(
        db_session,
        slug="replacement-case",
        owner=curator_user,
        submitter=curator_user,
        published=True,
        submitted_at=submitted_at,
    )
    await db_session.commit()
    headers = await _headers_for(async_client, another_curator.username)

    response = await async_client.get(
        f"{QUEUE_URL}?filter[state]=in_review&page[number]=1&page[size]=10",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "data": [
            {
                "record_id": str(record.id),
                "phenopacket_id": "replacement-case",
                "subject_label": "Label replacement-case",
                "physical_state": "published",
                "effective_state": "in_review",
                "owner": {
                    "id": curator_user.id,
                    "username": curator_user.username,
                    "display_name": curator_user.full_name,
                },
                "submitted_by": {
                    "id": curator_user.id,
                    "username": curator_user.username,
                    "display_name": curator_user.full_name,
                },
                "submitted_at": submitted_at.isoformat().replace("+00:00", "Z"),
                "record_revision": record.revision,
                "candidate_revision_id": candidate.id,
                "candidate_content_sha256": candidate.content_sha256,
                "approved_revision_id": None,
                "approved_content_sha256": None,
                "active_cycle_change_count": 2,
                "open_issue_count": 0,
                "has_published_head": True,
                "capabilities": [
                    {"action": "request_changes", "allowed": True, "blocked_by": []},
                    {"action": "approve", "allowed": True, "blocked_by": []},
                ],
            }
        ],
        "meta": {
            "page_number": 1,
            "page_size": 10,
            "total": 1,
            "total_pages": 1,
            "state_counts": {
                "draft": 0,
                "in_review": 1,
                "changes_requested": 0,
                "approved": 0,
            },
        },
    }

    public = await async_client.get(f"/api/v2/phenopackets/{record.phenopacket_id}")
    assert public.status_code == 200
    assert public.json()["phenopacket"]["subject"]["id"] == "replacement-case-old"


@pytest.mark.asyncio
async def test_queue_default_order_filters_search_facets_and_disabled_own_row(
    async_client,
    db_session,
    curator_user,
    another_curator,
):
    """All filters are server-side and state facets omit only the state filter."""
    now = datetime(2026, 8, 13, 12, tzinfo=timezone.utc)
    old_record, old_candidate = await _seed_queue_record(
        db_session,
        slug="renal-alpha",
        owner=curator_user,
        submitter=curator_user,
        submitted_at=now - timedelta(days=2),
    )
    await _seed_queue_record(
        db_session,
        slug="renal-beta",
        owner=another_curator,
        submitter=another_curator,
        submitted_at=now - timedelta(days=1),
    )
    await _seed_queue_record(
        db_session,
        slug="renal-returned",
        owner=curator_user,
        submitter=curator_user,
        effective_state="changes_requested",
        submitted_at=now,
    )
    db_session.add(
        Comment(
            record_type="phenopacket",
            record_id=old_record.id,
            author_id=another_curator.id,
            body_markdown="Open current-cycle concern",
            review_revision_id=old_candidate.id,
        )
    )
    await db_session.commit()
    headers = await _headers_for(async_client, another_curator.username)

    default = await async_client.get(
        f"{QUEUE_URL}?filter[state]=in_review&q=renal&page[size]=10",
        headers=headers,
    )
    assert default.status_code == 200, default.text
    assert [row["phenopacket_id"] for row in default.json()["data"]] == [
        "renal-alpha",
        "renal-beta",
    ]
    assert default.json()["meta"]["state_counts"] == {
        "draft": 0,
        "in_review": 2,
        "changes_requested": 1,
        "approved": 0,
    }

    with_issues = await async_client.get(
        f"{QUEUE_URL}?filter[issues]=open&q=alpha",
        headers=headers,
    )
    assert [row["phenopacket_id"] for row in with_issues.json()["data"]] == [
        "renal-alpha"
    ]
    assert with_issues.json()["data"][0]["open_issue_count"] == 1

    eligible = await async_client.get(
        f"{QUEUE_URL}?filter[eligibility]=reviewable_by_me&filter[state]=in_review",
        headers=headers,
    )
    assert [row["phenopacket_id"] for row in eligible.json()["data"]] == ["renal-alpha"]

    mine = await async_client.get(
        f"{QUEUE_URL}?filter[owner]=mine&filter[state]=in_review",
        headers=headers,
    )
    assert [row["phenopacket_id"] for row in mine.json()["data"]] == ["renal-beta"]
    blockers = mine.json()["data"][0]["capabilities"][0]["blocked_by"]
    assert blockers == [
        "self_review_forbidden",
        "reviewer_submitted",
        "reviewer_contributed",
    ]


@pytest.mark.asyncio
async def test_queue_numeric_owner_sort_and_admin_publish_capability(
    async_client,
    db_session,
    curator_user,
    admin_headers,
):
    """Numeric owner filtering, allowlisted sorting, and publish stay server-side."""
    await _seed_queue_record(
        db_session,
        slug="approved-alpha",
        owner=curator_user,
        submitter=curator_user,
        effective_state="approved",
    )
    await _seed_queue_record(
        db_session,
        slug="approved-zeta",
        owner=curator_user,
        submitter=curator_user,
        effective_state="approved",
    )
    await db_session.commit()

    response = await async_client.get(
        (
            f"{QUEUE_URL}?filter[state]=approved"
            f"&filter[owner]={curator_user.id}&sort=-phenopacket_id"
        ),
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert [row["phenopacket_id"] for row in response.json()["data"]] == [
        "approved-zeta",
        "approved-alpha",
    ]
    assert all(row["effective_state"] == "approved" for row in response.json()["data"])
    assert response.json()["data"][0]["capabilities"] == [
        {"action": "request_changes", "allowed": True, "blocked_by": []},
        {"action": "publish", "allowed": True, "blocked_by": []},
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "sort=clinical_secret",
        "filter[state]=published",
        "filter[owner]=nobody",
        "filter[eligibility]=sometimes",
        "filter[issues]=maybe",
    ],
)
async def test_queue_rejects_non_allowlisted_query_values(
    async_client, curator_headers, query
):
    """Unknown sort/filter values fail before any broad query can run."""
    response = await async_client.get(f"{QUEUE_URL}?{query}", headers=curator_headers)
    assert response.status_code in {400, 422}


@pytest.mark.asyncio
async def test_queue_select_count_is_independent_of_returned_row_count(
    async_client,
    db_session,
    curator_user,
    another_curator,
):
    """The page does not invoke policy or relationship SELECTs per row."""
    for index in range(4):
        await _seed_queue_record(
            db_session,
            slug=f"bounded-{index}",
            owner=curator_user,
            submitter=curator_user,
        )
    await db_session.commit()
    headers = await _headers_for(async_client, another_curator.username)
    statements: list[str] = []

    def count_selects(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(app_database.engine.sync_engine, "after_cursor_execute", count_selects)
    try:
        one = await async_client.get(
            f"{QUEUE_URL}?page[number]=1&page[size]=1", headers=headers
        )
        one_count = len(statements)
        statements.clear()
        full = await async_client.get(
            f"{QUEUE_URL}?page[number]=1&page[size]=10", headers=headers
        )
        full_count = len(statements)
    finally:
        event.remove(
            app_database.engine.sync_engine, "after_cursor_execute", count_selects
        )

    assert one.status_code == 200, one.text
    assert full.status_code == 200, full.text
    assert len(one.json()["data"]) == 1
    assert len(full.json()["data"]) == 4
    assert one_count == full_count
    assert full_count <= 4
