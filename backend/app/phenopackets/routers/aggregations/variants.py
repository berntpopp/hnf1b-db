"""Variant aggregation endpoints for phenopackets.

Provides variant statistics by pathogenicity and type.
"""

from typing import List

from .common import (
    AggregationResult,
    APIRouter,
    AsyncSession,
    Depends,
    Query,
    get_db,
    text,
)
from .sql_fragments import VARIANT_TYPE_CASE

router = APIRouter()


@router.get("/variant-pathogenicity", response_model=List[AggregationResult])
async def aggregate_variant_pathogenicity(
    count_mode: str = Query(
        "all",
        pattern="^(all|unique)$",
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


@router.get("/variant-types", response_model=List[AggregationResult])
async def aggregate_variant_types(
    count_mode: str = Query(
        "all",
        pattern="^(all|unique)$",
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
