"""Ontology term validation for HPO, MONDO, and LOINC."""

import re


class OntologyValidator:
    """Validates ontology term formats (HPO, MONDO, LOINC)."""

    def validate_hpo_term(self, term_id: str) -> bool:
        """Validate HPO term format.

        Args:
            term_id: HPO term ID to validate

        Returns:
            True if valid HPO term format
        """
        pattern = r"^HP:\d{7}$"
        return bool(re.match(pattern, term_id))

    def validate_mondo_term(self, term_id: str) -> bool:
        """Validate MONDO term format.

        Args:
            term_id: MONDO term ID to validate

        Returns:
            True if valid MONDO term format
        """
        pattern = r"^MONDO:\d{7}$"
        return bool(re.match(pattern, term_id))

    def validate_loinc_code(self, code: str) -> bool:
        """Validate LOINC code format.

        Args:
            code: LOINC code to validate

        Returns:
            True if valid LOINC code format
        """
        # LOINC codes are in format: 1-8 digits, hyphen, 1 digit
        pattern = r"^\d{1,8}-\d$"
        return bool(re.match(pattern, code))
