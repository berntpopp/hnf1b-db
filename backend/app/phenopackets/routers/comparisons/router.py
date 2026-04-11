"""Phenopacket comparison endpoints (thin FastAPI router).

Owns ``GET /compare/variant-types``, delegating the SQL fragment
assembly, the query body, and the statistical helpers to the sibling
modules (:mod:`variant_sql`, :mod:`query`, :mod:`statistics`).
"""

from __future__ import annotations

from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

from .query import build_phenotype_distribution_query
from .schemas import ComparisonResult, PhenotypeComparison
from .statistics import (
    calculate_cohens_h,
    calculate_fdr_correction,
    calculate_fisher_exact_test,
)
from .variant_sql import build_group_conditions

router = APIRouter(prefix="/compare", tags=["phenopackets-comparisons"])


@router.get("/variant-types", response_model=ComparisonResult)
async def compare_variant_types(
    comparison: Literal[
        "truncating_vs_non_truncating",
        "truncating_vs_non_truncating_excl_cnv",
        "cnv_vs_point_mutation",
        "cnv_deletion_vs_duplication",
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
    reporting_mode: Literal["all_cases", "reported_only"] = Query(
        "all_cases",
        description=(
            "all_cases: Include unreported phenotypes as absent "
            "(assumes not-reported = absent). "
            "reported_only: Only count explicitly reported present/absent cases"
        ),
    ),
    db: AsyncSession = Depends(get_db),
):
    """Compare phenotype distributions between variant type groups.

    Performs a Fisher's exact test per phenotype between two groups
    defined by the ``comparison`` parameter, with Benjamini-Hochberg
    FDR correction and Cohen's h effect size. Four comparison modes
    are supported:

    1. Truncating vs Non-truncating (all variants)
    2. Truncating vs Non-truncating (excluding large CNVs ≥50kb)
    3. CNVs (17q del/dup ≥50kb) vs Non-CNV variants
    4. CNV deletions vs CNV duplications

    See ``variant_sql.build_group_conditions`` for the classification
    rules. The response is byte-identical to the pre-Wave-4 flat
    module; the Wave 4 HTTP surface baseline fixture
    ``phenopackets_compare_variant_types.json`` locks this in.
    """
    try:
        (
            group1_condition,
            group2_condition,
            group1_name,
            group2_name,
        ) = build_group_conditions(comparison)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    query = build_phenotype_distribution_query(
        group1_condition=group1_condition,
        group2_condition=group2_condition,
    )

    result = await db.execute(text(query), {"min_prevalence": min_prevalence})
    rows = result.fetchall()

    # First pass: raw p-values and effect sizes for every phenotype.
    preliminary_data: list[dict] = []
    raw_p_values: list[float] = []

    for row in rows:
        p_value, odds_ratio = calculate_fisher_exact_test(
            row.group1_present,
            row.group1_absent,
            row.group2_present,
            row.group2_absent,
        )

        p1 = row.group1_present / row.group1_total if row.group1_total > 0 else 0.0
        p2 = row.group2_present / row.group2_total if row.group2_total > 0 else 0.0
        effect_size = calculate_cohens_h(p1, p2)

        preliminary_data.append(
            {
                "row": row,
                "p_value": p_value,
                "odds_ratio": odds_ratio,
                "effect_size": effect_size,
            }
        )
        raw_p_values.append(p_value)

    # Apply FDR correction (Benjamini-Hochberg).
    fdr_p_values = calculate_fdr_correction(raw_p_values)

    # Second pass: build the response objects with the FDR-corrected p-values.
    phenotypes: List[PhenotypeComparison] = []
    for i, data in enumerate(preliminary_data):
        row = data["row"]
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
                p_value=data["p_value"],
                p_value_fdr=fdr_p_values[i],
                odds_ratio=data["odds_ratio"],
                test_used="fisher_exact",
                significant=(fdr_p_values[i] < 0.05),
                effect_size=data["effect_size"],
            )
        )

    # Sort by the requested metric.
    if sort_by == "p_value":
        phenotypes.sort(key=lambda x: (x.p_value if x.p_value is not None else 1.0))
    elif sort_by == "effect_size":
        phenotypes.sort(
            key=lambda x: (x.effect_size if x.effect_size is not None else 0.0),
            reverse=True,
        )
    elif sort_by == "prevalence_diff":
        phenotypes.sort(
            key=lambda x: abs(x.group1_percentage - x.group2_percentage),
            reverse=True,
        )

    phenotypes = phenotypes[:limit]

    # Group sizes are the maximum totals observed across the returned
    # phenotypes — filtering by ``min_prevalence`` may have excluded
    # some phenotypes.
    group1_count = max((p.group1_total for p in phenotypes), default=0)
    group2_count = max((p.group2_total for p in phenotypes), default=0)

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
