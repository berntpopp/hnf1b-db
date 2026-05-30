"""Service for hybrid passage retrieval over publication full text.

Calls the backend ``GET /publications/passages`` endpoint (lexical FTS fused
with optional pgvector semantic search) and shapes the ranked passages for an
LLM: stable ``passage_id`` citation anchors, the verbatim
``recommended_citation`` for each passage's publication (reusing the same
citation map as :mod:`hnf1b_mcp.services.publications`), response-mode trimming,
and the retrieval diagnostics surfaced via ``_meta``.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.config import Settings
from hnf1b_mcp.contract._generated_paths import PUBLICATIONS_PASSAGES
from hnf1b_mcp.services.errors import McpToolError
from hnf1b_mcp.services.publications import build_pmid_citation_map
from hnf1b_mcp.services.shaping import apply_budget

#: Text-shaping modes accepted by the backend endpoint.
API_MODES = ("brief", "full", "ids_only")
#: Rerank strategies accepted by the backend endpoint.
RERANK_MODES = ("rrf", "lexical", "off")

#: Snippet length requested from the backend, sized to the response mode.
_SNIPPET_BY_MODE: dict[str, int] = {
    "minimal": 160,
    "compact": 240,
    "standard": 360,
    "full": 600,
}


def _shape_passage(
    passage: dict[str, Any],
    response_mode: str,
    citation_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Shape one API passage hit into an output record.

    Args:
        passage: A passage object from the endpoint's ``passages`` list.
        response_mode: One of ``minimal``/``compact``/``standard``/``full``.
        citation_map: ``bare_pmid -> {recommended_citation, ...}`` lookup.

    Returns:
        A shaped passage dict carrying the ``passage_id`` citation anchor, the
        publication's ``recommended_citation``, and the relevance ``score``
        (emitted in every mode); ``standard``/``full`` add ``seq`` and
        ``source``.
    """
    pmid = str(passage.get("pmid") or "")
    bare = pmid.replace("PMID:", "")
    citation = citation_map.get(bare, {})

    shaped: dict[str, Any] = {
        "passage_id": passage.get("passage_id"),
        "pmid": pmid,
        "section": passage.get("section"),
        "recommended_citation": citation.get("recommended_citation"),
    }
    text = passage.get("text")
    snippet = passage.get("snippet")
    if text is not None:
        shaped["text"] = text
    if snippet is not None:
        shaped["snippet"] = snippet
    # Always visible: lets the caller judge relevance even in the default
    # compact mode (near-zero scores flag weak RAG hits).
    shaped["score"] = passage.get("score")
    if response_mode in ("standard", "full"):
        shaped["seq"] = passage.get("seq")
        shaped["source"] = passage.get("source")
    return shaped


async def get_publication_passages(
    client: ApiClient,
    *,
    query: str,
    pmids: Optional[Sequence[str]] = None,
    sections: Optional[Sequence[str]] = None,
    mode: str = "brief",
    rerank: str = "rrf",
    limit: int = 8,
    response_mode: str = "compact",
) -> dict[str, Any]:
    """Retrieve ranked publication passages for a free-text query.

    Args:
        client: The API client.
        query: Free-text search query.
        pmids: Optional PMID filter (prefixed or bare).
        sections: Optional canonical-section filter.
        mode: Text shaping — ``brief`` (snippet), ``full`` (passage text), or
            ``ids_only``.
        rerank: ``rrf`` (lexical + semantic when available), ``lexical``, or
            ``off``.
        limit: Maximum passages to return.
        response_mode: Token-budget / verbosity mode.

    Returns:
        A dict with ``query``, ``passages`` (shaped, with citations), ``total``,
        plus internal ``_meta`` diagnostics and an optional ``_dropped``
        truncation signal consumed by the tool wrapper.

    Raises:
        McpToolError: If ``mode`` or ``rerank`` is invalid.
    """
    if mode not in API_MODES:
        raise McpToolError(
            "invalid_input", f"mode must be one of {API_MODES}", argument="mode"
        )
    if rerank not in RERANK_MODES:
        raise McpToolError(
            "invalid_input", f"rerank must be one of {RERANK_MODES}", argument="rerank"
        )

    budget = Settings().mode_char_budgets.get(response_mode, 12000)
    params: dict[str, Any] = {
        "q": query,
        "rerank": rerank,
        "mode": mode,
        "limit": limit,
        "snippet_chars": _SNIPPET_BY_MODE.get(response_mode, 240),
        "max_chars": budget,
    }
    if pmids:
        params["pmids"] = ",".join(p.replace("PMID:", "") for p in pmids)
    if sections:
        params["sections"] = ",".join(sections)

    body: dict[str, Any] = await client.get(PUBLICATIONS_PASSAGES, params=params)
    raw_passages: list[dict[str, Any]] = body.get("passages") or []
    api_meta: dict[str, Any] = body.get("meta") or {}

    # Reuse the publication citation map so each passage cites the same verified
    # recommended_citation the list/individual tools report. Skip the lookup
    # entirely when there is nothing to cite.
    citation_map: dict[str, dict[str, Any]] = (
        await build_pmid_citation_map(client) if raw_passages else {}
    )
    passages = [_shape_passage(p, response_mode, citation_map) for p in raw_passages]

    result: dict[str, Any] = {
        "query": query,
        "passages": passages,
        "total": len(passages),
    }
    # keep_min=1: the backend guarantees a non-empty result when a match exists,
    # so never let client-side budget trimming pop the sole top-ranked passage to
    # an empty list (a single long full-text passage can exceed minimal's 4 KB).
    result, dropped = apply_budget(result, budget, ["passages"], keep_min=1)
    if dropped:
        result["_dropped"] = dropped
        result["total"] = len(result["passages"])
    result["_meta"] = {
        "rerank_used": api_meta.get("rerank_used"),
        "lexical_candidate_count": api_meta.get("lexical_candidate_count"),
        "dense_candidate_count": api_meta.get("dense_candidate_count"),
        "embedding_dim": api_meta.get("embedding_dim"),
        "retrieval_truncated": api_meta.get("truncated"),
    }
    return result
