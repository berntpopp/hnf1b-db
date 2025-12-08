"""Feature aggregation endpoint for phenopackets.

Aggregates phenopackets by phenotypic features (HPO terms).
Uses materialized views when available for O(1) performance.
"""

from typing import List

from .common import (
    AggregationResult,
    APIRouter,
    AsyncSession,
    Depends,
    check_materialized_view_exists,
    get_db,
    logger,
    text,
)

router = APIRouter()


@router.get("/by-feature", response_model=List[AggregationResult])
async def aggregate_by_feature(
    db: AsyncSession = Depends(get_db),
):
    """Aggregate phenopackets by phenotypic features.

    Returns phenotypic features with three counts:
    - present_count: Features reported as present (excluded=false)
    - absent_count: Features reported as absent (excluded=true)
    - not_reported_count: Phenopackets without this feature reported

    The main 'count' field represents present_count for backwards compatibility.

    Performance: Uses mv_feature_aggregation materialized view when available.
    """
    # Try materialized view first (O(1) indexed lookup)
    if await check_materialized_view_exists(db, "mv_feature_aggregation"):
        logger.debug("Using mv_feature_aggregation materialized view")
        result = await db.execute(
            text("""
                SELECT hpo_id, label, present_count, absent_count,
                       not_reported_count, total_phenopackets
                FROM mv_feature_aggregation
                ORDER BY present_count DESC
            """)
        )
        rows = result.mappings().all()
        total = sum(int(row["present_count"]) for row in rows)

        return [
            AggregationResult(
                label=row["label"] or row["hpo_id"],
                count=int(row["present_count"]),
                percentage=(int(row["present_count"]) / total * 100)
                if total > 0
                else 0,
                details={
                    "hpo_id": row["hpo_id"],
                    "present_count": int(row["present_count"]),
                    "absent_count": int(row["absent_count"]),
                    "not_reported_count": int(row["not_reported_count"]),
                },
            )
            for row in rows
        ]

    # Fallback: Live JSONB query (O(n) scan)
    logger.debug("Falling back to live JSONB query for feature aggregation")

    # First, get total number of phenopackets
    total_phenopackets_result = await db.execute(
        text("SELECT COUNT(*) as total FROM phenopackets WHERE deleted_at IS NULL")
    )
    total_phenopackets = total_phenopackets_result.scalar() or 0

    # Query to get both present and absent counts for each HPO term
    query = """
    SELECT
        feature->'type'->>'id' as hpo_id,
        feature->'type'->>'label' as label,
        SUM(CASE WHEN NOT COALESCE((feature->>'excluded')::boolean, false)
            THEN 1 ELSE 0 END) as present_count,
        SUM(CASE WHEN COALESCE((feature->>'excluded')::boolean, false)
            THEN 1 ELSE 0 END) as absent_count
    FROM
        phenopackets,
        jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature
    WHERE
        deleted_at IS NULL
    GROUP BY
        feature->'type'->>'id',
        feature->'type'->>'label'
    ORDER BY
        present_count DESC
    """

    result = await db.execute(text(query))
    rows = result.mappings().all()

    # Calculate total for percentage (sum of all present counts)
    total = sum(int(row["present_count"]) for row in rows)

    return [
        AggregationResult(
            label=row["label"] or row["hpo_id"],
            count=int(row["present_count"]),
            percentage=(int(row["present_count"]) / total * 100) if total > 0 else 0,
            details={
                "hpo_id": row["hpo_id"],
                "present_count": int(row["present_count"]),
                "absent_count": int(row["absent_count"]),
                "not_reported_count": total_phenopackets
                - int(row["present_count"])
                - int(row["absent_count"]),
            },
        )
        for row in rows
    ]
