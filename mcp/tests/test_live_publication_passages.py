"""Live golden test for hnf1b_get_publication_passages against a running stack.

Marked ``live`` and excluded from CI (``addopts = -m 'not live'``); run with
``uv run pytest -m live`` against a backend with the publication full-text
backfill applied. Skips cleanly when the local stack is unreachable.
"""

from __future__ import annotations

import httpx
import pytest

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.publication_passages import get_publication_passages

LIVE_BASE = "http://localhost:8000/api/v2"


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_passage_search_returns_cited_hits() -> None:
    """A passage query returns ranked hits, each with a passage_id + citation."""
    client = ApiClient(base_url=LIVE_BASE)
    try:
        result = await get_publication_passages(
            client,
            query="cystic kidney disease",
            mode="brief",
            rerank="rrf",
            limit=5,
            response_mode="full",
        )
    except httpx.ConnectError:
        pytest.skip("Local API stack not reachable — skipping live test")
    finally:
        await client.aclose()

    assert "passages" in result
    assert result["_meta"]["rerank_used"] in {"rrf", "lexical", "off"}
    # If the backfill has run there should be ranked, citable hits.
    for passage in result["passages"]:
        assert passage["passage_id"]
        assert passage["pmid"].startswith("PMID:")
        assert "recommended_citation" in passage
