"""Phenopacket validation utilities with comprehensive variant format validation."""

import re
from difflib import get_close_matches
from typing import Any, Dict, List, Optional, Tuple

import httpx
from jsonschema import Draft7Validator


class PhenopacketValidator:
    """Validator for phenopacket documents."""

    def __init__(self):
        """Initialize the validator with phenopacket schema."""
        self.schema = self._get_phenopacket_schema()
        self.validator = Draft7Validator(self.schema)

    def _get_phenopacket_schema(self) -> Dict[str, Any]:
        """Get the phenopacket JSON schema."""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["id", "subject", "meta_data"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "subject": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {
                        "id": {"type": "string"},
                        "alternate_ids": {"type": "array", "items": {"type": "string"}},
                        "date_of_birth": {"type": "string"},
                        "time_at_last_encounter": {"type": "object"},
                        "vital_status": {"type": "object"},
                        "sex": {
                            "type": "string",
                            "enum": [
                                "UNKNOWN_SEX",
                                "FEMALE",
                                "MALE",
                                "OTHER_SEX",
                            ],
                        },
                        "karyotypic_sex": {"type": "string"},
                        "gender": {"$ref": "#/definitions/ontology_class"},
                        "taxonomy": {"$ref": "#/definitions/ontology_class"},
                    },
                },
                "phenotypic_features": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/phenotypic_feature"},
                },
                "measurements": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/measurement"},
                },
                "biosamples": {"type": "array", "items": {"type": "object"}},
                "interpretations": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/interpretation"},
                },
                "diseases": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/disease"},
                },
                "medical_actions": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/medical_action"},
                },
                "files": {"type": "array", "items": {"$ref": "#/definitions/file"}},
                "meta_data": {
                    "type": "object",
                    "required": ["created", "created_by", "resources"],
                    "properties": {
                        "created": {"type": "string"},
                        "created_by": {"type": "string"},
                        "submitted_by": {"type": "string"},
                        "resources": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["id", "name", "namespace_prefix"],
                            },
                        },
                        "phenopacket_schema_version": {"type": "string"},
                        "external_references": {"type": "array"},
                    },
                },
            },
            "definitions": {
                "ontology_class": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                    },
                },
                "phenotypic_feature": {
                    "type": "object",
                    "required": ["type"],
                    "properties": {
                        "type": {"$ref": "#/definitions/ontology_class"},
                        "excluded": {"type": "boolean"},
                        "severity": {"$ref": "#/definitions/ontology_class"},
                        "modifiers": {
                            "type": "array",
                            "items": {"$ref": "#/definitions/ontology_class"},
                        },
                        "onset": {"$ref": "#/definitions/time_element"},
                        "resolution": {"$ref": "#/definitions/time_element"},
                        "evidence": {
                            "type": "array",
                            "items": {"$ref": "#/definitions/evidence"},
                        },
                    },
                },
                "measurement": {
                    "type": "object",
                    "required": ["assay", "value"],
                    "properties": {
                        "assay": {"$ref": "#/definitions/ontology_class"},
                        "value": {"type": "object"},
                        "time_observed": {"$ref": "#/definitions/time_element"},
                        "procedure": {"type": "object"},
                        "interpretation": {"$ref": "#/definitions/ontology_class"},
                    },
                },
                "disease": {
                    "type": "object",
                    "required": ["term"],
                    "properties": {
                        "term": {"$ref": "#/definitions/ontology_class"},
                        "excluded": {"type": "boolean"},
                        "onset": {"$ref": "#/definitions/time_element"},
                        "resolution": {"$ref": "#/definitions/time_element"},
                        "disease_stage": {
                            "type": "array",
                            "items": {"$ref": "#/definitions/ontology_class"},
                        },
                        "clinical_tnm_finding": {
                            "type": "array",
                            "items": {"$ref": "#/definitions/ontology_class"},
                        },
                        "primary_site": {"$ref": "#/definitions/ontology_class"},
                    },
                },
                "interpretation": {
                    "type": "object",
                    "required": ["id", "progress_status"],
                    "properties": {
                        "id": {"type": "string"},
                        "progress_status": {
                            "type": "string",
                            "enum": [
                                "UNKNOWN",
                                "IN_PROGRESS",
                                "COMPLETED",
                                "SOLVED",
                                "UNSOLVED",
                            ],
                        },
                        "diagnosis": {
                            "type": "object",
                            "properties": {
                                "disease": {"$ref": "#/definitions/ontology_class"},
                                "genomic_interpretations": {
                                    "type": "array",
                                    "items": {
                                        "$ref": "#/definitions/genomic_interpretation"
                                    },
                                },
                            },
                        },
                    },
                },
                "genomic_interpretation": {
                    "type": "object",
                    "required": ["subject_or_biosample_id", "interpretation_status"],
                    "properties": {
                        "subject_or_biosample_id": {"type": "string"},
                        "interpretation_status": {
                            "type": "string",
                            "enum": [
                                "UNKNOWN",
                                "PATHOGENIC",
                                "LIKELY_PATHOGENIC",
                                "UNCERTAIN_SIGNIFICANCE",
                                "LIKELY_BENIGN",
                                "BENIGN",
                            ],
                        },
                        "variant_interpretation": {
                            "type": "object",
                            "properties": {
                                "acmg_pathogenicity_classification": {"type": "string"},
                                "therapeutic_actionability": {"type": "string"},
                                "variation_descriptor": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "variation": {"type": "object"},
                                        "label": {"type": "string"},
                                        "gene_context": {"type": "object"},
                                        "molecule_context": {"type": "string"},
                                        "allelic_state": {
                                            "$ref": "#/definitions/ontology_class"
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
                "medical_action": {
                    "type": "object",
                    "properties": {
                        "treatment": {"$ref": "#/definitions/treatment"},
                        "procedure": {"type": "object"},
                        "radiation_therapy": {"type": "object"},
                        "therapeutic_regimen": {"$ref": "#/definitions/ontology_class"},
                        "treatment_target": {"$ref": "#/definitions/ontology_class"},
                        "treatment_intent": {"$ref": "#/definitions/ontology_class"},
                        "response_to_treatment": {
                            "$ref": "#/definitions/ontology_class"
                        },
                        "adverse_events": {
                            "type": "array",
                            "items": {"$ref": "#/definitions/ontology_class"},
                        },
                        "treatment_termination_reason": {
                            "$ref": "#/definitions/ontology_class"
                        },
                    },
                },
                "treatment": {
                    "type": "object",
                    "required": ["agent"],
                    "properties": {
                        "agent": {"$ref": "#/definitions/ontology_class"},
                        "route_of_administration": {
                            "$ref": "#/definitions/ontology_class"
                        },
                        "dose_intervals": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                        "drug_type": {"type": "string"},
                    },
                },
                "file": {
                    "type": "object",
                    "required": ["uri"],
                    "properties": {
                        "uri": {"type": "string"},
                        "individual_to_file_identifiers": {"type": "object"},
                        "file_attributes": {"type": "object"},
                    },
                },
                "time_element": {
                    "type": "object",
                    "properties": {
                        "age": {"type": "object"},
                        "age_range": {"type": "object"},
                        "ontology_class": {"$ref": "#/definitions/ontology_class"},
                        "timestamp": {"type": "string"},
                        "interval": {"type": "object"},
                    },
                },
                "evidence": {
                    "type": "object",
                    "required": ["evidence_code"],
                    "properties": {
                        "evidence_code": {"$ref": "#/definitions/ontology_class"},
                        "reference": {"type": "object"},
                    },
                },
            },
        }

    def validate(self, phenopacket: Dict[str, Any]) -> List[str]:
        """Validate a phenopacket document including variant formats.

        Args:
            phenopacket: The phenopacket document to validate

        Returns:
            List of validation error messages, empty if valid
        """
        errors = []
        for error in self.validator.iter_errors(phenopacket):
            error_path = ".".join(str(p) for p in error.path)
            errors.append(f"{error_path}: {error.message}")

        # Add variant format validation
        variant_errors = self.validate_variants_in_phenopacket(phenopacket)
        errors.extend(variant_errors)

        return errors

    def is_valid(self, phenopacket: Dict[str, Any]) -> bool:
        """Check if a phenopacket is valid.

        Args:
            phenopacket: The phenopacket document to validate

        Returns:
            True if valid, False otherwise
        """
        return self.validator.is_valid(phenopacket)

    def validate_hpo_term(self, term_id: str) -> bool:
        """Validate HPO term format.

        Args:
            term_id: HPO term ID to validate

        Returns:
            True if valid HPO term format
        """
        import re

        pattern = r"^HP:\d{7}$"
        return bool(re.match(pattern, term_id))

    def validate_mondo_term(self, term_id: str) -> bool:
        """Validate MONDO term format.

        Args:
            term_id: MONDO term ID to validate

        Returns:
            True if valid MONDO term format
        """
        import re

        pattern = r"^MONDO:\d{7}$"
        return bool(re.match(pattern, term_id))

    def validate_loinc_code(self, code: str) -> bool:
        """Validate LOINC code format.

        Args:
            code: LOINC code to validate

        Returns:
            True if valid LOINC code format
        """
        import re

        # LOINC codes are in format: 1-8 digits, hyphen, 1 digit
        pattern = r"^\d{1,8}-\d$"
        return bool(re.match(pattern, code))

    def validate_sex(self, sex: str) -> bool:
        """Validate sex value.

        Args:
            sex: Sex value to validate

        Returns:
            True if valid sex value
        """
        valid_values = ["UNKNOWN_SEX", "FEMALE", "MALE", "OTHER_SEX"]
        return sex in valid_values

    def validate_interpretation_status(self, status: str) -> bool:
        """Validate interpretation status.

        Args:
            status: Interpretation status to validate

        Returns:
            True if valid interpretation status
        """
        valid_statuses = [
            "UNKNOWN",
            "PATHOGENIC",
            "LIKELY_PATHOGENIC",
            "UNCERTAIN_SIGNIFICANCE",
            "LIKELY_BENIGN",
            "BENIGN",
        ]
        return status in valid_statuses

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
            # VEP REST API endpoint
            vep_url = f"https://rest.ensembl.org/vep/human/hgvs/{hgvs_notation}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    vep_url, headers={"Content-Type": "application/json"}, timeout=10.0
                )

                if response.status_code == 200:
                    vep_data = response.json()
                    return True, vep_data[0] if vep_data else None, []
                elif response.status_code == 400:
                    # Invalid notation - try to provide suggestions
                    suggestions = self._get_notation_suggestions(hgvs_notation)
                    return False, None, suggestions
                else:
                    return False, None, ["VEP service temporarily unavailable"]

        except Exception:
            # Fallback to regex validation if VEP is unavailable
            return self._fallback_validation(hgvs_notation), None, []

    def _get_notation_suggestions(self, invalid_notation: str) -> List[str]:
        """Generate suggestions for fixing invalid notation.

        Args:
            invalid_notation: The invalid notation string

        Returns:
            List of suggestions
        """
        suggestions = []

        # Common HGVS patterns for HNF1B
        common_patterns = [
            "NM_000458.4:c.544+1G>A",
            "NM_000458.4:c.1234A>T",
            "NM_000458.4:c.123del",
            "NM_000458.4:c.123_456dup",
            "chr17:g.36459258A>G",
            "17:36459258-37832869:DEL",
        ]

        # Check for common mistakes
        if "c." in invalid_notation or "p." in invalid_notation:
            if not invalid_notation.startswith("NM_"):
                suggestions.append(
                    "Did you mean to include a transcript? Try: NM_000458.4:"
                    + invalid_notation
                )

            # Check for missing dot after c or p
            if re.match(r"^c\d+", invalid_notation) or re.match(
                r"^p[A-Z]", invalid_notation
            ):
                suggestions.append(
                    f"Missing dot notation. Did you mean: {invalid_notation[0]}.{invalid_notation[1:]}?"
                )

        # Check for VCF-like format that needs conversion
        if re.match(r"^\d+[-:]\d+[-:][ATCG]+[-:][ATCG]+$", invalid_notation):
            parts = re.split(r"[-:]", invalid_notation)
            if len(parts) >= 4:
                suggestions.append(
                    f"For VCF format, use: chr17-{parts[0]}-{parts[2]}-{parts[3]}"
                )
                suggestions.append(
                    f"For HGVS genomic, use: NC_000017.11:g.{parts[0]}{parts[2]}>{parts[3]}"
                )

        # Check for CNV notation issues
        notation_lower = invalid_notation.lower()
        if re.search(r'\b(del|dup|deletion|duplication)\b', notation_lower):
            if ":" not in invalid_notation:
                suggestions.append(
                    "For CNVs, use format: 17:start-end:DEL or 17:start-end:DUP"
                )

        # Find similar valid patterns
        close_matches = get_close_matches(
            invalid_notation, common_patterns, n=3, cutoff=0.6
        )
        if close_matches:
            suggestions.append(f"Similar valid formats: {', '.join(close_matches)}")

        # General help
        if not suggestions:
            suggestions.append(
                "Valid formats: NM_000458.4:c.123A>G, chr17:g.36459258A>G, 17:start-end:DEL"
            )

        return suggestions

    def _fallback_validation(self, notation: str) -> bool:
        """Fallback validation using regex when VEP is unavailable."""
        # Try all validation patterns
        return (
            self._validate_hgvs_c(notation)
            or self._validate_hgvs_p(notation)
            or self._validate_hgvs_g(notation)
            or self._validate_vcf(notation)
            or self._is_ga4gh_cnv_notation(notation)
        )

    def validate_variant_formats(self, variant_descriptor: Dict[str, Any]) -> List[str]:
        """Validate variant formats in a variation descriptor.

        Args:
            variant_descriptor: Variation descriptor from phenopacket

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check for required variant identification
        if not variant_descriptor.get("id"):
            errors.append("Variant descriptor missing 'id' field")

        # Validate expressions if present
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

        # Validate VRS allele if present
        if "vrsAllele" in variant_descriptor:
            vrs_errors = self._validate_vrs_allele(variant_descriptor["vrsAllele"])
            errors.extend(vrs_errors)

        # Validate structural variants (CNVs)
        if "structuralType" in variant_descriptor:
            # Check for GA4GH CNV notation in expressions
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

    def _validate_hgvs_c(self, value: str) -> bool:
        """Validate HGVS c. notation.

        Examples: NM_000458.4:c.544+1G>A, c.1234A>T, c.123_456del
        """
        # More comprehensive pattern for c. notation
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
        # Pattern for p. notation
        pattern = r"^(NP_\d+\.\d+:)?p\.([A-Z][a-z]{2}\d+[A-Z][a-z]{2}|[A-Z][a-z]{2}\d+\*|[A-Z][a-z]{2}\d+[A-Z][a-z]{2}fs|\?)$"
        return bool(re.match(pattern, value))

    def _validate_hgvs_g(self, value: str) -> bool:
        """Validate HGVS g. notation.

        Examples: NC_000017.11:g.36459258A>G
        """
        # Pattern for g. notation with reference sequence
        pattern = r"^NC_\d+\.\d+:g\.\d+[ATCG]>[ATCG]$"
        return bool(re.match(pattern, value))

    def _validate_vcf(self, value: str) -> bool:
        """Validate VCF format.

        Examples: chr17-36459258-A-G, 17-36459258-A-G
        """
        # Pattern for VCF: chr-pos-ref-alt or with special alleles
        pattern = r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y|M)-\d+-[ATCG]+-([ATCG]+|<[A-Z]+>)$"
        return bool(re.match(pattern, value, re.IGNORECASE))

    def _validate_spdi(self, value: str) -> bool:
        """Validate SPDI notation.

        Examples: NC_000017.11:36459257:A:G
        """
        # Pattern for SPDI: sequence:position:deletion:insertion
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

        # Check required VRS fields
        if vrs_allele.get("type") != "Allele":
            errors.append("VRS allele must have type 'Allele'")

        # Validate location
        location = vrs_allele.get("location", {})
        if not location:
            errors.append("VRS allele missing 'location' field")
        elif location.get("type") != "SequenceLocation":
            errors.append("VRS location must have type 'SequenceLocation'")

        # Validate state
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

        # Check variants in interpretations
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


class PhenopacketSanitizer:
    """Sanitize and clean phenopacket data."""

    @staticmethod
    def sanitize_phenopacket(phenopacket: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize a phenopacket document.

        Args:
            phenopacket: The phenopacket to sanitize

        Returns:
            Sanitized phenopacket
        """

        # Remove null values recursively
        def remove_nulls(obj):
            if isinstance(obj, dict):
                return {k: remove_nulls(v) for k, v in obj.items() if v is not None}
            elif isinstance(obj, list):
                return [remove_nulls(item) for item in obj if item is not None]
            return obj

        # Remove empty arrays and objects
        def remove_empty(obj):
            if isinstance(obj, dict):
                cleaned = {k: remove_empty(v) for k, v in obj.items()}
                return {k: v for k, v in cleaned.items() if v not in [[], {}, None]}
            elif isinstance(obj, list):
                return [remove_empty(item) for item in obj]
            return obj

        phenopacket = remove_nulls(phenopacket)
        phenopacket = remove_empty(phenopacket)

        return phenopacket

    @staticmethod
    def normalize_ontology_term(term: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize an ontology term.

        Args:
            term: Ontology term to normalize

        Returns:
            Normalized ontology term
        """
        if not isinstance(term, dict):
            return term

        # Ensure ID is uppercase for standard ontologies
        if "id" in term and isinstance(term["id"], str):
            parts = term["id"].split(":")
            if len(parts) == 2 and parts[0].upper() in ["HP", "MONDO", "OMIM", "LOINC"]:
                term["id"] = f"{parts[0].upper()}:{parts[1]}"

        return term
