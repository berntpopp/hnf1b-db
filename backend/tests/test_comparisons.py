"""Tests for variant type comparison endpoints and statistical calculations."""

import pytest
from scipy import stats

from app.phenopackets.routers.comparisons import (
    calculate_cohens_h,
    calculate_statistical_test,
)


class TestStatisticalFunctions:
    """Test statistical calculation functions."""

    def test_calculate_statistical_test_chi_square(self):
        """Test Chi-square test is used when expected frequencies >= 5."""
        # Large sample sizes should use Chi-square
        # Example: 100 present vs 50 absent in group1, 80 present vs 60 absent in group2
        p_value, test_used = calculate_statistical_test(
            group1_present=100,
            group1_absent=50,
            group2_present=80,
            group2_absent=60,
        )

        assert test_used == "chi_square"
        assert isinstance(p_value, float)
        assert 0.0 <= p_value <= 1.0

        # Manually verify with scipy
        contingency_table = [[100, 50], [80, 60]]
        expected_chi2, expected_p, _, _ = stats.chi2_contingency(contingency_table)
        assert abs(p_value - expected_p) < 0.0001

    def test_calculate_statistical_test_fisher_exact(self):
        """Test Fisher's exact test is used for small samples."""
        # Small sample sizes should use Fisher's exact
        # Example: 3 present vs 2 absent in group1, 1 present vs 4 absent in group2
        p_value, test_used = calculate_statistical_test(
            group1_present=3, group1_absent=2, group2_present=1, group2_absent=4
        )

        assert test_used == "fisher_exact"
        assert isinstance(p_value, float)
        assert 0.0 <= p_value <= 1.0

        # Manually verify with scipy
        contingency_table = [[3, 2], [1, 4]]
        _, expected_p = stats.fisher_exact(contingency_table)
        assert abs(p_value - expected_p) < 0.0001

    def test_calculate_statistical_test_edge_case_all_zeros(self):
        """Test handling of edge case with all zeros."""
        p_value, test_used = calculate_statistical_test(
            group1_present=0, group1_absent=0, group2_present=0, group2_absent=0
        )

        assert test_used == "none"
        assert p_value == 1.0

    def test_calculate_statistical_test_boundary_expected_freq(self):
        """Test boundary case where expected frequency is exactly 5."""
        # Design a case where expected frequencies are at the threshold
        # Total = 100, row1 = 60, row2 = 40, col1 = 50, col2 = 50
        # Expected: (60*50)/100 = 30, (60*50)/100 = 30, (40*50)/100 = 20, (40*50)/100 = 20
        # All >= 5, so should use Chi-square
        p_value, test_used = calculate_statistical_test(
            group1_present=30, group1_absent=30, group2_present=20, group2_absent=20
        )

        assert test_used == "chi_square"

    def test_calculate_statistical_test_significant_difference(self):
        """Test with data that should show significant difference."""
        # Very different proportions: 90% vs 10%
        p_value, test_used = calculate_statistical_test(
            group1_present=90,
            group1_absent=10,
            group2_present=10,
            group2_absent=90,
        )

        assert test_used == "chi_square"
        assert p_value < 0.001  # Should be highly significant

    def test_calculate_statistical_test_no_difference(self):
        """Test with identical proportions (should not be significant)."""
        # Identical proportions: 50% vs 50%
        p_value, test_used = calculate_statistical_test(
            group1_present=50, group1_absent=50, group2_present=50, group2_absent=50
        )

        assert test_used == "chi_square"
        assert p_value > 0.05  # Should not be significant

    def test_calculate_cohens_h_identical_proportions(self):
        """Test Cohen's h with identical proportions."""
        effect_size = calculate_cohens_h(p1=0.5, p2=0.5)

        assert effect_size == 0.0

    def test_calculate_cohens_h_small_effect(self):
        """Test Cohen's h with small effect size."""
        # Small effect: h ≈ 0.2
        # For example, 50% vs 55%
        effect_size = calculate_cohens_h(p1=0.50, p2=0.55)

        assert 0.1 < effect_size < 0.3  # Should be small effect

    def test_calculate_cohens_h_medium_effect(self):
        """Test Cohen's h with medium effect size."""
        # Medium effect: h ≈ 0.5
        # For example, 50% vs 70%
        effect_size = calculate_cohens_h(p1=0.50, p2=0.70)

        assert 0.4 < effect_size < 0.6  # Should be medium effect

    def test_calculate_cohens_h_large_effect(self):
        """Test Cohen's h with large effect size."""
        # Large effect: h ≈ 0.8
        # For example, 30% vs 70%
        effect_size = calculate_cohens_h(p1=0.30, p2=0.70)

        assert effect_size > 0.7  # Should be large effect

    def test_calculate_cohens_h_extreme_difference(self):
        """Test Cohen's h with extreme difference."""
        # Maximum difference: 0% vs 100%
        effect_size = calculate_cohens_h(p1=0.0, p2=1.0)

        # Maximum Cohen's h is π (approximately 3.14)
        assert effect_size > 3.0

    def test_calculate_cohens_h_edge_cases(self):
        """Test Cohen's h with edge case proportions."""
        # Test with 0%
        effect_size_zero = calculate_cohens_h(p1=0.0, p2=0.0)
        assert effect_size_zero == 0.0

        # Test with 100%
        effect_size_one = calculate_cohens_h(p1=1.0, p2=1.0)
        assert effect_size_one == 0.0

        # Test with values outside [0,1] (should be clamped)
        effect_size_invalid = calculate_cohens_h(p1=-0.1, p2=1.1)
        assert isinstance(effect_size_invalid, float)

    def test_calculate_cohens_h_symmetry(self):
        """Test that Cohen's h is symmetric (h(p1,p2) = h(p2,p1))."""
        h1 = calculate_cohens_h(p1=0.3, p2=0.7)
        h2 = calculate_cohens_h(p1=0.7, p2=0.3)

        assert abs(h1 - h2) < 0.0001


@pytest.mark.asyncio
class TestComparisonEndpoint:
    """Test the variant type comparison API endpoint."""

    async def test_compare_truncating_vs_non_truncating(self, async_client, db_session):
        """Test truncating vs non-truncating comparison endpoint."""
        response = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "limit": 10,
                "min_prevalence": 0.05,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "group1_name" in data
        assert "group2_name" in data
        assert "group1_count" in data
        assert "group2_count" in data
        assert "phenotypes" in data
        assert "metadata" in data

        # Check group names
        assert data["group1_name"] == "Truncating"
        assert data["group2_name"] == "Non-truncating"

        # Check metadata
        assert data["metadata"]["comparison_type"] == "truncating_vs_non_truncating"
        assert "significant_count" in data["metadata"]
        assert "total_phenotypes_compared" in data["metadata"]

        # Check phenotypes array
        phenotypes = data["phenotypes"]
        assert isinstance(phenotypes, list)
        assert len(phenotypes) <= 10  # Respects limit

        # Check each phenotype has required fields
        if phenotypes:
            phenotype = phenotypes[0]
            assert "hpo_id" in phenotype
            assert "hpo_label" in phenotype
            assert "group1_present" in phenotype
            assert "group1_absent" in phenotype
            assert "group1_total" in phenotype
            assert "group1_percentage" in phenotype
            assert "group2_present" in phenotype
            assert "group2_absent" in phenotype
            assert "group2_total" in phenotype
            assert "group2_percentage" in phenotype
            assert "p_value" in phenotype
            assert "test_used" in phenotype
            assert "significant" in phenotype
            assert "effect_size" in phenotype

            # Validate data types
            assert isinstance(phenotype["group1_present"], int)
            assert isinstance(phenotype["group1_percentage"], float)
            assert isinstance(phenotype["p_value"], (float, type(None)))
            assert isinstance(phenotype["significant"], bool)
            assert phenotype["test_used"] in ["chi_square", "fisher_exact", "none"]

            # Validate percentages are in valid range
            assert 0.0 <= phenotype["group1_percentage"] <= 100.0
            assert 0.0 <= phenotype["group2_percentage"] <= 100.0

    async def test_compare_cnv_vs_point_mutation(self, async_client, db_session):
        """Test CNV vs point mutation comparison endpoint."""
        response = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={"comparison": "cnv_vs_point_mutation", "limit": 10},
        )

        assert response.status_code == 200
        data = response.json()

        # Check group names
        assert data["group1_name"] == "CNVs (17q del/dup)"
        assert data["group2_name"] == "Point mutations"

        # Check metadata
        assert data["metadata"]["comparison_type"] == "cnv_vs_point_mutation"

    async def test_compare_with_different_sort_orders(self, async_client, db_session):
        """Test different sorting options."""
        # Sort by p-value (default)
        response_pvalue = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={"comparison": "truncating_vs_non_truncating", "sort_by": "p_value"},
        )
        assert response_pvalue.status_code == 200
        data_pvalue = response_pvalue.json()

        # Sort by effect size
        response_effect = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "sort_by": "effect_size",
            },
        )
        assert response_effect.status_code == 200
        data_effect = response_effect.json()

        # Sort by prevalence difference
        response_prev = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "sort_by": "prevalence_diff",
            },
        )
        assert response_prev.status_code == 200
        data_prev = response_prev.json()

        # Verify sorting worked (if phenotypes exist)
        if data_pvalue["phenotypes"]:
            # p-value sort: should be ascending
            p_values = [
                p["p_value"]
                for p in data_pvalue["phenotypes"]
                if p["p_value"] is not None
            ]
            if len(p_values) > 1:
                assert p_values == sorted(p_values)

        if data_effect["phenotypes"] and len(data_effect["phenotypes"]) > 1:
            # effect size sort: should be descending
            effect_sizes = [
                p["effect_size"]
                for p in data_effect["phenotypes"]
                if p["effect_size"] is not None
            ]
            if len(effect_sizes) > 1:
                assert effect_sizes == sorted(effect_sizes, reverse=True)

    async def test_compare_with_min_prevalence_filter(self, async_client, db_session):
        """Test minimum prevalence filtering."""
        # Low threshold (should return more results)
        response_low = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "min_prevalence": 0.01,
                "limit": 50,
            },
        )
        assert response_low.status_code == 200
        data_low = response_low.json()

        # High threshold (should return fewer results)
        response_high = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "min_prevalence": 0.5,
                "limit": 50,
            },
        )
        assert response_high.status_code == 200
        data_high = response_high.json()

        # High threshold should have fewer or equal results
        assert len(data_high["phenotypes"]) <= len(data_low["phenotypes"])

    async def test_compare_with_limit_parameter(self, async_client, db_session):
        """Test limit parameter."""
        response = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={"comparison": "truncating_vs_non_truncating", "limit": 5},
        )

        assert response.status_code == 200
        data = response.json()

        # Should respect limit
        assert len(data["phenotypes"]) <= 5

    async def test_compare_invalid_comparison_type(self, async_client, db_session):
        """Test with invalid comparison type."""
        response = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={"comparison": "invalid_comparison"},
        )

        # Should return 422 validation error
        assert response.status_code == 422

    async def test_compare_invalid_sort_by(self, async_client, db_session):
        """Test with invalid sort_by parameter."""
        response = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "sort_by": "invalid_sort",
            },
        )

        # Should return 422 validation error
        assert response.status_code == 422

    async def test_compare_invalid_prevalence_range(self, async_client, db_session):
        """Test with invalid prevalence values."""
        # Prevalence < 0
        response_low = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "min_prevalence": -0.1,
            },
        )
        assert response_low.status_code == 422

        # Prevalence > 1
        response_high = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "min_prevalence": 1.5,
            },
        )
        assert response_high.status_code == 422

    async def test_compare_limit_bounds(self, async_client, db_session):
        """Test limit parameter bounds."""
        # Limit < 1
        response_low = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={"comparison": "truncating_vs_non_truncating", "limit": 0},
        )
        assert response_low.status_code == 422

        # Limit > 100
        response_high = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={"comparison": "truncating_vs_non_truncating", "limit": 101},
        )
        assert response_high.status_code == 422

    async def test_compare_counts_consistency(self, async_client, db_session):
        """Test that counts are consistent."""
        response = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={"comparison": "truncating_vs_non_truncating"},
        )

        assert response.status_code == 200
        data = response.json()

        # Check that present + absent = total for each phenotype
        for phenotype in data["phenotypes"]:
            group1_total = phenotype["group1_present"] + phenotype["group1_absent"]
            group2_total = phenotype["group2_present"] + phenotype["group2_absent"]

            # Total should match (allowing for individuals without the phenotype reported)
            assert group1_total <= data["group1_count"]
            assert group2_total <= data["group2_count"]

            # Percentages should match calculations
            if phenotype["group1_total"] > 0:
                expected_pct1 = (
                    phenotype["group1_present"] / phenotype["group1_total"] * 100
                )
                assert abs(phenotype["group1_percentage"] - expected_pct1) < 0.01

            if phenotype["group2_total"] > 0:
                expected_pct2 = (
                    phenotype["group2_present"] / phenotype["group2_total"] * 100
                )
                assert abs(phenotype["group2_percentage"] - expected_pct2) < 0.01
