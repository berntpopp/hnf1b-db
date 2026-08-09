"""Profile-aware bridge between stored source curation and GA4GH JSON."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from google.protobuf.json_format import ParseDict
from phenopackets import Phenopacket
from pydantic import ValidationError

from app.phenopackets.curation.models import Hnf1bCurationProfile, ProjectionMetadata
from app.phenopackets.curation.projection import project_individual


class CurationProjectionError(ValueError):
    """Raised when v2 source truth cannot produce the claimed public packet."""


def canonicalize_curation_document(document: dict[str, Any]) -> dict[str, Any]:
    """Return a canonical v2 projection, leaving legacy documents untouched.

    Write/publish callers use this before persistence.  It deliberately
    recognizes an absent or pre-v2 extension as legacy rather than attempting
    to reinterpret historic fields as source observations.
    """
    block = document.get("hnf1bCuration")
    if not isinstance(block, dict) or "observationsById" not in block:
        return deepcopy(document)
    try:
        profile = Hnf1bCurationProfile.model_validate(block)
    except ValidationError as error:
        raise CurationProjectionError(str(error)) from error
    result = project_individual(
        list(profile.observations_by_id.values()),
        list(profile.resolutions_by_id.values()),
        algorithm_version=profile.projection.algorithm_version,
    )
    if result.blocking_conflicts:
        raise CurationProjectionError("curation projection has blocking conflicts")
    try:
        ParseDict(result.phenopacket, Phenopacket())
    except Exception as error:  # protobuf provides several concrete error types
        raise CurationProjectionError(
            "canonical projection is not GA4GH-valid"
        ) from error
    canonical = deepcopy(document)
    for field in (
        "subject",
        "phenotypicFeatures",
        "diseases",
        "interpretations",
        "metaData",
    ):
        canonical[field] = result.phenopacket[field]
    canonical["id"] = document.get("id", result.phenopacket["id"])
    canonical_block = profile.model_dump(by_alias=True, mode="json")
    canonical_block["projection"] = ProjectionMetadata(
        algorithm_version=profile.projection.algorithm_version,
        observations_digest=result.observations_digest,
        output_digest=result.output_digest,
    ).model_dump(by_alias=True, mode="json")
    canonical["hnf1bCuration"] = canonical_block
    return canonical
