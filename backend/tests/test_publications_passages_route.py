"""API tests for ``GET /api/v2/publications/passages`` (real Postgres).

The dense leg requires sentence-transformers (absent in CI), so the public
endpoint exercises the lexical path; ``rerank=rrf`` gracefully degrades to
lexical and the response reports it.
"""

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
