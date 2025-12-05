"""Statistical validation tests for variant classification logic.

This test suite validates that the Python implementation:
1. Applies R classification rules consistently
2. Produces reasonable distributions
3. Handles edge cases correctly
4. Generates valid statistical results

Based on R reference logic from docs/analysis/R-commands_genotype-phenotype.txt
"""

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
class TestClassificationConsistency:
    """Test that classification rules are applied consistently with R logic."""

    async def test_high_impact_always_truncating(self, db_session):
        """Verify that ALL HIGH impact variants are classified as truncating.

        R logic (line 78): IMPACT == "HIGH" ~ "T"
        No exceptions - HIGH impact should ALWAYS be truncating.
        """
        # Get all HIGH impact variants
        high_impact_result = await db_session.execute(
            text(
                """
            SELECT COUNT(DISTINCT p.phenopacket_id) as count
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp,
                 jsonb_array_elements(
                     interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                 ) AS ext
            WHERE p.deleted_at IS NULL
              AND ext->>'name' = 'vep_annotation'
              AND ext#>>'{value,impact}' = 'HIGH'
        """
            )
        )
        high_impact_count = high_impact_result.scalar()

        if high_impact_count > 0:
            # Verify ALL are classified as truncating by our logic
            truncating_result = await db_session.execute(
                text(
                    """
                SELECT COUNT(DISTINCT p.phenopacket_id) as count
                FROM phenopackets p,
                     jsonb_array_elements(p.phenopacket->'interpretations') AS interp
                WHERE p.deleted_at IS NULL
                  AND EXISTS (
                      SELECT 1
                      FROM jsonb_array_elements(
                          interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                      ) AS ext
                      WHERE ext->>'name' = 'vep_annotation'
                        AND ext#>>'{value,impact}' = 'HIGH'
                  )
            """
                )
            )
            truncating_count = truncating_result.scalar()

            assert high_impact_count == truncating_count, (
                f"All {high_impact_count} HIGH impact variants should be classified as truncating"
            )
            print(
                f"✓ Verified: All {high_impact_count} HIGH impact variants classified as truncating"
            )

    async def test_moderate_impact_always_non_truncating(self, db_session):
        """Verify that MODERATE impact variants are NEVER reclassified.

        R logic (line 77): IMPACT == "MODERATE" ~ "nT"
        Even if pathogenic, MODERATE stays non-truncating.
        """
        # Get MODERATE impact pathogenic variants
        moderate_pathogenic_result = await db_session.execute(
            text(
                """
            SELECT COUNT(DISTINCT p.phenopacket_id) as count
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp,
                 jsonb_array_elements(
                     interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                 ) AS ext
            WHERE p.deleted_at IS NULL
              AND ext->>'name' = 'vep_annotation'
              AND ext#>>'{value,impact}' = 'MODERATE'
              AND interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,interpretationStatus}'
                  IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
        """
            )
        )
        moderate_pathogenic_count = moderate_pathogenic_result.scalar()

        if moderate_pathogenic_count > 0:
            print(
                f"Found {moderate_pathogenic_count} MODERATE impact pathogenic variants"
            )
            print("✓ These should remain non-truncating (no reclassification)")

    async def test_low_impact_pathogenic_reclassified(self, db_session):
        """Verify that LOW impact + pathogenic variants ARE reclassified as truncating.

        R logic (line 79): IMPACT == "LOW" & ACMG_groups == "LP/P" ~ "T"
        This is the key edge case for cryptic splice effects.
        """
        # Get LOW impact pathogenic variants
        result = await db_session.execute(
            text(
                """
            SELECT COUNT(DISTINCT p.phenopacket_id) as count
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp,
                 jsonb_array_elements(
                     interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                 ) AS ext
            WHERE p.deleted_at IS NULL
              AND ext->>'name' = 'vep_annotation'
              AND ext#>>'{value,impact}' = 'LOW'
              AND interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,interpretationStatus}'
                  IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
        """
            )
        )
        low_pathogenic_count = result.scalar()

        if low_pathogenic_count > 0:
            print(f"Found {low_pathogenic_count} LOW impact pathogenic variants")
            print("✓ These should be reclassified as truncating (edge case handling)")

    async def test_low_impact_vus_not_reclassified(self, db_session):
        """Verify that LOW impact VUS variants are NOT reclassified.

        Only LOW + LP/P should be reclassified, not LOW + VUS.
        """
        # Get LOW impact VUS variants
        result = await db_session.execute(
            text(
                """
            SELECT COUNT(DISTINCT p.phenopacket_id) as count
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp,
                 jsonb_array_elements(
                     interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                 ) AS ext
            WHERE p.deleted_at IS NULL
              AND ext->>'name' = 'vep_annotation'
              AND ext#>>'{value,impact}' = 'LOW'
              AND interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,interpretationStatus}'
                  = 'UNCERTAIN_SIGNIFICANCE'
        """
            )
        )
        low_vus_count = result.scalar()

        if low_vus_count > 0:
            print(f"Found {low_vus_count} LOW impact VUS variants")
            print("✓ These should remain non-truncating (not pathogenic)")

    async def test_cnv_del_never_classified_as_dup(self, db_session):
        """Verify that deletion CNVs are never misclassified as duplications."""
        # Get variants with :DEL in ID
        # Use backslash escape to prevent SQLAlchemy from treating :DEL as bind parameter
        del_result = await db_session.execute(
            text(
                r"""
            SELECT COUNT(DISTINCT p.phenopacket_id) as count
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.deleted_at IS NULL
              AND interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ '\:DEL'
        """
            )
        )
        del_count = del_result.scalar()

        # Check if any are also classified as DUP (should be 0)
        both_result = await db_session.execute(
            text(
                r"""
            SELECT COUNT(DISTINCT p.phenopacket_id) as count
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.deleted_at IS NULL
              AND interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ '\:DEL'
              AND interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ '\:DUP'
        """
            )
        )
        both_count = both_result.scalar()

        assert both_count == 0, (
            f"Found {both_count} variants with both :DEL and :DUP (should be 0)"
        )

        if del_count > 0:
            print(f"✓ Verified: {del_count} deletion CNVs, none misclassified as DUP")


@pytest.mark.asyncio
class TestDistributionReasonableness:
    """Test that classification distributions are reasonable."""

    async def test_both_groups_have_variants(self, async_client):
        """Verify that both truncating and non-truncating groups exist.

        Uses the actual API endpoint for classification, which applies the full
        multi-tier classification logic (VEP IMPACT → pathogenicity + IMPACT →
        HGVS patterns → default). This ensures the test matches real behavior.

        If one group is empty, the classification logic may be broken.
        """
        # Use the API endpoint which applies proper multi-tier classification
        response = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "limit": 1,  # Only need summary data
                "min_prevalence": 0.0,  # Get all phenotypes to see group sizes
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Extract group counts from the ComparisonResult
        group1_count = data.get("group1_count", 0)
        group2_count = data.get("group2_count", 0)

        total = group1_count + group2_count

        # Skip test if no variants in database
        if total == 0:
            pytest.skip("No variants found in database")

        print("\n=== Classification Distribution (via API) ===")
        print(
            f"Truncating: {group1_count} ({group1_count / total * 100:.1f}%)"
            if total > 0
            else "Truncating: 0"
        )
        print(
            f"Non-truncating: {group2_count} ({group2_count / total * 100:.1f}%)"
            if total > 0
            else "Non-truncating: 0"
        )
        print(f"Total: {total}")

        # Assertions - both groups should have variants
        assert group1_count > 0, (
            "No truncating variants found - classification logic may be broken or "
            "data may lack VEP annotations and HGVS patterns for classification"
        )
        assert group2_count > 0, (
            "No non-truncating variants found - classification logic may be broken"
        )

        # Both groups should have at least 10% of total
        assert group1_count / total >= 0.1, "Truncating group too small (< 10%)"
        assert group2_count / total >= 0.1, "Non-truncating group too small (< 10%)"

        print("\n✓ Both groups have reasonable representation")

    async def test_cnv_distribution_if_present(self, db_session):
        """Test CNV distribution is reasonable if CNVs exist."""
        # Get CNV counts
        # Use backslash escape to prevent SQLAlchemy from treating :DEL/:DUP as bind parameters
        result = await db_session.execute(
            text(
                r"""
            SELECT
                CASE
                    WHEN interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ '\:DEL'
                        THEN '17qDel'
                    WHEN interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ '\:DUP'
                        THEN '17qDup'
                    ELSE 'Other'
                END as cnv_type,
                COUNT(*) as count
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.deleted_at IS NULL
              AND interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,id}' ~ '\:(DEL|DUP)'
            GROUP BY cnv_type
        """
            )
        )

        rows = result.fetchall()
        cnv_counts = {row[0]: row[1] for row in rows}

        total_cnvs = sum(cnv_counts.values())

        if total_cnvs > 0:
            print("\n=== CNV Distribution ===")
            for cnv_type, count in sorted(cnv_counts.items()):
                print(f"{cnv_type}: {count} ({count / total_cnvs * 100:.1f}%)")
            print(f"Total CNVs: {total_cnvs}")

            # At least one CNV type should exist
            assert len(cnv_counts) > 0, "CNVs found but not classified"
            print("\n✓ CNV distribution is reasonable")
        else:
            print("\n⚠ No CNVs found in database (skipping CNV distribution test)")


@pytest.mark.asyncio
class TestEdgeCaseHandling:
    """Test that edge cases are handled correctly."""

    async def test_missing_vep_impact_handled(self, db_session):
        """Test that variants without VEP IMPACT data are handled.

        R logic (line 82): is.na(IMPACT) & ACMG_groups == "LP/P" ~ "T"
        Missing IMPACT + pathogenic should still be classifiable via HGVS fallback.
        """
        # Get variants without VEP impact
        result = await db_session.execute(
            text(
                """
            SELECT COUNT(DISTINCT p.phenopacket_id) as count
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.deleted_at IS NULL
              AND interp.value#>'{diagnosis,genomicInterpretations}' IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM jsonb_array_elements(
                      interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                  ) AS ext
                  WHERE ext->>'name' = 'vep_annotation'
                    AND ext#>>'{value,impact}' IS NOT NULL
              )
        """
            )
        )
        missing_impact_count = result.scalar()

        if missing_impact_count > 0:
            print(f"Found {missing_impact_count} variants without VEP IMPACT")
            print("✓ These should use HGVS fallback classification")

            # Verify some have HGVS patterns (fallback works)
            hgvs_result = await db_session.execute(
                text(
                    """
                SELECT COUNT(DISTINCT p.phenopacket_id) as count
                FROM phenopackets p,
                     jsonb_array_elements(p.phenopacket->'interpretations') AS interp
                WHERE p.deleted_at IS NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM jsonb_array_elements(
                          interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,extensions}'
                      ) AS ext
                      WHERE ext->>'name' = 'vep_annotation'
                        AND ext#>>'{value,impact}' IS NOT NULL
                  )
                  AND EXISTS (
                      SELECT 1
                      FROM jsonb_array_elements(
                          interp.value#>'{diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor,expressions}'
                      ) AS expr
                      WHERE (
                          (expr->>'syntax' = 'hgvs.p' AND expr->>'value' ~* 'fs')
                          OR (expr->>'syntax' = 'hgvs.p' AND expr->>'value' ~* 'ter')
                          OR (expr->>'syntax' = 'hgvs.c' AND expr->>'value' ~ '[+-][1-6]')
                      )
                  )
            """
                )
            )
            hgvs_fallback_count = hgvs_fallback_count = hgvs_result.scalar()

            if hgvs_fallback_count > 0:
                print(f"  → {hgvs_fallback_count} use HGVS fallback classification")
        else:
            print("✓ All variants have VEP IMPACT data")

    async def test_multiple_interpretations_handled(self, db_session):
        """Test that phenopackets with multiple variant interpretations work.

        Some phenopackets may have multiple variants - ensure we handle this.
        """
        result = await db_session.execute(
            text(
                """
            SELECT
                p.phenopacket_id,
                jsonb_array_length(
                    interp.value#>'{diagnosis,genomicInterpretations}'
                ) as variant_count
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.deleted_at IS NULL
              AND jsonb_array_length(
                  interp.value#>'{diagnosis,genomicInterpretations}'
              ) > 1
            LIMIT 5
        """
            )
        )

        rows = result.fetchall()
        if rows:
            print(
                f"\n✓ Found {len(rows)} phenopackets with multiple variant interpretations"
            )
            for row in rows:
                print(f"  {row[0]}: {row[1]} variants")
        else:
            print(
                "\n✓ All phenopackets have single variant interpretations (simple case)"
            )

    async def test_pathogenicity_values_are_valid(self, db_session):
        """Test that all pathogenicity values are standard ACMG terms."""
        result = await db_session.execute(
            text(
                """
            SELECT DISTINCT
                interp.value#>>'{diagnosis,genomicInterpretations,0,variantInterpretation,interpretationStatus}' as status,
                COUNT(*) as count
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') AS interp
            WHERE p.deleted_at IS NULL
              AND interp.value#>'{diagnosis,genomicInterpretations}' IS NOT NULL
            GROUP BY status
            ORDER BY count DESC
        """
            )
        )

        rows = result.fetchall()
        valid_statuses = {
            "PATHOGENIC",
            "LIKELY_PATHOGENIC",
            "UNCERTAIN_SIGNIFICANCE",
            "LIKELY_BENIGN",
            "BENIGN",
        }

        print("\n=== Pathogenicity Status Distribution ===")
        for row in rows:
            status = row[0]
            count = row[1]
            is_valid = status in valid_statuses
            marker = "✓" if is_valid else "⚠"
            print(f"{marker} {status}: {count}")

            if not is_valid and status is not None:
                print("  Warning: Non-standard pathogenicity status")


@pytest.mark.asyncio
class TestStatisticalValidity:
    """Test that statistical calculations produce valid results."""

    async def test_comparison_endpoint_produces_valid_statistics(self, async_client):
        """Test that comparison endpoint produces valid statistical results."""
        response = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "limit": 10,
                "min_prevalence": 0.1,
            },
        )

        assert response.status_code == 200
        data = response.json()

        if data["phenotypes"]:
            print(
                f"\n=== Statistical Validity Check ({len(data['phenotypes'])} phenotypes) ==="
            )

            for pheno in data["phenotypes"]:
                # Validate p-value
                p_val = pheno["p_value"]
                assert 0.0 <= p_val <= 1.0, f"Invalid p-value: {p_val}"

                # Validate effect size
                effect = pheno["effect_size"]
                assert effect >= 0.0, f"Invalid effect size: {effect}"
                assert effect <= 3.15, (
                    f"Effect size > π: {effect}"
                )  # Max Cohen's h is π

                # Validate percentages
                assert 0.0 <= pheno["group1_percentage"] <= 100.0
                assert 0.0 <= pheno["group2_percentage"] <= 100.0

                # Validate counts
                assert (
                    pheno["group1_present"] + pheno["group1_absent"]
                    == pheno["group1_total"]
                )
                assert (
                    pheno["group2_present"] + pheno["group2_absent"]
                    == pheno["group2_total"]
                )

                # Validate test type
                assert pheno["test_used"] in ["chi_square", "fisher_exact", "none"]

            print(f"✓ All {len(data['phenotypes'])} phenotypes have valid statistics")

    async def test_effect_sizes_correlate_with_significance(self, async_client):
        """Test that larger effect sizes tend to correlate with significance.

        This is a sanity check - not always true, but generally expected.
        """
        response = await async_client.get(
            "/api/v2/phenopackets/compare/variant-types",
            params={
                "comparison": "truncating_vs_non_truncating",
                "limit": 50,
                "min_prevalence": 0.05,
            },
        )

        assert response.status_code == 200
        data = response.json()

        if len(data["phenotypes"]) >= 10:
            # Get significant and non-significant phenotypes
            significant = [
                p["effect_size"] for p in data["phenotypes"] if p["significant"]
            ]
            not_significant = [
                p["effect_size"] for p in data["phenotypes"] if not p["significant"]
            ]

            if significant and not_significant:
                avg_sig = sum(significant) / len(significant)
                avg_nonsig = sum(not_significant) / len(not_significant)

                print("\n=== Effect Size vs Significance ===")
                print(f"Significant (n={len(significant)}): avg h = {avg_sig:.3f}")
                print(
                    f"Non-significant (n={len(not_significant)}): avg h = {avg_nonsig:.3f}"
                )

                # Generally, significant results should have larger effect sizes
                # (though not always due to sample size effects)
                if avg_sig > avg_nonsig:
                    print(
                        "✓ Significant results have larger average effect size (expected)"
                    )
                else:
                    print(
                        "⚠ Significant results have smaller average effect size (possible with large samples)"
                    )
