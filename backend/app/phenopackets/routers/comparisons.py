"""Comparison endpoints for phenotype distributions across variant types.

Provides statistical comparisons of phenotype distributions between
variant groups (truncating vs non-truncating, CNV vs point mutations)
with Chi-square/Fisher's exact tests for significance.
"""

# ruff: noqa: E501, F821

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from scipy import stats
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(prefix="/compare", tags=["phenopackets-comparisons"])


class PhenotypeComparison(BaseModel):
    """Phenotype presence/absence comparison between two groups."""

    hpo_id: str = Field(..., description="HPO term identifier")
    hpo_label: str = Field(..., description="Human-readable phenotype name")
    group1_present: int = Field(..., description="Count present in group 1")
    group1_absent: int = Field(..., description="Count absent in group 1")
    group1_total: int = Field(..., description="Total individuals in group 1")
    group1_percentage: float = Field(..., description="Percentage present in group 1")
    group2_present: int = Field(..., description="Count present in group 2")
    group2_absent: int = Field(..., description="Count absent in group 2")
    group2_total: int = Field(..., description="Total individuals in group 2")
    group2_percentage: float = Field(..., description="Percentage present in group 2")
    p_value: Optional[float] = Field(
        None, description="P-value from Chi-square or Fisher's exact test"
    )
    test_used: Optional[str] = Field(
        None, description="Statistical test used (chi_square or fisher_exact)"
    )
    significant: bool = Field(
        ..., description="Whether difference is statistically significant (p < 0.05)"
    )
    effect_size: Optional[float] = Field(
        None, description="Effect size (Cohen's h for proportions)"
    )


class ComparisonResult(BaseModel):
    """Complete comparison result with metadata."""

    group1_name: str = Field(..., description="Name of first group")
    group2_name: str = Field(..., description="Name of second group")
    group1_count: int = Field(..., description="Total individuals in group 1")
    group2_count: int = Field(..., description="Total individuals in group 2")
    phenotypes: List[PhenotypeComparison] = Field(
        ..., description="List of phenotype comparisons"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


def calculate_statistical_test(
    group1_present: int,
    group1_absent: int,
    group2_present: int,
    group2_absent: int,
) -> tuple[float, str]:
    """Calculate appropriate statistical test for 2x2 contingency table.

    Uses Chi-square test if expected frequencies >= 5 in all cells,
    otherwise uses Fisher's exact test.

    Args:
        group1_present: Count of present phenotype in group 1
        group1_absent: Count of absent phenotype in group 1
        group2_present: Count of present phenotype in group 2
        group2_absent: Count of absent phenotype in group 2

    Returns:
        Tuple of (p_value, test_name)
    """
    contingency_table = [
        [group1_present, group1_absent],
        [group2_present, group2_absent],
    ]

    # Check expected frequencies for Chi-square test validity
    # Rule: all expected frequencies should be >= 5
    total = group1_present + group1_absent + group2_present + group2_absent
    if total == 0:
        return (1.0, "none")

    row1_total = group1_present + group1_absent
    row2_total = group2_present + group2_absent
    col1_total = group1_present + group2_present
    col2_total = group1_absent + group2_absent

    expected_freqs = [
        (row1_total * col1_total) / total,
        (row1_total * col2_total) / total,
        (row2_total * col1_total) / total,
        (row2_total * col2_total) / total,
    ]

    # Use Chi-square if all expected frequencies >= 5
    if all(freq >= 5 for freq in expected_freqs):
        chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
        return (float(p_value), "chi_square")
    else:
        # Use Fisher's exact test for small sample sizes
        oddsratio, p_value = stats.fisher_exact(contingency_table)
        return (float(p_value), "fisher_exact")


def calculate_cohens_h(p1: float, p2: float) -> float:
    """Calculate Cohen's h effect size for difference between two proportions.

    Cohen's h interpretation:
    - Small effect: h = 0.2
    - Medium effect: h = 0.5
    - Large effect: h = 0.8

    Args:
        p1: Proportion in group 1 (0.0 to 1.0)
        p2: Proportion in group 2 (0.0 to 1.0)

    Returns:
        Cohen's h effect size
    """
    import math

    # Apply arcsine transformation
    phi1 = 2 * math.asin(math.sqrt(max(0.0, min(1.0, p1))))
    phi2 = 2 * math.asin(math.sqrt(max(0.0, min(1.0, p2))))

    return abs(phi1 - phi2)


@router.get("/variant-types", response_model=ComparisonResult)
async def compare_variant_types(
    comparison: Literal[
        "truncating_vs_non_truncating", "cnv_vs_point_mutation"
    ] = Query(
        "truncating_vs_non_truncating",
        description="Type of variant comparison to perform",
    ),
    min_prevalence: float = Query(
        0.05,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum prevalence (0-1) in at least one group to include phenotype"
        ),
    ),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of phenotypes to return"
    ),
    sort_by: Literal["p_value", "effect_size", "prevalence_diff"] = Query(
        "p_value", description="Sort phenotypes by this metric"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Compare phenotype distributions between variant type groups.

    Performs statistical comparison of phenotype presence/absence between:
    1. Truncating vs Non-truncating variants
    2. CNVs (17q deletions/duplications) vs Point mutations

    **Truncating variants:**
    - Frameshift (p. notation contains 'fs')
    - Nonsense (p. notation contains 'Ter' or '*')
    - Splice site mutations (c. notation contains +1 to +6 or -1 to -3)

    **Non-truncating variants:**
    - Missense mutations (amino acid substitutions)
    - In-frame deletions/insertions
    - Other variants not classified as truncating

    **CNVs:**
    - Large deletions (17q deletion, identified by :DEL in variant ID)
    - Large duplications (identified by :DUP in variant ID)

    **Point mutations:**
    - SNVs, small indels (not CNVs)

    Args:
        comparison: Type of comparison to perform
        min_prevalence: Minimum prevalence (0-1) to include phenotype
        limit: Maximum number of phenotypes to return
        sort_by: Sort phenotypes by p_value, effect_size, or prevalence_diff
        db: Database session

    Returns:
        ComparisonResult with statistical tests for each phenotype
    """
    # Define variant classification SQL fragments
    if comparison == "truncating_vs_non_truncating":
        # Classify based on molecular consequence
        group1_condition = """
            -- Truncating: Frameshift, Nonsense, or Splice site
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(
                    interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,expressions}'
                ) AS expr
                WHERE (
                    -- Frameshift: contains 'fs' in protein notation
                    (expr->>'syntax' = 'hgvs.p' AND expr->>'value' ~* 'fs')
                    OR
                    -- Nonsense: contains 'Ter' or '*' in protein notation  # noqa: E501
                    (expr->>'syntax' = 'hgvs.p' AND (expr->>'value' ~* 'ter' OR expr->>'value' ~ '\\*'))
                    OR
                    -- Splice donor: +1 to +6 in transcript notation
                    (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '\\+[1-6]')
                    OR
                    -- Splice acceptor: -1 to -3 in transcript notation
                    (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '-[1-3]')
                )
            )
        """
        group2_condition = (
            """
            -- Non-truncating: All other variants (primarily missense)
            NOT ("""
            + group1_condition
            + ")"
        )

        group1_name = "Truncating"
        group2_name = "Non-truncating"

    elif comparison == "cnv_vs_point_mutation":
        # Classify based on structural type
        # noqa: E501
        group1_condition = """
            -- CNVs: Large deletions or duplications
            interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ ':(DEL|DUP)'
        """
        # noqa: E501
        group2_condition = """
            -- Point mutations: NOT CNVs
            interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' !~ ':(DEL|DUP)'
        """
        group1_name = "CNVs (17q del/dup)"
        group2_name = "Point mutations"

    else:
        raise ValueError(f"Unknown comparison type: {comparison}")

    # Query to get phenotype distributions for both groups
    # Use string concatenation to avoid escaping all JSONB curly braces
    query = (
        """
    WITH variant_classification AS (
        -- Classify each phenopacket into group 1 or group 2
        SELECT DISTINCT
            p.phenopacket_id,
            p.id as phenopacket_internal_id,
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
             jsonb_array_elements(p.phenopacket->'interpretations') AS interp
        WHERE p.deleted_at IS NULL
    ),
    group_sizes AS (
        -- Count total individuals in each group
        SELECT
            variant_group,
            COUNT(DISTINCT phenopacket_internal_id) as group_size
        FROM variant_classification
        WHERE variant_group IS NOT NULL
        GROUP BY variant_group
    ),
    phenotype_counts AS (
        -- Count phenotype presence/absence in each group
        SELECT
            pf.value#>>'{type, id}' as hpo_id,
            pf.value#>>'{type, label}' as hpo_label,
            vc.variant_group,
            -- Count present (not excluded)
            SUM(CASE
                WHEN NOT COALESCE((pf.value->>'excluded')::boolean, false)
                THEN 1 ELSE 0
            END) as present_count,
            -- Count explicitly absent (excluded = true)
            SUM(CASE
                WHEN COALESCE((pf.value->>'excluded')::boolean, false)
                THEN 1 ELSE 0
            END) as explicit_absent_count,
            -- Total individuals in this group
            MAX(gs.group_size) as group_size
        FROM variant_classification vc
        CROSS JOIN group_sizes gs
        JOIN phenopackets p ON p.id = vc.phenopacket_internal_id,
             jsonb_array_elements(p.phenopacket->'phenotypicFeatures') AS pf
        WHERE vc.variant_group = gs.variant_group
          AND vc.variant_group IS NOT NULL
        GROUP BY
            pf.value#>>'{type, id}',
            pf.value#>>'{type, label}',
            vc.variant_group,
            gs.variant_group
    ),
    phenotype_aggregated AS (
        -- Aggregate both groups for each phenotype
        SELECT  -- noqa: E501
            hpo_id,
            MAX(hpo_label) as hpo_label,
            MAX(CASE WHEN variant_group = 'group1' THEN present_count ELSE 0 END)
                as group1_present,
            -- noqa: E501
            MAX(CASE WHEN variant_group = 'group1' THEN group_size - present_count ELSE 0 END)
                as group1_absent,
            MAX(CASE WHEN variant_group = 'group1' THEN group_size ELSE 0 END)
                as group1_total,
            MAX(CASE WHEN variant_group = 'group2' THEN present_count ELSE 0 END)
                as group2_present,
            -- noqa: E501
            MAX(CASE WHEN variant_group = 'group2' THEN group_size - present_count ELSE 0 END)
                as group2_absent,
            MAX(CASE WHEN variant_group = 'group2' THEN group_size ELSE 0 END)
                as group2_total
        FROM phenotype_counts
        GROUP BY hpo_id
        HAVING MAX(CASE WHEN variant_group = 'group1' THEN group_size ELSE 0 END) > 0
           AND MAX(CASE WHEN variant_group = 'group2' THEN group_size ELSE 0 END) > 0
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

    result = await db.execute(text(query), {"min_prevalence": min_prevalence})
    rows = result.fetchall()

    # Calculate statistical tests and effect sizes for each phenotype
    phenotypes: List[PhenotypeComparison] = []
    for row in rows:
        p_value, test_used = calculate_statistical_test(
            row.group1_present,
            row.group1_absent,
            row.group2_present,
            row.group2_absent,
        )

        # Calculate effect size (Cohen's h)
        p1 = row.group1_present / row.group1_total if row.group1_total > 0 else 0.0
        p2 = row.group2_present / row.group2_total if row.group2_total > 0 else 0.0
        effect_size = calculate_cohens_h(p1, p2)

        phenotypes.append(
            PhenotypeComparison(
                hpo_id=row.hpo_id,
                hpo_label=row.hpo_label,
                group1_present=row.group1_present,
                group1_absent=row.group1_absent,
                group1_total=row.group1_total,
                group1_percentage=float(row.group1_percentage),
                group2_present=row.group2_present,
                group2_absent=row.group2_absent,
                group2_total=row.group2_total,
                group2_percentage=float(row.group2_percentage),
                p_value=p_value,
                test_used=test_used,
                significant=(p_value < 0.05) if p_value is not None else False,
                effect_size=effect_size,
            )
        )

    # Sort phenotypes by requested metric
    if sort_by == "p_value":
        phenotypes.sort(key=lambda x: (x.p_value if x.p_value is not None else 1.0))
    elif sort_by == "effect_size":
        phenotypes.sort(
            key=lambda x: (x.effect_size if x.effect_size is not None else 0.0),
            reverse=True,
        )
    elif sort_by == "prevalence_diff":
        phenotypes.sort(
            key=lambda x: abs(x.group1_percentage - x.group2_percentage), reverse=True
        )

    # Limit results
    phenotypes = phenotypes[:limit]

    # Get group sizes for metadata
    group1_count = phenotypes[0].group1_total if phenotypes else 0
    group2_count = phenotypes[0].group2_total if phenotypes else 0

    return ComparisonResult(
        group1_name=group1_name,
        group2_name=group2_name,
        group1_count=group1_count,
        group2_count=group2_count,
        phenotypes=phenotypes,
        metadata={
            "comparison_type": comparison,
            "min_prevalence": min_prevalence,
            "significant_count": sum(1 for p in phenotypes if p.significant),
            "total_phenotypes_compared": len(phenotypes),
        },
    )
