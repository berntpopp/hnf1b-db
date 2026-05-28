"""Live golden tests against the local HNF1B-db API (http://localhost:8000).

Run with ``uv run pytest -q -m live``.  Skipped gracefully when the API is
unreachable so the default test run stays green.
"""

from __future__ import annotations

import httpx
import pytest

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.variants import get_variant, search_variants

LIVE_BASE = "http://localhost:8000/api/v2"

pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_live_search_classification_total():
    """search_variants(classification=PATHOGENIC) has a real, non-zero total."""
    client = ApiClient(base_url=LIVE_BASE)
    try:
        result = await search_variants(
            client, classification="PATHOGENIC", response_mode="standard"
        )
    except httpx.ConnectError:
        pytest.skip("live API not reachable at localhost:8000")
    finally:
        await client.aclose()

    total = result["total"]
    assert total > 0
    # 41 PATHOGENIC records at time of writing; tolerate a single-page result.
    rows = result["variants"]
    if total <= result["page_size"]:
        assert total == len(rows)
    else:
        assert total == 41 or total >= len(rows)


@pytest.mark.asyncio
async def test_live_get_variant_authoritative():
    """get_variant returns non-null classification, consequence, and carriers."""
    client = ApiClient(base_url=LIVE_BASE)
    try:
        listing = await search_variants(
            client, classification="PATHOGENIC", response_mode="standard"
        )
        variant_id = listing["variants"][0]["variant_id"]
        record = await get_variant(client, variant_id)
    except httpx.ConnectError:
        pytest.skip("live API not reachable at localhost:8000")
    finally:
        await client.aclose()

    assert record["variant_id"] == variant_id
    assert record["classification"] is not None
    assert record["consequence"] is not None
    assert isinstance(record["carriers"], list)
    assert len(record["carriers"]) > 0


@pytest.mark.asyncio
async def test_live_consequence_post_filter():
    """search_variants(consequence=Missense) returns only Missense rows."""
    client = ApiClient(base_url=LIVE_BASE)
    try:
        result = await search_variants(
            client, consequence="Missense", response_mode="standard"
        )
    except httpx.ConnectError:
        pytest.skip("live API not reachable at localhost:8000")
    finally:
        await client.aclose()

    rows = result["variants"]
    assert len(rows) > 0
    for row in rows:
        assert row["consequence"] == "Missense"
    assert result["filtered_count"] == len(rows)
