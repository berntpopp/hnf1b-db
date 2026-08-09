"""Pure, permutation-invariant projection of typed reports into GA4GH fields."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from app.phenopackets.curation.conflicts import ProjectionConflict
from app.phenopackets.curation.hashing import observation_digest, sha256_digest
from app.phenopackets.curation.models import (
    AssessmentStatus,
    ProjectionResolution,
    ReportObservation,
    ResolutionStrategy,
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


def _project_time(value: Any) -> dict[str, Any] | None:
    """Project only GA4GH-supported typed time semantics from a source cell."""
    if value is None:
        return None
    if value.kind == "ontologyClass":
        return {"ontologyClass": _term_json(value.term)}
    if value.kind == "age":
        return {"age": {"iso8601duration": value.iso8601_duration}}
    # Gestational and locally unprojected source times stay in the source ledger.
    return None


def _comparable_duration_days(value: Any) -> int | None:
    """Return a conservative sortable duration only for explicit age values."""
    if value is None or value.kind != "age" or not value.iso8601_duration:
        return None
    match = re.fullmatch(
        r"P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?", value.iso8601_duration
    )
    if match is None:
        return None
    years, months, weeks, days = (int(part or 0) for part in match.groups())
    return years * 365 + months * 30 + weeks * 7 + days


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


def _resolution_for(
    conflict: ProjectionConflict,
    resolutions: dict[str, ProjectionResolution],
    applied: set[str],
) -> ProjectionResolution | None:
    """Return a current resolution, rejecting stale decisions before projection."""
    resolution = resolutions.get(conflict.conflict_key)
    if resolution is None:
        return None
    if resolution.candidate_set_digest != conflict.candidate_set_digest:
        raise StaleResolutionError(
            f"resolution {resolution.resolution_id} is stale for "
            f"{conflict.conflict_key}"
        )
    applied.add(conflict.conflict_key)
    return resolution


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
    if len({item.observation_id for item in ordered}) != len(ordered):
        raise ValueError("duplicate observationId in projection input")
    if len({item.conflict_key for item in resolutions}) != len(resolutions):
        raise ValueError("duplicate resolutions for one conflictKey")
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
    applied_resolution_keys: set[str] = set()
    resolutions_by_key = {
        resolution.conflict_key: resolution for resolution in resolutions
    }
    stated_sexes = {sex for _, sex in sex_candidates}
    subject: dict[str, Any] = {"id": subject_id}
    if len(stated_sexes) == 1:
        subject["sex"] = next(iter(stated_sexes))
    elif len(stated_sexes) > 1:
        conflict = _conflict("subject:sex", sex_candidates)
        resolution = _resolution_for(
            conflict, resolutions_by_key, applied_resolution_keys
        )
        if resolution is None:
            conflicts.append(conflict)
        elif resolution.strategy is ResolutionStrategy.SELECT_OBSERVATIONS:
            selected = [
                value
                for identifier, value in sex_candidates
                if identifier in set(resolution.selected_observation_ids)
            ]
            if len(set(selected)) != 1:
                raise ValueError("sex resolution must select one clinical sex")
            subject["sex"] = selected[0]
        elif isinstance(resolution.resolved_value, str):
            subject["sex"] = resolution.resolved_value
        else:
            raise ValueError("subject sex resolvedValue must be a sex string")
    features: list[dict[str, Any]] = []
    for term_id in sorted(feature_candidates):
        candidates = feature_candidates[term_id]
        polarities = {candidate[1] for candidate in candidates}
        if len(polarities) > 1:
            conflict = _conflict(
                f"phenotype:{term_id}:polarity",
                ((identifier, status.value) for identifier, status, _ in candidates),
            )
            resolution = _resolution_for(
                conflict, resolutions_by_key, applied_resolution_keys
            )
            if resolution is not None:
                if resolution.strategy is ResolutionStrategy.SELECT_OBSERVATIONS:
                    selected_candidates: list[tuple[str, AssessmentStatus, Any]] = [
                        candidate
                        for candidate in candidates
                        if candidate[0] in set(resolution.selected_observation_ids)
                    ]
                    if (
                        not selected_candidates
                        or len({candidate[1] for candidate in selected_candidates}) != 1
                    ):
                        raise ValueError("resolution must select one clinical polarity")
                    candidates = selected_candidates
                elif resolution.resolved_value in {"PRESENT", "EXCLUDED"}:
                    candidates = [
                        candidate
                        for candidate in candidates
                        if candidate[1] is AssessmentStatus(resolution.resolved_value)
                    ]
                    if not candidates:
                        raise ValueError(
                            "phenotype resolvedValue must be a candidate polarity"
                        )
                else:
                    raise ValueError(
                        "phenotype polarity resolvedValue must be PRESENT or EXCLUDED"
                    )
            else:
                conflicts.append(conflict)
                continue

        status = next(iter({candidate[1] for candidate in candidates}))
        representative = candidates[0][2]
        modifier_sets = {_modifier_key(finding) for _, _, finding in candidates}
        feature: dict[str, Any] = {
            "type": _term_json(representative.term),
            "excluded": status is AssessmentStatus.EXCLUDED,
        }
        assessment_evidence = [
            item
            for observation in ordered
            for assessment in observation.phenotypes
            if assessment.assessment_status is status
            and any(finding.term.id == term_id for finding in assessment.findings)
            for item in assessment.evidence
        ]
        if assessment_evidence:
            feature["evidence"] = [
                {
                    "reference": {"id": item.reference},
                    "evidenceCode": _term_json(item.evidence_code),
                }
                for item in sorted(assessment_evidence, key=lambda item: item.reference)
            ]
        onset = next(
            (
                assessment.onset.value
                for observation in ordered
                for assessment in observation.phenotypes
                if assessment.assessment_status is status
                and any(finding.term.id == term_id for finding in assessment.findings)
                and assessment.onset is not None
                and assessment.onset.source_status.value == "stated"
                and assessment.onset.value is not None
            ),
            None,
        )
        projected_onset = _project_time(onset)
        if projected_onset is not None:
            feature["onset"] = projected_onset
        if len(modifier_sets) == 1 and next(iter(modifier_sets)):
            feature["modifiers"] = [
                {"id": identifier, "label": label}
                for identifier, label in next(iter(modifier_sets))
            ]
        elif len(modifier_sets) > 1:
            conflict = _conflict(
                f"phenotype:{term_id}:modifiers",
                (
                    (identifier, _modifier_key(finding))
                    for identifier, _, finding in candidates
                ),
            )
            resolution = _resolution_for(
                conflict, resolutions_by_key, applied_resolution_keys
            )
            if resolution is None:
                conflicts.append(conflict)
            elif resolution.strategy is ResolutionStrategy.SELECT_OBSERVATIONS:
                selected = [
                    finding
                    for identifier, _, finding in candidates
                    if identifier in set(resolution.selected_observation_ids)
                ]
                selected_sets = {_modifier_key(finding) for finding in selected}
                if len(selected_sets) != 1:
                    raise ValueError("modifier resolution must select one modifier set")
                feature["modifiers"] = [
                    {"id": identifier, "label": label}
                    for identifier, label in next(iter(selected_sets))
                ]
            elif isinstance(resolution.resolved_value, tuple):
                feature["modifiers"] = [
                    _term_json(modifier) for modifier in resolution.resolved_value
                ]
            else:
                raise ValueError("modifier resolvedValue must be a modifier list")
        features.append(feature)

    diseases_by_term: dict[tuple[str, str], Any] = {}
    for observation in ordered:
        for disease in observation.diseases:
            if disease.asserted:
                diseases_by_term.setdefault(
                    (disease.term.id, disease.term.label), disease
                )
    descriptors_by_id: dict[str, dict[str, Any]] = {}
    descriptor_observations: dict[str, list[ReportObservation]] = {}
    for observation in ordered:
        if observation.variant is None or observation.variant.normalized is None:
            continue
        typed_descriptor = observation.variant.normalized
        descriptor = typed_descriptor.model_dump(by_alias=True, mode="json")
        descriptor_id = typed_descriptor.id
        previous = descriptors_by_id.get(descriptor_id)
        if previous is not None and previous != descriptor:
            raise ValueError("VRS descriptor id maps to non-identical variations")
        descriptors_by_id[descriptor_id] = descriptor
        descriptor_observations.setdefault(descriptor_id, []).append(observation)

    interpretations = []
    for descriptor_id in sorted(descriptors_by_id):
        descriptor = descriptors_by_id[descriptor_id]
        variant_observations = descriptor_observations[descriptor_id]
        contributions = {
            observation.classification.contribution.value
            for observation in variant_observations
            if observation.classification is not None
            and observation.classification.contribution is not None
            and observation.classification.contribution.source_status.value == "stated"
        }
        verdicts = {
            observation.classification.verdict.value
            for observation in variant_observations
            if observation.classification is not None
            and observation.classification.verdict is not None
            and observation.classification.verdict.source_status.value == "stated"
        }
        resolved_values: dict[str, str | None] = {
            "contribution": next(iter(contributions), None),
            "acmg": next(iter(verdicts), None),
        }
        for field, values in (("contribution", contributions), ("acmg", verdicts)):
            if len(values) <= 1:
                continue
            conflict = _conflict(
                f"variant:{descriptor_id}:{field}",
                (
                    (
                        item.observation_id,
                        (
                            item.classification.contribution.value
                            if field == "contribution"
                            and item.classification
                            and item.classification.contribution
                            and item.classification.contribution.source_status.value
                            == "stated"
                            else item.classification.verdict.value
                            if field == "acmg"
                            and item.classification
                            and item.classification.verdict
                            and item.classification.verdict.source_status.value
                            == "stated"
                            else None
                        ),
                    )
                    for item in variant_observations
                ),
            )
            resolution = _resolution_for(
                conflict, resolutions_by_key, applied_resolution_keys
            )
            if resolution is None:
                conflicts.append(conflict)
                continue
            selected_classifications = [
                item
                for item in variant_observations
                if item.observation_id in set(resolution.selected_observation_ids)
            ]
            selected_values = {
                item.classification.contribution.value
                if field == "contribution"
                and item.classification
                and item.classification.contribution
                else item.classification.verdict.value
                if item.classification and item.classification.verdict
                else None
                for item in selected_classifications
            }
            selected_values.discard(None)
            if len(selected_values) != 1:
                raise ValueError("classification resolution must select one value")
            resolved_values[field] = next(iter(selected_values))
        if any(
            conflict.conflict_key.startswith(f"variant:{descriptor_id}:")
            for conflict in conflicts
        ):
            continue
        contribution = resolved_values["contribution"] or "UNKNOWN"
        if contribution == "UNKNOWN":
            contribution = "UNKNOWN_STATUS"
        if contribution not in {
            "UNKNOWN_STATUS",
            "REJECTED",
            "CANDIDATE",
            "CONTRIBUTORY",
            "CAUSATIVE",
        }:
            raise ValueError("contribution must be a GA4GH interpretation status")
        acmg = resolved_values["acmg"]
        variant_interpretation: dict[str, Any] = {"variationDescriptor": descriptor}
        if acmg is not None:
            variant_interpretation["acmgPathogenicityClassification"] = acmg
        interpretations.append(
            {
                "id": f"interpretation-{descriptor_id}",
                "progressStatus": "COMPLETED",
                "diagnosis": {
                    "genomicInterpretations": [
                        {
                            "subjectOrBiosampleId": subject_id,
                            "interpretationStatus": contribution,
                            "variantInterpretation": variant_interpretation,
                        }
                    ]
                },
            }
        )
    references = sorted(
        {
            reference
            for observation in ordered
            if observation.publication
            for reference in (
                (
                    [f"PMID:{observation.publication.pmid}"]
                    if observation.publication.pmid
                    else []
                )
                + (
                    [f"DOI:{observation.publication.doi}"]
                    if observation.publication.doi
                    else []
                )
            )
        }
    )
    phenopacket: dict[str, Any] = {
        "id": f"phenopacket-{subject_id}",
        "subject": subject,
        "phenotypicFeatures": features,
        "diseases": [
            {
                "term": _term_json(disease.term),
                **(
                    {"onset": _project_time(disease.onset.value)}
                    if disease.onset is not None
                    and disease.onset.source_status.value == "stated"
                    and _project_time(disease.onset.value) is not None
                    else {}
                ),
            }
            for _, disease in sorted(diseases_by_term.items())
        ],
        "interpretations": interpretations,
        "metaData": {
            "created": "2026-01-01T00:00:00Z",
            "createdBy": "HNF1B-DB deterministic projection",
            "resources": [],
            "phenopacketSchemaVersion": "2.0",
            "externalReferences": [{"id": reference} for reference in references],
        },
    }
    comparable_reported_ages = [
        (days, observation.ages.reported.value)
        for observation in ordered
        if observation.source.age_reported_semantics == "encounter_age"
        and observation.ages is not None
        and observation.ages.reported is not None
        and observation.ages.reported.source_status.value == "stated"
        and observation.ages.reported.value is not None
        and (days := _comparable_duration_days(observation.ages.reported.value))
        is not None
    ]
    reported_age = max(
        comparable_reported_ages, default=(0, None), key=lambda item: item[0]
    )[1]
    projected_reported_age = _project_time(reported_age)
    if projected_reported_age is not None:
        phenopacket["subject"]["timeAtLastEncounter"] = projected_reported_age
    input_digest = observation_digest(ordered)
    frozen_conflicts = tuple(sorted(conflicts, key=lambda item: item.conflict_key))
    _validate_resolutions(
        frozen_conflicts,
        [
            item
            for item in resolutions
            if item.conflict_key not in applied_resolution_keys
        ],
    )
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
