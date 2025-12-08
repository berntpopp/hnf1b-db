"""Admin API endpoints for system management operations.

Provides admin-only endpoints for:
- System status and statistics
- Data sync operations (publications, annotations)
- Database maintenance tasks
"""
# ruff: noqa: E501 - SQL queries are more readable when not line-wrapped

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.database import get_db
from app.models.user import User
from app.publications.service import get_publication_metadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/admin", tags=["admin"])


# =============================================================================
# Response Models
# =============================================================================


class DataSyncStatus(BaseModel):
    """Status of a data synchronization category."""

    name: str = Field(..., description="Name of the data category")
    total: int = Field(..., description="Total items in database")
    synced: int = Field(..., description="Items with complete metadata")
    pending: int = Field(..., description="Items pending sync")
    last_sync: Optional[str] = Field(None, description="Last sync timestamp")


class SystemStatusResponse(BaseModel):
    """System status response with data sync information."""

    status: str = Field(default="healthy", description="Overall system status")
    timestamp: str = Field(..., description="Current server timestamp")
    database: dict = Field(..., description="Database statistics")
    sync_status: list[DataSyncStatus] = Field(
        ..., description="Status of various data sync operations"
    )


class SyncTaskResponse(BaseModel):
    """Response for sync task initiation."""

    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Human-readable message")
    items_to_process: int = Field(..., description="Number of items to process")
    estimated_time_seconds: Optional[int] = Field(
        None, description="Estimated time to complete"
    )


class SyncProgressResponse(BaseModel):
    """Response for sync task progress."""

    task_id: str = Field(..., description="Task identifier")
    status: str = Field(
        ..., description="Task status (pending/running/completed/failed)"
    )
    progress: float = Field(..., description="Progress percentage (0-100)")
    processed: int = Field(..., description="Items processed")
    total: int = Field(..., description="Total items")
    errors: int = Field(default=0, description="Number of errors")
    started_at: Optional[str] = Field(None, description="Task start time")
    completed_at: Optional[str] = Field(None, description="Task completion time")


# In-memory task tracking (for simplicity - could use Redis for production)
_sync_tasks: dict = {}


# =============================================================================
# System Status Endpoint
# =============================================================================


@router.get(
    "/status",
    response_model=SystemStatusResponse,
    summary="Get system status and sync statistics",
    description="""
    Returns comprehensive system status including:
    - Database statistics (phenopackets, publications, variants)
    - Data sync status (publications metadata, VEP annotations)
    - Last sync timestamps

    **Requires:** Admin authentication
    """,
    dependencies=[Depends(require_admin)],
)
async def get_system_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get system status and data sync statistics."""
    # Database statistics
    stats_query = text("""
        SELECT
            (SELECT COUNT(*) FROM phenopackets WHERE deleted_at IS NULL) as phenopackets_count,
            (SELECT COUNT(*) FROM users WHERE is_active = true) as users_count,
            (SELECT COUNT(*) FROM publication_metadata) as publications_cached
    """)
    stats_result = await db.execute(stats_query)
    stats = stats_result.fetchone()
    if stats is None:
        raise HTTPException(status_code=500, detail="Failed to fetch database statistics")

    # Publication sync status
    pub_query = text("""
        WITH phenopacket_pmids AS (
            SELECT DISTINCT ext_ref->>'id' as pmid
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
            WHERE ext_ref->>'id' LIKE 'PMID:%'
              AND deleted_at IS NULL
        )
        SELECT
            COUNT(*) as total,
            COUNT(pm.pmid) as synced
        FROM phenopacket_pmids pp
        LEFT JOIN publication_metadata pm ON pm.pmid = pp.pmid
    """)
    pub_result = await db.execute(pub_query)
    pub_stats = pub_result.fetchone()
    if pub_stats is None:
        raise HTTPException(status_code=500, detail="Failed to fetch publication statistics")

    # Get last publication sync time
    last_pub_sync_query = text("""
        SELECT MAX(fetched_at) as last_sync
        FROM publication_metadata
    """)
    last_pub_result = await db.execute(last_pub_sync_query)
    last_pub_sync = last_pub_result.scalar()

    # VEP annotation status
    vep_query = text("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (
                WHERE phenopacket->'interpretations'->0->'diagnosis'->'genomicInterpretations'->0
                    ->'variantInterpretation'->'variationDescriptor'->'extensions' @> '[{"name": "vep_annotation"}]'
            ) as annotated
        FROM phenopackets
        WHERE deleted_at IS NULL
          AND phenopacket @> '{"interpretations": [{}]}'
    """)
    vep_result = await db.execute(vep_query)
    vep_stats = vep_result.fetchone()
    if vep_stats is None:
        raise HTTPException(status_code=500, detail="Failed to fetch VEP statistics")

    sync_status = [
        DataSyncStatus(
            name="Publication Metadata",
            total=pub_stats.total or 0,
            synced=pub_stats.synced or 0,
            pending=(pub_stats.total or 0) - (pub_stats.synced or 0),
            last_sync=last_pub_sync.isoformat() if last_pub_sync else None,
        ),
        DataSyncStatus(
            name="VEP Annotations",
            total=vep_stats.total or 0,
            synced=vep_stats.annotated or 0,
            pending=(vep_stats.total or 0) - (vep_stats.annotated or 0),
            last_sync=None,  # Could track this with a separate table
        ),
    ]

    return SystemStatusResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        database={
            "phenopackets": stats.phenopackets_count or 0,
            "users": stats.users_count or 0,
            "publications_cached": stats.publications_cached or 0,
        },
        sync_status=sync_status,
    )


# =============================================================================
# Publication Sync Endpoints
# =============================================================================


async def _run_publication_sync(task_id: str, db: AsyncSession) -> None:
    """Background task to sync publication metadata."""
    task = _sync_tasks.get(task_id)
    if not task:
        return

    task["status"] = "running"
    task["started_at"] = datetime.now(timezone.utc).isoformat()

    try:
        # Get PMIDs to sync
        query = text("""
            WITH phenopacket_pmids AS (
                SELECT DISTINCT REPLACE(ext_ref->>'id', 'PMID:', '') as pmid
                FROM phenopackets,
                     jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
                WHERE ext_ref->>'id' LIKE 'PMID:%'
                  AND deleted_at IS NULL
            )
            SELECT pp.pmid
            FROM phenopacket_pmids pp
            LEFT JOIN publication_metadata pm ON pm.pmid = CONCAT('PMID:', pp.pmid)
            WHERE pm.pmid IS NULL
        """)
        result = await db.execute(query)
        pmids_to_sync = [row.pmid for row in result.fetchall()]

        task["total"] = len(pmids_to_sync)
        task["processed"] = 0
        task["errors"] = 0

        for pmid in pmids_to_sync:
            try:
                await get_publication_metadata(pmid, db, fetched_by="admin_sync")
                task["processed"] += 1
            except Exception as e:
                task["errors"] += 1
                logger.warning(f"Failed to sync PMID {pmid}: {e}")

            task["progress"] = (
                (task["processed"] / task["total"] * 100) if task["total"] > 0 else 100
            )

            # Rate limiting
            await asyncio.sleep(0.35)

        task["status"] = "completed"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"Publication sync completed: {task['processed']} synced, {task['errors']} errors"
        )

    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
        logger.error(f"Publication sync failed: {e}")


@router.post(
    "/sync/publications",
    response_model=SyncTaskResponse,
    summary="Start publication metadata sync",
    description="""
    Initiates a background task to sync publication metadata from PubMed.

    **Process:**
    1. Identifies PMIDs in phenopackets without cached metadata
    2. Fetches metadata from PubMed API (respecting rate limits)
    3. Stores permanently in database

    **Requires:** Admin authentication
    """,
    dependencies=[Depends(require_admin)],
)
async def start_publication_sync(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Start publication metadata sync task."""
    # Check for pending items
    query = text("""
        WITH phenopacket_pmids AS (
            SELECT DISTINCT REPLACE(ext_ref->>'id', 'PMID:', '') as pmid
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
            WHERE ext_ref->>'id' LIKE 'PMID:%'
              AND deleted_at IS NULL
        )
        SELECT COUNT(*) as count
        FROM phenopacket_pmids pp
        LEFT JOIN publication_metadata pm ON pm.pmid = CONCAT('PMID:', pp.pmid)
        WHERE pm.pmid IS NULL
    """)
    result = await db.execute(query)
    pending_count = result.scalar() or 0

    if pending_count == 0:
        return SyncTaskResponse(
            task_id="none",
            status="completed",
            message="All publications already synced",
            items_to_process=0,
            estimated_time_seconds=0,
        )

    # Create task
    task_id = f"pub_sync_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    _sync_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "processed": 0,
        "total": pending_count,
        "errors": 0,
        "started_at": None,
        "completed_at": None,
    }

    # Queue background task
    background_tasks.add_task(_run_publication_sync, task_id, db)

    # Estimate time (0.35s per item + overhead)
    estimated_seconds = int(pending_count * 0.4)

    logger.info(
        f"Publication sync initiated by {current_user.username}",
        extra={"task_id": task_id, "items": pending_count},
    )

    return SyncTaskResponse(
        task_id=task_id,
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
    # If no task_id, get the most recent task
    if task_id is None:
        # Find most recent task
        if not _sync_tasks:
            # Return current sync status from database
            query = text("""
                WITH phenopacket_pmids AS (
                    SELECT DISTINCT ext_ref->>'id' as pmid
                    FROM phenopackets,
                         jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
                    WHERE ext_ref->>'id' LIKE 'PMID:%'
                      AND deleted_at IS NULL
                )
                SELECT
                    COUNT(*) as total,
                    COUNT(pm.pmid) as synced
                FROM phenopacket_pmids pp
                LEFT JOIN publication_metadata pm ON pm.pmid = pp.pmid
            """)
            result = await db.execute(query)
            stats = result.fetchone()
            if stats is None:
                raise HTTPException(
                    status_code=500, detail="Failed to fetch sync statistics"
                )

            return SyncProgressResponse(
                task_id="none",
                status="idle",
                progress=100.0
                if stats.total == stats.synced
                else (stats.synced / stats.total * 100 if stats.total > 0 else 0),
                processed=stats.synced or 0,
                total=stats.total or 0,
                errors=0,
                started_at=None,
                completed_at=None,
            )

        # Get most recent task
        task_id = max(_sync_tasks.keys())

    task = _sync_tasks.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    return SyncProgressResponse(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        processed=task["processed"],
        total=task["total"],
        errors=task["errors"],
        started_at=task.get("started_at"),
        completed_at=task.get("completed_at"),
    )


# =============================================================================
# Data Statistics Endpoint
# =============================================================================


@router.get(
    "/statistics",
    summary="Get detailed database statistics",
    description="Returns detailed statistics about database contents.",
    dependencies=[Depends(require_admin)],
)
async def get_statistics(
    db: AsyncSession = Depends(get_db),
):
    """Get detailed database statistics for admin dashboard."""
    query = text("""
        SELECT
            -- Phenopackets
            (SELECT COUNT(*) FROM phenopackets WHERE deleted_at IS NULL) as phenopackets_total,
            (SELECT COUNT(*) FROM phenopackets WHERE deleted_at IS NOT NULL) as phenopackets_deleted,

            -- Users
            (SELECT COUNT(*) FROM users) as users_total,
            (SELECT COUNT(*) FROM users WHERE is_active = true) as users_active,
            (SELECT COUNT(*) FROM users WHERE role = 'admin') as users_admin,
            (SELECT COUNT(*) FROM users WHERE role = 'curator') as users_curator,

            -- Publications
            (SELECT COUNT(*) FROM publication_metadata) as publications_cached,
            (SELECT COUNT(DISTINCT ext_ref->>'id')
             FROM phenopackets,
                  jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
             WHERE ext_ref->>'id' LIKE 'PMID:%'
               AND deleted_at IS NULL) as publications_referenced,

            -- Variants (approximate count from interpretations)
            (SELECT COUNT(*)
             FROM phenopackets
             WHERE deleted_at IS NULL
               AND phenopacket @> '{"interpretations": [{}]}') as phenopackets_with_variants
    """)

    result = await db.execute(query)
    stats = result.fetchone()
    if stats is None:
        raise HTTPException(status_code=500, detail="Failed to fetch statistics")

    return {
        "phenopackets": {
            "total": stats.phenopackets_total or 0,
            "deleted": stats.phenopackets_deleted or 0,
            "with_variants": stats.phenopackets_with_variants or 0,
        },
        "users": {
            "total": stats.users_total or 0,
            "active": stats.users_active or 0,
            "admins": stats.users_admin or 0,
            "curators": stats.users_curator or 0,
        },
        "publications": {
            "referenced": stats.publications_referenced or 0,
            "cached": stats.publications_cached or 0,
            "pending_sync": (stats.publications_referenced or 0)
            - (stats.publications_cached or 0),
        },
    }
