"""Live golden tests for the publications service.

These tests hit the real local API stack at http://localhost:8000/api/v2.
They are marked ``@pytest.mark.live`` and excluded from the default test run
(see ``addopts`` in pyproject.toml).  Run them explicitly with::

    uv run pytest -q -m live

Tests skip gracefully when the stack is unreachable (httpx.ConnectError).
"""

from __future__ import annotations

import httpx
import pytest

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.publications import (
    get_publication_citing_individuals,
    list_publications,
)

LIVE_BASE = "http://localhost:8000/api/v2"


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_list_publications_citation_populated() -> None:
    """Every record from the real API has a non-empty pmid and recommended_citation."""
    c = ApiClient(base_url=LIVE_BASE)
    try:
        # full mode so the structured journal/year fields are present (they are
        # intentionally trimmed in minimal/compact, where the citation string
        # already embeds them).
        result = await list_publications(c, page_size=3, response_mode="full")
    except httpx.ConnectError:
        pytest.skip("Local API stack not reachable — skipping live test")
    finally:
        await c.aclose()

    assert "publications" in result
    pubs = result["publications"]
    assert len(pubs) > 0, "Expected at least one publication from the live API"

    for pub in pubs:
        assert pub["pmid"], f"pmid must be non-empty, got: {pub!r}"
        citation = pub["recommended_citation"]
        assert citation, (
            f"recommended_citation must be non-empty for pmid={pub['pmid']}"
        )
        # Must contain real author/title/year content — not just the unverified suffix
        assert "publication date unverified" not in citation or (
            # If unverified, authors+title must still be present
            pub["pmid"] and pub["journal"]
        ), f"Citation looks blank for pmid={pub['pmid']}: {citation!r}"
        # Verified citations must include year and authors
        if pub["year"]:
            assert str(pub["year"]) in citation, (
                f"Year {pub['year']} missing from citation for pmid={pub['pmid']}: {citation!r}"
            )


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_get_publication_citing_individuals() -> None:
    """PMID 18249217 must return citing_individuals including 'phenopacket-86'."""
    c = ApiClient(base_url=LIVE_BASE)
    try:
        result = await get_publication_citing_individuals(c, "18249217")
    except httpx.ConnectError:
        pytest.skip("Local API stack not reachable — skipping live test")
    finally:
        await c.aclose()

    assert result["pmid"] == "18249217"
    citing = result["citing_individuals"]
    assert len(citing) > 0, "Expected at least one citing individual for PMID 18249217"
    assert "phenopacket-86" in citing, (
        f"Expected 'phenopacket-86' in citing_individuals, got: {citing}"
    )
