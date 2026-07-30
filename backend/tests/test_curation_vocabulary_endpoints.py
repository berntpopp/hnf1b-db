"""Curation vocabulary endpoints (spec §4.6)."""

import pytest

ENDPOINTS = {
    "cohort": {"born", "fetus"},
    "detection-method": {
        "sanger",
        "ngs",
        "cma",
        "mlpa",
        "qpcr",
        "fish",
        "other",
        "not_reported",
    },
    "segregation": {
        "de_novo",
        "inherited_maternal",
        "inherited_paternal",
        "inherited_unspecified",
        "not_reported",
    },
    "family-history": {"positive", "negative", "not_reported"},
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
    """One shape across all four, unlike the pre-existing vocabulary endpoints."""
    response = await async_client.get(f"/api/v2/ontology/vocabularies/{name}")
    for item in response.json()["data"]:
        assert set(item) == {"value", "label", "description"}
        assert isinstance(item["value"], str)
        assert isinstance(item["label"], str)


@pytest.mark.asyncio
async def test_detection_method_is_ordered_by_sort_order(async_client):
    response = await async_client.get("/api/v2/ontology/vocabularies/detection-method")
    values = [item["value"] for item in response.json()["data"]]
    assert values == [
        "sanger",
        "ngs",
        "cma",
        "mlpa",
        "qpcr",
        "fish",
        "other",
        "not_reported",
    ]


@pytest.mark.asyncio
async def test_cohort_has_no_not_reported(async_client):
    """Absence of the key means 'not yet curated'; the source always states cohort."""
    response = await async_client.get("/api/v2/ontology/vocabularies/cohort")
    assert "not_reported" not in {item["value"] for item in response.json()["data"]}
