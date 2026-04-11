"""Admin sync endpoints for VEP variant annotations.

Owns ``POST /admin/sync/variants`` (start the sync task) and
``GET /admin/sync/variants/status`` (poll its progress).
"""
# ruff: noqa: E501 - SQL queries are more readable when not line-wrapped

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin._common import (
    idle_progress_response,
    progress_response_from_state,
)
from app.api.admin.schemas import SyncProgressResponse, SyncTaskResponse
from app.api.admin.sync_service import run_variant_sync
from app.api.admin.task_state import TaskKind, get_sync_task_store
from app.auth import require_admin
from app.database import get_db
from app.models.user import User
from app.phenopackets.routers.aggregations.sql_fragments import (
    UNIQUE_VARIANTS_CTE,
    get_pending_variants_count_query,
    get_unique_variants_query,
    get_variant_sync_status_query,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


@router.post(
    "/sync/variants",
    response_model=SyncTaskResponse,
    summary="Start variant annotation sync",
    description="""
    Initiates a background task to sync variant annotations from Ensembl VEP.

    **Process:**
    1. Identifies unique variants in phenopackets without cached annotations (or all if force=true)
    2. Fetches annotations from VEP API (batches of 200, respecting rate limits)
    3. Stores permanently in database

    **Parameters:**
    - force: If true, re-fetch all variant annotations even if already cached

    **Key optimization:** Only syncs unique variants, not per-phenopacket.

    **Requires:** Admin authentication
    """,
    dependencies=[Depends(require_admin)],
)
async def start_variant_sync(
    background_tasks: BackgroundTasks,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Start variant annotation sync task."""
    if force:
        # Force refresh: get all unique variants and delete existing cached data.
        query = text(get_unique_variants_query())
        result = await db.execute(query)
        all_variants = [row.variant_id for row in result.fetchall()]
        pending_count = len(all_variants)

        if pending_count > 0:
            delete_query = text(
                f"""
                DELETE FROM variant_annotations
                WHERE variant_id IN (
                    WITH {UNIQUE_VARIANTS_CTE}
                    SELECT variant_id FROM unique_variants
                )
                """
            )
            await db.execute(delete_query)
            await db.commit()
            logger.info(
                "Force refresh: deleted existing annotations for %s variants",
                pending_count,
            )
    else:
        # Count variants that actually need syncing (pending, not total),
        # matching the set that ``run_variant_sync`` will iterate via
        # ``get_pending_variants_query()``. Using the total "unique
        # variants" count here would report the wrong ``items_to_process``
        # and skew the progress bar in the admin UI.
        query = text(get_pending_variants_count_query())
        result = await db.execute(query)
        pending_count = int(result.scalar() or 0)

    if pending_count == 0:
        return SyncTaskResponse(
            task_id="none",
            status="completed",
            message="All variants already annotated",
            items_to_process=0,
            estimated_time_seconds=0,
        )

    store = get_sync_task_store()
    state = await store.create(TaskKind.VARIANT, total=pending_count)

    background_tasks.add_task(run_variant_sync, state.task_id, store)

    # Estimate time (batch of 50 takes ~3-4s + overhead)
    estimated_seconds = int((pending_count / 50 + 1) * 4)

    logger.info(
        "Variant sync initiated by %s",
        current_user.username,
        extra={"task_id": state.task_id, "items": pending_count},
    )

    return SyncTaskResponse(
        task_id=state.task_id,
        status="pending",
        message=f"Sync task queued for {pending_count} variants",
        items_to_process=pending_count,
        estimated_time_seconds=estimated_seconds,
    )


@router.get(
    "/sync/variants/status",
    response_model=SyncProgressResponse,
    summary="Get variant sync progress",
    description="Returns the current status of the variant annotation sync task.",
    dependencies=[Depends(require_admin)],
)
async def get_variant_sync_status(
    task_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get variant annotation sync task status."""
    store = get_sync_task_store()

    if task_id is None:
        latest = await store.get_latest(TaskKind.VARIANT)
        if latest is None:
            query = text(get_variant_sync_status_query())
            result = await db.execute(query)
            stats = result.fetchone()
            if stats is None:
                raise HTTPException(
                    status_code=500, detail="Failed to fetch sync statistics"
                )
            return idle_progress_response(
                synced=stats.synced or 0, total=stats.total or 0
            )
        return progress_response_from_state(latest)

    state = await store.get(task_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return progress_response_from_state(state)
