"""Admin status endpoints.

Read-only routes that expose system-wide counts and reference data
health: ``/admin/status``, ``/admin/statistics``, and
``/admin/reference/status``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin import queries
from app.api.admin.schemas import DataSyncStatus, SystemStatusResponse
from app.auth import require_admin
from app.database import get_db
from app.models.user import User
from app.reference.service import get_reference_data_status

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


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
    db_stats = await queries.fetch_database_stats(db)
    pub_total, pub_synced = await queries.fetch_publication_sync_stats(db)
    last_pub_sync = await queries.fetch_last_publication_sync(db)
    vep_total, vep_synced = await queries.fetch_vep_sync_stats(db)
    last_vep_sync = await queries.fetch_last_vep_sync(db)
    ref_status = await get_reference_data_status(db)

    sync_status = [
        DataSyncStatus(
            name="Publication Metadata",
            total=pub_total,
            synced=pub_synced,
            pending=pub_total - pub_synced,
            last_sync=last_pub_sync.isoformat() if last_pub_sync else None,
        ),
        DataSyncStatus(
            name="VEP Annotations",
            total=vep_total,
            synced=vep_synced,
            pending=vep_total - vep_synced,
            last_sync=last_vep_sync.isoformat() if last_vep_sync else None,
        ),
        DataSyncStatus(
            name="chr17q12 Genes",
            # Use synced count as total when genes are present (dynamic from Ensembl).
            # Before first sync, estimate ~175 genes in chr17q12 region.
            total=ref_status.chr17q12_gene_count
            if ref_status.chr17q12_gene_count > 0
            else 175,
            synced=ref_status.chr17q12_gene_count,
            pending=0,  # All Ensembl genes synced in a single operation
            last_sync=ref_status.last_updated.isoformat()
            if ref_status.last_updated
            else None,
        ),
    ]

    return SystemStatusResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        database=db_stats,
        sync_status=sync_status,
    )


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
    return await queries.fetch_detailed_statistics(db)


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
        "last_updated": ref_status.last_updated.isoformat()
        if ref_status.last_updated
        else None,
        "initialized": ref_status.has_grch38 and ref_status.has_hnf1b,
        "chr17q12_synced": ref_status.chr17q12_gene_count >= 60,
    }
