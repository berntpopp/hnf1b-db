"""Variant format validation for HGVS, VCF, VRS, and CNV notations."""

import re
from difflib import get_close_matches
from typing import Any, Dict, List, Optional, Tuple

import httpx


class VariantValidator:
    """Validates variant formats including HGVS, VCF, VRS, and CNV notations."""

    async def validate_variant_with_vep(
        self, hgvs_notation: str
    ) -> Tuple[bool, Optional[Dict], List[str]]:
        """Validate variant using Ensembl VEP API.

        Args:
            hgvs_notation: HGVS notation to validate

        Returns:
            Tuple of (is_valid, vep_data, suggestions)
        """
        try:
            vep_url = f"https://rest.ensembl.org/vep/human/hgvs/{hgvs_notation}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    vep_url, headers={"Content-Type": "application/json"}, timeout=10.0
                )

                if response.status_code == 200:
                    vep_data = response.json()
                    return True, vep_data[0] if vep_data else None, []
                elif response.status_code == 400:
                    suggestions = self._get_notation_suggestions(hgvs_notation)
                    return False, None, suggestions
                else:
                    return False, None, ["VEP service temporarily unavailable"]

        except Exception:
            return self._fallback_validation(hgvs_notation), None, []

    def validate_variant_formats(self, variant_descriptor: Dict[str, Any]) -> List[str]:
        """Validate variant formats in a variation descriptor.

        Args:
            variant_descriptor: Variation descriptor from phenopacket

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not variant_descriptor.get("id"):
            errors.append("Variant descriptor missing 'id' field")

        expressions = variant_descriptor.get("expressions", [])
        for expr in expressions:
            syntax = expr.get("syntax", "")
            value = expr.get("value", "")

            if syntax == "hgvs.c":
                if not self._validate_hgvs_c(value):
                    suggestions = self._get_notation_suggestions(value)
                    error_msg = f"Invalid HGVS c. notation: {value}"
                    if suggestions:
                        error_msg += f" | Suggestions: {'; '.join(suggestions)}"
                    errors.append(error_msg)
            elif syntax == "hgvs.p":
                if not self._validate_hgvs_p(value):
                    suggestions = self._get_notation_suggestions(value)
                    error_msg = f"Invalid HGVS p. notation: {value}"
                    if suggestions:
                        error_msg += f" | Suggestions: {'; '.join(suggestions)}"
                    errors.append(error_msg)
            elif syntax == "hgvs.g":
                if not self._validate_hgvs_g(value):
                    suggestions = self._get_notation_suggestions(value)
                    error_msg = f"Invalid HGVS g. notation: {value}"
                    if suggestions:
                        error_msg += f" | Suggestions: {'; '.join(suggestions)}"
                    errors.append(error_msg)
            elif syntax == "vcf":
                if not self._validate_vcf(value):
                    errors.append(f"Invalid VCF format: {value}")
            elif syntax == "spdi":
                if not self._validate_spdi(value):
                    errors.append(f"Invalid SPDI format: {value}")

        if "vrsAllele" in variant_descriptor:
            vrs_errors = self._validate_vrs_allele(variant_descriptor["vrsAllele"])
            errors.extend(vrs_errors)

        if "structuralType" in variant_descriptor:
            has_valid_cnv = False
            for expr in expressions:
                if expr.get("syntax") == "iscn" or self._is_ga4gh_cnv_notation(
                    expr.get("value", "")
                ):
                    has_valid_cnv = True
                    break
            if not has_valid_cnv:
                errors.append("Structural variant missing valid CNV notation")

        return errors

    def validate_variants_in_phenopacket(
        self, phenopacket: Dict[str, Any]
    ) -> List[str]:
        """Validate all variants in a phenopacket.

        Args:
            phenopacket: Complete phenopacket document

        Returns:
            List of all variant validation errors
        """
        all_errors = []

        for interpretation in phenopacket.get("interpretations", []):
            genomic_interps = interpretation.get("diagnosis", {}).get(
                "genomicInterpretations", []
            )
            for gi in genomic_interps:
                variant_descriptor = gi.get("variantInterpretation", {}).get(
                    "variationDescriptor", {}
                )
                if variant_descriptor:
                    errors = self.validate_variant_formats(variant_descriptor)
                    if errors:
                        subject_id = gi.get("subjectOrBiosampleId", "unknown")
                        all_errors.extend(
                            [f"Subject {subject_id}: {e}" for e in errors]
                        )

        return all_errors

    def _get_notation_suggestions(self, invalid_notation: str) -> List[str]:
        """Generate suggestions for fixing invalid notation.

        Args:
            invalid_notation: The invalid notation string

        Returns:
            List of suggestions
        """
        suggestions = []

        common_patterns = [
            "NM_000458.4:c.544+1G>A",
            "NM_000458.4:c.1234A>T",
            "NM_000458.4:c.123del",
            "NM_000458.4:c.123_456dup",
            "chr17:g.36459258A>G",
            "17:36459258-37832869:DEL",
        ]

        if "c." in invalid_notation or "p." in invalid_notation:
            if not invalid_notation.startswith("NM_"):
                suggestions.append(
                    "Did you mean to include a transcript? Try: NM_000458.4:"
                    + invalid_notation
                )

            if re.match(r"^c\d+", invalid_notation) or re.match(
                r"^p[A-Z]", invalid_notation
            ):
                suggestions.append(
                    f"Missing dot notation. Did you mean: {invalid_notation[0]}.{invalid_notation[1:]}?"
                )

        if re.match(r"^\d+[-:]\d+[-:][ATCG]+[-:][ATCG]+$", invalid_notation):
            parts = re.split(r"[-:]", invalid_notation)
            if len(parts) >= 4:
                suggestions.append(
                    f"For VCF format, use: chr17-{parts[0]}-{parts[2]}-{parts[3]}"
                )
                suggestions.append(
                    f"For HGVS genomic, use: NC_000017.11:g.{parts[0]}{parts[2]}>{parts[3]}"
                )

        notation_lower = invalid_notation.lower()
        if re.search(r"\b(del|dup|deletion|duplication)\b", notation_lower):
            if ":" not in invalid_notation:
                suggestions.append(
                    "For CNVs, use format: 17:start-end:DEL or 17:start-end:DUP"
                )

        close_matches = get_close_matches(
            invalid_notation, common_patterns, n=3, cutoff=0.6
        )
        if close_matches:
            suggestions.append(f"Similar valid formats: {', '.join(close_matches)}")

        if not suggestions:
            suggestions.append(
                "Valid formats: NM_000458.4:c.123A>G, chr17:g.36459258A>G, 17:start-end:DEL"
            )

        return suggestions

    def _fallback_validation(self, notation: str) -> bool:
        """Fallback validation using regex when VEP is unavailable."""
        return (
            self._validate_hgvs_c(notation)
            or self._validate_hgvs_p(notation)
            or self._validate_hgvs_g(notation)
            or self._validate_vcf(notation)
            or self._is_ga4gh_cnv_notation(notation)
        )

    def _validate_hgvs_c(self, value: str) -> bool:
        """Validate HGVS c. notation.

        Examples: NM_000458.4:c.544+1G>A, c.1234A>T, c.123_456del
        """
        patterns = [
            r"^(NM_\d+\.\d+:)?c\.([+\-*]?\d+[+\-]?\d*)([ATCG]>[ATCG])$",  # Substitution
            r"^(NM_\d+\.\d+:)?c\.\d+(_\d+)?del([ATCG]+)?$",  # Deletion
            r"^(NM_\d+\.\d+:)?c\.\d+(_\d+)?dup([ATCG]+)?$",  # Duplication
            r"^(NM_\d+\.\d+:)?c\.\d+(_\d+)?ins([ATCG]+)$",  # Insertion
            r"^(NM_\d+\.\d+:)?c\.\d+[+\-]\d+[ATCG]>[ATCG]$",  # Intronic
        ]
        return any(bool(re.match(pattern, value)) for pattern in patterns)

    def _validate_hgvs_p(self, value: str) -> bool:
        """Validate HGVS p. notation.

        Examples: NP_000449.3:p.Arg181*, p.Val123Phe
        """
        pattern = r"^(NP_\d+\.\d+:)?p\.([A-Z][a-z]{2}\d+[A-Z][a-z]{2}|[A-Z][a-z]{2}\d+\*|[A-Z][a-z]{2}\d+[A-Z][a-z]{2}fs|\?)$"
        return bool(re.match(pattern, value))

    def _validate_hgvs_g(self, value: str) -> bool:
        """Validate HGVS g. notation.

        Examples: NC_000017.11:g.36459258A>G
        """
        pattern = r"^NC_\d+\.\d+:g\.\d+[ATCG]>[ATCG]$"
        return bool(re.match(pattern, value))

    def _validate_vcf(self, value: str) -> bool:
        """Validate VCF format.

        Examples: chr17-36459258-A-G, 17-36459258-A-G
        """
        pattern = r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y|M)-\d+-[ATCG]+-([ATCG]+|<[A-Z]+>)$"
        return bool(re.match(pattern, value, re.IGNORECASE))

    def _validate_spdi(self, value: str) -> bool:
        """Validate SPDI notation.

        Examples: NC_000017.11:36459257:A:G
        """
        pattern = r"^NC_\d+\.\d+:\d+:[ATCG]*:[ATCG]+$"
        return bool(re.match(pattern, value))

    def _is_ga4gh_cnv_notation(self, value: str) -> bool:
        """Check if value matches GA4GH CNV notation.

        Examples: 17:36459258-37832869:DEL, 17:36459258-37832869:DUP
        """
        pattern = r"^([1-9]|1[0-9]|2[0-2]|X|Y):\d+-\d+:(DEL|DUP|INS|INV)$"
        return bool(re.match(pattern, value))

    def _validate_vrs_allele(self, vrs_allele: Dict[str, Any]) -> List[str]:
        """Validate VRS 2.0 allele structure."""
        errors = []

        if vrs_allele.get("type") != "Allele":
            errors.append("VRS allele must have type 'Allele'")

        location = vrs_allele.get("location", {})
        if not location:
            errors.append("VRS allele missing 'location' field")
        elif location.get("type") != "SequenceLocation":
            errors.append("VRS location must have type 'SequenceLocation'")

        state = vrs_allele.get("state", {})
        if not state:
            errors.append("VRS allele missing 'state' field")
        elif state.get("type") not in [
            "LiteralSequenceExpression",
            "ReferenceLengthExpression",
        ]:
            errors.append(
                "VRS state must be LiteralSequenceExpression or ReferenceLengthExpression"
            )

        return errors
