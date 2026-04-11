"""Phenotype distribution query for the comparisons router.

Builds the CTE chain that:

1. Classifies each variant into one of two groups (``group1_condition``
   / ``group2_condition`` coming from :mod:`variant_sql`).
2. Explodes each variant x phenotypic feature into one row with
   ``is_present`` / ``is_absent`` flags.
3. Aggregates per-phenotype counts per group, then pivots into the
   four-count layout the Fisher's exact test needs.
4. Filters phenotypes below ``:min_prevalence``.

Extracted from the monolithic ``comparisons.py`` during Wave 4.
"""
# ruff: noqa: E501 - SQL queries are more readable when not line-wrapped

from __future__ import annotations


def build_phenotype_distribution_query(
    group1_condition: str, group2_condition: str
) -> str:
    """Assemble the full SQL used by ``/compare/variant-types``.

    Returns the query text ready to be wrapped in a SQLAlchemy
    :func:`sqlalchemy.text` and executed with a ``min_prevalence``
    bind parameter.
    """
    return (
        """
    WITH variant_classification AS (
        -- Classify each VARIANT (not phenopacket) into group 1 or group 2.
        -- Matches R: one row per variant per individual (variant-level counting).
        SELECT
            p.phenopacket_id,
            p.id as phenopacket_internal_id,
            gen_interp.value#>>'{variantInterpretation,variationDescriptor,id}' as variant_id,
            CASE
                WHEN """
        + group1_condition
        + """ THEN 'group1'
                WHEN """
        + group2_condition
        + """ THEN 'group2'
                ELSE NULL
            END as variant_group
        FROM phenopackets p,
             jsonb_array_elements(p.phenopacket->'interpretations') AS interp,
             jsonb_array_elements(interp.value#>'{diagnosis,genomicInterpretations}') AS gen_interp
        WHERE p.deleted_at IS NULL
          AND gen_interp.value->>'interpretationStatus'
              IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
    ),
    variant_phenotype_matrix AS (
        -- Create a matrix of: variant_id x phenotype x present/absent.
        -- Each row represents one variant observation with one phenotype.
        -- CRITICAL: Each variant (genomic_interpretation) creates separate rows.
        SELECT
            ROW_NUMBER() OVER (ORDER BY vc.phenopacket_internal_id, vc.variant_id) as variant_phenotype_id,
            vc.phenopacket_internal_id,
            vc.variant_id,
            vc.variant_group,
            pf.value#>>'{type, id}' as hpo_id,
            pf.value#>>'{type, label}' as hpo_label,
            NOT COALESCE((pf.value->>'excluded')::boolean, false) as is_present,
            COALESCE((pf.value->>'excluded')::boolean, false) as is_absent
        FROM variant_classification vc
        JOIN phenopackets p ON p.id = vc.phenopacket_internal_id,
             jsonb_array_elements(p.phenopacket->'phenotypicFeatures') AS pf
        WHERE vc.variant_group IS NOT NULL
    ),
    phenotype_counts AS (
        -- Count for each phenotype: how many variants have it (yes) vs don't (no),
        -- grouped by variant_group (T/nT) and hpo_id.
        SELECT
            hpo_id,
            MAX(hpo_label) as hpo_label,
            variant_group,
            SUM(CASE WHEN is_present THEN 1 ELSE 0 END) as present_count,
            SUM(CASE WHEN is_absent THEN 1 ELSE 0 END) as absent_count
        FROM variant_phenotype_matrix
        GROUP BY hpo_id, variant_group
    ),
    phenotype_aggregated AS (
        -- Pivot to get yes.T, no.T, yes.nT, no.nT for each phenotype.
        SELECT
            hpo_id,
            MAX(hpo_label) as hpo_label,
            MAX(CASE WHEN variant_group = 'group1' THEN present_count ELSE 0 END) as group1_present,
            MAX(CASE WHEN variant_group = 'group1' THEN absent_count ELSE 0 END) as group1_absent,
            MAX(CASE WHEN variant_group = 'group1' THEN present_count + absent_count ELSE 0 END) as group1_total,
            MAX(CASE WHEN variant_group = 'group2' THEN present_count ELSE 0 END) as group2_present,
            MAX(CASE WHEN variant_group = 'group2' THEN absent_count ELSE 0 END) as group2_absent,
            MAX(CASE WHEN variant_group = 'group2' THEN present_count + absent_count ELSE 0 END) as group2_total
        FROM phenotype_counts
        GROUP BY hpo_id
        HAVING MAX(CASE WHEN variant_group = 'group1' THEN present_count + absent_count ELSE 0 END) > 0
           AND MAX(CASE WHEN variant_group = 'group2' THEN present_count + absent_count ELSE 0 END) > 0
    )
    SELECT
        hpo_id,
        hpo_label,
        group1_present,
        group1_absent,
        group1_total,
        CASE WHEN group1_total > 0
             THEN (group1_present::float / group1_total * 100)
             ELSE 0 END as group1_percentage,
        group2_present,
        group2_absent,
        group2_total,
        CASE WHEN group2_total > 0
             THEN (group2_present::float / group2_total * 100)
             ELSE 0 END as group2_percentage
    FROM phenotype_aggregated
    WHERE (group1_present::float / NULLIF(group1_total, 0) >= :min_prevalence
           OR group2_present::float / NULLIF(group2_total, 0) >= :min_prevalence)
    ORDER BY hpo_id
    """
    )
