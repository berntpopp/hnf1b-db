"""Disease aggregation endpoints for phenopackets.

Aggregates phenopackets by disease and kidney disease stages.
Uses materialized views when available for O(1) performance.
"""

from typing import List

from .common import (
    AggregationResult,
    APIRouter,
    AsyncSession,
    Depends,
    calculate_percentages,
    check_materialized_view_exists,
    get_db,
    logger,
    settings,
    text,
)

router = APIRouter()


@router.get("/by-disease", response_model=List[AggregationResult])
async def aggregate_by_disease(
    db: AsyncSession = Depends(get_db),
):
    """Aggregate phenopackets by disease.

    Performance: Uses mv_disease_aggregation materialized view when available.
    """
    # Try materialized view first (O(1) indexed lookup)
    if await check_materialized_view_exists(db, "mv_disease_aggregation"):
        logger.debug("Using mv_disease_aggregation materialized view")
        result = await db.execute(
            text("""
                SELECT disease_id, label, count, percentage
                FROM mv_disease_aggregation
                ORDER BY count DESC
            """)
        )
        rows = result.mappings().all()
        total = sum(int(row["count"]) for row in rows)
        rows_with_pct = calculate_percentages(rows, total=total)

        return [
            AggregationResult(
                label=row["label"] or row["disease_id"],
                count=int(row["count"]),
                percentage=row["percentage"],
                details={"disease_id": row["disease_id"]},
            )
            for row in rows_with_pct
        ]

    # Fallback: Live JSONB query (O(n) scan)
    logger.debug("Falling back to live JSONB query for disease aggregation")
    query = """
    SELECT
        disease->'term'->>'id' as disease_id,
        disease->'term'->>'label' as label,
        COUNT(*) as count
    FROM
        phenopackets,
        jsonb_array_elements(phenopacket->'diseases') as disease
    WHERE
        deleted_at IS NULL
        AND state = 'published'
        AND head_published_revision_id IS NOT NULL
        AND phenopacket_id NOT LIKE 'e2e-%'
    GROUP BY
        disease->'term'->>'id',
        disease->'term'->>'label'
    ORDER BY
        count DESC
    """

    result = await db.execute(text(query))
    rows = result.mappings().all()

    total = sum(int(row["count"]) for row in rows)
    rows_with_pct = calculate_percentages(rows, total=total)

    return [
        AggregationResult(
            label=row["label"] or row["disease_id"],
            count=int(row["count"]),
            percentage=row["percentage"],
            details={"disease_id": row["disease_id"]},
        )
        for row in rows_with_pct
    ]


@router.get("/kidney-stages", response_model=List[AggregationResult])
async def aggregate_kidney_stages(
    db: AsyncSession = Depends(get_db),
):
    """Get distribution of kidney disease stages.

    The cohort encodes CKD stages as STANDALONE HPO feature terms (HP:0012623
    Stage 1 … HP:0003774 Stage 5, plus HP:0012622 unspecified CKD) — NOT as a
    ``Stage`` modifier on a single CKD feature. This aggregates the present
    occurrences of those terms (``settings.hpo_terms.ckd_stages``), using the same
    present-count semantics as /by-feature so the two reconcile. ``percentage`` is
    each stage's share of all staged-CKD annotations.
    """
    stage_ids: list[str] = settings.hpo_terms.ckd_stages
    # Named placeholders (:stage_0 …) for the IN-list. The ids are server-side
    # config constants, but parameterising keeps the query injection-safe.
    placeholders = ", ".join(f":stage_{i}" for i in range(len(stage_ids)))
    params = {f"stage_{i}": sid for i, sid in enumerate(stage_ids)}

    query = f"""
    SELECT
        feature->'type'->>'id' as hpo_id,
        MIN(feature->'type'->>'label') as label,
        COUNT(*) as count
    FROM
        phenopackets,
        jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature
    WHERE
        deleted_at IS NULL
        AND state = 'published'
        AND head_published_revision_id IS NOT NULL
        AND phenopacket_id NOT LIKE 'e2e-%'
        AND feature->'type'->>'id' IN ({placeholders})
        AND NOT COALESCE((feature->>'excluded')::boolean, false)
    GROUP BY
        feature->'type'->>'id'
    ORDER BY
        hpo_id
    """

    result = await db.execute(text(query), params)
    rows = result.mappings().all()

    total = sum(int(row["count"]) for row in rows)
    rows_with_pct = calculate_percentages(rows, total=total)

    return [
        AggregationResult(
            label=row["label"] or row["hpo_id"],
            count=int(row["count"]),
            percentage=row["percentage"],
            hpo_id=row["hpo_id"],
        )
        for row in rows_with_pct
    ]
