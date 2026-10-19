"""Optimistic locking enforcement regression coverage [BUG-04]."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.phenopackets.models import PhenopacketCreate, PhenopacketUpdate
from app.phenopackets.repositories import PhenopacketRepository
from app.phenopackets.services.phenopacket_service import (
    PhenopacketService,
    ServiceConflict,
)


@pytest.fixture
def make_service(db_session):
    def _factory() -> PhenopacketService:
        return PhenopacketService(PhenopacketRepository(db_session))

    return _factory


def _minimal_packet(phenopacket_id: str = "LOCK-1") -> dict:
    return {
        "id": phenopacket_id,
        "subject": {"id": f"sub-{phenopacket_id}", "sex": "FEMALE"},
        "metaData": {
            "created": "2026-08-09T00:00:00Z",
            "createdBy": "test",
            "resources": [{"id": "hp", "name": "HPO", "namespacePrefix": "HP"}],
        },
    }


def test_phenopacket_update_requires_revision():
    """PhenopacketUpdate rejects omission of revision [BUG-04]."""
    with pytest.raises(ValidationError) as excinfo:
        PhenopacketUpdate(
            phenopacket=_minimal_packet(),
            change_reason="missing revision",
        )
    assert any(
        err["loc"] == ("revision",) and err["type"] == "missing"
        for err in excinfo.value.errors()
    )


@pytest.mark.asyncio
async def test_update_enforces_optimistic_locking_conflict(make_service):
    """PhenopacketService.update raises ServiceConflict when revision does not match [BUG-04]."""
    service = make_service()
    created = await service.create(
        PhenopacketCreate(phenopacket=_minimal_packet("LOCK-CONFLICT")),
        actor_id=None,
    )
    current_rev = created.revision

    wrong_payload = PhenopacketUpdate(
        phenopacket=_minimal_packet("LOCK-CONFLICT"),
        revision=current_rev + 5,
        change_reason="stale edit",
    )
    with pytest.raises(ServiceConflict) as excinfo:
        await service.update("LOCK-CONFLICT", wrong_payload, actor_id=None)
    assert excinfo.value.code == "revision_mismatch"
    assert excinfo.value.detail["current_revision"] == current_rev
    assert excinfo.value.detail["expected_revision"] == current_rev + 5


@pytest.mark.asyncio
async def test_update_succeeds_with_matching_revision(make_service):
    """PhenopacketService.update succeeds and increments revision when revision matches."""
    service = make_service()
    created = await service.create(
        PhenopacketCreate(phenopacket=_minimal_packet("LOCK-OK")),
        actor_id=None,
    )
    current_rev = created.revision

    valid_payload = PhenopacketUpdate(
        phenopacket=_minimal_packet("LOCK-OK"),
        revision=current_rev,
        change_reason="valid edit",
    )
    updated = await service.update("LOCK-OK", valid_payload, actor_id=None)
    assert updated.revision == current_rev + 1
