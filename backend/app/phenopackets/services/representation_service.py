"""Authoritative server-side Phenopacket representations."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Literal

from google.protobuf.json_format import (  # type: ignore[import-untyped]
    MessageToDict,
    ParseDict,
    ParseError,
)
from phenopackets import Phenopacket as Ga4ghPhenopacket  # type: ignore[import-untyped]

from app.phenopackets.privacy import (
    PublicRepresentationError,
    sanitize_profile_document,
    strip_restricted_for_ga4gh,
)

Representation = Literal["ga4gh", "profile"]


class RepresentationValidationError(ValueError):
    """The requested representation cannot be safely produced."""


def normalized_representation(mode: str) -> Representation:
    """Map deprecated mode names to their explicit representation names."""
    aliases = {"conformant": "ga4gh", "full": "profile"}
    mode = aliases.get(mode, mode)
    if mode not in {"ga4gh", "profile"}:
        raise RepresentationValidationError(f"unknown representation {mode!r}")
    return mode  # type: ignore[return-value]


def _normalize_for_ga4gh(document: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy interpretation statuses and coerce extension values."""
    doc = deepcopy(document)
    valid_statuses = {
        "UNKNOWN_STATUS",
        "REJECTED",
        "CANDIDATE",
        "CONTRIBUTORY",
        "CAUSATIVE",
    }
    valid_progress = {
        "UNKNOWN_PROGRESS",
        "IN_PROGRESS",
        "COMPLETED",
        "SOLVED",
        "UNSOLVED",
    }
    for interp in doc.get("interpretations", []):
        if not isinstance(interp, dict):
            continue
        if (
            "progressStatus" in interp
            and interp["progressStatus"] not in valid_progress
        ):
            interp.pop("progressStatus", None)
        for gi in interp.get("diagnosis", {}).get("genomicInterpretations", []):
            if not isinstance(gi, dict):
                continue
            st = gi.get("interpretationStatus")
            if st not in valid_statuses:
                gi["interpretationStatus"] = (
                    "CAUSATIVE"
                    if st in {"PATHOGENIC", "LIKELY_PATHOGENIC"}
                    else "CANDIDATE"
                )
            vi = gi.get("variantInterpretation")
            if isinstance(vi, dict):
                vi.pop("extensions", None)
                vd = vi.get("variationDescriptor")
                if isinstance(vd, dict):
                    for ext in vd.get("extensions", []):
                        if (
                            isinstance(ext, dict)
                            and "value" in ext
                            and not isinstance(ext["value"], str)
                        ):
                            ext["value"] = json.dumps(ext["value"])
    return doc


def ga4gh_representation(document: dict[str, Any]) -> dict[str, Any]:
    """Redact local data and prove the result parses as Phenopackets v2."""
    try:
        public = strip_restricted_for_ga4gh(document)
        normalized = _normalize_for_ga4gh(public)
        message = ParseDict(normalized, Ga4ghPhenopacket(), ignore_unknown_fields=True)
    except (ParseError, PublicRepresentationError, TypeError, ValueError) as exc:
        raise RepresentationValidationError(str(exc)) from exc
    return MessageToDict(message, preserving_proto_field_name=False)


def profile_representation(document: dict[str, Any]) -> dict[str, Any]:
    """Return the curator-only profile representation after privacy checks."""
    try:
        return sanitize_profile_document(document)
    except PublicRepresentationError as exc:
        raise RepresentationValidationError(str(exc)) from exc


def represent(document: dict[str, Any], mode: str) -> dict[str, Any]:
    """Create a named representation from an authoritative revision document."""
    representation = normalized_representation(mode)
    if representation == "ga4gh":
        return ga4gh_representation(document)
    return profile_representation(document)
