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
from app.core.config import settings
from app.database import async_session_maker, get_db
from app.models.user import User
from app.phenopackets.routers.aggregations.sql_fragments import (
    UNIQUE_VARIANTS_CTE,
    get_pending_variants_query,
    get_unique_variants_query,
    get_variant_sync_status_query,
)
from app.publications.service import get_publication_metadata
from app.reference.service import (
    get_reference_data_status,
    initialize_reference_data,
    sync_chr17q12_genes,
)
from app.variants.service import get_variant_annotations_batch

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

    # VEP annotation status - count unique variants by VRS ID (matches summary endpoint)
    # and count synced VCF expressions (what VEP can actually annotate)
    # Note: Some CNVs share the same VCF expression but have different VRS IDs
    # (e.g., different end positions), so total may exceed synced after full sync
    vep_query = text("""
        WITH unique_vrs_ids AS (
            -- Count total unique variants by VRS ID (variationDescriptor.id)
            -- This matches the summary endpoint count per GA4GH VRS 2.0 spec
            SELECT DISTINCT vd->>'id' as vrs_id
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                 jsonb_array_elements(
                    interp->'diagnosis'->'genomicInterpretations'
                 ) as gi,
                 LATERAL (
                     SELECT gi->'variantInterpretation'->'variationDescriptor' as vd
                 ) vd_lateral
            WHERE vd_lateral.vd IS NOT NULL
              AND vd_lateral.vd->>'id' IS NOT NULL
              AND p.deleted_at IS NULL
        ),
        unique_vcf_variants AS (
            -- Count unique VCF expressions (what VEP annotates)
            SELECT DISTINCT
                UPPER(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(expr->>'value', '^chr', '', 'i'),
                        ':',
                        '-',
                        'g'
                    )
                ) as variant_id
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'interpretations') as interp,
                 jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
                 jsonb_array_elements(
                     gi->'variantInterpretation'->'variationDescriptor'->'expressions'
                 ) as expr
            WHERE expr->>'syntax' = 'vcf'
              AND deleted_at IS NULL
              AND (
                  -- SNVs and small indels
                  expr->>'value' ~ '^(chr)?[0-9XYM]+-[0-9]+-[ACGT]+-[ACGT]+$'
                  OR
                  -- CNVs with END position (CHROM-POS-END-REF-<TYPE>) - primary format
                  -- Per VCF 4.3 spec: symbolic alleles need END for unique identification
                  expr->>'value' ~ '^(chr)?[0-9XYM]+-[0-9]+-[0-9]+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$'
                  OR
                  -- CNVs in region format (17:start-end:DEL)
                  expr->>'value' ~ '^(chr)?[0-9XYM]+[:-][0-9]+-[0-9]+[:-](DEL|DUP|INS|INV|CNV)$'
              )
        )
        SELECT
            (SELECT COUNT(*) FROM unique_vrs_ids) as total,
            COUNT(va.variant_id) as synced
        FROM unique_vcf_variants uv
        LEFT JOIN variant_annotations va ON va.variant_id = uv.variant_id
    """)
    vep_result = await db.execute(vep_query)
    vep_stats = vep_result.fetchone()
    if vep_stats is None:
        raise HTTPException(status_code=500, detail="Failed to fetch VEP statistics")

    # Get last VEP sync time
    last_vep_sync_query = text("""
        SELECT MAX(fetched_at) as last_sync
        FROM variant_annotations
    """)
    last_vep_result = await db.execute(last_vep_sync_query)
    last_vep_sync = last_vep_result.scalar()

    # Reference data status
    ref_status = await get_reference_data_status(db)

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
            synced=vep_stats.synced or 0,
            pending=(vep_stats.total or 0) - (vep_stats.synced or 0),
            last_sync=last_vep_sync.isoformat() if last_vep_sync else None,
        ),
        DataSyncStatus(
            name="chr17q12 Genes",
            # Use synced count as total when genes are present (dynamic from Ensembl)
            # Before first sync, estimate ~175 genes in chr17q12 region
            total=ref_status.chr17q12_gene_count if ref_status.chr17q12_gene_count > 0 else 175,
            synced=ref_status.chr17q12_gene_count,
            pending=0,  # All Ensembl genes synced in single operation
            last_sync=ref_status.last_updated.isoformat() if ref_status.last_updated else None,
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


async def _run_publication_sync(task_id: str) -> None:
    """Background task to sync publication metadata.

    Creates its own database session to avoid issues with request session lifecycle.
    """
    task = _sync_tasks.get(task_id)
    if not task:
        return

    task["status"] = "running"
    task["started_at"] = datetime.now(timezone.utc).isoformat()

    try:
        # Create a fresh database session for the background task
        async with async_session_maker() as db:
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
        # Force refresh: get all PMIDs and delete existing cached data
        query = text("""
            SELECT DISTINCT REPLACE(ext_ref->>'id', 'PMID:', '') as pmid
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
            WHERE ext_ref->>'id' LIKE 'PMID:%'
              AND deleted_at IS NULL
        """)
        result = await db.execute(query)
        all_pmids = [row.pmid for row in result.fetchall()]
        pending_count = len(all_pmids)

        if pending_count > 0:
            # Delete existing cached metadata for force refresh
            delete_query = text("""
                DELETE FROM publication_metadata
                WHERE pmid IN (
                    SELECT DISTINCT ext_ref->>'id' as pmid
                    FROM phenopackets,
                         jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
                    WHERE ext_ref->>'id' LIKE 'PMID:%'
                      AND deleted_at IS NULL
                )
            """)
            await db.execute(delete_query)
            await db.commit()
            logger.info(f"Force refresh: deleted existing metadata for {pending_count} publications")
    else:
        # Check for pending items only
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

    # Queue background task (no db session - task creates its own)
    background_tasks.add_task(_run_publication_sync, task_id)

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
# Variant Annotation Sync Endpoints
# =============================================================================


async def _run_variant_sync(task_id: str) -> None:
    """Background task to sync variant annotations from VEP.

    Creates its own database session to avoid issues with request session lifecycle.
    """
    task = _sync_tasks.get(task_id)
    if not task:
        return

    task["status"] = "running"
    task["started_at"] = datetime.now(timezone.utc).isoformat()

    try:
        # Create a fresh database session for the background task
        async with async_session_maker() as db:
            # Get unique variants to sync (using shared SQL fragment)
            query = text(get_pending_variants_query())
            result = await db.execute(query)
            variants_to_sync = [row.variant_id for row in result.fetchall()]

            # Note: CNVs ARE supported via VEP's /vep/homo_sapiens/region endpoint
            # using structural variant format (CHROM START END SV_TYPE STRAND ID).
            # The service.py _format_variant_for_vep() handles CNV formatting.

            task["total"] = len(variants_to_sync)
            task["processed"] = 0
            task["errors"] = 0

            # Process in batches using configured batch size (default 50)
            batch_size = settings.external_apis.vep.batch_size
            for i in range(0, len(variants_to_sync), batch_size):
                batch = variants_to_sync[i : i + batch_size]
                try:
                    results = await get_variant_annotations_batch(
                        batch, db, fetched_by="admin_sync", batch_size=batch_size
                    )
                    for vid in batch:
                        if vid in results and results[vid]:
                            task["processed"] += 1
                        else:
                            task["errors"] += 1
                except Exception as e:
                    task["errors"] += len(batch)
                    logger.warning(f"Failed to sync variant batch: {e}")

                task["progress"] = (
                    (task["processed"] / task["total"] * 100) if task["total"] > 0 else 100
                )

                # Rate limiting between batches - longer delay to avoid 503 errors
                await asyncio.sleep(1.0)

        task["status"] = "completed"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"Variant sync completed: {task['processed']} synced, {task['errors']} errors"
        )

    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
        logger.error(f"Variant sync failed: {e}")


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
        # Force refresh: get all unique variants and delete existing cached data
        # Use shared SQL fragment for DRY compliance
        query = text(get_unique_variants_query())
        result = await db.execute(query)
        all_variants = [row.variant_id for row in result.fetchall()]
        pending_count = len(all_variants)

        if pending_count > 0:
            # Delete existing cached annotations for force refresh
            delete_query = text(f"""
                DELETE FROM variant_annotations
                WHERE variant_id IN (
                    WITH {UNIQUE_VARIANTS_CTE}
                    SELECT variant_id FROM unique_variants
                )
            """)
            await db.execute(delete_query)
            await db.commit()
            logger.info(f"Force refresh: deleted existing annotations for {pending_count} variants")
    else:
        # Check for pending items (using shared SQL fragment)
        query = text(get_unique_variants_query("COUNT(*)"))
        result = await db.execute(query)
        pending_count = result.scalar() or 0

    if pending_count == 0:
        return SyncTaskResponse(
            task_id="none",
            status="completed",
            message="All variants already annotated",
            items_to_process=0,
            estimated_time_seconds=0,
        )

    # Create task
    task_id = f"var_sync_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    _sync_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "processed": 0,
        "total": pending_count,
        "errors": 0,
        "started_at": None,
        "completed_at": None,
    }

    # Queue background task (no db session - task creates its own)
    background_tasks.add_task(_run_variant_sync, task_id)

    # Estimate time (batch of 50 takes ~3-4s + overhead)
    estimated_seconds = int((pending_count / 50 + 1) * 4)

    logger.info(
        f"Variant sync initiated by {current_user.username}",
        extra={"task_id": task_id, "items": pending_count},
    )

    return SyncTaskResponse(
        task_id=task_id,
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
    # If no task_id, get the most recent variant sync task
    if task_id is None:
        # Find most recent variant sync task
        var_tasks = {k: v for k, v in _sync_tasks.items() if k.startswith("var_sync_")}
        if not var_tasks:
            # Return current sync status from database (using shared SQL fragment)
            query = text(get_variant_sync_status_query())
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
        task_id = max(var_tasks.keys())

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

            -- Phenopackets with variants
            (SELECT COUNT(*)
             FROM phenopackets
             WHERE deleted_at IS NULL
               AND phenopacket @> '{"interpretations": [{}]}') as phenopackets_with_variants,

            -- Variant annotations cached
            (SELECT COUNT(*) FROM variant_annotations) as variants_cached
    """)

    result = await db.execute(query)
    stats = result.fetchone()
    if stats is None:
        raise HTTPException(status_code=500, detail="Failed to fetch statistics")

    # Get unique variant count from phenopackets by VRS ID
    # This matches the summary endpoint count per GA4GH VRS 2.0 spec
    # Each unique variationDescriptor.id represents a distinct variant
    unique_variants_query = text("""
        SELECT COUNT(DISTINCT vd->>'id') as count
        FROM phenopackets p,
             jsonb_array_elements(p.phenopacket->'interpretations') as interp,
             jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
             LATERAL (
                 SELECT gi->'variantInterpretation'->'variationDescriptor' as vd
             ) vd_lateral
        WHERE vd_lateral.vd IS NOT NULL
          AND vd_lateral.vd->>'id' IS NOT NULL
          AND p.deleted_at IS NULL
    """)
    unique_result = await db.execute(unique_variants_query)
    unique_variants_count = unique_result.scalar() or 0

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
        "variants": {
            "unique": unique_variants_count,
            "cached": stats.variants_cached or 0,
            "pending_sync": unique_variants_count - (stats.variants_cached or 0),
        },
    }


# =============================================================================
# Reference Data Sync Endpoints
# =============================================================================


async def _run_reference_init(task_id: str) -> None:
    """Background task to initialize reference data (GRCh38 + HNF1B).

    Creates its own database session to avoid issues with request session lifecycle.
    """
    task = _sync_tasks.get(task_id)
    if not task:
        return

    task["status"] = "running"
    task["started_at"] = datetime.now(timezone.utc).isoformat()

    try:
        async with async_session_maker() as db:
            result = await initialize_reference_data(db)
            task["processed"] = result.imported
            task["total"] = result.total
            task["errors"] = result.errors
            task["progress"] = 100.0

        task["status"] = "completed"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"Reference data init completed: {result.imported} items created")

    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
        logger.error(f"Reference data init failed: {e}")


async def _run_genes_sync(task_id: str) -> None:
    """Background task to sync chr17q12 genes from Ensembl.

    Creates its own database session to avoid issues with request session lifecycle.
    """
    task = _sync_tasks.get(task_id)
    if not task:
        return

    task["status"] = "running"
    task["started_at"] = datetime.now(timezone.utc).isoformat()

    try:
        async with async_session_maker() as db:
            result = await sync_chr17q12_genes(db)
            task["processed"] = result.imported + result.updated
            task["total"] = result.total
            task["errors"] = result.errors
            task["progress"] = 100.0

        task["status"] = "completed"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(
            f"Gene sync completed: {result.imported} imported, "
            f"{result.updated} updated, {result.errors} errors"
        )

    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
        logger.error(f"Gene sync failed: {e}")


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
    dependencies=[Depends(require_admin)],
)
async def start_reference_init(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Start reference data initialization task."""
    # Check current status
    ref_status = await get_reference_data_status(db)

    if ref_status.has_grch38 and ref_status.has_hnf1b:
        return SyncTaskResponse(
            task_id="none",
            status="completed",
            message="Reference data already initialized (GRCh38 + HNF1B present)",
            items_to_process=0,
            estimated_time_seconds=0,
        )

    # Create task
    task_id = f"ref_init_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    _sync_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "processed": 0,
        "total": 15,  # genome + gene + transcript + 9 exons + 4 domains
        "errors": 0,
        "started_at": None,
        "completed_at": None,
    }

    background_tasks.add_task(_run_reference_init, task_id)

    logger.info(
        f"Reference data init initiated by {current_user.username}",
        extra={"task_id": task_id},
    )

    return SyncTaskResponse(
        task_id=task_id,
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
    dependencies=[Depends(require_admin)],
)
async def start_genes_sync(
    background_tasks: BackgroundTasks,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Start chr17q12 gene sync task."""
    # Check current status
    ref_status = await get_reference_data_status(db)

    if not force and ref_status.chr17q12_gene_count >= 60:
        return SyncTaskResponse(
            task_id="none",
            status="completed",
            message=f"chr17q12 genes already synced ({ref_status.chr17q12_gene_count} genes present)",
            items_to_process=0,
            estimated_time_seconds=0,
        )

    # Create task
    task_id = f"genes_sync_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    _sync_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "processed": 0,
        "total": 70,  # Expected ~70 genes
        "errors": 0,
        "started_at": None,
        "completed_at": None,
    }

    background_tasks.add_task(_run_genes_sync, task_id)

    logger.info(
        f"Gene sync initiated by {current_user.username}",
        extra={"task_id": task_id},
    )

    return SyncTaskResponse(
        task_id=task_id,
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
    dependencies=[Depends(require_admin)],
)
async def get_genes_sync_status(
    task_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get gene sync task status."""
    # If no task_id, get the most recent gene sync task
    if task_id is None:
        gene_tasks = {
            k: v for k, v in _sync_tasks.items()
            if k.startswith("genes_sync_") or k.startswith("ref_init_")
        }
        if not gene_tasks:
            # Return current sync status from database
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

        task_id = max(gene_tasks.keys())

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


@router.get(
    "/reference/status",
    summary="Get reference data status",
    description="Returns detailed status of reference data in the database.",
    dependencies=[Depends(require_admin)],
)
async def get_reference_status(
    db: AsyncSession = Depends(get_db),
):
    """Get detailed reference data status."""
    ref_status = await get_reference_data_status(db)

    return {
        "genomes": {
            "count": ref_status.genome_count,
            "has_grch38": ref_status.has_grch38,
        },
        "genes": {
            "total": ref_status.gene_count,
            "chr17q12_count": ref_status.chr17q12_gene_count,
            "has_hnf1b": ref_status.has_hnf1b,
        },
        "transcripts": {
            "count": ref_status.transcript_count,
        },
        "exons": {
            "count": ref_status.exon_count,
        },
        "protein_domains": {
            "count": ref_status.domain_count,
        },
        "last_updated": ref_status.last_updated.isoformat() if ref_status.last_updated else None,
        "initialized": ref_status.has_grch38 and ref_status.has_hnf1b,
        "chr17q12_synced": ref_status.chr17q12_gene_count >= 60,
    }
