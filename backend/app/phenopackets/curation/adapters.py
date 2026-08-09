"""Profile-aware bridge between stored source curation and GA4GH JSON."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from google.protobuf.json_format import ParseDict  # type: ignore[import-untyped]
from phenopackets import Phenopacket  # type: ignore[import-untyped]
from pydantic import ValidationError

from app.phenopackets.curation.models import Hnf1bCurationProfile, ProjectionMetadata
from app.phenopackets.curation.projection import project_individual


class CurationProjectionError(ValueError):
    """Raised when v2 source truth cannot produce the claimed public packet."""

    def __init__(self, code: str, detail: str, *, conflicts: tuple[Any, ...] = ()):
        """Preserve a machine-readable error code and optional conflicts."""
        super().__init__(detail)
        self.code = code
        self.conflicts = conflicts


def _apply_active_corrections(block: dict[str, Any]) -> dict[str, Any]:
    """Apply active JSON-pointer postimages after proving every preimage."""
    corrected = deepcopy(block)
    corrections = corrected.get("correctionsById", {})
    if not isinstance(corrections, dict):
        return corrected
    ordered_ids: list[str] = []
    remaining = dict(corrections)
    while remaining:
        ready = [
            key
            for key, item in remaining.items()
            if not isinstance(item, dict)
            or not item.get("supersedesCorrectionId")
            or item["supersedesCorrectionId"] in ordered_ids
        ]
        if not ready:
            raise CurationProjectionError(
                "invalid_correction", "correction chain cycle"
            )
        for key in sorted(ready):
            ordered_ids.append(key)
            remaining.pop(key)
    for correction_id in ordered_ids:
        correction = corrections[correction_id]
        if not isinstance(correction, dict):
            raise CurationProjectionError("invalid_correction", "invalid correction")
        pointer = correction.get("jsonPointer")
        if not isinstance(pointer, str) or not pointer.startswith("/"):
            raise CurationProjectionError(
                "invalid_correction", "invalid correction pointer"
            )
        if (
            not pointer.startswith("/observationsById/")
            or not pointer.endswith("/value")
            or any(
                forbidden in pointer
                for forbidden in (
                    "/raw",
                    "/source/",
                    "/correctionsById",
                    "/resolutionsById",
                    "/projection",
                    "/audit",
                )
            )
        ):
            raise CurationProjectionError(
                "invalid_correction", "correction pointer targets immutable source data"
            )
        parts = [
            part.replace("~1", "/").replace("~0", "~")
            for part in pointer[1:].split("/")
        ]
        target: Any = corrected
        try:
            for part in parts[:-1]:
                target = target[int(part)] if isinstance(target, list) else target[part]
            leaf = parts[-1]
            current = target[int(leaf)] if isinstance(target, list) else target[leaf]
        except (IndexError, KeyError, TypeError, ValueError) as error:
            raise CurationProjectionError(
                "invalid_correction", "invalid correction pointer traversal"
            ) from error
        if current != correction.get("preimage"):
            raise CurationProjectionError(
                "correction_preimage_mismatch", "correction preimage does not match"
            )
        if isinstance(target, list):
            target[int(leaf)] = correction.get("postimage")
        else:
            target[leaf] = correction.get("postimage")
    return corrected


def canonicalize_curation_document(
    document: dict[str, Any], *, publish: bool = False
) -> dict[str, Any]:
    """Return a canonical v2 projection, leaving legacy documents untouched.

    Write/publish callers use this before persistence.  It deliberately
    recognizes an absent or pre-v2 extension as legacy rather than attempting
    to reinterpret historic fields as source observations.
    """
    block = document.get("hnf1bCuration")
    if not isinstance(block, dict) or "observationsById" not in block:
        return deepcopy(document)
    try:
        profile = Hnf1bCurationProfile.model_validate(_apply_active_corrections(block))
    except ValidationError as error:
        raise CurationProjectionError("invalid_profile", str(error)) from error
    try:
        result = project_individual(
            list(profile.observations_by_id.values()),
            list(profile.resolutions_by_id.values()),
            algorithm_version=profile.projection.algorithm_version,
        )
    except (ValueError, TypeError) as error:
        raise CurationProjectionError("projection_error", str(error)) from error
    if result.blocking_conflicts and publish:
        raise CurationProjectionError(
            "blocking_conflicts",
            "curation projection has blocking conflicts",
            conflicts=result.blocking_conflicts,
        )
    try:
        ParseDict(result.phenopacket, Phenopacket())
    except Exception as error:  # protobuf provides several concrete error types
        raise CurationProjectionError(
            "parser_error", "canonical projection is not GA4GH-valid"
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
    # Corrections are an overlay for projection. Persist their original raw
    # source profile so re-canonicalizing is idempotent rather than applying a
    # postimage as though it were a fresh preimage.
    canonical_block = deepcopy(block)
    canonical_block["projection"] = ProjectionMetadata(
        algorithm_version=profile.projection.algorithm_version,
        observations_digest=result.observations_digest,
        output_digest=result.output_digest,
    ).model_dump(by_alias=True, mode="json")
    if result.blocking_conflicts:
        canonical_block["projection"]["blockingConflicts"] = [
            {
                "conflictKey": conflict.conflict_key,
                "candidateSetDigest": conflict.candidate_set_digest,
                "observationIds": list(conflict.observation_ids),
            }
            for conflict in result.blocking_conflicts
        ]
    canonical["hnf1bCuration"] = canonical_block
    return canonical
