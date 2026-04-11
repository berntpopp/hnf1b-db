"""Pydantic response models for the phenopacket comparisons router."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
        None, description="Raw p-value from Fisher's exact test"
    )
    p_value_fdr: Optional[float] = Field(
        None, description="FDR-adjusted p-value (Benjamini-Hochberg correction)"
    )
    odds_ratio: Optional[float] = Field(
        None, description="Odds ratio from Fisher's exact test"
    )
    test_used: Optional[str] = Field(
        None, description="Statistical test used (fisher_exact)"
    )
    significant: bool = Field(
        ..., description="Whether difference is statistically significant (FDR < 0.05)"
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
