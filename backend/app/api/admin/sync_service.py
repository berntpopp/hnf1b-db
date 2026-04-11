"""Background sync-service orchestration for admin operations.

Extracted from the old flat ``app/api/admin_endpoints.py`` during Wave 4.
Each ``run_*`` coroutine is enqueued by the corresponding endpoint
(``/sync/publications``, ``/sync/variants``, ``/sync/reference/init``,
``/sync/genes``) via ``BackgroundTasks`` and runs outside the request
lifecycle — so the task creates its own database session and updates
the durable :class:`SyncTaskStore` instead of the old in-memory dict.

The raw-SQL fragments that compute pending work live in the
``queries`` sibling module (admin-owned) and in
``app.phenopackets.routers.aggregations.sql_fragments`` (shared with
other modules).
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.admin.queries import fetch_pmids_to_sync
from app.api.admin.task_state import SyncTaskStore
from app.core.config import settings
from app.database import async_session_maker
from app.phenopackets.routers.aggregations.sql_fragments import (
    get_pending_variants_query,
)
from app.publications.service import PubMedError, get_publication_metadata
from app.reference.service import initialize_reference_data, sync_chr17q12_genes
from app.variants.service import VEPError, get_variant_annotations_batch

logger = logging.getLogger(__name__)


async def run_publication_sync(task_id: str, store: SyncTaskStore) -> None:
    """Background task: sync PubMed metadata for every un-cached PMID.

    Creates its own database session (the request session is gone by
    the time a ``BackgroundTasks`` callback fires). Progress is flushed
    to the cache after every item so an admin polling the progress
    endpoint sees live updates.
    """
    await store.mark_running(task_id)

    try:
        async with async_session_maker() as db:
            pmids_to_sync = await fetch_pmids_to_sync(db)
            await store.update_counts(
                task_id,
                processed=0,
                total=len(pmids_to_sync),
                errors=0,
            )

            for pmid in pmids_to_sync:
                try:
                    await get_publication_metadata(pmid, db, fetched_by="admin_sync")
                    await store.increment_processed(task_id)
                except (PubMedError, SQLAlchemyError, asyncio.TimeoutError) as exc:
                    await store.increment_errors(task_id, count=1)
                    logger.warning("Failed to sync PMID %s: %s", pmid, exc)

                # Rate limit: NCBI E-Utils tolerates 3 req/sec for anon clients
                await asyncio.sleep(0.35)

        await store.complete(task_id)
        final = await store.get(task_id)
        logger.info(
            "Publication sync completed: %s synced, %s errors",
            final.processed if final else "?",
            final.errors if final else "?",
        )

    except Exception as exc:  # noqa: BLE001
        # Best-effort: never leave a task stuck in "running" state. The
        # broad Exception is explicitly allowed — this is an end-of-task
        # failure handler, not a silent swallow.
        await store.fail(task_id, str(exc))
        logger.error("Publication sync failed: %s", exc)


async def run_variant_sync(task_id: str, store: SyncTaskStore) -> None:
    """Background task: sync VEP annotations for every pending variant."""
    await store.mark_running(task_id)

    try:
        async with async_session_maker() as db:
            query = text(get_pending_variants_query())
            result = await db.execute(query)
            variants_to_sync = [row.variant_id for row in result.fetchall()]

            await store.update_counts(
                task_id,
                processed=0,
                total=len(variants_to_sync),
                errors=0,
            )

            batch_size = settings.external_apis.vep.batch_size
            for i in range(0, len(variants_to_sync), batch_size):
                batch = variants_to_sync[i : i + batch_size]
                try:
                    results = await get_variant_annotations_batch(
                        batch, db, fetched_by="admin_sync", batch_size=batch_size
                    )
                    for vid in batch:
                        if vid in results and results[vid]:
                            await store.increment_processed(task_id)
                        else:
                            await store.increment_errors(task_id, count=1)
                except (VEPError, SQLAlchemyError, asyncio.TimeoutError) as exc:
                    await store.increment_errors(task_id, count=len(batch))
                    logger.warning("Failed to sync variant batch: %s", exc)

                # Rate limiting between batches — longer pause to avoid 503s
                await asyncio.sleep(1.0)

        await store.complete(task_id)
        final = await store.get(task_id)
        logger.info(
            "Variant sync completed: %s synced, %s errors",
            final.processed if final else "?",
            final.errors if final else "?",
        )

    except (SQLAlchemyError, VEPError) as exc:
        await store.fail(task_id, str(exc))
        logger.error("Variant sync failed: %s", exc)


async def run_reference_init(task_id: str, store: SyncTaskStore) -> None:
    """Background task: initialise reference data (GRCh38 + HNF1B core)."""
    await store.mark_running(task_id)

    try:
        async with async_session_maker() as db:
            result = await initialize_reference_data(db)
            await store.update_counts(
                task_id,
                processed=result.imported,
                total=result.total,
                errors=result.errors,
            )

        await store.complete(task_id)
        logger.info("Reference data init completed: %s items created", result.imported)

    except (httpx.HTTPError, SQLAlchemyError) as exc:
        await store.fail(task_id, str(exc))
        logger.error("Reference data init failed: %s", exc)


async def run_genes_sync(task_id: str, store: SyncTaskStore) -> None:
    """Background task: sync chr17q12 genes from Ensembl REST."""
    await store.mark_running(task_id)

    try:
        async with async_session_maker() as db:
            result = await sync_chr17q12_genes(db)
            await store.update_counts(
                task_id,
                processed=result.imported + result.updated,
                total=result.total,
                errors=result.errors,
            )

        await store.complete(task_id)
        logger.info(
            "Gene sync completed: %s imported, %s updated, %s errors",
            result.imported,
            result.updated,
            result.errors,
        )

    except (httpx.HTTPError, SQLAlchemyError) as exc:
        await store.fail(task_id, str(exc))
        logger.error("Gene sync failed: %s", exc)
