"""Aggregation and statistical endpoints for phenopackets.

Provides statistical summaries, aggregations by features, diseases,
variants, and publications.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.rate_limiter import check_rate_limit, get_client_ip
from app.phenopackets.models import (
    AggregationResult,
    Phenopacket,
)
from app.phenopackets.molecular_consequence import compute_molecular_consequence
from app.phenopackets.variant_search_validation import (
    validate_classification,
    validate_gene,
    validate_molecular_consequence,
    validate_search_query,
    validate_variant_type,
)
from app.utils.audit_logger import log_variant_search

router = APIRouter(prefix="/aggregate", tags=["phenopackets-aggregations"])


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
    """
    # First, get total number of phenopackets
    total_phenopackets_result = await db.execute(
        text("SELECT COUNT(*) as total FROM phenopackets")
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
    GROUP BY
        feature->'type'->>'id',
        feature->'type'->>'label'
    ORDER BY
        present_count DESC
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    # Calculate total for percentage (sum of all present counts)
    total = sum(int(row._mapping["present_count"]) for row in rows)

    return [
        AggregationResult(
            label=row.label or row.hpo_id,
            count=int(row._mapping["present_count"]),
            percentage=(int(row._mapping["present_count"]) / total * 100)
            if total > 0
            else 0,
            details={
                "hpo_id": row.hpo_id,
                "present_count": int(row._mapping["present_count"]),
                "absent_count": int(row._mapping["absent_count"]),
                "not_reported_count": total_phenopackets
                - int(row._mapping["present_count"])
                - int(row._mapping["absent_count"]),
            },
        )
        for row in rows
    ]


@router.get("/by-disease", response_model=List[AggregationResult])
async def aggregate_by_disease(
    db: AsyncSession = Depends(get_db),
):
    """Aggregate phenopackets by disease."""
    query = """
    SELECT
        disease->'term'->>'id' as disease_id,
        disease->'term'->>'label' as label,
        COUNT(*) as count
    FROM
        phenopackets,
        jsonb_array_elements(phenopacket->'diseases') as disease
    GROUP BY
        disease->'term'->>'id',
        disease->'term'->>'label'
    ORDER BY
        count DESC
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(int(row._mapping["count"]) for row in rows)

    return [
        AggregationResult(
            label=row.label or row.disease_id,
            count=int(row._mapping["count"]),
            percentage=(int(row._mapping["count"]) / total * 100) if total > 0 else 0,
            details={"disease_id": row.disease_id},
        )
        for row in rows
    ]


@router.get("/kidney-stages", response_model=List[AggregationResult])
async def aggregate_kidney_stages(
    db: AsyncSession = Depends(get_db),
):
    """Get distribution of kidney disease stages."""
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


@router.get("/sex-distribution", response_model=List[AggregationResult])
async def aggregate_sex_distribution(
    db: AsyncSession = Depends(get_db),
):
    """Get sex distribution of subjects."""
    query = """
    SELECT
        subject_sex as sex,
        COUNT(*) as count
    FROM
        phenopackets
    GROUP BY
        subject_sex
    ORDER BY
        count DESC
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(int(row._mapping["count"]) for row in rows)

    return [
        AggregationResult(
            label=row.sex,
            count=int(row._mapping["count"]),
            percentage=(int(row._mapping["count"]) / total * 100) if total > 0 else 0,
        )
        for row in rows
    ]


@router.get("/variant-pathogenicity", response_model=List[AggregationResult])
async def aggregate_variant_pathogenicity(
    count_mode: str = Query(
        "all",
        regex="^(all|unique)$",
        description=(
            "Count mode: 'all' (default) counts all variant instances, "
            "'unique' counts distinct variants"
        ),
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get distribution of variant pathogenicity classifications.

    Args:
        count_mode:
            - "all" (default): Count all variant instances across
              phenopackets (e.g., 864 total)
            - "unique": Count only unique variants (deduplicates by
              variant ID)
        db: Database session dependency
    """
    if count_mode == "unique":
        # Count unique variants by variant ID
        query = """
        SELECT
            gi->>'interpretationStatus' as classification,
            COUNT(DISTINCT vd->>'id') as count
        FROM
            phenopackets,
            jsonb_array_elements(phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
            LATERAL (
                SELECT gi->'variantInterpretation'->'variationDescriptor' as vd
            ) sub
        WHERE
            gi->'variantInterpretation'->'variationDescriptor' IS NOT NULL
        GROUP BY
            gi->>'interpretationStatus'
        ORDER BY
            count DESC
        """
    else:
        # Count all variant instances (original behavior)
        query = """
        SELECT
            gi->>'interpretationStatus' as classification,
            COUNT(*) as count
        FROM
            phenopackets,
            jsonb_array_elements(phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
        GROUP BY
            gi->>'interpretationStatus'
        ORDER BY
            count DESC
        """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(int(row._mapping["count"]) for row in rows)

    return [
        AggregationResult(
            label=row.classification,
            count=int(row._mapping["count"]),
            percentage=(int(row._mapping["count"]) / total * 100) if total > 0 else 0,
        )
        for row in rows
    ]


@router.get("/variant-types", response_model=List[AggregationResult])
async def aggregate_variant_types(
    count_mode: str = Query(
        "all",
        regex="^(all|unique)$",
        description=(
            "Count mode: 'all' (default) counts all variant instances, "
            "'unique' counts distinct variants"
        ),
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get distribution of variant types (SNV, CNV, etc.).

    Args:
        count_mode:
            - "all" (default): Count all variant instances across
              phenopackets (e.g., 864 total)
            - "unique": Count only unique variants (deduplicates by
              variant ID)
        db: Database session dependency
    """
    # Variant type detection logic:
    # - Copy Number Loss/Gain: Large structural variants >= 0.1 Mb
    # - Deletion/Duplication: Smaller variants (structural <0.1 Mb or from c. notation)
    # - Insertion/Indel/SNV: From c. notation patterns
    # Size threshold: 0.1 Mb (100kb) distinguishes CNVs from smaller variants
    variant_type_case = """
        CASE
            -- Large structural variants: parse size from label (e.g., "1.37Mb del")
            WHEN vd->'structuralType'->>'label' IN ('deletion', 'duplication') THEN
                CASE
                    WHEN COALESCE(
                        NULLIF(
                            regexp_replace(vd->>'label', '^([0-9.]+)Mb.*', '\\1'),
                            vd->>'label'
                        )::numeric,
                        0
                    ) >= 0.1 THEN
                        CASE
                            WHEN vd->'structuralType'->>'label' = 'deletion'
                                THEN 'Copy Number Loss'
                            ELSE 'Copy Number Gain'
                        END
                    -- Smaller structural variants (<0.1 Mb)
                    WHEN vd->'structuralType'->>'label' = 'deletion'
                        THEN 'Deletion'
                    ELSE 'Duplication'
                END
            -- Small variants: detect type from c. notation
            WHEN vd->'structuralType'->>'label' IS NULL THEN
                CASE
                    -- Indel: delins pattern
                    WHEN EXISTS (
                        SELECT 1 FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'syntax' = 'hgvs.c'
                        AND elem->>'value' ~ 'delins'
                    ) THEN 'Indel'
                    -- Small deletion
                    WHEN EXISTS (
                        SELECT 1 FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'syntax' = 'hgvs.c'
                        AND elem->>'value' ~ 'del'
                    ) THEN 'Deletion'
                    -- Duplication
                    WHEN EXISTS (
                        SELECT 1 FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'syntax' = 'hgvs.c'
                        AND elem->>'value' ~ 'dup'
                    ) THEN 'Duplication'
                    -- Insertion
                    WHEN EXISTS (
                        SELECT 1 FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'syntax' = 'hgvs.c'
                        AND elem->>'value' ~ 'ins'
                    ) THEN 'Insertion'
                    -- SNV: substitution pattern
                    WHEN EXISTS (
                        SELECT 1 FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'syntax' = 'hgvs.c'
                        AND elem->>'value' ~ '>[ACGT]'
                    ) THEN 'SNV'
                    ELSE 'NA'
                END
            ELSE 'NA'
        END
    """

    if count_mode == "unique":
        # Count unique variants by variant ID
        query = f"""
        WITH variant_types AS (
            SELECT DISTINCT
                vd->>'id' as variant_id,
                {variant_type_case} as variant_type
            FROM
                phenopackets,
                jsonb_array_elements(phenopacket->'interpretations') as interp,
                jsonb_array_elements(
                    interp->'diagnosis'->'genomicInterpretations'
                ) as gi,
                LATERAL (
                SELECT gi->'variantInterpretation'->'variationDescriptor' as vd
            ) sub
            WHERE
                gi->'variantInterpretation'->'variationDescriptor' IS NOT NULL
        )
        SELECT
            variant_type,
            COUNT(*) as count
        FROM variant_types
        GROUP BY variant_type
        ORDER BY count DESC
        """
    else:
        # Count all variant instances
        query = f"""
        SELECT
            {variant_type_case} as variant_type,
            COUNT(*) as count
        FROM
            phenopackets,
            jsonb_array_elements(phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
            LATERAL (
                SELECT gi->'variantInterpretation'->'variationDescriptor' as vd
            ) sub
        WHERE
            gi->'variantInterpretation'->'variationDescriptor' IS NOT NULL
        GROUP BY
            variant_type
        ORDER BY
            count DESC
        """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(int(row._mapping["count"]) for row in rows)

    return [
        AggregationResult(
            label=row.variant_type,
            count=int(row._mapping["count"]),
            percentage=(int(row._mapping["count"]) / total * 100) if total > 0 else 0,
        )
        for row in rows
    ]


@router.get("/publications", response_model=List[Dict])
async def aggregate_publications(
    db: AsyncSession = Depends(get_db),
):
    """Get publication statistics with detailed information.

    Returns detailed publication data including PMID, URL, DOI, phenopacket count.
    Suitable for publications table view.
    """
    query = """
    SELECT
        ext_ref->>'id' as pmid,
        ext_ref->>'reference' as url,
        ext_ref->>'description' as description,
        COUNT(DISTINCT phenopacket_id) as phenopacket_count,
        MIN(created_at) as first_added
    FROM
        phenopackets,
        jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
    WHERE
        ext_ref->>'id' LIKE 'PMID:%'
    GROUP BY
        ext_ref->>'id',
        ext_ref->>'reference',
        ext_ref->>'description'
    ORDER BY
        phenopacket_count DESC, pmid
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    return [
        {
            "pmid": row.pmid.replace("PMID:", "") if row.pmid else None,
            "url": row.url,
            "doi": (
                row.description.replace("DOI:", "")
                if row.description and row.description.startswith("DOI:")
                else None
            ),
            "phenopacket_count": row.phenopacket_count,
            "first_added": (row.first_added.isoformat() if row.first_added else None),
        }
        for row in rows
    ]


@router.get("/publication-types", response_model=List[AggregationResult])
async def aggregate_publication_types(
    db: AsyncSession = Depends(get_db),
):
    """Get distribution of publication types.

    Aggregates phenopackets by publication type (case_series, research, case_report, etc.).
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


@router.get("/all-variants")
async def aggregate_all_variants(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
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
    """Search and filter variants across all phenopackets.

    Aggregates variants from all phenopackets and returns unique variants
    with their details and the count of individuals carrying each variant.

    **Search Fields (8 total):**
    1. **Transcript (c. notation)**: e.g., "c.1654-2A>T"
    2. **Protein (p. notation)**: e.g., "p.Arg177Ter"
    3. **Variant ID**: e.g., "Var1", "ga4gh:VA.xxx"
    4. **HG38 Coordinates**: e.g., "chr17:36098063", "17:36459258-37832869"
    5. **Variant Type**: SNV, deletion, duplication, insertion, inversion, CNV
    6. **Classification**: PATHOGENIC, LIKELY_PATHOGENIC, etc.
    7. **Gene Symbol**: HNF1B
    8. **Molecular Consequence**: Frameshift, Nonsense, Missense, etc.

    Args:
        request: FastAPI request object for rate limiting
        query: Text search across HGVS notations, variant IDs, and coordinates
        variant_type: Filter by variant structural type
        classification: Filter by ACMG pathogenicity classification
        gene: Filter by gene symbol (e.g., "HNF1B")
        consequence: Filter by molecular consequence (e.g., "Frameshift")
        domain: Filter by protein domain (e.g., "POU-Specific Domain")
        limit: Maximum number of variants to return (default: 100, max: 1000)
        skip: Number of variants to skip for pagination (default: 0)
        sort: Sort field with optional '-' prefix for descending
            (e.g., 'simple_id', '-individualCount')
        pathogenicity: DEPRECATED - use 'classification' instead
        db: Database session

    Returns:
        List of unique variants with:
        - simple_id: User-friendly variant ID (e.g., "Var1")
        - variant_id: VRS ID or custom identifier
        - label: Human-readable variant description
        - gene_symbol: Gene symbol (e.g., "HNF1B")
        - gene_id: HGNC ID (e.g., "HGNC:5024")
        - structural_type: Variant type (e.g., "deletion", "SNV")
        - pathogenicity: ACMG classification
        - phenopacket_count: Number of individuals with this variant
        - hg38: Genomic coordinates or VCF string
        - transcript: HGVS c. notation
        - protein: HGVS p. notation
        - molecular_consequence: Computed molecular consequence

    Security:
        - All inputs validated with character whitelists
        - HGVS format validation
        - SQL injection prevention via parameterized queries
        - Length limits enforced (max 200 chars)

    Examples:
        # Search by HGVS notation
        GET /aggregate/all-variants?query=c.1654-2A>T

        # Search by genomic coordinates
        GET /aggregate/all-variants?query=chr17:36098063

        # Filter pathogenic deletions
        GET /aggregate/all-variants?variant_type=deletion&classification=PATHOGENIC

        # Search with molecular consequence filter
        GET /aggregate/all-variants?query=frameshift&consequence=Frameshift

        # Combined search and filters
        GET /aggregate/all-variants?query=HNF1B&variant_type=SNV&
            classification=PATHOGENIC
    """
    # Rate limiting (security layer)
    check_rate_limit(request)

    # Input validation (security layer)
    validated_query = validate_search_query(query)
    validated_variant_type = validate_variant_type(variant_type)
    validated_gene = validate_gene(gene)
    validated_consequence = validate_molecular_consequence(consequence)

    # Handle legacy 'pathogenicity' parameter (maintain backwards compatibility)
    classification_param = classification or pathogenicity
    validated_classification = validate_classification(classification_param)

    # Build query with optional filters
    where_clauses = []
    params: Dict[str, Any] = {"limit": limit, "offset": skip}

    # Text search: Search across HGVS notations, variant IDs, and coordinates
    if validated_query:
        # If query starts with "var", we'll search by simple_id after the join
        # Otherwise, search in JSONB fields
        if not validated_query.lower().startswith("var"):
            where_clauses.append(
                """(
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
            )
        params["query"] = f"%{validated_query}%"
        params["simple_id_query"] = f"%{validated_query}%"

    # Variant type filter
    # Filter logic must match frontend display in getVariantType()
    if validated_variant_type:
        if validated_variant_type == "CNV":
            # CNVs: Large structural variants with coordinate range format
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'value' ~ ':\\d+-\\d+:'
                )"""
            )
        elif validated_variant_type == "indel":
            # Indel: Small insertions, deletions, and complex indels (< 50bp)
            # Includes: del, ins, delins - but NOT CNVs
            where_clauses.append(
                """(
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
                )"""
            )
        elif validated_variant_type == "deletion":
            # Small deletions: Has 'del' in c. notation but NOT a CNV
            where_clauses.append(
                """(
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
                )"""
            )
        elif validated_variant_type == "duplication":
            # Small duplications: Has 'dup' in c. notation but NOT a CNV
            where_clauses.append(
                """(
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
                )"""
            )
        elif validated_variant_type == "insertion":
            # Insertions: Has 'ins' in c. notation but NOT a CNV
            where_clauses.append(
                """(
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
                )"""
            )
        elif validated_variant_type == "SNV":
            # SNVs: Match genomic context but exclude deletions/insertions/duplications
            # True SNVs are substitutions (>) without del/ins/dup keywords
            where_clauses.append(
                """(
                    vd->>'moleculeContext' = 'genomic'
                    AND NOT EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'value' ~ 'del|ins|dup|delins'
                    )
                )"""
            )
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

    # Molecular consequence filter (SQL-based for correct pagination)
    # Translate Python consequence logic to SQL WHERE clauses
    if validated_consequence:
        if validated_consequence == "Frameshift":
            # Protein notation contains 'fs' (frameshift)
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.p'
                    AND elem->>'value' ~* 'fs'
                )"""
            )
        elif validated_consequence == "Nonsense":
            # Protein notation contains 'Ter' or '*' (stop gained)
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.p'
                    AND (elem->>'value' ~* 'ter' OR elem->>'value' ~ '\\*')
                )"""
            )
        elif validated_consequence == "Missense":
            # Protein notation is amino acid substitution (e.g., p.Arg177Cys)
            # Pattern: three-letter amino acid, digits, three-letter amino acid
            # NOT containing 'Ter', 'fs', 'del', 'ins', or '='
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.p'
                    AND elem->>'value' ~ '[A-Z][a-z]{2}\\d+[A-Z][a-z]{2}'
                    AND elem->>'value' !~* 'ter|fs|del|ins|='
                )"""
            )
        elif validated_consequence == "Splice Donor":
            # Transcript notation with +1 to +6 (e.g., c.544+1G>T)
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.c'
                    AND elem->>'value' ~ '\\+[1-6]'
                )"""
            )
        elif validated_consequence == "Splice Acceptor":
            # Transcript notation with -1 to -3 (e.g., c.1654-2A>T)
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.c'
                    AND elem->>'value' ~ '-[1-3]'
                )"""
            )
        elif validated_consequence == "In-frame Deletion":
            # Protein notation contains 'del' but NOT 'fs' (frameshift)
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.p'
                    AND elem->>'value' ~* 'del'
                    AND elem->>'value' !~* 'fs'
                )"""
            )
        elif validated_consequence == "In-frame Insertion":
            # Protein notation contains 'ins' but NOT 'fs' (frameshift)
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.p'
                    AND elem->>'value' ~* 'ins'
                    AND elem->>'value' !~* 'fs'
                )"""
            )

    # Protein domain filter (HNF1B-specific)
    # Extract amino acid position from HGVS p. notation and check domain boundaries
    if domain:
        # Domain boundaries from UniProt P35680
        domain_boundaries = {
            "Dimerization Domain": (1, 31),
            "POU-Specific Domain": (8, 173),
            "POU Homeodomain": (232, 305),
            "Transactivation Domain": (314, 557),
        }

        if domain in domain_boundaries:
            start_pos, end_pos = domain_boundaries[domain]
            # Extract position from patterns like p.Arg177Ter, p.Ser148Leu, etc.
            # Regex extracts the numeric position after the three-letter amino acid code
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.p'
                    AND elem->>'value' ~ 'p\\.[A-Z][a-z]{2}(\\d+)'
                    AND (
                        regexp_match(elem->>'value', 'p\\.[A-Z][a-z]{2}(\\d+)')
                    )[1]::int BETWEEN :domain_start AND :domain_end
                )"""
            )
            params["domain_start"] = start_pos
            params["domain_end"] = end_pos

    # This elif was incorrectly indented - should be part of
    # validated_consequence check above. Moving it back would break logic,
    # so leaving as comment. Synonymous filter handled above.
    if False:  # Disabled - was incorrectly placed
        if validated_consequence == "Synonymous":
            # Protein notation contains '=' (no amino acid change)
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.p'
                    AND elem->>'value' ~ '='
                )"""
            )
        elif validated_consequence == "Intronic Variant":
            # Transcript notation with +/- positions beyond splice sites
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.c'
                    AND (
                        elem->>'value' ~ '\\+[7-9]|\\+\\d{2,}'
                        OR elem->>'value' ~ '-[4-9]|-\\d{2,}'
                    )
                )"""
            )

    where_sql = "AND " + " AND ".join(where_clauses) if where_clauses else ""

    # Build ORDER BY clause from sort parameter
    # Map frontend field names to SQL column names
    sort_field_map = {
        "simple_id": "simple_id",
        "variant_id": "variant_id",
        "transcript": "transcript",
        "protein": "protein",
        "variant_type": "structural_type",
        "hg38": "hg38",
        "classificationVerdict": "pathogenicity",
        "individualCount": "phenopacket_count",
    }

    # Default sort: by individual count DESC, then variant_id for deterministic ordering
    order_by = "phenopacket_count DESC, variant_id ASC"
    if sort:
        # Check if descending (starts with '-')
        if sort.startswith("-"):
            field_name = sort[1:]
            direction = "DESC"
        else:
            field_name = sort
            direction = "ASC"

        # Map field name to SQL column
        sql_column = sort_field_map.get(field_name)
        if sql_column:
            # Add variant_id as tie-breaker for deterministic ordering
            order_by = f"{sql_column} {direction}, variant_id ASC"

    query_sql = f"""
    WITH all_variants_unfiltered AS (
        -- Extract ALL variants WITHOUT filters to establish stable IDs
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
        -- Aggregate all variants to count occurrences
        SELECT
            variant_id,
            MAX(gene_symbol) as gene_symbol,
            COUNT(DISTINCT phenopacket_id) as phenopacket_count
        FROM all_variants_unfiltered
        GROUP BY variant_id
    ),
    all_variants_with_stable_id AS (
        -- Assign stable IDs to ALL variants based on unfiltered dataset
        -- Use variant_id as tie-breaker for deterministic ordering
        SELECT
            ROW_NUMBER() OVER (
                ORDER BY phenopacket_count DESC, gene_symbol ASC, variant_id ASC
            ) as simple_id,
            variant_id
        FROM all_variants_agg
    ),
    variant_raw AS (
        -- NOW apply filtering for the actual results
        SELECT DISTINCT ON (vd->>'id', p.id)
            vd->>'id' as variant_id,
            vd->>'label' as label,
            vd->'geneContext'->>'symbol' as gene_symbol,
            vd->'geneContext'->>'valueId' as gene_id,
            COALESCE(
                vd->'structuralType'->>'label',
                -- Classify based on HGVS notation to distinguish
                -- insertions from indels
                CASE
                    -- Check for delins (indel = deletion + insertion)
                    -- must check first
                    -- Pattern matches both "delins" and "del[BASES]ins[BASES]"
                    WHEN (
                        SELECT elem->>'value'
                        FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'syntax' = 'hgvs.c'
                        LIMIT 1
                    ) ~ 'del[A-Z]*ins' THEN 'indel'
                    -- Check for pure insertions (has 'ins' but not 'del')
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
                    -- Check for pure deletions (has 'del' but not 'ins' or 'dup')
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
                    -- Check for duplications (has 'dup' in HGVS)
                    WHEN (
                        SELECT elem->>'value'
                        FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'syntax' = 'hgvs.c'
                        LIMIT 1
                    ) ~ 'dup' THEN 'duplication'
                    -- CNVs from VCF alt field
                    WHEN vd->'vcfRecord'->>'alt' ~ '^<(DEL|DUP|INS|INV|CNV)' THEN 'CNV'
                    -- Default: SNV for genomic variants
                    WHEN vd->>'moleculeContext' = 'genomic' THEN 'SNV'
                    ELSE 'OTHER'
                END,
                vd->'molecularConsequences'->0->>'label'
            ) as structural_type,
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
        -- Aggregate filtered variants
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
        -- Join filtered results with pre-calculated stable IDs
        SELECT
            avwsi.simple_id,  -- Stable ID from unfiltered dataset
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
        {
        "AND CONCAT('Var', simple_id::text) ILIKE :simple_id_query"
        if validated_query and validated_query.lower().startswith("var")
        else ""
    }
    ORDER BY {order_by}
    LIMIT :limit
    OFFSET :offset
    """

    result = await db.execute(text(query_sql), params)
    rows = result.fetchall()

    # Get total count of variants (without limit/offset)
    # Reuse the same CTEs but only count final results
    # IMPORTANT: Must include simple_id filter to match main query
    count_query = f"""
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
        -- Assign stable IDs to ALL variants based on unfiltered dataset
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
            COUNT(DISTINCT phenopacket_id) as phenopacket_count
        FROM variant_raw
        GROUP BY variant_id
    ),
    variant_with_stable_id AS (
        -- Join filtered results with pre-calculated stable IDs
        SELECT
            avwsi.simple_id,
            va.variant_id
        FROM variant_agg va
        INNER JOIN all_variants_with_stable_id avwsi ON va.variant_id = avwsi.variant_id
    )
    SELECT COUNT(*) as total
    FROM variant_with_stable_id
    WHERE 1=1
        {
        "AND CONCAT('Var', simple_id::text) ILIKE :simple_id_query"
        if validated_query and validated_query.lower().startswith("var")
        else ""
    }
    """

    # Create a copy of params without limit/offset for count query
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    count_result = await db.execute(text(count_query), count_params)
    total_count = count_result.scalar() or 0

    # simple_id is calculated using default sort order (by individual count)
    # This ensures each variant has a stable ID regardless of current sort
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
        user_id=None,  # TODO: Get from auth when available
        query=validated_query,
        variant_type=validated_variant_type,
        classification=validated_classification,
        gene=validated_gene,
        consequence=validated_consequence,
        result_count=len(variants),
        request_path=str(request.url.path),
    )

    # Return variants with pagination metadata
    return {
        "data": variants,
        "total": total_count,
        "skip": skip,
        "limit": limit,
    }


@router.get("/age-of-onset", response_model=List[AggregationResult])
async def aggregate_age_of_onset(
    db: AsyncSession = Depends(get_db),
):
    """Get distribution of age of disease onset."""
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


@router.get("/summary", response_model=Dict[str, int])
async def get_summary_statistics(db: AsyncSession = Depends(get_db)):
    """Get lightweight summary statistics for home page.

    Returns:
        Dictionary with counts:
        - total_phenopackets: Total number of phenopackets
        - with_variants: Phenopackets containing interpretations
        - distinct_hpo_terms: Number of unique HPO terms used
        - distinct_publications: Number of unique publication references
        - distinct_variants: Number of unique genetic variants
        - male: Number of male subjects
        - female: Number of female subjects
        - unknown_sex: Number of subjects with unknown sex
    """
    # 1. Total phenopackets
    total_result = await db.execute(select(func.count()).select_from(Phenopacket))
    total_phenopackets = total_result.scalar()

    # 2. With variants (interpretations exist)
    with_variants_result = await db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM phenopackets
            WHERE jsonb_array_length(phenopacket->'interpretations') > 0
        """
        )
    )
    with_variants = with_variants_result.scalar()

    # 3. Distinct HPO terms
    distinct_hpo_result = await db.execute(
        text(
            """
            SELECT COUNT(DISTINCT feature->'type'->>'id')
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature
            WHERE feature->'type'->>'id' IS NOT NULL
        """
        )
    )
    distinct_hpo_terms = distinct_hpo_result.scalar() or 0

    # 4. Distinct sources (publications and internal cohort data)
    distinct_publications_result = await db.execute(
        text(
            """
            SELECT COUNT(DISTINCT ext_ref->>'id')
            FROM phenopackets,
                 jsonb_array_elements(
                     phenopacket->'metaData'->'externalReferences'
                 ) as ext_ref
            WHERE ext_ref->>'id' IS NOT NULL
        """
        )
    )
    distinct_publications = distinct_publications_result.scalar() or 0

    # 5. Distinct variants (unique variants across all phenopackets)
    distinct_variants_result = await db.execute(
        text(
            """
            SELECT COUNT(DISTINCT vd->>'id')
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                 jsonb_array_elements(
                    interp->'diagnosis'->'genomicInterpretations'
                ) as gi,
                 LATERAL (
                     SELECT gi->'variantInterpretation'->'variationDescriptor' as vd
                 ) vd_lateral
            WHERE vd_lateral.vd IS NOT NULL
              AND vd_lateral.vd->>'id' IS NOT NULL
        """
        )
    )
    distinct_variants = distinct_variants_result.scalar() or 0

    # 6. Sex distribution
    sex_distribution_result = await db.execute(
        text(
            """
            SELECT
                subject_sex,
                COUNT(*) as count
            FROM phenopackets
            GROUP BY subject_sex
        """
        )
    )
    sex_rows = sex_distribution_result.fetchall()

    # Parse sex distribution
    male = 0
    female = 0
    unknown_sex = 0
    for row in sex_rows:
        if row.subject_sex == "MALE":
            male = int(row._mapping["count"])
        elif row.subject_sex == "FEMALE":
            female = int(row._mapping["count"])
        else:
            unknown_sex += int(row._mapping["count"])

    return {
        "total_phenopackets": total_phenopackets,
        "with_variants": with_variants,
        "distinct_hpo_terms": distinct_hpo_terms,
        "distinct_publications": distinct_publications,
        "distinct_variants": distinct_variants,
        "male": male,
        "female": female,
        "unknown_sex": unknown_sex,
    }


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


@router.get("/survival-data", response_model=Dict[str, Any])
async def get_survival_data(
    comparison: str = Query(
        ...,
        description="Comparison type: variant_type, disease_subtype, or pathogenicity",
    ),
    endpoint: str = Query(
        "ckd_stage_3_plus",
        description=(
            "Clinical endpoint: ckd_stage_3_plus (default), "
            "stage_5_ckd, any_ckd, current_age"
        ),
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get Kaplan-Meier survival data with configurable clinical endpoints.

    Compares survival curves using different grouping strategies:
    - variant_type: CNV vs Truncating vs Non-truncating
    - disease_subtype: CAKUT vs CAKUT+MODY vs MODY
    - pathogenicity: P/LP vs VUS vs LB

    Supports multiple clinical endpoints:
    - ckd_stage_3_plus: CKD Stage 3+ (GFR <60)
    - stage_5_ckd: Stage 5 CKD (ESRD)
    - any_ckd: Any CKD diagnosis
    - current_age: Age at last follow-up (universal endpoint)

    Returns:
        Survival curves with Kaplan-Meier estimates, 95% CIs, and log-rank tests
    """
    from app.phenopackets.survival_analysis import (
        apply_bonferroni_correction,
        calculate_kaplan_meier,
        calculate_log_rank_test,
        parse_iso8601_age,
        parse_onset_ontology,
    )

    # CAKUT HPO terms (from R script lines 197-206)
    # Direct CAKUT phenotypes: Multicystic dysplasia, Unilateral agenesis,
    # Renal hypoplasia, Abnormal renal morphology
    CAKUT_HPO_TERMS = [
        "HP:0000003",  # Multicystic kidney dysplasia
        "HP:0000122",  # Unilateral renal agenesis
        "HP:0000089",  # Renal hypoplasia
        "HP:0012210",  # Abnormal renal morphology
    ]

    # Genital abnormality HPO term (R script line 201: combined with any_kidney)
    GENITAL_HPO = "HP:0000078"  # Abnormality of the genital system

    # ANY_KIDNEY HPO terms (R script lines 171-189 for any_kidney helper)
    # Used for the genital + any_kidney combination to classify as CAKUT
    ANY_KIDNEY_HPO_TERMS = [
        "HP:0012622",  # Chronic kidney disease (unspecified)
        "HP:0012623",  # Stage 1 chronic kidney disease
        "HP:0012624",  # Stage 2 chronic kidney disease
        "HP:0012625",  # Stage 3 chronic kidney disease
        "HP:0012626",  # Stage 4 chronic kidney disease
        "HP:0003774",  # Stage 5 chronic kidney disease
        "HP:0000003",  # Multicystic kidney dysplasia
        "HP:0000089",  # Renal hypoplasia
        "HP:0000107",  # Renal cyst
        "HP:0000122",  # Unilateral renal agenesis
        "HP:0012210",  # Abnormal renal morphology
        "HP:0033133",  # Renal cortical hyperechogenicity
        "HP:0000108",  # Multiple glomerular cysts
        "HP:0001970",  # Oligomeganephronia
    ]

    # MODY HPO term (from R script line 193)
    MODY_HPO = "HP:0004904"  # Maturity-onset diabetes of the young

    # Endpoint configuration
    endpoint_config: dict[str, dict[str, Optional[list[str]] | str]] = {
        "ckd_stage_3_plus": {
            "hpo_terms": [
                "HP:0012625",  # Stage 3 chronic kidney disease
                "HP:0012626",  # Stage 4 chronic kidney disease
                "HP:0003774",  # Stage 5 chronic kidney disease
            ],
            "label": "CKD Stage 3+ (GFR <60)",
        },
        "stage_5_ckd": {
            "hpo_terms": ["HP:0003774"],  # Stage 5 chronic kidney disease
            "label": "Stage 5 CKD (ESRD)",
        },
        "any_ckd": {
            "hpo_terms": [
                "HP:0012622",  # Chronic kidney disease (unspecified)
                "HP:0012623",  # Stage 1 chronic kidney disease
                "HP:0012624",  # Stage 2 chronic kidney disease
                "HP:0012625",  # Stage 3 chronic kidney disease
                "HP:0012626",  # Stage 4 chronic kidney disease
                "HP:0003774",  # Stage 5 chronic kidney disease
            ],
            "label": "Any CKD",
        },
        "current_age": {
            "hpo_terms": None,  # Special case: use current age
            "label": "Age at Last Follow-up",
        },
    }

    if endpoint not in endpoint_config:
        valid_options = ", ".join(endpoint_config.keys())
        raise ValueError(
            f"Unknown endpoint: {endpoint}. Valid options: {valid_options}"
        )

    config = endpoint_config[endpoint]
    endpoint_hpo_terms = config["hpo_terms"]
    endpoint_label = config["label"]

    # Type assertions for mypy
    assert isinstance(endpoint_label, str)
    assert endpoint_hpo_terms is None or isinstance(endpoint_hpo_terms, list)

    if comparison == "variant_type":
        # Check for special current_age endpoint
        if endpoint_hpo_terms is None:
            # For current_age endpoint (R script survival analysis):
            # - Time axis: report_age (age at last follow-up)
            # - Event: kidney_failure (Stage 4 or 5 CKD)
            # - Censored: Has CKD data but not Stage 4/5
            # - EXCLUDED: Patients without any CKD data (R script line 277)
            # NOTE: Only P/LP variants included (R script line 656)
            query = """
            WITH variant_classification AS (
                SELECT DISTINCT
                    p.phenopacket_id,
                    CASE
                        -- CNVs: Large deletions or duplications >= 50kb (17qDel/Dup in R)
                        -- Intragenic deletions < 50kb are classified as Truncating
                        WHEN interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ ':(DEL|DUP)'
                            AND COALESCE(
                                (SELECT (ext#>>'{value,length}')::bigint
                                 FROM jsonb_array_elements(
                                     interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                                 ) AS ext
                                 WHERE ext->>'name' = 'coordinates'
                                ), 0) >= 50000
                            THEN 'CNV'
                        -- Non-truncating: VEP IMPACT = MODERATE (R script line 89: MODERATE → nT)
                        WHEN EXISTS (
                            SELECT 1
                            FROM jsonb_array_elements(
                                interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                            ) AS ext
                            WHERE ext->>'name' = 'vep_annotation'
                              AND ext#>>'{value,impact}' = 'MODERATE'
                        ) THEN 'Non-truncating'
                        -- Truncating variants (R script lines 90-96)
                        WHEN (
                            -- Intragenic deletions/duplications < 50kb → Truncating
                            (
                                interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ ':(DEL|DUP)'
                                AND COALESCE(
                                    (SELECT (ext#>>'{value,length}')::bigint
                                     FROM jsonb_array_elements(
                                         interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                                     ) AS ext
                                     WHERE ext->>'name' = 'coordinates'
                                    ), 0) < 50000
                            )
                            OR
                            -- VEP IMPACT = HIGH → Truncating
                            EXISTS (
                                SELECT 1
                                FROM jsonb_array_elements(
                                    interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                                ) AS ext
                                WHERE ext->>'name' = 'vep_annotation'
                                  AND ext#>>'{value,impact}' = 'HIGH'
                            )
                            OR
                            -- VEP IMPACT = LOW/MODIFIER (already P/LP filtered) → Truncating
                            EXISTS (
                                SELECT 1
                                FROM jsonb_array_elements(
                                    interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                                ) AS ext
                                WHERE ext->>'name' = 'vep_annotation'
                                  AND ext#>>'{value,impact}' IN ('LOW', 'MODIFIER')
                            )
                            OR
                            -- No VEP annotation and not a DEL/DUP (already P/LP filtered) → Truncating
                            (
                                NOT EXISTS (
                                    SELECT 1
                                    FROM jsonb_array_elements(
                                        interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                                    ) AS ext
                                    WHERE ext->>'name' = 'vep_annotation'
                                )
                                AND NOT interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ ':(DEL|DUP)'
                            )
                            OR
                            -- HGVS pattern fallback for truncating effects
                            EXISTS (
                                SELECT 1
                                FROM jsonb_array_elements(
                                    interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,expressions}'
                                ) AS expr
                                WHERE (
                                    (expr->>'syntax' = 'hgvs.p' AND expr->>'value' ~* 'fs')
                                    OR (expr->>'syntax' = 'hgvs.p' AND (expr->>'value' ~* 'ter' OR expr->>'value' ~ '\\*'))
                                    OR (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '\\+[1-6]')
                                    OR (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '-[1-3]')
                                )
                            )
                        ) THEN 'Truncating'
                        ELSE 'Non-truncating'
                    END AS variant_group,
                    p.phenopacket->'subject'->'timeAtLastEncounter'->>'iso8601duration' as current_age,
                    -- Event: Stage 4 or Stage 5 CKD (R script lines 248-252)
                    EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                        WHERE pf->'type'->>'id' IN ('HP:0012626', 'HP:0003774')  -- Stage 4 and Stage 5 CKD
                            AND COALESCE((pf->>'excluded')::boolean, false) = false
                    ) as has_kidney_failure
                FROM phenopackets p,
                    jsonb_array_elements(p.phenopacket->'interpretations') as interp
                WHERE p.deleted_at IS NULL
                    AND p.phenopacket->'subject'->'timeAtLastEncounter'->>'iso8601duration' IS NOT NULL
                    -- P/LP filter: Only include Pathogenic/Likely Pathogenic (R script line 656)
                    AND interp.value->'diagnosis'->'genomicInterpretations'->0->>'interpretationStatus'
                        IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
                    -- CKD data filter: Only include patients with ANY CKD data (R script line 277)
                    -- This matches filter(!is.na(kidney_failure)) in R
                    AND EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                        WHERE pf->'type'->>'id' IN (
                            'HP:0012622',  -- Chronic kidney disease (unspecified)
                            'HP:0012623',  -- Stage 1 CKD
                            'HP:0012624',  -- Stage 2 CKD
                            'HP:0012625',  -- Stage 3 CKD
                            'HP:0012626',  -- Stage 4 CKD
                            'HP:0003774'   -- Stage 5 CKD
                        )
                    )
            )
            SELECT variant_group, current_age, has_kidney_failure
            FROM variant_classification
            """

            result = await db.execute(text(query))
            rows = result.fetchall()

            groups: dict[str, list[tuple[float, bool]]] = {
                "CNV": [],
                "Truncating": [],
                "Non-truncating": [],
            }

            for row in rows:
                current_age = parse_iso8601_age(row.current_age)
                if current_age is not None:
                    is_event = row.has_kidney_failure
                    groups[row.variant_group].append((current_age, is_event))

            # Calculate Kaplan-Meier curves
            survival_curves = {}
            for group_name, event_times in groups.items():
                if event_times:
                    survival_curves[group_name] = calculate_kaplan_meier(event_times)
                else:
                    survival_curves[group_name] = []

            # Perform pairwise log-rank tests
            statistical_tests = []
            group_names = list(groups.keys())
            for i in range(len(group_names)):
                for j in range(i + 1, len(group_names)):
                    group1 = group_names[i]
                    group2 = group_names[j]
                    if groups[group1] and groups[group2]:
                        test_result = calculate_log_rank_test(
                            groups[group1], groups[group2]
                        )
                        statistical_tests.append(
                            {
                                "group1": group1,
                                "group2": group2,
                                **test_result,
                            }
                        )

            # Apply Bonferroni correction for multiple comparisons
            statistical_tests = apply_bonferroni_correction(statistical_tests)

            return {
                "comparison_type": "variant_type",
                "endpoint": endpoint_label,
                "groups": [
                    {
                        "name": group_name,
                        "n": len(event_times),
                        "events": sum(1 for _, event in event_times if event),
                        "survival_data": survival_curves[group_name],
                    }
                    for group_name, event_times in groups.items()
                    if event_times
                ],
                "statistical_tests": statistical_tests,
                # Metadata for transparency
                "metadata": {
                    "event_definition": (
                        "Kidney failure: CKD Stage 4 (HP:0012626) or "
                        "Stage 5/ESRD (HP:0003774)"
                    ),
                    "time_axis": "Age at last clinical encounter (timeAtLastEncounter)",
                    "censoring": (
                        "Patients without kidney failure are censored at their "
                        "last reported age"
                    ),
                    "group_definitions": {
                        "CNV": (
                            "Copy number variants: deletions or duplications ≥50kb "
                            "(17q12 deletion/duplication syndrome)"
                        ),
                        "Truncating": (
                            "Frameshift, nonsense (stop gained), splice site variants, "
                            "or intragenic deletions <50kb"
                        ),
                        "Non-truncating": (
                            "Missense variants and other variants with MODERATE impact"
                        ),
                    },
                    "inclusion_criteria": (
                        "Pathogenic (P) and Likely Pathogenic (LP) variants only. "
                        "Requires CKD assessment data."
                    ),
                    "exclusion_criteria": (
                        "VUS, Likely Benign, and Benign variants excluded"
                    ),
                },
            }

        # Standard CKD endpoint
        # NOTE: Only P/LP variants included to match R script (line 656)
        query = """
        WITH variant_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                CASE
                    -- CNVs: Large deletions or duplications >= 50kb (17qDel/Dup in R)
                    -- Intragenic deletions < 50kb are classified as Truncating
                    WHEN interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ ':(DEL|DUP)'
                        AND COALESCE(
                            (SELECT (ext#>>'{value,length}')::bigint
                             FROM jsonb_array_elements(
                                 interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                             ) AS ext
                             WHERE ext->>'name' = 'coordinates'
                            ), 0) >= 50000
                        THEN 'CNV'
                    -- Non-truncating: VEP IMPACT = MODERATE (R script line 89: MODERATE → nT)
                    WHEN EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(
                            interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                        ) AS ext
                        WHERE ext->>'name' = 'vep_annotation'
                          AND ext#>>'{value,impact}' = 'MODERATE'
                    ) THEN 'Non-truncating'
                    -- Truncating variants (R script lines 90-96)
                    WHEN (
                        -- Intragenic deletions/duplications < 50kb → Truncating
                        (
                            interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ ':(DEL|DUP)'
                            AND COALESCE(
                                (SELECT (ext#>>'{value,length}')::bigint
                                 FROM jsonb_array_elements(
                                     interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                                 ) AS ext
                                 WHERE ext->>'name' = 'coordinates'
                                ), 0) < 50000
                        )
                        OR
                        -- VEP IMPACT = HIGH → Truncating
                        EXISTS (
                            SELECT 1
                            FROM jsonb_array_elements(
                                interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                            ) AS ext
                            WHERE ext->>'name' = 'vep_annotation'
                              AND ext#>>'{value,impact}' = 'HIGH'
                        )
                        OR
                        -- VEP IMPACT = LOW/MODIFIER (already P/LP filtered) → Truncating
                        EXISTS (
                            SELECT 1
                            FROM jsonb_array_elements(
                                interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                            ) AS ext
                            WHERE ext->>'name' = 'vep_annotation'
                              AND ext#>>'{value,impact}' IN ('LOW', 'MODIFIER')
                        )
                        OR
                        -- No VEP annotation and not a DEL/DUP (already P/LP filtered) → Truncating
                        (
                            NOT EXISTS (
                                SELECT 1
                                FROM jsonb_array_elements(
                                    interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                                ) AS ext
                                WHERE ext->>'name' = 'vep_annotation'
                            )
                            AND NOT interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ ':(DEL|DUP)'
                        )
                        OR
                        -- HGVS pattern fallback for truncating effects
                        EXISTS (
                            SELECT 1
                            FROM jsonb_array_elements(
                                interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,expressions}'
                            ) AS expr
                            WHERE (
                                (expr->>'syntax' = 'hgvs.p' AND expr->>'value' ~* 'fs')
                                OR (expr->>'syntax' = 'hgvs.p' AND (expr->>'value' ~* 'ter' OR expr->>'value' ~ '\\*'))
                                OR (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '\\+[1-6]')
                                OR (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '-[1-3]')
                            )
                        )
                    ) THEN 'Truncating'
                    ELSE 'Non-truncating'
                END AS variant_group,
                p.phenopacket->'subject'->>'timeAtLastEncounter' as current_age,
                p.phenopacket as phenopacket_data
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp
            WHERE p.deleted_at IS NULL
                -- P/LP filter: Only include Pathogenic/Likely Pathogenic (R script line 656)
                AND interp.value->'diagnosis'->'genomicInterpretations'->0->>'interpretationStatus'
                    IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
        ),
        endpoint_cases AS (
            SELECT
                vc.phenopacket_id,
                vc.variant_group,
                vc.current_age,
                pf->'onset' as onset,
                pf->'onset'->>'age' as onset_age
            FROM variant_classification vc,
                jsonb_array_elements(vc.phenopacket_data->'phenotypicFeatures') as pf
            WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                AND COALESCE((pf->>'excluded')::boolean, false) = false
        )
        SELECT
            variant_group,
            current_age,
            onset_age,
            onset
        FROM endpoint_cases
        """

        result = await db.execute(
            text(query), {"endpoint_hpo_terms": endpoint_hpo_terms}
        )
        rows = result.fetchall()

        # Group data by variant type
        groups = {"CNV": [], "Truncating": [], "Non-truncating": []}

        for row in rows:
            variant_group = row.variant_group

            # Parse onset age
            onset_age = None
            if row.onset_age:
                onset_age = parse_iso8601_age(row.onset_age)
            elif row.onset:
                onset_age = parse_onset_ontology(dict(row.onset))

            if onset_age is not None:
                groups[variant_group].append((onset_age, True))

        # Get censored patients (those without the endpoint)
        # NOTE: Only P/LP variants included to match R script (line 656)
        censored_query = """
        WITH variant_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                CASE
                    -- CNVs: Large deletions or duplications >= 50kb (17qDel/Dup in R)
                    -- Intragenic deletions < 50kb are classified as Truncating
                    WHEN interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ ':(DEL|DUP)'
                        AND COALESCE(
                            (SELECT (ext#>>'{value,length}')::bigint
                             FROM jsonb_array_elements(
                                 interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                             ) AS ext
                             WHERE ext->>'name' = 'coordinates'
                            ), 0) >= 50000
                        THEN 'CNV'
                    -- Non-truncating: VEP IMPACT = MODERATE (R script line 89: MODERATE → nT)
                    WHEN EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(
                            interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                        ) AS ext
                        WHERE ext->>'name' = 'vep_annotation'
                          AND ext#>>'{value,impact}' = 'MODERATE'
                    ) THEN 'Non-truncating'
                    -- Truncating variants (R script lines 90-96)
                    WHEN (
                        -- Intragenic deletions/duplications < 50kb → Truncating
                        (
                            interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ ':(DEL|DUP)'
                            AND COALESCE(
                                (SELECT (ext#>>'{value,length}')::bigint
                                 FROM jsonb_array_elements(
                                     interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                                 ) AS ext
                                 WHERE ext->>'name' = 'coordinates'
                                ), 0) < 50000
                        )
                        OR
                        -- VEP IMPACT = HIGH → Truncating
                        EXISTS (
                            SELECT 1
                            FROM jsonb_array_elements(
                                interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                            ) AS ext
                            WHERE ext->>'name' = 'vep_annotation'
                              AND ext#>>'{value,impact}' = 'HIGH'
                        )
                        OR
                        -- VEP IMPACT = LOW/MODIFIER (already P/LP filtered) → Truncating
                        EXISTS (
                            SELECT 1
                            FROM jsonb_array_elements(
                                interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                            ) AS ext
                            WHERE ext->>'name' = 'vep_annotation'
                              AND ext#>>'{value,impact}' IN ('LOW', 'MODIFIER')
                        )
                        OR
                        -- No VEP annotation and not a DEL/DUP (already P/LP filtered) → Truncating
                        (
                            NOT EXISTS (
                                SELECT 1
                                FROM jsonb_array_elements(
                                    interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                                ) AS ext
                                WHERE ext->>'name' = 'vep_annotation'
                            )
                            AND NOT interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ ':(DEL|DUP)'
                        )
                        OR
                        -- HGVS pattern fallback for truncating effects
                        EXISTS (
                            SELECT 1
                            FROM jsonb_array_elements(
                                interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,expressions}'
                            ) AS expr
                            WHERE (
                                (expr->>'syntax' = 'hgvs.p' AND expr->>'value' ~* 'fs')
                                OR (expr->>'syntax' = 'hgvs.p' AND (expr->>'value' ~* 'ter' OR expr->>'value' ~ '\\*'))
                                OR (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '\\+[1-6]')
                                OR (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '-[1-3]')
                            )
                        )
                    ) THEN 'Truncating'
                    ELSE 'Non-truncating'
                END AS variant_group,
                p.phenopacket->'subject'->>'timeAtLastEncounter' as current_age
            FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'interpretations') as interp
            WHERE p.deleted_at IS NULL
                -- P/LP filter: Only include Pathogenic/Likely Pathogenic (R script line 656)
                AND interp.value->'diagnosis'->'genomicInterpretations'->0->>'interpretationStatus'
                    IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
                AND NOT EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                    WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                )
                AND p.phenopacket->'subject'->>'timeAtLastEncounter' IS NOT NULL
        )
        SELECT variant_group, current_age
        FROM variant_classification
        """

        censored_result = await db.execute(
            text(censored_query), {"endpoint_hpo_terms": endpoint_hpo_terms}
        )
        censored_rows = censored_result.fetchall()

        for row in censored_rows:
            current_age = parse_iso8601_age(row.current_age)
            if current_age is not None:
                groups[row.variant_group].append((current_age, False))

        # Calculate Kaplan-Meier curves for each group
        survival_curves = {}
        for group_name, event_times in groups.items():
            if event_times:
                survival_curves[group_name] = calculate_kaplan_meier(event_times)
            else:
                survival_curves[group_name] = []

        # Perform pairwise log-rank tests
        statistical_tests = []
        group_names = list(groups.keys())
        for i in range(len(group_names)):
            for j in range(i + 1, len(group_names)):
                group1 = group_names[i]
                group2 = group_names[j]
                if groups[group1] and groups[group2]:
                    test_result = calculate_log_rank_test(
                        groups[group1], groups[group2]
                    )
                    statistical_tests.append(
                        {
                            "group1": group1,
                            "group2": group2,
                            **test_result,
                        }
                    )

        # Apply Bonferroni correction for multiple comparisons
        statistical_tests = apply_bonferroni_correction(statistical_tests)

        return {
            "comparison_type": "variant_type",
            "endpoint": endpoint_label,
            "groups": [
                {
                    "name": group_name,
                    "n": len(event_times),
                    "events": sum(1 for _, event in event_times if event),
                    "survival_data": survival_curves[group_name],
                }
                for group_name, event_times in groups.items()
            ],
            "statistical_tests": statistical_tests,
            # Metadata for transparency
            "metadata": {
                "event_definition": f"Onset of {endpoint_label}",
                "time_axis": "Age at phenotype onset (from phenotypicFeatures.onset)",
                "censoring": (
                    "Patients without the endpoint phenotype are censored at their "
                    "last reported age (timeAtLastEncounter)"
                ),
                "group_definitions": {
                    "CNV": (
                        "Copy number variants: deletions or duplications ≥50kb "
                        "(17q12 deletion/duplication syndrome)"
                    ),
                    "Truncating": (
                        "Frameshift, nonsense (stop gained), splice site variants, "
                        "or intragenic deletions <50kb"
                    ),
                    "Non-truncating": (
                        "Missense variants and other variants with MODERATE impact"
                    ),
                },
                "inclusion_criteria": (
                    "Pathogenic (P) and Likely Pathogenic (LP) variants only"
                ),
                "exclusion_criteria": (
                    "VUS, Likely Benign, and Benign variants excluded"
                ),
            },
        }

    elif comparison == "pathogenicity":
        # Pathogenicity comparison: P/LP vs VUS
        # Matches R script: survival_data_variants (ACMG_groups != "LB/B")
        # Key filters applied to match R script:
        # 1. CKD data filter: Only patients with CKD assessment (R: filter(!is.na(kidney_failure)))
        # 2. CNV exclusion: Excludes CNVs since they don't have standard ACMG classification
        #    (This matches R script's n=255 for LP/P + VUS with no CNVs)

        # Check for special current_age endpoint
        if endpoint_hpo_terms is None:
            # Special case: current_age endpoint (Age at Last Follow-up)
            # Use report_age as time axis, kidney_failure as event
            # Matches R script: kidney_failure_by_acmg_group (lines 781-790)
            query = """
            WITH pathogenicity_classification AS (
                SELECT DISTINCT
                    p.phenopacket_id,
                    CASE
                        WHEN gi->>'interpretationStatus' IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
                            THEN 'P/LP'
                        WHEN gi->>'interpretationStatus' = 'UNCERTAIN_SIGNIFICANCE'
                            THEN 'VUS'
                        ELSE 'Unknown'
                    END AS pathogenicity_group,
                    p.phenopacket->'subject'->'timeAtLastEncounter'->>'iso8601duration' as current_age,
                    EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                        WHERE pf->'type'->>'id' IN ('HP:0012626', 'HP:0003774')  -- Stage 4 and Stage 5 CKD
                            AND COALESCE((pf->>'excluded')::boolean, false) = false
                    ) as has_kidney_failure
                FROM phenopackets p,
                    jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                    jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
                WHERE p.deleted_at IS NULL
                    AND p.phenopacket->'subject'->'timeAtLastEncounter'->>'iso8601duration' IS NOT NULL
                    -- CNV exclusion: Exclude 17q deletions and duplications
                    -- CNVs don't have standard ACMG classification (R script n=255)
                    AND gi#>>'{variantInterpretation,variationDescriptor,id}' !~ ':(DEL|DUP)'
                    -- CKD data filter: Only include patients with any CKD assessment
                    -- Matches R script line 650: filter(!is.na(kidney_failure))
                    AND EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                        WHERE pf->'type'->>'id' IN (
                            'HP:0012622',  -- Chronic kidney disease (unspecified)
                            'HP:0012623',  -- Stage 1 CKD
                            'HP:0012624',  -- Stage 2 CKD
                            'HP:0012625',  -- Stage 3 CKD
                            'HP:0012626',  -- Stage 4 CKD
                            'HP:0003774'   -- Stage 5 CKD
                        )
                    )
            )
            SELECT pathogenicity_group, current_age, has_kidney_failure
            FROM pathogenicity_classification
            WHERE pathogenicity_group IN ('P/LP', 'VUS')
            """  # noqa: E501

            result = await db.execute(text(query))
            rows = result.fetchall()

            groups = {"P/LP": [], "VUS": []}

            for row in rows:
                current_age = parse_iso8601_age(row.current_age)
                if current_age is not None:
                    # Per R script: event is kidney_failure, not reaching current age
                    is_event = row.has_kidney_failure
                    groups[row.pathogenicity_group].append((current_age, is_event))

        else:
            # Standard endpoint: match any of the specified HPO terms
            # Applies same filters as current_age endpoint:
            # - CNV exclusion (no 17q DEL/DUP)
            # - CKD data filter (only patients with CKD assessment)
            query = """
            WITH pathogenicity_classification AS (
                SELECT DISTINCT
                    p.phenopacket_id,
                    CASE
                        WHEN gi->>'interpretationStatus' IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
                            THEN 'P/LP'
                        WHEN gi->>'interpretationStatus' = 'UNCERTAIN_SIGNIFICANCE'
                            THEN 'VUS'
                        ELSE 'Unknown'
                    END AS pathogenicity_group,
                    p.phenopacket->'subject'->>'timeAtLastEncounter' as current_age,
                    p.phenopacket as phenopacket_data
                FROM phenopackets p,
                    jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                    jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
                WHERE p.deleted_at IS NULL
                    -- CNV exclusion: Exclude 17q deletions and duplications
                    AND gi#>>'{variantInterpretation,variationDescriptor,id}' !~ ':(DEL|DUP)'
                    -- CKD data filter: Only include patients with any CKD assessment
                    AND EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                        WHERE pf->'type'->>'id' IN (
                            'HP:0012622', 'HP:0012623', 'HP:0012624',
                            'HP:0012625', 'HP:0012626', 'HP:0003774'
                        )
                    )
            ),
            endpoint_cases AS (
                SELECT
                    pc.phenopacket_id,
                    pc.pathogenicity_group,
                    pc.current_age,
                    pf->'onset' as onset,
                    pf->'onset'->>'age' as onset_age
                FROM pathogenicity_classification pc,
                    jsonb_array_elements(pc.phenopacket_data->'phenotypicFeatures') as pf
                WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                    AND COALESCE((pf->>'excluded')::boolean, false) = false
            )
            SELECT
                pathogenicity_group,
                current_age,
                onset_age,
                onset
            FROM endpoint_cases
            WHERE pathogenicity_group IN ('P/LP', 'VUS')
            """

            result = await db.execute(
                text(query), {"endpoint_hpo_terms": endpoint_hpo_terms}
            )
            rows = result.fetchall()

            # Group data by pathogenicity
            groups = {"P/LP": [], "VUS": []}

            for row in rows:
                pathogenicity_group = row.pathogenicity_group

                # Parse onset age
                onset_age = None
                if row.onset_age:
                    onset_age = parse_iso8601_age(row.onset_age)
                elif row.onset:
                    onset_age = parse_onset_ontology(dict(row.onset))

                if onset_age is not None:
                    groups[pathogenicity_group].append((onset_age, True))

            # Get censored patients (same filters applied)
            censored_query = """
            WITH pathogenicity_classification AS (
                SELECT DISTINCT
                    p.phenopacket_id,
                    CASE
                        WHEN gi->>'interpretationStatus' IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
                            THEN 'P/LP'
                        WHEN gi->>'interpretationStatus' = 'UNCERTAIN_SIGNIFICANCE'
                            THEN 'VUS'
                        ELSE 'Unknown'
                    END AS pathogenicity_group,
                    p.phenopacket->'subject'->>'timeAtLastEncounter' as current_age
                FROM phenopackets p,
                    jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                    jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
                WHERE p.deleted_at IS NULL
                    -- CNV exclusion
                    AND gi#>>'{variantInterpretation,variationDescriptor,id}' !~ ':(DEL|DUP)'
                    -- CKD data filter
                    AND EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                        WHERE pf->'type'->>'id' IN (
                            'HP:0012622', 'HP:0012623', 'HP:0012624',
                            'HP:0012625', 'HP:0012626', 'HP:0003774'
                        )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                        WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                            AND COALESCE((pf->>'excluded')::boolean, false) = false
                    )
                    AND p.phenopacket->'subject'->>'timeAtLastEncounter' IS NOT NULL
            )
            SELECT pathogenicity_group, current_age
            FROM pathogenicity_classification
            WHERE pathogenicity_group IN ('P/LP', 'VUS')
            """

            censored_result = await db.execute(
                text(censored_query), {"endpoint_hpo_terms": endpoint_hpo_terms}
            )
            censored_rows = censored_result.fetchall()

            for row in censored_rows:
                current_age = parse_iso8601_age(row.current_age)
                if current_age is not None:
                    groups[row.pathogenicity_group].append((current_age, False))

        # Calculate Kaplan-Meier curves
        survival_curves = {}
        for group_name, event_times in groups.items():
            if event_times:
                survival_curves[group_name] = calculate_kaplan_meier(event_times)
            else:
                survival_curves[group_name] = []

        # Perform pairwise log-rank tests
        statistical_tests = []
        group_names = [g for g in groups.keys() if groups[g]]
        for i in range(len(group_names)):
            for j in range(i + 1, len(group_names)):
                group1 = group_names[i]
                group2 = group_names[j]
                test_result = calculate_log_rank_test(groups[group1], groups[group2])
                statistical_tests.append(
                    {
                        "group1": group1,
                        "group2": group2,
                        **test_result,
                    }
                )

        # Apply Bonferroni correction for multiple comparisons
        statistical_tests = apply_bonferroni_correction(statistical_tests)

        return {
            "comparison_type": "pathogenicity",
            "endpoint": endpoint_label,
            "groups": [
                {
                    "name": group_name,
                    "n": len(event_times),
                    "events": sum(1 for _, event in event_times if event),
                    "survival_data": survival_curves[group_name],
                }
                for group_name, event_times in groups.items()
                if event_times
            ],
            "statistical_tests": statistical_tests,
            # Metadata for transparency
            "metadata": {
                "event_definition": (
                    "Kidney failure: CKD Stage 4 (HP:0012626) or "
                    "Stage 5/ESRD (HP:0003774)"
                ),
                "time_axis": "Age at last clinical encounter (timeAtLastEncounter)",
                "censoring": (
                    "Patients without kidney failure are censored at their "
                    "last reported age"
                ),
                "group_definitions": {
                    "P/LP": (
                        "Pathogenic or Likely Pathogenic variants according to "
                        "ACMG/AMP guidelines"
                    ),
                    "VUS": (
                        "Variants of Uncertain Significance - insufficient evidence "
                        "to classify as pathogenic or benign"
                    ),
                },
                "inclusion_criteria": (
                    "P/LP and VUS variants only. Requires CKD assessment data."
                ),
                "exclusion_criteria": (
                    "CNVs excluded (lack standard ACMG classification). "
                    "Likely Benign and Benign variants excluded."
                ),
            },
        }

    elif comparison == "disease_subtype":
        # Check for special current_age endpoint
        if endpoint_hpo_terms is None:
            # Special case: current_age endpoint (Age at Last Follow-up)
            # Use report_age as time axis, kidney_failure as event
            # Per R script lines 229-233: "Other" has status=0 (censored)
            # R script CAKUT definition (lines 197-206):
            # CAKUT = Multicystic dysplasia | Unilateral agenesis |
            #         (Genital abnormality & any_kidney) | Renal hypoplasia |
            #         Abnormal renal morphology
            query = """
            WITH disease_classification AS (
                SELECT DISTINCT
                    p.phenopacket_id,
                    -- Helper: has direct CAKUT phenotype
                    EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                        WHERE pf->'type'->>'id' = ANY(:cakut_hpo_terms)
                            AND COALESCE((pf->>'excluded')::boolean, false) = false
                    ) as has_direct_cakut,
                    -- Helper: has genital abnormality
                    EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                        WHERE pf->'type'->>'id' = :genital_hpo
                            AND COALESCE((pf->>'excluded')::boolean, false) = false
                    ) as has_genital,
                    -- Helper: has any kidney involvement (R script any_kidney)
                    EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                        WHERE pf->'type'->>'id' = ANY(:any_kidney_hpo_terms)
                            AND COALESCE((pf->>'excluded')::boolean, false) = false
                    ) as has_any_kidney,
                    -- Helper: has MODY
                    EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                        WHERE pf->'type'->>'id' = :mody_hpo
                            AND COALESCE((pf->>'excluded')::boolean, false) = false
                    ) as has_mody,
                    p.phenopacket->'subject'->'timeAtLastEncounter'->>'iso8601duration' as current_age,
                    EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                        WHERE pf->'type'->>'id' IN ('HP:0012626', 'HP:0003774')  -- Stage 4 and Stage 5 CKD
                            AND COALESCE((pf->>'excluded')::boolean, false) = false
                    ) as has_kidney_failure
                FROM phenopackets p
                WHERE p.deleted_at IS NULL
                    AND p.phenopacket->'subject'->'timeAtLastEncounter'->>'iso8601duration' IS NOT NULL
            ),
            classified AS (
                SELECT
                    phenopacket_id,
                    current_age,
                    has_kidney_failure,
                    -- CAKUT: direct CAKUT terms OR (genital AND any_kidney)
                    (has_direct_cakut OR (has_genital AND has_any_kidney)) as is_cakut,
                    has_mody as is_mody
                FROM disease_classification
            )
            SELECT
                CASE
                    WHEN is_cakut AND is_mody THEN 'CAKUT/MODY'
                    WHEN is_cakut THEN 'CAKUT'
                    WHEN is_mody THEN 'MODY'
                    ELSE 'Other'
                END AS disease_group,
                current_age,
                has_kidney_failure
            FROM classified
            """

            result = await db.execute(
                text(query),
                {
                    "cakut_hpo_terms": CAKUT_HPO_TERMS,
                    "genital_hpo": GENITAL_HPO,
                    "any_kidney_hpo_terms": ANY_KIDNEY_HPO_TERMS,
                    "mody_hpo": MODY_HPO,
                },
            )
            rows = result.fetchall()

            disease_groups: dict[str, list[tuple[float, bool]]] = {
                "CAKUT": [],
                "CAKUT/MODY": [],
                "MODY": [],
                "Other": [],
            }

            for row in rows:
                current_age = parse_iso8601_age(row.current_age)
                if current_age is not None:
                    # Per R script: event is kidney_failure, not reaching current age
                    is_event = row.has_kidney_failure
                    disease_groups[row.disease_group].append((current_age, is_event))

            # Calculate Kaplan-Meier curves
            survival_curves = {}
            for group_name, event_times in disease_groups.items():
                if event_times:
                    survival_curves[group_name] = calculate_kaplan_meier(event_times)
                else:
                    survival_curves[group_name] = []

            # Perform pairwise log-rank tests
            statistical_tests = []
            group_names = [g for g in disease_groups.keys() if disease_groups[g]]
            for i in range(len(group_names)):
                for j in range(i + 1, len(group_names)):
                    group1 = group_names[i]
                    group2 = group_names[j]
                    test_result = calculate_log_rank_test(
                        disease_groups[group1], disease_groups[group2]
                    )
                    statistical_tests.append(
                        {
                            "group1": group1,
                            "group2": group2,
                            **test_result,
                        }
                    )

            # Apply Bonferroni correction for multiple comparisons
            statistical_tests = apply_bonferroni_correction(statistical_tests)

            return {
                "comparison_type": "disease_subtype",
                "endpoint": endpoint_label,
                "groups": [
                    {
                        "name": group_name,
                        "n": len(event_times),
                        "events": sum(1 for _, event in event_times if event),
                        "survival_data": survival_curves[group_name],
                    }
                    for group_name, event_times in disease_groups.items()
                    if event_times
                ],
                "statistical_tests": statistical_tests,
                # Metadata for transparency
                "metadata": {
                    "event_definition": (
                        "Kidney failure: CKD Stage 4 (HP:0012626) or "
                        "Stage 5/ESRD (HP:0003774)"
                    ),
                    "time_axis": "Age at last clinical encounter (timeAtLastEncounter)",
                    "censoring": (
                        "Patients without kidney failure are censored at their "
                        "last reported age"
                    ),
                    "group_definitions": {
                        "CAKUT": (
                            "Multicystic kidney dysplasia (HP:0000003), OR "
                            "Unilateral renal agenesis (HP:0000122), OR "
                            "Renal hypoplasia (HP:0000089), OR "
                            "Abnormal renal morphology (HP:0012210), OR "
                            "(Genital abnormality AND any kidney involvement)"
                        ),
                        "MODY": "Maturity-onset diabetes of the young (HP:0004904)",
                        "CAKUT/MODY": "Meets criteria for both CAKUT and MODY",
                        "Other": "Does not meet criteria for CAKUT or MODY",
                    },
                    "inclusion_criteria": (
                        "All patients with P/LP/VUS variants and reported age"
                    ),
                    "exclusion_criteria": "Likely Benign and Benign variants excluded",
                },
            }

        # Standard CKD endpoint (not current_age)
        # Query for CAKUT vs CAKUT/MODY vs MODY (R script lines 197-214)
        # R script CAKUT definition: direct CAKUT terms OR (genital AND any_kidney)
        query = """
        WITH disease_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                -- Helper: has direct CAKUT phenotype
                EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                    WHERE pf->'type'->>'id' = ANY(:cakut_hpo_terms)
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                ) as has_direct_cakut,
                -- Helper: has genital abnormality
                EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                    WHERE pf->'type'->>'id' = :genital_hpo
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                ) as has_genital,
                -- Helper: has any kidney involvement (R script any_kidney)
                EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                    WHERE pf->'type'->>'id' = ANY(:any_kidney_hpo_terms)
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                ) as has_any_kidney,
                -- Helper: has MODY
                EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                    WHERE pf->'type'->>'id' = :mody_hpo
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                ) as has_mody,
                p.phenopacket->'subject'->>'timeAtLastEncounter' as current_age,
                p.phenopacket as phenopacket_data
            FROM phenopackets p
            WHERE p.deleted_at IS NULL
        ),
        classified AS (
            SELECT
                phenopacket_id,
                current_age,
                phenopacket_data,
                -- CAKUT: direct CAKUT terms OR (genital AND any_kidney)
                (has_direct_cakut OR (has_genital AND has_any_kidney)) as is_cakut,
                has_mody as is_mody
            FROM disease_classification
        ),
        with_disease_group AS (
            SELECT
                phenopacket_id,
                CASE
                    WHEN is_cakut AND is_mody THEN 'CAKUT/MODY'
                    WHEN is_cakut THEN 'CAKUT'
                    WHEN is_mody THEN 'MODY'
                    ELSE 'Other'
                END AS disease_group,
                current_age,
                phenopacket_data
            FROM classified
        ),
        endpoint_cases AS (
            SELECT
                dc.phenopacket_id,
                dc.disease_group,
                dc.current_age,
                pf->'onset' as onset,
                pf->'onset'->>'age' as onset_age
            FROM with_disease_group dc,
                jsonb_array_elements(dc.phenopacket_data->'phenotypicFeatures') as pf
            WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                AND COALESCE((pf->>'excluded')::boolean, false) = false
        )
        SELECT
            disease_group,
            current_age,
            onset_age,
            onset
        FROM endpoint_cases
        """

        result = await db.execute(
            text(query),
            {
                "cakut_hpo_terms": CAKUT_HPO_TERMS,
                "genital_hpo": GENITAL_HPO,
                "any_kidney_hpo_terms": ANY_KIDNEY_HPO_TERMS,
                "mody_hpo": MODY_HPO,
                "endpoint_hpo_terms": endpoint_hpo_terms,
            },
        )
        rows = result.fetchall()

        # Group data by disease subtype
        subtype_groups: dict[str, list[tuple[float, bool]]] = {
            "CAKUT": [],
            "CAKUT/MODY": [],
            "MODY": [],
            "Other": [],
        }

        for row in rows:
            disease_group = row.disease_group

            # Parse onset age
            onset_age = None
            if row.onset_age:
                onset_age = parse_iso8601_age(row.onset_age)
            elif row.onset:
                onset_age = parse_onset_ontology(dict(row.onset))

            if onset_age is not None:
                subtype_groups[disease_group].append((onset_age, True))

        # Get censored patients
        # R script CAKUT definition: direct CAKUT terms OR (genital AND any_kidney)
        censored_query = """
        WITH disease_classification AS (
            SELECT DISTINCT
                p.phenopacket_id,
                -- Helper: has direct CAKUT phenotype
                EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                    WHERE pf->'type'->>'id' = ANY(:cakut_hpo_terms)
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                ) as has_direct_cakut,
                -- Helper: has genital abnormality
                EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                    WHERE pf->'type'->>'id' = :genital_hpo
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                ) as has_genital,
                -- Helper: has any kidney involvement (R script any_kidney)
                EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                    WHERE pf->'type'->>'id' = ANY(:any_kidney_hpo_terms)
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                ) as has_any_kidney,
                -- Helper: has MODY
                EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                    WHERE pf->'type'->>'id' = :mody_hpo
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                ) as has_mody,
                p.phenopacket->'subject'->>'timeAtLastEncounter' as current_age
            FROM phenopackets p
            WHERE p.deleted_at IS NULL
                AND NOT EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as pf
                    WHERE pf->'type'->>'id' = ANY(:endpoint_hpo_terms)
                        AND COALESCE((pf->>'excluded')::boolean, false) = false
                )
                AND p.phenopacket->'subject'->>'timeAtLastEncounter' IS NOT NULL
        ),
        classified AS (
            SELECT
                phenopacket_id,
                current_age,
                -- CAKUT: direct CAKUT terms OR (genital AND any_kidney)
                (has_direct_cakut OR (has_genital AND has_any_kidney)) as is_cakut,
                has_mody as is_mody
            FROM disease_classification
        )
        SELECT
            CASE
                WHEN is_cakut AND is_mody THEN 'CAKUT/MODY'
                WHEN is_cakut THEN 'CAKUT'
                WHEN is_mody THEN 'MODY'
                ELSE 'Other'
            END AS disease_group,
            current_age
        FROM classified
        """

        censored_result = await db.execute(
            text(censored_query),
            {
                "cakut_hpo_terms": CAKUT_HPO_TERMS,
                "genital_hpo": GENITAL_HPO,
                "any_kidney_hpo_terms": ANY_KIDNEY_HPO_TERMS,
                "mody_hpo": MODY_HPO,
                "endpoint_hpo_terms": endpoint_hpo_terms,
            },
        )
        censored_rows = censored_result.fetchall()

        for row in censored_rows:
            current_age = parse_iso8601_age(row.current_age)
            if current_age is not None:
                subtype_groups[row.disease_group].append((current_age, False))

        # Calculate Kaplan-Meier curves
        survival_curves = {}
        for group_name, event_times in subtype_groups.items():
            if event_times:
                survival_curves[group_name] = calculate_kaplan_meier(event_times)
            else:
                survival_curves[group_name] = []

        # Perform pairwise log-rank tests
        statistical_tests = []
        group_names = [g for g in subtype_groups.keys() if subtype_groups[g]]
        for i in range(len(group_names)):
            for j in range(i + 1, len(group_names)):
                group1 = group_names[i]
                group2 = group_names[j]
                test_result = calculate_log_rank_test(
                    subtype_groups[group1], subtype_groups[group2]
                )
                statistical_tests.append(
                    {
                        "group1": group1,
                        "group2": group2,
                        **test_result,
                    }
                )

        # Apply Bonferroni correction for multiple comparisons
        statistical_tests = apply_bonferroni_correction(statistical_tests)

        return {
            "comparison_type": "disease_subtype",
            "endpoint": endpoint_label,
            "groups": [
                {
                    "name": group_name,
                    "n": len(event_times),
                    "events": sum(1 for _, event in event_times if event),
                    "survival_data": survival_curves[group_name],
                }
                for group_name, event_times in subtype_groups.items()
                if event_times
            ],
            "statistical_tests": statistical_tests,
            # Metadata for transparency
            "metadata": {
                "event_definition": f"Onset of {endpoint_label}",
                "time_axis": "Age at phenotype onset (from phenotypicFeatures.onset)",
                "censoring": (
                    "Patients without the endpoint phenotype are censored at their "
                    "last reported age (timeAtLastEncounter)"
                ),
                "group_definitions": {
                    "CAKUT": (
                        "Multicystic kidney dysplasia (HP:0000003), OR "
                        "Unilateral renal agenesis (HP:0000122), OR "
                        "Renal hypoplasia (HP:0000089), OR "
                        "Abnormal renal morphology (HP:0012210), OR "
                        "(Genital abnormality AND any kidney involvement)"
                    ),
                    "MODY": "Maturity-onset diabetes of the young (HP:0004904)",
                    "CAKUT/MODY": "Meets criteria for both CAKUT and MODY",
                    "Other": "Does not meet criteria for CAKUT or MODY",
                },
                "inclusion_criteria": "All patients with P/LP/VUS variants",
                "exclusion_criteria": "Likely Benign and Benign variants excluded",
            },
        }

    else:
        raise ValueError(
            f"Unknown comparison type: {comparison}. "
            "Valid options: variant_type, disease_subtype, pathogenicity"
        )
