"""Curation console vocabulary endpoints (plan Task 2 / spec §4).

Follows the same idiom as tests/test_curation_vocabulary_endpoints.py, which
covers the four Phase 2 curation vocabularies. These two are new for
Phase 3: publication type and classification system.
"""

import pytest

ENDPOINTS = {
    "publication-type": {
        "case_report",
        "case_series",
        "review_and_cases",
        "review",
        "research",
        "screening_multiple",
    },
    "classification-system": {"acmg", "clingen_cnv"},
}


@pytest.mark.parametrize("name,expected", ENDPOINTS.items())
@pytest.mark.asyncio
async def test_returns_expected_values(async_client, name, expected):
    response = await async_client.get(f"/api/v2/ontology/vocabularies/{name}")
    assert response.status_code == 200
    assert {item["value"] for item in response.json()["data"]} == expected


@pytest.mark.parametrize("name", ENDPOINTS)
@pytest.mark.asyncio
async def test_item_shape_is_canonical(async_client, name):
    """Same {value,label,description} shape as the other curation vocabularies."""
    response = await async_client.get(f"/api/v2/ontology/vocabularies/{name}")
    for item in response.json()["data"]:
        assert set(item) == {"value", "label", "description"}
        assert isinstance(item["value"], str)
        assert isinstance(item["label"], str)


@pytest.mark.asyncio
async def test_publication_type_is_ordered_by_sort_order(async_client):
    response = await async_client.get("/api/v2/ontology/vocabularies/publication-type")
    values = [item["value"] for item in response.json()["data"]]
    assert values == [
        "case_report",
        "case_series",
        "review_and_cases",
        "review",
        "research",
        "screening_multiple",
    ]


@pytest.mark.asyncio
async def test_classification_system_is_ordered_by_sort_order(async_client):
    response = await async_client.get(
        "/api/v2/ontology/vocabularies/classification-system"
    )
    values = [item["value"] for item in response.json()["data"]]
    assert values == ["acmg", "clingen_cnv"]
