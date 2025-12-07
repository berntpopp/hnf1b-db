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
    "interp.value->'diagnosis'->'genomicInterpretations'"
    "->0->>'interpretationStatus'"
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
        WHEN vd->'vcfRecord'->>'alt' ~ '^<(DEL|DUP|INS|INV|CNV)' THEN 'CNV'
        WHEN vd->>'moleculeContext' = 'genomic' THEN 'SNV'
        ELSE 'OTHER'
    END,
    vd->'molecularConsequences'->0->>'label'
)
"""
