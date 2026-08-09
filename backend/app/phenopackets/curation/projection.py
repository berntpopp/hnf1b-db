"""Pure, permutation-invariant projection of typed reports into GA4GH fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.phenopackets.curation.conflicts import ProjectionConflict
from app.phenopackets.curation.hashing import observation_digest, sha256_digest
from app.phenopackets.curation.models import (
    AssessmentStatus,
    ProjectionResolution,
    ReportObservation,
)


class StaleResolutionError(ValueError):
    """A stored resolution no longer corresponds to the current candidates."""


@dataclass(frozen=True)
class ProjectionResult:
    """Canonical GA4GH projection plus traceable publication-blocking conditions."""

    phenopacket: dict[str, Any]
    warnings: tuple[str, ...]
    blocking_conflicts: tuple[ProjectionConflict, ...]
    observations_digest: str
    output_digest: str


def _term_json(term: Any) -> dict[str, str]:
    return {"id": term.id, "label": term.label}


def _modifier_key(finding: Any) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted((modifier.id, modifier.label) for modifier in finding.modifiers)
    )


def _conflict(
    conflict_key: str,
    candidates: Iterable[tuple[str, Any]],
) -> ProjectionConflict:
    ordered = tuple(sorted(candidates, key=lambda item: item[0]))
    return ProjectionConflict(
        conflict_key=conflict_key,
        observation_ids=tuple(candidate[0] for candidate in ordered),
        candidates=ordered,
    )


def _validate_resolutions(
    conflicts: tuple[ProjectionConflict, ...],
    resolutions: Iterable[ProjectionResolution],
) -> None:
    by_key = {conflict.conflict_key: conflict for conflict in conflicts}
    for resolution in resolutions:
        conflict = by_key.get(resolution.conflict_key)
        if (
            conflict is None
            or conflict.candidate_set_digest != resolution.candidate_set_digest
        ):
            raise StaleResolutionError(
                "resolution "
                f"{resolution.resolution_id} is stale for {resolution.conflict_key}"
            )


def project_individual(
    observations: list[ReportObservation],
    resolutions: list[ProjectionResolution],
    *,
    algorithm_version: str,
) -> ProjectionResult:
    """Project a single individual's reports without using their input order.

    The returned document contains only GA4GH fields. Source-ledger values and
    conflicts are deliberately returned separately so public serialization can
    never accidentally expose local source provenance.
    """
    ordered = sorted(observations, key=lambda item: item.observation_id)
    if not ordered:
        raise ValueError("at least one observation is required for projection")
    subject_ids = {observation.identifiers.individual_id for observation in ordered}
    if len(subject_ids) != 1:
        raise ValueError("all observations must have the same individualId")
    subject_id = next(iter(subject_ids))
    sex_candidates = [
        (observation.observation_id, observation.identifiers.sex.value)
        for observation in ordered
        if observation.identifiers.sex is not None
        and observation.identifiers.sex.source_status.value == "stated"
        and observation.identifiers.sex.value is not None
    ]

    feature_candidates: dict[str, list[tuple[str, AssessmentStatus, Any]]] = {}
    for observation in ordered:
        for assessment in observation.phenotypes:
            if assessment.assessment_status not in {
                AssessmentStatus.PRESENT,
                AssessmentStatus.EXCLUDED,
            }:
                continue
            for finding in assessment.findings:
                feature_candidates.setdefault(finding.term.id, []).append(
                    (observation.observation_id, assessment.assessment_status, finding)
                )

    conflicts: list[ProjectionConflict] = []
    stated_sexes = {sex for _, sex in sex_candidates}
    subject: dict[str, str] = {"id": subject_id}
    if len(stated_sexes) == 1:
        subject["sex"] = next(iter(stated_sexes))
    elif len(stated_sexes) > 1:
        conflicts.append(_conflict("subject:sex", sex_candidates))
    features: list[dict[str, Any]] = []
    for term_id in sorted(feature_candidates):
        candidates = feature_candidates[term_id]
        polarities = {candidate[1] for candidate in candidates}
        if len(polarities) > 1:
            conflicts.append(
                _conflict(
                    f"phenotype:{term_id}:polarity",
                    (
                        (identifier, status.value)
                        for identifier, status, _ in candidates
                    ),
                )
            )
            continue

        status = next(iter(polarities))
        representative = candidates[0][2]
        modifier_sets = {_modifier_key(finding) for _, _, finding in candidates}
        feature: dict[str, Any] = {
            "type": _term_json(representative.term),
            "excluded": status is AssessmentStatus.EXCLUDED,
        }
        if len(modifier_sets) == 1 and next(iter(modifier_sets)):
            feature["modifiers"] = [
                {"id": identifier, "label": label}
                for identifier, label in next(iter(modifier_sets))
            ]
        elif len(modifier_sets) > 1:
            conflicts.append(
                _conflict(
                    f"phenotype:{term_id}:modifiers",
                    (
                        (identifier, _modifier_key(finding))
                        for identifier, _, finding in candidates
                    ),
                )
            )
        features.append(feature)

    frozen_conflicts = tuple(sorted(conflicts, key=lambda item: item.conflict_key))
    _validate_resolutions(frozen_conflicts, resolutions)
    phenopacket = {
        "id": f"phenopacket-{subject_id}",
        "subject": subject,
        "phenotypicFeatures": features,
        "diseases": [],
        "interpretations": [],
        "metaData": {
            "created": "2026-01-01T00:00:00Z",
            "createdBy": "HNF1B-DB deterministic projection",
            "resources": [],
            "phenopacketSchemaVersion": "2.0",
        },
    }
    input_digest = observation_digest(ordered)
    output_digest = sha256_digest(
        {"algorithmVersion": algorithm_version, "phenopacket": phenopacket}
    )
    return ProjectionResult(
        phenopacket=phenopacket,
        warnings=(),
        blocking_conflicts=frozen_conflicts,
        observations_digest=input_digest,
        output_digest=output_digest,
    )
