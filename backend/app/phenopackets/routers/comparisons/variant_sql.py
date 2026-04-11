"""SQL fragments for variant classification in comparison endpoints.

The comparisons endpoint supports four comparison modes, each with
its own set of ``group1_condition`` / ``group2_condition`` SQL
fragments and pretty group names. These fragments are huge and
repetitive — lifting them out of ``router.py`` keeps the router thin
enough to stay under 500 LOC.

Every fragment reads from a ``gen_interp`` row (already expanded
genomic interpretation) — the calling query is in ``query.py``.
"""
# ruff: noqa: E501 - SQL queries are more readable when not line-wrapped

from __future__ import annotations

from typing import Tuple

# =============================================================================
# Shared sub-fragments
# =============================================================================


_TRUNCATING_BASE = """
    (
        -- Priority 1: VEP IMPACT = HIGH
        EXISTS (
            SELECT 1
            FROM jsonb_array_elements(
                gen_interp.value#>'{variantInterpretation,variationDescriptor,extensions}'
            ) AS ext
            WHERE ext->>'name' = 'vep_annotation'
              AND ext#>>'{value,impact}' = 'HIGH'
        )
        OR
        -- Priority 2: VEP IMPACT = LOW/MODIFIER + Pathogenic
        (
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(
                    gen_interp.value#>'{variantInterpretation,variationDescriptor,extensions}'
                ) AS ext
                WHERE ext->>'name' = 'vep_annotation'
                  AND ext#>>'{value,impact}' IN ('LOW', 'MODIFIER')
            )
            AND
            gen_interp.value->>'interpretationStatus'
                IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
        )
        OR
        -- Priority 3: CNVs (DEL/DUP) + Pathogenic
        -- Matches R: is.na(IMPACT) & ACMG_groups == "LP/P" ~ "T" (CNVs have no IMPACT)
        (
            (gen_interp.value#>>'{variantInterpretation,variationDescriptor,id}' ~ 'DEL$'
             OR gen_interp.value#>>'{variantInterpretation,variationDescriptor,id}' ~ 'DUP$')
            AND
            gen_interp.value->>'interpretationStatus'
                IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
        )
        OR
        -- Priority 4: Missing VEP IMPACT + HGVS pattern indicates truncating
        -- For point mutations without VEP that show frameshift, nonsense, or splice site
        (
            NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(
                    gen_interp.value#>'{variantInterpretation,variationDescriptor,extensions}'
                ) AS ext
                WHERE ext->>'name' = 'vep_annotation'
                  AND ext#>>'{value,impact}' IS NOT NULL
            )
            AND
            gen_interp.value->>'interpretationStatus'
                IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
            AND
            gen_interp.value#>>'{variantInterpretation,variationDescriptor,id}' !~ 'DEL$'
            AND gen_interp.value#>>'{variantInterpretation,variationDescriptor,id}' !~ 'DUP$'
            AND
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(
                    gen_interp.value#>'{variantInterpretation,variationDescriptor,expressions}'
                ) AS expr
                WHERE (
                    -- Frameshift: contains 'fs' in protein notation
                    (expr->>'syntax' = 'hgvs.p' AND expr->>'value' ~* 'fs')
                    OR
                    -- Nonsense: contains 'Ter' or '*' in protein notation
                    (expr->>'syntax' = 'hgvs.p' AND (expr->>'value' ~* 'ter' OR expr->>'value' ~ '\\*'))
                    OR
                    -- Splice donor: +1 to +6 in transcript notation
                    (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '\\+[1-6]')
                    OR
                    -- Splice acceptor: -1 to -3 in transcript notation
                    (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '-[1-3]')
                    OR
                    -- Start loss: Met1 changes (affects start codon)
                    (expr->>'syntax' = 'hgvs.p' AND expr->>'value' ~* 'Met1')
                )
            )
        )
    )
"""


_LARGE_CNV = """
    (
        (gen_interp.value#>>'{variantInterpretation,variationDescriptor,id}' ~ 'DEL$'
         OR gen_interp.value#>>'{variantInterpretation,variationDescriptor,id}' ~ 'DUP$')
        AND
        COALESCE(
            (SELECT (ext#>>'{value,length}')::bigint
             FROM jsonb_array_elements(
                 gen_interp.value#>'{variantInterpretation,variationDescriptor,extensions}'
             ) AS ext
             WHERE ext->>'name' = 'coordinates'),
            0
        ) >= 50000
    )
"""


# =============================================================================
# Public helper
# =============================================================================


def build_group_conditions(comparison: str) -> Tuple[str, str, str, str]:
    """Return classification SQL + pretty names for a comparison mode.

    Tuple layout: ``(group1_condition, group2_condition, group1_name,
    group2_name)``.

    Raises ``ValueError`` if the comparison name is not recognised —
    the router catches this and returns a 400. The four modes are:

    - ``truncating_vs_non_truncating``           — all variants
    - ``truncating_vs_non_truncating_excl_cnv``  — same, but excludes large CNVs (>=50kb)
    - ``cnv_vs_point_mutation``                  — large CNVs vs everything else
    - ``cnv_deletion_vs_duplication``            — 17q deletions vs 17q duplications
    """
    if comparison == "truncating_vs_non_truncating":
        return (
            _TRUNCATING_BASE,
            f"NOT ({_TRUNCATING_BASE})",
            "Truncating",
            "Non-truncating",
        )

    if comparison == "truncating_vs_non_truncating_excl_cnv":
        # Same as the default comparison but large CNVs (>=50kb) are
        # excluded from BOTH groups. Small intragenic deletions
        # (<50kb) stay in the truncating group.
        group1 = f"NOT {_LARGE_CNV} AND {_TRUNCATING_BASE}"
        group2 = f"NOT {_LARGE_CNV} AND NOT ({_TRUNCATING_BASE})"
        return (
            group1,
            group2,
            "Truncating (excl. CNVs)",
            "Non-truncating (excl. CNVs)",
        )

    if comparison == "cnv_vs_point_mutation":
        group1 = _LARGE_CNV
        group2 = f"NOT {_LARGE_CNV}"
        return (
            group1,
            group2,
            "CNVs (17q del/dup)",
            "Non-CNV variants",
        )

    if comparison == "cnv_deletion_vs_duplication":
        group1 = """
            (
                -- Method 1: Variant ID ends with DEL suffix
                gen_interp.value#>>'{variantInterpretation,variationDescriptor,id}' ~ 'DEL$'
                OR
                -- Method 2: VEP consequence is transcript_ablation
                EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(
                        gen_interp.value#>'{variantInterpretation,variationDescriptor,extensions}'
                    ) AS ext
                    WHERE ext->>'name' = 'vep_annotation'
                      AND ext#>>'{value,most_severe_consequence}' = 'transcript_ablation'
                )
            )
        """
        group2 = """
            (
                -- Method 1: Variant ID ends with DUP suffix
                gen_interp.value#>>'{variantInterpretation,variationDescriptor,id}' ~ 'DUP$'
                OR
                -- Method 2: VEP consequence is transcript_amplification
                EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(
                        gen_interp.value#>'{variantInterpretation,variationDescriptor,extensions}'
                    ) AS ext
                    WHERE ext->>'name' = 'vep_annotation'
                      AND ext#>>'{value,most_severe_consequence}' = 'transcript_amplification'
                )
            )
        """
        return (group1, group2, "17q Deletion", "17q Duplication")

    raise ValueError(f"Unknown comparison type: {comparison}")
