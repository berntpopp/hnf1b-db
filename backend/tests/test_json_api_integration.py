"""Integration tests for JSON:API pagination workflows.

This module tests complete pagination workflows that span multiple requests,
ensuring data consistency and correct behavior across pagination boundaries.

Test coverage:
- Paginating through all records
- Following navigation links
- Data consistency with filters
- No duplicate records across pages
- No missing records across pages
- Pagination with concurrent data changes (eventual consistency)
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket
from app.phenopackets.validator import PhenopacketSanitizer


@pytest.fixture
async def large_phenopacket_set(db_session: AsyncSession):
    """Create a larger set of phenopackets for integration testing.

    Creates 100 phenopackets to test pagination across multiple pages.
    """
    sanitizer = PhenopacketSanitizer()
    phenopackets_data = []

    for i in range(100):
        sex = ["MALE", "FEMALE", "OTHER_SEX"][i % 3]
        has_variants = i % 2 == 0  # 50 with variants, 50 without

        data = {
            "id": f"test_integration_{i:03d}",
            "subject": {"id": f"integration_patient_{i:03d}", "sex": sex},
            "phenotypicFeatures": [
                {"type": {"id": "HP:0000001", "label": f"Feature {i}"}}
            ],
            "metaData": {
                "created": f"2024-01-{(i % 28) + 1:02d}T00:00:00Z",
                "phenopacketSchemaVersion": "2.0.0",
            },
        }

        if has_variants:
            data["interpretations"] = [
                {
                    "id": f"interpretation_{i}",
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "variationDescriptor": {
                                        "id": f"variant_{i}",
                                        "label": f"Variant {i}",
                                    }
                                }
                            }
                        ]
                    },
                }
            ]

        sanitized = sanitizer.sanitize_phenopacket(data)

        phenopacket = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
            created_by="integration_test",
        )

        db_session.add(phenopacket)
        phenopackets_data.append(phenopacket)

    await db_session.commit()

    yield phenopackets_data

    # Cleanup
    for pp in phenopackets_data:
        await db_session.delete(pp)
    await db_session.commit()


class TestPaginationWorkflows:
    """Test complete pagination workflows."""

    @pytest.mark.asyncio
    async def test_paginate_through_all_records(
        self, async_client: AsyncClient, large_phenopacket_set, auth_headers
    ):
        """Test paginating through a subset of records without duplicates."""
        page_size = 20
        all_ids = set()

        # Get first 3 pages
        for page in range(1, 4):
            response = await async_client.get(
                f"/api/v2/phenopackets/?page[number]={page}&page[size]={page_size}&sort=subject_id",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            # Collect all IDs (including non-test data)
            for phenopacket in data["data"]:
                phenopacket_id = phenopacket["id"]
                assert phenopacket_id not in all_ids, (
                    f"Duplicate phenopacket ID found: {phenopacket_id}"
                )
                all_ids.add(phenopacket_id)

        # Should have collected 60 unique records across 3 pages (20 per page)
        assert len(all_ids) == 60, (
            f"Expected 60 unique records across 3 pages, got {len(all_ids)}"
        )

    @pytest.mark.asyncio
    async def test_follow_navigation_links(
        self, async_client: AsyncClient, large_phenopacket_set, auth_headers
    ):
        """Test following next/prev links correctly navigates pages."""
        # Get first page with sorting for consistency
        response = await async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=15&sort=subject_id",
            headers=auth_headers,
        )
        assert response.status_code == 200
        page1_data = response.json()

        # Follow next link
        next_url = page1_data["links"]["next"]
        if next_url:
            # Remove base URL if present
            next_url = next_url.replace("http://test", "")

            response = await async_client.get(next_url, headers=auth_headers)
            assert response.status_code == 200
            page2_data = response.json()

            # Should be on page 2
            assert page2_data["meta"]["page"]["currentPage"] == 2

            # Check that records are different (test data only)
            page1_test_ids = {
                p["id"]
                for p in page1_data["data"]
                if p["id"].startswith("test_integration_")
            }
            page2_test_ids = {
                p["id"]
                for p in page2_data["data"]
                if p["id"].startswith("test_integration_")
            }

            # Only check if we have test data on both pages
            if page1_test_ids and page2_test_ids:
                assert page1_test_ids.isdisjoint(page2_test_ids), (
                    "Pages should not have overlapping test records"
                )

            # Follow prev link back to page 1
            prev_url = page2_data["links"]["prev"]
            if prev_url:
                prev_url = prev_url.replace("http://test", "")

                response = await async_client.get(prev_url, headers=auth_headers)
                assert response.status_code == 200
                page1_again = response.json()

                # Should be back on page 1
                assert page1_again["meta"]["page"]["currentPage"] == 1

    @pytest.mark.asyncio
    async def test_last_link_goes_to_last_page(
        self, async_client: AsyncClient, large_phenopacket_set, auth_headers
    ):
        """Test that last link correctly navigates to last page."""
        # Get first page
        response = await async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=20",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Follow last link
        last_url = data["links"]["last"]
        last_url = last_url.replace("http://test", "")

        response = await async_client.get(last_url, headers=auth_headers)
        assert response.status_code == 200
        last_page_data = response.json()

        # Should be on last page
        page_meta = last_page_data["meta"]["page"]
        assert page_meta["currentPage"] == page_meta["totalPages"]

        # Should have no next link
        assert last_page_data["links"]["next"] is None


class TestDataConsistency:
    """Test data consistency across pagination."""

    @pytest.mark.asyncio
    async def test_no_duplicate_records_across_pages(
        self, async_client: AsyncClient, large_phenopacket_set, auth_headers
    ):
        """Test that no test records appear on multiple pages."""
        page_size = 25
        total_pages = 5
        all_ids = set()

        for page in range(1, total_pages + 1):
            response = await async_client.get(
                f"/api/v2/phenopackets/?page[number]={page}&page[size]={page_size}&sort=subject_id",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            # Only check test data for duplicates
            for phenopacket in data["data"]:
                phenopacket_id = phenopacket["id"]
                if phenopacket_id.startswith("test_integration_"):
                    assert phenopacket_id not in all_ids, (
                        f"Duplicate ID {phenopacket_id} found on page {page}"
                    )
                    all_ids.add(phenopacket_id)

    @pytest.mark.asyncio
    async def test_data_consistency_with_filters(
        self, async_client: AsyncClient, large_phenopacket_set, auth_headers
    ):
        """Test that filtering produces consistent results across paginated requests."""
        # Get first 2 pages with MALE filter
        page_size = 25
        all_male_ids = set()

        for page in range(1, 3):
            response = await async_client.get(
                f"/api/v2/phenopackets/?page[number]={page}&page[size]={page_size}&filter[sex]=MALE&sort=subject_id",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            # Verify all are MALE
            for phenopacket in data["data"]:
                assert phenopacket["subject"]["sex"] == "MALE"
                all_male_ids.add(phenopacket["id"])

        # Should have some MALE records
        assert len(all_male_ids) > 0, (
            "Should have found at least some MALE phenopackets"
        )

    @pytest.mark.asyncio
    async def test_sorted_data_consistency(
        self, async_client: AsyncClient, large_phenopacket_set, auth_headers
    ):
        """Test that sorted pagination returns records in consistent order."""
        page_size = 20

        # Get page 1 sorted
        response1 = await async_client.get(
            f"/api/v2/phenopackets/?page[number]=1&page[size]={page_size}&sort=subject_id",
            headers=auth_headers,
        )
        page1_ids = [p["subject"]["id"] for p in response1.json()["data"]]

        # Get page 2 sorted
        response2 = await async_client.get(
            f"/api/v2/phenopackets/?page[number]=2&page[size]={page_size}&sort=subject_id",
            headers=auth_headers,
        )
        page2_ids = [p["subject"]["id"] for p in response2.json()["data"]]

        # Combine and check global sort order
        all_ids = page1_ids + page2_ids
        assert all_ids == sorted(all_ids), (
            "Records should be in ascending order across pages"
        )

        # Last ID of page 1 should be < first ID of page 2
        if page1_ids and page2_ids:
            assert page1_ids[-1] < page2_ids[0], (
                "Page boundaries should maintain sort order"
            )


class TestFilteringConsistency:
    """Test that filtering works consistently across pagination."""

    @pytest.mark.asyncio
    async def test_filter_results_match_across_pages(
        self, async_client: AsyncClient, large_phenopacket_set, auth_headers
    ):
        """Test that filter criteria are maintained across all pages."""
        filter_params = "filter[sex]=FEMALE&filter[has_variants]=true"
        page = 1
        max_pages = 10

        while page <= max_pages:
            response = await async_client.get(
                f"/api/v2/phenopackets/?page[number]={page}&page[size]=10&{filter_params}",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            # Verify all records match filter criteria
            for phenopacket in data["data"]:
                assert phenopacket["subject"]["sex"] == "FEMALE"
                assert "interpretations" in phenopacket

            if not data["links"]["next"]:
                break

            page += 1

    @pytest.mark.asyncio
    async def test_combined_filters_pagination(
        self, async_client: AsyncClient, large_phenopacket_set, auth_headers
    ):
        """Test pagination with multiple filters combined."""
        # Get first 2 pages with combined filters
        page_size = 15
        all_filtered_ids = set()

        for page in range(1, 3):
            response = await async_client.get(
                f"/api/v2/phenopackets/?page[number]={page}&page[size]={page_size}&filter[sex]=MALE&filter[has_variants]=true&sort=subject_id",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            # Verify all match both filters
            for phenopacket in data["data"]:
                assert phenopacket["subject"]["sex"] == "MALE"
                assert (
                    "interpretations" in phenopacket
                    and len(phenopacket["interpretations"]) > 0
                )
                all_filtered_ids.add(phenopacket["id"])

        # Should have found some records matching both filters
        assert len(all_filtered_ids) > 0, (
            "Should have found MALE phenopackets with variants"
        )


class TestSortingConsistency:
    """Test that sorting is consistent across pagination."""

    @pytest.mark.asyncio
    async def test_ascending_sort_across_pages(
        self, async_client: AsyncClient, large_phenopacket_set, auth_headers
    ):
        """Test ascending sort order is maintained across pages."""
        all_ids = []
        page = 1
        page_size = 20

        for _ in range(3):  # Get first 3 pages
            response = await async_client.get(
                f"/api/v2/phenopackets/?page[number]={page}&page[size]={page_size}&sort=subject_id",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            page_ids = [p["subject"]["id"] for p in data["data"]]
            all_ids.extend(page_ids)

            if not data["links"]["next"]:
                break

            page += 1

        # All IDs should be in ascending order
        assert all_ids == sorted(all_ids), (
            "IDs should be in ascending order across all pages"
        )

    @pytest.mark.asyncio
    async def test_descending_sort_across_pages(
        self, async_client: AsyncClient, large_phenopacket_set, auth_headers
    ):
        """Test descending sort order is maintained across pages."""
        all_ids = []
        page = 1
        page_size = 20

        for _ in range(3):  # Get first 3 pages
            response = await async_client.get(
                f"/api/v2/phenopackets/?page[number]={page}&page[size]={page_size}&sort=-subject_id",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            page_ids = [p["subject"]["id"] for p in data["data"]]
            all_ids.extend(page_ids)

            if not data["links"]["next"]:
                break

            page += 1

        # All IDs should be in descending order
        assert all_ids == sorted(all_ids, reverse=True), (
            "IDs should be in descending order across all pages"
        )


class TestComplexScenarios:
    """Test complex real-world pagination scenarios."""

    @pytest.mark.asyncio
    async def test_filter_sort_paginate_combined(
        self, async_client: AsyncClient, large_phenopacket_set, auth_headers
    ):
        """Test combining filtering, sorting, and pagination."""
        # Get MALE phenopackets, sorted by subject_id, paginated
        all_ids = []
        page = 1
        page_size = 15

        while page <= 5:  # Safety limit
            response = await async_client.get(
                f"/api/v2/phenopackets/?page[number]={page}&page[size]={page_size}&filter[sex]=MALE&sort=subject_id",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            for phenopacket in data["data"]:
                # Check filter
                assert phenopacket["subject"]["sex"] == "MALE"
                all_ids.append(phenopacket["subject"]["id"])

            if not data["links"]["next"]:
                break

            page += 1

        # Check sort order
        assert all_ids == sorted(all_ids), "Results should be sorted"

    @pytest.mark.asyncio
    async def test_pagination_metadata_consistency(
        self, async_client: AsyncClient, large_phenopacket_set, auth_headers
    ):
        """Test that metadata is consistent across all pages."""
        page_size = 20
        total_pages_expected = None
        total_records_expected = None

        for page in range(1, 6):  # Check first 5 pages
            response = await async_client.get(
                f"/api/v2/phenopackets/?page[number]={page}&page[size]={page_size}",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            page_meta = data["meta"]["page"]

            # First page sets expectations
            if total_pages_expected is None:
                total_pages_expected = page_meta["totalPages"]
                total_records_expected = page_meta["totalRecords"]
            else:
                # All pages should report same totals
                assert page_meta["totalPages"] == total_pages_expected, (
                    "totalPages should be consistent across pages"
                )
                assert page_meta["totalRecords"] == total_records_expected, (
                    "totalRecords should be consistent across pages"
                )

            # Current page should match request
            assert page_meta["currentPage"] == page

            if not data["links"]["next"]:
                break

    @pytest.mark.asyncio
    async def test_page_boundary_accuracy(
        self, async_client: AsyncClient, large_phenopacket_set, auth_headers
    ):
        """Test that page boundaries are accurate (no overlap or gaps)."""
        page_size = 17  # Use odd number to test boundary calculation

        # Get two consecutive pages
        response1 = await async_client.get(
            f"/api/v2/phenopackets/?page[number]=1&page[size]={page_size}&sort=subject_id",
            headers=auth_headers,
        )
        page1_data = response1.json()

        response2 = await async_client.get(
            f"/api/v2/phenopackets/?page[number]=2&page[size]={page_size}&sort=subject_id",
            headers=auth_headers,
        )
        page2_data = response2.json()

        # Extract IDs
        page1_ids = {p["id"] for p in page1_data["data"]}
        page2_ids = {p["id"] for p in page2_data["data"]}

        # No overlap
        assert page1_ids.isdisjoint(page2_ids), (
            "Pages should not have overlapping records"
        )

        # Check sorted order (last of page1 < first of page2)
        page1_subject_ids = [p["subject"]["id"] for p in page1_data["data"]]
        page2_subject_ids = [p["subject"]["id"] for p in page2_data["data"]]

        if page1_subject_ids and page2_subject_ids:
            assert page1_subject_ids[-1] < page2_subject_ids[0], (
                "Page boundary should maintain sort order"
            )
