"""Common table expressions (CTEs) used by aggregation + admin queries.

Owns:

- The phenopacket-to-variant linking CTE (``PHENOPACKET_VARIANT_LINK_CTE``)
- The "unique variants" CTE pair used by the admin sync endpoints
  (``VCF_VARIANTS_CTE``, ``INTERNAL_CNV_VARIANTS_CTE``,
  ``UNIQUE_VARIANTS_CTE``)
- Three small query-builder helpers that wrap those CTEs for the
  common admin queries: ``get_unique_variants_query``,
  ``get_pending_variants_query``, ``get_variant_sync_status_query``

Extracted during Wave 4 from ``aggregations/sql_fragments.py``.
"""
# ruff: noqa: E501 - SQL queries are more readable when not line-wrapped

from __future__ import annotations

# =============================================================================
# Public visibility filter fragment (I3 + I7 + I1 invariants).
#
# Every public endpoint that touches the ``phenopackets`` table must embed
# this fragment (or the ORM ``public_filter()`` helper) in its WHERE clause
# so that draft, archived, and soft-deleted records are never exposed.
# =============================================================================

PUBLIC_FILTER_FRAGMENT = (
    "p.deleted_at IS NULL"
    "\n      AND p.state = 'published'"
    "\n      AND p.head_published_revision_id IS NOT NULL"
)

# =============================================================================
# Phenopacket-Variant Linking CTE (Survival Analysis)
# =============================================================================

PHENOPACKET_VARIANT_LINK_CTE = f"""
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
      AND {PUBLIC_FILTER_FRAGMENT}
)
"""


def get_phenopacket_variant_link_cte() -> str:
    """Get CTE for linking phenopackets to ``variant_annotations``.

    The CTE maps ``phenopacket_id`` to a normalised VCF-format
    ``variant_id`` suitable for joining against the
    ``variant_annotations`` table.
    """
    return PHENOPACKET_VARIANT_LINK_CTE


# =============================================================================
# Unique Variant Extraction CTEs (Admin Sync)
# =============================================================================

# Regex patterns for variant format validation.
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


# Internal CNV format regex (e.g., var:HNF1B:17:36459258-37832869:DEL).
# fmt: off
INTERNAL_CNV_PATTERN = (
    "'^var:[A-Za-z0-9]+:[0-9XYM]+:[0-9]+-[0-9]+:(DEL|DUP|INS|INV|CNV)$'"
)
# fmt: on


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
    FROM phenopackets p,
         jsonb_array_elements(p.phenopacket->'interpretations') as interp,
         jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
         jsonb_array_elements(
             gi->'variantInterpretation'->'variationDescriptor'->'expressions'
         ) as expr
    WHERE expr->>'syntax' = 'vcf'
      AND {PUBLIC_FILTER_FRAGMENT}
      AND {VCF_VARIANT_PATTERNS}
)"""


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


# Combined CTE: VCF variants only (internal CNV format is redundant).
# Note: internal CNV variants (var:GENE:CHROM:START-END:TYPE) are
# duplicates of VCF variants stored in a different format. VCF format
# is preferred for VEP.
UNIQUE_VARIANTS_CTE = f"""
{VCF_VARIANTS_CTE},
unique_variants AS (
    SELECT variant_id FROM vcf_variants
)"""


def get_unique_variants_query(select_clause: str = "variant_id") -> str:
    """Generate a complete query over the unique-variants CTE."""
    return f"""
WITH {UNIQUE_VARIANTS_CTE}
SELECT {select_clause}
FROM unique_variants
"""


def get_pending_variants_query() -> str:
    """Generate a query for variants not yet in ``variant_annotations``."""
    return f"""
WITH {UNIQUE_VARIANTS_CTE}
SELECT uv.variant_id
FROM unique_variants uv
LEFT JOIN variant_annotations va ON va.variant_id = uv.variant_id
WHERE va.variant_id IS NULL
"""


def get_pending_variants_count_query() -> str:
    """Generate a COUNT query for variants not yet in ``variant_annotations``.

    Used by the admin variant sync endpoint to report the correct
    ``items_to_process`` for the non-force path — counting pending
    variants, not all unique variants.
    """
    return f"""
WITH {UNIQUE_VARIANTS_CTE}
SELECT COUNT(*)
FROM unique_variants uv
LEFT JOIN variant_annotations va ON va.variant_id = uv.variant_id
WHERE va.variant_id IS NULL
"""


def get_variant_sync_status_query() -> str:
    """Generate a query returning ``(total, synced)`` counts for sync status."""
    return f"""
WITH {UNIQUE_VARIANTS_CTE}
SELECT
    COUNT(*) as total,
    COUNT(va.variant_id) as synced
FROM unique_variants uv
LEFT JOIN variant_annotations va ON va.variant_id = uv.variant_id
"""
