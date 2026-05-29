"""Per-publication orchestration: fetch -> license-gate -> chunk -> persist.

Ties the leaf modules together into the unit of work shared by the admin sync
endpoint and the one-off backfill script. Fetching is injected via
:class:`PublicationFetchers` so the orchestration logic (the license gate,
chunking, sequencing, and persistence) is tested with in-memory fakes and no
network. :func:`build_fetchers` wires the real clients over an aiohttp session.

Also exposes :func:`backfill_embeddings`, the async batched driver that embeds
passages whose stored ``text_hash`` is stale (used only when the optional
embedding provider is available).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional, Sequence

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession

from app.publications.fulltext import persistence
from app.publications.fulltext.abstract_client import fetch_abstracts
from app.publications.fulltext.chunking import (
    TokenCounter,
    chunk_section,
    get_tokenizer,
)
from app.publications.fulltext.coverage import classify_coverage
from app.publications.fulltext.embeddings import (
    EmbeddingProvider,
    hash_text,
)
from app.publications.fulltext.fulltext_client import (
    fetch_bioc,
    fetch_europepmc_core,
    fetch_jats,
    resolve_pmcids,
)
from app.publications.fulltext.types import (
    AbstractResult,
    FullTextResult,
    PassageRow,
    make_passage_id,
)

logger = logging.getLogger(__name__)


@dataclass
class PubOutcome:
    """Result of processing a single publication.

    Attributes:
        pmid: Normalized PMID.
        coverage: Assigned coverage tier.
        abstract_fetched: Whether a non-empty abstract was stored.
        full_text_fetched: Whether license-permitted body passages were stored.
        license_skipped: Whether body text existed but was dropped by the gate.
        passages_written: Number of passage rows written.
        error: Error message when processing failed, else ``None``.
    """

    pmid: str
    coverage: str = "title_only"
    abstract_fetched: bool = False
    full_text_fetched: bool = False
    license_skipped: bool = False
    passages_written: int = 0
    error: Optional[str] = None


@dataclass
class PublicationFetchers:
    """Injected async fetchers for one publication's external data.

    Attributes:
        fetch_abstract: ``pmid -> AbstractResult | None``.
        fetch_fulltext: ``pmid -> FullTextResult | None`` with license/OA merged.
    """

    fetch_abstract: Callable[[str], Awaitable[Optional[AbstractResult]]]
    fetch_fulltext: Callable[[str], Awaitable[Optional[FullTextResult]]]


def build_fetchers(
    session: aiohttp.ClientSession,
    *,
    abstract_api_key: Optional[str] = None,
) -> PublicationFetchers:
    """Wire real external clients into a :class:`PublicationFetchers`.

    Args:
        session: A shared aiohttp client session.
        abstract_api_key: Optional NCBI API key for higher efetch rate limits.

    Returns:
        A :class:`PublicationFetchers` bound to the live NCBI / PubTator /
        EuropePMC endpoints from configuration.
    """
    from app.core.config import settings

    apis = settings.external_apis

    async def _fetch_abstract(pmid: str) -> Optional[AbstractResult]:
        results = await fetch_abstracts(
            [pmid],
            session=session,
            base_url=apis.efetch.base_url,
            api_key=abstract_api_key,
            batch_size=apis.efetch.batch_size,
            timeout=apis.efetch.timeout_seconds,
        )
        return results.get(f"PMID:{pmid.replace('PMID:', '')}")

    async def _resolve_one_pmcid(pmid: str) -> Optional[str]:
        resolved = await resolve_pmcids(
            [pmid.replace("PMID:", "")],
            session=session,
            base_url=apis.idconv.base_url,
            tool=apis.idconv.tool,
            email=apis.idconv.email,
            batch_size=apis.idconv.batch_size,
            timeout=apis.idconv.timeout_seconds,
        )
        return resolved.get(pmid.replace("PMID:", ""))

    async def _fetch_fulltext(pmid: str) -> Optional[FullTextResult]:
        bioc = await fetch_bioc(
            pmid,
            session=session,
            base_url=apis.pubtator3.base_url,
            timeout=apis.pubtator3.timeout_seconds,
        )
        is_oa, raw_license = await fetch_europepmc_core(
            pmid,
            session=session,
            base_url=apis.europepmc.base_url,
            timeout=apis.europepmc.timeout_seconds,
        )
        if bioc is not None and bioc.sections:
            return FullTextResult(
                pmid=f"PMID:{pmid.replace('PMID:', '')}",
                pmcid=bioc.pmcid,
                license=raw_license,
                is_open_access=is_oa,
                sections=bioc.sections,
                source="pubtator_full_bioc",
            )
        # Fallback: JATS via EuropePMC when PubTator had no body but the record
        # is open access and we can resolve a PMCID.
        pmcid = (bioc.pmcid if bioc else None) or await _resolve_one_pmcid(pmid)
        if pmcid and is_oa:
            jats = await fetch_jats(
                pmcid,
                "PMC",
                session=session,
                base_url=apis.europepmc.base_url,
                timeout=apis.europepmc.timeout_seconds,
            )
            if jats:
                return FullTextResult(
                    pmid=f"PMID:{pmid.replace('PMID:', '')}",
                    pmcid=pmcid,
                    license=raw_license,
                    is_open_access=is_oa,
                    sections=jats,
                    source="europe_pmc_jats",
                )
        # No body anywhere — still surface pmcid/license/OA so metadata records them.
        return FullTextResult(
            pmid=f"PMID:{pmid.replace('PMID:', '')}",
            pmcid=pmcid,
            license=raw_license,
            is_open_access=is_oa,
            sections=(),
            source="pubtator_full_bioc",
        )

    return PublicationFetchers(
        fetch_abstract=_fetch_abstract, fetch_fulltext=_fetch_fulltext
    )


def build_passage_rows(
    pmid: str,
    sections: Sequence,
    *,
    max_tokens: int,
    overlap_tokens: int,
    tokenizer: Optional[TokenCounter] = None,
) -> list[PassageRow]:
    """Chunk license-permitted sections into ordered, persistable passage rows.

    Each :class:`~app.publications.fulltext.types.RawSection` is chunked
    independently (never crossing the section boundary). A per-section index
    makes ``passage_id`` unique within ``(pmid, section)`` even when several raw
    blocks share a section label, while ``seq`` gives a stable global order.

    Args:
        pmid: PMID (prefixed or bare).
        sections: Ordered ``RawSection`` objects that passed the license gate.
        max_tokens: Chunk window size.
        overlap_tokens: Chunk window overlap.
        tokenizer: Tokenizer to use; defaults to :func:`get_tokenizer`.

    Returns:
        Ordered passage rows ready for persistence.
    """
    active = tokenizer if tokenizer is not None else get_tokenizer()
    rows: list[PassageRow] = []
    per_section_idx: dict[str, int] = {}
    seq = 0
    for raw in sections:
        for chunk in chunk_section(
            raw.section,
            raw.text,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            tokenizer=active,
        ):
            idx = per_section_idx.get(raw.section, 0)
            per_section_idx[raw.section] = idx + 1
            rows.append(
                PassageRow(
                    pmid=f"PMID:{pmid.replace('PMID:', '')}",
                    passage_id=make_passage_id(pmid, raw.section, idx),
                    section=raw.section,
                    seq=seq,
                    text=chunk.text,
                    char_count=chunk.char_count,
                    token_count=chunk.token_count,
                    source="",  # set by caller from coverage decision
                )
            )
            seq += 1
    return rows


async def process_publication(
    db: AsyncSession,
    pmid: str,
    *,
    fetchers: PublicationFetchers,
    allowed_licenses: Sequence[str],
    chunk_max_tokens: int = 510,
    chunk_overlap_tokens: int = 50,
    tokenizer: Optional[TokenCounter] = None,
    ensure_metadata: bool = True,
) -> PubOutcome:
    """Fetch, license-gate, chunk, and persist one publication's content.

    Resilient to fetch failures: a network error on the abstract or full-text
    leg degrades that leg to "unavailable" rather than aborting (the publication
    simply lands in a lower coverage tier). Database errors propagate so the
    caller can isolate them per-PMID and continue the batch.

    Args:
        db: The async session (committed once here, atomically per publication).
        pmid: PMID (prefixed or bare).
        fetchers: Injected external fetchers.
        allowed_licenses: License allow-set for the gate.
        chunk_max_tokens: Chunk window size.
        chunk_overlap_tokens: Chunk window overlap.
        tokenizer: Tokenizer override (defaults to the active tokenizer).
        ensure_metadata: When ``True``, insert a placeholder metadata row if the
            publication has none (so the FK + update always succeed).

    Returns:
        A :class:`PubOutcome` summarizing what was stored.
    """
    normalized = f"PMID:{pmid.replace('PMID:', '')}"
    outcome = PubOutcome(pmid=normalized)

    abstract_text: Optional[str] = None
    try:
        abstract_result = await fetchers.fetch_abstract(pmid)
        abstract_text = abstract_result.text if abstract_result else None
    except Exception as exc:  # noqa: BLE001 - degrade, don't abort the batch
        logger.warning("abstract fetch failed for %s: %s", normalized, exc)

    fulltext: Optional[FullTextResult] = None
    try:
        fulltext = await fetchers.fetch_fulltext(pmid)
    except Exception as exc:  # noqa: BLE001 - degrade to abstract/title tier
        logger.warning("full-text fetch failed for %s: %s", normalized, exc)

    decision = classify_coverage(
        abstract=abstract_text, fulltext=fulltext, allowed_licenses=allowed_licenses
    )

    had_body = bool(fulltext and fulltext.sections)
    outcome.coverage = decision.coverage
    outcome.abstract_fetched = bool(abstract_text)
    outcome.full_text_fetched = decision.coverage == "full_text"
    outcome.license_skipped = had_body and decision.coverage != "full_text"

    passages = build_passage_rows(
        normalized,
        decision.sections,
        max_tokens=chunk_max_tokens,
        overlap_tokens=chunk_overlap_tokens,
        tokenizer=tokenizer,
    )
    source = decision.source or "pubtator_full_bioc"
    passages = [
        PassageRow(
            pmid=p.pmid,
            passage_id=p.passage_id,
            section=p.section,
            seq=p.seq,
            text=p.text,
            char_count=p.char_count,
            token_count=p.token_count,
            source=source,
        )
        for p in passages
    ]

    if ensure_metadata:
        await persistence.ensure_metadata_row(db, normalized)
    await persistence.update_metadata_coverage(
        db,
        normalized,
        abstract=abstract_text,
        coverage=decision.coverage,
        license=decision.license,
        pmcid=decision.pmcid,
        fulltext_fetched_at=datetime.now(timezone.utc),
    )
    outcome.passages_written = await persistence.replace_passages(
        db, normalized, passages
    )
    await db.commit()
    return outcome


@dataclass
class SyncCounts:
    """Aggregate counts for a batch publication sync.

    Attributes:
        processed: Publications successfully processed.
        abstracts_fetched: Publications that gained a stored abstract.
        full_text_fetched: Publications that gained license-permitted passages.
        license_skipped: Publications whose body text was dropped by the gate.
        errors: Publications that raised during processing.
    """

    processed: int = 0
    abstracts_fetched: int = 0
    full_text_fetched: int = 0
    license_skipped: int = 0
    errors: int = 0


async def sync_publications(
    db: AsyncSession,
    pmids: Sequence[str],
    *,
    session: aiohttp.ClientSession,
    allowed_licenses: Sequence[str],
    chunk_max_tokens: int = 510,
    chunk_overlap_tokens: int = 50,
    abstract_api_key: Optional[str] = None,
    ensure_metadata: Optional[Callable[[str], Awaitable[None]]] = None,
    rate_limit_delay: float = 0.35,
) -> SyncCounts:
    """Process a batch of PMIDs with per-PMID error isolation and rate limiting.

    Shared by the admin sync endpoint's background task and the one-off backfill
    script. Each publication is processed independently: a failure is counted,
    the session is rolled back, and the batch continues.

    Args:
        db: The async session.
        pmids: PMIDs to process (prefixed or bare).
        session: A shared aiohttp client session for external fetches.
        allowed_licenses: License allow-set for the gate.
        chunk_max_tokens: Chunk window size.
        chunk_overlap_tokens: Chunk window overlap.
        abstract_api_key: Optional NCBI API key.
        ensure_metadata: Optional best-effort coroutine that ensures base
            citation metadata (title/authors/...) exists for a PMID before its
            abstract/full-text columns are updated.
        rate_limit_delay: Seconds to sleep between publications (politeness).

    Returns:
        Aggregate :class:`SyncCounts` for the batch.
    """
    fetchers = build_fetchers(session, abstract_api_key=abstract_api_key)
    counts = SyncCounts()
    for pmid in pmids:
        try:
            if ensure_metadata is not None:
                try:
                    await ensure_metadata(pmid)
                except Exception as exc:  # noqa: BLE001 - placeholder row covers this
                    logger.warning("base metadata ensure failed for %s: %s", pmid, exc)
            outcome = await process_publication(
                db,
                pmid,
                fetchers=fetchers,
                allowed_licenses=allowed_licenses,
                chunk_max_tokens=chunk_max_tokens,
                chunk_overlap_tokens=chunk_overlap_tokens,
            )
            counts.processed += 1
            counts.abstracts_fetched += int(outcome.abstract_fetched)
            counts.full_text_fetched += int(outcome.full_text_fetched)
            counts.license_skipped += int(outcome.license_skipped)
        except Exception as exc:  # noqa: BLE001 - isolate per-PMID, continue batch
            counts.errors += 1
            await db.rollback()
            logger.warning("publication sync failed for %s: %s", pmid, exc)
        if rate_limit_delay:
            await asyncio.sleep(rate_limit_delay)
    return counts


async def backfill_embeddings(
    db: AsyncSession,
    provider: EmbeddingProvider,
    *,
    batch_size: int = 32,
    max_passages: Optional[int] = None,
) -> int:
    """Embed passages whose stored ``text_hash`` is stale, in batches.

    Skips passages already embedded with a matching ``text_hash`` for the
    provider's model, so re-runs are idempotent and cheap.

    Args:
        db: The async session (committed per batch).
        provider: The embedding provider.
        batch_size: Number of passages embedded and committed per batch.
        max_passages: Optional cap on total passages embedded this run.

    Returns:
        The number of passages embedded.
    """
    model_name = provider.model_name
    embedded = 0
    while True:
        remaining = batch_size
        if max_passages is not None:
            remaining = min(batch_size, max_passages - embedded)
            if remaining <= 0:
                break
        batch = await persistence.fetch_passages_needing_embedding(
            db, model_name=model_name, text_hash_of=hash_text, limit=remaining
        )
        if not batch:
            break
        vectors = await provider.embed([text for _, _, text in batch], is_query=False)
        for (passage_id, pmid, passage_text), vector in zip(batch, vectors):
            await persistence.upsert_embedding(
                db,
                passage_id=passage_id,
                pmid=pmid,
                model_name=model_name,
                embedding=vector,
                text_hash=hash_text(passage_text),
            )
        await db.commit()
        embedded += len(batch)
        logger.info("embedded %s passages (model=%s)", embedded, model_name)
    return embedded
