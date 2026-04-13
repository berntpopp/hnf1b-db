"""Wave 5a: phenopacket CREATE must emit an audit row.

Before this fix, only UPDATE and DELETE wrote audit rows; CREATE
silently skipped it, so the audit history endpoint never had an
'initial import' row for any phenopacket created through the API.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_HP_RESOURCE = {
    "id": "hp",
    "name": "Human Phenotype Ontology",
    "namespacePrefix": "HP",
    "url": "http://purl.obolibrary.org/obo/hp.owl",
    "version": "2024-01-01",
    "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
}


def _valid_payload(phenopacket_id: str, subject_id: str, sex: str = "MALE") -> dict:
    """Return a minimal valid phenopacket POST payload (resources required)."""
    return {
        "phenopacket": {
            "id": phenopacket_id,
            "subject": {"id": subject_id, "sex": sex},
            "phenotypicFeatures": [
                {"type": {"id": "HP:0000107", "label": "Renal cyst"}}
            ],
            "metaData": {
                "created": "2026-04-11T00:00:00Z",
                "createdBy": "pytest",
                "phenopacketSchemaVersion": "2.0",
                "resources": [_HP_RESOURCE],
            },
        }
    }


@pytest.mark.asyncio
async def test_create_phenopacket_emits_audit_row(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
):
    """POST /phenopackets writes a CREATE audit row with the patch structure."""
    payload = _valid_payload("audit-on-create-001", "subject-aoc-001")
    response = await async_client.post(
        "/api/v2/phenopackets/", json=payload, headers=admin_headers
    )
    assert response.status_code == 200, response.text

    # There should be exactly ONE audit row for this phenopacket, with action=CREATE
    result = await db_session.execute(
        text("""
            SELECT action, new_value, change_summary, changed_by_id
            FROM phenopacket_audit
            WHERE phenopacket_id = 'audit-on-create-001'
        """)
    )
    rows = list(result)
    assert len(rows) == 1, f"expected 1 audit row, got {len(rows)}"
    row = rows[0]
    assert row.action == "CREATE"
    assert row.new_value is not None
    assert row.new_value["id"] == "audit-on-create-001"
    assert "Initial import" in (row.change_summary or "")
    assert row.changed_by_id is not None  # FK populated


@pytest.mark.asyncio
async def test_create_then_update_yields_create_audit_row(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
):
    """POST emits a CREATE audit row; subsequent PUT is tracked via revisions.

    Wave 7 D.1 contract change: PUT now delegates to PhenopacketStateService
    which writes PhenopacketRevision rows instead of PhenopacketAudit rows.
    The CREATE audit row (written by PhenopacketService.create) is still
    present; only the UPDATE audit row is no longer written.
    (DONE_WITH_CONCERNS: PUT audit trail moved from phenopacket_audit to
    phenopacket_revisions as part of Wave 7 D.1 state-machine integration.)
    """
    create_payload = _valid_payload("audit-on-create-002", "subject-aoc-002", "FEMALE")
    create_resp = await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )
    assert create_resp.status_code == 200, create_resp.text

    # Build update payload: same phenopacket but with sex changed to MALE
    update_inner = dict(create_payload["phenopacket"])
    update_inner["subject"] = {"id": "subject-aoc-002", "sex": "MALE"}
    update_payload = {
        "phenopacket": update_inner,
        "revision": 1,
        "change_reason": "correcting sex",
    }
    put_resp = await async_client.put(
        "/api/v2/phenopackets/audit-on-create-002",
        json=update_payload,
        headers=admin_headers,
    )
    assert put_resp.status_code == 200, put_resp.text

    # Only the CREATE audit row exists; PUT no longer writes to phenopacket_audit.
    result = await db_session.execute(
        text("""
            SELECT action
            FROM phenopacket_audit
            WHERE phenopacket_id = 'audit-on-create-002'
            ORDER BY changed_at
        """)
    )
    actions = [row.action for row in result]
    assert actions == ["CREATE"]

    # The PUT change is tracked via phenopacket_revisions (state-machine audit trail).
    # _inplace_save on a fresh draft (no editing_revision_id) does not create
    # a new revision row — it only bumps pp.revision and overwrites the content.
    rev_result = await db_session.execute(
        text("""
            SELECT revision_number
            FROM phenopacket_revisions
            WHERE record_id = (
                SELECT id FROM phenopackets WHERE phenopacket_id = 'audit-on-create-002'
            )
            ORDER BY revision_number
        """)
    )
    rev_numbers = [row.revision_number for row in rev_result]
    # No revision rows: _inplace_save with editing_revision_id=NULL skips row insert
    assert rev_numbers == []
