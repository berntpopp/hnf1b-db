"""Variant-type classification SQL fragments.

Three distinct classification helpers live here — each with its own
use-site in the aggregation endpoints:

- ``VARIANT_TYPE_CLASSIFICATION_SQL`` — survival analysis CNV /
  Truncating / Non-truncating buckets
- ``VARIANT_TYPE_CASE`` — variant-type distribution chart
  (SNV / Deletion / Duplication / Insertion / Indel / CNV gain/loss)
- ``STRUCTURAL_TYPE_CASE`` — all-variants listing page (coarse
  structural type detection)
- ``get_variant_type_classification_sql`` — survival analysis V2
  that joins against the ``variant_annotations`` table for VEP
  impact instead of reading it from the JSONB extensions

Extracted during Wave 4 from ``aggregations/sql_fragments.py``.
"""
# ruff: noqa: E501 - SQL queries are more readable when not line-wrapped

from __future__ import annotations

from .paths import VD_EXPRESSIONS, VD_EXTENSIONS, VD_ID

# =============================================================================
# Variant Type Classification SQL (Survival Analysis V1)
# =============================================================================

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
# Variant Type CASE Expression (variant aggregation chart)
# =============================================================================

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
# Structural Type CASE Expression (All Variants listing)
# =============================================================================

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


VALID_STRUCTURAL_TYPES = frozenset(
    {"SNV", "deletion", "duplication", "insertion", "indel", "inversion", "CNV"}
)


def get_structural_type_filter(variant_type: str) -> str:
    """Generate a SQL WHERE clause filtering by structural type.

    Uses :data:`STRUCTURAL_TYPE_CASE` as the single source of truth
    so the filter always matches the display classification. Returns
    an empty string for unknown types so the caller can treat it as
    "no filter".
    """
    if variant_type not in VALID_STRUCTURAL_TYPES:
        return ""
    return f"({STRUCTURAL_TYPE_CASE}) = '{variant_type}'"


# =============================================================================
# Variant Type Classification with VEP (Survival Analysis V2)
# =============================================================================


# fmt: off
def get_variant_type_classification_sql(vep_impact_alias: str = "va.impact") -> str:
    """Generate survival-analysis classification SQL using VEP impact data.

    This V2 variant joins with the ``variant_annotations`` table
    instead of relying on the VEP data embedded in the phenopacket
    JSONB extensions.

    The alias is configurable because the caller may alias the
    ``variant_annotations`` table differently in the host query.
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
