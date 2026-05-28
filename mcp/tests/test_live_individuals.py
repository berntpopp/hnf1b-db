"""Live golden tests for services/individuals.py against the real API.

These tests require a running HNF1B-db API at http://localhost:8000/api/v2 and
are excluded from default CI via ``addopts = "-m 'not live'"`` in pyproject.toml.

Run explicitly with::

    uv run pytest -q -m live tests/test_live_individuals.py
"""

from __future__ import annotations

import pytest

try:
    import httpx as _httpx  # noqa: F401 — just to confirm the dep is present
except ImportError:
    pass

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.individuals import get_individual, get_individuals

LIVE_BASE = "http://localhost:8000/api/v2"


@pytest.fixture
async def live_client():
    """Yield a real ApiClient; skip if localhost:8000 is unreachable."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as probe:
            await probe.get(f"{LIVE_BASE}/phenopackets/", params={"page[size]": 1})
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        pytest.skip(f"Live API not reachable at {LIVE_BASE}: {exc}")

    client = ApiClient(base_url=LIVE_BASE)
    yield client
    await client.aclose()


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_list_individuals_non_empty_ids(live_client: ApiClient) -> None:
    """(a) List individuals — every returned record must have a non-empty phenopacket_id."""
    result = await get_individuals(live_client, page_size=5)

    assert isinstance(result["individuals"], list)
    assert len(result["individuals"]) > 0, (
        "Expected at least one individual in the list"
    )

    for ind in result["individuals"]:
        assert ind.get("phenopacket_id"), f"Record missing phenopacket_id: {ind!r}"
        assert ind["uri"] == f"hnf1b://individual/{ind['phenopacket_id']}", (
            f"URI mismatch for {ind['phenopacket_id']!r}: {ind['uri']!r}"
        )


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_batch_by_id_non_empty(live_client: ApiClient) -> None:
    """(b) Batch fetch by id — must return a record with non-empty id (no crash)."""
    # First discover one id from the list endpoint
    list_result = await get_individuals(live_client, page_size=3)
    individuals = list_result["individuals"]
    assert individuals, "No individuals returned by list endpoint; cannot proceed"

    sample_id: str = individuals[0]["phenopacket_id"]
    assert sample_id, "First list record has empty phenopacket_id"

    # Now batch-fetch that single id
    batch_result = await get_individuals(live_client, ids=[sample_id])

    assert batch_result["total"] >= 1, (
        f"Batch for {sample_id!r} returned total={batch_result['total']}"
    )
    assert len(batch_result["individuals"]) >= 1

    fetched = batch_result["individuals"][0]
    assert fetched.get("phenopacket_id") == sample_id, (
        f"Expected phenopacket_id={sample_id!r}, got {fetched.get('phenopacket_id')!r}"
    )
    assert fetched["uri"] == f"hnf1b://individual/{sample_id}"


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_get_individual_has_subject(live_client: ApiClient) -> None:
    """(c) get_individual — must return a record with a non-empty subject."""
    # Discover one id first
    list_result = await get_individuals(live_client, page_size=3)
    individuals = list_result["individuals"]
    assert individuals, "No individuals returned by list endpoint; cannot proceed"

    sample_id: str = individuals[0]["phenopacket_id"]

    individual = await get_individual(live_client, sample_id)

    assert individual.get("phenopacket_id") == sample_id
    assert individual.get("subject"), (
        f"get_individual({sample_id!r}) returned empty subject: {individual!r}"
    )
