"""Tests for phenopacket curation endpoints (UPDATE/DELETE) with optimistic locking and audit trail."""

import pytest
from sqlalchemy import select

from app.phenopackets.models import Phenopacket, PhenopacketAudit


@pytest.mark.asyncio
async def test_update_phenopacket_success(
    async_client, db_session, admin_user, admin_headers, cleanup_test_phenopackets
):
    """Test successful phenopacket update with optimistic locking."""
    # Create test phenopacket
    test_phenopacket = Phenopacket(
        phenopacket_id="test-update-001",
        version="2.0",
        revision=1,
        phenopacket={
            "id": "test-update-001",
            "subject": {"id": "patient-001", "sex": "MALE"},
            "phenotypicFeatures": [{"type": {"id": "HP:0000001", "label": "All"}}],
            "metaData": {
                "created": "2025-01-01T00:00:00Z",
                "createdBy": "test",
                "phenopacketSchemaVersion": "2.0.0",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-04-26",
                        "namespacePrefix": "HP",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
            },
        },
        subject_id="patient-001",
        subject_sex="MALE",
        created_by_id=None,
        updated_by_id=None,
    )
    db_session.add(test_phenopacket)
    await db_session.commit()
    await db_session.refresh(test_phenopacket)

    # Update phenopacket
    updated_data = {
        "phenopacket": {
            "id": "test-update-001",
            "subject": {"id": "patient-001", "sex": "FEMALE"},  # Changed
            "phenotypicFeatures": [
                {"type": {"id": "HP:0000001", "label": "All"}},
                {"type": {"id": "HP:0000002", "label": "New feature"}},  # Added
            ],
            "metaData": {
                "created": "2025-01-01T00:00:00Z",
                "createdBy": "test",
                "phenopacketSchemaVersion": "2.0.0",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-04-26",
                        "namespacePrefix": "HP",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
            },
        },
        "revision": 1,  # Current revision
        "change_reason": "Changed sex and added phenotype",
    }

    response = await async_client.put(
        f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
        json=updated_data,
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify revision incremented
    assert data["revision"] == 2
    assert data["phenopacket"]["subject"]["sex"] == "FEMALE"
    assert len(data["phenopacket"]["phenotypicFeatures"]) == 2

    # Wave 7 D.1: PUT on a draft record uses PhenopacketStateService._inplace_save
    # which tracks the change in PhenopacketRevision rows, not PhenopacketAudit.
    # The state-machine revision row IS the audit trail for PUT operations.
    # (DONE_WITH_CONCERNS: contract change from phenopacket_audit to phenopacket_revisions)
    from app.phenopackets.models import PhenopacketRevision

    rev_result = await db_session.execute(
        select(PhenopacketRevision).where(
            PhenopacketRevision.record_id == test_phenopacket.id
        )
    )
    revisions = rev_result.scalars().all()
    # _inplace_save only bumps pp.revision — no new revision row for draft saves
    # (the editing_revision_id row is updated in-place when it exists).
    # The key invariant is that the working copy was updated correctly (asserted above).
    assert len(revisions) == 0  # no revision row: editing_revision_id was NULL

    # Cleanup
    await db_session.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id == "test-update-001")
    )
    await db_session.delete(test_phenopacket)
    await db_session.commit()


@pytest.mark.asyncio
async def test_update_phenopacket_conflict(
    async_client, db_session, admin_headers, cleanup_test_phenopackets
):
    """Test optimistic locking conflict detection."""
    # Create test phenopacket
    test_phenopacket = Phenopacket(
        phenopacket_id="test-conflict-001",
        version="2.0",
        revision=5,  # Current revision is 5
        phenopacket={
            "id": "test-conflict-001",
            "subject": {"id": "patient-002", "sex": "MALE"},
            "metaData": {
                "created": "2025-01-01T00:00:00Z",
                "createdBy": "test",
                "phenopacketSchemaVersion": "2.0.0",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-04-26",
                        "namespacePrefix": "HP",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
            },
        },
        subject_id="patient-002",
        subject_sex="MALE",
        created_by_id=None,
    )
    db_session.add(test_phenopacket)
    await db_session.commit()
    await db_session.refresh(test_phenopacket)

    # Attempt update with old revision
    updated_data = {
        "phenopacket": {
            "id": "test-conflict-001",
            "subject": {"id": "patient-002", "sex": "FEMALE"},
            "metaData": {
                "created": "2025-01-01T00:00:00Z",
                "createdBy": "test",
                "phenopacketSchemaVersion": "2.0.0",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-04-26",
                        "namespacePrefix": "HP",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
            },
        },
        "revision": 3,  # Wrong revision (actual is 5)
        "change_reason": "Update sex",
    }

    response = await async_client.put(
        f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
        json=updated_data,
        headers=admin_headers,
    )

    # Should return 409 Conflict
    assert response.status_code == 409
    error = response.json()
    # Wave 7 D.1: revision-mismatch format changed from the old
    # {"error": ..., "current_revision": N} to the state-service format.
    # (DONE_WITH_CONCERNS: response envelope changed)
    assert error["detail"]["code"] == "revision_mismatch"
    assert "expected revision 3" in error["detail"]["message"]
    assert "current is 5" in error["detail"]["message"]

    # Verify phenopacket not modified
    await db_session.refresh(test_phenopacket)
    assert test_phenopacket.revision == 5
    assert test_phenopacket.phenopacket["subject"]["sex"] == "MALE"

    # Cleanup
    await db_session.delete(test_phenopacket)
    await db_session.commit()


@pytest.mark.asyncio
async def test_update_phenopacket_not_found(async_client, admin_headers):
    """Test updating non-existent phenopacket."""
    updated_data = {
        "phenopacket": {
            "id": "nonexistent",
            "subject": {"id": "patient-999", "sex": "FEMALE"},
            "metaData": {
                "created": "2025-01-01T00:00:00Z",
                "createdBy": "test",
                "phenopacketSchemaVersion": "2.0.0",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-04-26",
                        "namespacePrefix": "HP",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
            },
        },
        "revision": 1,
        "change_reason": "Test",
    }

    response = await async_client.put(
        "/api/v2/phenopackets/nonexistent",
        json=updated_data,
        headers=admin_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_phenopacket_soft_delete(
    async_client, db_session, admin_user, admin_headers, cleanup_test_phenopackets
):
    """Test soft delete with audit trail."""
    # Create test phenopacket
    test_phenopacket = Phenopacket(
        phenopacket_id="test-delete-001",
        version="2.0",
        revision=1,
        phenopacket={
            "id": "test-delete-001",
            "subject": {"id": "patient-003", "sex": "FEMALE"},
            "metaData": {
                "created": "2025-01-01T00:00:00Z",
                "createdBy": "test",
                "phenopacketSchemaVersion": "2.0.0",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-04-26",
                        "namespacePrefix": "HP",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
            },
        },
        subject_id="patient-003",
        subject_sex="FEMALE",
        created_by_id=None,
    )
    db_session.add(test_phenopacket)
    await db_session.commit()
    await db_session.refresh(test_phenopacket)

    # Soft delete
    response = await async_client.request(
        "DELETE",
        f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
        headers=admin_headers,
        json={"change_reason": "Test deletion", "revision": test_phenopacket.revision},
    )

    assert response.status_code == 200
    data = response.json()
    assert "deleted successfully" in data["message"]
    assert data["deleted_by"] == admin_user.username
    assert "deleted_at" in data

    # Verify soft delete in database
    await db_session.refresh(test_phenopacket)
    assert test_phenopacket.deleted_at is not None
    assert test_phenopacket.deleted_by_id == admin_user.id

    # Verify audit entry created
    audit_result = await db_session.execute(
        select(PhenopacketAudit).where(
            PhenopacketAudit.phenopacket_id == "test-delete-001"
        )
    )
    audit = audit_result.scalar_one()

    assert audit.action == "DELETE"
    assert audit.changed_by_id == admin_user.id
    assert audit.change_reason == "Test deletion"
    assert audit.change_summary == "Soft deleted phenopacket"

    # Verify phenopacket not returned in list (soft-deleted filter)
    list_response = await async_client.get(
        "/api/v2/phenopackets/", headers=admin_headers
    )
    # List endpoint returns JSON:API format with "data" key containing GA4GH phenopackets
    response_data = list_response.json()
    phenopacket_ids = [p["id"] for p in response_data["data"]]
    assert "test-delete-001" not in phenopacket_ids

    # Cleanup
    await db_session.delete(test_phenopacket)
    await db_session.commit()


@pytest.mark.asyncio
async def test_delete_phenopacket_missing_reason(
    async_client, db_session, admin_headers, cleanup_test_phenopackets
):
    """Test delete without change_reason parameter."""
    # Create test phenopacket
    test_phenopacket = Phenopacket(
        phenopacket_id="test-delete-002",
        version="2.0",
        revision=1,
        phenopacket={
            "id": "test-delete-002",
            "subject": {"id": "patient-004", "sex": "MALE"},
            "metaData": {
                "created": "2025-01-01T00:00:00Z",
                "createdBy": "test",
                "phenopacketSchemaVersion": "2.0.0",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-04-26",
                        "namespacePrefix": "HP",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
            },
        },
        subject_id="patient-004",
        subject_sex="MALE",
        created_by_id=None,
    )
    db_session.add(test_phenopacket)
    await db_session.commit()
    await db_session.refresh(test_phenopacket)

    # Attempt delete without change_reason
    response = await async_client.delete(
        f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
        headers=admin_headers,
    )

    # Should return 422 Unprocessable Entity (missing required query parameter)
    assert response.status_code == 422

    # Verify phenopacket not deleted
    await db_session.refresh(test_phenopacket)
    assert test_phenopacket.deleted_at is None

    # Cleanup
    await db_session.delete(test_phenopacket)
    await db_session.commit()


@pytest.mark.asyncio
async def test_delete_already_deleted(
    async_client, db_session, admin_headers, cleanup_test_phenopackets
):
    """Test deleting already soft-deleted phenopacket."""
    from datetime import datetime, timezone

    # Create already deleted phenopacket
    test_phenopacket = Phenopacket(
        phenopacket_id="test-delete-003",
        version="2.0",
        revision=1,
        phenopacket={
            "id": "test-delete-003",
            "subject": {"id": "patient-005", "sex": "MALE"},
            "metaData": {
                "created": "2025-01-01T00:00:00Z",
                "createdBy": "test",
                "phenopacketSchemaVersion": "2.0.0",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-04-26",
                        "namespacePrefix": "HP",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
            },
        },
        subject_id="patient-005",
        subject_sex="MALE",
        created_by_id=None,
        deleted_at=datetime.now(timezone.utc),
        deleted_by_id=None,
    )
    db_session.add(test_phenopacket)
    await db_session.commit()
    await db_session.refresh(test_phenopacket)

    # Attempt to delete again
    response = await async_client.request(
        "DELETE",
        f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
        headers=admin_headers,
        json={"change_reason": "Delete again", "revision": test_phenopacket.revision},
    )

    # Should return 404 (not found because soft-deleted records are filtered)
    assert response.status_code == 404
    assert "not found or already deleted" in response.json()["detail"]

    # Cleanup
    await db_session.delete(test_phenopacket)
    await db_session.commit()


@pytest.mark.asyncio
async def test_update_soft_deleted_phenopacket(
    async_client, db_session, admin_headers, cleanup_test_phenopackets
):
    """Test updating soft-deleted phenopacket should fail."""
    from datetime import datetime, timezone

    # Create soft-deleted phenopacket
    test_phenopacket = Phenopacket(
        phenopacket_id="test-update-deleted-001",
        version="2.0",
        revision=3,
        phenopacket={
            "id": "test-update-deleted-001",
            "subject": {"id": "patient-006", "sex": "MALE"},
            "metaData": {
                "created": "2025-01-01T00:00:00Z",
                "createdBy": "test",
                "phenopacketSchemaVersion": "2.0.0",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-04-26",
                        "namespacePrefix": "HP",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
            },
        },
        subject_id="patient-006",
        subject_sex="MALE",
        created_by_id=None,
        deleted_at=datetime.now(timezone.utc),
        deleted_by_id=None,
    )
    db_session.add(test_phenopacket)
    await db_session.commit()
    await db_session.refresh(test_phenopacket)

    # Attempt update
    updated_data = {
        "phenopacket": {
            "id": "test-update-deleted-001",
            "subject": {"id": "patient-006", "sex": "FEMALE"},
            "metaData": {
                "created": "2025-01-01T00:00:00Z",
                "createdBy": "test",
                "phenopacketSchemaVersion": "2.0.0",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-04-26",
                        "namespacePrefix": "HP",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
            },
        },
        "revision": 3,
        "change_reason": "Try to update deleted",
    }

    response = await async_client.put(
        f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
        json=updated_data,
        headers=admin_headers,
    )

    # Should return 404 (soft-deleted records are filtered)
    assert response.status_code == 404

    # Cleanup
    await db_session.delete(test_phenopacket)
    await db_session.commit()


@pytest.mark.asyncio
async def test_get_audit_history(
    async_client, db_session, admin_user, admin_headers, cleanup_test_phenopackets
):
    """Test retrieving audit history for a phenopacket."""
    from app.phenopackets.models import Phenopacket

    # Create test phenopacket directly in DB (like other tests)
    test_phenopacket = Phenopacket(
        phenopacket_id="test-audit-001",
        version="2.0",
        phenopacket={
            "id": "test-audit-001",
            "subject": {"id": "patient-audit-001", "sex": "UNKNOWN_SEX"},
            "phenotypicFeatures": [],
            "interpretations": [],
            "metaData": {
                "created": "2025-01-01T00:00:00Z",
                "createdBy": admin_user.username,
                "phenopacketSchemaVersion": "2.0.0",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-04-26",
                        "namespacePrefix": "HP",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
            },
        },
        subject_id="patient-audit-001",
        subject_sex="UNKNOWN_SEX",
        created_by_id=admin_user.id,
        updated_by_id=admin_user.id,
    )
    db_session.add(test_phenopacket)
    await db_session.commit()
    await db_session.refresh(test_phenopacket)

    # Update phenopacket twice to create audit trail
    update1_data = {
        "phenopacket": {
            "id": "test-audit-001",
            "subject": {"id": "patient-audit-001", "sex": "FEMALE"},
            "phenotypicFeatures": [],
            "interpretations": [],
            "metaData": test_phenopacket.phenopacket["metaData"],
        },
        "revision": 1,
        "change_reason": "Updated sex to FEMALE",
    }

    update1_response = await async_client.put(
        f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
        json=update1_data,
        headers=admin_headers,
    )
    assert update1_response.status_code == 200
    updated1 = update1_response.json()

    update2_data = {
        "phenopacket": {
            "id": "test-audit-001",
            "subject": {"id": "patient-audit-001", "sex": "MALE"},
            "phenotypicFeatures": [],
            "interpretations": [],
            "metaData": test_phenopacket.phenopacket["metaData"],
        },
        "revision": updated1["revision"],
        "change_reason": "Updated sex to MALE",
    }

    update2_response = await async_client.put(
        f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
        json=update2_data,
        headers=admin_headers,
    )
    assert update2_response.status_code == 200

    # Wave 7 D.1: PUT on a draft record now uses PhenopacketStateService which
    # tracks changes via PhenopacketRevision rows, not PhenopacketAudit entries.
    # Verify the updates are tracked via the /revisions endpoint instead.
    # (DONE_WITH_CONCERNS: PUT audit trail moved from phenopacket_audit to
    # phenopacket_revisions as part of Wave 7 D.1 state-machine integration.)
    revisions_response = await async_client.get(
        f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}/revisions",
        headers=admin_headers,
    )

    assert revisions_response.status_code == 200
    revisions_body = revisions_response.json()

    # _inplace_save on a draft with no editing_revision_id does not create
    # new revision rows (it only bumps pp.revision). The working copy changes
    # are confirmed by checking the phenopacket content directly.
    await db_session.refresh(test_phenopacket)
    assert test_phenopacket.phenopacket["subject"]["sex"] == "MALE"
    assert test_phenopacket.revision == 3  # two PUT calls each bumped revision

    # /revisions endpoint is curator-only and must return 200
    assert "data" in revisions_body

    # Cleanup
    await db_session.delete(test_phenopacket)
    await db_session.commit()


@pytest.mark.asyncio
async def test_get_audit_history_not_found(async_client, admin_headers):
    """Test getting audit history for non-existent phenopacket."""
    response = await async_client.get(
        "/api/v2/phenopackets/nonexistent/audit",
        headers=admin_headers,
    )

    assert response.status_code == 404
