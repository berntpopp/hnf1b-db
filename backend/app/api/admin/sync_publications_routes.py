"""Admin sync endpoints for publication metadata.

Owns ``POST /admin/sync/publications`` (start a sync task) and
``GET /admin/sync/publications/status`` (poll its progress).
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin import queries
from app.api.admin._common import (
    idle_progress_response,
    progress_response_from_state,
)
from app.api.admin.schemas import SyncProgressResponse, SyncTaskResponse
from app.api.admin.sync_service import run_publication_sync
from app.api.admin.task_state import TaskKind, get_sync_task_store
from app.auth import require_admin
from app.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


@router.post(
    "/sync/publications",
    response_model=SyncTaskResponse,
    summary="Start publication metadata sync",
    description="""
    Initiates a background task to sync publication metadata from PubMed.

    **Process:**
    1. Identifies PMIDs in phenopackets without cached metadata (or all if force=true)
    2. Fetches metadata from PubMed API (respecting rate limits)
    3. Stores permanently in database

    **Parameters:**
    - force: If true, re-fetch all publications even if already synced

    **Requires:** Admin authentication
    """,
    dependencies=[Depends(require_admin)],
)
async def start_publication_sync(
    background_tasks: BackgroundTasks,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Start publication metadata sync task."""
    if force:
        all_pmids = await queries.fetch_all_referenced_pmids(db)
        pending_count = len(all_pmids)
        if pending_count > 0:
            await queries.delete_all_publication_metadata(db)
            logger.info(
                "Force refresh: deleted existing metadata for %s publications",
                pending_count,
            )
    else:
        pending_count = await queries.count_pending_publication_sync(db)

    if pending_count == 0:
        return SyncTaskResponse(
            task_id="none",
            status="completed",
            message="All publications already synced",
            items_to_process=0,
            estimated_time_seconds=0,
        )

    store = get_sync_task_store()
    state = await store.create(TaskKind.PUBLICATION, total=pending_count)

    background_tasks.add_task(run_publication_sync, state.task_id, store)

    # Estimate time (0.35s per item + overhead)
    estimated_seconds = int(pending_count * 0.4)

    logger.info(
        "Publication sync initiated by %s",
        current_user.username,
        extra={"task_id": state.task_id, "items": pending_count},
    )

    return SyncTaskResponse(
        task_id=state.task_id,
        status="pending",
        message=f"Sync task queued for {pending_count} publications",
        items_to_process=pending_count,
        estimated_time_seconds=estimated_seconds,
    )


@router.get(
    "/sync/publications/status",
    response_model=SyncProgressResponse,
    summary="Get publication sync progress",
    description="Returns the current status of the publication sync task.",
    dependencies=[Depends(require_admin)],
)
async def get_publication_sync_status(
    task_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get publication sync task status."""
    store = get_sync_task_store()

    if task_id is None:
        latest = await store.get_latest(TaskKind.PUBLICATION)
        if latest is None:
            snapshot = await queries.fetch_current_publication_sync_snapshot(db)
            return idle_progress_response(
                synced=snapshot["synced"], total=snapshot["total"]
            )
        return progress_response_from_state(latest)

    state = await store.get(task_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return progress_response_from_state(state)
