"""Variant aggregation endpoints for phenopackets.

Provides variant statistics by pathogenicity and type.
"""

from typing import List

from .common import (
    APIRouter,
    AggregationResult,
    AsyncSession,
    Depends,
    Query,
    get_db,
    text,
)

router = APIRouter()


@router.get("/variant-pathogenicity", response_model=List[AggregationResult])
async def aggregate_variant_pathogenicity(
    count_mode: str = Query(
        "all",
        regex="^(all|unique)$",
        description=(
            "Count mode: 'all' (default) counts all variant instances, "
            "'unique' counts distinct variants"
        ),
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get distribution of variant pathogenicity classifications.

    Args:
        count_mode:
            - "all" (default): Count all variant instances across
              phenopackets (e.g., 864 total)
            - "unique": Count only unique variants (deduplicates by
              variant ID)
        db: Database session dependency
    """
    if count_mode == "unique":
        # Count unique variants by variant ID
        query = """
        SELECT
            gi->>'interpretationStatus' as classification,
            COUNT(DISTINCT vd->>'id') as count
        FROM
            phenopackets,
            jsonb_array_elements(phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
            LATERAL (
                SELECT gi->'variantInterpretation'->'variationDescriptor' as vd
            ) sub
        WHERE
            gi->'variantInterpretation'->'variationDescriptor' IS NOT NULL
        GROUP BY
            gi->>'interpretationStatus'
        ORDER BY
            count DESC
        """
    else:
        # Count all variant instances (original behavior)
        query = """
        SELECT
            gi->>'interpretationStatus' as classification,
            COUNT(*) as count
        FROM
            phenopackets,
            jsonb_array_elements(phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
        GROUP BY
            gi->>'interpretationStatus'
        ORDER BY
            count DESC
        """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(int(row._mapping["count"]) for row in rows)

    return [
        AggregationResult(
            label=row.classification,
            count=int(row._mapping["count"]),
            percentage=(int(row._mapping["count"]) / total * 100) if total > 0 else 0,
        )
        for row in rows
    ]


# SQL expression for variant type detection
VARIANT_TYPE_CASE = """
    CASE
        -- Large structural variants: parse size from label (e.g., "1.37Mb del")
        WHEN vd->'structuralType'->>'label' IN ('deletion', 'duplication') THEN
            CASE
                WHEN COALESCE(
                    NULLIF(
                        regexp_replace(vd->>'label', '^([0-9.]+)Mb.*', '\\1'),
                        vd->>'label'
                    )::numeric,
                    0
                ) >= 0.1 THEN
                    CASE
                        WHEN vd->'structuralType'->>'label' = 'deletion'
                            THEN 'Copy Number Loss'
                        ELSE 'Copy Number Gain'
                    END
                -- Smaller structural variants (<0.1 Mb)
                WHEN vd->'structuralType'->>'label' = 'deletion'
                    THEN 'Deletion'
                ELSE 'Duplication'
            END
        -- Small variants: detect type from c. notation
        WHEN vd->'structuralType'->>'label' IS NULL THEN
            CASE
                -- Indel: delins pattern
                WHEN EXISTS (
                    SELECT 1 FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.c'
                    AND elem->>'value' ~ 'delins'
                ) THEN 'Indel'
                -- Small deletion
                WHEN EXISTS (
                    SELECT 1 FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.c'
                    AND elem->>'value' ~ 'del'
                ) THEN 'Deletion'
                -- Duplication
                WHEN EXISTS (
                    SELECT 1 FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.c'
                    AND elem->>'value' ~ 'dup'
                ) THEN 'Duplication'
                -- Insertion
                WHEN EXISTS (
                    SELECT 1 FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.c'
                    AND elem->>'value' ~ 'ins'
                ) THEN 'Insertion'
                -- SNV: substitution pattern
                WHEN EXISTS (
                    SELECT 1 FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.c'
                    AND elem->>'value' ~ '>[ACGT]'
                ) THEN 'SNV'
                ELSE 'NA'
            END
        ELSE 'NA'
    END
"""


@router.get("/variant-types", response_model=List[AggregationResult])
async def aggregate_variant_types(
    count_mode: str = Query(
        "all",
        regex="^(all|unique)$",
        description=(
            "Count mode: 'all' (default) counts all variant instances, "
            "'unique' counts distinct variants"
        ),
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get distribution of variant types (SNV, CNV, etc.).

    Args:
        count_mode:
            - "all" (default): Count all variant instances across
              phenopackets (e.g., 864 total)
            - "unique": Count only unique variants (deduplicates by
              variant ID)
        db: Database session dependency
    """
    if count_mode == "unique":
        # Count unique variants by variant ID
        query = f"""
        WITH variant_types AS (
            SELECT DISTINCT
                vd->>'id' as variant_id,
                {VARIANT_TYPE_CASE} as variant_type
            FROM
                phenopackets,
                jsonb_array_elements(phenopacket->'interpretations') as interp,
                jsonb_array_elements(
                    interp->'diagnosis'->'genomicInterpretations'
                ) as gi,
                LATERAL (
                SELECT gi->'variantInterpretation'->'variationDescriptor' as vd
            ) sub
            WHERE
                gi->'variantInterpretation'->'variationDescriptor' IS NOT NULL
        )
        SELECT
            variant_type,
            COUNT(*) as count
        FROM variant_types
        GROUP BY variant_type
        ORDER BY count DESC
        """
    else:
        # Count all variant instances
        query = f"""
        SELECT
            {VARIANT_TYPE_CASE} as variant_type,
            COUNT(*) as count
        FROM
            phenopackets,
            jsonb_array_elements(phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
            LATERAL (
                SELECT gi->'variantInterpretation'->'variationDescriptor' as vd
            ) sub
        WHERE
            gi->'variantInterpretation'->'variationDescriptor' IS NOT NULL
        GROUP BY
            variant_type
        ORDER BY
            count DESC
        """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(int(row._mapping["count"]) for row in rows)

    return [
        AggregationResult(
            label=row.variant_type,
            count=int(row._mapping["count"]),
            percentage=(int(row._mapping["count"]) / total * 100) if total > 0 else 0,
        )
        for row in rows
    ]
