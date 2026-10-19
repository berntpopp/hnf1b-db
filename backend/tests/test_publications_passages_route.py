"""API tests for ``GET /api/v2/publications/passages`` (real Postgres).

The dense leg requires sentence-transformers (absent in CI), so the public
endpoint exercises the lexical path; ``rerank=rrf`` gracefully degrades to
lexical and the response reports it.
"""

import inspect

import pytest
from sqlalchemy import text

from app.publications.fulltext import persistence
from app.publications.fulltext.types import PassageRow

PMID = "PMID:5"
_PASSAGES = [
    PassageRow(
        PMID,
        "PMID:5:methods:0",
        "methods",
        0,
        "HNF1B sequencing in a cystic kidney disease cohort",
        50,
        8,
        "pubtator_full_bioc",
    ),
    PassageRow(
        PMID,
        "PMID:5:results:0",
        "results",
        1,
        "renal cysts and diabetes mellitus were frequent",
        47,
        7,
        "pubtator_full_bioc",
    ),
]


async def _seed(db):
    await persistence.ensure_metadata_row(db, PMID, title="Seed")
    await db.execute(
        text("UPDATE publication_metadata SET coverage='full_text' WHERE pmid=:p"),
        {"p": PMID},
    )
    await persistence.replace_passages(db, PMID, _PASSAGES)
    await db.commit()


@pytest.mark.asyncio
async def test_passages_endpoint_returns_ranked_hits(async_client, db_session):
    await _seed(db_session)
    resp = await async_client.get(
        "/api/v2/publications/passages",
        params={"q": "cystic kidney", "rerank": "lexical"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["passages"]
    top = body["passages"][0]
    assert top["passage_id"].startswith("PMID:5:")
    assert top["text"]  # full mode
    assert top["score"] > 0
    meta = body["meta"]
    assert meta["rerank_used"] == "lexical"
    assert meta["total"] == len(body["passages"])
    assert meta["lexical_candidate_count"] >= 1


@pytest.mark.asyncio
async def test_passages_ids_only_mode(async_client, db_session):
    await _seed(db_session)
    resp = await async_client.get(
        "/api/v2/publications/passages",
        params={"q": "kidney", "mode": "ids_only", "rerank": "lexical"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["passages"]
    assert all(p["text"] is None for p in body["passages"])


@pytest.mark.asyncio
async def test_passages_brief_mode_has_snippet(async_client, db_session):
    await _seed(db_session)
    resp = await async_client.get(
        "/api/v2/publications/passages",
        params={"q": "cystic kidney", "mode": "brief", "rerank": "lexical"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["passages"]
    assert any(p["snippet"] for p in body["passages"])


@pytest.mark.asyncio
async def test_passages_rrf_degrades_to_lexical_without_embeddings(
    async_client, db_session
):
    await _seed(db_session)
    resp = await async_client.get(
        "/api/v2/publications/passages", params={"q": "kidney", "rerank": "rrf"}
    )
    assert resp.status_code == 200
    # No embedding provider in CI -> dense disabled, reported as lexical.
    meta = resp.json()["meta"]
    assert meta["rerank_used"] == "lexical"
    # The silent hybrid->lexical degradation must be explicit in meta.
    assert meta["embeddings_available"] is False


@pytest.mark.asyncio
async def test_passages_section_filter(async_client, db_session):
    await _seed(db_session)
    resp = await async_client.get(
        "/api/v2/publications/passages",
        params={"q": "diabetes", "sections": "results", "rerank": "lexical"},
    )
    assert resp.status_code == 200
    assert {p["section"] for p in resp.json()["passages"]} == {"results"}


@pytest.mark.asyncio
async def test_passages_invalid_rerank_400(async_client, db_session):
    await _seed(db_session)
    resp = await async_client.get(
        "/api/v2/publications/passages", params={"q": "kidney", "rerank": "nope"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_passages_requires_query(async_client, db_session):
    resp = await async_client.get("/api/v2/publications/passages")
    assert resp.status_code == 422  # missing required q


@pytest.mark.asyncio
async def test_shared_provider_async_offloaded():
    """Verify _shared_provider is an async function that uses thread offloading and caching."""
    from app.publications.endpoints.passages_route import (
        _PROVIDER_CACHE,
        _shared_provider,
    )

    assert inspect.iscoroutinefunction(_shared_provider)
    p1 = await _shared_provider()
    p2 = await _shared_provider()
    assert p1 is p2
    assert "provider" in _PROVIDER_CACHE


@pytest.mark.asyncio
async def test_suggest_phenotypes_from_passages(async_client, db_session):
    """Verify suggest-phenotypes extracts terms from stored passages with bare or prefixed PMID."""
    await _seed(db_session)

    # Bare PMID
    resp = await async_client.get(
        "/api/v2/publications/passages/suggest-phenotypes",
        params={"pmid": "5"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["pmid"] == "5"
    hpo_ids = {s["hpo_id"]: s for s in body["suggestions"]}
    assert (
        "HP:0000107" in hpo_ids
    )  # Renal cyst (from "cystic kidney disease" / "renal cysts")
    assert hpo_ids["HP:0000107"]["excluded"] is False
    assert "HP:0000819" in hpo_ids  # Diabetes mellitus
    assert hpo_ids["HP:0000819"]["excluded"] is False

    # Prefixed PMID
    resp2 = await async_client.get(
        "/api/v2/publications/passages/suggest-phenotypes",
        params={"pmid": "PMID:5"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["pmid"] == "5"


@pytest.mark.asyncio
async def test_suggest_phenotypes_with_negation(async_client, db_session):
    """Verify negation cues are scoped to the local clause around each phenotype."""
    negated_pmid = "PMID:99"
    await persistence.ensure_metadata_row(
        db_session, negated_pmid, title="Negation test"
    )
    passages = [
        PassageRow(
            negated_pmid,
            "PMID:99:results:0",
            "results",
            0,
            "The patient had no hypomagnesemia and renal insufficiency was absent. "
            "The patient had renal cysts but no diabetes mellitus.",
            125,
            20,
            "pubtator_full_bioc",
        )
    ]
    await persistence.replace_passages(db_session, negated_pmid, passages)
    await db_session.commit()

    resp = await async_client.get(
        "/api/v2/publications/passages/suggest-phenotypes",
        params={"pmid": "99"},
    )
    assert resp.status_code == 200
    body = resp.json()
    hpo_map = {s["hpo_id"]: s for s in body["suggestions"]}
    assert "HP:0002917" in hpo_map  # Hypomagnesemia
    assert hpo_map["HP:0002917"]["excluded"] is True
    assert "HP:0000083" in hpo_map  # Renal insufficiency
    assert hpo_map["HP:0000083"]["excluded"] is True
    assert "HP:0000107" in hpo_map  # Renal cyst (positive in first clause)
    assert hpo_map["HP:0000107"]["excluded"] is False
    assert "HP:0000819" in hpo_map  # Diabetes mellitus (negated in second clause)
    assert hpo_map["HP:0000819"]["excluded"] is True


@pytest.mark.asyncio
async def test_suggest_phenotypes_fallback_to_metadata(async_client, db_session):
    """Verify fallback to publication_metadata when no fulltext passages exist."""
    meta_pmid = "PMID:88"
    await persistence.ensure_metadata_row(
        db_session, meta_pmid, title="Renal study without hypokalemia"
    )
    await db_session.execute(
        text(
            "UPDATE publication_metadata "
            "SET abstract='Patient presenting with multicystic kidney dysplasia.' "
            "WHERE pmid=:p"
        ),
        {"p": meta_pmid},
    )
    await db_session.commit()

    resp = await async_client.get(
        "/api/v2/publications/passages/suggest-phenotypes",
        params={"pmid": "88"},
    )
    assert resp.status_code == 200
    body = resp.json()
    hpo_map = {s["hpo_id"]: s for s in body["suggestions"]}
    assert "HP:0000003" in hpo_map  # Multicystic kidney dysplasia
    assert hpo_map["HP:0000003"]["excluded"] is False
    assert hpo_map["HP:0000003"]["section"] == "abstract"
    assert "HP:0002900" in hpo_map  # Hypokalemia
    assert hpo_map["HP:0002900"]["excluded"] is True
    assert hpo_map["HP:0002900"]["section"] == "title"
