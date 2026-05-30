"""MCP tool: hnf1b_compare_phenotypes — cross-variant cohort phenotype comparison."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services import compare as compare_service
from hnf1b_mcp.services.dataclass import DataClass
from hnf1b_mcp.services.safe_tool import run_tool
from hnf1b_mcp.services.shaping import ResponseMode, resolve_mode


def register(mcp: FastMCP, client: ApiClient | None) -> None:
    """Register the hnf1b_compare_phenotypes tool on *mcp*.

    Args:
        mcp: The :class:`~fastmcp.FastMCP` application instance.
        client: The :class:`~hnf1b_mcp.client.api_client.ApiClient`, or *None*
            during registration-only scenarios.
    """

    @mcp.tool(
        name="hnf1b_compare_phenotypes",
        annotations={
            "title": "Compare Phenotypes Across Variants",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def hnf1b_compare_phenotypes(
        variant_ids: list[str],
        top_n: int = 25,
        response_mode: ResponseMode | None = None,
        include_stats: bool = False,
    ) -> dict[str, Any]:
        """Compare HPO phenotype frequencies across carriers of several variants.

        A genotype-phenotype analytical primitive: instead of fetching each
        variant's carriers and tallying HPO terms by hand, this returns per-HPO
        observed / excluded / unknown counts for each variant group in one call.

        Pass canonical ``variant_id`` values (GA4GH VRS / CNV descriptor) and/or
        the friendly ``simple_id`` (e.g. ``"Var6"``) returned by
        ``hnf1b_search_variants`` / ``hnf1b_get_variant`` — both are accepted and
        resolved to the canonical id. Up to 10 variants per call. An id that names
        no known variant (typo / stale id) is returned in
        ``unmatched_variant_ids`` and omitted from ``groups``; a real variant with
        no phenotyped carriers instead appears in ``groups`` with ``n: 0`` — the
        two are reported distinctly.

        Args:
            variant_ids: 1–10 variant ids (canonical and/or ``simple_id``).
            top_n: Maximum distinct HPO features to return, ranked by total
                observed count across groups (default 25, max 100).
            response_mode: Response verbosity — one of ``minimal``,
                ``compact``, ``standard``, ``full``.  Defaults to ``compact``.
                Controls the char budget the feature list is trimmed to (a
                ``meta.truncated`` signal fires when it does), so a large
                comparison never overflows the mode ceiling.
            include_stats: When ``True`` and exactly two variants resolve, attach
                an EXPLORATORY per-feature ``stats`` block (two-sided Fisher exact
                ``fisher_p`` + ``effect_direction``). Uncorrected for multiple
                comparisons — research use only, not a confirmatory finding.

        Returns:
            A dict with ``groups`` (per-variant ``{alias, variant_id, simple_id,
            n, annotation_completeness}``), ``group_aliases`` (``{alias:
            variant_id}``), ``unmatched_variant_ids``, ``features`` (each
            ``{hpo_id, label, total_observed, by_group}`` where ``by_group`` is
            keyed by group alias with cells ``[observed, excluded, unknown,
            observed_rate_among_recorded]``), ``total_distinct_features``,
            ``returned_features``/``has_more``, a ``note``, ``data_class``, and
            ``meta`` (carrying ``by_group_format``).
        """
        mode = resolve_mode(response_mode)
        return await run_tool(
            lambda: compare_service.compare_phenotypes(
                client,  # type: ignore[arg-type]
                variant_ids,
                top_n=top_n,
                response_mode=mode,
                include_stats=include_stats,
            ),
            data_class=DataClass.DERIVED,
            response_mode=mode,
        )
