"""Live golden tests for resolve_terms against http://localhost:8000/api/v2.

Run with:
    uv run pytest -q -m live tests/test_live_terms.py

These tests are excluded from the default ``uv run pytest`` run (no ``-m live``
flag) so that CI stays green without a running API server.
"""

from __future__ import annotations

import httpx
import pytest

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.terms import resolve_terms

LIVE_BASE_URL = "http://localhost:8000/api/v2"


@pytest.fixture
async def live_client():
    """Yield an ApiClient pointed at the local dev API; close after test."""
    client = ApiClient(base_url=LIVE_BASE_URL)
    yield client
    await client.aclose()


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_hpo_renal_returns_hp_matches(live_client: ApiClient) -> None:
    """HPO autocomplete for 'renal' returns at least one HP: term."""
    try:
        result = await resolve_terms(live_client, "renal", vocabulary="hpo")
    except httpx.ConnectError:
        pytest.skip("Live API not reachable at http://localhost:8000")

    matches = result["matches"]
    assert len(matches) > 0, "Expected at least one HPO match for 'renal'"
    hp_ids = [m["id"] for m in matches if m["id"].startswith("HP:")]
    assert len(hp_ids) > 0, (
        f"Expected at least one HP: id, got ids: {[m['id'] for m in matches]}"
    )
    # HP:0000107 (Renal cyst) is a well-known hit for 'renal'
    labels_lower = {m["label"].lower() for m in matches}
    assert any("renal" in lbl for lbl in labels_lower), (
        f"Expected a label containing 'renal', got: {labels_lower}"
    )


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_allelic_state_returns_geno_matches(live_client: ApiClient) -> None:
    """Allelic-state controlled vocab returns GENO: ids."""
    try:
        result = await resolve_terms(live_client, "", vocabulary="allelic-state")
    except httpx.ConnectError:
        pytest.skip("Live API not reachable at http://localhost:8000")

    matches = result["matches"]
    assert len(matches) > 0, "Expected at least one allelic-state entry"
    geno_ids = [m["id"] for m in matches if m["id"].startswith("GENO:")]
    assert len(geno_ids) > 0, (
        f"Expected at least one GENO: id, got ids: {[m['id'] for m in matches]}"
    )
