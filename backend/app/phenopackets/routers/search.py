"""Full-text and structured search for phenopackets with cursor pagination."""

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.json_api import JsonApiCursorResponse
from app.utils.pagination import (
    build_cursor_response,
    decode_cursor,
    encode_cursor,
)

router = APIRouter()


@router.get("/search", response_model=JsonApiCursorResponse)
async def search_phenopackets(
    request: Request,
    q: Optional[str] = Query(None, description="Full-text search query"),
    hpo_id: Optional[str] = Query(None, description="Filter by HPO term ID"),
    sex: Optional[str] = Query(None, description="Filter by subject sex"),
    gene: Optional[str] = Query(None, description="Filter by gene symbol"),
    pmid: Optional[str] = Query(None, description="Filter by publication PMID"),
    # Cursor pagination (JSON:API v1.1)
    page_size: int = Query(
        20, alias="page[size]", ge=1, le=100, description="Page size"
    ),
    page_after: Optional[str] = Query(
        None, alias="page[after]", description="Cursor for next page"
    ),
    page_before: Optional[str] = Query(
        None, alias="page[before]", description="Cursor for previous page"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Advanced phenopacket search with full-text and structured filters.

    Uses cursor-based pagination for stable results during browsing.
    """
    # Base query parts
    select_clause = "SELECT id, phenopacket_id, phenopacket, created_at"
    from_clause = "FROM phenopackets"
    where_conditions = ["deleted_at IS NULL"]
    params: Dict[str, Any] = {}

    # Full-text search
    if q:
        select_clause += (
            ", ts_rank(search_vector, plainto_tsquery('english', :search_query))"
            " AS search_rank"
        )
        where_conditions.append(
            "search_vector @@ plainto_tsquery('english', :search_query)"
        )
        params["search_query"] = q

    # Structured filters
    if hpo_id:
        where_conditions.append("phenopacket->'phenotypicFeatures' @> :hpo_filter")
        params["hpo_filter"] = json.dumps([{"type": {"id": hpo_id}}])
    if sex:
        where_conditions.append("subject_sex = :sex")
        params["sex"] = sex
    if gene:
        where_conditions.append("phenopacket->'interpretations' @> :gene_filter")
        params["gene_filter"] = json.dumps(
            [
                {
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "variationDescriptor": {
                                        "geneContext": {"symbol": gene}
                                    }
                                }
                            }
                        ]
                    }
                }
            ]
        )
    if pmid:
        where_conditions.append(
            "phenopacket->'metaData'->'externalReferences' @> :pmid_filter"
        )
        params["pmid_filter"] = json.dumps([{"id": f"PMID:{pmid}"}])

    # Handle cursor pagination
    is_backward = page_before is not None
    cursor_data = None

    if page_after:
        cursor_data = decode_cursor(page_after)
    elif page_before:
        cursor_data = decode_cursor(page_before)

    # Build cursor condition
    if cursor_data:
        cursor_created_at = cursor_data.get("created_at")
        cursor_id = cursor_data.get("id")

        if cursor_created_at and cursor_id:
            if is_backward:
                # Going backward: get records BEFORE cursor
                # (newer records if sorting DESC)
                where_conditions.append("""(
                    (created_at > :cursor_created_at)
                    OR (created_at = :cursor_created_at AND id > :cursor_id)
                )""")
            else:
                # Going forward: get records AFTER cursor
                # (older records if sorting DESC)
                where_conditions.append("""(
                    (created_at < :cursor_created_at)
                    OR (created_at = :cursor_created_at AND id < :cursor_id)
                )""")
            params["cursor_created_at"] = cursor_created_at
            params["cursor_id"] = str(cursor_id)

    # Construct the final query
    where_clause = f"WHERE {' AND '.join(where_conditions)}"

    # Order by search rank if searching, otherwise by created_at
    if q:
        if is_backward:
            order_clause = "ORDER BY search_rank ASC, created_at ASC, id ASC"
        else:
            order_clause = "ORDER BY search_rank DESC, created_at DESC, id DESC"
    else:
        if is_backward:
            order_clause = "ORDER BY created_at ASC, id ASC"
        else:
            order_clause = "ORDER BY created_at DESC, id DESC"

    # Fetch one extra to detect if there are more pages
    params["limit"] = page_size + 1

    # Get paginated results
    query_str = (
        f"{select_clause} {from_clause} {where_clause} {order_clause} LIMIT :limit"
    )
    result = await db.execute(text(query_str), params)
    rows = list(result.fetchall())

    # Detect if there are more pages
    has_more = len(rows) > page_size
    if has_more:
        rows = rows[:page_size]

    # Reverse results if going backward
    if is_backward:
        rows = list(reversed(rows))

    # Determine has_next and has_prev
    if is_backward:
        has_next = True  # We came from a next page
        has_prev = has_more
    elif page_after:
        has_next = has_more
        has_prev = True  # We came from a previous page
    else:
        # First page
        has_next = has_more
        has_prev = False

    # Format response
    data = [
        {
            "id": pp.phenopacket_id,
            "type": "phenopacket",
            "attributes": pp.phenopacket,
            "meta": {"search_rank": pp.search_rank if q else None},
        }
        for pp in rows
    ]

    # Build cursors from first and last records
    start_cursor = None
    end_cursor = None

    if rows:
        first_row = rows[0]
        last_row = rows[-1]

        start_cursor = encode_cursor(
            {
                "created_at": first_row.created_at,
                "id": first_row.id,
            }
        )
        end_cursor = encode_cursor(
            {
                "created_at": last_row.created_at,
                "id": last_row.id,
            }
        )

    # Build filter dict for pagination links
    filters: Dict[str, Any] = {}
    if q:
        filters["q"] = q
    if hpo_id:
        filters["hpo_id"] = hpo_id
    if sex:
        filters["sex"] = sex
    if gene:
        filters["gene"] = gene
    if pmid:
        filters["pmid"] = pmid

    # Build JSON:API cursor response
    base_url = str(request.url.path)
    return build_cursor_response(
        data=data,
        page_size=page_size,
        has_next=has_next,
        has_prev=has_prev,
        start_cursor=start_cursor,
        end_cursor=end_cursor,
        base_url=base_url,
        filters=filters,
        sort=None,
    )


@router.get("/search/facets")
async def get_search_facets(
    q: Optional[str] = Query(None, description="Full-text search query"),
    hpo_id: Optional[str] = Query(None, description="Filter by HPO term ID"),
    sex: Optional[str] = Query(None, description="Filter by subject sex"),
    gene: Optional[str] = Query(None, description="Filter by gene symbol"),
    pmid: Optional[str] = Query(None, description="Filter by publication PMID"),
    db: AsyncSession = Depends(get_db),
):
    """Get facet counts for search filters based on current search criteria."""
    # Base query conditions
    where_conditions = ["deleted_at IS NULL"]
    params: Dict[str, Any] = {}

    # Apply existing filters for facet counts
    if q:
        where_conditions.append(
            "search_vector @@ plainto_tsquery('english', :search_query)"
        )
        params["search_query"] = q

    if hpo_id:
        where_conditions.append("phenopacket->'phenotypicFeatures' @> :hpo_filter")
        params["hpo_filter"] = json.dumps([{"type": {"id": hpo_id}}])

    if sex:
        where_conditions.append("subject_sex = :sex")
        params["sex"] = sex

    if gene:
        where_conditions.append("phenopacket->'interpretations' @> :gene_filter")
        params["gene_filter"] = json.dumps(
            [
                {
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "variationDescriptor": {
                                        "geneContext": {"symbol": gene}
                                    }
                                }
                            }
                        ]
                    }
                }
            ]
        )

    if pmid:
        where_conditions.append(
            "phenopacket->'metaData'->'externalReferences' @> :pmid_filter"
        )
        params["pmid_filter"] = json.dumps([{"id": f"PMID:{pmid}"}])

    where_clause = f"WHERE {' AND '.join(where_conditions)}"

    # Get sex distribution (don't apply sex filter for sex facet)
    sex_where = " AND ".join([c for c in where_conditions if "subject_sex" not in c])
    sex_query = f"""
        SELECT p.subject_sex AS value, COUNT(*) AS count
        FROM phenopackets p
        WHERE {sex_where}
        GROUP BY p.subject_sex
        ORDER BY count DESC
    """
    sex_result = await db.execute(text(sex_query), params)
    sex_facets = [
        {"value": row.value, "label": row.value, "count": row.count}
        for row in sex_result.fetchall()
    ]

    # Get has_variants distribution
    variants_query = f"""
        SELECT
            CASE
                WHEN jsonb_array_length(phenopacket->'interpretations') > 0 THEN true
                ELSE false
            END AS value,
            COUNT(*) AS count
        FROM phenopackets
        {where_clause}
        GROUP BY value
        ORDER BY value DESC
    """
    variants_result = await db.execute(text(variants_query), params)
    variants_facets = [
        {
            "value": row.value,
            "label": "Yes" if row.value else "No",
            "count": row.count,
        }
        for row in variants_result.fetchall()
    ]

    # Get pathogenicity distribution
    pathogenicity_query = f"""
        SELECT
            gi.value->'variantInterpretation'
                ->>'acmgPathogenicityClassification' AS value,
            COUNT(DISTINCT p.id) AS count
        FROM phenopackets p
        CROSS JOIN LATERAL jsonb_array_elements(
            p.phenopacket->'interpretations') AS interp
        CROSS JOIN LATERAL jsonb_array_elements(
            interp.value->'diagnosis'->'genomicInterpretations') AS gi
        {where_clause}
        AND gi.value->'variantInterpretation'
            ->>'acmgPathogenicityClassification' IS NOT NULL
        GROUP BY gi.value->'variantInterpretation'
            ->>'acmgPathogenicityClassification'
        ORDER BY count DESC
        LIMIT 20
    """
    pathogenicity_result = await db.execute(text(pathogenicity_query), params)
    pathogenicity_facets = [
        {"value": row.value, "label": row.value, "count": row.count}
        for row in pathogenicity_result.fetchall()
    ]

    # Get top genes
    genes_query = f"""
        SELECT
            gi.value->'variantInterpretation'->'variationDescriptor'
                ->'geneContext'->>'symbol' AS value,
            COUNT(DISTINCT p.id) AS count
        FROM phenopackets p
        CROSS JOIN LATERAL jsonb_array_elements(
            p.phenopacket->'interpretations') AS interp
        CROSS JOIN LATERAL jsonb_array_elements(
            interp.value->'diagnosis'->'genomicInterpretations') AS gi
        {where_clause}
        AND gi.value->'variantInterpretation'->'variationDescriptor'
            ->'geneContext'->>'symbol' IS NOT NULL
        GROUP BY gi.value->'variantInterpretation'->'variationDescriptor'
            ->'geneContext'->>'symbol'
        ORDER BY count DESC
        LIMIT 20
    """
    genes_result = await db.execute(text(genes_query), params)
    genes_facets = [
        {"value": row.value, "label": row.value, "count": row.count}
        for row in genes_result.fetchall()
    ]

    # Get top phenotypes
    phenotypes_query = f"""
        SELECT
            pf.value->'type'->>'id' AS hpo_id,
            pf.value->'type'->>'label' AS label,
            COUNT(DISTINCT p.id) AS count
        FROM phenopackets p
        CROSS JOIN LATERAL jsonb_array_elements(
            p.phenopacket->'phenotypicFeatures') AS pf
        {where_clause}
        AND pf.value->'type'->>'id' IS NOT NULL
        GROUP BY hpo_id, label
        ORDER BY count DESC
        LIMIT 20
    """
    phenotypes_result = await db.execute(text(phenotypes_query), params)
    phenotypes_facets = [
        {"value": row.hpo_id, "label": row.label, "count": row.count}
        for row in phenotypes_result.fetchall()
    ]

    return {
        "facets": {
            "sex": sex_facets,
            "hasVariants": variants_facets,
            "pathogenicity": pathogenicity_facets,
            "genes": genes_facets,
            "phenotypes": phenotypes_facets,
        }
    }
