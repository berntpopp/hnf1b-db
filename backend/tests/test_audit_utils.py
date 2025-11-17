"""Unit tests for audit trail utilities.

Tests the audit utility functions for phenopacket change tracking,
including JSON Patch generation, change summaries, and conflict detection.
"""

import copy
from typing import Any, Dict

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.audit import (
    compare_phenopackets,
    create_audit_entry,
    generate_change_summary,
    generate_json_patch,
)


# Test Fixtures
@pytest.fixture
def sample_phenopacket_minimal() -> Dict[str, Any]:
    """Minimal phenopacket for testing."""
    return {
        "id": "phenopacket:HNF1B:001",
        "subject": {"id": "patient-001", "sex": "MALE"},
        "phenotypicFeatures": [],
        "interpretations": [],
        "metaData": {
            "created": "2025-01-01T00:00:00Z",
            "createdBy": "curator@example.com",
            "resources": [],
            "phenopacketSchemaVersion": "2.0.0",
        },
    }


@pytest.fixture
def sample_phenopacket_with_data() -> Dict[str, Any]:
    """Phenopacket with phenotypes and variants for testing."""
    return {
        "id": "phenopacket:HNF1B:002",
        "subject": {"id": "patient-002", "sex": "FEMALE"},
        "phenotypicFeatures": [
            {
                "type": {"id": "HP:0000001", "label": "Phenotype 1"},
                "excluded": False,
            },
            {
                "type": {"id": "HP:0000002", "label": "Phenotype 2"},
                "excluded": False,
            },
        ],
        "interpretations": [
            {
                "id": "interpretation-1",
                "progressStatus": "SOLVED",
                "diagnosis": {
                    "disease": {"id": "MONDO:0001", "label": "Disease 1"},
                    "genomicInterpretations": [],
                },
            }
        ],
        "diseases": [{"term": {"id": "MONDO:0001", "label": "Disease 1"}}],
        "metaData": {
            "created": "2025-01-01T00:00:00Z",
            "createdBy": "curator@example.com",
            "resources": [],
            "phenopacketSchemaVersion": "2.0.0",
        },
    }


# JSON Patch Tests
class TestGenerateJsonPatch:
    """Test RFC 6902 JSON Patch generation."""

    def test_no_changes(self, sample_phenopacket_minimal: Dict[str, Any]) -> None:
        """Test that identical phenopackets produce empty patch."""
        patch = generate_json_patch(
            sample_phenopacket_minimal, sample_phenopacket_minimal
        )
        assert patch == []

    def test_simple_field_change(self, sample_phenopacket_minimal: Dict[str, Any]) -> None:
        """Test patch for simple field modification."""
        old = copy.deepcopy(sample_phenopacket_minimal)
        new = copy.deepcopy(sample_phenopacket_minimal)
        new["subject"]["sex"] = "FEMALE"

        patch = generate_json_patch(old, new)

        assert len(patch) == 1
        assert patch[0]["op"] == "replace"
        assert patch[0]["path"] == "/subject/sex"
        assert patch[0]["value"] == "FEMALE"

    def test_add_phenotype(self, sample_phenopacket_minimal: Dict[str, Any]) -> None:
        """Test patch for adding phenotypic features."""
        old = copy.deepcopy(sample_phenopacket_minimal)
        new = copy.deepcopy(sample_phenopacket_minimal)
        new["phenotypicFeatures"] = [
            {"type": {"id": "HP:0000118", "label": "Phenotypic abnormality"}}
        ]

        patch = generate_json_patch(old, new)

        assert len(patch) >= 1
        # Should have a replace or add operation for phenotypicFeatures
        paths = [op["path"] for op in patch]
        assert "/phenotypicFeatures" in paths or any(
            "/phenotypicFeatures" in p for p in paths
        )

    def test_multiple_changes(
        self, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test patch with multiple simultaneous changes."""
        old = copy.deepcopy(sample_phenopacket_minimal)
        new = copy.deepcopy(sample_phenopacket_minimal)
        new["subject"]["sex"] = "FEMALE"
        new["phenotypicFeatures"] = [
            {"type": {"id": "HP:0000001", "label": "Phenotype"}}
        ]

        patch = generate_json_patch(old, new)

        assert len(patch) >= 2
        paths = {op["path"] for op in patch}
        assert "/subject/sex" in paths


# Change Summary Tests
class TestGenerateChangeSummary:
    """Test human-readable change summary generation."""

    def test_create_summary_minimal(
        self, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test CREATE summary for minimal phenopacket."""
        summary = generate_change_summary("CREATE", None, sample_phenopacket_minimal)
        assert "Initial import" in summary
        assert "0 phenotype(s)" in summary
        assert "0 variant(s)" in summary

    def test_create_summary_with_data(
        self, sample_phenopacket_with_data: Dict[str, Any]
    ) -> None:
        """Test CREATE summary with phenotypes and variants."""
        summary = generate_change_summary("CREATE", None, sample_phenopacket_with_data)
        assert "Initial import" in summary
        assert "2 phenotype(s)" in summary
        assert "1 variant(s)" in summary

    def test_update_summary_no_changes(
        self, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test UPDATE summary when no changes detected."""
        summary = generate_change_summary(
            "UPDATE", sample_phenopacket_minimal, sample_phenopacket_minimal
        )
        assert "Updated phenopacket metadata" in summary

    def test_update_summary_sex_change(
        self, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test UPDATE summary for sex field change."""
        old = copy.deepcopy(sample_phenopacket_minimal)
        new = copy.deepcopy(sample_phenopacket_minimal)
        new["subject"]["sex"] = "FEMALE"

        summary = generate_change_summary("UPDATE", old, new)
        assert "Updated:" in summary
        assert "changed sex to FEMALE" in summary

    def test_update_summary_added_phenotypes(
        self, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test UPDATE summary for adding phenotypes."""
        old = copy.deepcopy(sample_phenopacket_minimal)
        new = copy.deepcopy(sample_phenopacket_minimal)
        new["phenotypicFeatures"] = [
            {"type": {"id": "HP:0000001", "label": "Phenotype 1"}},
            {"type": {"id": "HP:0000002", "label": "Phenotype 2"}},
            {"type": {"id": "HP:0000003", "label": "Phenotype 3"}},
        ]

        summary = generate_change_summary("UPDATE", old, new)
        assert "Updated:" in summary
        assert "added 3 phenotype(s)" in summary

    def test_update_summary_removed_phenotypes(
        self, sample_phenopacket_with_data: Dict[str, Any]
    ) -> None:
        """Test UPDATE summary for removing phenotypes."""
        old = copy.deepcopy(sample_phenopacket_with_data)
        new = copy.deepcopy(sample_phenopacket_with_data)
        new["phenotypicFeatures"] = []

        summary = generate_change_summary("UPDATE", old, new)
        assert "Updated:" in summary
        assert "removed 2 phenotype(s)" in summary

    def test_update_summary_added_variants(
        self, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test UPDATE summary for adding variants."""
        old = copy.deepcopy(sample_phenopacket_minimal)
        new = copy.deepcopy(sample_phenopacket_minimal)
        new["interpretations"] = [
            {"id": "int-1", "progressStatus": "SOLVED"},
            {"id": "int-2", "progressStatus": "IN_PROGRESS"},
        ]

        summary = generate_change_summary("UPDATE", old, new)
        assert "Updated:" in summary
        assert "added 2 variant(s)" in summary

    def test_update_summary_added_diseases(
        self, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test UPDATE summary for adding diseases."""
        old = copy.deepcopy(sample_phenopacket_minimal)
        new = copy.deepcopy(sample_phenopacket_minimal)
        new["diseases"] = [{"term": {"id": "MONDO:0001", "label": "Disease 1"}}]

        summary = generate_change_summary("UPDATE", old, new)
        assert "Updated:" in summary
        assert "added 1 disease(s)" in summary

    def test_update_summary_multiple_changes(
        self, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test UPDATE summary with multiple changes."""
        old = copy.deepcopy(sample_phenopacket_minimal)
        new = copy.deepcopy(sample_phenopacket_minimal)
        new["subject"]["sex"] = "FEMALE"
        new["phenotypicFeatures"] = [
            {"type": {"id": "HP:0000001", "label": "Phenotype"}}
        ]
        new["interpretations"] = [{"id": "int-1", "progressStatus": "SOLVED"}]

        summary = generate_change_summary("UPDATE", old, new)
        assert "Updated:" in summary
        assert "added 1 phenotype(s)" in summary
        assert "added 1 variant(s)" in summary
        assert "changed sex to FEMALE" in summary

    def test_delete_summary(self, sample_phenopacket_minimal: Dict[str, Any]) -> None:
        """Test DELETE summary."""
        summary = generate_change_summary("DELETE", sample_phenopacket_minimal, None)
        assert summary == "Soft deleted phenopacket"

    def test_create_summary_null_phenopacket(self) -> None:
        """Test CREATE summary with None phenopacket."""
        summary = generate_change_summary("CREATE", None, None)
        assert summary == "Created phenopacket"

    def test_update_summary_null_values(self) -> None:
        """Test UPDATE summary with None values."""
        summary = generate_change_summary("UPDATE", None, None)
        assert summary == "Updated phenopacket"


# Conflict Detection Tests
class TestComparePhenopackets:
    """Test phenopacket comparison and conflict detection."""

    def test_no_conflicts_identical(
        self, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test that identical phenopackets have no conflicts."""
        result = compare_phenopackets(
            sample_phenopacket_minimal, sample_phenopacket_minimal
        )

        assert result["has_conflicts"] is False
        assert result["conflicts"] == []
        assert result["patch"] == []
        assert result["patch_count"] == 0

    def test_no_conflicts_safe_changes(
        self, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test that safe changes don't trigger conflicts."""
        old = copy.deepcopy(sample_phenopacket_minimal)
        new = copy.deepcopy(sample_phenopacket_minimal)
        new["phenotypicFeatures"] = [
            {"type": {"id": "HP:0000001", "label": "Phenotype"}}
        ]

        result = compare_phenopackets(old, new)

        assert result["has_conflicts"] is False
        assert result["conflicts"] == []
        assert result["patch_count"] > 0

    def test_conflict_subject_sex_change(
        self, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test that changing subject sex triggers conflict."""
        old = copy.deepcopy(sample_phenopacket_minimal)
        new = copy.deepcopy(sample_phenopacket_minimal)
        new["subject"]["sex"] = "FEMALE"

        result = compare_phenopackets(old, new)

        assert result["has_conflicts"] is True
        assert len(result["conflicts"]) == 1
        assert "Modified critical field: /subject/sex" in result["conflicts"]
        assert result["patch_count"] == 1

    def test_conflict_subject_id_change(
        self, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test that changing subject ID triggers conflict."""
        old = copy.deepcopy(sample_phenopacket_minimal)
        new = copy.deepcopy(sample_phenopacket_minimal)
        new["subject"]["id"] = "different-patient-id"

        result = compare_phenopackets(old, new)

        assert result["has_conflicts"] is True
        conflicts_list = result["conflicts"]
        assert isinstance(conflicts_list, list)
        assert any(
            "Modified critical field: /subject/id" in c for c in conflicts_list
        )

    def test_conflict_schema_version_change(
        self, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test that changing schema version triggers conflict."""
        old = copy.deepcopy(sample_phenopacket_minimal)
        new = copy.deepcopy(sample_phenopacket_minimal)
        new["metaData"]["phenopacketSchemaVersion"] = "3.0.0"

        result = compare_phenopackets(old, new)

        assert result["has_conflicts"] is True
        conflicts_list = result["conflicts"]
        assert isinstance(conflicts_list, list)
        assert any(
            "Modified critical field: /metaData/phenopacketSchemaVersion" in c
            for c in conflicts_list
        )

    def test_multiple_conflicts(
        self, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test detection of multiple conflicts."""
        old = copy.deepcopy(sample_phenopacket_minimal)
        new = copy.deepcopy(sample_phenopacket_minimal)
        new["subject"]["sex"] = "FEMALE"
        new["subject"]["id"] = "different-patient"

        result = compare_phenopackets(old, new)

        assert result["has_conflicts"] is True
        assert len(result["conflicts"]) >= 2


# Database Integration Tests
class TestCreateAuditEntry:
    """Test audit entry creation in database."""

    @pytest.mark.asyncio
    async def test_create_audit_create_action(
        self, db_session: AsyncSession, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test creating CREATE audit entry."""
        audit = await create_audit_entry(
            db=db_session,
            phenopacket_id="phenopacket:HNF1B:001",
            action="CREATE",
            old_value=None,
            new_value=sample_phenopacket_minimal,
            changed_by="curator@example.com",
            change_reason="Initial import from Google Sheets",
        )

        assert audit is not None
        assert audit.phenopacket_id == "phenopacket:HNF1B:001"
        assert audit.action == "CREATE"
        assert audit.old_value is None
        assert audit.new_value is not None
        assert audit.changed_by == "curator@example.com"
        assert audit.change_reason == "Initial import from Google Sheets"
        assert audit.change_patch is None  # CREATE has no patch
        assert audit.change_summary is not None
        assert "Initial import" in audit.change_summary
        assert audit.changed_at is not None

    @pytest.mark.asyncio
    async def test_create_audit_update_action(
        self,
        db_session: AsyncSession,
        sample_phenopacket_minimal: Dict[str, Any],
    ) -> None:
        """Test creating UPDATE audit entry with JSON Patch."""
        old = copy.deepcopy(sample_phenopacket_minimal)
        new = copy.deepcopy(sample_phenopacket_minimal)
        new["subject"]["sex"] = "FEMALE"

        audit = await create_audit_entry(
            db=db_session,
            phenopacket_id="phenopacket:HNF1B:001",
            action="UPDATE",
            old_value=old,
            new_value=new,
            changed_by="curator@example.com",
            change_reason="Corrected patient sex",
        )

        assert audit is not None
        assert audit.action == "UPDATE"
        assert audit.old_value is not None
        assert audit.new_value is not None
        assert audit.change_patch is not None
        assert len(audit.change_patch) > 0
        assert audit.change_summary is not None
        assert "changed sex to FEMALE" in audit.change_summary

    @pytest.mark.asyncio
    async def test_create_audit_delete_action(
        self, db_session: AsyncSession, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test creating DELETE audit entry."""
        audit = await create_audit_entry(
            db=db_session,
            phenopacket_id="phenopacket:HNF1B:001",
            action="DELETE",
            old_value=sample_phenopacket_minimal,
            new_value=None,
            changed_by="admin@example.com",
            change_reason="Patient withdrew consent",
        )

        assert audit is not None
        assert audit.action == "DELETE"
        assert audit.old_value is not None
        assert audit.new_value is None
        assert audit.change_patch is None
        assert audit.change_summary == "Soft deleted phenopacket"

    @pytest.mark.asyncio
    async def test_create_audit_invalid_action(
        self, db_session: AsyncSession, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test that invalid action raises ValueError."""
        with pytest.raises(ValueError, match="Invalid action"):
            await create_audit_entry(
                db=db_session,
                phenopacket_id="phenopacket:HNF1B:001",
                action="INVALID_ACTION",
                old_value=None,
                new_value=sample_phenopacket_minimal,
                changed_by="curator@example.com",
                change_reason="Test",
            )

    @pytest.mark.asyncio
    async def test_create_audit_persists(
        self, db_session: AsyncSession, sample_phenopacket_minimal: Dict[str, Any]
    ) -> None:
        """Test that audit entry is properly persisted to database."""
        _ = await create_audit_entry(
            db=db_session,
            phenopacket_id="phenopacket:HNF1B:TEST",
            action="CREATE",
            old_value=None,
            new_value=sample_phenopacket_minimal,
            changed_by="test@example.com",
            change_reason="Unit test",
        )

        # Verify we can retrieve it
        query = text(
            "SELECT * FROM phenopacket_audit WHERE phenopacket_id = :phenopacket_id"
        )
        result = await db_session.execute(
            query, {"phenopacket_id": "phenopacket:HNF1B:TEST"}
        )
        row = result.fetchone()

        assert row is not None
        assert row.action == "CREATE"
        assert row.changed_by == "test@example.com"
        assert row.change_reason == "Unit test"
