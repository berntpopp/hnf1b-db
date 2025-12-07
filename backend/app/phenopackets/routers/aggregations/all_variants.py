"""All variants aggregation endpoint for phenopackets.

Provides comprehensive variant search with filtering, pagination, and sorting.
Extracted from the monolithic aggregations.py for better maintainability.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.rate_limiter import check_rate_limit, get_client_ip
from app.models.json_api import JsonApiResponse
from app.phenopackets.molecular_consequence import compute_molecular_consequence
from app.phenopackets.variant_search_validation import (
    validate_classification,
    validate_gene,
    validate_molecular_consequence,
    validate_search_query,
    validate_variant_type,
)
from app.utils.audit_logger import log_variant_search
from app.utils.pagination import build_offset_response

from .variant_query_builder import VariantQueryBuilder

router = APIRouter()


# HNF1B protein domain boundaries from UniProt P35680
DOMAIN_BOUNDARIES = {
    "Dimerization Domain": (1, 31),
    "POU-Specific Domain": (8, 173),
    "POU Homeodomain": (232, 305),
    "Transactivation Domain": (314, 557),
}

# Map frontend field names to SQL column names for sorting
SORT_FIELD_MAP = {
    "simple_id": "simple_id",
    "variant_id": "variant_id",
    "transcript": "transcript",
    "protein": "protein",
    "variant_type": "structural_type",
    "hg38": "hg38",
    "classificationVerdict": "pathogenicity",
    "individualCount": "phenopacket_count",
}


@router.get("/all-variants", response_model=JsonApiResponse)
async def aggregate_all_variants(
    request: Request,
    response: Response,
    page_number: int = Query(
        1, alias="page[number]", ge=1, description="Page number (1-indexed)"
    ),
    page_size: int = Query(
        100, alias="page[size]", ge=1, le=500, description="Page size"
    ),
    query: Optional[str] = Query(
        None,
        description="Search in HGVS notations, variant ID, or genomic coordinates",
    ),
    variant_type: Optional[str] = Query(
        None, description="Filter by variant type (SNV, deletion, etc.)"
    ),
    classification: Optional[str] = Query(
        None, description="Filter by ACMG classification"
    ),
    gene: Optional[str] = Query(None, description="Filter by gene symbol"),
    consequence: Optional[str] = Query(
        None, description="Filter by molecular consequence"
    ),
    domain: Optional[str] = Query(
        None, description="Filter by protein domain (e.g., 'POU-Specific Domain')"
    ),
    pathogenicity: Optional[str] = Query(
        None, description="DEPRECATED: use 'classification' instead"
    ),
    sort: Optional[str] = Query(
        None, description="Sort field with optional '-' prefix for descending"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Search and filter variants with offset pagination.

    Uses page[number] and page[size] for direct page access.

    **Search Fields:**
    - Transcript (c. notation): e.g., "c.1654-2A>T"
    - Protein (p. notation): e.g., "p.Arg177Ter"
    - Variant ID: e.g., "Var1", "ga4gh:VA.xxx"
    - HG38 Coordinates: e.g., "chr17:36098063"

    **Filters:**
    - variant_type: SNV, deletion, duplication, insertion, CNV
    - classification: PATHOGENIC, LIKELY_PATHOGENIC, etc.
    - gene: HNF1B
    - consequence: Frameshift, Nonsense, Missense, etc.
    - domain: POU-Specific Domain, POU Homeodomain, etc.
    """
    # Rate limiting (security layer)
    await check_rate_limit(request)

    # HTTP caching: 5 minutes for variant data
    response.headers["Cache-Control"] = "public, max-age=300"

    # Input validation (security layer)
    validated_query = validate_search_query(query)
    validated_variant_type = validate_variant_type(variant_type)
    validated_gene = validate_gene(gene)
    validated_consequence = validate_molecular_consequence(consequence)

    # Handle legacy 'pathogenicity' parameter
    classification_param = classification or pathogenicity
    validated_classification = validate_classification(classification_param)

    # Build query using fluent builder pattern
    builder = VariantQueryBuilder()

    if validated_query:
        builder.with_text_search(validated_query)
    if validated_variant_type:
        builder.with_variant_type(validated_variant_type)
    if validated_classification:
        builder.with_classification(validated_classification)
    if validated_gene:
        builder.with_gene_filter(validated_gene)
    if validated_consequence:
        builder.with_consequence(validated_consequence)
    if domain and domain in DOMAIN_BOUNDARIES:
        start_pos, end_pos = DOMAIN_BOUNDARIES[domain]
        builder.with_domain_filter(start_pos, end_pos)

    # Build ORDER BY clause
    sort_field = "phenopacket_count"
    sort_direction = "DESC"

    if sort:
        if sort.startswith("-"):
            sort_field = SORT_FIELD_MAP.get(sort[1:], "phenopacket_count")
            sort_direction = "DESC"
        else:
            sort_field = SORT_FIELD_MAP.get(sort, "phenopacket_count")
            sort_direction = "ASC"

    order_by = f"{sort_field} {sort_direction}, variant_id ASC"

    # Execute single query with window function for count
    query_sql, params = builder.build(
        order_by=order_by,
        limit=page_size,
        offset=(page_number - 1) * page_size,
    )
    result = await db.execute(text(query_sql), params)
    rows = list(result.fetchall())

    # Extract total count from window function (same for all rows)
    total_count = rows[0].total_count if rows else 0

    # Build response data
    variants = [
        {
            "simple_id": f"Var{row.simple_id}",
            "variant_id": row.variant_id,
            "label": row.label,
            "gene_symbol": row.gene_symbol,
            "gene_id": row.gene_id,
            "structural_type": row.structural_type,
            "pathogenicity": row.pathogenicity,
            "phenopacket_count": row.phenopacket_count,
            "hg38": row.hg38,
            "transcript": row.transcript,
            "protein": row.protein,
            "molecular_consequence": compute_molecular_consequence(
                transcript=row.transcript,
                protein=row.protein,
                variant_type=row.structural_type,
                vep_extensions=row.vep_extensions if row.vep_extensions else None,
            ),
        }
        for row in rows
    ]

    # Audit logging (GDPR compliance)
    log_variant_search(
        client_ip=get_client_ip(request),
        user_id=None,
        query=validated_query,
        variant_type=validated_variant_type,
        classification=validated_classification,
        gene=validated_gene,
        consequence=validated_consequence,
        result_count=len(variants),
        request_path=str(request.url.path),
    )

    # Build filter dict for pagination links
    filters: Dict[str, Any] = {}
    if validated_query:
        filters["query"] = validated_query
    if validated_variant_type:
        filters["variant_type"] = validated_variant_type
    if validated_classification:
        filters["classification"] = validated_classification
    if validated_gene:
        filters["gene"] = validated_gene
    if validated_consequence:
        filters["consequence"] = validated_consequence
    if domain:
        filters["domain"] = domain

    # Build JSON:API offset response
    base_url = str(request.url.path)
    return build_offset_response(
        data=variants,
        current_page=page_number,
        page_size=page_size,
        total_records=total_count,
        base_url=base_url,
        filters=filters,
        sort=sort,
    )
