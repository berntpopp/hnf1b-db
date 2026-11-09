"""API tests for ``GET|PUT /api/v2/publications/{pmid}/specialty``."""

from __future__ import annotations

import aiohttp
import pytest
from sqlalchemy import text

from app.publications.endpoints import specialty_route
from app.publications.specialty import SpecialtySuggestion

URL = "/api/v2/publications/PMID:16971658/specialty"


@pytest.fixture
async def seeded(db_session):
    await db_session.execute(
        text(
            "INSERT INTO publication_metadata (pmid, title, authors, journal, year) "
            "VALUES ('PMID:16971658', 'T', '[]'::jsonb, 'JASN', 2006)"
        )
    )
    await db_session.commit()


@pytest.fixture
def fake_ncbi(monkeypatch):
    calls: list[list[str]] = []

    async def fake(pmids, **kwargs):
        calls.append(list(pmids))
        return {
            "16971658": SpecialtySuggestion(
                "16971658",
                scores={"nephrology": 3, "pediatrics": 1},
                evidence={
                    "nephrology": ["journal", "first_author"],
                    "pediatrics": ["first_author"],
                },
            )
        }

    monkeypatch.setattr(specialty_route, "fetch_specialty_suggestions", fake)
    return calls


@pytest.mark.asyncio
async def test_requires_auth_and_curator(async_client, viewer_headers, seeded):
    assert (await async_client.get(URL)).status_code == 401
    assert (await async_client.get(URL, headers=viewer_headers)).status_code == 403
    put = await async_client.put(
        URL, json={"medical_specialty": ["nephrology"]}, headers=viewer_headers
    )
    assert put.status_code == 403


@pytest.mark.asyncio
async def test_get_returns_ranked_suggestions_with_evidence(
    async_client, curator_headers, seeded, fake_ncbi
):
    r = await async_client.get(URL, headers=curator_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pmid"] == "PMID:16971658"
    assert body["medical_specialty"] == []
    assert body["vocabulary"][:2] == ["nephrology", "diabetology"]
    assert body["suggestions"] == [
        {
            "specialty": "nephrology",
            "score": 3,
            "evidence": ["journal", "first_author"],
        },
        {"specialty": "pediatrics", "score": 1, "evidence": ["first_author"]},
    ]
    assert fake_ncbi == [["PMID:16971658"]]


@pytest.mark.asyncio
async def test_put_saves_dedupes_keeps_order_and_metadata_exposes_it(
    async_client, curator_headers, seeded, fake_ncbi
):
    r = await async_client.put(
        URL,
        json={"medical_specialty": ["pediatrics", "nephrology", "pediatrics"]},
        headers=curator_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"medical_specialty": ["pediatrics", "nephrology"]}
    meta = await async_client.get("/api/v2/publications/16971658/metadata")
    assert meta.json()["medical_specialty"] == ["pediatrics", "nephrology"]
    got = await async_client.get(URL, headers=curator_headers)
    assert got.json()["medical_specialty"] == ["pediatrics", "nephrology"]

    cleared = await async_client.put(
        URL, json={"medical_specialty": []}, headers=curator_headers
    )
    assert cleared.json() == {"medical_specialty": []}
    meta = await async_client.get("/api/v2/publications/16971658/metadata")
    assert meta.json()["medical_specialty"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"medical_specialty": ["cardiology"]},
        {"medical_specialty": "nephrology"},
        {"medical_specialty": ["nephrology"] * 9},
        {},
    ],
)
async def test_put_rejects_invalid_payload(
    async_client, curator_headers, seeded, payload
):
    r = await async_client.put(URL, json=payload, headers=curator_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_invalid_pmid_is_400(async_client, curator_headers):
    r = await async_client.get(
        "/api/v2/publications/abc';--/specialty", headers=curator_headers
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_ncbi_failure_degrades_to_empty_suggestions(
    async_client, curator_headers, seeded, monkeypatch
):
    async def boom(pmids, **kwargs):
        raise aiohttp.ClientConnectionError("down")

    monkeypatch.setattr(specialty_route, "fetch_specialty_suggestions", boom)
    r = await async_client.get(URL, headers=curator_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["suggestions"] == []
    assert "NCBI" in body["suggestion_error"]
    assert "nephrology" in body["vocabulary"]


@pytest.mark.asyncio
async def test_no_pubmed_record_gives_empty_suggestions(
    async_client, curator_headers, seeded, monkeypatch
):
    async def none(pmids, **kwargs):
        return {}

    monkeypatch.setattr(specialty_route, "fetch_specialty_suggestions", none)
    r = await async_client.get(URL, headers=curator_headers)
    assert r.status_code == 200
    assert r.json()["suggestions"] == []


@pytest.mark.asyncio
async def test_unknown_pmid_is_404(async_client, curator_headers, monkeypatch):
    from app.publications.service import PubMedNotFoundError

    async def not_found(pmid, db, fetched_by=None):
        raise PubMedNotFoundError(f"{pmid} not found in PubMed")

    monkeypatch.setattr(specialty_route, "get_publication_metadata", not_found)
    r = await async_client.get(
        "/api/v2/publications/1/specialty", headers=curator_headers
    )
    assert r.status_code == 404
