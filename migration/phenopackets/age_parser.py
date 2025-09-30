"""Age and temporal information parsing for phenopackets."""

import re
from typing import Any, Dict, Optional

import pandas as pd


class AgeParser:
    """Parser for age and temporal information in phenopackets."""

    @staticmethod
    def build_iso8601_duration(
        years: int = 0, months: int = 0, days: int = 0
    ) -> Optional[str]:
        """Build ISO8601 duration string from components.

        Args:
            years: Number of years
            months: Number of months
            days: Number of days

        Returns:
            ISO8601 duration string (e.g., "P1Y2M3D") or None if all values are 0
        """
        if not any([years, months, days]):
            return None

        duration_parts = []
        if years > 0:
            duration_parts.append(f"{years}Y")
        if months > 0:
            duration_parts.append(f"{months}M")
        if days > 0:
            duration_parts.append(f"{days}D")

        return "P" + "".join(duration_parts)

    @classmethod
    def parse_age(cls, age_str: Any) -> Optional[Dict[str, Any]]:
        """Parse age to ISO8601 duration format or HPO onset term.

        Args:
            age_str: Age string to parse

        Returns:
            Dictionary with either 'iso8601duration' or 'ontologyClass' key
        """
        if pd.isna(age_str):
            return None

        age_str = str(age_str).strip().lower()

        # Handle special onset terms
        if age_str in ["prenatal", "pre-natal", "antenatal"]:
            return {"ontologyClass": {"id": "HP:0034199", "label": "Prenatal onset"}}
        elif age_str in ["congenital", "birth", "at birth", "newborn", "neonatal"]:
            return {"ontologyClass": {"id": "HP:0003577", "label": "Congenital onset"}}
        elif age_str in ["infantile", "infant", "infancy"]:
            return {"ontologyClass": {"id": "HP:0003593", "label": "Infantile onset"}}
        elif age_str in ["childhood", "child"]:
            return {"ontologyClass": {"id": "HP:0011463", "label": "Childhood onset"}}
        elif age_str in ["adult", "adulthood"]:
            return {"ontologyClass": {"id": "HP:0003581", "label": "Adult onset"}}

        # Parse numeric ages (e.g., "1y9m", "2y", "6m", "3d")
        try:
            # Pattern for years, months, days
            pattern = r"(?:(\d+)\s*y(?:ears?)?)?\s*(?:(\d+)\s*m(?:onths?)?)?\s*(?:(\d+)\s*d(?:ays?)?)?"
            match = re.match(pattern, age_str)

            if match and any(match.groups()):
                years = int(match.group(1)) if match.group(1) else 0
                months = int(match.group(2)) if match.group(2) else 0
                days = int(match.group(3)) if match.group(3) else 0

                # Build ISO8601 duration using helper method
                duration = cls.build_iso8601_duration(years, months, days)
                if duration:
                    return {"iso8601duration": duration}

            # Try simple number (assume years)
            if age_str.isdigit():
                duration = cls.build_iso8601_duration(years=int(age_str))
                if duration:
                    return {"iso8601duration": duration}

            # Try extracting first number
            match = re.search(r"(\d+)", age_str)
            if match:
                years = int(match.group(1))
                duration = cls.build_iso8601_duration(years=years)
                if duration:
                    return {"iso8601duration": duration}

        except (ValueError, TypeError, AttributeError):
            pass

        return None

    @staticmethod
    def parse_review_date(date_str: Any) -> Optional[str]:
        """Parse ReviewDate to ISO8601 timestamp.

        Args:
            date_str: Date string to parse

        Returns:
            ISO8601 timestamp string or None
        """
        if pd.isna(date_str):
            return None

        try:
            # Parse format like "3/20/2021 12:27:42"
            dt = pd.to_datetime(date_str)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError, AttributeError):
            return None