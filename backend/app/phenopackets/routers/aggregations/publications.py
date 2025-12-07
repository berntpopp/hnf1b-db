"""Publication aggregation endpoints for phenopackets.

Provides publication statistics and timeline data.
"""

from typing import Dict, List

from .common import (
    AggregationResult,
    APIRouter,
    AsyncSession,
    Depends,
    get_db,
    text,
)

router = APIRouter()


@router.get("/publication-types", response_model=List[AggregationResult])
async def aggregate_publication_types(
    db: AsyncSession = Depends(get_db),
):
    """Get distribution of publication types.

    Aggregates phenopackets by publication type (case_series, research, etc.).
    Publication type is stored in metaData.externalReferences.reference field.

    Returns:
        List of aggregation results with publication type labels and counts
    """
    query = """
    SELECT
        ext_ref->>'reference' as pub_type,
        COUNT(DISTINCT p.id) as count
    FROM
        phenopackets p,
        jsonb_array_elements(p.phenopacket->'metaData'->'externalReferences') as ext_ref
    WHERE
        ext_ref->>'reference' IS NOT NULL
        AND ext_ref->>'reference' != ''
    GROUP BY
        ext_ref->>'reference'
    ORDER BY
        count DESC
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(int(row._mapping["count"]) for row in rows)

    return [
        AggregationResult(
            label=row.pub_type,
            count=int(row._mapping["count"]),
            percentage=(int(row._mapping["count"]) / total * 100) if total > 0 else 0,
        )
        for row in rows
    ]


@router.get("/publications-timeline", response_model=List[Dict])
async def get_publications_timeline(
    db: AsyncSession = Depends(get_db),
):
    """Get timeline of phenopackets added over time by publication year.

    Extracts publication years from external references and returns
    cumulative counts of phenopackets added each year.

    Returns:
        List of timeline points with year, count, and cumulative total:
        [
            {
                "year": 2018,
                "count": 4,
                "cumulative": 4,
                "publications": ["PMID:12345678", "PMID:87654321"]
            },
            ...
        ]
    """
    query = """
    WITH publication_years AS (
        SELECT
            p.phenopacket_id,
            p.created_at,
            ext_ref->>'id' as pmid,
            COALESCE(
                NULLIF(
                    regexp_replace(
                        ext_ref->>'description',
                        '.*[, ](\\d{4}).*',
                        '\\1'
                    ),
                    ext_ref->>'description'
                )::integer,
                EXTRACT(YEAR FROM p.created_at)::integer
            ) as pub_year
        FROM phenopackets p,
            jsonb_array_elements(
                p.phenopacket->'metaData'->'externalReferences'
            ) as ext_ref
        WHERE ext_ref->>'id' LIKE 'PMID:%'
    ),
    year_counts AS (
        SELECT
            pub_year as year,
            COUNT(DISTINCT phenopacket_id) as count,
            array_agg(DISTINCT pmid ORDER BY pmid) as publications
        FROM publication_years
        WHERE pub_year IS NOT NULL
        GROUP BY pub_year
        ORDER BY pub_year
    )
    SELECT
        year,
        count,
        SUM(count) OVER (ORDER BY year) as cumulative,
        publications
    FROM year_counts
    ORDER BY year
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    return [
        {
            "year": int(row.year),
            "count": int(row._mapping["count"]),
            "cumulative": int(row.cumulative),
            "publications": row.publications or [],
        }
        for row in rows
    ]


@router.get("/publications-by-type", response_model=List[Dict])
async def get_publications_by_type(
    db: AsyncSession = Depends(get_db),
):
    """Get publication counts grouped by PMID and type.

    Returns publication information with PMID, type, and phenopacket count.
    Frontend can enrich with publication years from PubMed API.

    Returns:
        List of publications with type and count:
        [
            {
                "pmid": "PMID:30791938",
                "publication_type": "review_and_cases",
                "phenopacket_count": 1
            },
            ...
        ]
    """
    query = """
    SELECT
        ext_ref->>'id' as pmid,
        COALESCE(ext_ref->>'reference', 'unknown') as publication_type,
        COUNT(DISTINCT p.phenopacket_id) as phenopacket_count
    FROM phenopackets p,
        jsonb_array_elements(
            p.phenopacket->'metaData'->'externalReferences'
        ) as ext_ref
    WHERE ext_ref->>'id' LIKE 'PMID:%'
    GROUP BY ext_ref->>'id', ext_ref->>'reference'
    ORDER BY pmid
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    return [
        {
            "pmid": row.pmid,
            "publication_type": row.publication_type,
            "phenopacket_count": int(row.phenopacket_count),
        }
        for row in rows
    ]
