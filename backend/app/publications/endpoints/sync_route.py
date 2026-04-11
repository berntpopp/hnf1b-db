"""``POST /api/v2/publications/sync`` endpoint + background task."""
# ruff: noqa: E501 - SQL queries are more readable when not line-wrapped

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import async_session_maker, get_db
from app.publications.service import (
    PubMedAPIError,
    PubMedNotFoundError,
    PubMedRateLimitError,
    PubMedTimeoutError,
    get_publication_metadata,
)

from .schemas import SyncResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["publications"])


async def _sync_publications_background() -> None:
    """Background task to sync all publication metadata from PubMed.

    Opens its own database session via ``async_session_maker`` — the
    request-scoped session from ``Depends(get_db)`` is closed by the
    time ``BackgroundTasks`` fires, so reusing it would fail on the
    first query. Mirrors the admin sync service pattern.

    1. Get all unique PMIDs from phenopackets
    2. Filter out already-stored entries
    3. Batch fetch from PubMed (respecting rate limits)
    4. Store permanently in publication_metadata table
    """
    logger.info("Starting background publication sync")

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

        stored_query = text("""
            SELECT REPLACE(pmid, 'PMID:', '') as pmid
            FROM publication_metadata
        """)
        stored_result = await db.execute(stored_query)
        stored_pmids = {row.pmid for row in stored_result.fetchall()}

        to_fetch = [pmid for pmid in all_pmids if pmid not in stored_pmids]

        logger.info(
            "Need to fetch %s PMIDs (%s already stored)",
            len(to_fetch),
            len(stored_pmids),
        )

        fetched = 0
        errors = 0

        for pmid in to_fetch:
            try:
                await get_publication_metadata(pmid, db, fetched_by="sync")
                fetched += 1
                if fetched % 10 == 0:
                    logger.info("Synced %s/%s publications", fetched, len(to_fetch))
            except (
                PubMedAPIError,
                PubMedTimeoutError,
                PubMedRateLimitError,
                PubMedNotFoundError,
                SQLAlchemyError,
            ) as exc:
                errors += 1
                logger.warning("Failed to fetch %s: %s", pmid, exc)

            # Rate limiting: 3 req/sec without API key = ~333ms between requests.
            await asyncio.sleep(0.35)

        logger.info("Sync complete: %s fetched, %s errors", fetched, errors)


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
