"""MCP tool: hnf1b_get_statistics — aggregate statistics over HNF1B phenopackets."""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services import statistics as statistics_service
from hnf1b_mcp.services.dataclass import DataClass
from hnf1b_mcp.services.safe_tool import run_tool
from hnf1b_mcp.services.shaping import ResponseMode, resolve_mode


def register(mcp: FastMCP, client: ApiClient | None) -> None:
    """Register the hnf1b_get_statistics tool on *mcp*.

    Args:
        mcp: The :class:`~fastmcp.FastMCP` application instance.
        client: The :class:`~hnf1b_mcp.client.api_client.ApiClient` used to
            communicate with the HNF1B-db REST API, or *None* during
            registration-only scenarios (e.g. capability introspection).
    """

    @mcp.tool(
        name="hnf1b_get_statistics",
        annotations={
            "title": "Get HNF1B Cohort Statistics",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def hnf1b_get_statistics(
        metric: Literal[
            "summary",
            "sex_distribution",
            "age_of_onset",
            "by_disease",
            "kidney_stages",
            "by_feature",
            "variant_pathogenicity",
            "variant_types",
            "survival",
            "publications_timeline",
        ],
        comparison: Literal[
            "variant_type",
            "pathogenicity",
            "disease_subtype",
            "protein_domain",
        ]
        | None = None,
        count_mode: Literal["all", "unique"] | None = None,
        dry_run: bool = False,
        response_mode: ResponseMode | None = None,
        max_response_chars: int | None = None,
    ) -> dict[str, Any]:
        """Fetch aggregate statistics for the HNF1B phenopacket cohort.

        Returns pre-computed aggregate statistics over the entire HNF1B-db
        phenopacket cohort.  Choose a *metric* to select the statistic; for
        ``survival`` also supply a *comparison* grouping variable.

        Available metrics:

        - ``summary`` — cohort-level counts and completeness overview.
        - ``sex_distribution`` — breakdown of sex across all individuals.
        - ``age_of_onset`` — distribution of renal age-of-onset bins.
        - ``by_disease`` — case counts grouped by disease category.
        - ``kidney_stages`` — distribution of CKD/ESRD staging.
        - ``by_feature`` — HPO feature prevalence across the cohort.
        - ``variant_pathogenicity`` — pathogenicity class distribution.
        - ``variant_types`` — variant type (missense, frameshift, …) counts.
        - ``survival`` — Kaplan-Meier–style renal-survival data; requires
          *comparison* to be one of ``variant_type``, ``pathogenicity``,
          ``disease_subtype``, or ``protein_domain``.
        - ``publications_timeline`` — publications per year timeline. Each row
          carries a ``publication_count`` (the inline PMID list is bounded out
          for token efficiency); use ``hnf1b_get_publications(year=…)`` to list
          the PMIDs for a year.

        Args:
            metric: The aggregate statistic to retrieve.
            comparison: Required when *metric* is ``"survival"``; selects the
                grouping variable for survival curves.  Must be one of
                ``variant_type``, ``pathogenicity``, ``disease_subtype``,
                ``protein_domain``.
            count_mode: For ``variant_types``/``variant_pathogenicity`` only —
                ``"all"`` (default) counts per-carrier variant instances;
                ``"unique"`` counts distinct variants. The returned ``unit``
                field states which was used.
            dry_run: When ``True`` skip the HTTP fetch and return a lightweight
                availability/size estimate dict (no API call is made).
            response_mode: Budget tier — ``"minimal"``, ``"compact"``
                (default), ``"standard"``, or ``"full"``.
            max_response_chars: Hard character-budget override (≤ 80 000).

        Returns:
            A dict with ``metric``, ``result`` (shaped upstream payload),
            ``data_class``, and ``meta``.  On *dry_run* returns ``metric``,
            ``available``, and ``estimated`` instead.  A ``_dropped`` key is
            added when the payload was trimmed.
        """
        return await run_tool(
            lambda: statistics_service.get_statistics(
                client,  # type: ignore[arg-type]
                metric,
                response_mode=resolve_mode(response_mode),
                max_response_chars=max_response_chars,
                dry_run=dry_run,
                comparison=comparison,
                count_mode=count_mode,
            ),
            data_class=DataClass.DERIVED,
            response_mode=resolve_mode(response_mode),
        )
