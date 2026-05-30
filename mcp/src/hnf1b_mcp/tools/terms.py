"""MCP tool: hnf1b_resolve_terms — ontology and controlled-vocabulary resolution."""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services import terms as terms_service
from hnf1b_mcp.services.dataclass import DataClass
from hnf1b_mcp.services.safe_tool import run_tool
from hnf1b_mcp.services.shaping import resolve_mode


def register(mcp: FastMCP, client: ApiClient | None) -> None:
    """Register the hnf1b_resolve_terms tool on *mcp*.

    Args:
        mcp: The :class:`~fastmcp.FastMCP` application instance.
        client: The :class:`~hnf1b_mcp.client.api_client.ApiClient` used to
            communicate with the HNF1B-db REST API, or *None* during
            registration-only scenarios (e.g. capability introspection).
    """

    @mcp.tool(
        name="hnf1b_resolve_terms",
        annotations={
            "title": "Resolve HPO / Vocabulary Terms",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def hnf1b_resolve_terms(
        text: str,
        vocabulary: Literal[
            "hpo",
            "sex",
            "interpretation-status",
            "progress-status",
            "allelic-state",
            "evidence-code",
        ] = "hpo",
        limit: int = 10,
        response_mode: str | None = None,
    ) -> dict[str, Any]:
        """Resolve ontology or controlled-vocabulary terms against the HNF1B-db API.

        Look up HPO phenotype terms or controlled-vocabulary values used by
        HNF1B-db.  For HPO, performs a free-text autocomplete search returning
        matching HPO identifiers with labels and descriptions.  For named
        controlled vocabularies (sex, interpretation-status, progress-status,
        allelic-state, evidence-code), retrieves the full vocabulary list and
        optionally filters by *text* (case-insensitive substring match),
        returning at most *limit* entries.

        Use this tool to:
        - Find the correct ``HP:XXXXXXX`` term ID before submitting phenotype
          queries.
        - Enumerate allowed values for structured annotation fields
          (e.g. sex, allelic state).

        Args:
            text: Free-text query string.  May be empty for controlled
                vocabularies to retrieve the full list.
            vocabulary: Vocabulary to search.  One of ``"hpo"``, ``"sex"``,
                ``"interpretation-status"``, ``"progress-status"``,
                ``"allelic-state"``, ``"evidence-code"``.  Defaults to
                ``"hpo"``.
            limit: Maximum number of matches to return (≥ 1).  Defaults to 10.
                A value below 1 returns an ``invalid_input`` error.
            response_mode: Response verbosity — one of ``minimal``, ``compact``,
                ``standard``, ``full``.  Defaults to ``compact``.

        Returns:
            A dict with keys ``query``, ``vocabulary``, ``matches``,
            ``data_class``, and ``meta``.  Each match contains ``id``,
            ``label``, and ``description``; HPO matches additionally carry a
            numeric ``score`` (relevance, higher = better) when the backend
            supplied one.  For a controlled vocabulary capped by ``limit``,
            ``meta`` carries ``total_matches``/``returned`` so the truncation is
            never silent.
        """
        return await run_tool(
            lambda: terms_service.resolve_terms(
                client,  # type: ignore[arg-type]
                text,
                vocabulary=vocabulary,
                limit=limit,
            ),
            data_class=DataClass.EXTERNAL_REF,
            response_mode=resolve_mode(response_mode),
        )
