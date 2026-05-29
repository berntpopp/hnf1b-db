"""Integration tests for passage persistence + hybrid retrieval (real Postgres).

These exercise the pgvector-backed test database: passage persistence, the
lexical FTS leg, the dense pgvector leg fused via RRF (using the deterministic
FakeEmbeddingProvider), filters, response modes, and budget truncation.
"""

import pytest
from sqlalchemy import text

from app.publications.fulltext import persistence
from app.publications.fulltext.embeddings import FakeEmbeddingProvider, hash_text
from app.publications.fulltext.retrieval import search_passages
from app.publications.fulltext.types import PassageRow

PMID = "PMID:1"

_PASSAGES = [
    PassageRow(PMID, "PMID:1:methods:0", "methods", 0,
               "HNF1B targeted sequencing in a cystic kidney disease cohort", 58, 9,
               "pubtator_full_bioc"),
    PassageRow(PMID, "PMID:1:results:0", "results", 1,
               "renal cysts and maturity onset diabetes were observed", 53, 8,
               "pubtator_full_bioc"),
    PassageRow(PMID, "PMID:1:discussion:0", "discussion", 2,
               "the phenotype frequently includes hypomagnesemia and hyperuricemia", 66, 8,
               "pubtator_full_bioc"),
    PassageRow(PMID, "PMID:1:abstract:0", "abstract", 3,
               "HNF1B variants cause cystic kidney disease and diabetes", 55, 8,
               "pubtator_full_bioc"),
]


async def _seed(db, *, with_embeddings=False):
    """Seed one publication + its passages (and optional fake embeddings)."""
    await persistence.ensure_metadata_row(db, PMID, title="Seed pub")
    await db.execute(
        text("UPDATE publication_metadata SET coverage='full_text' WHERE pmid=:p"),
        {"p": PMID},
    )
    await persistence.replace_passages(db, PMID, _PASSAGES)
    if with_embeddings:
        provider = FakeEmbeddingProvider(dim=384)
        vectors = await provider.embed([p.text for p in _PASSAGES])
        for passage, vector in zip(_PASSAGES, vectors):
            await persistence.upsert_embedding(
                db, passage_id=passage.passage_id, pmid=PMID,
                model_name=provider.model_name, embedding=vector,
                text_hash=hash_text(passage.text),
            )
    await db.commit()


@pytest.mark.asyncio
async def test_replace_passages_is_idempotent(db_session):
    await _seed(db_session)
    # Re-seed: replace should DELETE + re-INSERT, not duplicate.
    n = await persistence.replace_passages(db_session, PMID, _PASSAGES)
    await db_session.commit()
    assert n == 4
    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM publication_fulltext WHERE pmid=:p"),
            {"p": PMID},
        )
    ).scalar()
    assert count == 4


@pytest.mark.asyncio
async def test_lexical_ranks_keyword_match_first(db_session):
    await _seed(db_session)
    result = await search_passages(
        db_session, "cystic kidney", rerank="lexical", mode="full", limit=10
    )
    assert result.rerank_used == "lexical"
    assert result.lexical_candidate_count >= 2
    ids = [p.passage_id for p in result.passages]
    # methods + abstract mention "cystic kidney"; discussion (hypomagnesemia) must not top.
    assert "PMID:1:methods:0" in ids
    assert "PMID:1:abstract:0" in ids
    assert ids[0] in ("PMID:1:methods:0", "PMID:1:abstract:0")


@pytest.mark.asyncio
async def test_section_filter(db_session):
    await _seed(db_session)
    result = await search_passages(
        db_session, "diabetes", sections=["results"], rerank="lexical"
    )
    assert {p.section for p in result.passages} == {"results"}


@pytest.mark.asyncio
async def test_pmid_filter_excludes_others(db_session):
    await _seed(db_session)
    result = await search_passages(
        db_session, "kidney", pmids=["999999"], rerank="lexical"
    )
    assert result.passages == []


@pytest.mark.asyncio
async def test_ids_only_mode_omits_text(db_session):
    await _seed(db_session)
    result = await search_passages(db_session, "kidney", mode="ids_only", rerank="lexical")
    assert result.passages
    assert all(p.text is None and p.snippet is None for p in result.passages)


@pytest.mark.asyncio
async def test_brief_mode_sets_snippet(db_session):
    await _seed(db_session)
    result = await search_passages(db_session, "cystic kidney", mode="brief", rerank="lexical")
    assert result.passages
    assert all(p.text is None for p in result.passages)
    assert any(p.snippet for p in result.passages)


@pytest.mark.asyncio
async def test_full_mode_max_chars_truncates(db_session):
    await _seed(db_session)
    result = await search_passages(
        db_session, "kidney diabetes cysts hypomagnesemia HNF1B", rerank="lexical",
        mode="full", limit=10, max_chars=60,
    )
    # First passage always included; budget then stops further ones.
    assert len(result.passages) == 1
    assert result.truncated is True


@pytest.mark.asyncio
async def test_rrf_uses_dense_leg_with_embeddings(db_session):
    await _seed(db_session, with_embeddings=True)
    provider = FakeEmbeddingProvider(dim=384)
    # Query text identical to the results passage -> deterministic fake vector
    # matches that passage's stored vector exactly (cosine distance 0).
    # Disable section boosts to isolate the dense/RRF mechanics (boost behaviour
    # is covered by the rrf unit tests). With boosts off, the exact-text passage
    # — nearest dense neighbour AND a top lexical hit — must rank first.
    result = await search_passages(
        db_session, "renal cysts and maturity onset diabetes were observed",
        rerank="rrf", provider=provider, mode="full", limit=10, section_boosts={},
    )
    assert result.rerank_used == "rrf"
    assert result.dense_candidate_count > 0
    assert result.embedding_dim == 384
    # The exact-text passage is the nearest dense neighbour.
    assert result.passages[0].passage_id == "PMID:1:results:0"
    assert result.passages[0].dense_rank == 1


@pytest.mark.asyncio
async def test_rrf_falls_back_to_lexical_without_provider(db_session):
    await _seed(db_session)
    result = await search_passages(db_session, "kidney", rerank="rrf", provider=None)
    assert result.rerank_used == "lexical"
    assert any("dense disabled" in note for note in result.notes)


@pytest.mark.asyncio
async def test_rrf_falls_back_when_no_embeddings_stored(db_session):
    await _seed(db_session, with_embeddings=False)
    provider = FakeEmbeddingProvider(dim=384)
    result = await search_passages(db_session, "kidney", rerank="rrf", provider=provider)
    assert result.rerank_used == "lexical"
    assert any("no embeddings" in note for note in result.notes)


@pytest.mark.asyncio
async def test_invalid_rerank_and_mode_raise(db_session):
    with pytest.raises(ValueError):
        await search_passages(db_session, "x", rerank="bogus")
    with pytest.raises(ValueError):
        await search_passages(db_session, "x", mode="bogus")
