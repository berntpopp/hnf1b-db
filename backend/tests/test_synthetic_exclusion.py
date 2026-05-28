"""Synthetic (e2e-*) record exclusion from public aggregation/search/list paths.

Playwright e2e tests create real ``e2e-`` phenopackets and may leave them
published. They must not inflate cohort aggregates or appear in anonymous
discovery — but the single-record GET must still return them (so the e2e
lifecycle self-check, which reads its own record by id, keeps working).

Also covers the summary distinct_publications (PMID-only) vs distinct_sources
(all external references) split.
"""

from __future__ import annotations

import pytest


async def _insert_published(db_session, admin_user, ppid: str, content: dict):
    """Insert one published phenopacket (+ head revision) with given content."""
    from app.phenopackets.models import Phenopacket, PhenopacketRevision

    pp = Phenopacket(
        phenopacket_id=ppid,
        phenopacket={"id": ppid, **content},
        state="published",
        revision=1,
        created_by_id=admin_user.id,
        subject_sex="UNKNOWN_SEX",
    )
    db_session.add(pp)
    await db_session.flush()
    rev = PhenopacketRevision(
        record_id=pp.id,
        revision_number=1,
        state="published",
        content_jsonb=pp.phenopacket,
        change_reason="init",
        actor_id=admin_user.id,
        from_state=None,
        to_state="published",
        is_head_published=True,
    )
    db_session.add(rev)
    await db_session.flush()
    pp.head_published_revision_id = rev.id
    await db_session.commit()
    return pp


@pytest.mark.asyncio
async def test_e2e_record_excluded_from_search_list_and_summary(
    async_client, db_session, admin_user
):
    """A published e2e-* record is invisible to anonymous search/list/summary."""
    await _insert_published(db_session, admin_user, "real-rec-1", {})
    await _insert_published(db_session, admin_user, "e2e-wave7-leak-1", {})

    # Search (anonymous) excludes the synthetic record.
    r = await async_client.get("/api/v2/phenopackets/search")
    ids = {item.get("id") for item in r.json().get("data", [])}
    assert "real-rec-1" in ids
    assert "e2e-wave7-leak-1" not in ids

    # List (anonymous) excludes the synthetic record.
    r = await async_client.get("/api/v2/phenopackets/")
    ids = {item.get("id") for item in r.json().get("data", [])}
    assert "real-rec-1" in ids
    assert "e2e-wave7-leak-1" not in ids

    # Summary total counts only the real record.
    r = await async_client.get("/api/v2/phenopackets/aggregate/summary")
    assert r.json()["total_phenopackets"] == 1


@pytest.mark.asyncio
async def test_e2e_record_still_readable_by_id(async_client, db_session, admin_user):
    """Single-record GET must still return the e2e record (lifecycle invariant)."""
    await _insert_published(db_session, admin_user, "e2e-wave7-lifecycle-2", {})

    r = await async_client.get("/api/v2/phenopackets/e2e-wave7-lifecycle-2")
    assert r.status_code == 200
    assert r.json()["phenopacket_id"] == "e2e-wave7-lifecycle-2"


@pytest.mark.asyncio
async def test_summary_publications_pmid_only_sources_all(
    async_client, db_session, admin_user
):
    """distinct_publications counts PMID-only; distinct_sources counts all refs."""
    await _insert_published(
        db_session,
        admin_user,
        "real-rec-pub-1",
        {
            "metaData": {
                "externalReferences": [
                    {"id": "PMID:30666461"},
                    {"id": "OMIM:137920"},
                ]
            }
        },
    )

    r = await async_client.get("/api/v2/phenopackets/aggregate/summary")
    body = r.json()
    assert body["distinct_publications"] == 1  # PMID only
    assert body["distinct_sources"] == 2  # PMID + OMIM
