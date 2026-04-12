"""Admin sync endpoints for reference data (GRCh38 + HNF1B + chr17q12 genes).

Owns ``POST /admin/sync/reference/init``, ``POST /admin/sync/genes``,
and ``GET /admin/sync/genes/status``.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin._common import progress_response_from_state
from app.api.admin.schemas import SyncProgressResponse, SyncTaskResponse
from app.api.admin.sync_service import run_genes_sync, run_reference_init
from app.api.admin.task_state import TaskKind, get_sync_task_store
from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.reference.service import get_reference_data_status

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


@router.post(
    "/sync/reference/init",
    response_model=SyncTaskResponse,
    summary="Initialize reference data (GRCh38 + HNF1B)",
    description="""
    Initializes core reference data required for the application:

    **What it creates:**
    - GRCh38 genome assembly entry
    - HNF1B gene with coordinates
    - NM_000458.4 canonical transcript
    - 9 HNF1B exons
    - 4 protein domains (UniProt P35680)

    **Idempotent:** Safe to call multiple times - skips existing data.

    **Requires:** Admin authentication
    """,
)
async def start_reference_init(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start reference data initialization task."""
    ref_status = await get_reference_data_status(db)

    if ref_status.has_grch38 and ref_status.has_hnf1b:
        return SyncTaskResponse(
            task_id="none",
            status="completed",
            message="Reference data already initialized (GRCh38 + HNF1B present)",
            items_to_process=0,
            estimated_time_seconds=0,
        )

    store = get_sync_task_store()
    # genome + gene + transcript + 9 exons + 4 domains
    state = await store.create(TaskKind.REFERENCE, total=15)

    background_tasks.add_task(run_reference_init, state.task_id, store)

    logger.info(
        "Reference data init initiated by %s",
        current_user.username,
        extra={"task_id": state.task_id},
    )

    return SyncTaskResponse(
        task_id=state.task_id,
        status="pending",
        message="Reference data initialization queued",
        items_to_process=15,
        estimated_time_seconds=5,
    )


@router.post(
    "/sync/genes",
    response_model=SyncTaskResponse,
    summary="Sync chr17q12 region genes from Ensembl",
    description="""
    Syncs all genes in the chr17q12 region from Ensembl REST API.

    **Process:**
    1. Ensures GRCh38 genome exists
    2. Fetches ~70 genes from Ensembl for region 17:36000000-39900000
    3. Filters for protein_coding, lncRNA, miRNA, snRNA, snoRNA
    4. Creates or updates gene records

    **Key genes:** LHX1, HNF1B, ACACA, AATF, ZNHIT3, PIGW, GGNBP2

    **Rate limiting:** Respects Ensembl 15 req/sec limit

    **Requires:** Admin authentication
    """,
)
async def start_genes_sync(
    background_tasks: BackgroundTasks,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start chr17q12 gene sync task."""
    ref_status = await get_reference_data_status(db)

    if not force and ref_status.chr17q12_gene_count >= 60:
        return SyncTaskResponse(
            task_id="none",
            status="completed",
            message=(
                f"chr17q12 genes already synced "
                f"({ref_status.chr17q12_gene_count} genes present)"
            ),
            items_to_process=0,
            estimated_time_seconds=0,
        )

    store = get_sync_task_store()
    state = await store.create(TaskKind.GENES, total=70)

    background_tasks.add_task(run_genes_sync, state.task_id, store)

    logger.info(
        "Gene sync initiated by %s",
        current_user.username,
        extra={"task_id": state.task_id},
    )

    return SyncTaskResponse(
        task_id=state.task_id,
        status="pending",
        message="chr17q12 gene sync queued",
        items_to_process=70,
        estimated_time_seconds=10,
    )


@router.get(
    "/sync/genes/status",
    response_model=SyncProgressResponse,
    summary="Get gene sync progress",
    description="Returns the current status of the gene sync task.",
)
async def get_genes_sync_status(
    task_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get gene sync task status."""
    store = get_sync_task_store()

    if task_id is None:
        latest = await store.get_latest(TaskKind.GENES)
        if latest is None:
            ref_status = await get_reference_data_status(db)
            return SyncProgressResponse(
                task_id="none",
                status="idle",
                progress=100.0 if ref_status.chr17q12_gene_count >= 60 else 0,
                processed=ref_status.chr17q12_gene_count,
                total=70,
                errors=0,
                started_at=None,
                completed_at=None,
            )
        return progress_response_from_state(latest)

    state = await store.get(task_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return progress_response_from_state(state)
