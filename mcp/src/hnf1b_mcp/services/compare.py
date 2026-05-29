"""Cohort phenotype comparison across variant carrier groups.

Answers the first-class genotype-phenotype question "how do phenotype
frequencies differ between carriers of variant X vs Y" in a single call,
replacing an N-call client-side fan-out + hand-tally.
"""

from __future__ import annotations

from typing import Any

from ..client.api_client import ApiClient
from ..contract._generated_paths import PHENOPACKETS_BY_VARIANT_BY_VARIANT_ID
from .errors import McpToolError

_MAX_VARIANTS = 10
_MAX_TOP_N = 100


def _tally_features(
    phenopackets: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], int]:
    """Tally observed/excluded HPO features across a carrier group.

    Args:
        phenopackets: Carrier phenopacket content dicts.

    Returns:
        ``(per_hpo, n)`` where *per_hpo* maps ``hpo_id`` to
        ``{label, observed, excluded}`` and *n* is the carrier count.
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
    return per_hpo, len(phenopackets)


async def compare_phenotypes(
    client: ApiClient,
    variant_ids: list[str],
    top_n: int = 25,
) -> dict[str, Any]:
    """Compare HPO phenotype frequencies across carriers of several variants.

    For each variant the carrier cohort is fetched once (``/phenopackets/
    by-variant/{id}`` returns full phenopacket content), then per-HPO
    observed / excluded / unknown counts are tabulated per group. Features are
    ranked by total observed count across groups and the top *top_n* returned.

    Args:
        client: Authenticated :class:`ApiClient` instance.
        variant_ids: 1–10 canonical variant ids (GA4GH VRS / CNV descriptor).
        top_n: Max distinct HPO features to return (ranked by total observed).

    Returns:
        A dict with ``groups`` (per-variant ``{variant_id, n}``), ``features``
        (each ``{hpo_id, label, total_observed, by_group: {variant_id:
        {observed, excluded, unknown}}}``), ``total_distinct_features``, and a
        ``note`` describing the unknown semantics.

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

    groups: list[dict[str, Any]] = []
    # hpo_id -> {label, by_group: {variant_id: {observed, excluded}}}
    feature_index: dict[str, dict[str, Any]] = {}

    for vid in variant_ids:
        raw: Any = await client.get(
            PHENOPACKETS_BY_VARIANT_BY_VARIANT_ID.format(variant_id=vid)
        )
        carriers: list[dict[str, Any]] = raw if isinstance(raw, list) else []
        phenopackets = [
            c.get("phenopacket", {}) for c in carriers if isinstance(c, dict)
        ]
        per_hpo, n = _tally_features(phenopackets)
        groups.append({"variant_id": vid, "n": n})
        for hpo_id, counts in per_hpo.items():
            idx = feature_index.setdefault(
                hpo_id, {"label": counts["label"], "by_group": {}}
            )
            if not idx["label"]:
                idx["label"] = counts["label"]
            idx["by_group"][vid] = {
                "observed": counts["observed"],
                "excluded": counts["excluded"],
            }

    group_n: dict[str, int] = {g["variant_id"]: g["n"] for g in groups}

    features: list[dict[str, Any]] = []
    for hpo_id, idx in feature_index.items():
        by_group: dict[str, dict[str, int]] = {}
        total_observed = 0
        for vid in variant_ids:
            cell = idx["by_group"].get(vid, {"observed": 0, "excluded": 0})
            observed = cell["observed"]
            excluded = cell["excluded"]
            total_observed += observed
            by_group[vid] = {
                "observed": observed,
                "excluded": excluded,
                "unknown": max(group_n.get(vid, 0) - observed - excluded, 0),
            }
        features.append(
            {
                "hpo_id": hpo_id,
                "label": idx["label"],
                "total_observed": total_observed,
                "by_group": by_group,
            }
        )

    features.sort(key=lambda f: f["total_observed"], reverse=True)
    total_distinct = len(features)

    return {
        "groups": groups,
        "features": features[:top_n],
        "total_distinct_features": total_distinct,
        "note": (
            "Per-group counts: observed (HPO present), excluded (confirmed"
            " absent), unknown (carrier did not report the term). Ranked by"
            " total observed across groups; truncated to top_n."
        ),
    }
