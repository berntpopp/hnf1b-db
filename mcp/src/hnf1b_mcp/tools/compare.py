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
            "openWorldHint": False,
        },
    )
    async def hnf1b_compare_phenotypes(
        variant_ids: list[str],
        top_n: int = 25,
        response_mode: ResponseMode | None = None,
    ) -> dict[str, Any]:
        """Compare HPO phenotype frequencies across carriers of several variants.

        A genotype-phenotype analytical primitive: instead of fetching each
        variant's carriers and tallying HPO terms by hand, this returns per-HPO
        observed / excluded / unknown counts for each variant group in one call.

        Pass the canonical ``variant_id`` values (GA4GH VRS / CNV descriptor, as
        returned by ``hnf1b_search_variants`` / ``hnf1b_get_variant``). Up to 10
        variants per call.

        Args:
            variant_ids: 1–10 variant ids whose carrier cohorts to compare.
            top_n: Maximum distinct HPO features to return, ranked by total
                observed count across groups (default 25, max 100).
            response_mode: Response verbosity — one of ``minimal``,
                ``compact``, ``standard``, ``full``.  Defaults to ``compact``.

        Returns:
            A dict with ``groups`` (per-variant ``{variant_id, n}`` carrier
            counts), ``features`` (each ``{hpo_id, label, total_observed,
            by_group: {variant_id: {observed, excluded, unknown}}}``),
            ``total_distinct_features``, a ``note``, ``data_class``, and
            ``meta``.
        """
        return await run_tool(
            lambda: compare_service.compare_phenotypes(
                client,  # type: ignore[arg-type]
                variant_ids,
                top_n=top_n,
            ),
            data_class=DataClass.DERIVED,
            response_mode=resolve_mode(response_mode),
        )
