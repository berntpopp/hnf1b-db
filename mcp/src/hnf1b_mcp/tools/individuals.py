"""MCP tools for retrieving HNF1B-db individual phenopacket records."""
from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services import individuals as individuals_service
from hnf1b_mcp.services.dataclass import DataClass
from hnf1b_mcp.services.safe_tool import run_tool
from hnf1b_mcp.services.shaping import resolve_mode


def register(mcp: FastMCP, client: ApiClient | None) -> None:
    """Register individual phenopacket retrieval and cohort-discovery tools on *mcp*.

    Args:
        mcp: The :class:`~fastmcp.FastMCP` application instance.
        client: The :class:`~hnf1b_mcp.client.api_client.ApiClient` used to
            communicate with the HNF1B-db REST API, or *None* during
            registration-only scenarios (e.g. capability introspection).
    """

    @mcp.tool(
        name="hnf1b_get_individual",
        annotations={"readOnlyHint": True, "openWorldHint": False},
    )
    async def hnf1b_get_individual(
        phenopacket_id: str,
        include_phenotypes: bool = True,
        include_variants: bool = True,
        include_measurements: bool = True,
        include_publications: bool = True,
        response_mode: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve the full phenopacket record for a single individual.

        Fetches by phenopacket_id.

        Fetches authoritative curated data for one HNF1B-db individual from the
        ``/phenopackets/{phenopacket_id}`` endpoint and returns a compact shaped
        record.  Use ``hnf1b_get_individuals`` to retrieve multiple records in a
        single call, or ``hnf1b_find_individuals_by_phenotype`` to discover
        individuals sharing a given HPO phenotype.

        Args:
            phenopacket_id: The phenopacket identifier to look up.
            include_phenotypes: Include the ``phenotypic_features`` list in the
                response.  Defaults to ``True``.
            include_variants: Include the ``variants`` list extracted from
                genomic interpretations.  Defaults to ``True``.
            include_measurements: Include the ``measurements`` list.  Defaults
                to ``True``.
            include_publications: Include the ``publications`` list extracted
                from ``metaData.externalReferences`` (PMID entries only).
                Defaults to ``True``.
            response_mode: Response verbosity — one of ``minimal``,
                ``compact``, ``standard``, ``full``.  Defaults to ``compact``.

        Returns:
            A dict with keys ``phenopacket_id``, ``subject``, ``diseases``,
            ``uri``, and conditionally ``phenotypic_features``, ``variants``,
            ``measurements``, ``publications``, plus ``data_class`` and
            ``meta``.
        """
        return await run_tool(
            lambda: individuals_service.get_individual(
                client,  # type: ignore[arg-type]
                phenopacket_id,
                include_phenotypes=include_phenotypes,
                include_variants=include_variants,
                include_measurements=include_measurements,
                include_publications=include_publications,
            ),
            data_class=DataClass.CURATED,
            response_mode=resolve_mode(response_mode),
        )

    @mcp.tool(
        name="hnf1b_get_individuals",
        annotations={"readOnlyHint": True, "openWorldHint": False},
    )
    async def hnf1b_get_individuals(
        ids: list[str] | None = None,
        sex: str | None = None,
        has_variants: bool | None = None,
        page_size: int = 25,
        expand: bool = False,
        dedupe_publications: bool = False,
        response_mode: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve a list of HNF1B-db individuals by IDs or with optional filters.

        When ``ids`` is provided the batch endpoint is used for efficient
        multi-record retrieval.  Otherwise the discovery list endpoint is
        queried and each individual is optionally fetched in full when
        ``expand=True``.  Use ``hnf1b_find_individuals_by_phenotype`` to first
        discover individuals sharing a given HPO term before fetching them.

        Args:
            ids: Optional list of phenopacket IDs for batch retrieval.  When
                supplied, ``sex`` and ``has_variants`` filters are ignored.
            sex: Filter by biological sex — e.g. ``"MALE"`` or ``"FEMALE"``.
                Applied only when ``ids`` is not provided.
            has_variants: Filter to individuals with (``True``) or without
                (``False``) recorded variants.  Applied only when ``ids`` is
                not provided.
            page_size: Maximum number of results per page (discovery endpoint
                only).  Defaults to 25.
            expand: When ``True`` and using the discovery endpoint, fetch each
                individual record in full rather than returning minimal stubs.
                Defaults to ``False``.
            dedupe_publications: Hoist unique publications to a top-level
                ``publications`` list and replace per-record publications with
                ``publication_refs`` (PMID strings).  Defaults to ``False``.
            response_mode: Response verbosity — one of ``minimal``,
                ``compact``, ``standard``, ``full``.  Defaults to ``compact``.

        Returns:
            A dict with keys ``individuals``, ``total``, ``page_size``, and
            optionally ``publications`` (when ``dedupe_publications=True``),
            plus ``data_class`` and ``meta``.
        """
        filters: dict[str, Any] = {}
        if sex is not None:
            filters["sex"] = sex
        if has_variants is not None:
            filters["has_variants"] = has_variants

        return await run_tool(
            lambda: individuals_service.get_individuals(
                client,  # type: ignore[arg-type]
                ids=ids,
                filters=filters or None,
                page_size=page_size,
                expand=expand,
                dedupe_publications=dedupe_publications,
            ),
            data_class=DataClass.CURATED,
            response_mode=resolve_mode(response_mode),
        )

    @mcp.tool(
        name="hnf1b_find_individuals_by_phenotype",
        annotations={"readOnlyHint": True, "openWorldHint": False},
    )
    async def hnf1b_find_individuals_by_phenotype(
        hpo_ids: list[str],
        page_size: int = 25,
        response_mode: str | None = None,
    ) -> dict[str, Any]:
        """Cohort discovery: find individuals sharing one or more HPO phenotype terms.

        Queries the ``/phenopackets/search`` discovery endpoint for each
        supplied HPO term ID, collects and deduplicates the matching phenopacket
        IDs while preserving order, then fetches authoritative content for the
        merged cohort via the batch endpoint.  Suitable for building HPO-matched
        cohorts for downstream analysis.

        Args:
            hpo_ids: One or more HPO term IDs (e.g. ``["HP:0000083",
                "HP:0000107"]``).  Results are the union of all matching
                individuals across all supplied terms.
            page_size: Maximum number of individuals to return in the final
                result.  Defaults to 25.
            response_mode: Response verbosity — one of ``minimal``,
                ``compact``, ``standard``, ``full``.  Defaults to ``compact``.

        Returns:
            A dict with keys ``individuals``, ``total``, ``page_size``,
            ``data_class``, and ``meta``.
        """
        resolved = resolve_mode(response_mode)

        async def handler() -> dict[str, Any]:
            seen: dict[str, None] = {}
            for hpo_id in hpo_ids:
                resp: dict[str, Any] = await client.get(  # type: ignore[union-attr]
                    "/phenopackets/search",
                    params={"hpo_id": hpo_id},
                )
                for item in resp.get("data", []):
                    item_id: str = item.get("id", "")
                    if item_id and item_id not in seen:
                        seen[item_id] = None
            merged_ids = list(seen.keys())
            return await individuals_service.get_individuals(
                client,  # type: ignore[arg-type]
                ids=merged_ids[:page_size] if merged_ids else None,
                page_size=page_size,
            )

        return await run_tool(
            handler,
            data_class=DataClass.CURATED,
            response_mode=resolved,
        )
