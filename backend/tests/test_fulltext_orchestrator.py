"""Integration tests for per-publication orchestration (real Postgres).

Exercise the fetch -> license-gate -> chunk -> persist flow via injected fake
fetchers (no network), the batch sync aggregation/error-isolation, and the
embedding backfill driver with the deterministic FakeEmbeddingProvider.
"""

import pytest
from sqlalchemy import text

from app.publications.fulltext import orchestrator, persistence
from app.publications.fulltext.embeddings import FakeEmbeddingProvider
from app.publications.fulltext.orchestrator import (
    PublicationFetchers,
    backfill_embeddings,
    process_publication,
)
from app.publications.fulltext.types import AbstractResult, FullTextResult, RawSection

ALLOWED = ["CC0", "CC-BY", "CC-BY-NC", "PMC-OA"]

_BODY = (
    RawSection("methods", "We performed HNF1B targeted next generation sequencing "
               "in a cohort of children with cystic kidney disease.", 0),
    RawSection("results", "Renal cysts and maturity onset diabetes of the young "
               "were the most frequent findings in carriers.", 1),
)


def _fetchers(abstract_text, fulltext):
    async def fa(pmid):
        return AbstractResult(f"PMID:{pmid.replace('PMID:', '')}", abstract_text) \
            if abstract_text is not None else None

    async def ff(pmid):
        return fulltext

    return PublicationFetchers(fetch_abstract=fa, fetch_fulltext=ff)


async def _coverage(db, pmid):
    row = (
        await db.execute(
            text("SELECT coverage, abstract, license, pmcid FROM publication_metadata "
                 "WHERE pmid=:p"),
            {"p": pmid},
        )
    ).first()
    return row


@pytest.mark.asyncio
async def test_full_text_path_persists_passages(db_session):
    ft = FullTextResult("PMID:10", "PMC10", "cc by", True, _BODY, "pubtator_full_bioc")
    fetchers = _fetchers("An abstract.", ft)
    outcome = await process_publication(
        db_session, "10", fetchers=fetchers, allowed_licenses=ALLOWED
    )
    assert outcome.coverage == "full_text"
    assert outcome.full_text_fetched is True
    assert outcome.abstract_fetched is True
    assert outcome.license_skipped is False
    assert outcome.passages_written >= 2
    row = await _coverage(db_session, "PMID:10")
    assert row.coverage == "full_text"
    assert row.license == "CC-BY"
    assert row.pmcid == "PMC10"
    assert row.abstract == "An abstract."
    n = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM publication_fulltext WHERE pmid='PMID:10'")
        )
    ).scalar()
    assert n == outcome.passages_written


@pytest.mark.asyncio
async def test_license_gate_drops_body(db_session):
    # Non-OA + a license outside the allow-set -> body dropped, abstract kept.
    ft = FullTextResult("PMID:11", "PMC11", "cc by-nc-nd", False, _BODY, "pubtator_full_bioc")
    fetchers = _fetchers("Has an abstract.", ft)
    outcome = await process_publication(
        db_session, "11", fetchers=fetchers, allowed_licenses=ALLOWED
    )
    assert outcome.coverage == "abstract_only"
    assert outcome.license_skipped is True
    assert outcome.passages_written == 0
    n = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM publication_fulltext WHERE pmid='PMID:11'")
        )
    ).scalar()
    assert n == 0


@pytest.mark.asyncio
async def test_open_access_without_license_kept_via_pmc_oa(db_session):
    # No explicit license but open access -> PMC-OA escape hatch permits body.
    ft = FullTextResult("PMID:12", "PMC12", None, True, _BODY, "pubtator_full_bioc")
    outcome = await process_publication(
        db_session, "12", fetchers=_fetchers(None, ft), allowed_licenses=ALLOWED
    )
    assert outcome.coverage == "full_text"
    assert outcome.passages_written >= 2


@pytest.mark.asyncio
async def test_title_only_when_nothing_available(db_session):
    outcome = await process_publication(
        db_session, "13", fetchers=_fetchers(None, None), allowed_licenses=ALLOWED
    )
    assert outcome.coverage == "title_only"
    assert outcome.passages_written == 0


@pytest.mark.asyncio
async def test_passage_ids_unique_across_repeated_sections(db_session):
    body = (
        RawSection("methods", "First methods block about sequencing.", 0),
        RawSection("methods", "Second methods block about validation.", 1),
    )
    ft = FullTextResult("PMID:14", "PMC14", "cc by", True, body, "pubtator_full_bioc")
    await process_publication(
        db_session, "14", fetchers=_fetchers(None, ft), allowed_licenses=ALLOWED
    )
    ids = [
        r.passage_id
        for r in (
            await db_session.execute(
                text("SELECT passage_id FROM publication_fulltext WHERE pmid='PMID:14' "
                     "ORDER BY seq")
            )
        ).fetchall()
    ]
    assert len(ids) == len(set(ids))  # unique
    assert ids == ["PMID:14:methods:0", "PMID:14:methods:1"]


@pytest.mark.asyncio
async def test_sync_publications_aggregates_and_degrades_fetch_failures(
    db_session, monkeypatch
):
    # A fetch failure degrades gracefully (the pub lands in a lower tier), it is
    # NOT counted as a hard error — that is the per-leg resilience contract.
    ft = FullTextResult("PMID:20", "PMC20", "cc by", True, _BODY, "pubtator_full_bioc")

    def fake_build(session, *, abstract_api_key=None):
        async def fa(pmid):
            if pmid == "99":
                raise RuntimeError("transient network blip")
            return AbstractResult(f"PMID:{pmid}", "abs")

        async def ff(pmid):
            return ft if pmid == "20" else None

        return PublicationFetchers(fetch_abstract=fa, fetch_fulltext=ff)

    monkeypatch.setattr(orchestrator, "build_fetchers", fake_build)
    counts = await orchestrator.sync_publications(
        db_session, ["20", "21", "99"], session=None, allowed_licenses=ALLOWED,
        rate_limit_delay=0,
    )
    assert counts.processed == 3  # all completed (99 degraded to title_only)
    assert counts.errors == 0  # fetch blips are degraded, not errored
    assert counts.full_text_fetched == 1  # 20
    assert counts.abstracts_fetched == 2  # 20 + 21 (99's abstract failed)


@pytest.mark.asyncio
async def test_sync_publications_isolates_hard_errors(db_session, monkeypatch):
    # A hard failure inside process_publication is counted and the batch
    # continues (the session is rolled back so later PMIDs still commit).
    real = orchestrator.process_publication

    async def flaky(db, pmid, **kwargs):
        if pmid == "99":
            raise RuntimeError("hard failure")
        return await real(db, pmid, **kwargs)

    ft = FullTextResult("PMID:20", "PMC20", "cc by", True, _BODY, "pubtator_full_bioc")

    def fake_build(session, *, abstract_api_key=None):
        return _fetchers("abs", ft)

    monkeypatch.setattr(orchestrator, "build_fetchers", fake_build)
    monkeypatch.setattr(orchestrator, "process_publication", flaky)
    counts = await orchestrator.sync_publications(
        db_session, ["20", "99", "21"], session=None, allowed_licenses=ALLOWED,
        rate_limit_delay=0,
    )
    assert counts.errors == 1
    assert counts.processed == 2


@pytest.mark.asyncio
async def test_backfill_embeddings_idempotent(db_session):
    ft = FullTextResult("PMID:30", "PMC30", "cc by", True, _BODY, "pubtator_full_bioc")
    await process_publication(
        db_session, "30", fetchers=_fetchers(None, ft), allowed_licenses=ALLOWED
    )
    provider = FakeEmbeddingProvider(dim=384)
    embedded = await backfill_embeddings(db_session, provider, batch_size=8)
    assert embedded >= 2
    stored = await persistence.count_embeddings(db_session, model_name=provider.model_name)
    assert stored == embedded
    # Re-run: nothing stale -> zero new embeddings.
    again = await backfill_embeddings(db_session, provider, batch_size=8)
    assert again == 0
