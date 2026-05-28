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
from .shaping import apply_budget, resolve_mode

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
    params: dict[str, Any] | None = None
    if metric == "survival":
        params = {"comparison": comparison}

    upstream: Any = await client.get(path, params=params)

    # ------------------------------------------------------------------
    # 6. Wrap and budget-trim
    # ------------------------------------------------------------------
    # Wrap upstream payload as {"metric": metric, "result": <data>}
    # then trim the largest list(s) inside "result".
    result_data: dict[str, Any] = (
        upstream if isinstance(upstream, dict) else {"raw": upstream}
    )

    # Build a temporary wrapper so apply_budget can see the full payload size.
    # We prefix list keys with "result." conceptually, but apply_budget works
    # on a flat dict, so we pass the result_data directly plus the outer metric.
    # Strategy: apply budget on the full wrapper dict using dotted list keys
    # is not supported; instead we budget the result_data sub-dict and then
    # re-assemble.
    list_keys = _METRIC_LIST_KEYS.get(metric, ["data"])
    # fall back to any list-valued key in result_data when known keys absent
    effective_list_keys = [k for k in list_keys if k in result_data]
    if not effective_list_keys:
        effective_list_keys = [
            k for k, v in result_data.items() if isinstance(v, list)
        ]

    # We need to account for the wrapper overhead ("metric" key etc.).
    wrapper_overhead = len(json.dumps({"metric": metric, "result": None}))
    inner_budget = max(max_chars - wrapper_overhead, 1)

    shaped_result, dropped = apply_budget(
        result_data,
        max_chars=inner_budget,
        list_keys=effective_list_keys,
    )

    out: dict[str, Any] = {"metric": metric, "result": shaped_result}
    if dropped is not None:
        out["_dropped"] = dropped
    return out
