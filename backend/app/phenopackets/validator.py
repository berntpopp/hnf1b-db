"""Phenopacket validation facade for backward compatibility.

This module provides a unified interface to the modular validation system.
It maintains backward compatibility with existing code while delegating
to specialized validators.

For new code, consider using the specific validators directly from:
    app.phenopackets.validation.schema_validator
    app.phenopackets.validation.variant_validator
    app.phenopackets.validation.ontology_validator
    app.phenopackets.validation.sanitizer
"""

from typing import Any, Dict, List, Optional, Tuple

from app.phenopackets.validation import (
    OntologyValidator,
    PhenopacketSanitizer,
    SchemaValidator,
    VariantValidator,
)


class PhenopacketValidator:
    """Unified validator for phenopacket documents (facade pattern).

    This class delegates to specialized validators while maintaining
    the original API for backward compatibility.
    """

    def __init__(self):
        """Initialize the validator with all sub-validators."""
        self.schema_validator = SchemaValidator()
        self.variant_validator = VariantValidator()
        self.ontology_validator = OntologyValidator()

    def validate(self, phenopacket: Dict[str, Any]) -> List[str]:
        """Validate a phenopacket document including variant formats.

        Args:
            phenopacket: The phenopacket document to validate

        Returns:
            List of validation error messages, empty if valid
        """
        # Validate schema
        errors = self.schema_validator.validate(phenopacket)

        # Add variant format validation
        variant_errors = self.variant_validator.validate_variants_in_phenopacket(
            phenopacket
        )
        errors.extend(variant_errors)

        return errors

    def is_valid(self, phenopacket: Dict[str, Any]) -> bool:
        """Check if a phenopacket is valid.

        Args:
            phenopacket: The phenopacket document to validate

        Returns:
            True if valid, False otherwise
        """
        return self.schema_validator.is_valid(phenopacket)

    def validate_hpo_term(self, term_id: str) -> bool:
        """Validate HPO term format.

        Args:
            term_id: HPO term ID to validate

        Returns:
            True if valid HPO term format
        """
        return self.ontology_validator.validate_hpo_term(term_id)

    def validate_mondo_term(self, term_id: str) -> bool:
        """Validate MONDO term format.

        Args:
            term_id: MONDO term ID to validate

        Returns:
            True if valid MONDO term format
        """
        return self.ontology_validator.validate_mondo_term(term_id)

    def validate_loinc_code(self, code: str) -> bool:
        """Validate LOINC code format.

        Args:
            code: LOINC code to validate

        Returns:
            True if valid LOINC code format
        """
        return self.ontology_validator.validate_loinc_code(code)

    def validate_sex(self, sex: str) -> bool:
        """Validate sex value.

        Args:
            sex: Sex value to validate

        Returns:
            True if valid sex value
        """
        return self.schema_validator.validate_sex(sex)

    def validate_interpretation_status(self, status: str) -> bool:
        """Validate interpretation status.

        Args:
            status: Interpretation status to validate

        Returns:
            True if valid interpretation status
        """
        return self.schema_validator.validate_interpretation_status(status)

    async def validate_variant_with_vep(
        self, hgvs_notation: str
    ) -> Tuple[bool, Optional[Dict], List[str]]:
        """Validate variant using Ensembl VEP API.

        Args:
            hgvs_notation: HGVS notation to validate

        Returns:
            Tuple of (is_valid, vep_data, suggestions)
        """
        return await self.variant_validator.validate_variant_with_vep(hgvs_notation)

    def validate_variant_formats(self, variant_descriptor: Dict[str, Any]) -> List[str]:
        """Validate variant formats in a variation descriptor.

        Args:
            variant_descriptor: Variation descriptor from phenopacket

        Returns:
            List of validation errors (empty if valid)
        """
        return self.variant_validator.validate_variant_formats(variant_descriptor)

    def validate_variants_in_phenopacket(
        self, phenopacket: Dict[str, Any]
    ) -> List[str]:
        """Validate all variants in a phenopacket.

        Args:
            phenopacket: Complete phenopacket document

        Returns:
            List of all variant validation errors
        """
        return self.variant_validator.validate_variants_in_phenopacket(phenopacket)

    # Simple regex-based validation methods (used by variant_validator_endpoint)
    def _validate_hgvs_c(self, notation: str) -> bool:
        """Validate HGVS c. notation format."""
        import re

        return bool(re.match(r"^[A-Z_]+\d+\.\d+:c\.\d+[ACGT]>[ACGT]", notation))

    def _validate_hgvs_p(self, notation: str) -> bool:
        """Validate HGVS p. notation format."""
        import re

        return bool(re.match(r"^[A-Z_]+\d+\.\d+:p\.\w+", notation))

    def _validate_hgvs_g(self, notation: str) -> bool:
        """Validate HGVS g. notation format."""
        import re

        return bool(re.match(r"^(chr)?[\dXY]+:g\.\d+[ACGT]>[ACGT]", notation))

    def _validate_vcf(self, notation: str) -> bool:
        """Validate VCF format."""
        import re

        return bool(re.match(r"^(chr)?[\dXY]+-\d+-[ATCG]+-[ATCG]+", notation))

    def _is_ga4gh_cnv_notation(self, notation: str) -> bool:
        """Check if notation is GA4GH CNV format."""
        import re

        return bool(re.match(r"^[\dXY]+:\d+-\d+:(DEL|DUP|INS|INV)", notation))

    def _get_notation_suggestions(self, notation: str) -> List[str]:
        """Get suggestions for variant notation."""
        suggestions = []
        if ":" in notation:
            if "c." in notation:
                suggestions.append("Format: NM_000458.4:c.123A>G")
            elif "p." in notation:
                suggestions.append("Format: NP_000449.3:p.Arg181*")
            elif "g." in notation:
                suggestions.append("Format: chr17:g.36459258A>G")
        return suggestions

    def _fallback_validation(self, notation: str) -> bool:
        """Try all validation methods as fallback."""
        return (
            self._validate_hgvs_c(notation)
            or self._validate_hgvs_p(notation)
            or self._validate_hgvs_g(notation)
            or self._validate_vcf(notation)
            or self._is_ga4gh_cnv_notation(notation)
        )


# Export sanitizer for backward compatibility
__all__ = ["PhenopacketValidator", "PhenopacketSanitizer"]
