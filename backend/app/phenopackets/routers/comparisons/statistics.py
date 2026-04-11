"""Statistical helpers for phenopacket comparisons.

Extracted during Wave 4 from the monolithic ``comparisons.py``. The
regression test suite imports these directly from
``app.phenopackets.routers.comparisons``; the package ``__init__.py``
re-exports them so the test imports remain unchanged.
"""

from __future__ import annotations

import math
from typing import List

from scipy import stats


def calculate_fisher_exact_test(
    group1_present: int,
    group1_absent: int,
    group2_present: int,
    group2_absent: int,
) -> tuple[float, float]:
    """Calculate Fisher's exact test for a 2x2 contingency table.

    Always uses Fisher's exact test to match the R reference
    implementation. It is more appropriate for small sample sizes and
    gives exact p-values.

    Contingency table layout (matches R script)::

        [[yes.T, no.T],
         [yes.nT, no.nT]]

    Returns ``(p_value, odds_ratio)``. The odds ratio is returned as
    ``None`` when the computed value is non-finite — the rest of the
    pipeline treats that as "undefined" and avoids leaking inf/nan into
    the JSON response.
    """
    contingency_table = [
        [group1_present, group1_absent],
        [group2_present, group2_absent],
    ]

    total = group1_present + group1_absent + group2_present + group2_absent
    if total == 0:
        # Undefined odds ratio surfaced as ``None`` for JSON safety.
        return (1.0, None)  # type: ignore[return-value]

    # Fisher's exact test — matches
    # ``fisher.test(rbind(c(yes.T, no.T), c(yes.nT, no.nT)))`` in R.
    odds_ratio, p_value = stats.fisher_exact(contingency_table)

    if not math.isfinite(odds_ratio):
        odds_ratio = None
    else:
        odds_ratio = float(odds_ratio)

    return (float(p_value), odds_ratio)


def calculate_fdr_correction(p_values: List[float]) -> List[float]:
    """Apply Benjamini-Hochberg FDR correction for multiple testing.

    Matches R's ``p.adjust(pfisher, method="fdr")``. Returns the
    q-values in the same order as ``p_values``.
    """
    n = len(p_values)
    if n == 0:
        return []

    indexed_pvals = sorted(enumerate(p_values), key=lambda x: x[1])
    fdr_values: List[float] = [0.0] * n
    cummin = 1.0

    for rank_from_end, (original_idx, pval) in enumerate(reversed(indexed_pvals)):
        rank = n - rank_from_end  # 1-based rank from smallest
        adjusted = pval * n / rank
        cummin = min(cummin, adjusted)
        fdr_values[original_idx] = min(cummin, 1.0)

    return fdr_values


def calculate_cohens_h(p1: float, p2: float) -> float:
    """Calculate Cohen's h effect size for two proportions.

    Interpretation:
    - Small effect: h = 0.2
    - Medium effect: h = 0.5
    - Large effect: h = 0.8
    """
    phi1 = 2 * math.asin(math.sqrt(max(0.0, min(1.0, p1))))
    phi2 = 2 * math.asin(math.sqrt(max(0.0, min(1.0, p2))))
    return abs(phi1 - phi2)
