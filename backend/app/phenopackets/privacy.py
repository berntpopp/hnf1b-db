"""Fail-closed serialization helpers for public and curator representations."""

from __future__ import annotations

import re
from typing import Any


class PublicRepresentationError(ValueError):
    """A document cannot safely be emitted as a public representation."""


_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_RESTRICTED_LOCAL_KEYS = {
    "hnf1bcuration",
    "email",
    "reviewer",
    "revieweremail",
    "reviewerid",
    "comment",
    "comments",
    "password",
    "credential",
    "credentials",
    "sourcereportid",
    "sourcedatasetid",
    "sourcesystem",
    "sourceidentity",
    "raw",
    "rawvalue",
    "rawvalues",
    "rawreport",
    "migrationmetadata",
}

# Phenopackets v2 JSON field names. This is intentionally an allowlist shared
# by every recursive level: an unrecognized key is never emitted publicly.
_GA4GH_KEYS = {
    "id",
    "label",
    "description",
    "subject",
    "sex",
    "gender",
    "taxonomy",
    "timeAtLastEncounter",
    "alternateIds",
    "dateOfBirth",
    "ageAtCollection",
    "phenotypicFeatures",
    "type",
    "excluded",
    "severity",
    "modifiers",
    "onset",
    "resolution",
    "evidence",
    "evidenceCode",
    "reference",
    "measurements",
    "assay",
    "value",
    "timeObserved",
    "procedure",
    "interpretation",
    "biosamples",
    "sampledTissue",
    "histologicalDiagnosis",
    "individualId",
    "diagnosticMarkers",
    "interpretations",
    "diagnosis",
    "disease",
    "genomicInterpretations",
    "subjectOrBiosampleId",
    "interpretationStatus",
    "variantInterpretation",
    "acmgPathogenicityClassification",
    "therapeuticActionability",
    "variationDescriptor",
    "variation",
    "geneContext",
    "expressions",
    "vcfRecord",
    "moleculeContext",
    "structuralType",
    "allelicState",
    "diseases",
    "term",
    "diseaseStage",
    "clinicalTnmFinding",
    "primarySite",
    "metaData",
    "created",
    "createdBy",
    "submittedBy",
    "resources",
    "name",
    "namespacePrefix",
    "url",
    "version",
    "iriPrefix",
    "externalReferences",
    "files",
    "uri",
    "fileFormat",
    "fileFormatVersion",
    "individualToFileIdentifiers",
    "htsFile",
    "genomeAssembly",
    "isObserved",
    "age",
    "ageRange",
    "ontologyClass",
    "timestamp",
    "interval",
    "start",
    "end",
}
_TOP_LEVEL_KEYS = {
    "id",
    "subject",
    "phenotypicFeatures",
    "measurements",
    "biosamples",
    "interpretations",
    "diseases",
    "metaData",
    "files",
}


def _forbidden_key(key: str) -> bool:
    """Return whether key represents local restricted provenance or PII."""
    lowered = key.lower()
    return lowered in _RESTRICTED_LOCAL_KEYS


def _redact(value: Any, *, top_level: bool = False) -> Any:
    """Recursively emit only allowlisted keys and reject forbidden values."""
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if not isinstance(value, dict):
        if isinstance(value, str) and _EMAIL.search(value):
            raise PublicRepresentationError("email-like values are not public")
        return value

    result: dict[str, Any] = {}
    for key, nested in value.items():
        if _forbidden_key(key):
            continue
        if key not in (_TOP_LEVEL_KEYS if top_level else _GA4GH_KEYS):
            continue
        result[key] = _redact(nested)
    return result


def redact_public_document(document: dict[str, Any]) -> dict[str, Any]:
    """Return the recursive public GA4GH-safe projection of ``document``.

    Local curation/provenance keys and unrecognized fields are default-denied;
    values that look like email addresses make the representation fail closed.
    """
    if not isinstance(document, dict):
        raise PublicRepresentationError("phenopacket document must be an object")
    return _redact(document, top_level=True)


def sanitize_profile_document(document: dict[str, Any]) -> dict[str, Any]:
    """Return curator profile content after refusing credential/email leakage."""

    def check(value: Any, path: str = "$") -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                nested_path = f"{path}.{key}"
                if _forbidden_key(key):
                    raise PublicRepresentationError(
                        f"profile contains restricted field at {nested_path}"
                    )
                check(nested, nested_path)
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                check(nested, f"{path}[{index}]")
        elif isinstance(value, str) and _EMAIL.search(value):
            raise PublicRepresentationError(
                f"profile contains restricted email-like value at {path}"
            )

    check(document)
    return document
