"""Tests for POST /api/v2/phenopackets/import-batch (Issue #554)."""

import pytest
from sqlalchemy import func, select

from app.phenopackets.models import Phenopacket


def _valid_phenopacket(phenopacket_id: str, subject_id: str) -> dict:
    """Return a minimal valid phenopacket payload."""
    return {
        "id": phenopacket_id,
        "subject": {"id": subject_id, "sex": "MALE"},
        "phenotypicFeatures": [{"type": {"id": "HP:0000107", "label": "Renal cyst"}}],
        "metaData": {
            "created": "2026-04-11T00:00:00Z",
            "createdBy": "batch-import-test",
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


@pytest.mark.asyncio
async def test_import_batch_requires_curator_role(async_client, viewer_headers):
    """Anonymous or viewer callers must be rejected."""
    payload = {"phenopackets": [_valid_phenopacket("BATCH-001", "SUB-001")]}

    # Anonymous -> 401
    resp_anon = await async_client.post(
        "/api/v2/phenopackets/import-batch",
        json=payload,
    )
    assert resp_anon.status_code == 401

    # Viewer -> 403
    resp_viewer = await async_client.post(
        "/api/v2/phenopackets/import-batch",
        json=payload,
        headers=viewer_headers,
    )
    assert resp_viewer.status_code == 403


@pytest.mark.asyncio
async def test_import_batch_dry_run_writes_nothing(
    async_client, curator_headers, db_session
):
    """dry_run=True (default) validates rows and writes 0 records to database."""
    p1 = _valid_phenopacket("BATCH-DRY-1", "SUB-DRY-1")
    p2 = _valid_phenopacket("BATCH-DRY-2", "SUB-DRY-2")
    payload = {"phenopackets": [p1, p2]}

    resp = await async_client.post(
        "/api/v2/phenopackets/import-batch?dry_run=true",
        json=payload,
        headers=curator_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    assert body["total_rows"] == 2
    assert body["valid_rows"] == 2
    assert body["invalid_rows"] == 0
    assert body["committed_rows"] == 0
    assert len(body["results"]) == 2
    assert body["results"][0]["valid"] is True
    assert body["results"][1]["valid"] is True

    # Verify database has not been touched
    count = await db_session.scalar(
        select(func.count())
        .select_from(Phenopacket)
        .where(Phenopacket.phenopacket_id.in_(["BATCH-DRY-1", "BATCH-DRY-2"]))
    )
    assert count == 0


@pytest.mark.asyncio
async def test_import_batch_validation_reporting(async_client, curator_headers):
    """Invalid rows report schema and structural errors in results array."""
    valid_p = _valid_phenopacket("BATCH-REP-1", "SUB-REP-1")
    invalid_p = {
        "id": "BATCH-REP-2",
        # missing subject and metaData
        "phenotypicFeatures": [],
    }
    payload = {"phenopackets": [valid_p, invalid_p]}

    resp = await async_client.post(
        "/api/v2/phenopackets/import-batch",
        json=payload,
        headers=curator_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_rows"] == 2
    assert body["valid_rows"] == 1
    assert body["invalid_rows"] == 1

    r0 = body["results"][0]
    assert r0["phenopacket_id"] == "BATCH-REP-1"
    assert r0["valid"] is True
    assert r0["errors"] == []

    r1 = body["results"][1]
    assert r1["phenopacket_id"] == "BATCH-REP-2"
    assert r1["valid"] is False
    assert len(r1["errors"]) > 0


@pytest.mark.asyncio
async def test_import_batch_commit_and_duplicate_detection(
    async_client, curator_headers, db_session
):
    """dry_run=False commits valid rows and marks existing rows on subsequent run."""
    p1 = _valid_phenopacket("BATCH-LIVE-1", "SUB-LIVE-1")
    payload = {"phenopackets": [p1]}

    # 1. Commit live
    resp1 = await async_client.post(
        "/api/v2/phenopackets/import-batch?dry_run=false",
        json=payload,
        headers=curator_headers,
    )
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert body1["dry_run"] is False
    assert body1["committed_rows"] == 1
    assert body1["valid_rows"] == 1

    # Verify record in DB
    record = (
        await db_session.execute(
            select(Phenopacket).where(Phenopacket.phenopacket_id == "BATCH-LIVE-1")
        )
    ).scalar_one_or_none()
    assert record is not None
    assert record.phenopacket_id == "BATCH-LIVE-1"

    # 2. Subsequent import attempts to re-import the same ID
    resp2 = await async_client.post(
        "/api/v2/phenopackets/import-batch?dry_run=true",
        json=payload,
        headers=curator_headers,
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["valid_rows"] == 0
    assert body2["invalid_rows"] == 1
    assert body2["results"][0]["already_exists"] is True
    assert body2["results"][0]["valid"] is False
