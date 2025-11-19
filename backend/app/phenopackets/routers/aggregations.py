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
    total_phenopackets = total_phenopackets_result.scalar()

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
    if count_mode == "unique":
        # Count unique variants by variant ID using structuralType field
        query = """
        WITH variant_types AS (
            SELECT DISTINCT
                vd->>'id' as variant_id,
                CASE
                    WHEN COALESCE(
                        vd->'structuralType'->>'label',
                        vd->'molecularConsequences'->0->>'label',
                        'Other'
                    ) = 'SNV' THEN 'SNV'
                    ELSE INITCAP(COALESCE(
                        vd->'structuralType'->>'label',
                        vd->'molecularConsequences'->0->>'label',
                        'Other'
                    ))
                END as variant_type
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
        # Count all variant instances using structuralType field
        query = """
        SELECT
            CASE
                WHEN COALESCE(
                    vd->'structuralType'->>'label',
                    vd->'molecularConsequences'->0->>'label',
                    'Other'
                ) = 'SNV' THEN 'SNV'
                ELSE INITCAP(COALESCE(
                    vd->'structuralType'->>'label',
                    vd->'molecularConsequences'->0->>'label',
                    'Other'
                ))
            END as variant_type,
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

    # 4. Distinct publications
    distinct_publications_result = await db.execute(
        text(
            """
            SELECT COUNT(DISTINCT ext_ref->>'id')
            FROM phenopackets,
                 jsonb_array_elements(
                     phenopacket->'metaData'->'externalReferences'
                 ) as ext_ref
            WHERE ext_ref->>'id' LIKE 'PMID:%'
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
            "count": int(row.count),
            "cumulative": int(row.cumulative),
            "publications": row.publications or [],
        }
        for row in rows
    ]
