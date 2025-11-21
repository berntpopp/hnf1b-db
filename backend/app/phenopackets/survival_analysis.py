"""Survival analysis utilities for Kaplan-Meier curves.

This module provides utilities for:
- Parsing ISO8601 age durations
- Calculating Kaplan-Meier survival estimates with confidence intervals
- Computing log-rank test statistics
"""

import math
import re
from typing import Optional


def parse_iso8601_age(iso8601_duration: Optional[str]) -> Optional[float]:
    """Parse ISO8601 duration string to age in years.

    Args:
        iso8601_duration: ISO8601 duration string (e.g., "P25Y6M", "P3Y", "P45Y6M2D")

    Returns:
        Age in years as float, or None if invalid/missing

    Examples:
        >>> parse_iso8601_age("P25Y")
        25.0
        >>> parse_iso8601_age("P5Y6M")
        5.5
        >>> parse_iso8601_age("P1Y3M15D")
        1.29
        >>> parse_iso8601_age(None)
        None
    """
    if not iso8601_duration:
        return None

    # Match ISO8601 duration: P[nY][nM][nD]
    pattern = r"P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?"
    match = re.match(pattern, iso8601_duration)

    if not match:
        return None

    years = int(match.group(1) or 0)
    months = int(match.group(2) or 0)
    days = int(match.group(3) or 0)

    # Convert to years
    age_years = years + (months / 12.0) + (days / 365.25)

    return round(age_years, 2)


def parse_onset_ontology(ontology_class: dict) -> Optional[float]:
    """Parse onset ontology class to approximate age in years.

    Args:
        ontology_class: HPO ontology class with id and label
            e.g., {"id": "HP:0003577", "label": "Congenital onset"}

    Returns:
        Approximate age in years, or None if cannot determine

    Mapping:
        - HP:0011460 (Embryonal onset): -0.5 (prenatal)
        - HP:0011461 (Fetal onset): -0.25 (prenatal)
        - HP:0003577 (Congenital onset): 0
        - HP:0003623 (Neonatal onset): 0
        - HP:0410280 (Pediatric onset): 5
        - HP:0011462 (Infantile onset): 0.5
        - HP:0011463 (Childhood onset): 5
        - HP:0003621 (Juvenile onset): 10
        - HP:0025709 (Adolescent onset): 15
        - HP:0003581 (Adult onset): 18
        - HP:0003584 (Late onset): 60
    """
    if not ontology_class or "id" not in ontology_class:
        return None

    onset_mapping = {
        "HP:0011460": -0.5,  # Embryonal onset
        "HP:0011461": -0.25,  # Fetal onset
        "HP:0003577": 0,  # Congenital onset
        "HP:0003623": 0,  # Neonatal onset
        "HP:0410280": 5,  # Pediatric onset
        "HP:0011462": 0.5,  # Infantile onset
        "HP:0011463": 5,  # Childhood onset
        "HP:0003621": 10,  # Juvenile onset
        "HP:0025709": 15,  # Adolescent onset
        "HP:0003581": 18,  # Adult onset
        "HP:0003584": 60,  # Late onset
        "HP:0003596": 40,  # Middle age onset
        "HP:0003593": 1,  # Infant onset
        "HP:0003674": 1,  # Postnatal onset (approximate)
    }

    hpo_id = ontology_class.get("id")
    return onset_mapping.get(hpo_id)


def calculate_kaplan_meier(event_times: list[tuple[float, bool]]) -> list[dict]:
    """Calculate Kaplan-Meier survival estimates with 95% confidence intervals.

    Uses Greenwood's formula for variance estimation and log-log transformation
    for confidence interval calculation (more accurate for extreme probabilities).

    Args:
        event_times: List of (time, event_occurred) tuples
            - time: Age at event or censoring (years)
            - event_occurred: True if event occurred, False if censored

    Returns:
        List of dictionaries with survival estimates at each time point:
        [
            {
                "time": 0.0,
                "survival_probability": 1.0,
                "ci_lower": 1.0,
                "ci_upper": 1.0,
                "at_risk": 100,
                "events": 0,
                "censored": 0
            },
            ...
        ]

    Example:
        >>> data = [(25.0, True), (30.0, False), (35.0, True), (40.0, False)]
        >>> result = calculate_kaplan_meier(data)
        >>> len(result) > 0
        True
        >>> all('ci_lower' in r and 'ci_upper' in r for r in result)
        True
    """
    if not event_times:
        return []

    # Sort by time
    sorted_data = sorted(event_times, key=lambda x: x[0])

    # Group by unique time points
    time_groups = {}
    for time, event in sorted_data:
        if time not in time_groups:
            time_groups[time] = {"events": 0, "censored": 0}
        if event:
            time_groups[time]["events"] += 1
        else:
            time_groups[time]["censored"] += 1

    # Calculate survival probability at each time point
    result = []
    n_at_risk = len(event_times)
    survival_prob = 1.0
    greenwood_variance = 0.0  # Cumulative variance using Greenwood's formula

    # Start at time 0
    result.append(
        {
            "time": 0.0,
            "survival_probability": 1.0,
            "ci_lower": 1.0,
            "ci_upper": 1.0,
            "at_risk": n_at_risk,
            "events": 0,
            "censored": 0,
        }
    )

    for time in sorted(time_groups.keys()):
        group = time_groups[time]
        events = group["events"]
        censored = group["censored"]

        # Update survival probability (only for events, not censored)
        if events > 0:
            survival_prob *= (n_at_risk - events) / n_at_risk

            # Update Greenwood's variance: Var(S(t)) = S(t)^2 * sum(d_i / (n_i * (n_i - d_i)))
            if n_at_risk > events:
                greenwood_variance += events / (n_at_risk * (n_at_risk - events))

        # Calculate 95% confidence interval using log-log transformation
        # More accurate for extreme probabilities than plain Greenwood
        ci_lower = 1.0
        ci_upper = 1.0

        if survival_prob > 0 and survival_prob < 1 and greenwood_variance > 0:
            se = survival_prob * math.sqrt(greenwood_variance)  # Standard error
            z = 1.96  # 95% CI

            # Log-log transformation for better CI at extreme probabilities
            if survival_prob > 0:
                log_log_s = math.log(-math.log(survival_prob))
                se_log_log = se / (survival_prob * abs(math.log(survival_prob)))

                ci_lower_ll = log_log_s - z * se_log_log
                ci_upper_ll = log_log_s + z * se_log_log

                ci_lower = math.exp(-math.exp(ci_upper_ll))  # Note: swap for correct bounds
                ci_upper = math.exp(-math.exp(ci_lower_ll))

                # Clip to valid probability range
                ci_lower = max(0.0, min(1.0, ci_lower))
                ci_upper = max(0.0, min(1.0, ci_upper))

        result.append(
            {
                "time": round(time, 2),
                "survival_probability": round(survival_prob, 4),
                "ci_lower": round(ci_lower, 4),
                "ci_upper": round(ci_upper, 4),
                "at_risk": n_at_risk,
                "events": events,
                "censored": censored,
            }
        )

        # Update number at risk for next time point
        n_at_risk -= events + censored

    return result


def calculate_log_rank_test(
    group1_times: list[tuple[float, bool]], group2_times: list[tuple[float, bool]]
) -> dict:
    """Calculate log-rank test statistic for comparing two survival curves.

    Args:
        group1_times: Event times for group 1 [(time, event), ...]
        group2_times: Event times for group 2 [(time, event), ...]

    Returns:
        Dictionary with test results:
        {
            "statistic": float,  # Chi-square test statistic
            "p_value": float,    # Two-tailed p-value
            "significant": bool  # True if p < 0.05
        }

    Note:
        Uses Mantel-Haenszel log-rank test for comparing survival distributions
    """
    # Combine all unique event times
    all_times = set()
    for time, _ in group1_times + group2_times:
        all_times.add(time)

    observed_minus_expected = 0.0
    variance = 0.0

    # Number at risk in each group at start
    n1 = len(group1_times)
    n2 = len(group2_times)

    # Create lookup for events at each time
    g1_events = {t: sum(1 for time, event in group1_times if time == t and event) for t in all_times}
    g2_events = {t: sum(1 for time, event in group2_times if time == t and event) for t in all_times}

    for time in sorted(all_times):
        # Number still at risk at this time
        n1_risk = sum(1 for t, _ in group1_times if t >= time)
        n2_risk = sum(1 for t, _ in group2_times if t >= time)
        n_total = n1_risk + n2_risk

        if n_total == 0:
            continue

        # Observed events
        d1 = g1_events[time]
        d2 = g2_events[time]
        d_total = d1 + d2

        if d_total == 0:
            continue

        # Expected events in group 1
        expected_d1 = (n1_risk / n_total) * d_total

        # Update test statistic components
        observed_minus_expected += d1 - expected_d1

        # Variance component
        if n_total > 1:
            var_component = (n1_risk * n2_risk * d_total * (n_total - d_total)) / (
                n_total * n_total * (n_total - 1)
            )
            variance += var_component

    # Calculate chi-square statistic
    if variance > 0:
        chi_square = (observed_minus_expected**2) / variance
    else:
        chi_square = 0.0

    # Calculate p-value from chi-square distribution (df=1)
    # Using simple approximation for p-value
    # For production, would use scipy.stats.chi2.sf(chi_square, 1)
    import math

    if chi_square == 0:
        p_value = 1.0
    else:
        # Approximate p-value using normal approximation
        z = math.sqrt(chi_square)
        # Two-tailed test
        p_value = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
        p_value = max(0.0, min(1.0, p_value))

    return {
        "statistic": round(chi_square, 4),
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05,
    }
