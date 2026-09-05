"""Exact candidate approval and publication snapshot regression coverage."""

from __future__ import annotations

from copy import deepcopy

import pytest
from sqlalchemy import select

from app.phenopackets.models import (
    ApprovalAttestation,
    PhenopacketCreate,
    PhenopacketRevision,
)
from app.phenopackets.repositories import PhenopacketRepository
from app.phenopackets.services.phenopacket_service import PhenopacketService
from app.phenopackets.services.revision_ledger import (
    build_ledger_v2_payload,
    content_sha256,
    ledger_sha256,
)
from app.phenopackets.services.state_service import PhenopacketStateService


def _attestation() -> ApprovalAttestation:
    """Return the complete affirmative approval attestation."""
    return ApprovalAttestation(
        independent_review=True,
        no_unmanaged_conflict=True,
    )


async def _submit(
    service: PhenopacketStateService,
    record,
    actor,
) -> tuple[object, PhenopacketRevision]:
    """Submit the fixture's active working copy and return its candidate."""
    return await service.transition(
        record.id,
        to_state="in_review",
        reason="freeze exact candidate",
        expected_revision=record.revision,
        actor=actor,
    )


async def _approve(
    service: PhenopacketStateService,
    record,
    candidate: PhenopacketRevision,
    actor,
    *,
    reason: str = "independent review complete",
) -> tuple[object, PhenopacketRevision]:
    """Approve by echoing the exact server-returned candidate identity."""
    assert candidate.content_sha256 is not None
    return await service.transition(
        record.id,
        to_state="approved",
        reason=reason,
        expected_revision=record.revision,
        actor=actor,
        candidate_revision_id=candidate.id,
        candidate_content_sha256=candidate.content_sha256,
        attestation=_attestation(),
    )


async def _publish(
    service: PhenopacketStateService,
    record,
    approved: PhenopacketRevision,
    actor,
) -> tuple[object, PhenopacketRevision]:
    """Publish by echoing the exact server-returned approval identity."""
    assert approved.content_sha256 is not None
    return await service.transition(
        record.id,
        to_state="published",
        reason="publish exact approval",
        expected_revision=record.revision,
        actor=actor,
        approved_revision_id=approved.id,
        approved_content_sha256=approved.content_sha256,
    )


@pytest.mark.asyncio
async def test_submit_freezes_publish_canonical_content_once_and_publish_copies_it(
    db_session,
    draft_record,
    curator_user,
    admin_user,
    monkeypatch,
):
    """Submission canonicalizes once; approval and publication copy exact bytes."""
    calls: list[bool] = []

    def canonicalize(content, *, publish=False):
        calls.append(publish)
        canonical = deepcopy(content)
        canonical["hnf1bCuration"] = {
            **canonical.get("hnf1bCuration", {}),
            "extensionOnlyEvidence": {"status": "frozen"},
        }
        return canonical

    monkeypatch.setattr(
        PhenopacketStateService,
        "_canonicalize_for_persistence",
        staticmethod(canonicalize),
    )
    draft_record.phenopacket = {
        "id": draft_record.phenopacket_id,
        "hnf1bCuration": {"extensionOnlyEvidence": {"status": "draft"}},
    }
    service = PhenopacketStateService(db_session)

    record, candidate = await _submit(service, draft_record, curator_user)

    assert calls == [True]
    assert candidate.content_jsonb["hnf1bCuration"] == {
        "extensionOnlyEvidence": {"status": "frozen"}
    }
    assert candidate.content_sha256 == content_sha256(candidate.content_jsonb)
    assert record.phenopacket == candidate.content_jsonb

    record.phenopacket = deepcopy(candidate.content_jsonb)
    record.phenopacket["hnf1bCuration"]["extensionOnlyEvidence"]["status"] = (
        "unreviewed-working-copy-mutation"
    )
    record, approved = await _approve(service, record, candidate, admin_user)
    record, published = await _publish(service, record, approved, admin_user)
    await db_session.flush()

    assert calls == [True]
    assert approved.content_jsonb == candidate.content_jsonb
    assert approved.content_sha256 == candidate.content_sha256
    assert approved.parent_revision_id == candidate.id
    assert published.content_jsonb == approved.content_jsonb
    assert published.content_sha256 == approved.content_sha256
    assert published.parent_revision_id == approved.id
    assert record.phenopacket == approved.content_jsonb
    assert record.head_published_revision_id == published.id
    assert record.editing_revision_id is None

    public_head = await db_session.get(
        PhenopacketRevision, record.head_published_revision_id
    )
    assert public_head is not None
    assert public_head.id == published.id
    assert public_head.content_jsonb == approved.content_jsonb


@pytest.mark.asyncio
async def test_resubmit_refreezes_once_before_candidate_and_not_during_decisions(
    db_session,
    draft_record,
    curator_user,
    another_curator,
    admin_user,
    monkeypatch,
):
    """Changes-requested resubmission freezes once before the new candidate."""
    service = PhenopacketStateService(db_session)
    record, first_candidate = await _submit(service, draft_record, curator_user)
    record, _ = await service.transition(
        record.id,
        to_state="changes_requested",
        reason="revise extension evidence",
        expected_revision=record.revision,
        actor=another_curator,
    )
    record = await service.edit_record(
        record.id,
        new_content={
            "id": draft_record.phenopacket_id,
            "hnf1bCuration": {"extensionOnlyEvidence": {"status": "revised"}},
        },
        change_reason="address review",
        expected_revision=record.revision,
        actor=curator_user,
    )

    calls: list[bool] = []

    def canonicalize(content, *, publish=False):
        calls.append(publish)
        canonical = deepcopy(content)
        canonical["hnf1bCuration"]["extensionOnlyEvidence"]["status"] = (
            "frozen-resubmission"
        )
        return canonical

    monkeypatch.setattr(
        PhenopacketStateService,
        "_canonicalize_for_persistence",
        staticmethod(canonicalize),
    )

    record, resubmitted = await _submit(service, record, curator_user)

    assert calls == [True]
    assert resubmitted.id != first_candidate.id
    assert resubmitted.content_jsonb["hnf1bCuration"] == {
        "extensionOnlyEvidence": {"status": "frozen-resubmission"}
    }
    assert record.phenopacket == resubmitted.content_jsonb

    record, approved = await _approve(service, record, resubmitted, admin_user)
    record, published = await _publish(service, record, approved, admin_user)

    assert calls == [True]
    assert approved.content_jsonb == resubmitted.content_jsonb
    assert published.content_jsonb == approved.content_jsonb


@pytest.mark.asyncio
@pytest.mark.parametrize("stale_field", ["candidate_revision_id", "digest"])
async def test_approval_rejects_stale_exact_candidate_without_mutation(
    db_session,
    draft_record,
    curator_user,
    admin_user,
    stale_field,
):
    """A stale ID or extension-only digest change cannot approve a candidate."""
    service = PhenopacketStateService(db_session)
    draft_record.phenopacket = {
        "id": draft_record.phenopacket_id,
        "hnf1bCuration": {"extensionOnlyEvidence": {"status": "candidate"}},
    }
    record, candidate = await _submit(service, draft_record, curator_user)
    assert candidate.content_sha256 is not None
    original_pointer = record.editing_revision_id
    original_revision = record.revision
    original_content = deepcopy(record.phenopacket)

    changed_extension = deepcopy(candidate.content_jsonb)
    changed_extension["hnf1bCuration"]["extensionOnlyEvidence"]["status"] = "stale"
    supplied_id = (
        candidate.id + 1 if stale_field == "candidate_revision_id" else candidate.id
    )
    supplied_digest = (
        content_sha256(changed_extension)
        if stale_field == "digest"
        else candidate.content_sha256
    )

    with pytest.raises(PhenopacketStateService.ReviewRevisionMismatch):
        await service.transition(
            record.id,
            to_state="approved",
            reason="stale review",
            expected_revision=record.revision,
            actor=admin_user,
            candidate_revision_id=supplied_id,
            candidate_content_sha256=supplied_digest,
            attestation=_attestation(),
        )

    assert record.editing_revision_id == original_pointer
    assert record.revision == original_revision
    assert record.phenopacket == original_content


@pytest.mark.asyncio
@pytest.mark.parametrize("stale_field", ["approved_revision_id", "digest"])
async def test_publication_rejects_stale_exact_approval_without_head_swap(
    db_session,
    draft_record,
    curator_user,
    admin_user,
    stale_field,
):
    """A stale approval ID or extension-only digest leaves all pointers intact."""
    service = PhenopacketStateService(db_session)
    draft_record.phenopacket = {
        "id": draft_record.phenopacket_id,
        "hnf1bCuration": {"extensionOnlyEvidence": {"status": "approved"}},
    }
    record, candidate = await _submit(service, draft_record, curator_user)
    record, approved = await _approve(service, record, candidate, admin_user)
    assert approved.content_sha256 is not None
    original_pointer = record.editing_revision_id
    original_revision = record.revision
    original_content = deepcopy(record.phenopacket)

    changed_extension = deepcopy(approved.content_jsonb)
    changed_extension["hnf1bCuration"]["extensionOnlyEvidence"]["status"] = "stale"
    supplied_id = (
        approved.id + 1 if stale_field == "approved_revision_id" else approved.id
    )
    supplied_digest = (
        content_sha256(changed_extension)
        if stale_field == "digest"
        else approved.content_sha256
    )

    with pytest.raises(PhenopacketStateService.ReviewRevisionMismatch):
        await service.transition(
            record.id,
            to_state="published",
            reason="stale publish",
            expected_revision=record.revision,
            actor=admin_user,
            approved_revision_id=supplied_id,
            approved_content_sha256=supplied_digest,
        )

    assert record.head_published_revision_id is None
    assert record.editing_revision_id == original_pointer
    assert record.revision == original_revision
    assert record.phenopacket == original_content


@pytest.mark.asyncio
async def test_approval_records_exact_decision_metadata_and_hashes_role_and_metadata(
    db_session,
    draft_record,
    curator_user,
    admin_user,
):
    """The v2 approval ledger binds the exact rationale, attestation, and role."""
    service = PhenopacketStateService(db_session)
    record, candidate = await _submit(service, draft_record, curator_user)
    record, approved = await _approve(
        service,
        record,
        candidate,
        admin_user,
        reason="approved after independent review",
    )

    expected_metadata = {
        "schemaVersion": 1,
        "candidate_revision_id": candidate.id,
        "candidate_content_sha256": candidate.content_sha256,
        "attestation": {
            "independent_review": True,
            "no_unmanaged_conflict": True,
        },
        "rationale": "approved after independent review",
    }
    assert approved.actor_role == "admin"
    assert approved.decision_metadata == expected_metadata
    assert approved.content_sha256 == content_sha256(approved.content_jsonb)
    assert approved.ledger_version == 2

    payload = build_ledger_v2_payload(
        parent_revision_id=approved.parent_revision_id,
        revision_number=approved.revision_number,
        state=approved.state,
        event_type=approved.event_type,
        from_state=approved.from_state,
        to_state=approved.to_state,
        change_reason=approved.change_reason,
        change_patch=approved.change_patch,
        content_sha256=approved.content_sha256,
        projection_hash=approved.projection_hash,
        actor_id=approved.actor_id,
        actor_role=approved.actor_role,
        decision_metadata=expected_metadata,
    )
    assert approved.ledger_hash == ledger_sha256(payload)
    assert approved.ledger_hash != ledger_sha256({**payload, "actor_role": "curator"})
    assert approved.ledger_hash != ledger_sha256(
        {**payload, "decision_metadata": {**expected_metadata, "rationale": "tampered"}}
    )


@pytest.mark.asyncio
async def test_every_new_state_revision_is_v2_while_legacy_head_remains_unchanged(
    db_session,
    published_record,
    curator_user,
    admin_user,
):
    """Draft, review, approval, and publication writes use v2 without backfill."""
    service = PhenopacketStateService(db_session)
    legacy_head_id = published_record.head_published_revision_id
    legacy_head = await db_session.get(PhenopacketRevision, legacy_head_id)
    assert legacy_head is not None
    assert legacy_head.ledger_version is None

    record = await service.edit_record(
        published_record.id,
        new_content={
            **published_record.phenopacket,
            "hnf1bCuration": {"extensionOnlyEvidence": {"status": "draft"}},
        },
        change_reason="create replacement draft",
        expected_revision=published_record.revision,
        actor=curator_user,
    )
    record = await service.edit_record(
        record.id,
        new_content={
            **record.phenopacket,
            "hnf1bCuration": {"extensionOnlyEvidence": {"status": "saved"}},
        },
        change_reason="save replacement draft",
        expected_revision=record.revision,
        actor=curator_user,
    )
    record, candidate = await _submit(service, record, curator_user)
    record, approved = await _approve(service, record, candidate, admin_user)
    record, published = await _publish(service, record, approved, admin_user)
    await db_session.flush()

    rows = list(
        (
            await db_session.execute(
                select(PhenopacketRevision)
                .where(PhenopacketRevision.record_id == record.id)
                .order_by(PhenopacketRevision.revision_number)
            )
        ).scalars()
    )
    assert rows[0].id == legacy_head_id
    assert rows[0].actor_role is None
    assert rows[0].content_sha256 is None
    assert rows[0].ledger_version is None
    for revision in rows[1:]:
        assert revision.actor_role in {"curator", "admin"}
        assert revision.content_sha256 == content_sha256(revision.content_jsonb)
        assert revision.ledger_version == 2
    assert [revision.event_type for revision in rows[1:]] == [
        "draft_created",
        "draft_saved",
        "state_transition",
        "state_transition",
        "published",
    ]
    assert record.head_published_revision_id == published.id


@pytest.mark.asyncio
async def test_initial_creation_records_complete_v2_evidence(
    db_session,
    curator_user,
):
    """The creation-only revision constructor emits the same v2 evidence."""
    service = PhenopacketService(PhenopacketRepository(db_session))
    content = {
        "id": "exact-snapshot-created",
        "subject": {"id": "exact-snapshot-subject", "sex": "FEMALE"},
        "phenotypicFeatures": [{"type": {"id": "HP:0000107", "label": "Renal cyst"}}],
        "metaData": {
            "created": "2026-08-14T00:00:00Z",
            "createdBy": "exact-snapshot-test",
            "phenopacketSchemaVersion": "2.0",
            "resources": [
                {
                    "id": "hp",
                    "name": "Human Phenotype Ontology",
                    "namespacePrefix": "HP",
                    "url": "http://purl.obolibrary.org/obo/hp.owl",
                    "version": "2024-01-01",
                    "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                }
            ],
        },
    }

    record = await service.create(
        PhenopacketCreate(phenopacket=content),
        actor_id=curator_user.id,
    )
    revision = (
        await db_session.execute(
            select(PhenopacketRevision).where(
                PhenopacketRevision.record_id == record.id
            )
        )
    ).scalar_one()

    assert revision.actor_role == "curator"
    assert revision.decision_metadata is None
    assert revision.content_sha256 == content_sha256(revision.content_jsonb)
    assert revision.ledger_version == 2
    payload = build_ledger_v2_payload(
        parent_revision_id=None,
        revision_number=revision.revision_number,
        state="draft",
        event_type="created",
        from_state=None,
        to_state="draft",
        change_reason="Initial creation",
        change_patch=None,
        content_sha256=revision.content_sha256,
        projection_hash=revision.projection_hash,
        actor_id=revision.actor_id,
        actor_role="curator",
        decision_metadata=None,
    )
    assert revision.ledger_hash == ledger_sha256(payload)
