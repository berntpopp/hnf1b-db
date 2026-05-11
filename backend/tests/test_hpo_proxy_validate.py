from __future__ import annotations

import asyncio

import pytest

from app.services.ontology_service import OntologySource, OntologyTerm, ontology_service


@pytest.mark.asyncio
async def test_validate_route_uses_async_term_lookup_for_slow_fetch(
    async_client, monkeypatch
):
    term_id = "HP:9999999"
    mocked_term = OntologyTerm(
        id=term_id,
        label="Slow mocked term",
        source=OntologySource.HPO_API,
    )

    def fail_sync_lookup(requested_term_id: str):
        raise AssertionError(f"sync lookup used for {requested_term_id}")

    async def fake_async_lookup(requested_term_id: str):
        assert requested_term_id == term_id
        await asyncio.sleep(0.01)
        return mocked_term

    monkeypatch.setattr(ontology_service, "get_term", fail_sync_lookup)
    monkeypatch.setattr(
        ontology_service, "get_term_async", fake_async_lookup, raising=False
    )

    response = await async_client.get(
        "/api/v2/hpo/validate", params={"term_ids": term_id}
    )

    assert response.status_code == 200
    assert response.json()[term_id] == {
        "valid": True,
        "name": "Slow mocked term",
        "source": "hpo_api",
    }


@pytest.mark.asyncio
async def test_validate_route_marks_unknown_placeholder_invalid(
    async_client, monkeypatch
):
    term_id = "HP:0000000"
    unknown_term = OntologyTerm(
        id=term_id,
        label=f"Unknown term: {term_id}",
        source=OntologySource.LOCAL_HARDCODED,
    )

    async def fake_async_lookup(requested_term_id: str):
        assert requested_term_id == term_id
        return unknown_term

    monkeypatch.setattr(
        ontology_service, "get_term_async", fake_async_lookup, raising=False
    )

    response = await async_client.get(
        "/api/v2/hpo/validate", params={"term_ids": term_id}
    )

    assert response.status_code == 200
    assert response.json()[term_id] == {
        "valid": False,
        "name": f"Unknown term: {term_id}",
        "source": "local_hardcoded",
    }


@pytest.mark.asyncio
async def test_validate_route_marks_obsolete_term_invalid(async_client, monkeypatch):
    term_id = "HP:0000001"
    obsolete_term = OntologyTerm(
        id=term_id,
        label="Obsolete term",
        source=OntologySource.OLS_API,
        is_obsolete=True,
    )

    async def fake_async_lookup(requested_term_id: str):
        assert requested_term_id == term_id
        return obsolete_term

    monkeypatch.setattr(
        ontology_service, "get_term_async", fake_async_lookup, raising=False
    )

    response = await async_client.get(
        "/api/v2/hpo/validate", params={"term_ids": term_id}
    )

    assert response.status_code == 200
    assert response.json()[term_id] == {
        "valid": False,
        "name": "Obsolete term",
        "source": "ols_api",
    }
