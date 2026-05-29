"""Integration test: the publications list endpoint surfaces RAG coverage fields.

Verifies the additive ``abstract``/``coverage``/``pmcid``/``license``/
``has_full_text`` columns appear on ``GET /api/v2/publications/`` for a published
publication, without disturbing the existing list contract.
"""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from app.phenopackets.models import Phenopacket, PhenopacketRevision


async def _seed_published_pub_with_coverage(db_session, *, pmid, actor_id):
    """Insert a publication_metadata row (full_text coverage) + a published
    phenopacket that cites it, so the list query's pub_counts CTE returns it.
    """
    await db_session.execute(
        text("""
            INSERT INTO publication_metadata (
                pmid, title, authors, journal, year, doi, abstract,
                coverage, pmcid, license, fetched_at, fetched_by
            ) VALUES (
                :pmid, :title, CAST(:authors AS JSONB), :journal, :year, :doi,
                :abstract, :coverage, :pmcid, :license, :fetched_at, 'test'
            )
        """),
        {
            "pmid": pmid,
            "title": "HNF1B cystic kidney disease cohort",
            "authors": json.dumps([{"name": "Obeidova L"}, {"name": "Seeman T"}]),
            "journal": "PLoS One",
            "year": 2020,
            "doi": "10.1371/journal.pone.0235071",
            "abstract": "Cystic kidney diseases are a heterogeneous group...",
            "coverage": "full_text",
            "pmcid": "PMC7310724",
            "license": "CC-BY",
            "fetched_at": datetime.now(timezone.utc),
        },
    )
    ppid = f"PUB-COV-{pmid.replace('PMID:', '')}"
    pp_json = {
        "id": ppid,
        "subject": {"id": f"SUB-{ppid}", "sex": "UNKNOWN_SEX"},
        "metaData": {
            "created": "2026-05-29T00:00:00Z",
            "createdBy": "cov-test",
            "phenopacketSchemaVersion": "2.0",
            "externalReferences": [{"id": pmid, "description": "cohort"}],
        },
    }
    row = Phenopacket(
        phenopacket_id=ppid,
        phenopacket=pp_json,
        subject_id=f"SUB-{ppid}",
        subject_sex="UNKNOWN_SEX",
        created_by_id=None,
        state="published",
        revision=1,
    )
    db_session.add(row)
    await db_session.flush()
    rev = PhenopacketRevision(
        record_id=row.id,
        revision_number=1,
        state="published",
        content_jsonb=pp_json,
        change_reason="init",
        actor_id=actor_id,
        from_state=None,
        to_state="published",
        is_head_published=True,
    )
    db_session.add(rev)
    await db_session.flush()
    row.head_published_revision_id = rev.id
    await db_session.commit()


@pytest.mark.asyncio
async def test_list_endpoint_exposes_coverage_fields(async_client, db_session, admin_user):
    await _seed_published_pub_with_coverage(
        db_session, pmid="PMID:32574212", actor_id=admin_user.id
    )
    resp = await async_client.get("/api/v2/publications/")
    assert resp.status_code == 200
    items = resp.json()["data"]
    item = next(i for i in items if i["pmid"] == "32574212")
    assert item["coverage"] == "full_text"
    assert item["has_full_text"] is True
    assert item["pmcid"] == "PMC7310724"
    assert item["license"] == "CC-BY"
    assert item["abstract"].startswith("Cystic kidney diseases")


@pytest.mark.asyncio
async def test_list_endpoint_defaults_when_no_metadata(async_client, db_session, admin_user):
    """A cited PMID with no metadata row defaults to title_only / no full text."""
    ppid = "PUB-COV-NOMETA"
    pp_json = {
        "id": ppid,
        "subject": {"id": f"SUB-{ppid}", "sex": "UNKNOWN_SEX"},
        "metaData": {
            "created": "2026-05-29T00:00:00Z",
            "createdBy": "cov-test",
            "phenopacketSchemaVersion": "2.0",
            "externalReferences": [{"id": "PMID:99999999", "description": "x"}],
        },
    }
    row = Phenopacket(
        phenopacket_id=ppid,
        phenopacket=pp_json,
        subject_id=f"SUB-{ppid}",
        subject_sex="UNKNOWN_SEX",
        created_by_id=None,
        state="published",
        revision=1,
    )
    db_session.add(row)
    await db_session.flush()
    rev = PhenopacketRevision(
        record_id=row.id,
        revision_number=1,
        state="published",
        content_jsonb=pp_json,
        change_reason="init",
        actor_id=admin_user.id,
        from_state=None,
        to_state="published",
        is_head_published=True,
    )
    db_session.add(rev)
    await db_session.flush()
    row.head_published_revision_id = rev.id
    await db_session.commit()

    resp = await async_client.get("/api/v2/publications/")
    assert resp.status_code == 200
    item = next(i for i in resp.json()["data"] if i["pmid"] == "99999999")
    assert item["coverage"] == "title_only"
    assert item["has_full_text"] is False
    assert item["abstract"] is None
