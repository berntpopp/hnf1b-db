"""Phenopacket comparisons sub-package.

Split from the old 861-LOC flat module during Wave 4. The public
import path is unchanged::

    from app.phenopackets.routers.comparisons import router

Submodules:

- ``schemas``     — Pydantic request/response models
- ``statistics``  — Fisher's exact test + FDR + Cohen's h helpers
- ``variant_sql`` — per-comparison-mode SQL classification fragments
- ``query``       — phenotype distribution CTE assembly
- ``router``      — thin FastAPI router delegating to the above

The three statistics helpers (``calculate_fisher_exact_test``,
``calculate_fdr_correction``, ``calculate_cohens_h``) are re-exported
at the package level so the existing 1,467-line
``tests/test_comparisons.py`` keeps working unchanged.
"""

from .router import router
from .schemas import ComparisonResult, PhenotypeComparison
from .statistics import (
    calculate_cohens_h,
    calculate_fdr_correction,
    calculate_fisher_exact_test,
)

__all__ = [
    "router",
    "ComparisonResult",
    "PhenotypeComparison",
    "calculate_cohens_h",
    "calculate_fdr_correction",
    "calculate_fisher_exact_test",
]
