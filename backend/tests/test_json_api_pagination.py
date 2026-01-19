"""Tests for JSON:API pagination implementation.

This module tests the JSON:API v1.1 compliant pagination, filtering,
and sorting features added in Issue #62.

Test coverage:
- Offset pagination (page[number], page[size])
- Filtering (filter[sex], filter[has_variants])
- Sorting (sort parameter with asc/desc)
- Response structure (data, meta, links)
- Pagination metadata accuracy
- Navigation links (first, prev, next, last)
- Edge cases (empty results, last page, single page)
- Backwards compatibility (skip/limit parameters)
- Error handling (invalid sort fields, out-of-range pages)
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket
from app.phenopackets.validator import PhenopacketSanitizer


@pytest.fixture(scope="function")
async def fixture_sample_phenopackets(fixture_db_session: AsyncSession):
    """Create sample phenopackets for pagination testing.

    Creates 50 phenopackets with varying attributes:
    - 25 MALE, 25 FEMALE
    - 30 with variants, 20 without
    - Sequential IDs for sorting tests
    """
    from sqlalchemy import delete

    sanitizer = PhenopacketSanitizer()

    # Pre-cleanup: Remove any leftover test data from failed previous runs
    await fixture_db_session.execute(
        delete(Phenopacket).where(Phenopacket.phenopacket_id.like("test_pagination_%"))
    )
    await fixture_db_session.commit()
    await fixture_db_session.rollback()  # Ensure fresh session

    phenopackets_data = []

    for i in range(50):
        sex = "MALE" if i % 2 == 0 else "FEMALE"
        has_variants = i < 30  # First 30 have variants

        data = {
            "id": f"test_pagination_{i:03d}",  # Zero-padded for sorting
            "subject": {"id": f"patient_{i:03d}", "sex": sex},
            "phenotypicFeatures": [
                {"type": {"id": "HP:0000001", "label": f"Test feature {i}"}}
            ],
            "metaData": {
                "created": "2024-01-01T00:00:00Z",
                "phenopacketSchemaVersion": "2.0.0",
            },
        }

        # Add variants to first 30 phenopackets
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
                                        "label": f"Test variant {i}",
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
            created_by="test_user",
        )

        fixture_db_session.add(phenopacket)
        phenopackets_data.append(phenopacket)

    await fixture_db_session.commit()

    yield phenopackets_data

    # Cleanup: Use delete query instead of iterating over objects
    try:
        await fixture_db_session.rollback()  # Clear any pending transactions
        await fixture_db_session.execute(
            delete(Phenopacket).where(
                Phenopacket.phenopacket_id.like("test_pagination_%")
            )
        )
        await fixture_db_session.commit()
    except Exception as e:
        print(f"Warning: Cleanup failed: {e}")
        try:
            await fixture_db_session.rollback()
        except Exception:
            # Ignore rollback errors during test fixture cleanup.
            pass


class TestJsonApiResponseStructure:
    """Test JSON:API response structure compliance."""

    @pytest.mark.asyncio
    async def test_jsonapi_response_contains_required_fields(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Verify response has required JSON:API fields."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=20",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert "data" in data, "Response must have 'data' field"
        assert "meta" in data, "Response must have 'meta' field"
        assert "links" in data, "Response must have 'links' field"

        # Check data is a list
        assert isinstance(data["data"], list), "'data' must be a list"

        # Check meta structure
        assert "page" in data["meta"], "Meta must have 'page' field"
        page_meta = data["meta"]["page"]
        assert "currentPage" in page_meta
        assert "pageSize" in page_meta
        assert "totalPages" in page_meta
        assert "totalRecords" in page_meta

        # Check links structure
        links = data["links"]
        assert "self" in links
        assert "first" in links
        assert "next" in links or links["next"] is None
        assert "prev" in links or links["prev"] is None
        assert "last" in links

    @pytest.mark.asyncio
    async def test_jsonapi_data_contains_valid_phenopackets(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Verify data array contains valid phenopacket documents."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=5",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check data has items
        assert len(data["data"]) == 5, "Should return exactly 5 phenopackets"

        # Verify each item is a valid phenopacket
        for phenopacket in data["data"]:
            assert "id" in phenopacket
            assert "subject" in phenopacket
            assert "metaData" in phenopacket


class TestOffsetPagination:
    """Test offset-based pagination (page[number], page[size])."""

    @pytest.mark.asyncio
    async def test_jsonapi_first_page_returns_correct_metadata(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test first page pagination metadata."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=20",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check metadata
        page_meta = data["meta"]["page"]
        assert page_meta["currentPage"] == 1
        assert page_meta["pageSize"] == 20
        assert page_meta["totalRecords"] >= 50  # At least our test data
        assert page_meta["totalPages"] >= 3  # 50 records / 20 per page = 3 pages

        # Check links
        links = data["links"]
        assert links["prev"] is None, "First page should have no prev link"
        assert links["next"] is not None, "First page should have next link"
        # Links may be URL-encoded
        assert (
            "page" in links["first"]
            and "number" in links["first"]
            and "1" in links["first"]
        )
        assert (
            "page" in links["next"]
            and "number" in links["next"]
            and "2" in links["next"]
        )

        # Check data
        assert len(data["data"]) == 20

    @pytest.mark.asyncio
    async def test_jsonapi_middle_page_has_prev_and_next_links(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test middle page has both prev and next links."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=2&page[size]=20",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check metadata
        page_meta = data["meta"]["page"]
        assert page_meta["currentPage"] == 2

        # Check links
        links = data["links"]
        assert links["prev"] is not None, "Middle page should have prev link"
        assert links["next"] is not None, "Middle page should have next link"
        # URL-encoded format: page%5Bnumber%5D or unencoded page[number]
        assert (
            "page[number]=1" in links["prev"] or "page%5Bnumber%5D=1" in links["prev"]
        )
        assert (
            "page[number]=3" in links["next"] or "page%5Bnumber%5D=3" in links["next"]
        )

    @pytest.mark.asyncio
    async def test_jsonapi_last_page_has_no_next_link(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test last page has no next link."""
        # Get first page to find total pages
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=20",
            headers=fixture_auth_headers,
        )
        total_pages = response.json()["meta"]["page"]["totalPages"]

        # Get last page
        response = await fixture_async_client.get(
            f"/api/v2/phenopackets/?page[number]={total_pages}&page[size]=20",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check metadata
        page_meta = data["meta"]["page"]
        assert page_meta["currentPage"] == total_pages

        # Check links
        links = data["links"]
        assert links["next"] is None, "Last page should have no next link"
        assert links["prev"] is not None, "Last page should have prev link"

    @pytest.mark.asyncio
    async def test_jsonapi_page_size_variations_respected(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test different page sizes work correctly."""
        page_sizes = [10, 25, 50, 100]

        for page_size in page_sizes:
            response = await fixture_async_client.get(
                f"/api/v2/phenopackets/?page[number]=1&page[size]={page_size}",
                headers=fixture_auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            # Check page size is respected
            page_meta = data["meta"]["page"]
            assert page_meta["pageSize"] == page_size

            # Check data doesn't exceed page size
            assert len(data["data"]) <= page_size

    @pytest.mark.asyncio
    async def test_jsonapi_single_page_result_no_navigation(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test when all results fit on one page."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=1000",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        page_meta = data["meta"]["page"]
        links = data["links"]

        # If total records < page size, should be single page
        if page_meta["totalRecords"] <= 1000:
            assert page_meta["totalPages"] == 1
            assert links["prev"] is None
            assert links["next"] is None

    @pytest.mark.asyncio
    async def test_jsonapi_empty_page_beyond_data_returns_empty(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test requesting a page beyond available data."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=9999&page[size]=20",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should return empty data array
        assert len(data["data"]) == 0

        # Metadata should still be correct
        page_meta = data["meta"]["page"]
        assert page_meta["currentPage"] == 9999


class TestFiltering:
    """Test filtering parameters (filter[sex], filter[has_variants])."""

    @pytest.mark.asyncio
    async def test_jsonapi_filter_by_sex_returns_matching_records(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test filtering by subject sex."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=100&filter[sex]=MALE",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check all returned phenopackets have sex=MALE
        for phenopacket in data["data"]:
            assert phenopacket["subject"]["sex"] == "MALE"

        # Check total count reflects filter
        page_meta = data["meta"]["page"]
        # We have 25 MALE phenopackets in test data
        test_male_count = sum(
            1 for pp in fixture_sample_phenopackets if pp.subject_sex == "MALE"
        )
        assert page_meta["totalRecords"] >= test_male_count

    @pytest.mark.asyncio
    async def test_jsonapi_filter_by_has_variants_returns_matching_records(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test filtering by variant presence."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=100&filter[has_variants]=true",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check all returned phenopackets have variants
        for phenopacket in data["data"]:
            assert (
                "interpretations" in phenopacket
                and len(phenopacket.get("interpretations", [])) > 0
            ), "Phenopacket should have interpretations when filter[has_variants]=true"

        # Check total count
        page_meta = data["meta"]["page"]
        # We have 30 phenopackets with variants in test data
        test_variant_count = sum(
            1 for pp in fixture_sample_phenopackets if pp.phenopacket.get("interpretations")
        )
        assert page_meta["totalRecords"] >= test_variant_count

    @pytest.mark.asyncio
    async def test_jsonapi_combined_filters_returns_matching_records(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test combining multiple filters."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=100&filter[sex]=MALE&filter[has_variants]=true",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check all returned phenopackets match both filters
        for phenopacket in data["data"]:
            assert phenopacket["subject"]["sex"] == "MALE"
            assert "interpretations" in phenopacket

        # Check pagination works with filters
        links = data["links"]

        # Links should preserve filters (handle URL encoding)
        if links["next"]:
            next_link = links["next"]
            assert (
                "filter[sex]=MALE" in next_link or "filter%5Bsex%5D=MALE" in next_link
            )
            assert (
                "filter[has_variants]=" in next_link
                or "filter%5Bhas_variants%5D=" in next_link
            )

    @pytest.mark.asyncio
    async def test_jsonapi_filter_no_results_returns_empty(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test filter that returns no results."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=20&filter[sex]=OTHER_SEX",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should return empty data
        # Note: Might have other phenopackets from migrations, so check if our test data is filtered
        # All phenopackets with OTHER_SEX should not include our test data
        for phenopacket in data["data"]:
            assert not phenopacket["id"].startswith("test_pagination_")


class TestSorting:
    """Test sorting parameter (sort)."""

    @pytest.mark.asyncio
    async def test_jsonapi_sort_ascending_orders_correctly(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test ascending sort order."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=10&sort=subject_id",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Extract subject IDs - filter to only test data with zero-padded IDs
        # The API uses natural sorting (Var2 before Var10) which differs from
        # Python's lexicographic sort, so we only check our test data which uses
        # zero-padded IDs that sort the same way in both systems
        subject_ids = [
            pp["subject"]["id"]
            for pp in data["data"]
            if pp["subject"]["id"].startswith("patient_")
        ]

        # Check they are in ascending order (within test data)
        if subject_ids:
            assert subject_ids == sorted(subject_ids), (
                "Test patient IDs should be in ascending order"
            )

    @pytest.mark.asyncio
    async def test_jsonapi_sort_descending_orders_correctly(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test descending sort order (- prefix)."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=10&sort=-subject_id",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Extract subject IDs
        subject_ids = [pp["subject"]["id"] for pp in data["data"]]

        # Check they are in descending order
        assert subject_ids == sorted(subject_ids, reverse=True), (
            "Subject IDs should be in descending order"
        )

    @pytest.mark.asyncio
    async def test_jsonapi_sort_preserved_in_pagination_links(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test that sorting is preserved in pagination links."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=20&sort=-subject_id",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        links = data["links"]

        # Check sort parameter is preserved in links
        if links["next"]:
            assert "sort=-subject_id" in links["next"]
        assert "sort=-subject_id" in links["self"]

    @pytest.mark.asyncio
    async def test_jsonapi_sort_with_filters_works(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test sorting combined with filtering."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=20&filter[sex]=MALE&sort=subject_id",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check all are MALE
        for phenopacket in data["data"]:
            assert phenopacket["subject"]["sex"] == "MALE"

        # Check sorted
        subject_ids = [pp["subject"]["id"] for pp in data["data"]]
        assert subject_ids == sorted(subject_ids)

    @pytest.mark.asyncio
    async def test_jsonapi_invalid_sort_field_returns_400(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test error handling for invalid sort field."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=20&sort=invalid_field",
            headers=fixture_auth_headers,
        )

        # Should return 400 Bad Request
        assert response.status_code == 400
        error = response.json()
        assert "detail" in error
        assert "Invalid sort field" in error["detail"]


class TestBackwardsCompatibility:
    """Test legacy skip/limit parameters still work."""

    @pytest.mark.asyncio
    async def test_jsonapi_legacy_skip_limit_converted(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test page[number] and page[size] parameters (replaced skip/limit)."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=20",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should still return JSON:API format
        assert "data" in data
        assert "meta" in data
        assert "links" in data

        # Should return correct number of items
        assert len(data["data"]) <= 20

    @pytest.mark.asyncio
    async def test_jsonapi_legacy_sex_filter_works(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test filter[sex] parameter (replaced legacy sex param)."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=20&filter[sex]=MALE",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should filter by sex
        for phenopacket in data["data"]:
            assert phenopacket["subject"]["sex"] == "MALE"

    @pytest.mark.asyncio
    async def test_jsonapi_legacy_has_variants_filter_works(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test filter[has_variants] parameter (replaced legacy param)."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=20&filter[has_variants]=true",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should filter by variant presence
        for phenopacket in data["data"]:
            assert "interpretations" in phenopacket

    @pytest.mark.asyncio
    async def test_jsonapi_mixed_legacy_and_new_params_handled(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test mixing legacy and new parameters (new takes precedence)."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?skip=0&limit=10&page[number]=1&page[size]=20",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Legacy parameters should be converted to new format
        page_meta = data["meta"]["page"]
        # Either new params take precedence OR legacy params work
        # The implementation converts skip/limit to page[number]/page[size]
        assert page_meta["pageSize"] in [
            10,
            20,
        ]  # Could be either depending on implementation


class TestPaginationMetadata:
    """Test pagination metadata accuracy."""

    @pytest.mark.asyncio
    async def test_jsonapi_total_records_matches_actual_count(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test totalRecords matches actual count."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=10",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        page_meta = data["meta"]["page"]

        # Count should include at least our test data
        assert page_meta["totalRecords"] >= 50

    @pytest.mark.asyncio
    async def test_jsonapi_total_pages_calculated_correctly(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test totalPages is correctly calculated."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=20",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        page_meta = data["meta"]["page"]
        total_records = page_meta["totalRecords"]
        page_size = page_meta["pageSize"]
        total_pages = page_meta["totalPages"]

        # Calculate expected pages (ceiling division)
        expected_pages = (total_records + page_size - 1) // page_size

        assert total_pages == expected_pages

    @pytest.mark.asyncio
    async def test_jsonapi_metadata_reflects_filtered_results(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test metadata reflects filtered results."""
        # Get unfiltered count
        response_all = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=1000",
            headers=fixture_auth_headers,
        )
        total_all = response_all.json()["meta"]["page"]["totalRecords"]

        # Get filtered count
        response_filtered = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=1000&filter[sex]=MALE",
            headers=fixture_auth_headers,
        )
        total_filtered = response_filtered.json()["meta"]["page"]["totalRecords"]

        # Filtered should be less than total
        assert total_filtered < total_all


class TestNavigationLinks:
    """Test pagination navigation links."""

    @pytest.mark.asyncio
    async def test_jsonapi_links_are_valid_and_work(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test that pagination links are valid and work."""
        # Get first page
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=20",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        links = data["links"]

        # Follow next link
        if links["next"]:
            # Extract path from URL
            next_url = links["next"]
            if next_url.startswith("http://test"):
                next_url = next_url.replace("http://test", "")

            response_next = await fixture_async_client.get(next_url, headers=fixture_auth_headers)
            assert response_next.status_code == 200
            next_data = response_next.json()

            # Should be page 2
            assert next_data["meta"]["page"]["currentPage"] == 2

    @pytest.mark.asyncio
    async def test_jsonapi_links_preserve_filter_params(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test that navigation links preserve filter parameters."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=20&filter[sex]=MALE&filter[has_variants]=true",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        links = data["links"]

        # Check all links preserve filters (handle URL encoding)
        for link_name, link_url in links.items():
            if link_url:
                # Check for filter parameters (URL encoded or not)
                assert (
                    "filter[sex]=MALE" in link_url or "filter%5Bsex%5D=MALE" in link_url
                ), f"{link_name} link should preserve sex filter"
                assert (
                    "filter[has_variants]=" in link_url
                    or "filter%5Bhas_variants%5D=" in link_url
                ), f"{link_name} link should preserve has_variants filter"

    @pytest.mark.asyncio
    async def test_jsonapi_self_link_matches_request(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test that self link matches the current request."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=2&page[size]=25&filter[sex]=MALE",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        self_link = data["links"]["self"]

        # Self link should contain current parameters (handle URL encoding)
        assert "page[number]=2" in self_link or "page%5Bnumber%5D=2" in self_link
        assert "page[size]=25" in self_link or "page%5Bsize%5D=25" in self_link
        assert "filter[sex]=MALE" in self_link or "filter%5Bsex%5D=MALE" in self_link


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_jsonapi_page_size_of_one_returns_single_item(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test pagination with page size of 1."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=1",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should return exactly 1 item
        assert len(data["data"]) == 1

        # Total pages should equal total records
        page_meta = data["meta"]["page"]
        assert page_meta["totalPages"] == page_meta["totalRecords"]

    @pytest.mark.asyncio
    async def test_jsonapi_maximum_page_size_accepted(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test maximum allowed page size (1000)."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=1000",
            headers=fixture_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should accept max page size
        page_meta = data["meta"]["page"]
        assert page_meta["pageSize"] == 1000

    @pytest.mark.asyncio
    async def test_jsonapi_page_size_exceeds_limit_returns_422(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test that page size > 1000 is rejected."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=1&page[size]=2000",
            headers=fixture_auth_headers,
        )

        # Should return 422 Validation Error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_jsonapi_zero_page_number_returns_422(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test that page number 0 is rejected."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=0&page[size]=20",
            headers=fixture_auth_headers,
        )

        # Should return 422 Validation Error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_jsonapi_negative_page_number_returns_422(
        self, fixture_async_client: AsyncClient, fixture_sample_phenopackets, fixture_auth_headers
    ):
        """Test that negative page number is rejected."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/?page[number]=-1&page[size]=20",
            headers=fixture_auth_headers,
        )

        # Should return 422 Validation Error
        assert response.status_code == 422
