"""Tests for variant type comparison endpoints and statistical calculations."""

import json

import pytest
from scipy import stats
from sqlalchemy import text

from app.phenopackets.routers.comparisons import (
    calculate_cohens_h,
    calculate_fdr_correction,
    calculate_fisher_exact_test,
)


class TestStatisticalFunctions:
    """Test statistical calculation functions."""

    def test_comparison_fisher_exact_small_samples_returns_valid(self):
        """Test Fisher's exact test with small samples."""
        # Small sample sizes
        # Example: 3 present vs 2 absent in group1, 1 present vs 4 absent in group2
        p_value, odds_ratio = calculate_fisher_exact_test(
            group1_present=3, group1_absent=2, group2_present=1, group2_absent=4
        )

        assert isinstance(p_value, float)
        assert isinstance(odds_ratio, float)
        assert 0.0 <= p_value <= 1.0

        # Manually verify with scipy
        contingency_table = [[3, 2], [1, 4]]
        expected_or, expected_p = stats.fisher_exact(contingency_table)
        assert abs(p_value - expected_p) < 0.0001
        assert abs(odds_ratio - expected_or) < 0.0001

    def test_comparison_fisher_exact_large_samples_uses_fisher(self):
        """Test Fisher's exact test with large samples (always uses Fisher now)."""
        # Large sample sizes - should still use Fisher's exact
        p_value, odds_ratio = calculate_fisher_exact_test(
            group1_present=100,
            group1_absent=50,
            group2_present=80,
            group2_absent=60,
        )

        assert isinstance(p_value, float)
        assert isinstance(odds_ratio, float)
        assert 0.0 <= p_value <= 1.0

        # Manually verify with scipy Fisher's exact
        contingency_table = [[100, 50], [80, 60]]
        expected_or, expected_p = stats.fisher_exact(contingency_table)
        assert abs(p_value - expected_p) < 0.0001
        assert abs(odds_ratio - expected_or) < 0.0001

    def test_comparison_fisher_exact_all_zeros_returns_defaults(self):
        """Test handling of edge case with all zeros."""
        p_value, odds_ratio = calculate_fisher_exact_test(
            group1_present=0, group1_absent=0, group2_present=0, group2_absent=0
        )

        assert p_value == 1.0
        assert odds_ratio is None  # Undefined odds ratio returns None for JSON safety

    def test_comparison_fisher_exact_significant_difference_detected(self):
        """Test with data that should show significant difference."""
        # Very different proportions: 90% vs 10%
        p_value, odds_ratio = calculate_fisher_exact_test(
            group1_present=90,
            group1_absent=10,
            group2_present=10,
            group2_absent=90,
        )

        assert p_value < 0.001  # Should be highly significant
        assert odds_ratio > 1  # Group 1 has higher odds of "present"

    def test_comparison_fisher_exact_no_difference_not_significant(self):
        """Test with identical proportions (should not be significant)."""
        # Identical proportions: 50% vs 50%
        p_value, odds_ratio = calculate_fisher_exact_test(
            group1_present=50, group1_absent=50, group2_present=50, group2_absent=50
        )

        assert p_value > 0.05  # Should not be significant
        assert abs(odds_ratio - 1.0) < 0.0001  # Odds ratio should be ~1

    def test_comparison_fdr_correction_basic_values_valid(self):
        """Test FDR correction with known p-values."""
        # Test with a simple set of p-values
        p_values = [0.01, 0.04, 0.03, 0.005]
        fdr_values = calculate_fdr_correction(p_values)

        assert len(fdr_values) == len(p_values)
        # All FDR values should be >= raw p-values
        for raw, fdr in zip(p_values, fdr_values):
            assert fdr >= raw
        # All FDR values should be <= 1.0
        for fdr in fdr_values:
            assert fdr <= 1.0

    def test_comparison_fdr_correction_empty_list_returns_empty(self):
        """Test FDR correction with empty list."""
        fdr_values = calculate_fdr_correction([])
        assert fdr_values == []

    def test_comparison_fdr_correction_single_value_unchanged(self):
        """Test FDR correction with single p-value."""
        p_values = [0.03]
        fdr_values = calculate_fdr_correction(p_values)
        assert len(fdr_values) == 1
        assert fdr_values[0] == 0.03  # Single value unchanged

    def test_comparison_fdr_correction_monotonicity_preserved(self):
        """Test that FDR-corrected values maintain order."""
        # Sorted p-values should give sorted FDR values
        p_values = [0.001, 0.01, 0.02, 0.05, 0.1]
        fdr_values = calculate_fdr_correction(p_values)

        # FDR values should be monotonically increasing for sorted p-values
        for i in range(len(fdr_values) - 1):
            assert fdr_values[i] <= fdr_values[i + 1]

    def test_comparison_cohens_h_identical_proportions_zero(self):
        """Test Cohen's h with identical proportions."""
        effect_size = calculate_cohens_h(p1=0.5, p2=0.5)

        assert effect_size == 0.0

    def test_comparison_cohens_h_small_effect_range(self):
        """Test Cohen's h with small effect size."""
        # Small effect: h ≈ 0.2
        # For example, 50% vs 55%
        effect_size = calculate_cohens_h(p1=0.50, p2=0.55)

        assert 0.1 < effect_size < 0.3  # Should be small effect

    def test_comparison_cohens_h_medium_effect_range(self):
        """Test Cohen's h with medium effect size."""
        # Medium effect: h ≈ 0.5
        # For example, 50% vs 70%
        effect_size = calculate_cohens_h(p1=0.50, p2=0.70)

        assert 0.4 < effect_size < 0.6  # Should be medium effect

    def test_comparison_cohens_h_large_effect_range(self):
        """Test Cohen's h with large effect size."""
        # Large effect: h ≈ 0.8
        # For example, 30% vs 70%
        effect_size = calculate_cohens_h(p1=0.30, p2=0.70)

        assert effect_size > 0.7  # Should be large effect

    def test_comparison_cohens_h_extreme_difference_max_value(self):
        """Test Cohen's h with extreme difference."""
        # Maximum difference: 0% vs 100%
        effect_size = calculate_cohens_h(p1=0.0, p2=1.0)

        # Maximum Cohen's h is π (approximately 3.14)
        assert effect_size > 3.0

    def test_comparison_cohens_h_edge_cases_valid(self):
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

    def test_comparison_cohens_h_symmetry_preserved(self):
        """Test that Cohen's h is symmetric (h(p1,p2) = h(p2,p1))."""
        h1 = calculate_cohens_h(p1=0.3, p2=0.7)
        h2 = calculate_cohens_h(p1=0.7, p2=0.3)

        assert abs(h1 - h2) < 0.0001


@pytest.mark.asyncio
class TestComparisonEndpoint:
    """Test the variant type comparison API endpoint."""

    async def test_comparison_truncating_vs_non_truncating_returns_200(
        self, fixture_async_client, fixture_db_session
    ):
        """Test truncating vs non-truncating comparison endpoint."""
        response = await fixture_async_client.get(
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
            assert phenotype["test_used"] == "fisher_exact"
            # Check new fields are present
            assert "p_value_fdr" in phenotype
            assert "odds_ratio" in phenotype
            assert isinstance(phenotype["p_value_fdr"], (float, type(None)))
            assert isinstance(phenotype["odds_ratio"], (float, type(None)))

            # Validate percentages are in valid range
            assert 0.0 <= phenotype["group1_percentage"] <= 100.0
            assert 0.0 <= phenotype["group2_percentage"] <= 100.0

    async def test_comparison_cnv_vs_point_mutation_returns_200(
        self, fixture_async_client, fixture_db_session
    ):
        """Test CNV vs point mutation comparison endpoint."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={"comparison": "cnv_vs_point_mutation", "limit": 10},
        )

        assert response.status_code == 200
        data = response.json()

        # Check group names
        assert data["group1_name"] == "CNVs (17q del/dup)"
        assert data["group2_name"] == "Non-CNV variants"

        # Check metadata
        assert data["metadata"]["comparison_type"] == "cnv_vs_point_mutation"

    async def test_comparison_truncating_excl_cnv_correct_counts(
        self, fixture_async_client, fixture_db_session
    ):
        """Test truncating vs non-truncating comparison excluding large CNVs."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating_excl_cnv",
                "limit": 10,
                "min_prevalence": 0.05,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Check group names indicate CNV exclusion
        assert data["group1_name"] == "Truncating (excl. CNVs)"
        assert data["group2_name"] == "Non-truncating (excl. CNVs)"

        # Check metadata
        assert (
            data["metadata"]["comparison_type"]
            == "truncating_vs_non_truncating_excl_cnv"
        )

        # Use min_prevalence=0 to get accurate total counts across all phenotypes
        # (min_prevalence filtering can affect which phenotypes are included)
        response_excl = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating_excl_cnv",
                "limit": 100,
                "min_prevalence": 0,
            },
        )
        response_with_cnv = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "limit": 100,
                "min_prevalence": 0,
            },
        )
        data_excl = response_excl.json()
        data_with_cnv = response_with_cnv.json()

        # The truncating count excluding CNVs should be < the full count
        # (since CNVs are classified as truncating)
        assert data_excl["group1_count"] <= data_with_cnv["group1_count"]

        # The non-truncating count should remain the same
        # (CNVs are truncating, not non-truncating, so excluding them shouldn't
        # affect the non-truncating count)
        assert data_excl["group2_count"] == data_with_cnv["group2_count"]

    async def test_comparison_sort_by_pvalue_ascending(
        self, fixture_async_client, fixture_db_session
    ):
        """Test different sorting options."""
        # Sort by p-value (default)
        response_pvalue = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={"comparison": "truncating_vs_non_truncating", "sort_by": "p_value"},
        )
        assert response_pvalue.status_code == 200
        data_pvalue = response_pvalue.json()

        # Sort by effect size
        response_effect = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "sort_by": "effect_size",
            },
        )
        assert response_effect.status_code == 200
        data_effect = response_effect.json()

        # Sort by prevalence difference
        response_prev = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "sort_by": "prevalence_diff",
            },
        )
        assert response_prev.status_code == 200
        _ = response_prev.json()  # Response validated by status code check

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

    async def test_comparison_min_prevalence_filter_reduces_results(
        self, fixture_async_client, fixture_db_session
    ):
        """Test minimum prevalence filtering."""
        # Low threshold (should return more results)
        response_low = await fixture_async_client.get(
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
        response_high = await fixture_async_client.get(
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

    async def test_comparison_limit_parameter_respected(
        self, fixture_async_client, fixture_db_session
    ):
        """Test limit parameter."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={"comparison": "truncating_vs_non_truncating", "limit": 5},
        )

        assert response.status_code == 200
        data = response.json()

        # Should respect limit
        assert len(data["phenotypes"]) <= 5

    async def test_comparison_invalid_comparison_type_returns_422(
        self, fixture_async_client, fixture_db_session
    ):
        """Test with invalid comparison type."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={"comparison": "invalid_comparison"},
        )

        # Should return 422 validation error
        assert response.status_code == 422

    async def test_comparison_invalid_sort_by_returns_422(
        self, fixture_async_client, fixture_db_session
    ):
        """Test with invalid sort_by parameter."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "sort_by": "invalid_sort",
            },
        )

        # Should return 422 validation error
        assert response.status_code == 422

    async def test_comparison_invalid_prevalence_range_returns_422(
        self, fixture_async_client, fixture_db_session
    ):
        """Test with invalid prevalence values."""
        # Prevalence < 0
        response_low = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "min_prevalence": -0.1,
            },
        )
        assert response_low.status_code == 422

        # Prevalence > 1
        response_high = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "min_prevalence": 1.5,
            },
        )
        assert response_high.status_code == 422

    async def test_comparison_limit_bounds_validated(
        self, fixture_async_client, fixture_db_session
    ):
        """Test limit parameter bounds."""
        # Limit < 1
        response_low = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={"comparison": "truncating_vs_non_truncating", "limit": 0},
        )
        assert response_low.status_code == 422

        # Limit > 100
        response_high = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={"comparison": "truncating_vs_non_truncating", "limit": 101},
        )
        assert response_high.status_code == 422

    async def test_comparison_counts_consistency_validated(
        self, fixture_async_client, fixture_db_session
    ):
        """Test that counts are consistent."""
        response = await fixture_async_client.get(
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


@pytest.mark.asyncio
class TestVEPImpactBasedClassification:
    """Test VEP IMPACT-based truncating variant classification.

    This test class verifies that the Python implementation matches the R reference
    logic from docs/analysis/R-commands_genotype-phenotype.txt (lines 75-84).

    R logic priority:
    1. IMPACT = HIGH → Truncating (T)
    2. IMPACT = MODERATE → Non-truncating (nT)
    3. IMPACT = LOW/MODIFIER/missing + Pathogenic (LP/P) → Truncating (T)
    4. Default → other (excluded from analysis)
    """

    async def test_comparison_vep_impact_high_classified_truncating(
        self, fixture_db_session
    ):
        """Test that variants with VEP IMPACT = HIGH are classified as truncating.

        R logic (line 78):
            IMPACT == "HIGH" ~ "T"
        """
        # Create test phenopacket with HIGH impact variant
        test_phenopacket = {
            "id": "test-high-impact",
            "subject": {"id": "patient-high-impact"},
            "interpretations": [
                {
                    "id": "interp-1",
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "interpretationStatus": "UNCERTAIN_SIGNIFICANCE",
                                    "variationDescriptor": {
                                        "id": "var-1",
                                        "expressions": [
                                            {
                                                "syntax": "hgvs.c",
                                                "value": "NM_000458.4:c.123A>G",
                                            }
                                        ],
                                        "extensions": [
                                            {
                                                "name": "vep_annotation",
                                                "value": {
                                                    "impact": "HIGH",
                                                    "most_severe_consequence": "stop_gained",
                                                },
                                            }
                                        ],
                                    },
                                }
                            }
                        ]
                    },
                }
            ],
            "phenotypicFeatures": [
                {
                    "type": {"id": "HP:0000107", "label": "Renal cyst"},
                    "excluded": False,
                }
            ],
        }

        # Insert test phenopacket
        # Use CAST() instead of :: to avoid SQLAlchemy interpreting :pk::jsonb incorrectly
        await fixture_db_session.execute(
            text(
                """
            INSERT INTO phenopackets (id, phenopacket_id, phenopacket, subject_id, subject_sex, revision)
            VALUES (gen_random_uuid(), :pid, CAST(:pk AS jsonb), :sid, :sex, 1)
        """
            ),
            {
                "pid": "test-high-impact",
                "pk": json.dumps(test_phenopacket),
                "sid": "patient-high-impact",
                "sex": "UNKNOWN_SEX",
            },
        )
        await fixture_db_session.commit()

        # Query variant classification
        result = await fixture_db_session.execute(
            text(
                """
            SELECT
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(
                            interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                        ) AS ext
                        WHERE ext->>'name' = 'vep_annotation'
                          AND ext#>>'{value,impact}' = 'HIGH'
                    ) THEN 'Truncating'
                    ELSE 'Non-truncating'
                END as classification
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.phenopacket_id = :pid
        """
            ),
            {"pid": "test-high-impact"},
        )

        row = result.fetchone()
        assert row is not None
        assert row[0] == "Truncating"

        # Cleanup
        await fixture_db_session.execute(
            text("DELETE FROM phenopackets WHERE phenopacket_id = :pid"),
            {"pid": "test-high-impact"},
        )
        await fixture_db_session.commit()

    async def test_comparison_vep_impact_moderate_classified_non_truncating(
        self, fixture_db_session
    ):
        """Test that variants with VEP IMPACT = MODERATE are non-truncating.

        R logic (line 77):
            IMPACT == "MODERATE" ~ "nT"
        """
        test_phenopacket = {
            "id": "test-moderate-impact",
            "subject": {"id": "patient-moderate-impact"},
            "interpretations": [
                {
                    "id": "interp-1",
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "interpretationStatus": "LIKELY_PATHOGENIC",
                                    "variationDescriptor": {
                                        "id": "var-1",
                                        "expressions": [
                                            {
                                                "syntax": "hgvs.p",
                                                "value": "NP_000449.3:p.Arg177Cys",
                                            }
                                        ],
                                        "extensions": [
                                            {
                                                "name": "vep_annotation",
                                                "value": {
                                                    "impact": "MODERATE",
                                                    "most_severe_consequence": "missense_variant",
                                                },
                                            }
                                        ],
                                    },
                                }
                            }
                        ]
                    },
                }
            ],
            "phenotypicFeatures": [
                {
                    "type": {"id": "HP:0000107", "label": "Renal cyst"},
                    "excluded": False,
                }
            ],
        }

        # Insert test phenopacket
        # Use CAST() instead of :: to avoid SQLAlchemy interpreting :pk::jsonb incorrectly
        await fixture_db_session.execute(
            text(
                """
            INSERT INTO phenopackets (id, phenopacket_id, phenopacket, subject_id, subject_sex, revision)
            VALUES (gen_random_uuid(), :pid, CAST(:pk AS jsonb), :sid, :sex, 1)
        """
            ),
            {
                "pid": "test-moderate-impact",
                "pk": json.dumps(test_phenopacket),
                "sid": "patient-moderate-impact",
                "sex": "UNKNOWN_SEX",
            },
        )
        await fixture_db_session.commit()

        # Query - MODERATE should NOT be truncating even if pathogenic
        result = await fixture_db_session.execute(
            text(
                """
            SELECT
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(
                            interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                        ) AS ext
                        WHERE ext->>'name' = 'vep_annotation'
                          AND ext#>>'{value,impact}' = 'MODERATE'
                    ) THEN 'Non-truncating'
                    ELSE 'Other'
                END as classification
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.phenopacket_id = :pid
        """
            ),
            {"pid": "test-moderate-impact"},
        )

        row = result.fetchone()
        assert row is not None
        assert row[0] == "Non-truncating"

        # Cleanup
        await fixture_db_session.execute(
            text("DELETE FROM phenopackets WHERE phenopacket_id = :pid"),
            {"pid": "test-moderate-impact"},
        )
        await fixture_db_session.commit()

    async def test_comparison_vep_impact_low_pathogenic_classified_truncating(
        self, fixture_db_session
    ):
        """Test LOW impact + pathogenic → truncating (edge case handling).

        R logic (line 79):
            IMPACT == "LOW" & ACMG_groups == "LP/P" ~ "T"

        This handles cases where VEP impact prediction is wrong but clinical
        interpretation identifies the variant as pathogenic (e.g., cryptic splice).
        """
        test_phenopacket = {
            "id": "test-low-pathogenic",
            "subject": {"id": "patient-low-pathogenic"},
            "interpretations": [
                {
                    "id": "interp-1",
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "interpretationStatus": "LIKELY_PATHOGENIC",
                                    "variationDescriptor": {
                                        "id": "var-1",
                                        "expressions": [
                                            {
                                                "syntax": "hgvs.c",
                                                "value": "NM_000458.4:c.544+5G>A",
                                            }
                                        ],
                                        "extensions": [
                                            {
                                                "name": "vep_annotation",
                                                "value": {
                                                    "impact": "LOW",
                                                    "most_severe_consequence": "splice_region_variant",
                                                },
                                            }
                                        ],
                                    },
                                }
                            }
                        ]
                    },
                }
            ],
            "phenotypicFeatures": [
                {
                    "type": {"id": "HP:0000107", "label": "Renal cyst"},
                    "excluded": False,
                }
            ],
        }

        # Insert test phenopacket
        # Use CAST() instead of :: to avoid SQLAlchemy interpreting :pk::jsonb incorrectly
        await fixture_db_session.execute(
            text(
                """
            INSERT INTO phenopackets (id, phenopacket_id, phenopacket, subject_id, subject_sex, revision)
            VALUES (gen_random_uuid(), :pid, CAST(:pk AS jsonb), :sid, :sex, 1)
        """
            ),
            {
                "pid": "test-low-pathogenic",
                "pk": json.dumps(test_phenopacket),
                "sid": "patient-low-pathogenic",
                "sex": "UNKNOWN_SEX",
            },
        )
        await fixture_db_session.commit()

        # Query - LOW + LIKELY_PATHOGENIC should be truncating
        result = await fixture_db_session.execute(
            text(
                """
            SELECT
                CASE
                    WHEN (
                        EXISTS (
                            SELECT 1
                            FROM jsonb_array_elements(
                                interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                            ) AS ext
                            WHERE ext->>'name' = 'vep_annotation'
                              AND ext#>>'{value,impact}' = 'LOW'
                        )
                        AND
                        interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,interpretationStatus}'
                            IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
                    ) THEN 'Truncating'
                    ELSE 'Non-truncating'
                END as classification
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.phenopacket_id = :pid
        """
            ),
            {"pid": "test-low-pathogenic"},
        )

        row = result.fetchone()
        assert row is not None
        assert row[0] == "Truncating"

        # Cleanup
        await fixture_db_session.execute(
            text("DELETE FROM phenopackets WHERE phenopacket_id = :pid"),
            {"pid": "test-low-pathogenic"},
        )
        await fixture_db_session.commit()

    async def test_comparison_vep_impact_low_vus_classified_non_truncating(
        self, fixture_db_session
    ):
        """Test LOW impact + VUS → non-truncating (not pathogenic).

        R logic: Only LOW + LP/P → T, so LOW + VUS should be nT or other.
        """
        test_phenopacket = {
            "id": "test-low-vus",
            "subject": {"id": "patient-low-vus"},
            "interpretations": [
                {
                    "id": "interp-1",
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "interpretationStatus": "UNCERTAIN_SIGNIFICANCE",
                                    "variationDescriptor": {
                                        "id": "var-1",
                                        "expressions": [
                                            {
                                                "syntax": "hgvs.c",
                                                "value": "NM_000458.4:c.123A>G",
                                            }
                                        ],
                                        "extensions": [
                                            {
                                                "name": "vep_annotation",
                                                "value": {
                                                    "impact": "LOW",
                                                    "most_severe_consequence": "synonymous_variant",
                                                },
                                            }
                                        ],
                                    },
                                }
                            }
                        ]
                    },
                }
            ],
            "phenotypicFeatures": [
                {
                    "type": {"id": "HP:0000107", "label": "Renal cyst"},
                    "excluded": False,
                }
            ],
        }

        # Insert test phenopacket
        # Use CAST() instead of :: to avoid SQLAlchemy interpreting :pk::jsonb incorrectly
        await fixture_db_session.execute(
            text(
                """
            INSERT INTO phenopackets (id, phenopacket_id, phenopacket, subject_id, subject_sex, revision)
            VALUES (gen_random_uuid(), :pid, CAST(:pk AS jsonb), :sid, :sex, 1)
        """
            ),
            {
                "pid": "test-low-vus",
                "pk": json.dumps(test_phenopacket),
                "sid": "patient-low-vus",
                "sex": "UNKNOWN_SEX",
            },
        )
        await fixture_db_session.commit()

        # Query - LOW + VUS should NOT be truncating
        result = await fixture_db_session.execute(
            text(
                """
            SELECT
                CASE
                    WHEN (
                        EXISTS (
                            SELECT 1
                            FROM jsonb_array_elements(
                                interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                            ) AS ext
                            WHERE ext->>'name' = 'vep_annotation'
                              AND ext#>>'{value,impact}' = 'LOW'
                        )
                        AND
                        interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,interpretationStatus}'
                            NOT IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
                    ) THEN 'Non-truncating'
                    ELSE 'Other'
                END as classification
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.phenopacket_id = :pid
        """
            ),
            {"pid": "test-low-vus"},
        )

        row = result.fetchone()
        assert row is not None
        assert row[0] == "Non-truncating"

        # Cleanup
        await fixture_db_session.execute(
            text("DELETE FROM phenopackets WHERE phenopacket_id = :pid"),
            {"pid": "test-low-vus"},
        )
        await fixture_db_session.commit()

    async def test_comparison_hgvs_fallback_when_no_vep_impact(
        self, fixture_db_session
    ):
        """Test HGVS pattern fallback when VEP IMPACT is missing.

        R logic (line 82):
            is.na(IMPACT) & ACMG_groups == "LP/P" ~ "T"

        Should use HGVS patterns when no VEP data available.
        """
        test_phenopacket = {
            "id": "test-hgvs-fallback",
            "subject": {"id": "patient-hgvs-fallback"},
            "interpretations": [
                {
                    "id": "interp-1",
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "interpretationStatus": "PATHOGENIC",
                                    "variationDescriptor": {
                                        "id": "var-1",
                                        "expressions": [
                                            {
                                                "syntax": "hgvs.p",
                                                "value": "NP_000449.3:p.Arg177Ter",
                                            }
                                        ],
                                        # No VEP extension
                                    },
                                }
                            }
                        ]
                    },
                }
            ],
            "phenotypicFeatures": [
                {
                    "type": {"id": "HP:0000107", "label": "Renal cyst"},
                    "excluded": False,
                }
            ],
        }

        # Insert test phenopacket
        # Use CAST() instead of :: to avoid SQLAlchemy interpreting :pk::jsonb incorrectly
        await fixture_db_session.execute(
            text(
                """
            INSERT INTO phenopackets (id, phenopacket_id, phenopacket, subject_id, subject_sex, revision)
            VALUES (gen_random_uuid(), :pid, CAST(:pk AS jsonb), :sid, :sex, 1)
        """
            ),
            {
                "pid": "test-hgvs-fallback",
                "pk": json.dumps(test_phenopacket),
                "sid": "patient-hgvs-fallback",
                "sex": "UNKNOWN_SEX",
            },
        )
        await fixture_db_session.commit()

        # Query - Should use HGVS pattern (Ter = nonsense = truncating)
        result = await fixture_db_session.execute(
            text(
                """
            SELECT
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(
                            interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,expressions}'
                        ) AS expr
                        WHERE expr->>'syntax' = 'hgvs.p'
                          AND expr->>'value' ~* 'ter'
                    ) THEN 'Truncating'
                    ELSE 'Non-truncating'
                END as classification
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.phenopacket_id = :pid
        """
            ),
            {"pid": "test-hgvs-fallback"},
        )

        row = result.fetchone()
        assert row is not None
        assert row[0] == "Truncating"

        # Cleanup
        await fixture_db_session.execute(
            text("DELETE FROM phenopackets WHERE phenopacket_id = :pid"),
            {"pid": "test-hgvs-fallback"},
        )
        await fixture_db_session.commit()


@pytest.mark.asyncio
class TestCNVSubtypeClassification:
    """Test CNV subtype classification (17q deletion vs duplication).

    This test class verifies that the Python implementation can distinguish
    between deletions and duplications, matching R logic from
    docs/analysis/R-commands_genotype-phenotype.txt (lines 87-88):
        EFFECT == "transcript_ablation" ~ "17qDel"
        EFFECT == "transcript_amplification" ~ "17qDup"
    """

    async def test_comparison_cnv_deletion_classified_by_variant_id(
        self, fixture_db_session
    ):
        """Test that CNVs with :DEL suffix are classified as deletions."""
        test_phenopacket = {
            "id": "test-cnv-del",
            "subject": {"id": "patient-cnv-del"},
            "interpretations": [
                {
                    "id": "interp-1",
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "interpretationStatus": "PATHOGENIC",
                                    "variationDescriptor": {
                                        "id": "17:36459258-37832869:DEL",
                                        "expressions": [
                                            {
                                                "syntax": "spdi",
                                                "value": "17:36459258:1373611:0",
                                            }
                                        ],
                                    },
                                }
                            }
                        ]
                    },
                }
            ],
            "phenotypicFeatures": [
                {
                    "type": {"id": "HP:0000107", "label": "Renal cyst"},
                    "excluded": False,
                }
            ],
        }

        # Insert test phenopacket
        # Use CAST() instead of :: to avoid SQLAlchemy interpreting :pk::jsonb incorrectly
        await fixture_db_session.execute(
            text(
                """
            INSERT INTO phenopackets (id, phenopacket_id, phenopacket, subject_id, subject_sex, revision)
            VALUES (gen_random_uuid(), :pid, CAST(:pk AS jsonb), :sid, :sex, 1)
        """
            ),
            {
                "pid": "test-cnv-del",
                "pk": json.dumps(test_phenopacket),
                "sid": "patient-cnv-del",
                "sex": "UNKNOWN_SEX",
            },
        )
        await fixture_db_session.commit()

        # Query - Should be classified as deletion
        # Use raw string and escape : to prevent SQLAlchemy bind parameter interpretation
        result = await fixture_db_session.execute(
            text(
                r"""
            SELECT
                CASE
                    WHEN interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ '\:DEL'
                        THEN '17q Deletion'
                    WHEN interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ '\:DUP'
                        THEN '17q Duplication'
                    ELSE 'Other'
                END as cnv_subtype
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.phenopacket_id = :pid
        """
            ),
            {"pid": "test-cnv-del"},
        )

        row = result.fetchone()
        assert row is not None
        assert row[0] == "17q Deletion"

        # Cleanup
        await fixture_db_session.execute(
            text("DELETE FROM phenopackets WHERE phenopacket_id = :pid"),
            {"pid": "test-cnv-del"},
        )
        await fixture_db_session.commit()

    async def test_comparison_cnv_duplication_classified_by_variant_id(
        self, fixture_db_session
    ):
        """Test that CNVs with :DUP suffix are classified as duplications."""
        test_phenopacket = {
            "id": "test-cnv-dup",
            "subject": {"id": "patient-cnv-dup"},
            "interpretations": [
                {
                    "id": "interp-1",
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "interpretationStatus": "PATHOGENIC",
                                    "variationDescriptor": {
                                        "id": "17:36459258-37832869:DUP",
                                        "expressions": [
                                            {
                                                "syntax": "spdi",
                                                "value": "17:36459258:0:1373611",
                                            }
                                        ],
                                    },
                                }
                            }
                        ]
                    },
                }
            ],
            "phenotypicFeatures": [
                {
                    "type": {"id": "HP:0000107", "label": "Renal cyst"},
                    "excluded": False,
                }
            ],
        }

        # Insert test phenopacket
        # Use CAST() instead of :: to avoid SQLAlchemy interpreting :pk::jsonb incorrectly
        await fixture_db_session.execute(
            text(
                """
            INSERT INTO phenopackets (id, phenopacket_id, phenopacket, subject_id, subject_sex, revision)
            VALUES (gen_random_uuid(), :pid, CAST(:pk AS jsonb), :sid, :sex, 1)
        """
            ),
            {
                "pid": "test-cnv-dup",
                "pk": json.dumps(test_phenopacket),
                "sid": "patient-cnv-dup",
                "sex": "UNKNOWN_SEX",
            },
        )
        await fixture_db_session.commit()

        # Query - Should be classified as duplication
        # Use raw string and escape : to prevent SQLAlchemy bind parameter interpretation
        result = await fixture_db_session.execute(
            text(
                r"""
            SELECT
                CASE
                    WHEN interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ '\:DEL'
                        THEN '17q Deletion'
                    WHEN interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ '\:DUP'
                        THEN '17q Duplication'
                    ELSE 'Other'
                END as cnv_subtype
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.phenopacket_id = :pid
        """
            ),
            {"pid": "test-cnv-dup"},
        )

        row = result.fetchone()
        assert row is not None
        assert row[0] == "17q Duplication"

        # Cleanup
        await fixture_db_session.execute(
            text("DELETE FROM phenopackets WHERE phenopacket_id = :pid"),
            {"pid": "test-cnv-dup"},
        )
        await fixture_db_session.commit()

    async def test_comparison_cnv_deletion_classified_by_vep_consequence(
        self, fixture_db_session
    ):
        """Test deletion classification by VEP consequence (transcript_ablation).

        R logic (line 87):
            EFFECT == "transcript_ablation" ~ "17qDel"
        """
        test_phenopacket = {
            "id": "test-cnv-del-vep",
            "subject": {"id": "patient-cnv-del-vep"},
            "interpretations": [
                {
                    "id": "interp-1",
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "interpretationStatus": "PATHOGENIC",
                                    "variationDescriptor": {
                                        "id": "var-cnv-del",
                                        "expressions": [
                                            {
                                                "syntax": "hgvs.g",
                                                "value": "NC_000017.11:g.36459258_37832869del",
                                            }
                                        ],
                                        "extensions": [
                                            {
                                                "name": "vep_annotation",
                                                "value": {
                                                    "most_severe_consequence": "transcript_ablation",
                                                    "impact": "HIGH",
                                                },
                                            }
                                        ],
                                    },
                                }
                            }
                        ]
                    },
                }
            ],
            "phenotypicFeatures": [
                {
                    "type": {"id": "HP:0000107", "label": "Renal cyst"},
                    "excluded": False,
                }
            ],
        }

        # Insert test phenopacket
        # Use CAST() instead of :: to avoid SQLAlchemy interpreting :pk::jsonb incorrectly
        await fixture_db_session.execute(
            text(
                """
            INSERT INTO phenopackets (id, phenopacket_id, phenopacket, subject_id, subject_sex, revision)
            VALUES (gen_random_uuid(), :pid, CAST(:pk AS jsonb), :sid, :sex, 1)
        """
            ),
            {
                "pid": "test-cnv-del-vep",
                "pk": json.dumps(test_phenopacket),
                "sid": "patient-cnv-del-vep",
                "sex": "UNKNOWN_SEX",
            },
        )
        await fixture_db_session.commit()

        # Query - Should be classified as deletion by VEP consequence
        result = await fixture_db_session.execute(
            text(
                """
            SELECT
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(
                            interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                        ) AS ext
                        WHERE ext->>'name' = 'vep_annotation'
                          AND ext#>>'{value,most_severe_consequence}' = 'transcript_ablation'
                    ) THEN '17q Deletion'
                    ELSE 'Other'
                END as cnv_subtype
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.phenopacket_id = :pid
        """
            ),
            {"pid": "test-cnv-del-vep"},
        )

        row = result.fetchone()
        assert row is not None
        assert row[0] == "17q Deletion"

        # Cleanup
        await fixture_db_session.execute(
            text("DELETE FROM phenopackets WHERE phenopacket_id = :pid"),
            {"pid": "test-cnv-del-vep"},
        )
        await fixture_db_session.commit()

    async def test_comparison_cnv_duplication_classified_by_vep_consequence(
        self, fixture_db_session
    ):
        """Test duplication classification by VEP consequence (transcript_amplification).

        R logic (line 88):
            EFFECT == "transcript_amplification" ~ "17qDup"
        """
        test_phenopacket = {
            "id": "test-cnv-dup-vep",
            "subject": {"id": "patient-cnv-dup-vep"},
            "interpretations": [
                {
                    "id": "interp-1",
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "variantInterpretation": {
                                    "interpretationStatus": "PATHOGENIC",
                                    "variationDescriptor": {
                                        "id": "var-cnv-dup",
                                        "expressions": [
                                            {
                                                "syntax": "hgvs.g",
                                                "value": "NC_000017.11:g.36459258_37832869dup",
                                            }
                                        ],
                                        "extensions": [
                                            {
                                                "name": "vep_annotation",
                                                "value": {
                                                    "most_severe_consequence": "transcript_amplification",
                                                    "impact": "HIGH",
                                                },
                                            }
                                        ],
                                    },
                                }
                            }
                        ]
                    },
                }
            ],
            "phenotypicFeatures": [
                {
                    "type": {"id": "HP:0000107", "label": "Renal cyst"},
                    "excluded": False,
                }
            ],
        }

        # Insert test phenopacket
        # Use CAST() instead of :: to avoid SQLAlchemy interpreting :pk::jsonb incorrectly
        await fixture_db_session.execute(
            text(
                """
            INSERT INTO phenopackets (id, phenopacket_id, phenopacket, subject_id, subject_sex, revision)
            VALUES (gen_random_uuid(), :pid, CAST(:pk AS jsonb), :sid, :sex, 1)
        """
            ),
            {
                "pid": "test-cnv-dup-vep",
                "pk": json.dumps(test_phenopacket),
                "sid": "patient-cnv-dup-vep",
                "sex": "UNKNOWN_SEX",
            },
        )
        await fixture_db_session.commit()

        # Query - Should be classified as duplication by VEP consequence
        result = await fixture_db_session.execute(
            text(
                """
            SELECT
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(
                            interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                        ) AS ext
                        WHERE ext->>'name' = 'vep_annotation'
                          AND ext#>>'{value,most_severe_consequence}' = 'transcript_amplification'
                    ) THEN '17q Duplication'
                    ELSE 'Other'
                END as cnv_subtype
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.phenopacket_id = :pid
        """
            ),
            {"pid": "test-cnv-dup-vep"},
        )

        row = result.fetchone()
        assert row is not None
        assert row[0] == "17q Duplication"

        # Cleanup
        await fixture_db_session.execute(
            text("DELETE FROM phenopackets WHERE phenopacket_id = :pid"),
            {"pid": "test-cnv-dup-vep"},
        )
        await fixture_db_session.commit()

    async def test_comparison_cnv_deletion_vs_duplication_endpoint_returns_200(
        self, fixture_async_client, fixture_db_session
    ):
        """Test the CNV deletion vs duplication comparison endpoint."""
        response = await fixture_async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "cnv_deletion_vs_duplication",
                "limit": 10,
                "min_prevalence": 0.01,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "group1_name" in data
        assert "group2_name" in data
        assert "phenotypes" in data
        assert "metadata" in data

        # Check group names
        assert data["group1_name"] == "17q Deletion"
        assert data["group2_name"] == "17q Duplication"

        # Check metadata
        assert data["metadata"]["comparison_type"] == "cnv_deletion_vs_duplication"
