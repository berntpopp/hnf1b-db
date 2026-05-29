"""``POST /api/v2/publications/sync`` endpoint + background task."""
# noqa: visibility: admin sync needs to discover un-synced PMIDs across all states (require_admin guard enforced at route level)
# ruff: noqa: E501 - SQL queries are more readable when not line-wrapped

from __future__ import annotations

import logging

import aiohttp
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.core.config import settings
from app.database import async_session_maker, get_db
from app.publications.fulltext.orchestrator import (
    sync_publications as run_publication_sync,
)
from app.publications.service import get_publication_metadata

from .schemas import SyncResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["publications"])


async def _sync_publications_background() -> None:
    """Background task to sync publication abstracts + open-access full text.

    Opens its own database session via ``async_session_maker`` — the
    request-scoped session from ``Depends(get_db)`` is closed by the time
    ``BackgroundTasks`` fires, so reusing it would fail on the first query.

    1. Get all unique PMIDs referenced by published phenopackets.
    2. Ensure base citation metadata (title/authors/...) via the PubMed service.
    3. Fetch abstracts (efetch) + license-gated open-access full text, chunk
       into passages, and persist — with per-PMID error isolation.
    """
    logger.info("Starting background publication full-text sync")

    async with async_session_maker() as db:
        query = text("""
            SELECT DISTINCT REPLACE(ext_ref->>'id', 'PMID:', '') as pmid
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
            WHERE ext_ref->>'id' LIKE 'PMID:%'
              AND deleted_at IS NULL
        """)
        result = await db.execute(query)
        all_pmids = [row.pmid for row in result.fetchall()]
        logger.info("Found %s unique PMIDs in phenopackets", len(all_pmids))

        async def _ensure_metadata(pmid: str) -> None:
            # Populate title/authors/journal/year/doi via the existing PubMed
            # (esummary) service; process_publication then fills abstract +
            # coverage. Cached PMIDs are not re-fetched.
            await get_publication_metadata(pmid, db, fetched_by="sync")

        async with aiohttp.ClientSession() as session:
            counts = await run_publication_sync(
                db,
                all_pmids,
                session=session,
                allowed_licenses=settings.publications_rag.allowed_licenses,
                chunk_max_tokens=settings.publications_rag.chunk_max_tokens,
                chunk_overlap_tokens=settings.publications_rag.chunk_overlap_tokens,
                abstract_api_key=settings.PUBMED_API_KEY,
                ensure_metadata=_ensure_metadata,
            )

        logger.info(
            "Publication full-text sync complete",
            extra={
                "processed": counts.processed,
                "abstracts_fetched": counts.abstracts_fetched,
                "full_text_fetched": counts.full_text_fetched,
                "license_skipped": counts.license_skipped,
                "errors": counts.errors,
            },
        )


@router.post(
    "/sync",
    response_model=SyncResponse,
    summary="Sync publication metadata from PubMed (admin only)",
    description="""
    Batch sync all publication metadata from PubMed for PMIDs found in phenopackets.

    **Requires:** Admin authentication

    **Process:**
    1. Find all unique PMIDs referenced in phenopackets
    2. Filter out already-stored entries
    3. Queue background task to fetch remaining from PubMed
    4. Respects PubMed rate limits (3 req/sec without API key)

    **Note:** This is an async operation. The endpoint returns immediately
    and fetching continues in the background.
    """,
    dependencies=[Depends(require_admin)],
)
async def sync_publications(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Sync all publication metadata from PubMed."""
    all_query = text("""
        SELECT COUNT(DISTINCT REPLACE(ext_ref->>'id', 'PMID:', '')) as count
        FROM phenopackets,
             jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
        WHERE ext_ref->>'id' LIKE 'PMID:%'
          AND deleted_at IS NULL
    """)
    all_result = await db.execute(all_query)
    total_pmids = all_result.scalar() or 0

    stored_query = text("""
        SELECT COUNT(*) as count
        FROM publication_metadata
    """)
    stored_result = await db.execute(stored_query)
    already_stored = stored_result.scalar() or 0

    to_fetch = max(0, total_pmids - already_stored)

    background_tasks.add_task(_sync_publications_background)

    logger.info(
        "Publication sync initiated",
        extra={"total": total_pmids, "stored": already_stored, "to_fetch": to_fetch},
    )

    return SyncResponse(
        status="sync_started",
        message=f"Background sync initiated for {to_fetch} publications",
        total_pmids=total_pmids,
        already_stored=already_stored,
        to_fetch=to_fetch,
    )
