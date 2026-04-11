"""Smoke tests for the /survival-data endpoint.

Exercises the live SurvivalHandlerFactory dispatch path for every
supported comparison × endpoint combination. On an empty test
database, the ``groups`` list will be empty, but the response shape,
imports, factory wiring, and SQL generation are all exercised. This
is the regression safety net for Wave 3's deletion of the legacy
_handle_* functions in survival.py.

This module does NOT assert numeric survival curves — for that, see
the pure-function tests in test_survival_analysis.py.

Uses the ``async_client`` fixture from conftest.py (not ``client``,
which is a local synchronous TestClient fixture inside
test_phenopackets_crud.py with a deliberate collision-avoidance
docstring).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

COMPARISONS = ["variant_type", "pathogenicity", "disease_subtype", "protein_domain"]
ENDPOINTS = ["ckd_stage_3_plus", "stage_5_ckd", "any_ckd", "current_age"]

SURVIVAL_PATH = "/api/v2/phenopackets/aggregate/survival-data"


@pytest.mark.asyncio
class TestSurvivalEndpointSmoke:
    """Exercise every (comparison, endpoint) pair through the live dispatcher."""

    @pytest.mark.parametrize("comparison", COMPARISONS)
    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    async def test_returns_well_formed_response(
        self,
        async_client: AsyncClient,
        comparison: str,
        endpoint: str,
    ) -> None:
        """Every (comparison, endpoint) pair returns a 200 with the expected shape."""
        response = await async_client.get(
            SURVIVAL_PATH,
            params={"comparison": comparison, "endpoint": endpoint},
        )
        assert response.status_code == 200, response.text

        body = response.json()
        assert body["comparison_type"] == comparison
        assert "endpoint" in body
        assert "groups" in body
        assert isinstance(body["groups"], list)
        assert "statistical_tests" in body
        assert isinstance(body["statistical_tests"], list)
        assert "metadata" in body
        assert isinstance(body["metadata"], dict)
        # Metadata always carries the group definitions and criteria
        assert "group_definitions" in body["metadata"]
        assert "inclusion_criteria" in body["metadata"]

    async def test_invalid_comparison_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """Unknown comparison types return 400 (client error), not 500."""
        response = await async_client.get(
            SURVIVAL_PATH,
            params={"comparison": "not_a_real_type", "endpoint": "ckd_stage_3_plus"},
        )
        assert response.status_code == 400, response.text
        body = response.json()
        # Error shape is the standard {detail, error_code, request_id} from
        # the exception handlers added in Wave 2.
        assert "detail" in body

    async def test_invalid_endpoint_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """Unknown endpoint values return 400 (client error), not 500."""
        response = await async_client.get(
            SURVIVAL_PATH,
            params={"comparison": "variant_type", "endpoint": "not_a_real_endpoint"},
        )
        assert response.status_code == 400, response.text
        body = response.json()
        assert "detail" in body
        # The detail should name the valid options — useful for client debugging.
        assert "Valid options" in body["detail"] or "valid" in body["detail"].lower()
