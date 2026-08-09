"""Lossless conversion of one validated source row into a typed observation."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from app.phenopackets.curation.definitions import (
    FINDING_DEFINITIONS,
    PHENOTYPE_QUESTIONS,
)
from app.phenopackets.curation.identifiers import (
    assessment_id_for,
    observation_id_for,
    row_hmac_sha256,
)
from app.phenopackets.curation.models import (
    AssessmentStatus,
    CaseObservation,
    ClassificationObservation,
    CurationStatus,
    NotesObservation,
    ObservationOrigin,
    ObservedValue,
    OntologyTerm,
    PhenotypeAssessment,
    PhenotypeFinding,
    PublicationObservation,
    ReportObservation,
    SourceManifestRef,
    SourceReviewProvenance,
    SourceStatus,
    SubjectObservation,
    TemporalObservation,
    VariantObservation,
)
from migration.phenopackets.laterality import (
    ModifierVocabulary,
    ModifierVocabularyError,
    parse_laterality,
)
from migration.phenopackets.publication_mapping import (
    PublicationMappingError,
    PublicationReference,
    resolve_publication,
)
from migration.phenopackets.source_column_map import SOURCE_COLUMNS
from migration.phenopackets.strict_age_parser import AgeParseError, parse_source_age


class ObservationExtractionError(ValueError):
    """A source row cannot satisfy the complete typed observation contract."""


_NOT_REPORTED = {"nr", "not reported"}
_NOT_APPLICABLE = {"na", "n/a", "not applicable"}
_PSEUDONYMOUS_REVIEWER_ID = re.compile(r"^reviewer-[a-z0-9][a-z0-9-]{0,62}$")
_PSEUDONYMOUS_REVIEWER_LABEL = re.compile(r"^(?:[Ss]ource )?[Rr]eviewer [0-9]+$")


def _string(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.casefold() == "nan" else text


def _observed(value: Any, *, normalized: Any | None = None) -> ObservedValue[Any]:
    raw = _string(value)
    lowered = raw.casefold()
    if not raw:
        return ObservedValue(raw=raw, source_status=SourceStatus.BLANK, value=None)
    if lowered in _NOT_REPORTED:
        return ObservedValue(
            raw=raw, source_status=SourceStatus.NOT_REPORTED, value=None
        )
    if lowered in _NOT_APPLICABLE:
        return ObservedValue(
            raw=raw, source_status=SourceStatus.NOT_APPLICABLE, value=None
        )
    if lowered == "unknown":
        return ObservedValue(raw=raw, source_status=SourceStatus.UNKNOWN, value=None)
    return ObservedValue(
        raw=raw, source_status=SourceStatus.STATED, value=normalized or raw
    )


def _age(value: Any, *, context: str | None = None) -> ObservedValue[Any]:
    observed = _observed(value)
    if observed.source_status is not SourceStatus.STATED:
        return observed
    try:
        return ObservedValue(
            raw=observed.raw,
            source_status=SourceStatus.STATED,
            value=parse_source_age(observed.raw, context=context),
        )
    except AgeParseError as exc:
        raise ObservationExtractionError(str(exc)) from exc


def _approved_reviewer(
    mapping: Mapping[str, tuple[str, str]], source_reviewer: str
) -> tuple[str, str]:
    """Return a configured opaque reviewer reference, never a direct identity."""
    reviewer = mapping.get(source_reviewer)
    if reviewer is None:
        raise ObservationExtractionError(
            "source reviewer has no approved pseudonymous mapping"
        )
    reviewer_id, display_label = reviewer
    if (
        not _PSEUDONYMOUS_REVIEWER_ID.fullmatch(reviewer_id)
        or not _PSEUDONYMOUS_REVIEWER_LABEL.fullmatch(display_label)
        or "@" in reviewer_id
        or "@" in display_label
    ):
        raise ObservationExtractionError("reviewer mapping is not pseudonymous")
    return reviewer


def validate_reviewer_mapping(mapping: Mapping[str, tuple[str, str]]) -> None:
    """Validate every configured reviewer value before source loading begins."""
    for source_reviewer in mapping:
        _approved_reviewer(mapping, source_reviewer)


def _phenotypes(
    observation_id: str,
    row: Mapping[str, Any],
    *,
    modifier_vocabulary: ModifierVocabulary | None,
) -> tuple[PhenotypeAssessment, ...]:
    definitions = {item.definition_id: item for item in FINDING_DEFINITIONS}
    assessments: list[PhenotypeAssessment] = []
    for question in PHENOTYPE_QUESTIONS:
        raw = _string(row[question.source_column])
        lowered = raw.casefold()
        status: AssessmentStatus | None
        curation: CurationStatus
        findings: tuple[PhenotypeFinding, ...] = ()
        if not raw:
            curation, status = CurationStatus.UNCURATED, None
        elif lowered in _NOT_REPORTED:
            curation, status = CurationStatus.CURATED, AssessmentStatus.NOT_REPORTED
        elif lowered in _NOT_APPLICABLE:
            curation, status = CurationStatus.CURATED, AssessmentStatus.NOT_APPLICABLE
        elif question.source_column == "KidneyBiopsy" and lowered == "no":
            # ``no`` records no biopsy assessment, not an adjudication that both
            # mutually distinct biopsy findings are absent.
            curation, status = CurationStatus.CURATED, AssessmentStatus.NOT_ASSESSED
        else:
            curation = CurationStatus.CURATED
            status = (
                AssessmentStatus.EXCLUDED
                if lowered in {"no", "none", "absent", "negative"}
                else AssessmentStatus.PRESENT
            )
            candidates = [definitions[item] for item in question.definition_ids]
            matches = [
                item for item in candidates if item.term_label.casefold() in lowered
            ]
            if lowered in {"no", "none", "absent", "negative"}:
                matches = candidates
            try:
                laterality = parse_laterality(raw, vocabulary=modifier_vocabulary)
            except ModifierVocabularyError as exc:
                raise ObservationExtractionError(
                    "source laterality is not importable"
                ) from exc
            if len(candidates) == 1 and not matches:
                if lowered not in {"yes", "present", "positive"} and not laterality:
                    raise ObservationExtractionError(
                        f"unknown phenotype value for {question.source_column}"
                    )
                matches = candidates
            if not matches:
                raise ObservationExtractionError(
                    f"unknown categorical value for {question.source_column}"
                )
            modifiers = tuple(
                OntologyTerm(id=item["id"], label=item["label"]) for item in laterality
            )
            findings = tuple(
                PhenotypeFinding(
                    definition_id=match.definition_id,
                    term=OntologyTerm(id=match.term_id, label=match.term_label),
                    modifiers=modifiers,
                )
                for match in matches
            )
        assessments.append(
            PhenotypeAssessment(
                assessment_id=assessment_id_for(
                    observation_id, "phenotype", question.source_column, "0"
                ),
                column=question.source_column,
                raw_value=raw,
                source_status=_observed(raw).source_status,
                curation_status=curation,
                assessment_status=status,
                findings=findings,
            )
        )
    return tuple(assessments)


def extract_observation(
    row: Mapping[str, Any],
    *,
    row_number: int,
    source_system: str,
    dataset_key: str,
    manifest_sha256: str,
    row_hmac_key: bytes,
    reviewer_mapping: Mapping[str, tuple[str, str]],
    modifier_vocabulary: ModifierVocabulary | None = None,
    publication_mapping: Mapping[str, PublicationReference] | None = None,
) -> ReportObservation:
    """Return one complete observation or fail without retaining source emails."""
    missing = sorted(
        entry.header for entry in SOURCE_COLUMNS if entry.header not in row
    )
    if missing:
        raise ObservationExtractionError(
            "source row is missing columns: " + ", ".join(missing)
        )
    individual_id = _string(row["individual_id"])
    report_id = _string(row["report_id"])
    if not individual_id or not report_id:
        raise ObservationExtractionError("individual_id and report_id are required")
    reviewer_source = _string(row["ReviewBy"])
    mapped_reviewer = _approved_reviewer(reviewer_mapping, reviewer_source)
    observation_id = observation_id_for(source_system, dataset_key, report_id)
    row_fingerprint = row_hmac_sha256(
        "\x1f".join(_string(row[item.header]) for item in SOURCE_COLUMNS).encode(),
        row_hmac_key,
    )
    try:
        publication = resolve_publication(
            row["Publication"], mapping=publication_mapping
        )
    except PublicationMappingError as exc:
        raise ObservationExtractionError(
            "source publication alias is not importable"
        ) from exc
    return ReportObservation(
        observation_id=observation_id,
        origin=ObservationOrigin.IMPORTED,
        source=SourceManifestRef(
            provider=source_system,
            dataset_id=dataset_key,
            sheet="Individuals",
            row_number=row_number,
            row_hmac_sha256=row_fingerprint,
            manifest_sha256=manifest_sha256,
            imported_at=datetime.now(timezone.utc),
        ),
        identifiers=SubjectObservation(
            individual_id=individual_id,
            source_subject_id=individual_id,
            report_id=report_id,
            individual_identifier=_observed(row["IndividualIdentifier"]),
            sex=_observed(row["Sex"]),
        ),
        publication=PublicationObservation(
            source_key=_observed(row["Publication"]),
            publication_type=_observed(row["PublicationType"]),
            pmid=publication.pmid if publication is not None else None,
            doi=publication.doi if publication is not None else None,
        ),
        case=CaseObservation(
            duplicate_check=_observed(row["DupCheck"]),
            problematic=_observed(row["Problematic"]),
            cohort=_observed(row["Cohort"]),
            family_history=_observed(row["FamilyHistory"]),
        ),
        ages=TemporalObservation(
            onset=_age(row["AgeOnset"], context=_string(row["Cohort"])),
            reported=_age(row["AgeReported"], context=_string(row["Cohort"])),
        ),
        variant=VariantObservation(
            variant_type=_observed(row["VariantType"]),
            reported=_observed(row["VariantReported"]),
            source_id=_observed(row["ID"]),
            hg19_info=_observed(row["hg19_INFO"]),
            hg19=_observed(row["hg19"]),
            hg38_info=_observed(row["hg38_INFO"]),
            hg38=_observed(row["hg38"]),
            varsome=_observed(row["Varsome"]),
            detection_method=_observed(row["DetecionMethod"]),
            segregation=_observed(row["Segregation"]),
        ),
        classification=ClassificationObservation(
            verdict=_observed(row["verdict_classification"]),
            criteria=_observed(row["criteria_classification"]),
            comment=_observed(row["comment_classification"]),
            system=_observed(row["system_classification"]),
            date=_observed(row["date_classification"]),
        ),
        phenotypes=_phenotypes(
            observation_id, row, modifier_vocabulary=modifier_vocabulary
        ),
        source_review=SourceReviewProvenance(
            reviewer_id=mapped_reviewer[0],
            reviewer_display_label=mapped_reviewer[1],
            reviewed_on=_string(row["ReviewDate"]),
        ),
        notes=NotesObservation(comment=_observed(row["Comment"])),
    )
