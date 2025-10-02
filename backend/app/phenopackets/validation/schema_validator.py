"""JSON Schema validation for Phenopackets v2."""

from typing import Any, Dict, List

from jsonschema import Draft7Validator


class SchemaValidator:
    """Validates phenopackets against JSON schema."""

    def __init__(self):
        """Initialize the validator with phenopacket schema."""
        self.schema = self._get_phenopacket_schema()
        self.validator = Draft7Validator(self.schema)

    def _get_phenopacket_schema(self) -> Dict[str, Any]:
        """Get the phenopacket JSON schema.

        Returns:
            GA4GH Phenopackets v2 JSON schema
        """
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
        """Validate a phenopacket against the JSON schema.

        Args:
            phenopacket: The phenopacket document to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        for error in self.validator.iter_errors(phenopacket):
            error_path = ".".join(str(p) for p in error.path)
            errors.append(f"{error_path}: {error.message}")
        return errors

    def is_valid(self, phenopacket: Dict[str, Any]) -> bool:
        """Check if a phenopacket is valid against the schema.

        Args:
            phenopacket: The phenopacket document to validate

        Returns:
            True if valid, False otherwise
        """
        return self.validator.is_valid(phenopacket)

    def validate_sex(self, sex: str) -> bool:
        """Validate sex value against allowed values.

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
