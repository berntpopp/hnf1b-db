"""Centralized SQL fragments for aggregation queries.

This module provides:
1. JSONB path constants for consistent phenopacket data access
2. Variant classification SQL fragments for different analysis contexts

All variant classification and JSONB path logic lives here.
Import from here instead of defining inline SQL strings.

Usage Contexts:
- VARIANT_TYPE_CLASSIFICATION_SQL: Survival analysis (CNV/Truncating/Non-truncating)
- VARIANT_TYPE_CASE: Variant type aggregation (SNV/Deletion/Duplication/etc.)
- STRUCTURAL_TYPE_CASE: All variants listing (structural type detection)
"""

# =============================================================================
# JSONB Path Constants (DRY)
# =============================================================================

# Base path to variationDescriptor within genomicInterpretation
VD_BASE = "diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor"

# Variation descriptor field paths (require interp alias in query)
# Note: Triple braces {{{ produce literal { + f-string substitution
VD_ID = f"interp.value#>>'{{{VD_BASE},id}}'"
VD_EXTENSIONS = f"interp.value#>'{{{VD_BASE},extensions}}'"
VD_EXPRESSIONS = f"interp.value#>'{{{VD_BASE},expressions}}'"

# Subject age path (used in survival queries)
CURRENT_AGE_PATH = "p.phenopacket->'subject'->'timeAtLastEncounter'->>'iso8601duration'"

# Interpretation status path (used for P/LP filtering)
INTERP_STATUS_PATH = (
    "interp.value->'diagnosis'->'genomicInterpretations'->0->>'interpretationStatus'"
)


# =============================================================================
# Variant Type Classification SQL (Survival Analysis)
# =============================================================================
# Purpose: Classify variants for survival analysis curves
# Categories: CNV (>=50kb), Truncating, Non-truncating
# Used by: survival.py for Kaplan-Meier analysis

# fmt: off
VARIANT_TYPE_CLASSIFICATION_SQL = f"""
CASE
    -- CNVs: Large deletions or duplications >= 50kb
    WHEN {VD_ID} ~ ':(DEL|DUP)'
        AND COALESCE(
            (SELECT (ext#>>'{{value,length}}')::bigint
             FROM jsonb_array_elements({VD_EXTENSIONS}) AS ext
             WHERE ext->>'name' = 'coordinates'
            ), 0) >= 50000
        THEN 'CNV'
    -- Non-truncating: VEP IMPACT = MODERATE
    WHEN EXISTS (
        SELECT 1
        FROM jsonb_array_elements({VD_EXTENSIONS}) AS ext
        WHERE ext->>'name' = 'vep_annotation'
          AND ext#>>'{{value,impact}}' = 'MODERATE'
    ) THEN 'Non-truncating'
    -- Truncating variants
    WHEN (
        -- Intragenic deletions/duplications < 50kb
        (
            {VD_ID} ~ ':(DEL|DUP)'
            AND COALESCE(
                (SELECT (ext#>>'{{value,length}}')::bigint
                 FROM jsonb_array_elements({VD_EXTENSIONS}) AS ext
                 WHERE ext->>'name' = 'coordinates'
                ), 0) < 50000
        )
        OR
        -- VEP IMPACT = HIGH
        EXISTS (
            SELECT 1
            FROM jsonb_array_elements({VD_EXTENSIONS}) AS ext
            WHERE ext->>'name' = 'vep_annotation'
              AND ext#>>'{{value,impact}}' = 'HIGH'
        )
        OR
        -- VEP IMPACT = LOW/MODIFIER (P/LP filtered)
        EXISTS (
            SELECT 1
            FROM jsonb_array_elements({VD_EXTENSIONS}) AS ext
            WHERE ext->>'name' = 'vep_annotation'
              AND ext#>>'{{value,impact}}' IN ('LOW', 'MODIFIER')
        )
        OR
        -- No VEP and not DEL/DUP (P/LP filtered)
        (
            NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements({VD_EXTENSIONS}) AS ext
                WHERE ext->>'name' = 'vep_annotation'
            )
            AND NOT {VD_ID} ~ ':(DEL|DUP)'
        )
        OR
        -- HGVS pattern fallback
        EXISTS (
            SELECT 1
            FROM jsonb_array_elements({VD_EXPRESSIONS}) AS expr
            WHERE (
                (expr->>'syntax' = 'hgvs.p' AND expr->>'value' ~* 'fs')
                OR (expr->>'syntax' = 'hgvs.p'
                    AND (expr->>'value' ~* 'ter' OR expr->>'value' ~ '\\*'))
                OR (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '\\+[1-6]')
                OR (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '-[1-3]')
            )
        )
    ) THEN 'Truncating'
    ELSE 'Non-truncating'
END
"""
# fmt: on


# =============================================================================
# Variant Type CASE Expression (Variant Aggregation)
# =============================================================================
# Purpose: Classify variants for type distribution charts
# Categories: SNV, Deletion, Duplication, Insertion, Indel, Copy Number Loss/Gain
# Used by: variants.py for variant type statistics
# Requires: vd alias for variationDescriptor in query

VARIANT_TYPE_CASE = """
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


# =============================================================================
# Structural Type CASE Expression (All Variants)
# =============================================================================
# Purpose: Basic structural type classification for variant listings
# Categories: deletion, duplication, insertion, indel, SNV, CNV, OTHER
# Used by: all_variants.py for variant list queries
# Requires: vd alias for variationDescriptor in query

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
        WHEN (
            SELECT elem->>'value'
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.c'
            LIMIT 1
        ) ~ 'inv' THEN 'inversion'
        WHEN vd->'vcfRecord'->>'alt' ~ '^<(DEL|DUP|INS|INV|CNV)' THEN 'CNV'
        WHEN (
            SELECT elem->>'value'
            FROM jsonb_array_elements(vd->'expressions') elem
            WHERE elem->>'syntax' = 'hgvs.c'
            LIMIT 1
        ) ~ '>[ACGT]' THEN 'SNV'
        WHEN vd->>'moleculeContext' = 'genomic' THEN 'SNV'
        ELSE 'OTHER'
    END,
    vd->'molecularConsequences'->0->>'label'
)
"""


# =============================================================================
# Variant Type Filter SQL Generation (DRY)
# =============================================================================
# Purpose: Generate SQL WHERE clauses for filtering by structural type
# Uses STRUCTURAL_TYPE_CASE as single source of truth
# Used by: variant_query_builder.py for type filtering

# Valid structural types that can be filtered
VALID_STRUCTURAL_TYPES = frozenset({
    "SNV", "deletion", "duplication", "insertion", "indel", "inversion", "CNV"
})


def get_structural_type_filter(variant_type: str) -> str:
    """Generate SQL WHERE clause to filter by structural type.

    Uses STRUCTURAL_TYPE_CASE as the single source of truth for type classification.
    This ensures filtering logic matches the display classification exactly.

    Args:
        variant_type: One of 'SNV', 'deletion', 'duplication', 'insertion',
                     'indel', 'inversion', 'CNV'

    Returns:
        SQL expression that can be used in WHERE clause, or empty string if invalid

    Example:
        >>> filter_sql = get_structural_type_filter("SNV")
        >>> # Returns: "(COALESCE(vd->'structuralType'->>'label', ...) = 'SNV')"
    """
    if variant_type not in VALID_STRUCTURAL_TYPES:
        return ""
    return f"({STRUCTURAL_TYPE_CASE}) = '{variant_type}'"


# =============================================================================
# Phenopacket-Variant Linking CTE (Survival Analysis)
# =============================================================================
# Purpose: Link phenopackets to their variant_annotations via variant_id
# Used by: survival.py for variant type classification with VEP data
# Note: Extracts VCF-format variant IDs that match variant_annotations.variant_id

# CTE: Link phenopacket_id to variant_id for JOIN with variant_annotations
# This enables survival analysis to use VEP impact data from the separate table
PHENOPACKET_VARIANT_LINK_CTE = """
phenopacket_variant_link AS (
    SELECT DISTINCT
        p.phenopacket_id,
        UPPER(
            REGEXP_REPLACE(
                REGEXP_REPLACE(expr->>'value', '^chr', '', 'i'),
                ':',
                '-',
                'g'
            )
        ) as variant_id
    FROM phenopackets p,
         jsonb_array_elements(p.phenopacket->'interpretations') as interp,
         jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
         jsonb_array_elements(
             gi->'variantInterpretation'->'variationDescriptor'->'expressions'
         ) as expr
    WHERE expr->>'syntax' = 'vcf'
      AND p.deleted_at IS NULL
)
"""


def get_phenopacket_variant_link_cte() -> str:
    """Get CTE for linking phenopackets to variant_annotations.

    Returns:
        SQL CTE string that maps phenopacket_id to variant_id (VCF format).
        Use with LEFT JOIN to variant_annotations table.

    Example usage in query:
        WITH {get_phenopacket_variant_link_cte()}
        SELECT p.*, va.impact
        FROM phenopackets p
        LEFT JOIN phenopacket_variant_link pvl ON pvl.phenopacket_id = p.phenopacket_id
        LEFT JOIN variant_annotations va ON va.variant_id = pvl.variant_id
    """
    return PHENOPACKET_VARIANT_LINK_CTE


# =============================================================================
# Variant Type Classification with VEP (Survival Analysis V2)
# =============================================================================
# Purpose: Classify variants using VEP data from variant_annotations table
# Categories: CNV (>=50kb), Truncating (HIGH impact), Non-truncating (MODERATE)
# Used by: survival.py for Kaplan-Meier analysis
# Requires: LEFT JOIN to variant_annotations (aliased as 'va') in query

# fmt: off
def get_variant_type_classification_sql(vep_impact_alias: str = "va.impact") -> str:
    """Generate variant classification SQL that uses VEP data from variant_annotations.

    This version joins with the variant_annotations table instead of looking
    for embedded VEP data in phenopacket JSONB extensions.

    Args:
        vep_impact_alias: SQL alias for the VEP impact column (default: "va.impact")
            Use when variant_annotations is aliased differently in your query.

    Returns:
        SQL CASE expression string for variant type classification.

    Classification logic:
        1. CNV: Large deletions/duplications >= 50kb (from JSONB coordinates)
        2. Non-truncating: VEP IMPACT = 'MODERATE' (from variant_annotations)
        3. Truncating: VEP IMPACT = 'HIGH', small indels < 50kb, or HGVS patterns

    Example usage:
        classification_sql = get_variant_type_classification_sql()
        query = f'''
        WITH {get_phenopacket_variant_link_cte()}
        SELECT {classification_sql} AS variant_group
        FROM phenopackets p
        JOIN jsonb_array_elements(...) as interp ON true
        LEFT JOIN phenopacket_variant_link pvl ON pvl.phenopacket_id = p.phenopacket_id
        LEFT JOIN variant_annotations va ON va.variant_id = pvl.variant_id
        '''
    """
    return f"""
CASE
    -- CNVs: Large deletions or duplications >= 50kb
    WHEN {VD_ID} ~ ':(DEL|DUP)'
        AND COALESCE(
            (SELECT (ext#>>'{{value,length}}')::bigint
             FROM jsonb_array_elements({VD_EXTENSIONS}) AS ext
             WHERE ext->>'name' = 'coordinates'
            ), 0) >= 50000
        THEN 'CNV'

    -- Non-truncating: VEP IMPACT = MODERATE (from variant_annotations table)
    WHEN {vep_impact_alias} = 'MODERATE' THEN 'Non-truncating'

    -- Truncating: VEP IMPACT = HIGH
    WHEN {vep_impact_alias} = 'HIGH' THEN 'Truncating'

    -- Truncating: Intragenic deletions/duplications < 50kb
    WHEN {VD_ID} ~ ':(DEL|DUP)'
        AND COALESCE(
            (SELECT (ext#>>'{{value,length}}')::bigint
             FROM jsonb_array_elements({VD_EXTENSIONS}) AS ext
             WHERE ext->>'name' = 'coordinates'
            ), 0) < 50000
        THEN 'Truncating'

    -- Truncating: HGVS pattern fallback (frameshift, nonsense, splice)
    WHEN EXISTS (
        SELECT 1
        FROM jsonb_array_elements({VD_EXPRESSIONS}) AS expr
        WHERE (
            (expr->>'syntax' = 'hgvs.p' AND expr->>'value' ~* 'fs')
            OR (expr->>'syntax' = 'hgvs.p'
                AND (expr->>'value' ~* 'ter' OR expr->>'value' ~ '\\*'))
            OR (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '\\+[1-6]')
            OR (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '-[1-3]')
        )
    ) THEN 'Truncating'

    -- VEP LOW/MODIFIER impact: classify as Truncating (conservative for P/LP)
    WHEN {vep_impact_alias} IN ('LOW', 'MODIFIER') THEN 'Truncating'

    -- No VEP annotation and not CNV: default to Truncating (conservative)
    WHEN {vep_impact_alias} IS NULL AND NOT {VD_ID} ~ ':(DEL|DUP)' THEN 'Truncating'

    -- Default fallback
    ELSE 'Non-truncating'
END
"""
# fmt: on


# =============================================================================
# Unique Variant Extraction CTEs (Admin Sync)
# =============================================================================
# Purpose: Extract unique variant IDs for VEP annotation sync
# Categories: VCF expressions, Internal CNV format
# Used by: admin_endpoints.py for variant sync operations
# Note: Combines variants from two sources with UNION for deduplication

# Regex patterns for variant format validation
VCF_VARIANT_PATTERNS = """(
    -- SNVs and small indels (ACGT bases)
    expr->>'value' ~ '^(chr)?[0-9XYM]+-[0-9]+-[ACGT]+-[ACGT]+$'
    OR
    -- CNVs with END position (CHROM-POS-END-REF-<TYPE>) - primary format
    -- Per VCF 4.3 spec: symbolic alleles need END for unique identification
    expr->>'value' ~ '^(chr)?[0-9XYM]+-[0-9]+-[0-9]+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$'
    OR
    -- CNVs with symbolic alleles 4-part (<DEL>, <DUP>, etc.)
    expr->>'value' ~ '^(chr)?[0-9XYM]+-[0-9]+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$'
    OR
    -- CNVs in region format (17:start-end:DEL or 17-start-end-DEL)
    expr->>'value' ~ '^(chr)?[0-9XYM]+[:-][0-9]+-[0-9]+[:-](DEL|DUP|INS|INV|CNV)$'
)"""

# Internal CNV format regex (e.g., var:HNF1B:17:36459258-37832869:DEL)
# fmt: off
INTERNAL_CNV_PATTERN = (
    "'^var:[A-Za-z0-9]+:[0-9XYM]+:[0-9]+-[0-9]+:(DEL|DUP|INS|INV|CNV)$'"
)
# fmt: on

# CTE: Extract variants from VCF expressions array
VCF_VARIANTS_CTE = f"""
vcf_variants AS (
    -- Variants from VCF expressions array
    SELECT DISTINCT
        UPPER(
            REGEXP_REPLACE(
                REGEXP_REPLACE(expr->>'value', '^chr', '', 'i'),
                ':',
                '-',
                'g'
            )
        ) as variant_id
    FROM phenopackets,
         jsonb_array_elements(phenopacket->'interpretations') as interp,
         jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
         jsonb_array_elements(
             gi->'variantInterpretation'->'variationDescriptor'->'expressions'
         ) as expr
    WHERE expr->>'syntax' = 'vcf'
      AND deleted_at IS NULL
      AND {VCF_VARIANT_PATTERNS}
)"""

# CTE: Extract variants from variationDescriptor.id (internal CNV format)
INTERNAL_CNV_VARIANTS_CTE = f"""
internal_cnv_variants AS (
    -- Variants from variationDescriptor.id (internal CNV format)
    -- Format: var:GENE:CHROM:START-END:TYPE (e.g., var:HNF1B:17:36459258-37832869:DEL)
    SELECT DISTINCT vd->>'id' as variant_id
    FROM phenopackets p,
         jsonb_array_elements(p.phenopacket->'interpretations') as interp,
         jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
         LATERAL (
             SELECT gi->'variantInterpretation'->'variationDescriptor' as vd
         ) vd_lateral
    WHERE vd_lateral.vd IS NOT NULL
      AND vd_lateral.vd->>'id' IS NOT NULL
      AND p.deleted_at IS NULL
      AND vd_lateral.vd->>'id' ~ {INTERNAL_CNV_PATTERN}
)"""

# Combined CTE: VCF variants only (internal CNV format is redundant)
# Note: Internal CNV variants (var:GENE:CHROM:START-END:TYPE) are duplicates
# of VCF variants stored in a different format. VCF format is preferred for VEP.
UNIQUE_VARIANTS_CTE = f"""
{VCF_VARIANTS_CTE},
unique_variants AS (
    SELECT variant_id FROM vcf_variants
)"""


def get_unique_variants_query(select_clause: str = "variant_id") -> str:
    """Generate a complete query for unique variants.

    Args:
        select_clause: The SELECT clause to use (default: "variant_id")

    Returns:
        Complete SQL query string with CTEs

    Example:
        >>> query = get_unique_variants_query("COUNT(*)")
        >>> # Returns: WITH ... SELECT COUNT(*) FROM unique_variants
    """
    return f"""
WITH {UNIQUE_VARIANTS_CTE}
SELECT {select_clause}
FROM unique_variants
"""


def get_pending_variants_query() -> str:
    """Generate query for variants not yet in variant_annotations table.

    Returns:
        Complete SQL query string that finds variants needing sync
    """
    return f"""
WITH {UNIQUE_VARIANTS_CTE}
SELECT uv.variant_id
FROM unique_variants uv
LEFT JOIN variant_annotations va ON va.variant_id = uv.variant_id
WHERE va.variant_id IS NULL
"""


def get_variant_sync_status_query() -> str:
    """Generate query for variant sync status (total/synced counts).

    Returns:
        Complete SQL query string returning total and synced counts
    """
    return f"""
WITH {UNIQUE_VARIANTS_CTE}
SELECT
    COUNT(*) as total,
    COUNT(va.variant_id) as synced
FROM unique_variants uv
LEFT JOIN variant_annotations va ON va.variant_id = uv.variant_id
"""


# =============================================================================
# Protein Domain Constants (HNF1B) - Survival Analysis
# =============================================================================
# Purpose: Classify missense variants by protein functional domain location
# Used by: survival_handlers.py for protein domain Kaplan-Meier analysis
# Reference: UniProt P35680, doi:10.3390/ijms251910609
#
# Note: Only applicable to missense variants with valid HGVS.p notation.
# CNVs and truncating variants are excluded from this analysis.

# HNF1B protein domain boundaries (amino acid positions)
# Based on UniProt P35680 and published literature
HNF1B_PROTEIN_DOMAINS: dict[str, dict[str, int | str]] = {
    "POU-S": {
        "start": 90,
        "end": 173,
        "label": "POU-S (DNA Binding 1)",
        "description": "POU-specific domain for DNA binding",
    },
    "POU-H": {
        "start": 232,
        "end": 305,
        "label": "POU-H (DNA Binding 2)",
        "description": "POU-homeodomain for DNA binding",
    },
    "TAD": {
        "start": 314,
        "end": 557,
        "label": "TAD (Transactivation)",
        "description": "C-terminal transactivation domain for coactivator recruitment",
    },
}

# Regex pattern for missense variants in HGVS.p notation
# Matches: p.Arg177Cys, p.Met1Val, p.Gly400Ser, etc.
# Excludes: p.Arg177Ter (nonsense), p.Arg177fs (frameshift), p.Arg177* (stop)
# Note: Uses negative lookahead (?!Ter) to exclude termination codons
MISSENSE_HGVS_P_PATTERN = r"^p\.[A-Z][a-z]{2}\d+(?!Ter)[A-Z][a-z]{2}$"

# Regex pattern for extracting amino acid position from HGVS.p
# Captures the numeric position: p.Arg177Cys -> 177
AMINO_ACID_POSITION_PATTERN = r"p\.[A-Z][a-z]{2}(\d+)"


def get_missense_filter_sql(vd_path: str = "vd") -> str:
    """Generate SQL filter for missense variants only.

    Filters to variants with HGVS.p notation matching missense pattern,
    excluding truncating variants (nonsense, frameshift, stop gained).

    Args:
        vd_path: SQL alias/path for variationDescriptor (default: "vd")

    Returns:
        SQL EXISTS clause that filters to missense variants only

    Example:
        >>> vd = "gi->'variantInterpretation'->'variationDescriptor'"
        >>> sql = get_missense_filter_sql(vd)
    """
    # Note: PostgreSQL regex doesn't support lookahead, so we use AND NOT
    # to exclude nonsense variants ending in 'Ter'.
    # The pattern does NOT anchor at the start to handle NP_xxx:p.Xxx123Yyy format.
    return f"""EXISTS (
        SELECT 1
        FROM jsonb_array_elements({vd_path}->'expressions') elem
        WHERE elem->>'syntax' = 'hgvs.p'
        AND elem->>'value' ~ 'p\\.[A-Z][a-z]{{2}}\\d+[A-Z][a-z]{{2}}$'
        AND elem->>'value' !~ 'Ter$'
    )"""


def get_amino_acid_position_sql(vd_path: str = "vd") -> str:
    r"""Generate SQL to extract amino acid position from HGVS.p notation.

    Extracts the numeric position from patterns like p.Arg177Cys -> 177.

    Args:
        vd_path: SQL alias/path for variationDescriptor (default: "vd")

    Returns:
        SQL expression that extracts amino acid position as integer

    Example:
        >>> sql = get_amino_acid_position_sql()
        >>> # Returns: (regexp_match(..., 'p\.[A-Z][a-z]{2}(\d+)'))[1]::int
    """
    return f"""(regexp_match(
        (SELECT elem->>'value'
         FROM jsonb_array_elements({vd_path}->'expressions') elem
         WHERE elem->>'syntax' = 'hgvs.p'
         LIMIT 1),
        'p\\.[A-Z][a-z]{{2}}(\\d+)'
    ))[1]::int"""


def get_protein_domain_classification_sql(vd_path: str = "vd") -> str:
    """Generate SQL CASE for protein domain classification.

    Classifies missense variants into HNF1B protein domains based on
    amino acid position extracted from HGVS.p notation.

    Args:
        vd_path: SQL alias/path for variationDescriptor (default: "vd")

    Returns:
        SQL CASE expression for domain classification

    Domain boundaries:
        - POU-S: aa 90-173 (DNA binding domain 1)
        - POU-H: aa 232-305 (DNA binding domain 2)
        - TAD: aa 314-557 (Transactivation domain)
        - Other: Outside defined domains or position extraction failed

    Example:
        >>> sql = get_protein_domain_classification_sql()
        >>> # Returns CASE expression classifying into POU-S/POU-H/TAD/Other
    """
    pos_sql = get_amino_acid_position_sql(vd_path)
    pou_s = HNF1B_PROTEIN_DOMAINS["POU-S"]
    pou_h = HNF1B_PROTEIN_DOMAINS["POU-H"]
    tad = HNF1B_PROTEIN_DOMAINS["TAD"]

    return f"""CASE
    WHEN {pos_sql} BETWEEN {pou_s['start']} AND {pou_s['end']} THEN 'POU-S'
    WHEN {pos_sql} BETWEEN {pou_h['start']} AND {pou_h['end']} THEN 'POU-H'
    WHEN {pos_sql} BETWEEN {tad['start']} AND {tad['end']} THEN 'TAD'
    ELSE 'Other'
END"""


def get_cnv_exclusion_filter() -> str:
    """Generate SQL filter to exclude CNV/deletion variants.

    CNVs and large deletions don't have amino acid positions and must
    be excluded from protein domain analysis.

    Returns:
        SQL expression for WHERE clause to exclude CNVs

    Example:
        >>> sql = get_cnv_exclusion_filter()
        >>> # Use in WHERE: AND {sql}
    """
    return f"NOT {VD_ID} ~ ':(DEL|DUP)'"


def get_vcf_id_extraction_sql(
    vd_path: str = "gi->'variantInterpretation'->'variationDescriptor'",
) -> str:
    """Generate SQL to extract normalized VCF ID for variant_annotations JOIN.

    Extracts the VCF expression value from a variationDescriptor and normalizes
    it to match the format stored in variant_annotations table:
    - Removes 'chr' prefix (case insensitive)
    - Converts ':' to '-'
    - Uppercases the result

    Args:
        vd_path: SQL path to variationDescriptor (default assumes 'gi' alias)

    Returns:
        SQL expression that extracts the normalized VCF ID

    Example:
        >>> join_sql = get_vcf_id_extraction_sql()
        >>> query = f"LEFT JOIN variant_annotations va ON va.variant_id = ({join_sql})"
    """
    return f"""UPPER(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                (SELECT expr->>'value'
                 FROM jsonb_array_elements({vd_path}->'expressions') expr
                 WHERE expr->>'syntax' = 'vcf'
                 LIMIT 1),
                '^chr', '', 'i'
            ),
            ':',
            '-',
            'g'
        )
    )"""
