"""Aggregate statistics service for HNF1B phenopacket endpoints.

All endpoints live under ``/phenopackets/aggregate/`` and are published-only
(safe, read-only).  The public entry-point is :func:`get_statistics`.
"""

from __future__ import annotations

import json
from typing import Any

from ..client.api_client import ApiClient
from ..config import Settings
from ..contract._generated_paths import (
    PHENOPACKETS_AGGREGATE_AGE_OF_ONSET,
    PHENOPACKETS_AGGREGATE_BY_DISEASE,
    PHENOPACKETS_AGGREGATE_BY_FEATURE,
    PHENOPACKETS_AGGREGATE_KIDNEY_STAGES,
    PHENOPACKETS_AGGREGATE_PUBLICATIONS_TIMELINE,
    PHENOPACKETS_AGGREGATE_SEX_DISTRIBUTION,
    PHENOPACKETS_AGGREGATE_SUMMARY,
    PHENOPACKETS_AGGREGATE_SURVIVAL_DATA,
    PHENOPACKETS_AGGREGATE_VARIANT_PATHOGENICITY,
    PHENOPACKETS_AGGREGATE_VARIANT_TYPES,
)
from .errors import McpToolError
from .shaping import _size, apply_budget, resolve_mode

# Metrics whose counts are per-carrier variant *instances* (e.g. sum ≈ 864),
# NOT distinct variants (~198). The unit is stated explicitly so a caller never
# mistakes the distribution for one over unique variants. ``count_mode=unique``
# switches the backend to distinct-variant counts.
_VARIANT_INSTANCE_METRICS = {"variant_types", "variant_pathogenicity"}
_VALID_COUNT_MODES = ("all", "unique")


def _round_percentages(obj: Any) -> Any:
    """Recursively round any ``percentage`` float to 2 dp to kill float noise.

    Args:
        obj: An arbitrary JSON-like structure.

    Returns:
        The same structure with ``percentage`` values rounded to 2 decimals.
    """
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k == "percentage" and isinstance(v, float):
                out[k] = round(v, 2)
            else:
                out[k] = _round_percentages(v)
        return out
    if isinstance(obj, list):
        return [_round_percentages(v) for v in obj]
    return obj


def _downsample(points: list[Any], keep: int) -> list[Any]:
    """Uniformly down-sample a time-series, always retaining first and last.

    Args:
        points: The ordered list of survival time points.
        keep: Approximate number of points to retain.

    Returns:
        A down-sampled copy preserving the endpoints (curve shape).
    """
    if len(points) <= keep or keep < 2:
        return points
    step = -(-len(points) // keep)  # ceil division
    sampled = points[::step]
    if sampled and points[-1] is not sampled[-1]:
        sampled.append(points[-1])
    return sampled


def _shape_survival(
    result_data: dict[str, Any], max_chars: int
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Fit a survival payload to budget by down-sampling curves, not dropping arms.

    Survival ``groups`` are comparison arms referenced by ``statistical_tests``;
    dropping a whole arm would leave a p-value citing an absent arm. Instead we
    progressively down-sample each arm's ``survival_data`` time-series and only
    drop arms as a disclosed last resort.

    Args:
        result_data: The survival payload (with ``groups``).
        max_chars: The character budget for the result portion.

    Returns:
        ``(shaped, dropped_summary)`` — *dropped_summary* is ``None`` when no
        reshaping was needed.
    """
    if _size(result_data) <= max_chars:
        return result_data, None

    groups = result_data.get("groups")
    if not isinstance(groups, list) or not groups:
        # No curves to thin — fall back to the generic list trimmer.
        return apply_budget(result_data, max_chars, ["groups", "data"])

    originals = [
        list(g.get("survival_data") or []) if isinstance(g, dict) else []
        for g in groups
    ]
    for keep in (150, 80, 40, 20, 10, 5):
        for group, original in zip(groups, originals):
            if original:
                group["survival_data"] = _downsample(original, keep)
        if _size(result_data) <= max_chars:
            return result_data, {
                "downsampled_curve_points_to": keep,
                "arms_preserved": len(groups),
                "reason": "max_response_chars",
                "note": (
                    "survival curves down-sampled to fit the budget; all"
                    " comparison arms (and statistical_tests) are preserved"
                ),
            }

    # Last resort: drop arms from the end, disclosing which ones.
    dropped_names: list[str] = []
    while len(groups) > 1 and _size(result_data) > max_chars:
        removed = groups.pop()
        dropped_names.append(str(removed.get("name", "?")))
    return result_data, {
        "dropped_arms": dropped_names,
        "reason": "max_response_chars",
        "note": (
            "budget too small even after down-sampling; dropped arms are listed"
            " — statistical_tests may reference a dropped arm. Widen"
            " response_mode for the full comparison."
        ),
    }

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Map the MCP-side friendly metric name → the generated API path constant.
# The friendly KEYS are an MCP-side curation concern (kept here); the path VALUES
# are sourced from the generated contract so they cannot drift from the backend.
_METRIC_PATH: dict[str, str] = {
    "summary": PHENOPACKETS_AGGREGATE_SUMMARY,
    "sex_distribution": PHENOPACKETS_AGGREGATE_SEX_DISTRIBUTION,
    "age_of_onset": PHENOPACKETS_AGGREGATE_AGE_OF_ONSET,
    "by_disease": PHENOPACKETS_AGGREGATE_BY_DISEASE,
    "kidney_stages": PHENOPACKETS_AGGREGATE_KIDNEY_STAGES,
    "by_feature": PHENOPACKETS_AGGREGATE_BY_FEATURE,
    "variant_pathogenicity": PHENOPACKETS_AGGREGATE_VARIANT_PATHOGENICITY,
    "variant_types": PHENOPACKETS_AGGREGATE_VARIANT_TYPES,
    "survival": PHENOPACKETS_AGGREGATE_SURVIVAL_DATA,
    "publications_timeline": PHENOPACKETS_AGGREGATE_PUBLICATIONS_TIMELINE,
}

# Metrics that have well-known top-level list keys in their upstream payload.
# Used to guide apply_budget for efficient trimming.
_METRIC_LIST_KEYS: dict[str, list[str]] = {
    "summary": [],
    "sex_distribution": ["data"],
    "age_of_onset": ["data"],
    "by_disease": ["data"],
    "kidney_stages": ["data"],
    "by_feature": ["features", "data"],
    "variant_pathogenicity": ["data"],
    "variant_types": ["data"],
    "survival": ["groups", "data"],
    "publications_timeline": ["timeline", "data"],
}

_VALID_METRICS: list[str] = sorted(_METRIC_PATH.keys())

# NOTE: the survival-data ``comparison`` param is NOT exposed as an enum in the
# OpenAPI snapshot (it is a runtime-validated plain string distinct from the
# /compare/variant-types ``Comparison`` enum), so it stays hand-coded MCP-side.
_SURVIVAL_COMPARISONS: list[str] = sorted(
    ["variant_type", "pathogenicity", "disease_subtype", "protein_domain"]
)

# Static dry-run estimates per metric (rough description strings).
_DRY_RUN_ESTIMATES: dict[str, str] = {
    "summary": "1 summary object",
    "sex_distribution": "~3 groups/rows",
    "age_of_onset": "~10 groups/rows",
    "by_disease": "~5 groups/rows",
    "kidney_stages": "~5 groups/rows",
    "by_feature": "~50 groups/rows",
    "variant_pathogenicity": "~4 groups/rows",
    "variant_types": "~5 groups/rows",
    "survival": "~4 groups/rows",
    "publications_timeline": "~20 groups/rows",
}

_HARD_CAP = 80_000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_statistics(
    client: ApiClient,
    metric: str,
    response_mode: str | None = "compact",
    max_response_chars: int | None = None,
    dry_run: bool = False,
    comparison: str | None = None,
    count_mode: str | None = None,
) -> dict[str, Any]:
    """Fetch an aggregate statistics metric from the HNF1B phenopacket API.

    Args:
        client: Configured :class:`~hnf1b_mcp.client.api_client.ApiClient`.
        metric: One of the known aggregate metric names (see module constants).
        response_mode: Budget tier — ``"minimal"``, ``"compact"`` (default),
            ``"standard"``, or ``"full"``.
        max_response_chars: Hard override for the char budget; capped at
            ``80 000``.  When *None* the tier budget from
            :class:`~hnf1b_mcp.config.Settings` is used.
        dry_run: When ``True`` skip the actual HTTP fetch and return a
            lightweight availability/estimate dict.
        comparison: Required when *metric* is ``"survival"``; must be one of
            ``variant_type``, ``pathogenicity``, ``disease_subtype``,
            ``protein_domain``.
        count_mode: Only meaningful for ``variant_types`` /
            ``variant_pathogenicity``. ``"all"`` (default) counts per-carrier
            variant *instances*; ``"unique"`` counts distinct variants.

    Returns:
        A plain :class:`dict` with at least ``metric`` and (on live runs)
        ``result``.  A ``_dropped`` key is added when the payload was trimmed
        to stay within *max_response_chars*.

    Raises:
        McpToolError: On invalid *metric*, missing/bad *comparison* for
            survival, or upstream API errors.
    """
    # ------------------------------------------------------------------
    # 1. Validate metric
    # ------------------------------------------------------------------
    if metric not in _METRIC_PATH:
        raise McpToolError(
            "invalid_input",
            f"Unknown metric '{metric}'. Choose one of: {_VALID_METRICS}",
            argument="metric",
            choices=_VALID_METRICS,
        )

    # ------------------------------------------------------------------
    # 2. Validate survival comparison
    # ------------------------------------------------------------------
    if metric == "survival":
        if comparison is None or comparison not in _SURVIVAL_COMPARISONS:
            raise McpToolError(
                "invalid_input",
                (
                    "survival requires a 'comparison' parameter; "
                    f"choose one of {_SURVIVAL_COMPARISONS}"
                ),
                argument="comparison",
                choices=_SURVIVAL_COMPARISONS,
            )

    # ------------------------------------------------------------------
    # 2b. Validate count_mode (variant metrics only)
    # ------------------------------------------------------------------
    if count_mode is not None and count_mode not in _VALID_COUNT_MODES:
        raise McpToolError(
            "invalid_input",
            f"count_mode must be one of {list(_VALID_COUNT_MODES)}",
            argument="count_mode",
            choices=list(_VALID_COUNT_MODES),
        )

    # ------------------------------------------------------------------
    # 3. dry_run fast-path (no HTTP)
    # ------------------------------------------------------------------
    if dry_run:
        return {
            "metric": metric,
            "available": True,
            "estimated": _DRY_RUN_ESTIMATES.get(metric, "unknown"),
        }

    # ------------------------------------------------------------------
    # 4. Resolve char budget
    # ------------------------------------------------------------------
    resolved_mode = resolve_mode(response_mode)
    settings = Settings()
    budget_from_mode = settings.mode_char_budgets[resolved_mode]
    max_chars = min(
        max_response_chars if max_response_chars is not None else budget_from_mode,
        _HARD_CAP,
    )

    # ------------------------------------------------------------------
    # 5. Fetch upstream
    # ------------------------------------------------------------------
    path = _METRIC_PATH[metric]
    params: dict[str, Any] = {}
    if metric == "survival":
        params["comparison"] = comparison
    if metric in _VARIANT_INSTANCE_METRICS and count_mode is not None:
        params["count_mode"] = count_mode

    upstream: Any = await client.get(path, params=params or None)

    # ------------------------------------------------------------------
    # 6. Wrap and budget-trim
    # ------------------------------------------------------------------
    # Wrap upstream payload as {"metric": metric, "result": <data>}
    # then trim the largest list(s) inside "result".
    result_data: dict[str, Any] = (
        upstream if isinstance(upstream, dict) else {"raw": upstream}
    )

    # Kill percentage float noise (e.g. 45.023148… -> 45.02) everywhere.
    result_data = _round_percentages(result_data)

    # We need to account for the wrapper overhead ("metric" key etc.).
    wrapper_overhead = len(json.dumps({"metric": metric, "result": None}))
    inner_budget = max(max_chars - wrapper_overhead, 1)

    if metric == "survival":
        # Preserve every comparison arm; down-sample curves to fit the budget.
        shaped_result, dropped = _shape_survival(result_data, inner_budget)
    else:
        list_keys = _METRIC_LIST_KEYS.get(metric, ["data"])
        # fall back to any list-valued key in result_data when known keys absent
        effective_list_keys = [k for k in list_keys if k in result_data]
        if not effective_list_keys:
            effective_list_keys = [
                k for k, v in result_data.items() if isinstance(v, list)
            ]
        shaped_result, dropped = apply_budget(
            result_data,
            max_chars=inner_budget,
            list_keys=effective_list_keys,
        )

    out: dict[str, Any] = {"metric": metric, "result": shaped_result}

    # Label what the variant distributions actually count, so a caller never
    # reads per-carrier instance counts as a distribution over distinct variants.
    if metric in _VARIANT_INSTANCE_METRICS:
        effective_mode = count_mode or "all"
        if effective_mode == "unique":
            out["unit"] = "distinct_variants"
            out["unit_note"] = "counts are distinct variants (count_mode=unique)."
        else:
            out["unit"] = "variant_instances_per_carrier"
            out["unit_note"] = (
                "counts are per-carrier variant instances (the column sums to"
                " the carrier total, ~864), NOT distinct variants (~198). Pass"
                " count_mode='unique' for a distribution over distinct variants."
            )

    if dropped is not None:
        out["_dropped"] = dropped
    return out
