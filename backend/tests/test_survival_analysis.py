"""Tests for survival analysis utilities.

Tests cover:
- ISO8601 age parsing
- Onset ontology parsing
- Kaplan-Meier survival curve calculations
- Log-rank test statistics
- Bonferroni correction

These tests validate mathematical correctness against known results
and ensure edge cases are handled properly.
"""

from app.phenopackets.survival_analysis import (
    apply_bonferroni_correction,
    calculate_kaplan_meier,
    calculate_log_rank_test,
    parse_iso8601_age,
    parse_onset_ontology,
)


class TestParseISO8601Age:
    """Tests for ISO8601 duration parsing."""

    def test_years_only(self):
        """Parse duration with only years."""
        assert parse_iso8601_age("P25Y") == 25.0
        assert parse_iso8601_age("P0Y") == 0.0
        assert parse_iso8601_age("P100Y") == 100.0

    def test_years_and_months(self):
        """Parse duration with years and months."""
        assert parse_iso8601_age("P5Y6M") == 5.5
        assert parse_iso8601_age("P1Y3M") == 1.25
        assert parse_iso8601_age("P0Y6M") == 0.5

    def test_years_months_days(self):
        """Parse duration with years, months, and days."""
        # 1 year, 3 months, ~15 days ≈ 1.29 years
        result = parse_iso8601_age("P1Y3M15D")
        assert result is not None
        assert 1.28 <= result <= 1.30

    def test_months_only(self):
        """Parse duration with only months."""
        assert parse_iso8601_age("P6M") == 0.5
        assert parse_iso8601_age("P12M") == 1.0

    def test_days_only(self):
        """Parse duration with only days."""
        result = parse_iso8601_age("P365D")
        assert result is not None
        # 365 / 365.25 ≈ 1.0
        assert 0.99 <= result <= 1.0

    def test_none_input(self):
        """Return None for None input."""
        assert parse_iso8601_age(None) is None

    def test_empty_string(self):
        """Return None for empty string."""
        assert parse_iso8601_age("") is None

    def test_invalid_format(self):
        """Return None for invalid format."""
        assert parse_iso8601_age("25 years") is None
        assert parse_iso8601_age("invalid") is None
        assert parse_iso8601_age("25Y") is None  # Missing P prefix


class TestParseOnsetOntology:
    """Tests for onset ontology parsing."""

    def test_congenital_onset(self):
        """Parse congenital onset (HP:0003577)."""
        result = parse_onset_ontology({"id": "HP:0003577", "label": "Congenital onset"})
        assert result == 0

    def test_adult_onset(self):
        """Parse adult onset (HP:0003581)."""
        result = parse_onset_ontology({"id": "HP:0003581", "label": "Adult onset"})
        assert result == 18

    def test_juvenile_onset(self):
        """Parse juvenile onset (HP:0003621)."""
        result = parse_onset_ontology({"id": "HP:0003621", "label": "Juvenile onset"})
        assert result == 10

    def test_late_onset(self):
        """Parse late onset (HP:0003584)."""
        result = parse_onset_ontology({"id": "HP:0003584", "label": "Late onset"})
        assert result == 60

    def test_prenatal_onset(self):
        """Prenatal onsets return negative values."""
        embryonal = parse_onset_ontology(
            {"id": "HP:0011460", "label": "Embryonal onset"}
        )
        assert embryonal == -0.5

        fetal = parse_onset_ontology({"id": "HP:0011461", "label": "Fetal onset"})
        assert fetal == -0.25

    def test_none_input(self):
        """Return None for None input."""
        assert parse_onset_ontology(None) is None

    def test_missing_id(self):
        """Return None when id field is missing."""
        assert parse_onset_ontology({"label": "Some onset"}) is None

    def test_unknown_hpo_id(self):
        """Return None for unknown HPO ID."""
        assert parse_onset_ontology({"id": "HP:9999999", "label": "Unknown"}) is None


class TestCalculateKaplanMeier:
    """Tests for Kaplan-Meier survival curve calculations."""

    def test_empty_input(self):
        """Return empty list for empty input."""
        assert calculate_kaplan_meier([]) == []

    def test_all_events(self):
        """Calculate KM curve when all subjects have events."""
        # 4 subjects, all have events at different times
        data = [(10.0, True), (20.0, True), (30.0, True), (40.0, True)]
        result = calculate_kaplan_meier(data)

        # Should start at 1.0
        assert result[0]["survival_probability"] == 1.0
        assert result[0]["time"] == 0.0

        # Each event reduces survival by 1/n_at_risk
        # At t=10: S = 3/4 = 0.75
        assert result[1]["time"] == 10.0
        assert result[1]["survival_probability"] == 0.75

        # At t=20: S = 0.75 * 2/3 = 0.5
        assert result[2]["time"] == 20.0
        assert result[2]["survival_probability"] == 0.5

        # At t=30: S = 0.5 * 1/2 = 0.25
        assert result[3]["time"] == 30.0
        assert result[3]["survival_probability"] == 0.25

        # At t=40: S = 0.25 * 0/1 = 0.0
        assert result[4]["time"] == 40.0
        assert result[4]["survival_probability"] == 0.0

    def test_all_censored(self):
        """Calculate KM curve when all subjects are censored."""
        data = [(10.0, False), (20.0, False), (30.0, False)]
        result = calculate_kaplan_meier(data)

        # Survival probability stays at 1.0 (no events)
        for point in result:
            assert point["survival_probability"] == 1.0

    def test_mixed_events_and_censoring(self):
        """Calculate KM curve with mix of events and censoring."""
        # Typical survival data
        data = [
            (5.0, True),  # Event at 5
            (10.0, False),  # Censored at 10
            (15.0, True),  # Event at 15
            (20.0, False),  # Censored at 20
        ]
        result = calculate_kaplan_meier(data)

        assert result[0]["survival_probability"] == 1.0
        # At t=5: S = 3/4 = 0.75
        assert result[1]["survival_probability"] == 0.75
        # At t=10: censoring, S stays 0.75
        assert result[2]["survival_probability"] == 0.75
        # At t=15: S = 0.75 * 1/2 = 0.375
        assert result[3]["survival_probability"] == 0.375

    def test_ties_at_same_time(self):
        """Handle multiple events at the same time."""
        # 2 events at same time
        data = [(10.0, True), (10.0, True), (20.0, True)]
        result = calculate_kaplan_meier(data)

        # At t=10: 2 events out of 3 at risk
        # S = (3-2)/3 = 1/3 ≈ 0.3333
        assert result[1]["time"] == 10.0
        assert abs(result[1]["survival_probability"] - 0.3333) < 0.01

    def test_confidence_intervals_present(self):
        """Confidence intervals should be included."""
        data = [(10.0, True), (20.0, True), (30.0, False)]
        result = calculate_kaplan_meier(data)

        for point in result:
            assert "ci_lower" in point
            assert "ci_upper" in point
            # CI bounds should be valid probabilities
            assert 0.0 <= point["ci_lower"] <= 1.0
            assert 0.0 <= point["ci_upper"] <= 1.0
            # Lower should be <= upper
            assert point["ci_lower"] <= point["ci_upper"]

    def test_at_risk_decreases(self):
        """Number at risk should decrease over time."""
        data = [(10.0, True), (20.0, True), (30.0, False), (40.0, True)]
        result = calculate_kaplan_meier(data)

        at_risk_values = [point["at_risk"] for point in result]
        # Should be monotonically decreasing
        for i in range(1, len(at_risk_values)):
            assert at_risk_values[i] <= at_risk_values[i - 1]


class TestCalculateLogRankTest:
    """Tests for log-rank test calculations."""

    def test_identical_curves(self):
        """Identical survival curves should have high p-value."""
        group1 = [(10.0, True), (20.0, True), (30.0, True)]
        group2 = [(10.0, True), (20.0, True), (30.0, True)]

        result = calculate_log_rank_test(group1, group2)

        assert "statistic" in result
        assert "p_value" in result
        assert "significant" in result
        # Similar curves should not be significant
        assert result["p_value"] > 0.05
        assert result["significant"] is False

    def test_different_curves(self):
        """Very different survival curves should have low p-value."""
        # Group 1: all events early
        group1 = [(5.0, True), (6.0, True), (7.0, True), (8.0, True), (9.0, True)]
        # Group 2: all events late
        group2 = [
            (50.0, True),
            (60.0, True),
            (70.0, True),
            (80.0, True),
            (90.0, True),
        ]

        result = calculate_log_rank_test(group1, group2)

        # Very different curves should be significant
        assert result["p_value"] < 0.05
        assert result["significant"] is True

    def test_one_group_all_censored(self):
        """Handle case where one group is all censored."""
        group1 = [(10.0, True), (20.0, True), (30.0, True)]
        group2 = [(10.0, False), (20.0, False), (30.0, False)]

        result = calculate_log_rank_test(group1, group2)

        # Should return valid result
        assert "p_value" in result
        assert 0.0 <= result["p_value"] <= 1.0

    def test_empty_groups(self):
        """Handle empty groups gracefully."""
        result = calculate_log_rank_test([], [(10.0, True)])

        # Should not crash
        assert "p_value" in result

    def test_chi_square_statistic_positive(self):
        """Chi-square statistic should be non-negative."""
        group1 = [(10.0, True), (20.0, False)]
        group2 = [(15.0, True), (25.0, True)]

        result = calculate_log_rank_test(group1, group2)

        assert result["statistic"] >= 0.0


class TestApplyBonferroniCorrection:
    """Tests for Bonferroni correction."""

    def test_single_test(self):
        """Single test: correction factor is 1."""
        tests = [{"p_value": 0.03, "comparison": "A vs B"}]
        result = apply_bonferroni_correction(tests)

        assert len(result) == 1
        assert result[0]["p_value_corrected"] == 0.03

    def test_multiple_tests(self):
        """Multiple tests: p-values multiplied by n_tests."""
        tests = [
            {"p_value": 0.01, "comparison": "A vs B"},
            {"p_value": 0.03, "comparison": "A vs C"},
            {"p_value": 0.06, "comparison": "B vs C"},
        ]
        result = apply_bonferroni_correction(tests)

        assert len(result) == 3
        # 0.01 * 3 = 0.03
        assert result[0]["p_value_corrected"] == 0.03
        # 0.03 * 3 = 0.09
        assert result[1]["p_value_corrected"] == 0.09
        # 0.06 * 3 = 0.18
        assert result[2]["p_value_corrected"] == 0.18

    def test_p_value_capped_at_one(self):
        """Corrected p-value should not exceed 1.0."""
        tests = [
            {"p_value": 0.5, "comparison": "A vs B"},
            {"p_value": 0.5, "comparison": "A vs C"},
        ]
        result = apply_bonferroni_correction(tests)

        # 0.5 * 2 = 1.0 (capped)
        assert result[0]["p_value_corrected"] == 1.0

    def test_significance_updated(self):
        """Significance should be based on corrected p-value."""
        tests = [
            {"p_value": 0.02, "comparison": "A vs B"},  # 0.02 * 2 = 0.04 (significant)
            {
                "p_value": 0.03,
                "comparison": "A vs C",
            },  # 0.03 * 2 = 0.06 (not significant)
        ]
        result = apply_bonferroni_correction(tests)

        assert result[0]["significant"] is True  # 0.04 < 0.05
        assert result[1]["significant"] is False  # 0.06 > 0.05

    def test_empty_list(self):
        """Handle empty list gracefully."""
        result = apply_bonferroni_correction([])
        assert result == []

    def test_preserves_other_fields(self):
        """Original fields should be preserved."""
        tests = [{"p_value": 0.01, "comparison": "A vs B", "statistic": 5.5}]
        result = apply_bonferroni_correction(tests)

        assert result[0]["comparison"] == "A vs B"
        assert result[0]["statistic"] == 5.5
        assert result[0]["p_value"] == 0.01  # Original preserved


class TestKaplanMeierVsR:
    """Validation tests comparing against R's survfit() output.

    These tests use known results from R to validate correctness.
    """

    def test_simple_survival_matches_r(self):
        """Verify KM calculation matches R survfit() for simple case.

        R code:
        library(survival)
        time <- c(1, 2, 3, 4, 5)
        event <- c(1, 1, 0, 1, 1)  # 1=event, 0=censored
        fit <- survfit(Surv(time, event) ~ 1)
        summary(fit)
        """
        data = [
            (1.0, True),
            (2.0, True),
            (3.0, False),  # Censored
            (4.0, True),
            (5.0, True),
        ]
        result = calculate_kaplan_meier(data)

        # Expected from R:
        # time  n.risk  n.event  survival
        # 1     5       1        0.800
        # 2     4       1        0.600
        # 4     2       1        0.300
        # 5     1       1        0.000

        # Find results at each time point
        times_surv = {r["time"]: r["survival_probability"] for r in result}

        assert abs(times_surv.get(1.0, 0) - 0.8) < 0.01
        assert abs(times_surv.get(2.0, 0) - 0.6) < 0.01
        assert abs(times_surv.get(4.0, 0) - 0.3) < 0.01
        assert abs(times_surv.get(5.0, 0) - 0.0) < 0.01
