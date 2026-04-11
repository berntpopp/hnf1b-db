"""Tests for ``app/publications/endpoints/list_route.py``.

Covers the Wave 4 extraction of ``_build_where_clauses`` (shared between
the list query and the count query so they can't drift) and the list
endpoint itself under pagination / filter / search parameters.

Uses the ``async_client`` fixture from ``conftest.py`` and writes
directly to the ``publication_metadata`` and ``phenopackets`` tables
via the ``db_session`` fixture — this is faster and more reliable
than driving the admin sync endpoint which depends on PubMed.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from app.phenopackets.models import Phenopacket
from app.publications.endpoints.list_route import _build_where_clauses

# ---------------------------------------------------------------------------
# Unit tests for the shared helper
# ---------------------------------------------------------------------------


class TestBuildWhereClauses:
    """``_build_where_clauses`` composes filter fragments from query params."""

    def test_no_filters_returns_empty_clauses_and_params(self):
        """Bare call returns no fragments and no binds."""
        clauses, params = _build_where_clauses(
            filter_year=None,
            filter_year_gte=None,
            filter_year_lte=None,
            filter_has_doi=None,
            q=None,
        )
        assert clauses == []
        assert params == {}

    def test_exact_year_filter(self):
        """``filter[year]=2023`` compiles to ``pm.year = :filter_year``."""
        clauses, params = _build_where_clauses(
            filter_year=2023,
            filter_year_gte=None,
            filter_year_lte=None,
            filter_has_doi=None,
            q=None,
        )
        assert clauses == ["pm.year = :filter_year"]
        assert params == {"filter_year": 2023}

    def test_year_range_filter(self):
        """``gte`` and ``lte`` may be combined."""
        clauses, params = _build_where_clauses(
            filter_year=None,
            filter_year_gte=2020,
            filter_year_lte=2024,
            filter_has_doi=None,
            q=None,
        )
        assert "pm.year >= :filter_year_gte" in clauses
        assert "pm.year <= :filter_year_lte" in clauses
        assert params["filter_year_gte"] == 2020
        assert params["filter_year_lte"] == 2024

    def test_has_doi_true_clause(self):
        """``filter[has_doi]=true`` requires a non-empty doi."""
        clauses, _ = _build_where_clauses(
            filter_year=None,
            filter_year_gte=None,
            filter_year_lte=None,
            filter_has_doi=True,
            q=None,
        )
        assert clauses == ["pm.doi IS NOT NULL AND pm.doi != ''"]

    def test_has_doi_false_clause(self):
        """``filter[has_doi]=false`` matches NULL OR empty string."""
        clauses, _ = _build_where_clauses(
            filter_year=None,
            filter_year_gte=None,
            filter_year_lte=None,
            filter_has_doi=False,
            q=None,
        )
        assert clauses == ["(pm.doi IS NULL OR pm.doi = '')"]

    def test_search_query_binds_wildcard_percent(self):
        """``q=foo`` becomes an ILIKE with ``%foo%`` against four columns."""
        clauses, params = _build_where_clauses(
            filter_year=None,
            filter_year_gte=None,
            filter_year_lte=None,
            filter_has_doi=None,
            q="renal",
        )
        assert len(clauses) == 1
        assert "pc.pmid ILIKE :search_query" in clauses[0]
        assert "pm.title ILIKE :search_query" in clauses[0]
        assert "pm.journal ILIKE :search_query" in clauses[0]
        assert "pm.authors::text ILIKE :search_query" in clauses[0]
        assert params["search_query"] == "%renal%"

    def test_all_filters_compose(self):
        """All filters together → five clauses and a populated params dict."""
        clauses, params = _build_where_clauses(
            filter_year=2023,
            filter_year_gte=2020,
            filter_year_lte=2024,
            filter_has_doi=True,
            q="cysts",
        )
        assert len(clauses) == 5
        assert set(params.keys()) == {
            "filter_year",
            "filter_year_gte",
            "filter_year_lte",
            "search_query",
        }


# ---------------------------------------------------------------------------
# Integration tests for the list endpoint
# ---------------------------------------------------------------------------


async def _seed_publication_row(
    db_session,
    *,
    pmid: str,
    title: str,
    year: int,
    doi: str | None = None,
    authors: list[dict] | None = None,
    journal: str = "J. Test",
) -> None:
    """Insert one ``publication_metadata`` row via raw SQL.

    Also inserts a phenopacket that references the PMID so the
    ``pub_counts`` CTE picks it up (the list query requires the join
    to phenopackets — publications with no referencing phenopacket
    are never returned).
    """
    # ``fetched_at`` is TIMESTAMPTZ (migration a7f1c2d9e5b3), so the
    # tz-aware UTC datetime round-trips without any ``.replace`` hack.
    await db_session.execute(
        text("""
            INSERT INTO publication_metadata (
                pmid, title, authors, journal, year, doi, fetched_at, fetched_by
            )
            VALUES (
                :pmid, :title, CAST(:authors AS JSONB), :journal, :year,
                :doi, :fetched_at, 'test'
            )
            ON CONFLICT (pmid) DO UPDATE SET
                title = EXCLUDED.title,
                year = EXCLUDED.year,
                doi = EXCLUDED.doi,
                authors = EXCLUDED.authors,
                journal = EXCLUDED.journal
        """),
        {
            "pmid": pmid,
            "title": title,
            "authors": __import__("json").dumps(
                authors or [{"name": "Smith A"}, {"name": "Jones B"}]
            ),
            "journal": journal,
            "year": year,
            "doi": doi,
            "fetched_at": datetime.now(timezone.utc),
        },
    )

    # Insert a phenopacket that cites the PMID so the list query's
    # pub_counts CTE returns a row for it.
    phenopacket_id = f"PUB-TEST-{pmid.replace('PMID:', '')}"
    row = Phenopacket(
        phenopacket_id=phenopacket_id,
        phenopacket={
            "id": phenopacket_id,
            "subject": {"id": f"SUB-{phenopacket_id}", "sex": "UNKNOWN_SEX"},
            "phenotypicFeatures": [],
            "metaData": {
                "created": "2026-04-11T00:00:00Z",
                "createdBy": "pub-test",
                "phenopacketSchemaVersion": "2.0",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "namespacePrefix": "HP",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-01-01",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
                "externalReferences": [{"id": pmid, "description": title}],
            },
        },
        subject_id=f"SUB-{phenopacket_id}",
        subject_sex="UNKNOWN_SEX",
        created_by="pub-test",
    )
    db_session.add(row)

    await db_session.commit()


@pytest.mark.asyncio
class TestPublicationsListEndpoint:
    """``GET /api/v2/publications/`` end-to-end."""

    async def test_empty_response(self, async_client):
        """With no publications, endpoint returns an empty data array."""
        response = await async_client.get("/api/v2/publications/?page[size]=5")
        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert body["data"] == []

    async def test_list_returns_seeded_publication(self, async_client, db_session):
        """A seeded publication shows up in the default list."""
        await _seed_publication_row(
            db_session,
            pmid="PMID:11111",
            title="HNF1B cystic disease",
            year=2020,
            doi="10.1000/abc",
        )
        response = await async_client.get("/api/v2/publications/?page[size]=5")
        assert response.status_code == 200
        pmids = [item["pmid"] for item in response.json()["data"]]
        assert "11111" in pmids

    async def test_year_filter_narrows_result_set(self, async_client, db_session):
        """``filter[year]=2021`` excludes publications from other years."""
        await _seed_publication_row(
            db_session, pmid="PMID:22221", title="2020 paper", year=2020
        )
        await _seed_publication_row(
            db_session, pmid="PMID:22222", title="2021 paper", year=2021
        )

        response = await async_client.get(
            "/api/v2/publications/?page[size]=5&filter[year]=2021"
        )
        assert response.status_code == 200
        data = response.json()["data"]
        years = {item["year"] for item in data}
        assert years == {2021}

    async def test_has_doi_filter_excludes_missing_doi(self, async_client, db_session):
        """``filter[has_doi]=true`` excludes rows with NULL/empty DOI."""
        await _seed_publication_row(
            db_session, pmid="PMID:33331", title="with doi", year=2022, doi="10.1/x"
        )
        await _seed_publication_row(
            db_session, pmid="PMID:33332", title="no doi", year=2022
        )

        response = await async_client.get(
            "/api/v2/publications/?page[size]=10&filter[has_doi]=true"
        )
        assert response.status_code == 200
        pmids = {item["pmid"] for item in response.json()["data"]}
        assert "33331" in pmids
        assert "33332" not in pmids

    async def test_search_query_filter(self, async_client, db_session):
        """``q=kidney`` matches title substring via ILIKE."""
        await _seed_publication_row(
            db_session, pmid="PMID:44441", title="Kidney disease review", year=2022
        )
        await _seed_publication_row(
            db_session, pmid="PMID:44442", title="Liver disease review", year=2022
        )

        response = await async_client.get("/api/v2/publications/?q=kidney")
        assert response.status_code == 200
        pmids = [item["pmid"] for item in response.json()["data"]]
        assert "44441" in pmids
        assert "44442" not in pmids

    async def test_invalid_sort_field_returns_400(self, async_client):
        """Unknown sort field → 400 from ``parse_sort_parameter``."""
        response = await async_client.get("/api/v2/publications/?sort=not_a_real_field")
        assert response.status_code == 400

    async def test_authors_formatting_many_names(self, async_client, db_session):
        """Four or more authors → ``First A et al.`` formatting."""
        await _seed_publication_row(
            db_session,
            pmid="PMID:55551",
            title="many authors",
            year=2023,
            authors=[
                {"name": "Alpha A"},
                {"name": "Beta B"},
                {"name": "Gamma G"},
                {"name": "Delta D"},
                {"name": "Epsilon E"},
            ],
        )
        response = await async_client.get("/api/v2/publications/?q=authors")
        assert response.status_code == 200
        data = response.json()["data"]
        assert any("et al." in item["authors"] for item in data)

    async def test_title_fallback_when_metadata_missing(self, async_client, db_session):
        """Phenopackets referencing unknown PMIDs still appear with fallback text.

        The list query LEFT JOINs ``publication_metadata`` onto the
        ``pub_counts`` CTE. When a phenopacket cites a PMID that has
        never been synced, the join returns NULL for title/authors and
        the endpoint substitutes ``"Title unavailable"`` / ``"-"``.
        This test wires up that scenario by inserting a phenopacket
        that references a PMID **without** seeding its metadata row.
        """
        row = Phenopacket(
            phenopacket_id="PUB-FALLBACK-001",
            phenopacket={
                "id": "PUB-FALLBACK-001",
                "subject": {"id": "S1", "sex": "UNKNOWN_SEX"},
                "phenotypicFeatures": [],
                "metaData": {
                    "created": "2026-04-11T00:00:00Z",
                    "createdBy": "test",
                    "phenopacketSchemaVersion": "2.0",
                    "resources": [
                        {
                            "id": "hp",
                            "name": "HPO",
                            "namespacePrefix": "HP",
                            "url": "http://x",
                            "version": "1",
                            "iriPrefix": "http://x",
                        }
                    ],
                    "externalReferences": [{"id": "PMID:66661"}],
                },
            },
            subject_id="S1",
            subject_sex="UNKNOWN_SEX",
            created_by="test",
        )
        db_session.add(row)
        await db_session.commit()

        response = await async_client.get("/api/v2/publications/?page[size]=50")
        assert response.status_code == 200
        fallback = next(
            (item for item in response.json()["data"] if item["pmid"] == "66661"),
            None,
        )
        assert fallback is not None
        assert fallback["title"] == "Title unavailable"
        assert fallback["authors"] == "-"
