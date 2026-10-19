"""Tests for clinical feature-specific endpoints and pagination [PERF-04]."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

CLINICAL_ENDPOINTS = [
    "/api/v2/clinical/renal-insufficiency",
    "/api/v2/clinical/genital-abnormalities",
    "/api/v2/clinical/diabetes",
    "/api/v2/clinical/hypomagnesemia",
    "/api/v2/clinical/pancreatic-abnormalities",
    "/api/v2/clinical/liver-abnormalities",
    "/api/v2/clinical/kidney-morphology",
    "/api/v2/clinical/multisystem-involvement",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", CLINICAL_ENDPOINTS)
async def test_clinical_endpoints_accept_limit_and_offset(
    async_client: AsyncClient, endpoint: str
) -> None:
    """All 8 clinical endpoints accept limit and offset query parameters."""
    response = await async_client.get(endpoint, params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_clinical_endpoints_reject_invalid_limit(
    async_client: AsyncClient,
) -> None:
    """Clinical endpoints reject limit > 500 with HTTP 422."""
    response = await async_client.get(
        "/api/v2/clinical/renal-insufficiency", params={"limit": 1000}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_by_variant_accepts_limit_and_offset(
    async_client: AsyncClient,
) -> None:
    """GET /api/v2/phenopackets/by-variant/{variant_id} accepts limit and offset."""
    response = await async_client.get(
        "/api/v2/phenopackets/by-variant/var-test-123",
        params={"limit": 10, "offset": 0},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_genes_reference_accepts_limit_and_offset(
    async_client: AsyncClient,
    db_session,
) -> None:
    """GET /api/v2/reference/genes accepts limit and offset parameters."""
    from app.reference.service import initialize_reference_data

    await initialize_reference_data(db_session)
    response = await async_client.get(
        "/api/v2/reference/genes",
        params={"limit": 10, "offset": 0},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
