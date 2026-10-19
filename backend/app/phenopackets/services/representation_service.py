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


def _norm_ts(ts: Any) -> Any:
    """Append 'Z' to naive ISO-8601 timestamps required by protobuf Timestamp."""
    if (
        isinstance(ts, str)
        and ts
        and not ts.endswith("Z")
        and "+" not in ts[10:]
        and "-" not in ts[10:]
    ):
        return f"{ts}Z"
    return ts


def _norm_time_element(te: Any) -> Any:
    """Normalize legacy TimeElement dicts and resolve oneof element collisions."""
    if not isinstance(te, dict):
        return te
    if "iso8601duration" in te and "age" not in te:
        return {"age": {"iso8601duration": te["iso8601duration"]}}
    age = te.get("age")
    if isinstance(age, dict):
        if "iso8601duration" in age:
            return {"age": {"iso8601duration": age["iso8601duration"]}}
        if "ontologyClass" in age:
            return {"ontologyClass": age["ontologyClass"]}
    if "ontologyClass" in te:
        return {"ontologyClass": te["ontologyClass"]}
    if "gestationalAge" in te:
        return {"gestationalAge": te["gestationalAge"]}
    if "ageRange" in te:
        return {"ageRange": te["ageRange"]}
    if "timestamp" in te:
        return {"timestamp": _norm_ts(te["timestamp"])}
    return te


def _normalize_for_ga4gh(document: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy fields while preserving VRS/clinical data in extensions."""
    doc = deepcopy(document)
    subj = doc.get("subject")
    if isinstance(subj, dict) and "timeAtLastEncounter" in subj:
        subj["timeAtLastEncounter"] = _norm_time_element(subj["timeAtLastEncounter"])
    for pf in doc.get("phenotypicFeatures", []):
        if isinstance(pf, dict):
            if "onset" in pf:
                pf["onset"] = _norm_time_element(pf["onset"])
            if "resolution" in pf:
                pf["resolution"] = _norm_time_element(pf["resolution"])
            for ev in pf.get("evidence", []):
                if isinstance(ev, dict) and isinstance(ev.get("reference"), dict):
                    ev["reference"].pop("recordedAt", None)
    for d in doc.get("diseases", []):
        if isinstance(d, dict):
            if "onset" in d:
                d["onset"] = _norm_time_element(d["onset"])
            if "resolution" in d:
                d["resolution"] = _norm_time_element(d["resolution"])
    md = doc.get("metaData")
    if isinstance(md, dict):
        if "created" in md:
            md["created"] = _norm_ts(md["created"])
        for u in md.get("updates", []):
            if isinstance(u, dict):
                if "timestamp" in u:
                    u["timestamp"] = _norm_ts(u["timestamp"])
                u.pop("publication", None)
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
                vi_exts = vi.pop("extensions", None)
                vd = vi.get("variationDescriptor")
                if isinstance(vd, dict):
                    exts = list(vd.get("extensions") or [])
                    if isinstance(vi_exts, list):
                        exts.extend(vi_exts)
                    for extra_key in ("vrsAllele", "molecularConsequences"):
                        if extra_key in vd:
                            val = vd.pop(extra_key)
                            if val is not None:
                                exts.append(
                                    {
                                        "name": extra_key,
                                        "value": (
                                            json.dumps(val)
                                            if not isinstance(val, str)
                                            else val
                                        ),
                                    }
                                )
                    for ext in exts:
                        if (
                            isinstance(ext, dict)
                            and "value" in ext
                            and not isinstance(ext["value"], str)
                        ):
                            ext["value"] = json.dumps(ext["value"])
                    if exts:
                        vd["extensions"] = exts
    return doc


def ga4gh_representation(document: dict[str, Any]) -> dict[str, Any]:
    """Redact local data and prove the result parses as Phenopackets v2."""
    try:
        public = strip_restricted_for_ga4gh(document)
        normalized = _normalize_for_ga4gh(public)
        message = ParseDict(normalized, Ga4ghPhenopacket(), ignore_unknown_fields=False)
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
