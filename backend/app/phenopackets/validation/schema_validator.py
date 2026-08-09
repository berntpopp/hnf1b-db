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
                "hnf1bCuration": {
                    "type": "object",
                    "description": (
                        "HNF1B-DB curated case-level facts. Namespaced and "
                        "explicitly NOT GA4GH content: conformant export strips "
                        "it. Stored inside the phenopacket so it inherits "
                        "revisioning, audit and the optimistic lock. Values are "
                        "checked against reference tables by the async domain "
                        "validator, not here."
                    ),
                    "additionalProperties": False,
                    "properties": {
                        "cohort": {"type": "string"},
                        "familyHistory": {"type": "string"},
                        "detectionMethod": {"type": "string"},
                        "curatedBy": {"type": "string"},
                        "curatedAt": {"type": "string"},
                        "publicationType": {"type": "string"},
                        "classificationSystem": {"type": "string"},
                        "classificationDate": {"type": "string"},
                        "classificationComment": {"type": "string"},
                        "caseComment": {"type": "string"},
                        "problematic": {"type": "string"},
                        "duplicateCheck": {"type": "string"},
                        "schemaVersion": {"type": "string"},
                        "definitionsVersion": {"type": "string"},
                        "sourceSubjectId": {"type": "string"},
                        "observationsById": {
                            "type": "object",
                            "additionalProperties": {
                                "$ref": "#/definitions/reportObservation"
                            },
                        },
                        "correctionsById": {
                            "type": "object",
                            "additionalProperties": {
                                "$ref": "#/definitions/curationCorrection"
                            },
                        },
                        "resolutionsById": {
                            "type": "object",
                            "additionalProperties": {
                                "$ref": "#/definitions/projectionResolution"
                            },
                        },
                        "projection": {"$ref": "#/definitions/projectionMetadata"},
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
                "sourceManifestRef": {
                    "type": "object",
                    "required": ["provider", "datasetId", "sheet", "manifestSha256"],
                    "additionalProperties": False,
                    "properties": {
                        "provider": {"type": "string"},
                        "datasetId": {"type": "string"},
                        "sheet": {"type": "string"},
                        "rowNumber": {"type": ["integer", "null"]},
                        "rowHmacSha256": {"type": ["string", "null"]},
                        "manifestSha256": {"type": "string"},
                        "importRunId": {"type": ["string", "null"]},
                        "importedAt": {"type": ["string", "null"]},
                    },
                },
                "subjectObservation": {
                    "type": "object",
                    "required": ["individualId", "sourceSubjectId", "reportId"],
                    "additionalProperties": False,
                    "properties": {
                        "individualId": {"type": "string"},
                        "sourceSubjectId": {"type": "string"},
                        "reportId": {"type": "string"},
                        "individualIdentifier": {
                            "anyOf": [
                                {"$ref": "#/definitions/observedValue"},
                                {"type": "null"},
                            ]
                        },
                        "sex": {
                            "anyOf": [
                                {"$ref": "#/definitions/observedValue"},
                                {"type": "null"},
                            ]
                        },
                    },
                },
                "observedValue": {
                    "type": "object",
                    "required": ["raw", "sourceStatus"],
                    "additionalProperties": False,
                    "properties": {
                        "raw": {"type": "string"},
                        "sourceStatus": {
                            "enum": [
                                "stated",
                                "not_reported",
                                "not_applicable",
                                "unknown",
                                "blank",
                            ]
                        },
                        "value": {},
                        "correctionIds": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "reportObservation": {
                    "type": "object",
                    "required": ["observationId", "origin", "source", "identifiers"],
                    "additionalProperties": False,
                    "properties": {
                        "observationId": {"type": "string"},
                        "origin": {"type": "string"},
                        "source": {"$ref": "#/definitions/sourceManifestRef"},
                        "identifiers": {"$ref": "#/definitions/subjectObservation"},
                        "publication": {"type": ["object", "null"]},
                        "case": {"type": ["object", "null"]},
                        "ages": {"type": ["object", "null"]},
                        "variant": {"type": ["object", "null"]},
                        "classification": {"type": ["object", "null"]},
                        "diseases": {"type": "array", "items": {"type": "object"}},
                        "phenotypes": {"type": "array", "items": {"type": "object"}},
                        "sourceReview": {"type": ["object", "null"]},
                        "notes": {"type": ["object", "null"]},
                    },
                },
                "curationCorrection": {
                    "type": "object",
                    "required": [
                        "correctionId",
                        "jsonPointer",
                        "preimage",
                        "postimage",
                        "sourceManifestSha256",
                        "reason",
                        "actorId",
                        "createdAt",
                    ],
                    "additionalProperties": False,
                    "properties": {
                        "correctionId": {"type": "string"},
                        "jsonPointer": {"type": "string"},
                        "preimage": {},
                        "postimage": {},
                        "sourceManifestSha256": {"type": "string"},
                        "reason": {"type": "string"},
                        "actorId": {"type": "integer"},
                        "createdAt": {"type": "string"},
                        "supersedesCorrectionId": {"type": ["string", "null"]},
                    },
                },
                "projectionResolution": {
                    "type": "object",
                    "required": [
                        "resolutionId",
                        "conflictKey",
                        "candidateSetDigest",
                        "strategy",
                        "reason",
                        "resolvedByUserId",
                        "resolvedAt",
                    ],
                    "additionalProperties": False,
                    "properties": {
                        "resolutionId": {"type": "string"},
                        "conflictKey": {"type": "string"},
                        "candidateSetDigest": {"type": "string"},
                        "strategy": {"type": "string"},
                        "selectedObservationIds": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "resolvedValue": {},
                        "reason": {"type": "string"},
                        "resolvedByUserId": {"type": "integer"},
                        "resolvedAt": {"type": "string"},
                    },
                },
                "projectionMetadata": {
                    "type": "object",
                    "required": ["algorithmVersion"],
                    "additionalProperties": False,
                    "properties": {
                        "algorithmVersion": {"type": "string"},
                        "observationsDigest": {"type": ["string", "null"]},
                        "outputDigest": {"type": ["string", "null"]},
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
                    # "id" is deliberately NOT required: 365 of the 923 corpus
                    # records have no id on their sole interpretation (measured
                    # 2026-07-30). GA4GH's Interpretation.id is a plain string
                    # field with no cardinality constraint of its own; this
                    # schema was stricter than the corpus it validates. See
                    # docs/adr/0003-ga4gh-conformance-debt.md — this is not one
                    # of D1-D5, just an overly strict schema, so no ADR entry.
                    "required": ["progressStatus"],
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
                                        "moleculeContext": {
                                            "type": "string",
                                            "enum": [
                                                "unspecified_molecule_context",
                                                "genomic",
                                                "transcript",
                                                "protein",
                                            ],
                                        },
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
                        "responseToTreatment": {"$ref": "#/definitions/ontologyClass"},
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
                        # GA4GH's conformant shape is an object wrapping
                        # iso8601duration, e.g. {"iso8601duration": "P13Y"}.
                        # 672 phenotypicFeatures[].onset.age occurrences across
                        # the corpus (measured 2026-07-30) instead store a bare
                        # ISO-8601 duration string, e.g. "P13Y" directly. Accept
                        # both shapes, matching how the frontend already reads
                        # age (frontend/src/utils/age.js::readEncounterAge).
                        # diseases[].onset.age never uses the bare-string form
                        # in the corpus (216 uses, all object-shaped) and
                        # subject.timeAtLastEncounter is validated only as
                        # "type": "object" below (not through this $ref), so
                        # neither needed a matching change.
                        "age": {"type": ["object", "string"]},
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
        curation = phenopacket.get("hnf1bCuration")
        if isinstance(curation, dict) and (
            "observationsById" in curation or "schemaVersion" in curation
        ):
            from pydantic import ValidationError

            from app.phenopackets.curation.models import Hnf1bCurationProfile

            try:
                Hnf1bCurationProfile.model_validate(curation)
            except ValidationError as error:
                errors.extend(
                    f"hnf1bCuration.{item['loc']}: {item['msg']}"
                    for item in error.errors()
                )
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
