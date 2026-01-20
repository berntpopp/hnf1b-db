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
    Optional,
    User,
    check_materialized_view_exists,
    datetime,
    get_current_user_optional,
    get_db,
    log_aggregation_access,
    logger,
    text,
    timezone,
)

router = APIRouter()


@router.get("/by-disease", response_model=List[AggregationResult])
async def aggregate_by_disease(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Aggregate phenopackets by disease.

    Performance: Uses mv_disease_aggregation materialized view when available.
    """
    # Log access for authenticated users only
    if current_user:
        log_aggregation_access(
            user_id=current_user.id,
            endpoint="/aggregate/by-disease",
            timestamp=datetime.now(timezone.utc),
        )

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

        return [
            AggregationResult(
                label=row["label"] or row["disease_id"],
                count=int(row["count"]),
                percentage=(int(row["count"]) / total * 100) if total > 0 else 0,
                details={"disease_id": row["disease_id"]},
            )
            for row in rows
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
    GROUP BY
        disease->'term'->>'id',
        disease->'term'->>'label'
    ORDER BY
        count DESC
    """

    result = await db.execute(text(query))
    rows = result.mappings().all()

    total = sum(int(row["count"]) for row in rows)

    return [
        AggregationResult(
            label=row["label"] or row["disease_id"],
            count=int(row["count"]),
            percentage=(int(row["count"]) / total * 100) if total > 0 else 0,
            details={"disease_id": row["disease_id"]},
        )
        for row in rows
    ]


@router.get("/kidney-stages", response_model=List[AggregationResult])
async def aggregate_kidney_stages(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get distribution of kidney disease stages."""
    # Log access for authenticated users only
    if current_user:
        log_aggregation_access(
            user_id=current_user.id,
            endpoint="/aggregate/kidney-stages",
            timestamp=datetime.now(timezone.utc),
        )

    query = """
    SELECT
        modifier->>'label' as stage,
        COUNT(*) as count
    FROM
        phenopackets,
        jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature,
        jsonb_array_elements(COALESCE(feature->'modifiers', '[]'::jsonb)) as modifier
    WHERE
        feature->'type'->>'id' = 'HP:0012622'
        AND modifier->>'label' LIKE '%Stage%'
    GROUP BY
        modifier->>'label'
    ORDER BY
        stage
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(int(row._mapping["count"]) for row in rows)

    return [
        AggregationResult(
            label=row.stage,
            count=int(row._mapping["count"]),
            percentage=(int(row._mapping["count"]) / total * 100) if total > 0 else 0,
        )
        for row in rows
    ]
