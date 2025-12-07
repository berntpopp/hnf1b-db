"""All variants aggregation endpoint for phenopackets.

Provides comprehensive variant search with filtering, pagination, and sorting.
Extracted from the monolithic aggregations.py for better maintainability.
"""

from typing import Any, Dict, List, Optional

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


def _build_text_search_clause(validated_query: str) -> str:
    """Build SQL WHERE clause for text search."""
    return """(
        vd->>'id' ILIKE :query
        OR vd->>'label' ILIKE :query
        OR vd->>'description' ILIKE :query
        OR EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') AS expr
            WHERE expr->>'value' ILIKE :query
        )
        OR COALESCE(
            NULLIF(CONCAT(
                COALESCE(vd->'vcfRecord'->>'chrom', ''), ':',
                COALESCE(vd->'vcfRecord'->>'pos', ''), ':',
                COALESCE(vd->'vcfRecord'->>'ref', ''), ':',
                COALESCE(vd->'vcfRecord'->>'alt', '')
            ), ':::'),
            ''
        ) ILIKE :query
    )"""


def _build_variant_type_clause(variant_type: str) -> str:
    """Build SQL WHERE clause for variant type filtering."""
    clauses = {
        "CNV": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'value' ~ ':\\d+-\\d+:'
        )""",
        "indel": """(
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.c'
                AND elem->>'value' ~ 'del|ins|delins'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'value' ~ ':\\d+-\\d+:'
            )
        )""",
        "deletion": """(
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.c'
                AND elem->>'value' ~ 'del'
                AND elem->>'value' !~ 'dup'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'value' ~ ':\\d+-\\d+:'
            )
        )""",
        "duplication": """(
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.c'
                AND elem->>'value' ~ 'dup'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'value' ~ ':\\d+-\\d+:'
            )
        )""",
        "insertion": """(
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.c'
                AND elem->>'value' ~ 'ins'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'value' ~ ':\\d+-\\d+:'
            )
        )""",
        "SNV": """(
            vd->>'moleculeContext' = 'genomic'
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'value' ~ 'del|ins|dup|delins'
            )
        )""",
    }
    return clauses.get(variant_type, "")


def _build_consequence_clause(consequence: str) -> str:
    """Build SQL WHERE clause for molecular consequence filtering."""
    clauses = {
        "Frameshift": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.p'
            AND elem->>'value' ~* 'fs'
        )""",
        "Nonsense": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.p'
            AND (elem->>'value' ~* 'ter' OR elem->>'value' ~ '\\*')
        )""",
        "Missense": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.p'
            AND elem->>'value' ~ '[A-Z][a-z]{2}\\d+[A-Z][a-z]{2}'
            AND elem->>'value' !~* 'ter|fs|del|ins|='
        )""",
        "Splice Donor": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.c'
            AND elem->>'value' ~ '\\+[1-6]'
        )""",
        "Splice Acceptor": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.c'
            AND elem->>'value' ~ '-[1-3]'
        )""",
        "In-frame Deletion": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.p'
            AND elem->>'value' ~* 'del'
            AND elem->>'value' !~* 'fs'
        )""",
        "In-frame Insertion": """EXISTS (
            SELECT 1
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.p'
            AND elem->>'value' ~* 'ins'
            AND elem->>'value' !~* 'fs'
        )""",
    }
    return clauses.get(consequence, "")


def _build_domain_clause() -> str:
    """Build SQL WHERE clause for protein domain filtering."""
    return """EXISTS (
        SELECT 1
        FROM jsonb_array_elements(vd->'expressions') elem
        WHERE elem->>'syntax' = 'hgvs.p'
        AND elem->>'value' ~ 'p\\.[A-Z][a-z]{2}(\\d+)'
        AND (
            regexp_match(elem->>'value', 'p\\.[A-Z][a-z]{2}(\\d+)')
        )[1]::int BETWEEN :domain_start AND :domain_end
    )"""


def _build_where_clauses(
    validated_query: Optional[str],
    validated_variant_type: Optional[str],
    validated_classification: Optional[str],
    validated_gene: Optional[str],
    validated_consequence: Optional[str],
    domain: Optional[str],
    params: Dict[str, Any],
) -> List[str]:
    """Build list of WHERE clauses based on filter parameters."""
    where_clauses = []

    # Text search
    if validated_query and not validated_query.lower().startswith("var"):
        where_clauses.append(_build_text_search_clause(validated_query))
        params["query"] = f"%{validated_query}%"
        params["simple_id_query"] = f"%{validated_query}%"
    elif validated_query:
        params["query"] = f"%{validated_query}%"
        params["simple_id_query"] = f"%{validated_query}%"

    # Variant type filter
    if validated_variant_type:
        clause = _build_variant_type_clause(validated_variant_type)
        if clause:
            where_clauses.append(clause)
        else:
            # Fallback for other types
            where_clauses.append(
                """COALESCE(
                    vd->'structuralType'->>'label',
                    CASE
                        WHEN vd->'vcfRecord'->>'alt' ~
                            '^<(DEL|DUP|INS|INV|CNV)' THEN 'CNV'
                        WHEN vd->>'moleculeContext' = 'genomic' THEN 'SNV'
                        ELSE 'OTHER'
                    END
                ) = :variant_type"""
            )
            params["variant_type"] = validated_variant_type

    # Classification filter
    if validated_classification:
        where_clauses.append("gi->>'interpretationStatus' = :classification")
        params["classification"] = validated_classification

    # Gene filter
    if validated_gene:
        where_clauses.append("vd->'geneContext'->>'symbol' = :gene")
        params["gene"] = validated_gene

    # Molecular consequence filter
    if validated_consequence:
        clause = _build_consequence_clause(validated_consequence)
        if clause:
            where_clauses.append(clause)

    # Protein domain filter
    if domain and domain in DOMAIN_BOUNDARIES:
        start_pos, end_pos = DOMAIN_BOUNDARIES[domain]
        where_clauses.append(_build_domain_clause())
        params["domain_start"] = start_pos
        params["domain_end"] = end_pos

    return where_clauses


# SQL fragment for structural type classification
STRUCTURAL_TYPE_CASE = """
COALESCE(
    vd->'structuralType'->>'label',
    CASE
        WHEN (
            SELECT elem->>'value'
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.c'
            LIMIT 1
        ) ~ 'del[A-Z]*ins' THEN 'indel'
        WHEN (
            SELECT elem->>'value'
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.c'
            LIMIT 1
        ) ~ 'ins' AND (
            SELECT elem->>'value'
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.c'
            LIMIT 1
        ) !~ 'del' THEN 'insertion'
        WHEN (
            SELECT elem->>'value'
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.c'
            LIMIT 1
        ) ~ 'del' AND (
            SELECT elem->>'value'
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.c'
            LIMIT 1
        ) !~ 'ins' THEN 'deletion'
        WHEN (
            SELECT elem->>'value'
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.c'
            LIMIT 1
        ) ~ 'dup' THEN 'duplication'
        WHEN vd->'vcfRecord'->>'alt' ~ '^<(DEL|DUP|INS|INV|CNV)' THEN 'CNV'
        WHEN vd->>'moleculeContext' = 'genomic' THEN 'SNV'
        ELSE 'OTHER'
    END,
    vd->'molecularConsequences'->0->>'label'
)
"""


def _build_main_query(
    where_sql: str, order_by: str, validated_query: Optional[str]
) -> str:
    """Build the main variant aggregation SQL query."""
    simple_id_filter = (
        "AND CONCAT('Var', simple_id::text) ILIKE :simple_id_query"
        if validated_query and validated_query.lower().startswith("var")
        else ""
    )

    return f"""
    WITH all_variants_unfiltered AS (
        SELECT DISTINCT ON (vd->>'id', p.id)
            vd->>'id' as variant_id,
            vd->'geneContext'->>'symbol' as gene_symbol,
            p.id as phenopacket_id
        FROM
            phenopackets p,
            jsonb_array_elements(p.phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
            LATERAL (SELECT gi->'variantInterpretation' as vi) vi_lateral,
            LATERAL (SELECT vi_lateral.vi->'variationDescriptor' as vd) vd_lateral
        WHERE
            vi_lateral.vi IS NOT NULL
            AND vd_lateral.vd IS NOT NULL
    ),
    all_variants_agg AS (
        SELECT
            variant_id,
            MAX(gene_symbol) as gene_symbol,
            COUNT(DISTINCT phenopacket_id) as phenopacket_count
        FROM all_variants_unfiltered
        GROUP BY variant_id
    ),
    all_variants_with_stable_id AS (
        SELECT
            ROW_NUMBER() OVER (
                ORDER BY phenopacket_count DESC, gene_symbol ASC, variant_id ASC
            ) as simple_id,
            variant_id
        FROM all_variants_agg
    ),
    variant_raw AS (
        SELECT DISTINCT ON (vd->>'id', p.id)
            vd->>'id' as variant_id,
            vd->>'label' as label,
            vd->'geneContext'->>'symbol' as gene_symbol,
            vd->'geneContext'->>'valueId' as gene_id,
            {STRUCTURAL_TYPE_CASE} as structural_type,
            COALESCE(
                vi->>'acmgPathogenicityClassification',
                gi->>'interpretationStatus'
            ) as pathogenicity,
            COALESCE(
                NULLIF(CONCAT(
                    COALESCE(vd->'vcfRecord'->>'chrom', ''), ':',
                    COALESCE(vd->'vcfRecord'->>'pos', ''), ':',
                    COALESCE(vd->'vcfRecord'->>'ref', ''), ':',
                    COALESCE(vd->'vcfRecord'->>'alt', '')
                ), ':::'),
                (
                    SELECT elem->>'value'
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' IN ('vcf', 'ga4gh', 'text')
                    LIMIT 1
                ),
                vd->>'description'
            ) as hg38,
            (
                SELECT elem->>'value'
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.c'
                LIMIT 1
            ) as transcript,
            (
                SELECT elem->>'value'
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.p'
                LIMIT 1
            ) as protein,
            vd->'extensions' as vep_extensions,
            p.id as phenopacket_id
        FROM
            phenopackets p,
            jsonb_array_elements(p.phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
            LATERAL (SELECT gi->'variantInterpretation' as vi) vi_lateral,
            LATERAL (SELECT vi_lateral.vi->'variationDescriptor' as vd) vd_lateral
        WHERE
            vi_lateral.vi IS NOT NULL
            AND vd_lateral.vd IS NOT NULL
            {where_sql}
    ),
    variant_agg AS (
        SELECT
            variant_id,
            MAX(label) as label,
            MAX(gene_symbol) as gene_symbol,
            MAX(gene_id) as gene_id,
            MAX(structural_type) as structural_type,
            MAX(pathogenicity) as pathogenicity,
            MAX(hg38) as hg38,
            MAX(transcript) as transcript,
            MAX(protein) as protein,
            (ARRAY_AGG(vep_extensions))[1] as vep_extensions,
            COUNT(DISTINCT phenopacket_id) as phenopacket_count
        FROM variant_raw
        GROUP BY variant_id
    ),
    variant_with_stable_id AS (
        SELECT
            avwsi.simple_id,
            va.variant_id,
            va.label,
            va.gene_symbol,
            va.gene_id,
            va.structural_type,
            va.pathogenicity,
            va.phenopacket_count,
            va.hg38,
            va.transcript,
            va.protein,
            va.vep_extensions
        FROM variant_agg va
        INNER JOIN all_variants_with_stable_id avwsi ON va.variant_id = avwsi.variant_id
    )
    SELECT *
    FROM variant_with_stable_id
    WHERE 1=1
        {simple_id_filter}
    ORDER BY {order_by}
    LIMIT :limit
    OFFSET :offset
    """


def _build_count_query(where_sql: str, validated_query: Optional[str]) -> str:
    """Build the COUNT query for pagination."""
    simple_id_filter = (
        "AND CONCAT('Var', simple_id::text) ILIKE :simple_id_query"
        if validated_query and validated_query.lower().startswith("var")
        else ""
    )

    return f"""
    WITH all_variants_unfiltered AS (
        SELECT DISTINCT ON (vd->>'id', p.id)
            vd->>'id' as variant_id,
            vd->'geneContext'->>'symbol' as gene_symbol,
            p.id as phenopacket_id
        FROM
            phenopackets p,
            jsonb_array_elements(p.phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
            LATERAL (SELECT gi->'variantInterpretation' as vi) vi_lateral,
            LATERAL (SELECT vi_lateral.vi->'variationDescriptor' as vd) vd_lateral
        WHERE
            vi_lateral.vi IS NOT NULL
            AND vd_lateral.vd IS NOT NULL
    ),
    variant_raw AS (
        SELECT DISTINCT ON (vd->>'id', p.id)
            vd->>'id' as variant_id,
            p.id as phenopacket_id
        FROM
            phenopackets p,
            jsonb_array_elements(p.phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
            LATERAL (SELECT gi->'variantInterpretation' as vi) vi_lateral,
            LATERAL (SELECT vi_lateral.vi->'variationDescriptor' as vd) vd_lateral
        WHERE
            vi_lateral.vi IS NOT NULL
            AND vd_lateral.vd IS NOT NULL
            {where_sql}
    ),
    variant_agg AS (
        SELECT variant_id, COUNT(DISTINCT phenopacket_id) as phenopacket_count
        FROM variant_raw
        GROUP BY variant_id
    ),
    all_variants_with_stable_id AS (
        SELECT
            ROW_NUMBER() OVER (
                ORDER BY (
                    SELECT COUNT(DISTINCT phenopacket_id)
                    FROM all_variants_unfiltered
                    WHERE all_variants_unfiltered.variant_id = a.variant_id
                ) DESC, a.variant_id ASC
            ) as simple_id,
            a.variant_id
        FROM (SELECT DISTINCT variant_id FROM all_variants_unfiltered) a
    ),
    variant_with_stable_id AS (
        SELECT avwsi.simple_id, va.variant_id
        FROM variant_agg va
        INNER JOIN all_variants_with_stable_id avwsi ON va.variant_id = avwsi.variant_id
    )
    SELECT COUNT(*) as total
    FROM variant_with_stable_id
    WHERE 1=1
        {simple_id_filter}
    """


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

    # Build query parameters
    params: Dict[str, Any] = {
        "limit": page_size,
        "offset": (page_number - 1) * page_size,
    }

    # Build WHERE clauses
    where_clauses = _build_where_clauses(
        validated_query,
        validated_variant_type,
        validated_classification,
        validated_gene,
        validated_consequence,
        domain,
        params,
    )

    where_sql = "AND " + " AND ".join(where_clauses) if where_clauses else ""

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

    # Execute COUNT query
    count_sql = _build_count_query(where_sql, validated_query)
    count_result = await db.execute(text(count_sql), params)
    total_count = count_result.scalar() or 0

    # Execute main query
    query_sql = _build_main_query(where_sql, order_by, validated_query)
    result = await db.execute(text(query_sql), params)
    rows = list(result.fetchall())

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
