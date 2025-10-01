"""Age utilities for parsing and comparing ISO8601 durations in phenopackets."""

import re
from typing import Optional


class AgeParser:
    """ISO8601 duration parser for age filtering in phenopackets."""

    @staticmethod
    def parse_iso8601_to_years(duration: str) -> Optional[float]:
        """Parse ISO8601 duration to years as a float.

        Examples:
            P1Y -> 1.0
            P1Y6M -> 1.5
            P2Y3M -> 2.25
            P10M -> 0.833...
            P5D -> 0.0137... (5/365)

        Args:
            duration: ISO8601 duration string (e.g., 'P1Y2M3D')

        Returns:
            Age in years as float, or None if parsing fails
        """
        if not duration or not isinstance(duration, str):
            return None

        # Remove whitespace and ensure it starts with 'P'
        duration = duration.strip()
        if not duration.startswith("P"):
            return None

        try:
            # Extract years, months, and days using regex
            years_match = re.search(r"(\d+(?:\.\d+)?)Y", duration)
            months_match = re.search(r"(\d+(?:\.\d+)?)M", duration)
            days_match = re.search(r"(\d+(?:\.\d+)?)D", duration)

            years = float(years_match.group(1)) if years_match else 0
            months = float(months_match.group(1)) if months_match else 0
            days = float(days_match.group(1)) if days_match else 0

            # Convert to years (using 365.25 days per year for accuracy)
            total_years = years + (months / 12) + (days / 365.25)

            return total_years

        except (AttributeError, ValueError):
            return None

    @staticmethod
    def create_postgresql_age_condition(
        age_years: float, comparison: str = ">="
    ) -> str:
        """Create a PostgreSQL condition for age filtering.

        This creates a SQL condition that extracts and compares ages from
        ISO8601 durations stored in JSONB.

        Args:
            age_years: Age in years to compare against
            comparison: Comparison operator ('>=', '<=', '>', '<', '=')

        Returns:
            PostgreSQL condition string for use in WHERE clause
        """
        # Convert years to approximate total months for comparison
        total_months = int(age_years * 12)

        # PostgreSQL expression to extract and calculate age in months
        # This handles P1Y2M format by extracting years and months separately
        sql_condition = rf"""
        (
            COALESCE(
                (regexp_match(
                    phenopacket->>'subject'->>'timeAtLastEncounter'->>'age'->>'iso8601duration',
                    'P(\d+)Y'
                ))[1]::int * 12,
                0
            ) +
            COALESCE(
                (regexp_match(
                    phenopacket->>'subject'->>'timeAtLastEncounter'->>'age'->>'iso8601duration',
                    'P\d*Y?(\d+)M'
                ))[1]::int,
                0
            )
        ) {comparison} {total_months}
        """

        return sql_condition

    @staticmethod
    def format_years_to_iso8601(years: float) -> str:
        """Convert years (float) to ISO8601 duration string.

        Args:
            years: Age in years

        Returns:
            ISO8601 duration string
        """
        if years < 0:
            raise ValueError("Age cannot be negative")

        # Calculate whole years and remaining months
        whole_years = int(years)
        remaining_months = int((years - whole_years) * 12)

        # Build the duration string
        parts = ["P"]
        if whole_years > 0:
            parts.append(f"{whole_years}Y")
        if remaining_months > 0:
            parts.append(f"{remaining_months}M")

        # Handle edge case where age is 0
        if len(parts) == 1:
            parts.append("0Y")

        return "".join(parts)


def extract_age_from_phenopacket(phenopacket_data: dict) -> Optional[float]:
    """Extract age in years from a phenopacket dictionary.

    Args:
        phenopacket_data: Phenopacket data as dictionary

    Returns:
        Age in years or None if not found/parseable
    """
    try:
        # Navigate through the nested structure
        subject = phenopacket_data.get("subject", {})
        time_at_last_encounter = subject.get("timeAtLastEncounter", {})
        age = time_at_last_encounter.get("age", {})
        iso_duration = age.get("iso8601duration")

        if iso_duration:
            return AgeParser.parse_iso8601_to_years(iso_duration)

        return None
    except (KeyError, AttributeError, TypeError):
        return None


def compare_ages(age1: str, age2: str) -> int:
    """Compare two ISO8601 duration strings.

    Args:
        age1: First ISO8601 duration
        age2: Second ISO8601 duration

    Returns:
        -1 if age1 < age2, 0 if equal, 1 if age1 > age2
    """
    years1 = AgeParser.parse_iso8601_to_years(age1)
    years2 = AgeParser.parse_iso8601_to_years(age2)

    if years1 is None or years2 is None:
        raise ValueError("Invalid ISO8601 duration format")

    if years1 < years2:
        return -1
    elif years1 > years2:
        return 1
    return 0
