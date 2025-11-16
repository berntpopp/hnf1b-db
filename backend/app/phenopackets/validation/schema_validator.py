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
            GA4GH Phenopackets v2 JSON schema (camelCase format)
        """
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["id", "subject", "metaData"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "subject": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {
                        "id": {"type": "string"},
                        "alternateIds": {"type": "array", "items": {"type": "string"}},
                        "dateOfBirth": {"type": "string"},
                        "timeAtLastEncounter": {"type": "object"},
                        "vitalStatus": {"type": "object"},
                        "sex": {
                            "type": "string",
                            "enum": [
                                "UNKNOWN_SEX",
                                "FEMALE",
                                "MALE",
                                "OTHER_SEX",
                            ],
                        },
                        "karyotypicSex": {"type": "string"},
                        "gender": {"$ref": "#/definitions/ontologyClass"},
                        "taxonomy": {"$ref": "#/definitions/ontologyClass"},
                    },
                },
                "phenotypicFeatures": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/phenotypicFeature"},
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
                "medicalActions": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/medicalAction"},
                },
                "files": {"type": "array", "items": {"$ref": "#/definitions/file"}},
                "metaData": {
                    "type": "object",
                    "required": ["created", "createdBy", "resources"],
                    "properties": {
                        "created": {"type": "string"},
                        "createdBy": {"type": "string"},
                        "submittedBy": {"type": "string"},
                        "resources": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["id", "name", "namespacePrefix"],
                            },
                        },
                        "phenopacketSchemaVersion": {"type": "string"},
                        "externalReferences": {"type": "array"},
                    },
                },
            },
            "definitions": {
                "ontologyClass": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                    },
                },
                "phenotypicFeature": {
                    "type": "object",
                    "required": ["type"],
                    "properties": {
                        "type": {"$ref": "#/definitions/ontologyClass"},
                        "excluded": {"type": "boolean"},
                        "severity": {"$ref": "#/definitions/ontologyClass"},
                        "modifiers": {
                            "type": "array",
                            "items": {"$ref": "#/definitions/ontologyClass"},
                        },
                        "onset": {"$ref": "#/definitions/timeElement"},
                        "resolution": {"$ref": "#/definitions/timeElement"},
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
                        "assay": {"$ref": "#/definitions/ontologyClass"},
                        "value": {"type": "object"},
                        "timeObserved": {"$ref": "#/definitions/timeElement"},
                        "procedure": {"type": "object"},
                        "interpretation": {"$ref": "#/definitions/ontologyClass"},
                    },
                },
                "disease": {
                    "type": "object",
                    "required": ["term"],
                    "properties": {
                        "term": {"$ref": "#/definitions/ontologyClass"},
                        "excluded": {"type": "boolean"},
                        "onset": {"$ref": "#/definitions/timeElement"},
                        "resolution": {"$ref": "#/definitions/timeElement"},
                        "diseaseStage": {
                            "type": "array",
                            "items": {"$ref": "#/definitions/ontologyClass"},
                        },
                        "clinicalTnmFinding": {
                            "type": "array",
                            "items": {"$ref": "#/definitions/ontologyClass"},
                        },
                        "primarySite": {"$ref": "#/definitions/ontologyClass"},
                    },
                },
                "interpretation": {
                    "type": "object",
                    "required": ["id", "progressStatus"],
                    "properties": {
                        "id": {"type": "string"},
                        "progressStatus": {
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
                                "disease": {"$ref": "#/definitions/ontologyClass"},
                                "genomicInterpretations": {
                                    "type": "array",
                                    "items": {
                                        "$ref": "#/definitions/genomicInterpretation"
                                    },
                                },
                            },
                        },
                    },
                },
                "genomicInterpretation": {
                    "type": "object",
                    "required": ["subjectOrBiosampleId", "interpretationStatus"],
                    "properties": {
                        "subjectOrBiosampleId": {"type": "string"},
                        "interpretationStatus": {
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
                        "variantInterpretation": {
                            "type": "object",
                            "properties": {
                                "acmgPathogenicityClassification": {"type": "string"},
                                "therapeuticActionability": {"type": "string"},
                                "variationDescriptor": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "variation": {"type": "object"},
                                        "label": {"type": "string"},
                                        "geneContext": {"type": "object"},
                                        "moleculeContext": {"type": "string"},
                                        "allelicState": {
                                            "$ref": "#/definitions/ontologyClass"
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
                "medicalAction": {
                    "type": "object",
                    "properties": {
                        "treatment": {"$ref": "#/definitions/treatment"},
                        "procedure": {"type": "object"},
                        "radiationTherapy": {"type": "object"},
                        "therapeuticRegimen": {"$ref": "#/definitions/ontologyClass"},
                        "treatmentTarget": {"$ref": "#/definitions/ontologyClass"},
                        "treatmentIntent": {"$ref": "#/definitions/ontologyClass"},
                        "responseToTreatment": {
                            "$ref": "#/definitions/ontologyClass"
                        },
                        "adverseEvents": {
                            "type": "array",
                            "items": {"$ref": "#/definitions/ontologyClass"},
                        },
                        "treatmentTerminationReason": {
                            "$ref": "#/definitions/ontologyClass"
                        },
                    },
                },
                "treatment": {
                    "type": "object",
                    "required": ["agent"],
                    "properties": {
                        "agent": {"$ref": "#/definitions/ontologyClass"},
                        "routeOfAdministration": {
                            "$ref": "#/definitions/ontologyClass"
                        },
                        "doseIntervals": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                        "drugType": {"type": "string"},
                    },
                },
                "file": {
                    "type": "object",
                    "required": ["uri"],
                    "properties": {
                        "uri": {"type": "string"},
                        "individualToFileIdentifiers": {"type": "object"},
                        "fileAttributes": {"type": "object"},
                    },
                },
                "timeElement": {
                    "type": "object",
                    "properties": {
                        "age": {"type": "object"},
                        "ageRange": {"type": "object"},
                        "ontologyClass": {"$ref": "#/definitions/ontologyClass"},
                        "timestamp": {"type": "string"},
                        "interval": {"type": "object"},
                    },
                },
                "evidence": {
                    "type": "object",
                    "required": ["evidenceCode"],
                    "properties": {
                        "evidenceCode": {"$ref": "#/definitions/ontologyClass"},
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
