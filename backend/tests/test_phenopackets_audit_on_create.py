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
async def test_create_then_update_yields_two_audit_rows(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
):
    """Two audit rows: the CREATE row (from this task) + the UPDATE row."""
    create_payload = _valid_payload("audit-on-create-002", "subject-aoc-002", "FEMALE")
    await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )

    # Build update payload: same phenopacket but with sex changed to MALE
    update_inner = dict(create_payload["phenopacket"])
    update_inner["subject"] = {"id": "subject-aoc-002", "sex": "MALE"}
    update_payload = {
        "phenopacket": update_inner,
        "revision": 1,
        "change_reason": "correcting sex",
    }
    await async_client.put(
        "/api/v2/phenopackets/audit-on-create-002",
        json=update_payload,
        headers=admin_headers,
    )

    result = await db_session.execute(
        text("""
            SELECT action
            FROM phenopacket_audit
            WHERE phenopacket_id = 'audit-on-create-002'
            ORDER BY changed_at
        """)
    )
    actions = [row.action for row in result]
    assert actions == ["CREATE", "UPDATE"]
