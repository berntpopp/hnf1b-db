"""Strict Pydantic contracts for source-faithful curation observations."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _camel_case(name: str) -> str:
    """Serialize internal snake_case names in the stored JSON's camelCase form."""
    head, *tail = name.split("_")
    return head + "".join(piece.title() for piece in tail)


class CurationModel(BaseModel):
    """Closed stored-profile model with JSON aliases matching the specification."""

    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, alias_generator=_camel_case
    )


class SourceStatus(str, Enum):
    """Explicit source meaning for observed scalar cells."""

    STATED = "stated"
    NOT_REPORTED = "not_reported"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"
    BLANK = "blank"


class CurationStatus(str, Enum):
    """Workflow state, intentionally separate from clinical assessment state."""

    UNCURATED = "UNCURATED"
    CURATED = "CURATED"


class AssessmentStatus(str, Enum):
    """Explicit clinical assessment states for a source phenotype question."""

    PRESENT = "PRESENT"
    EXCLUDED = "EXCLUDED"
    NOT_REPORTED = "NOT_REPORTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INDETERMINATE = "INDETERMINATE"
    NOT_ASSESSED = "NOT_ASSESSED"


class ObservationOrigin(str, Enum):
    """Permitted provenance of an observation."""

    IMPORTED = "imported"
    MANUAL = "manual"


ValueT = TypeVar("ValueT")


class ObservedValue(CurationModel, Generic[ValueT]):
    """Immutable raw source cell plus its separately stored normalized value."""

    raw: str
    source_status: SourceStatus
    value: ValueT | None = None
    correction_ids: tuple[str, ...] = ()

    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, alias_generator=_camel_case, frozen=True
    )


class SourceManifestRef(CurationModel):
    """Non-clinical provenance reference for one report observation."""

    provider: str
    dataset_id: str
    sheet: str
    row_number: int | None = None
    row_hmac_sha256: str | None = None
    manifest_sha256: str
    import_run_id: str | None = None
    imported_at: datetime | None = None

    @field_validator("row_hmac_sha256")
    @classmethod
    def validate_hmac(cls, value: str | None) -> str | None:
        """Require the explicitly keyed row-fingerprint representation."""
        if value is not None and not value.startswith("hmac-sha256:"):
            raise ValueError("rowHmacSha256 must use keyed hmac-sha256 format")
        return value


class PublicationObservation(CurationModel):
    """Source publication identity and optional resolved official references."""

    source_key: ObservedValue[str] | None = None
    publication_type: ObservedValue[str] | None = None
    pmid: str | None = None
    doi: str | None = None


class SubjectObservation(CurationModel):
    """Typed subject and report roles; report ID is not an alternate subject ID."""

    individual_id: str
    source_subject_id: str
    report_id: str
    individual_identifier: ObservedValue[str] | None = None
    sex: ObservedValue[str] | None = None


class TemporalObservation(CurationModel):
    """Raw temporal source value and validated typed representation."""

    onset: ObservedValue[dict[str, Any]] | None = None
    reported: ObservedValue[dict[str, Any]] | None = None


class CaseObservation(CurationModel):
    """All report-level case fields retained as typed source values."""

    duplicate_check: ObservedValue[str] | None = None
    problematic: ObservedValue[str] | None = None
    cohort: ObservedValue[str] | None = None
    family_history: ObservedValue[str] | None = None


class NotesObservation(CurationModel):
    """Report-level source notes that must not collapse to the case level."""

    comment: ObservedValue[str] | None = None


class DiseaseObservation(CurationModel):
    """An explicit source/adjudicated diagnosis, never inferred from a variant."""

    term: OntologyTerm
    asserted: bool = True
    onset: ObservedValue[dict[str, Any]] | None = None


class VariantObservation(CurationModel):
    """Reported variant evidence with a separate validated normalized identity."""

    variant_type: ObservedValue[str] | None = None
    reported: ObservedValue[str] | None = None
    source_id: ObservedValue[str] | None = None
    normalized: dict[str, Any] | None = None
    hg19_info: ObservedValue[str] | None = None
    hg19: ObservedValue[str] | None = None
    hg38_info: ObservedValue[str] | None = None
    hg38: ObservedValue[str] | None = None
    varsome: ObservedValue[str] | None = None
    detection_method: ObservedValue[str] | None = None
    segregation: ObservedValue[str] | None = None


class ClassificationObservation(CurationModel):
    """Classification evidence that remains tied to the source report/variant."""

    verdict: ObservedValue[str] | None = None
    criteria: ObservedValue[str] | None = None
    comment: ObservedValue[str] | None = None
    system: ObservedValue[str] | None = None
    date: ObservedValue[str] | None = None
    contribution: ObservedValue[str] | None = None


class OntologyTerm(CurationModel):
    """Ontology term reference stored in a local observation."""

    id: str
    label: str


class PhenotypeFinding(CurationModel):
    """Mapped finding, including a stable local definition ID."""

    definition_id: str
    term: OntologyTerm
    source_term: OntologyTerm | None = None
    modifiers: tuple[OntologyTerm, ...] = ()


class EvidenceObservation(CurationModel):
    """A report-specific evidence reference with an explicit ECO term."""

    reference: str
    evidence_code: OntologyTerm


class PhenotypeAssessment(CurationModel):
    """One explicit source-question assessment."""

    assessment_id: str
    column: str
    raw_value: str
    curation_status: CurationStatus
    assessment_status: AssessmentStatus | None
    findings: tuple[PhenotypeFinding, ...] = ()
    evidence: tuple[EvidenceObservation, ...] = ()
    onset: ObservedValue[dict[str, Any]] | None = None
    correction_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_status_axes(self) -> "PhenotypeAssessment":
        """Require a clinical state exactly when workflow curation is complete."""
        if (
            self.curation_status is CurationStatus.UNCURATED
            and self.assessment_status is not None
        ):
            raise ValueError(
                "uncurated phenotype assessments must have null assessmentStatus"
            )
        if (
            self.curation_status is CurationStatus.CURATED
            and self.assessment_status is None
        ):
            raise ValueError(
                "curated phenotype assessments require an assessmentStatus"
            )
        return self


class SourceReviewProvenance(CurationModel):
    """Mapped reviewer provenance; raw reviewer emails are intentionally absent."""

    reviewer_id: str | None = None
    reviewer_display_label: str | None = None
    reviewed_on: str | None = None


class ReportObservation(CurationModel):
    """One publication/report row attached to one biological individual."""

    observation_id: str
    origin: ObservationOrigin
    source: SourceManifestRef
    identifiers: SubjectObservation
    publication: PublicationObservation | None = None
    case: CaseObservation | None = None
    ages: TemporalObservation | None = None
    variant: VariantObservation | None = None
    classification: ClassificationObservation | None = None
    diseases: tuple[DiseaseObservation, ...] = ()
    phenotypes: tuple[PhenotypeAssessment, ...] = ()
    source_review: SourceReviewProvenance | None = None
    notes: NotesObservation | None = None

    @model_validator(mode="after")
    def validate_imported_contract(self) -> "ReportObservation":
        """Enforce complete source matrices and stable identities for imports."""
        if self.origin is not ObservationOrigin.IMPORTED:
            return self
        from app.phenopackets.curation.definitions import PHENOTYPE_QUESTIONS
        from app.phenopackets.curation.identifiers import (
            assessment_id_for,
            observation_id_for,
        )

        if self.observation_id != observation_id_for(
            self.source.provider, self.source.dataset_id, self.identifiers.report_id
        ):
            raise ValueError(
                "imported observationId must be its UUIDv5 source identity"
            )
        expected_columns = {question.source_column for question in PHENOTYPE_QUESTIONS}
        if (
            len(self.phenotypes) != 30
            or {item.column for item in self.phenotypes} != expected_columns
        ):
            raise ValueError(
                "imported observations require exactly 30 known assessments"
            )
        for assessment in self.phenotypes:
            expected_id = assessment_id_for(
                self.observation_id, "phenotype", assessment.column, "0"
            )
            if assessment.assessment_id != expected_id:
                raise ValueError(
                    "imported assessmentId must be its UUIDv5 source identity"
                )
        return self


class CurationCorrection(CurationModel):
    """Append-only correction preserving exact before and after JSON values."""

    correction_id: str
    json_pointer: str
    preimage: Any
    postimage: Any
    source_manifest_sha256: str
    reason: str
    actor_id: int
    created_at: datetime
    supersedes_correction_id: str | None = None


class ProjectionResolution(CurationModel):
    """A curator decision whose candidate digest proves it remains current."""

    resolution_id: str
    conflict_key: str
    candidate_set_digest: str
    strategy: str
    selected_observation_ids: tuple[str, ...] = ()
    resolved_value: Any = None
    reason: str
    resolved_by_user_id: int
    resolved_at: datetime

    @model_validator(mode="after")
    def validate_payload(self) -> "ProjectionResolution":
        """Require an explicit, non-empty payload for supported strategies."""
        if self.strategy not in {"select_observations", "resolved_value"}:
            raise ValueError("unsupported resolution strategy")
        if self.strategy == "select_observations" and not self.selected_observation_ids:
            raise ValueError("select_observations requires selectedObservationIds")
        if self.strategy == "resolved_value" and self.resolved_value is None:
            raise ValueError("resolved_value requires resolvedValue")
        return self


class ProjectionMetadata(CurationModel):
    """Digest metadata for a deterministic GA4GH projection."""

    algorithm_version: str = "1.0"
    observations_digest: str | None = None
    output_digest: str | None = None


class Hnf1bCurationProfile(CurationModel):
    """The single clinical source of truth stored in the revisioned document."""

    schema_version: str = "2.0"
    definitions_version: str = "hnf1b-phenotypes/1"
    source_subject_id: str
    observations_by_id: dict[str, ReportObservation] = Field(default_factory=dict)
    corrections_by_id: dict[str, CurationCorrection] = Field(default_factory=dict)
    resolutions_by_id: dict[str, ProjectionResolution] = Field(default_factory=dict)
    projection: ProjectionMetadata = Field(default_factory=ProjectionMetadata)

    @model_validator(mode="after")
    def validate_cross_references(self) -> "Hnf1bCurationProfile":
        """Keep identity maps and source-subject bindings structurally coherent."""
        for key, observation in self.observations_by_id.items():
            if key != observation.observation_id:
                raise ValueError("observationsById key must equal observationId")
            if observation.identifiers.source_subject_id != self.source_subject_id:
                raise ValueError(
                    "report sourceSubjectId must match profile sourceSubjectId"
                )
        for key, correction in self.corrections_by_id.items():
            if key != correction.correction_id:
                raise ValueError("correctionsById key must equal correctionId")
        for key, resolution in self.resolutions_by_id.items():
            if key != resolution.resolution_id:
                raise ValueError("resolutionsById key must equal resolutionId")
        return self
