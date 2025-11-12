"""Full-text and structured search for phenopackets."""

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get("/search")
async def search_phenopackets(
    q: Optional[str] = Query(None, description="Full-text search query"),
    hpo_id: Optional[str] = Query(None, description="Filter by HPO term ID"),
    sex: Optional[str] = Query(None, description="Filter by subject sex"),
    gene: Optional[str] = Query(None, description="Filter by gene symbol"),
    pmid: Optional[str] = Query(None, description="Filter by publication PMID"),
    rank_by_relevance: bool = Query(True, description="Sort by search rank"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Advanced phenopacket search with full-text and structured filters."""
    # Base query parts
    select_clause = "SELECT id, phenopacket_id, phenopacket"
    from_clause = "FROM phenopackets"
    where_conditions = []
    params: Dict[str, Any] = {"limit": limit, "offset": skip}
    order_by_clause = ""

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
        if rank_by_relevance:
            order_by_clause = "ORDER BY search_rank DESC"

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

    # Construct the final query
    where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

    # Get total count
    count_query_str = f"SELECT COUNT(*) {from_clause} {where_clause}"
    total_result = await db.execute(text(count_query_str), params)
    total = total_result.scalar_one()

    # Get paginated results
    query_str = (
        f"{select_clause} {from_clause} {where_clause} {order_by_clause} "
        "LIMIT :limit OFFSET :offset"
    )
    result = await db.execute(text(query_str), params)
    phenopackets = result.fetchall()

    # Format response
    data = [
        {
            "id": pp.phenopacket_id,
            "type": "phenopacket",
            "attributes": pp.phenopacket,
            "meta": {"search_rank": pp.search_rank if q else None},
        }
        for pp in phenopackets
    ]

    return {
        "data": data,
        "meta": {"total": total},
    }


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
    where_conditions = []
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

    where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

    # Get sex distribution
    sex_query = f"""
        SELECT p.subject_sex AS value, COUNT(*) AS count
        FROM phenopackets p
        {where_clause if not sex else ""}
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
            gi.value->'variantInterpretation'->>
                'acmgPathogenicityClassification' AS value,
            COUNT(DISTINCT p.id) AS count
        FROM phenopackets p
        CROSS JOIN LATERAL jsonb_array_elements(
            p.phenopacket->'interpretations'
        ) AS interp
        CROSS JOIN LATERAL jsonb_array_elements(
            interp.value->'diagnosis'->'genomicInterpretations'
        ) AS gi
        {where_clause}
        {"AND" if where_conditions else "WHERE"} gi.value->'variantInterpretation'->>
            'acmgPathogenicityClassification' IS NOT NULL
        GROUP BY gi.value->'variantInterpretation'->>'acmgPathogenicityClassification'
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
            gi.value->'variantInterpretation'->
                'variationDescriptor'->'geneContext'->>'symbol' AS value,
            COUNT(DISTINCT p.id) AS count
        FROM phenopackets p
        CROSS JOIN LATERAL jsonb_array_elements(
            p.phenopacket->'interpretations'
        ) AS interp
        CROSS JOIN LATERAL jsonb_array_elements(
            interp.value->'diagnosis'->'genomicInterpretations'
        ) AS gi
        {where_clause}
        {"AND" if where_conditions else "WHERE"} gi.value->'variantInterpretation'->
            'variationDescriptor'->'geneContext'->>'symbol' IS NOT NULL
        GROUP BY gi.value->'variantInterpretation'->
            'variationDescriptor'->'geneContext'->>'symbol'
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
            p.phenopacket->'phenotypicFeatures'
        ) AS pf
        {where_clause}
        {"AND" if where_conditions else "WHERE"} pf.value->'type'->>'id' IS NOT NULL
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
