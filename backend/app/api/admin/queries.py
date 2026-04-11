"""Raw SQL helper queries used by the admin endpoints.

Extracted from the old flat ``app/api/admin_endpoints.py`` during the
Wave 4 decomposition. Each function here returns a plain dict of the
columns the caller needs, so the ``endpoints`` module stays focused on
HTTP plumbing and does not need to touch SQL directly.

The SQL fragments that are shared with other modules (notably the
variant sync status queries used by both admin and the aggregations
sub-package) still live in
``app.phenopackets.routers.aggregations.sql_fragments`` — this module
only owns the queries that are admin-specific.
"""
# ruff: noqa: E501 - SQL queries are more readable when not line-wrapped

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# =============================================================================
# System-status / /status endpoint helpers
# =============================================================================


async def fetch_database_stats(db: AsyncSession) -> dict[str, int]:
    """Return aggregate DB counts used by ``/admin/status``."""
    stats_query = text(
        """
        SELECT
            (SELECT COUNT(*) FROM phenopackets WHERE deleted_at IS NULL) as phenopackets_count,
            (SELECT COUNT(*) FROM users WHERE is_active = true) as users_count,
            (SELECT COUNT(*) FROM publication_metadata) as publications_cached
        """
    )
    result = await db.execute(stats_query)
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=500, detail="Failed to fetch database statistics"
        )
    return {
        "phenopackets": row.phenopackets_count or 0,
        "users": row.users_count or 0,
        "publications_cached": row.publications_cached or 0,
    }


async def fetch_publication_sync_stats(db: AsyncSession) -> tuple[int, int]:
    """Return ``(total_referenced_pmids, synced_pmids)`` for the PubMed sync view."""
    query = text(
        """
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
        """
    )
    result = await db.execute(query)
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=500, detail="Failed to fetch publication statistics"
        )
    return (row.total or 0, row.synced or 0)


async def fetch_last_publication_sync(db: AsyncSession) -> Optional[datetime]:
    """Return the timestamp of the most recently cached PubMed metadata row."""
    result = await db.execute(
        text("SELECT MAX(fetched_at) as last_sync FROM publication_metadata")
    )
    return result.scalar()


async def fetch_vep_sync_stats(db: AsyncSession) -> tuple[int, int]:
    """Return ``(unique_variant_count, synced_annotation_count)`` for VEP.

    Counts unique variants by VRS id (to match the summary endpoint) but
    measures "synced" by VCF-expression matches against
    ``variant_annotations`` — this is the existing admin contract, kept
    identical so the /status shape does not change.
    """
    query = text(
        """
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
        """
    )
    result = await db.execute(query)
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=500, detail="Failed to fetch VEP statistics"
        )
    return (row.total or 0, row.synced or 0)


async def fetch_last_vep_sync(db: AsyncSession) -> Optional[datetime]:
    """Return the timestamp of the most recently cached VEP annotation."""
    result = await db.execute(
        text("SELECT MAX(fetched_at) as last_sync FROM variant_annotations")
    )
    return result.scalar()


# =============================================================================
# /sync/publications orchestration helpers
# =============================================================================


async def fetch_pmids_to_sync(db: AsyncSession) -> list[str]:
    """Return the list of un-cached PMIDs referenced by any phenopacket."""
    query = text(
        """
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
        """
    )
    result = await db.execute(query)
    return [row.pmid for row in result.fetchall()]


async def fetch_all_referenced_pmids(db: AsyncSession) -> list[str]:
    """Return every PMID referenced by any phenopacket (for force refresh)."""
    query = text(
        """
        SELECT DISTINCT REPLACE(ext_ref->>'id', 'PMID:', '') as pmid
        FROM phenopackets,
             jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
        WHERE ext_ref->>'id' LIKE 'PMID:%'
          AND deleted_at IS NULL
        """
    )
    result = await db.execute(query)
    return [row.pmid for row in result.fetchall()]


async def delete_all_publication_metadata(db: AsyncSession) -> None:
    """Delete every cached publication row that a phenopacket currently references.

    Used by the "force refresh" branch of ``/sync/publications``.
    """
    query = text(
        """
        DELETE FROM publication_metadata
        WHERE pmid IN (
            SELECT DISTINCT ext_ref->>'id' as pmid
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
            WHERE ext_ref->>'id' LIKE 'PMID:%'
              AND deleted_at IS NULL
        )
        """
    )
    await db.execute(query)
    await db.commit()


async def count_pending_publication_sync(db: AsyncSession) -> int:
    """Return how many PMIDs need a publication-metadata sync."""
    query = text(
        """
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
        """
    )
    result = await db.execute(query)
    return int(result.scalar() or 0)


async def fetch_current_publication_sync_snapshot(
    db: AsyncSession,
) -> dict[str, int]:
    """Return ``{"total": ..., "synced": ...}`` for the idle-status path.

    Used when ``/sync/publications/status`` is called without an active
    task — we return the current DB view instead of an error.
    """
    total, synced = await fetch_publication_sync_stats(db)
    return {"total": total, "synced": synced}


# =============================================================================
# /statistics endpoint helpers
# =============================================================================


async def fetch_detailed_statistics(db: AsyncSession) -> dict[str, Any]:
    """Return the full ``/admin/statistics`` payload.

    Keeps the admin endpoint short and makes the SQL reviewable as a
    single unit.
    """
    query = text(
        """
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
        """
    )
    result = await db.execute(query)
    stats = result.fetchone()
    if stats is None:
        raise HTTPException(status_code=500, detail="Failed to fetch statistics")

    unique_variants_query = text(
        """
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
        """
    )
    unique_result = await db.execute(unique_variants_query)
    unique_variants_count = int(unique_result.scalar() or 0)

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
