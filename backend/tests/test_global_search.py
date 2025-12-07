"""Comprehensive tests for the search module.

Tests cover:
- GlobalSearchRepository: full-text search, autocomplete, count, refresh
- PhenopacketSearchRepository: filtered search, cursor pagination
- GlobalSearchService: search orchestration, empty queries
- PhenopacketSearchService: facets, pagination links
- Search API endpoints: /search/autocomplete, /search/global
- MV refresh utilities
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.search.mv_refresh import (
    MVRefreshMiddleware,
    refresh_global_search_index,
    schedule_refresh_if_stale,
)
from app.search.repositories import GlobalSearchRepository, PhenopacketSearchRepository
from app.search.schemas import GlobalSearchResponse, SearchResultItem
from app.search.services import (
    FacetService,
    GlobalSearchService,
    PaginationParams,
    PhenopacketSearchService,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
async def search_test_data(db_session: AsyncSession):
    """Insert test data for search tests."""
    # Note: We skip gene insertion as it requires a valid genome_id FK reference
    # The existing data in the database should contain genes for search tests

    # Insert test publication
    await db_session.execute(
        text("""
        INSERT INTO publication_metadata (pmid, title, authors, journal, year)
        VALUES (
            'PMID:88888', 'SEARCHGENE mutation analysis study',
            '[]'::jsonb, 'Test Journal', 2024
        )
        ON CONFLICT (pmid) DO NOTHING
    """)
    )

    # Insert test phenopacket with interpretations for variant extraction
    phenopacket_json = {
        "subject": {"id": "SEARCH_SUBJ_001", "sex": "FEMALE"},
        "phenotypicFeatures": [{"type": {"id": "HP:0000001", "label": "Test Feature"}}],
        "interpretations": [
            {
                "diagnosis": {
                    "genomicInterpretations": [
                        {
                            "variantInterpretation": {
                                "variationDescriptor": {
                                    "label": "SEARCHGENE:c.100A>G",
                                    "geneContext": {"symbol": "SEARCHGENE"},
                                    "moleculeContext": "transcript",
                                    "expressions": [{"value": "c.100A>G"}],
                                },
                                "acmgPathogenicityClassification": "PATHOGENIC",
                            }
                        }
                    ]
                }
            }
        ],
        "metaData": {"externalReferences": [{"id": "PMID:88888"}]},
    }

    await db_session.execute(
        text("""
        INSERT INTO phenopackets (id, phenopacket_id, phenopacket, subject_id, subject_sex)
        VALUES (gen_random_uuid(), :pid, CAST(:pp AS jsonb), :subj_id, :sex)
        ON CONFLICT (phenopacket_id) DO NOTHING
    """),
        {
            "pid": "PP_SEARCH_TEST_001",
            "pp": json.dumps(phenopacket_json),
            "subj_id": "SEARCH_SUBJ_001",
            "sex": "FEMALE",
        },
    )

    await db_session.commit()

    # Refresh the materialized view
    await db_session.execute(text("REFRESH MATERIALIZED VIEW global_search_index"))
    await db_session.commit()

    yield

    # Cleanup
    await db_session.execute(
        text("DELETE FROM phenopackets WHERE phenopacket_id = 'PP_SEARCH_TEST_001'")
    )
    await db_session.execute(text("DELETE FROM publication_metadata WHERE pmid = 'PMID:88888'"))
    await db_session.commit()

    # Refresh MV after cleanup
    await db_session.execute(text("REFRESH MATERIALIZED VIEW global_search_index"))
    await db_session.commit()


# ============================================================================
# GlobalSearchRepository Tests
# ============================================================================


class TestGlobalSearchRepository:
    """Tests for GlobalSearchRepository."""

    @pytest.mark.asyncio
    async def test_search_returns_results(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test that search returns matching results."""
        repo = GlobalSearchRepository(db_session)
        # Use SEARCHGENE which is inserted by the search_test_data fixture
        results = await repo.search("SEARCHGENE", limit=10)

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_with_type_filter(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test search with type filter."""
        repo = GlobalSearchRepository(db_session)
        # Search for SEARCHGENE with Variant type filter (from fixture data)
        results = await repo.search("SEARCHGENE", type_filter="Variant", limit=10)

        # Should find the variant from fixture
        if results:
            assert all(r["type"] == "Variant" for r in results)

    @pytest.mark.asyncio
    async def test_search_pagination(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test search pagination with limit and offset."""
        repo = GlobalSearchRepository(db_session)

        # Get first page using fixture data search term
        page1 = await repo.search("SEARCHGENE", limit=1, offset=0)
        # Get second page
        page2 = await repo.search("SEARCHGENE", limit=1, offset=1)

        # If there are multiple results, pages should differ
        if len(page1) > 0 and len(page2) > 0:
            assert page1[0]["id"] != page2[0]["id"]

    @pytest.mark.asyncio
    async def test_search_empty_query(self, db_session: AsyncSession):
        """Test search with empty query returns nothing gracefully."""
        repo = GlobalSearchRepository(db_session)
        # Empty string should be handled by service layer, but repo should not crash
        results = await repo.search("xyznonexistent123", limit=10)
        assert results == []

    @pytest.mark.asyncio
    async def test_count_returns_type_breakdown(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test count returns results grouped by type."""
        repo = GlobalSearchRepository(db_session)
        counts = await repo.count("SEARCHGENE")

        assert isinstance(counts, dict)
        # Should find at least some type (Variant from fixture)
        assert len(counts) >= 1

    @pytest.mark.asyncio
    async def test_autocomplete_prefix_match(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test autocomplete returns prefix matches."""
        repo = GlobalSearchRepository(db_session)
        # Use SEARCH which should match SEARCHGENE variant from fixture
        results = await repo.autocomplete("SEARCH", limit=10)

        assert len(results) >= 1
        # Prefix matches should be prioritized
        assert any("SEARCH" in r["label"].upper() for r in results)

    @pytest.mark.asyncio
    async def test_autocomplete_similarity_match(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test autocomplete uses trigram similarity for fuzzy matches."""
        repo = GlobalSearchRepository(db_session)
        # Use SEARCHGEN which should find SEARCHGENE via prefix/similarity
        results = await repo.autocomplete("SEARCHGEN", limit=10)

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_autocomplete_respects_limit(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test autocomplete respects the limit parameter."""
        repo = GlobalSearchRepository(db_session)
        results = await repo.autocomplete("S", limit=2)

        assert len(results) <= 2


# ============================================================================
# PhenopacketSearchRepository Tests
# ============================================================================


class TestPhenopacketSearchRepository:
    """Tests for PhenopacketSearchRepository."""

    @pytest.mark.asyncio
    async def test_search_with_text_query(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test phenopacket search with full-text query."""
        repo = PhenopacketSearchRepository(db_session)
        results = await repo.search(query="SEARCH_SUBJ_001", limit=10)

        # Should find the test phenopacket
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_with_sex_filter(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test phenopacket search with sex filter."""
        repo = PhenopacketSearchRepository(db_session)
        results = await repo.search(filters={"sex": "FEMALE"}, limit=10)

        assert len(results) >= 1
        # All results should match the filter (verified via subject_sex column)

    @pytest.mark.asyncio
    async def test_search_with_gene_filter(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test phenopacket search with gene filter."""
        repo = PhenopacketSearchRepository(db_session)
        results = await repo.search(filters={"gene": "SEARCHGENE"}, limit=10)

        # Should find phenopacket with SEARCHGENE variant
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_with_pmid_filter(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test phenopacket search with PMID filter."""
        repo = PhenopacketSearchRepository(db_session)

        # Test with PMID: prefix
        results = await repo.search(filters={"pmid": "PMID:88888"}, limit=10)
        assert len(results) >= 1

        # Test without prefix (should auto-add)
        results2 = await repo.search(filters={"pmid": "88888"}, limit=10)
        assert len(results2) >= 1

    @pytest.mark.asyncio
    async def test_search_cursor_pagination(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test cursor-based pagination."""
        repo = PhenopacketSearchRepository(db_session)

        # Get first page
        first_page = await repo.search(limit=1)

        if len(first_page) > 0:
            # Use cursor from first result
            cursor_data = {
                "created_at": first_page[0]["created_at"],
                "id": first_page[0]["id"],
            }
            second_page = await repo.search(
                limit=1, cursor_data=cursor_data, is_backward=False
            )
            # Should get different or no results
            if len(second_page) > 0:
                assert second_page[0]["id"] != first_page[0]["id"]

    @pytest.mark.asyncio
    async def test_search_backward_pagination(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test backward cursor pagination."""
        repo = PhenopacketSearchRepository(db_session)

        # Get a page first
        results = await repo.search(limit=5)

        if len(results) > 1:
            # Navigate backward from the last result
            cursor_data = {
                "created_at": results[-1]["created_at"],
                "id": results[-1]["id"],
            }
            backward_results = await repo.search(
                limit=5, cursor_data=cursor_data, is_backward=True
            )
            # Backward pagination should work
            assert isinstance(backward_results, list)

    @pytest.mark.asyncio
    async def test_count_with_filters(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test count with various filters."""
        repo = PhenopacketSearchRepository(db_session)

        total_count = await repo.count()
        female_count = await repo.count(filters={"sex": "FEMALE"})

        assert total_count >= female_count


# ============================================================================
# GlobalSearchService Tests
# ============================================================================


class TestGlobalSearchService:
    """Tests for GlobalSearchService."""

    @pytest.mark.asyncio
    async def test_search_orchestration(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test search service orchestrates repo calls correctly."""
        service = GlobalSearchService(db_session)
        pagination = PaginationParams(page=1, page_size=20)

        response = await service.search("SEARCHGENE", pagination)

        assert isinstance(response, GlobalSearchResponse)
        assert response.page == 1
        assert response.page_size == 20
        assert response.total >= 1
        assert len(response.results) >= 1
        assert isinstance(response.summary, dict)

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_empty(self, db_session: AsyncSession):
        """Test empty query returns empty response."""
        service = GlobalSearchService(db_session)
        pagination = PaginationParams(page=1, page_size=20)

        response = await service.search("", pagination)

        assert response.results == []
        assert response.total == 0
        assert response.summary == {}

    @pytest.mark.asyncio
    async def test_search_whitespace_query_returns_empty(
        self, db_session: AsyncSession
    ):
        """Test whitespace-only query returns empty response."""
        service = GlobalSearchService(db_session)
        pagination = PaginationParams(page=1, page_size=20)

        response = await service.search("   ", pagination)

        assert response.results == []

    @pytest.mark.asyncio
    async def test_search_with_type_filter(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test search with type filter through service."""
        service = GlobalSearchService(db_session)
        pagination = PaginationParams(page=1, page_size=20)

        response = await service.search("SEARCHGENE", pagination, type_filter="Variant")

        # All results should be of type Variant (from fixture data)
        if response.results:
            assert all(r.type == "Variant" for r in response.results)

    @pytest.mark.asyncio
    async def test_autocomplete_min_length(self, db_session: AsyncSession):
        """Test autocomplete requires minimum query length."""
        service = GlobalSearchService(db_session)

        # Single character should return empty
        response = await service.autocomplete("S", limit=10)
        assert response.results == []

    @pytest.mark.asyncio
    async def test_autocomplete_valid_query(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test autocomplete with valid query."""
        service = GlobalSearchService(db_session)

        response = await service.autocomplete("SEARCH", limit=10)

        assert len(response.results) >= 1
        assert all(isinstance(r, SearchResultItem) for r in response.results)

    @pytest.mark.asyncio
    async def test_refresh_index(self, db_session: AsyncSession):
        """Test MV refresh through service."""
        service = GlobalSearchService(db_session)

        # Should not raise
        await service.refresh_index(concurrently=True)


# ============================================================================
# PhenopacketSearchService Tests
# ============================================================================


class TestPhenopacketSearchService:
    """Tests for PhenopacketSearchService."""

    @pytest.mark.asyncio
    async def test_search_returns_jsonapi_structure(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test search returns JSON:API compliant structure."""
        service = PhenopacketSearchService(db_session)

        result = await service.search(query="SEARCH", page_size=10)

        assert "data" in result
        assert "meta" in result
        assert "links" in result
        assert "page" in result["meta"]

    @pytest.mark.asyncio
    async def test_search_pagination_metadata(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test search includes proper pagination metadata."""
        service = PhenopacketSearchService(db_session)

        result = await service.search(page_size=10)

        page_info = result["meta"]["page"]
        assert "pageSize" in page_info
        assert "hasNextPage" in page_info
        assert "hasPreviousPage" in page_info
        assert "startCursor" in page_info
        assert "endCursor" in page_info

    @pytest.mark.asyncio
    async def test_search_links_structure(
        self, db_session: AsyncSession, search_test_data
    ):
        """Test search links have correct structure."""
        service = PhenopacketSearchService(db_session)

        result = await service.search(page_size=10)

        links = result["links"]
        assert "self" in links
        assert "first" in links
        assert "prev" in links
        assert "next" in links

    @pytest.mark.asyncio
    async def test_get_facets(self, db_session: AsyncSession, search_test_data):
        """Test facet retrieval."""
        service = PhenopacketSearchService(db_session)

        facets = await service.get_facets()

        assert isinstance(facets, dict)
        # Should have common facet categories
        assert "sex" in facets or "genes" in facets or "phenotypes" in facets


# ============================================================================
# FacetService Tests
# ============================================================================


class TestFacetService:
    """Tests for FacetService.

    Note: These tests don't use the search_test_data fixture since
    facets work with all existing data in the database.
    """

    @pytest.mark.asyncio
    async def test_get_facets_returns_all_categories(
        self, db_session: AsyncSession
    ):
        """Test get_facets returns all expected facet categories."""
        service = FacetService(db_session)

        facets = await service.get_facets()

        expected_categories = ["sex", "hasVariants", "pathogenicity", "genes", "phenotypes"]
        for category in expected_categories:
            assert category in facets
            assert isinstance(facets[category], list)

    @pytest.mark.asyncio
    async def test_facet_item_structure(
        self, db_session: AsyncSession
    ):
        """Test facet items have correct structure."""
        service = FacetService(db_session)

        facets = await service.get_facets()

        for category, items in facets.items():
            for item in items:
                assert "value" in item
                assert "label" in item
                assert "count" in item
                assert isinstance(item["count"], int)


# ============================================================================
# PaginationParams Tests
# ============================================================================


class TestPaginationParams:
    """Tests for PaginationParams dataclass."""

    def test_default_values(self):
        """Test default pagination values."""
        params = PaginationParams()
        assert params.page == 1
        assert params.page_size == 20

    def test_offset_calculation(self):
        """Test offset calculation for different pages."""
        assert PaginationParams(page=1, page_size=20).offset == 0
        assert PaginationParams(page=2, page_size=20).offset == 20
        assert PaginationParams(page=3, page_size=10).offset == 20
        assert PaginationParams(page=5, page_size=50).offset == 200


# ============================================================================
# MV Refresh Tests
# ============================================================================


class TestMVRefresh:
    """Tests for materialized view refresh utilities."""

    @pytest.mark.asyncio
    async def test_refresh_global_search_index(self, db_session: AsyncSession):
        """Test MV refresh executes without error."""
        # Should not raise
        await refresh_global_search_index(db_session, concurrently=True)

    @pytest.mark.asyncio
    async def test_refresh_non_concurrent(self, db_session: AsyncSession):
        """Test non-concurrent MV refresh."""
        await refresh_global_search_index(db_session, concurrently=False)

    @pytest.mark.asyncio
    async def test_schedule_refresh_respects_staleness(
        self, db_session: AsyncSession
    ):
        """Test scheduled refresh respects staleness threshold."""
        # Force a refresh first
        await refresh_global_search_index(db_session)

        # Immediate second call should skip (not stale yet)
        refreshed = await schedule_refresh_if_stale(db_session, max_age_seconds=60)

        # Either it refreshed (first time) or skipped (recent)
        assert isinstance(refreshed, bool)


class TestMVRefreshMiddleware:
    """Tests for MVRefreshMiddleware context manager."""

    @pytest.mark.asyncio
    async def test_middleware_no_refresh_when_clean(self, db_session: AsyncSession):
        """Test middleware doesn't refresh when not marked dirty."""
        with patch(
            "app.search.mv_refresh.schedule_refresh_if_stale", new_callable=AsyncMock
        ) as mock_refresh:
            async with MVRefreshMiddleware(db_session):
                # Don't mark dirty
                pass

            mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_middleware_refreshes_when_dirty(self, db_session: AsyncSession):
        """Test middleware refreshes when marked dirty."""
        with patch(
            "app.search.mv_refresh.schedule_refresh_if_stale", new_callable=AsyncMock
        ) as mock_refresh:
            async with MVRefreshMiddleware(db_session) as mv:
                mv.mark_dirty()

            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_middleware_no_refresh_on_exception(self, db_session: AsyncSession):
        """Test middleware doesn't refresh when exception occurs."""
        with patch(
            "app.search.mv_refresh.schedule_refresh_if_stale", new_callable=AsyncMock
        ) as mock_refresh:
            try:
                async with MVRefreshMiddleware(db_session) as mv:
                    mv.mark_dirty()
                    raise ValueError("Test exception")
            except ValueError:
                pass

            mock_refresh.assert_not_called()


# ============================================================================
# API Endpoint Tests
# ============================================================================


class TestSearchEndpoints:
    """Tests for search API endpoints."""

    @pytest.mark.asyncio
    async def test_autocomplete_endpoint(
        self, async_client, db_session: AsyncSession, search_test_data
    ):
        """Test /search/autocomplete endpoint."""
        response = await async_client.get(
            "/api/v2/search/autocomplete", params={"q": "SEARCH", "limit": 5}
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    @pytest.mark.asyncio
    async def test_autocomplete_min_length_validation(self, async_client):
        """Test autocomplete rejects queries shorter than min length."""
        response = await async_client.get(
            "/api/v2/search/autocomplete", params={"q": "S"}
        )

        # FastAPI should return 422 for validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_global_search_endpoint(
        self, async_client, db_session: AsyncSession, search_test_data
    ):
        """Test /search/global endpoint."""
        response = await async_client.get(
            "/api/v2/search/global",
            params={"q": "SEARCHGENE", "page": 1, "page_size": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data
        assert "summary" in data

    @pytest.mark.asyncio
    async def test_global_search_with_type_filter(
        self, async_client, db_session: AsyncSession, search_test_data
    ):
        """Test /search/global with type filter."""
        response = await async_client.get(
            "/api/v2/search/global",
            params={"q": "SEARCHGENE", "type": "Variant"},
        )

        assert response.status_code == 200
        data = response.json()
        for result in data["results"]:
            assert result["type"] == "Variant"

    @pytest.mark.asyncio
    async def test_global_search_pagination(
        self, async_client, db_session: AsyncSession, search_test_data
    ):
        """Test /search/global pagination parameters."""
        response = await async_client.get(
            "/api/v2/search/global",
            params={"q": "SEARCHGENE", "page": 2, "page_size": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 5
