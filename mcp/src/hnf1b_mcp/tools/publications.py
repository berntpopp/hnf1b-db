"""MCP tool: hnf1b_get_publications — publications list and reverse lookup."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services import publications as publications_service
from hnf1b_mcp.services.dataclass import DataClass
from hnf1b_mcp.services.safe_tool import run_tool
from hnf1b_mcp.services.shaping import resolve_mode


def register(mcp: FastMCP, client: ApiClient | None) -> None:
    """Register the hnf1b_get_publications tool on *mcp*.

    Args:
        mcp: The :class:`~fastmcp.FastMCP` application instance.
        client: The :class:`~hnf1b_mcp.client.api_client.ApiClient` used to
            communicate with the HNF1B-db REST API, or *None* during
            registration-only scenarios (e.g. capability introspection).
    """

    @mcp.tool(
        name="hnf1b_get_publications",
        annotations={
            "title": "Get HNF1B Publications",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def hnf1b_get_publications(
        q: str | None = None,
        year: int | None = None,
        has_doi: bool | None = None,
        page_size: int = 25,
        sort: str | None = None,
        citing_pmid: str | None = None,
        include_citing_individuals: bool = False,
        response_mode: str | None = None,
    ) -> dict[str, Any]:
        """Browse and search the local HNF1B publication cache.

        Returns paginated publications from the HNF1B-db local cache, or
        performs a reverse lookup to discover which individuals (phenopackets)
        cite a given publication.

        Set ``citing_pmid`` for reverse lookup — all other filters are ignored
        when that parameter is supplied.  Without ``citing_pmid``, use ``q``,
        ``year``, ``has_doi``, and ``page_size`` to filter/paginate the
        publication list.

        This tool NEVER calls the live PubMed metadata endpoint; it reads
        only the local DB cache.

        Args:
            q: Free-text search query forwarded to the list endpoint.
            year: Filter publications to this exact calendar year.
            has_doi: When ``True``, return only publications with a DOI;
                when ``False``, return only those without.  ``None`` disables
                the filter.
            page_size: Number of publications per page (default 25, max 1000).
            sort: Optional ordering — a field name optionally ``-``-prefixed for
                descending. Allowed: ``phenopacket_count`` (default,
                most-cited first), ``year``, ``pmid``, ``title``, ``journal``,
                ``first_added``. The applied ordering is echoed as
                ``applied_sort``.
            citing_pmid: Bare PMID (digits) or ``"PMID:NNN"`` prefixed string.
                When provided, performs a reverse lookup — returns the list of
                phenopacket IDs that cite this publication.
            include_citing_individuals: Only meaningful with ``citing_pmid``.
                When ``False`` (default) the ``citing_individuals`` list is
                summarized to the first 10 ids in EVERY mode (``total`` stays the
                true count); when the full set is larger, meta carries
                ``citing_individuals_total`` / ``citing_individuals_returned`` /
                ``citing_individuals_truncated`` / ``citing_individuals_note``.
                Set ``True`` for the full list (still bounded by the response-mode
                char budget, with the truncation signal in every mode); pass the
                ids to ``hnf1b_get_individuals``, or use
                ``hnf1b_find_individuals_by_phenotype`` for the matched cohort.
            response_mode: Response verbosity — one of ``minimal``,
                ``compact``, ``standard``, ``full``.  Defaults to ``compact``.
                In ``minimal``/``compact`` the redundant ``journal``/``year``/
                ``date_confidence`` fields (already inside
                ``recommended_citation``) and the large ``abstract`` are omitted;
                ``standard``/``full`` include them. The mode's char budget is
                enforced on the list (with a ``meta.truncated`` signal), so a
                page never exceeds the budget.

        Returns:
            When ``citing_pmid`` is given: a dict with keys ``pmid``,
            ``citing_individuals`` (a bounded sample of phenopacket ID strings
            unless ``include_citing_individuals=True``), ``total`` (the true
            citing count), ``data_class``, and ``meta`` (carrying the
            ``citing_individuals_*`` truncation signals when the full set
            exceeds the sample).

            Otherwise: a dict with keys ``publications`` (shaped records with
            ``pmid``, ``recommended_citation``, ``phenopacket_count``, ``uri``,
            and the ``coverage``/``has_full_text`` full-text flags in every
            mode, plus ``journal``/``year``/``date_confidence`` and the full
            ``abstract`` in standard/full), ``total``, ``page``, ``page_size``,
            ``applied_sort``, ``data_class``, and ``meta``.
        """
        mode = resolve_mode(response_mode)

        async def handler() -> dict[str, Any]:
            if citing_pmid is not None:
                return await publications_service.get_publication_citing_individuals(
                    client,  # type: ignore[arg-type]
                    citing_pmid,
                    response_mode=mode,
                    include_citing_individuals=include_citing_individuals,
                )
            filters: dict[str, Any] = {}
            if year is not None:
                filters["year"] = year
            if has_doi is not None:
                filters["has_doi"] = has_doi
            return await publications_service.list_publications(
                client,  # type: ignore[arg-type]
                q=q,
                filters=filters or None,
                page_size=page_size,
                sort=sort,
                response_mode=mode,
            )

        return await run_tool(
            handler,
            data_class=DataClass.CURATED,
            response_mode=mode,
        )
