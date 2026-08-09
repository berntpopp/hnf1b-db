"""Feature aggregation endpoint for phenopackets.

Aggregates phenopackets by phenotypic features (HPO terms).
"""

from typing import List

from .common import (
    AggregationResult,
    APIRouter,
    AsyncSession,
    Depends,
    calculate_percentages,
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

    Always reads published-head snapshots. Legacy materialized views are based
    on mutable working copies and are therefore not public-safe.
    """
    logger.debug("Reading published-head feature aggregation")

    # First, get total number of published phenopackets (public filter: I3 + I7)
    total_phenopackets_result = await db.execute(
        text(
            "SELECT COUNT(*) as total FROM phenopackets p "
            "JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id"
            " WHERE p.deleted_at IS NULL"
            " AND p.state = 'published'"
            " AND p.head_published_revision_id IS NOT NULL"
            " AND p.phenopacket_id NOT LIKE 'e2e-%'"
        )
    )
    total_phenopackets = total_phenopackets_result.scalar() or 0

    # Query to get both present and absent counts for each HPO term
    # GROUP BY the HPO id only (not id+label): the same HPO id can appear with
    # multiple label spellings, which previously produced duplicate rows (one a
    # zero-count ghost). MIN(label) picks a single canonical label per id.
    query = """
    SELECT
        feature->'type'->>'id' as hpo_id,
        MIN(feature->'type'->>'label') as label,
        SUM(CASE WHEN NOT COALESCE((feature->>'excluded')::boolean, false)
            THEN 1 ELSE 0 END) as present_count,
        SUM(CASE WHEN COALESCE((feature->>'excluded')::boolean, false)
            THEN 1 ELSE 0 END) as absent_count
    FROM
        phenopackets p
        JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id,
        jsonb_array_elements(r.content_jsonb->'phenotypicFeatures') as feature
    WHERE
        p.deleted_at IS NULL
        AND p.state = 'published'
        AND p.head_published_revision_id IS NOT NULL
        AND p.phenopacket_id NOT LIKE 'e2e-%'
    GROUP BY
        feature->'type'->>'id'
    ORDER BY
        present_count DESC
    """

    result = await db.execute(text(query))
    rows = result.mappings().all()

    # Calculate total for percentage (sum of all present counts)
    total = sum(int(row["present_count"]) for row in rows)
    rows_with_pct = calculate_percentages(rows, total=total, count_key="present_count")

    return [
        AggregationResult(
            label=row["label"] or row["hpo_id"],
            count=int(row["present_count"]),
            percentage=row["percentage"],
            hpo_id=row["hpo_id"],
            details={
                "hpo_id": row["hpo_id"],
                "present_count": int(row["present_count"]),
                "absent_count": int(row["absent_count"]),
                "not_reported_count": total_phenopackets
                - int(row["present_count"])
                - int(row["absent_count"]),
            },
        )
        for row in rows_with_pct
    ]
