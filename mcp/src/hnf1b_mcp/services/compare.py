"""Cohort phenotype comparison across variant carrier groups.

Answers the first-class genotype-phenotype question "how do phenotype
frequencies differ between carriers of variant X vs Y" in a single call,
replacing an N-call client-side fan-out + hand-tally.

Output contract (token-efficient, self-documenting):

* ``groups`` — one entry per resolved variant: ``{alias, variant_id, simple_id,
  n, annotation_completeness}``. ``alias`` (``g0``, ``g1``, …) is a short handle
  used as the ``by_group`` key so the ~41-char canonical id is never repeated
  per feature.
* ``group_aliases`` — ``{alias: variant_id}`` convenience map.
* ``unmatched_variant_ids`` — caller ids that name no known variant (typo / stale
  id), ALWAYS present. A real variant with zero phenotyped carriers instead stays
  in ``groups`` with ``n: 0`` — the two are no longer indistinguishable.
* ``features`` — each ``{hpo_id, label, total_observed, by_group}`` where
  ``by_group[alias]`` is the fixed-order tuple
  ``[observed, excluded, unknown, observed_rate_among_recorded]``.
"""

from __future__ import annotations

from math import comb
from typing import Any

from ..client.api_client import ApiClient
from ..config import Settings
from ..contract._generated_paths import PHENOPACKETS_BY_VARIANT_BY_VARIANT_ID
from .errors import McpToolError
from .shaping import apply_budget, resolve_mode
from .variants import build_variant_id_index

_MAX_VARIANTS = 10
_MAX_TOP_N = 100

#: One-line, machine-readable description of the ``by_group`` cell layout, echoed
#: in meta so a consumer never has to infer the tuple order from prose.
BY_GROUP_FORMAT = (
    "by_group[alias] = [observed, excluded, unknown, observed_rate_among_recorded];"
    " keys are group aliases (see group_aliases). rate = observed/(observed+"
    "excluded) rounded to 3dp, or null when no carrier recorded the term."
)


def _tally_features(
    phenopackets: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Tally observed/excluded HPO features across a carrier group.

    Args:
        phenopackets: Carrier phenopacket content dicts.

    Returns:
        ``per_hpo`` mapping ``hpo_id`` to ``{label, observed, excluded}``.
    """
    per_hpo: dict[str, dict[str, Any]] = {}
    for pp in phenopackets:
        for feat in pp.get("phenotypicFeatures", []):
            hpo_type = feat.get("type", {})
            hpo_id = hpo_type.get("id", "")
            if not hpo_id:
                continue
            entry = per_hpo.setdefault(
                hpo_id,
                {"label": hpo_type.get("label", ""), "observed": 0, "excluded": 0},
            )
            if feat.get("excluded", False):
                entry["excluded"] += 1
            else:
                entry["observed"] += 1
    return per_hpo


def _observed_rate(observed: int, excluded: int) -> float | None:
    """Penetrance among RECORDED carriers: observed/(observed+excluded).

    ``None`` (not ``0``) when no carrier recorded the term, so "nobody assessed
    it" is never conflated with "assessed and absent in everyone".
    """
    recorded = observed + excluded
    if recorded <= 0:
        return None
    return round(observed / recorded, 3)


def _fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float | None:
    """Two-sided Fisher exact p-value for the 2x2 table ``[[a, b], [c, d]]``.

    Dependency-free (the MCP sidecar ships no scipy/numpy): sums hypergeometric
    probabilities over all tables with the same margins whose probability is
    ``<=`` the observed table's (the standard two-sided convention, matching
    ``scipy.stats.fisher_exact``). EXPLORATORY / uncorrected — research use only.

    Args:
        a: Top-left cell (e.g. group-0 observed).
        b: Top-right cell (e.g. group-0 excluded).
        c: Bottom-left cell (e.g. group-1 observed).
        d: Bottom-right cell (e.g. group-1 excluded).

    Returns:
        The two-sided p-value rounded to 4dp, or ``None`` when the table is empty.
    """
    n = a + b + c + d
    if n <= 0:
        return None
    r1, r2, c1 = a + b, c + d, a + c
    denom = comb(n, c1)
    if denom == 0:
        return None

    def prob(k: int) -> float:
        return comb(r1, k) * comb(r2, c1 - k) / denom

    p_obs = prob(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    total = sum(prob(k) for k in range(lo, hi + 1) if prob(k) <= p_obs * (1 + 1e-7))
    return min(1.0, round(total, 4))


async def compare_phenotypes(
    client: ApiClient,
    variant_ids: list[str],
    top_n: int = 25,
    response_mode: str = "compact",
    include_stats: bool = False,
) -> dict[str, Any]:
    """Compare HPO phenotype frequencies across carriers of several variants.

    Each variant id (canonical ``variant_id`` OR friendly ``simple_id`` such as
    ``"Var6"``) is resolved to its canonical id via the shared variant index;
    ids that name no known variant are returned in ``unmatched_variant_ids`` and
    omitted from ``groups`` (a typo is no longer indistinguishable from a real
    zero-carrier variant). For each resolved variant the carrier cohort is fetched
    once, per-HPO observed/excluded/unknown counts are tabulated, features are
    ranked by total observed across groups, and the top *top_n* are returned —
    bounded by the *response_mode* char budget.

    Args:
        client: Authenticated :class:`ApiClient` instance.
        variant_ids: 1–10 variant ids (canonical and/or ``simple_id``).
        top_n: Max distinct HPO features to return (ranked by total observed).
        response_mode: ``minimal``/``compact``/``standard``/``full`` — controls
            the char budget the feature list is trimmed to (with a ``_dropped``
            signal), so a comparison never overflows the mode ceiling.
        include_stats: When ``True`` and exactly two variants resolve, attach an
            EXPLORATORY per-feature ``stats`` (two-sided Fisher exact ``fisher_p``
            + ``effect_direction``). Uncorrected, research use only.

    Returns:
        A dict with ``groups``, ``group_aliases``, ``unmatched_variant_ids``,
        ``features`` (``by_group`` keyed by alias, cells
        ``[observed, excluded, unknown, observed_rate_among_recorded]``),
        ``total_distinct_features``, ``returned_features``, ``top_n``,
        ``has_more``, and a ``note``.

    Raises:
        McpToolError: ``invalid_input`` for an empty/oversized variant list or
            bad *top_n*; upstream errors propagated from :class:`ApiClient`.
    """
    if not variant_ids:
        raise McpToolError(
            "invalid_input",
            "variant_ids must contain at least one variant id",
            argument="variant_ids",
        )
    if len(variant_ids) > _MAX_VARIANTS:
        raise McpToolError(
            "invalid_input",
            f"variant_ids accepts at most {_MAX_VARIANTS} variants per call",
            argument="variant_ids",
        )
    if top_n < 1 or top_n > _MAX_TOP_N:
        raise McpToolError(
            "invalid_input",
            f"top_n must be between 1 and {_MAX_TOP_N}",
            argument="top_n",
        )

    mode = resolve_mode(response_mode)

    # ------------------------------------------------------------------
    # Resolve ids -> canonical (accepts simple_id); collect unmatched.
    # ------------------------------------------------------------------
    index = await build_variant_id_index(client)
    ordered_canon: list[str] = []
    group_rows: dict[str, dict[str, Any]] = {}
    unmatched: list[str] = []
    seen: set[str] = set()
    for rid in variant_ids:
        row = index.get(rid) or index.get(str(rid))
        if row is None:
            unmatched.append(rid)
            continue
        canon = row["variant_id"]
        if canon in seen:
            continue  # same variant supplied twice (e.g. via id + simple_id)
        seen.add(canon)
        ordered_canon.append(canon)
        group_rows[canon] = row

    alias_of: dict[str, str] = {c: f"g{i}" for i, c in enumerate(ordered_canon)}

    # ------------------------------------------------------------------
    # Fetch + tally each resolved cohort.
    # ------------------------------------------------------------------
    group_n: dict[str, int] = {}
    # hpo_id -> {label, by_alias: {alias: {observed, excluded}}}
    feature_index: dict[str, dict[str, Any]] = {}
    for canon in ordered_canon:
        alias = alias_of[canon]
        raw: Any = await client.get(
            PHENOPACKETS_BY_VARIANT_BY_VARIANT_ID.format(variant_id=canon)
        )
        carriers: list[dict[str, Any]] = raw if isinstance(raw, list) else []
        phenopackets = [
            c.get("phenopacket", {}) for c in carriers if isinstance(c, dict)
        ]
        per_hpo = _tally_features(phenopackets)
        group_n[alias] = len(phenopackets)
        for hpo_id, counts in per_hpo.items():
            idx = feature_index.setdefault(
                hpo_id, {"label": counts["label"], "by_alias": {}}
            )
            if not idx["label"]:
                idx["label"] = counts["label"]
            idx["by_alias"][alias] = {
                "observed": counts["observed"],
                "excluded": counts["excluded"],
            }

    aliases = [alias_of[c] for c in ordered_canon]

    # ------------------------------------------------------------------
    # annotation_completeness per group: mean over the FULL feature universe
    # of (observed+excluded)/n — the fraction of carriers for whom each term was
    # assessed. Stable (computed before top_n slicing). None when n == 0.
    # ------------------------------------------------------------------
    n_features = len(feature_index)
    completeness: dict[str, float | None] = {}
    for alias in aliases:
        n = group_n.get(alias, 0)
        if n <= 0 or n_features == 0:
            completeness[alias] = None
            continue
        recorded = 0
        for idx in feature_index.values():
            cell = idx["by_alias"].get(alias)
            if cell:
                recorded += cell["observed"] + cell["excluded"]
        completeness[alias] = round(recorded / (n * n_features), 3)

    # ------------------------------------------------------------------
    # Build features with alias-keyed tuple cells.
    # ------------------------------------------------------------------
    features: list[dict[str, Any]] = []
    for hpo_id, idx in feature_index.items():
        by_group: dict[str, list[Any]] = {}
        total_observed = 0
        for alias in aliases:
            cell = idx["by_alias"].get(alias, {"observed": 0, "excluded": 0})
            observed = cell["observed"]
            excluded = cell["excluded"]
            total_observed += observed
            unknown = max(group_n.get(alias, 0) - observed - excluded, 0)
            by_group[alias] = [
                observed,
                excluded,
                unknown,
                _observed_rate(observed, excluded),
            ]
        features.append(
            {
                "hpo_id": hpo_id,
                "label": idx["label"],
                "total_observed": total_observed,
                "by_group": by_group,
            }
        )

    # Deterministic order: total_observed desc, then hpo_id asc for a stable tie-break.
    features.sort(key=lambda f: (-f["total_observed"], f["hpo_id"]))
    total_distinct = len(features)
    shown = features[:top_n]

    # ------------------------------------------------------------------
    # Optional exploratory enrichment stats (exactly two groups only).
    # ------------------------------------------------------------------
    stats_note: str | None = None
    if include_stats:
        if len(aliases) == 2:
            g0, g1 = aliases[0], aliases[1]
            for feat in shown:
                a, b, _, r0 = feat["by_group"][g0]
                c, d, _, r1 = feat["by_group"][g1]
                if r0 is None or r1 is None:
                    direction = "insufficient_data"
                elif r0 > r1:
                    direction = "higher_in_g0"
                elif r1 > r0:
                    direction = "higher_in_g1"
                else:
                    direction = "equal"
                feat["stats"] = {
                    "fisher_p": _fisher_exact_two_sided(a, b, c, d),
                    "effect_direction": direction,
                }
            stats_note = (
                "stats.fisher_p is a two-sided Fisher exact test on the 2x2"
                " [observed, excluded] table for g0 vs g1. EXPLORATORY and"
                " uncorrected for multiple comparisons — research use only, not a"
                " confirmatory finding."
            )
        else:
            stats_note = (
                "include_stats was requested but enrichment stats require exactly"
                f" two resolved variants; {len(aliases)} resolved — stats omitted."
            )

    groups = [
        {
            "alias": alias_of[c],
            "variant_id": c,
            "simple_id": group_rows[c].get("simple_id"),
            "n": group_n.get(alias_of[c], 0),
            "annotation_completeness": completeness.get(alias_of[c]),
        }
        for c in ordered_canon
    ]

    note = (
        "by_group cells are [observed, excluded, unknown,"
        " observed_rate_among_recorded] keyed by group alias (see group_aliases);"
        " observed = HPO present, excluded = confirmed absent, unknown = carrier"
        " did not report the term, observed_rate_among_recorded ="
        " observed/(observed+excluded) (penetrance among assessed; null when none"
        " recorded). annotation_completeness is the mean fraction of carriers for"
        " whom each term was assessed. unmatched_variant_ids lists ids that name"
        " no known variant (vs a real variant with n:0). Ranked by total observed"
        " across groups; the top top_n of total_distinct_features are returned."
    )

    result: dict[str, Any] = {
        "groups": groups,
        "group_aliases": {alias_of[c]: c for c in ordered_canon},
        "unmatched_variant_ids": unmatched,
        "features": shown,
        "total_distinct_features": total_distinct,
        "returned_features": len(shown),
        "top_n": top_n,
        "has_more": total_distinct > len(shown),
        "note": note,
        "_meta": {"by_group_format": BY_GROUP_FORMAT},
    }
    if stats_note is not None:
        result["_meta"]["stats_note"] = stats_note

    # ------------------------------------------------------------------
    # Enforce the response_mode char budget (the only list tool that lacked one):
    # trim the features list to fit, keeping at least the top-ranked feature, and
    # re-sync the returned_features/has_more counters with the truncation.
    # ------------------------------------------------------------------
    budget = Settings().mode_char_budgets.get(mode, 12000)
    result, dropped = apply_budget(result, budget, ["features"], keep_min=1)
    if dropped is not None:
        result["returned_features"] = len(result["features"])
        result["has_more"] = total_distinct > len(result["features"])
        result["_dropped"] = dropped

    return result
