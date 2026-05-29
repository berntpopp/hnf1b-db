"""MCP tool: hnf1b_get_publication_passages — RAG retrieval over full text."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services import publication_passages as passages_service
from hnf1b_mcp.services.dataclass import DataClass
from hnf1b_mcp.services.safe_tool import run_tool
from hnf1b_mcp.services.shaping import resolve_mode


def register(mcp: FastMCP, client: ApiClient | None) -> None:
    """Register the hnf1b_get_publication_passages tool on *mcp*.

    Args:
        mcp: The :class:`~fastmcp.FastMCP` application instance.
        client: The :class:`~hnf1b_mcp.client.api_client.ApiClient`, or *None*
            during registration-only scenarios (e.g. capability introspection).
    """

    @mcp.tool(
        name="hnf1b_get_publication_passages",
        annotations={"readOnlyHint": True, "openWorldHint": False},
    )
    async def hnf1b_get_publication_passages(
        query: str,
        pmids: list[str] | None = None,
        sections: list[str] | None = None,
        mode: str = "brief",
        rerank: str = "rrf",
        limit: int = 8,
        response_mode: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve ranked passages from publication full text for a query (RAG).

        Searches stored, license-gated open-access passages with hybrid
        retrieval: PostgreSQL full-text search (always) fused with optional
        semantic (pgvector) search via Reciprocal Rank Fusion. Returns the
        most relevant passages, each with a stable ``passage_id`` and the
        publication's verbatim ``recommended_citation``.

        Use this to ground answers in the actual text of HNF1B publications
        (abstracts + open-access body sections). For citation metadata or
        reverse "who cites this PMID" lookups, use ``hnf1b_get_publications``.

        Args:
            query: Free-text search query (required).
            pmids: Optional list of PMIDs (``"PMID:NNN"`` or bare digits) to
                restrict the search to specific publications.
            sections: Optional list of canonical sections to restrict to
                (``title``, ``abstract``, ``intro``, ``methods``, ``results``,
                ``discussion``, ``conclusion``, ``table``).
            mode: Text shaping — ``brief`` (highlighted snippet, default),
                ``full`` (full passage text), or ``ids_only`` (citation anchors
                only).
            rerank: ``rrf`` (lexical + semantic when embeddings exist; falls
                back to lexical otherwise), ``lexical``, or ``off``.
            limit: Maximum passages to return (default 8).
            response_mode: Token budget / verbosity — one of ``minimal``,
                ``compact`` (default), ``standard``, ``full``.
                ``standard``/``full`` also include per-passage ``score``,
                ``seq``, and ``source``.

        Returns:
            A dict with ``query``, ``passages`` (each with ``passage_id``,
            ``pmid``, ``section``, ``recommended_citation``, and text/snippet),
            ``total``, ``data_class``, and ``meta`` (including ``rerank_used``,
            ``lexical_candidate_count``, ``dense_candidate_count``,
            ``embedding_dim``).
        """
        rmode = resolve_mode(response_mode)

        async def handler() -> dict[str, Any]:
            return await passages_service.get_publication_passages(
                client,  # type: ignore[arg-type]
                query=query,
                pmids=pmids,
                sections=sections,
                mode=mode,
                rerank=rerank,
                limit=limit,
                response_mode=rmode,
            )

        return await run_tool(
            handler,
            data_class=DataClass.CURATED,
            response_mode=rmode,
        )
