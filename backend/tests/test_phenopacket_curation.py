"""Tests for phenopacket curation endpoints (UPDATE/DELETE) with optimistic locking and audit trail."""

import pytest
from sqlalchemy import select

from app.phenopackets.models import Phenopacket, PhenopacketAudit


@pytest.mark.asyncio
async def test_update_phenopacket_success(
    async_client, db_session, admin_headers, cleanup_test_phenopackets
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
            "phenotypicFeatures": [
                {"type": {"id": "HP:0000001", "label": "All"}}
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
        subject_id="patient-001",
        subject_sex="MALE",
        created_by="test",
        updated_by="test",
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
        "updated_by": "admin",
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

    # Verify audit entry created
    audit_result = await db_session.execute(
        select(PhenopacketAudit).where(
            PhenopacketAudit.phenopacket_id == "test-update-001"
        )
    )
    audit = audit_result.scalar_one()

    assert audit.action == "UPDATE"
    assert audit.changed_by == "admin"
    assert audit.change_reason == "Changed sex and added phenotype"
    assert audit.change_patch is not None
    assert "changed sex to FEMALE" in audit.change_summary
    assert "added 1 phenotype(s)" in audit.change_summary

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
        created_by="test",
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
    assert "error" in error["detail"]
    assert error["detail"]["current_revision"] == 5
    assert error["detail"]["expected_revision"] == 3

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
    async_client, db_session, admin_headers, cleanup_test_phenopackets
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
        created_by="test",
    )
    db_session.add(test_phenopacket)
    await db_session.commit()
    await db_session.refresh(test_phenopacket)

    # Soft delete
    response = await async_client.request(
        "DELETE",
        f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
        headers=admin_headers,
        json={"change_reason": "Test deletion"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "deleted successfully" in data["message"]
    assert data["deleted_by"] == "testadmin"
    assert "deleted_at" in data

    # Verify soft delete in database
    await db_session.refresh(test_phenopacket)
    assert test_phenopacket.deleted_at is not None
    assert test_phenopacket.deleted_by == "testadmin"

    # Verify audit entry created
    audit_result = await db_session.execute(
        select(PhenopacketAudit).where(
            PhenopacketAudit.phenopacket_id == "test-delete-001"
        )
    )
    audit = audit_result.scalar_one()

    assert audit.action == "DELETE"
    assert audit.changed_by == "testadmin"
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
        created_by="test",
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
        created_by="test",
        deleted_at=datetime.now(timezone.utc),
        deleted_by="previous_user",
    )
    db_session.add(test_phenopacket)
    await db_session.commit()
    await db_session.refresh(test_phenopacket)

    # Attempt to delete again
    response = await async_client.request(
        "DELETE",
        f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}",
        headers=admin_headers,
        json={"change_reason": "Delete again"},
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
        created_by="test",
        deleted_at=datetime.now(timezone.utc),
        deleted_by="curator",
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
        created_by=admin_user.username,
        updated_by=admin_user.username,
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

    # Test audit history endpoint
    audit_response = await async_client.get(
        f"/api/v2/phenopackets/{test_phenopacket.phenopacket_id}/audit",
        headers=admin_headers,
    )

    assert audit_response.status_code == 200
    audit_entries = audit_response.json()

    # Should have 2 UPDATE entries
    assert len(audit_entries) == 2

    # Check most recent entry (should be UPDATE to MALE)
    latest_entry = audit_entries[0]
    assert latest_entry["action"] == "UPDATE"
    assert latest_entry["change_reason"] == "Updated sex to MALE"
    assert latest_entry["phenopacket_id"] == test_phenopacket.phenopacket_id
    assert latest_entry["changed_by"] == admin_user.username
    assert latest_entry["change_summary"] is not None
    assert "changed sex to MALE" in latest_entry["change_summary"]

    # Verify change_patch exists and is a list
    assert latest_entry["change_patch"] is not None
    assert isinstance(latest_entry["change_patch"], list)
    assert len(latest_entry["change_patch"]) > 0

    # Verify entries are ordered by timestamp (most recent first)
    for i in range(len(audit_entries) - 1):
        current_time = audit_entries[i]["changed_at"]
        next_time = audit_entries[i + 1]["changed_at"]
        assert current_time >= next_time

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
