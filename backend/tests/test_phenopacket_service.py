"""Unit tests for ``app.phenopackets.services.phenopacket_service``.

Covers the Router → Service → Repository layer introduced in Wave 4.
Each test drives the service through its ``PhenopacketRepository`` and
asserts that the right ``ServiceError`` subclass is raised for each
failure mode, so the router can map exceptions to HTTP status codes
with confidence.

These tests use the real async session (via the ``db_session`` fixture)
rather than mocks, because the whole point of the service layer is to
exercise SQLAlchemy's integrity constraints and audit chain end-to-end.
"""

from __future__ import annotations

import pytest

from app.phenopackets.models import (
    Phenopacket,
    PhenopacketCreate,
    PhenopacketUpdate,
)
from app.phenopackets.repositories import PhenopacketRepository
from app.phenopackets.services.phenopacket_service import (
    PhenopacketService,
    ServiceConflict,
    ServiceError,
    ServiceNotFound,
    ServiceValidationError,
)

# ---------------------------------------------------------------------------
# Sample phenopacket builders
# ---------------------------------------------------------------------------


def _build_phenopacket(
    phenopacket_id: str = "SERVICE-TEST-001",
    subject_id: str = "SUB-SERVICE-001",
    sex: str = "MALE",
) -> dict:
    """Return a minimal valid phenopacket payload for service tests.

    Carries the full ``metaData`` block (including a ``resources`` entry
    for HPO) so ``PhenopacketValidator`` accepts it — the schema validator
    requires both ``created`` / ``createdBy`` and a non-empty ``resources``
    array.
    """
    return {
        "id": phenopacket_id,
        "subject": {"id": subject_id, "sex": sex},
        "phenotypicFeatures": [{"type": {"id": "HP:0000107", "label": "Renal cyst"}}],
        "metaData": {
            "created": "2026-04-11T00:00:00Z",
            "createdBy": "service-test",
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


@pytest.fixture
def make_service(db_session):
    """Factory that returns a fresh PhenopacketService bound to db_session."""

    def _factory() -> PhenopacketService:
        return PhenopacketService(PhenopacketRepository(db_session))

    return _factory


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


class TestPhenopacketServiceCreate:
    """``PhenopacketService.create`` behaviour."""

    @pytest.mark.asyncio
    async def test_create_returns_persisted_phenopacket(self, make_service):
        """A valid phenopacket is created and returned with the sanitised payload."""
        service = make_service()
        payload = PhenopacketCreate(
            phenopacket=_build_phenopacket(),
        )

        result = await service.create(payload, actor_id=None)

        assert isinstance(result, Phenopacket)
        assert result.phenopacket_id == "SERVICE-TEST-001"
        assert result.subject_id == "SUB-SERVICE-001"
        assert result.subject_sex == "MALE"
        assert result.created_by_id is None

    @pytest.mark.asyncio
    async def test_create_unknown_sex_defaults_to_unknown(self, make_service):
        """Missing ``subject.sex`` falls back to ``UNKNOWN_SEX`` per schema default."""
        service = make_service()
        payload_data = _build_phenopacket(
            phenopacket_id="SERVICE-TEST-002",
            subject_id="SUB-SERVICE-002",
        )
        payload_data["subject"].pop("sex", None)
        payload = PhenopacketCreate(
            phenopacket=payload_data,
        )

        result = await service.create(payload, actor_id=None)

        assert result.subject_sex == "UNKNOWN_SEX"

    @pytest.mark.asyncio
    async def test_create_duplicate_id_raises_service_conflict(self, make_service):
        """A second insert with the same id must raise ServiceConflict(code=duplicate_id).

        This is the test that pins the new ``IntegrityError.orig.sqlstate``
        detection path — prior to the fix we were substring-matching the
        error text, which is locale-dependent.
        """
        service = make_service()
        payload = PhenopacketCreate(
            phenopacket=_build_phenopacket(phenopacket_id="SERVICE-TEST-DUP"),
        )

        # First insert succeeds
        await service.create(payload, actor_id=None)

        # Second insert with the same id fails with a structured conflict
        with pytest.raises(ServiceConflict) as excinfo:
            await service.create(payload, actor_id=None)

        assert excinfo.value.code == "duplicate_id"
        assert "SERVICE-TEST-DUP" in str(excinfo.value.detail)

    @pytest.mark.asyncio
    async def test_create_invalid_payload_raises_validation_error(self, make_service):
        """A payload missing required fields is rejected before the DB write.

        We strip ``metaData`` — the sanitizer leaves it as ``None`` and the
        ``PhenopacketValidator`` rejects the shape. This verifies that the
        service raises ``ServiceValidationError`` (router maps to 400).
        """
        service = make_service()
        bad = _build_phenopacket(phenopacket_id="SERVICE-TEST-BAD")
        bad.pop("metaData", None)
        payload = PhenopacketCreate(
            phenopacket=bad,
        )

        with pytest.raises(ServiceValidationError) as excinfo:
            await service.create(payload, actor_id=None)

        assert excinfo.value.errors  # the validator attaches its error dict

    @pytest.mark.asyncio
    async def test_service_conflict_is_subclass_of_service_error(self):
        """Router's ``except ServiceError`` clauses must still catch conflicts."""
        conflict = ServiceConflict({"error": "x"}, code="duplicate_id")
        assert isinstance(conflict, ServiceError)


# ---------------------------------------------------------------------------
# update()
# ---------------------------------------------------------------------------


class TestPhenopacketServiceUpdate:
    """``PhenopacketService.update`` behaviour."""

    @pytest.mark.asyncio
    async def test_update_missing_id_raises_not_found(self, make_service):
        """Updating a nonexistent row raises ServiceNotFound (router → 404)."""
        service = make_service()
        payload = PhenopacketUpdate(
            phenopacket=_build_phenopacket(phenopacket_id="DOES-NOT-EXIST"),
            change_reason="service test",
        )

        with pytest.raises(ServiceNotFound):
            await service.update("DOES-NOT-EXIST", payload, actor_id=None)

    @pytest.mark.asyncio
    async def test_update_wrong_revision_raises_conflict(self, make_service):
        """Optimistic locking rejects stale revisions with ServiceConflict."""
        service = make_service()
        created = await service.create(
            PhenopacketCreate(
                phenopacket=_build_phenopacket(phenopacket_id="SERVICE-TEST-REV"),
            ),
            actor_id=None,
        )
        # ``revision`` starts at 1 for a new row. Supply a stale value.
        stale_revision = created.revision - 1 if created.revision > 0 else 99

        payload = PhenopacketUpdate(
            phenopacket=_build_phenopacket(phenopacket_id="SERVICE-TEST-REV"),
            change_reason="service test",
            revision=stale_revision,
        )

        with pytest.raises(ServiceConflict) as excinfo:
            await service.update("SERVICE-TEST-REV", payload, actor_id=None)

        assert excinfo.value.code == "revision_mismatch"
        assert excinfo.value.detail["current_revision"] == created.revision
        assert excinfo.value.detail["expected_revision"] == stale_revision

    @pytest.mark.asyncio
    async def test_update_success_increments_revision(self, make_service):
        """A successful update increments the ``revision`` counter."""
        service = make_service()
        created = await service.create(
            PhenopacketCreate(
                phenopacket=_build_phenopacket(phenopacket_id="SERVICE-TEST-INC"),
            ),
            actor_id=None,
        )
        start_revision = created.revision

        # Re-read a fresh service because the session may have been rolled
        # back if the previous test failed.
        service2 = make_service()
        updated_phenopacket = _build_phenopacket(
            phenopacket_id="SERVICE-TEST-INC",
            subject_id="SUB-SERVICE-INC-2",
        )
        payload = PhenopacketUpdate(
            phenopacket=updated_phenopacket,
            change_reason="service test update",
        )

        updated = await service2.update("SERVICE-TEST-INC", payload, actor_id=None)

        assert updated.revision == start_revision + 1
        assert updated.subject_id == "SUB-SERVICE-INC-2"

    @pytest.mark.asyncio
    async def test_update_invalid_payload_raises_validation_error(self, make_service):
        """A validation failure on update surfaces as ServiceValidationError."""
        service = make_service()
        await service.create(
            PhenopacketCreate(
                phenopacket=_build_phenopacket(phenopacket_id="SERVICE-TEST-BAD-UP"),
            ),
            actor_id=None,
        )

        service2 = make_service()
        bad = _build_phenopacket(phenopacket_id="SERVICE-TEST-BAD-UP")
        bad.pop("metaData", None)

        with pytest.raises(ServiceValidationError):
            await service2.update(
                "SERVICE-TEST-BAD-UP",
                PhenopacketUpdate(phenopacket=bad, change_reason="service test"),
                actor_id=None,
            )


# ---------------------------------------------------------------------------
# soft_delete()
# ---------------------------------------------------------------------------


class TestPhenopacketServiceSoftDelete:
    """``PhenopacketService.soft_delete`` behaviour."""

    @pytest.mark.asyncio
    async def test_soft_delete_missing_raises_not_found(self, make_service):
        """Deleting a nonexistent row raises ServiceNotFound."""
        service = make_service()
        with pytest.raises(ServiceNotFound):
            await service.soft_delete(
                "DOES-NOT-EXIST",
                change_reason="service test",
                actor_id=None,
            )

    @pytest.mark.asyncio
    async def test_soft_delete_returns_summary_dict(self, make_service):
        """Success returns a dict with message/deleted_at/deleted_by fields."""
        service = make_service()
        await service.create(
            PhenopacketCreate(
                phenopacket=_build_phenopacket(phenopacket_id="SERVICE-TEST-DEL"),
            ),
            actor_id=None,
        )

        service2 = make_service()
        result = await service2.soft_delete(
            "SERVICE-TEST-DEL",
            change_reason="service test delete",
            actor_id=None,
        )

        assert "SERVICE-TEST-DEL" in result["message"]
        assert result["deleted_by"] is None
        assert result["deleted_at"] is not None

    @pytest.mark.asyncio
    async def test_soft_delete_then_read_returns_none(self, make_service):
        """After soft delete ``service.get`` must no longer return the row.

        Also verifies the ``include_deleted=True`` read path still
        returns the soft-deleted row — used by audit/timeline views.
        """
        service = make_service()
        await service.create(
            PhenopacketCreate(
                phenopacket=_build_phenopacket(phenopacket_id="SERVICE-TEST-HIDDEN"),
            ),
            actor_id=None,
        )

        service2 = make_service()
        await service2.soft_delete(
            "SERVICE-TEST-HIDDEN",
            change_reason="service test",
            actor_id=None,
        )

        service3 = make_service()
        assert await service3.get("SERVICE-TEST-HIDDEN") is None
        # Still reachable when requesting with include_deleted
        assert (
            await service3.get("SERVICE-TEST-HIDDEN", include_deleted=True) is not None
        )
