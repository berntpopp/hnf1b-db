"""MCP tool: hnf1b_search — unified discovery search over HNF1B-db entities."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services import search as search_service
from hnf1b_mcp.services.dataclass import DataClass
from hnf1b_mcp.services.safe_tool import run_tool
from hnf1b_mcp.services.shaping import ResponseMode, resolve_mode


def register(mcp: FastMCP, client: ApiClient | None) -> None:
    """Register the hnf1b_search tool on *mcp*.

    Args:
        mcp: The :class:`~fastmcp.FastMCP` application instance.
        client: The :class:`~hnf1b_mcp.client.api_client.ApiClient` used to
            communicate with the HNF1B-db REST API, or *None* during
            registration-only scenarios (e.g. capability introspection).
    """

    @mcp.tool(
        name="hnf1b_search",
        annotations={
            "title": "Search HNF1B-db (Discovery)",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def hnf1b_search(
        query: str,
        types: list[str] | None = None,
        limit: int = 10,
        response_mode: ResponseMode | None = None,
    ) -> dict[str, Any]:
        """Unified discovery search — returns typed ID hits.

        Searches across individuals, variants, and publications in HNF1B-db
        and returns a list of typed ID hits only.  Use the typed
        ``hnf1b_get_individual``, ``hnf1b_get_variant``, or
        ``hnf1b_get_publications`` tools to fetch authoritative content for any
        returned ID.

        Args:
            query: Free-text search string.  Must be non-empty.
            types: Entity types to include.  Allowed values are
                ``individual``, ``variant``, ``publication``, ``gene``.
                Defaults to ``["individual", "variant", "publication"]``.
            limit: Maximum number of results to return (≥ 1).  Defaults to 10.
            response_mode: Response verbosity — one of ``minimal``,
                ``compact``, ``standard``, ``full``.  Defaults to ``compact``.

        Returns:
            A dict with keys ``query``, ``hits``, ``counts``, ``guidance``,
            ``data_class``, and ``meta``.  Each hit contains ``type``, ``id``,
            ``label``, ``uri``, and a numeric ``score`` (relevance, higher =
            better) when the backend supplied one.
        """
        resolved_types: tuple[str, ...] = (
            tuple(types) if types else ("individual", "variant", "publication")
        )
        return await run_tool(
            lambda: search_service.search(
                client,  # type: ignore[arg-type]
                query,
                types=resolved_types,
                limit=limit,
            ),
            data_class=DataClass.OPERATIONAL,
            response_mode=resolve_mode(response_mode),
        )
