"""Append-only revision regression coverage for source-faithful curation."""

import pytest
from sqlalchemy import select

from app.phenopackets.models import PhenopacketRevision
from app.phenopackets.services.state_service import PhenopacketStateService


@pytest.mark.asyncio
async def test_draft_save_appends_without_mutating_prior_revision(
    db_session, published_record, curator_user
):
    """A second draft save preserves the first draft's bytes and appends N+1."""
    service = PhenopacketStateService(db_session)
    record = await service.edit_record(
        published_record.id,
        new_content={"id": published_record.phenopacket_id, "stage": "first"},
        change_reason="start curation",
        expected_revision=published_record.revision,
        actor=curator_user,
    )
    first_draft_id = record.editing_revision_id
    assert first_draft_id is not None

    record = await service.edit_record(
        record.id,
        new_content={"id": published_record.phenopacket_id, "stage": "second"},
        change_reason="continue curation",
        expected_revision=record.revision,
        actor=curator_user,
    )

    revisions = list(
        (
            await db_session.execute(
                select(PhenopacketRevision)
                .where(PhenopacketRevision.record_id == record.id)
                .order_by(PhenopacketRevision.revision_number)
            )
        ).scalars()
    )
    first_draft = next(
        revision for revision in revisions if revision.id == first_draft_id
    )
    assert first_draft.content_jsonb["stage"] == "first"
    assert record.editing_revision_id != first_draft_id
    assert [revision.revision_number for revision in revisions] == [1, 2, 3]


@pytest.mark.asyncio
async def test_publish_appends_a_new_head_without_rewriting_approved_revision(
    db_session, published_record, curator_user, admin_user
):
    """Publishing creates a distinct immutable head row and swaps only the pointer."""
    service = PhenopacketStateService(db_session)
    original_head_id = published_record.head_published_revision_id
    record = await service.edit_record(
        published_record.id,
        new_content={"id": published_record.phenopacket_id, "stage": "draft"},
        change_reason="edit",
        expected_revision=published_record.revision,
        actor=curator_user,
    )
    record, _ = await service.transition(
        record.id,
        to_state="in_review",
        reason="review",
        expected_revision=record.revision,
        actor=curator_user,
    )
    record, approved = await service.transition(
        record.id,
        to_state="approved",
        reason="approve",
        expected_revision=record.revision,
        actor=admin_user,
    )
    approved_id = approved.id
    record, published = await service.transition(
        record.id,
        to_state="published",
        reason="publish",
        expected_revision=record.revision,
        actor=admin_user,
    )

    reloaded_approved = (
        await db_session.execute(
            select(PhenopacketRevision).where(PhenopacketRevision.id == approved_id)
        )
    ).scalar_one()
    assert published.id != approved_id
    assert record.head_published_revision_id == published.id
    assert record.head_published_revision_id != original_head_id
    assert reloaded_approved.state == "approved"
    assert reloaded_approved.to_state == "approved"


@pytest.mark.asyncio
async def test_update_requires_revision_or_if_match(
    async_client, curator_headers, draft_record
):
    """Writes reject missing optimistic-lock preconditions with HTTP 428."""
    response = await async_client.put(
        f"/api/v2/phenopackets/{draft_record.phenopacket_id}",
        json={
            "phenopacket": {
                "id": draft_record.phenopacket_id,
                "subject": {"id": draft_record.phenopacket_id, "sex": "FEMALE"},
                "metaData": {
                    "created": "2026-08-09T00:00:00Z",
                    "createdBy": "test",
                    "resources": [{"id": "hp", "name": "HPO", "namespacePrefix": "HP"}],
                },
            },
            "change_reason": "test mandatory precondition",
        },
        headers=curator_headers,
    )

    assert response.status_code == 428
    assert response.json()["detail"]["code"] == "precondition_required"
