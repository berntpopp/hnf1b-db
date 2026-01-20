"""Demographics aggregation endpoints for phenopackets.

Provides sex distribution and age of onset statistics.
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


@router.get("/sex-distribution", response_model=List[AggregationResult])
async def aggregate_sex_distribution(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get sex distribution of subjects.

    Performance: Uses mv_sex_distribution materialized view when available.
    """
    # Log access for authenticated users only
    if current_user:
        log_aggregation_access(
            user_id=current_user.id,
            endpoint="/aggregate/sex-distribution",
            timestamp=datetime.now(timezone.utc),
        )

    # Try materialized view first (O(1) indexed lookup)
    if await check_materialized_view_exists(db, "mv_sex_distribution"):
        logger.debug("Using mv_sex_distribution materialized view")
        result = await db.execute(
            text("""
                SELECT sex, count, percentage
                FROM mv_sex_distribution
                ORDER BY count DESC
            """)
        )
        rows = result.mappings().all()
        total = sum(int(row["count"]) for row in rows)

        return [
            AggregationResult(
                label=row["sex"],
                count=int(row["count"]),
                percentage=(int(row["count"]) / total * 100) if total > 0 else 0,
            )
            for row in rows
        ]

    # Fallback: Live query (simple, but still benefits from index)
    logger.debug("Falling back to live query for sex distribution")
    query = """
    SELECT
        subject_sex as sex,
        COUNT(*) as count
    FROM
        phenopackets
    WHERE
        deleted_at IS NULL
    GROUP BY
        subject_sex
    ORDER BY
        count DESC
    """

    result = await db.execute(text(query))
    rows = result.mappings().all()

    total = sum(int(row["count"]) for row in rows)

    return [
        AggregationResult(
            label=row["sex"],
            count=int(row["count"]),
            percentage=(int(row["count"]) / total * 100) if total > 0 else 0,
        )
        for row in rows
    ]


@router.get("/age-of-onset", response_model=List[AggregationResult])
async def aggregate_age_of_onset(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get distribution of age of disease onset."""
    # Log access for authenticated users only
    if current_user:
        log_aggregation_access(
            user_id=current_user.id,
            endpoint="/aggregate/age-of-onset",
            timestamp=datetime.now(timezone.utc),
        )

    query = """
    SELECT
        disease->'onset'->'ontologyClass'->>'label' as onset_label,
        disease->'onset'->'ontologyClass'->>'id' as onset_id,
        COUNT(*) as count
    FROM
        phenopackets,
        jsonb_array_elements(phenopacket->'diseases') as disease
    WHERE
        disease->'onset'->'ontologyClass'->>'label' IS NOT NULL
    GROUP BY
        disease->'onset'->'ontologyClass'->>'label',
        disease->'onset'->'ontologyClass'->>'id'
    ORDER BY
        count DESC
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(int(row._mapping["count"]) for row in rows)

    return [
        AggregationResult(
            label=row.onset_label,
            count=int(row._mapping["count"]),
            percentage=(int(row._mapping["count"]) / total * 100) if total > 0 else 0,
            details={"hpo_id": row.onset_id},
        )
        for row in rows
    ]
