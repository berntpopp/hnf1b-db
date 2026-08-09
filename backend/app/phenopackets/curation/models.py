"""Strict Pydantic contracts for source-faithful curation observations."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)


def _camel_case(name: str) -> str:
    """Serialize internal snake_case names in the stored JSON's camelCase form."""
    head, *tail = name.split("_")
    return head + "".join(piece.title() for piece in tail)


class CurationModel(BaseModel):
    """Closed stored-profile model with JSON aliases matching the specification."""

    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, alias_generator=_camel_case, frozen=True
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


class ResolutionStrategy(str, Enum):
    """Typed curator actions that can be applied by the deterministic projector."""

    SELECT_OBSERVATIONS = "select_observations"
    RESOLVED_VALUE = "resolved_value"


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
    reported_age_is_encounter_age: bool = False

    @field_validator("row_hmac_sha256")
    @classmethod
    def validate_hmac(cls, value: str | None) -> str | None:
        """Require the explicitly keyed row-fingerprint representation."""
        if value is not None and not re.fullmatch(r"hmac-sha256:[0-9a-f]{64}", value):
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


class TemporalValue(CurationModel):
    """Closed representation of a source age, gestational age, or ontology onset."""

    kind: Literal["age", "gestationalAge", "ontologyClass", "unprojected"]
    iso8601_duration: str | None = None
    term: OntologyTerm | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "TemporalValue":
        """Disallow free-form temporal dictionaries in imported evidence."""
        if self.kind in {"age", "gestationalAge"}:
            if not self.iso8601_duration or self.term is not None:
                raise ValueError(
                    "duration temporal values require only iso8601Duration"
                )
        elif self.kind == "ontologyClass":
            if self.term is None or self.iso8601_duration is not None:
                raise ValueError("ontology temporal values require only term")
        elif self.iso8601_duration is not None or self.term is not None:
            raise ValueError(
                "unprojected temporal values cannot contain projected data"
            )
        return self


class TemporalObservation(CurationModel):
    """Raw temporal source value and validated typed representation."""

    onset: ObservedValue[TemporalValue] | None = None
    reported: ObservedValue[TemporalValue] | None = None


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
    onset: ObservedValue[TemporalValue] | None = None


class VrsText(CurationModel):
    """The VRS text variation form supported by source-faithful imports."""

    definition: str = Field(min_length=1)


class VrsTextVariation(CurationModel):
    """Closed VRS variation wrapper; no arbitrary JSON can enter the ledger."""

    text: VrsText


class VrsDescriptor(CurationModel):
    """A stable VRS descriptor whose GA4GH identifier names its exact variation."""

    id: str
    variation: VrsTextVariation

    @field_validator("id")
    @classmethod
    def validate_vrs_id(cls, value: str) -> str:
        """Require canonical GA4GH VRS allele identity syntax."""
        if not re.fullmatch(r"ga4gh:VA\.[A-Za-z0-9_-]+", value):
            raise ValueError("VRS descriptor id must be a ga4gh:VA identifier")
        return value


class VariantObservation(CurationModel):
    """Reported variant evidence with a separate validated normalized identity."""

    variant_type: ObservedValue[str] | None = None
    reported: ObservedValue[str] | None = None
    source_id: ObservedValue[str] | None = None
    normalized: VrsDescriptor | None = None
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

    @model_validator(mode="after")
    def validate_reference_and_eco(self) -> "EvidenceObservation":
        """Keep source evidence references and ECO terms projectable to GA4GH."""
        if not re.fullmatch(r"(?:PMID:\d+|DOI:10\.\S+)", self.reference):
            raise ValueError("evidence reference must be PMID:<digits> or DOI:<doi>")
        if not re.fullmatch(r"ECO:\d{7}", self.evidence_code.id):
            raise ValueError("evidence code must be an ECO term")
        return self


class PhenotypeAssessment(CurationModel):
    """One explicit source-question assessment."""

    assessment_id: str
    column: str
    raw_value: str
    source_status: SourceStatus
    curation_status: CurationStatus
    assessment_status: AssessmentStatus | None
    findings: tuple[PhenotypeFinding, ...] = ()
    evidence: tuple[EvidenceObservation, ...] = ()
    onset: ObservedValue[TemporalValue] | None = None
    correction_ids: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def derive_source_status(cls, data: Any) -> Any:
        """Make the source's NA/NR/blank meanings impossible to curate as positive."""
        if not isinstance(data, dict):
            return data
        raw = str(data.get("raw_value", data.get("rawValue", ""))).strip().upper()
        implied = {
            "": SourceStatus.BLANK.value,
            "NA": SourceStatus.NOT_APPLICABLE.value,
            "N/A": SourceStatus.NOT_APPLICABLE.value,
            "NOT APPLICABLE": SourceStatus.NOT_APPLICABLE.value,
            "NR": SourceStatus.NOT_REPORTED.value,
            "NOT REPORTED": SourceStatus.NOT_REPORTED.value,
        }.get(raw, SourceStatus.STATED.value)
        provided = data.get("source_status", data.get("sourceStatus"))
        if provided is not None and provided != implied:
            raise ValueError("sourceStatus conflicts with the raw source cell")
        value = dict(data)
        value["source_status"] = implied
        return value

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
        if (
            self.assessment_status
            not in {
                AssessmentStatus.PRESENT,
                AssessmentStatus.EXCLUDED,
            }
            and self.findings
        ):
            raise ValueError("non-positive phenotype states cannot contain findings")
        if (
            self.assessment_status
            in {
                AssessmentStatus.PRESENT,
                AssessmentStatus.EXCLUDED,
            }
            and not self.findings
        ):
            raise ValueError("positive phenotype states require a finding")
        if self.source_status in {
            SourceStatus.NOT_REPORTED,
            SourceStatus.NOT_APPLICABLE,
            SourceStatus.BLANK,
        } and self.assessment_status in {
            AssessmentStatus.PRESENT,
            AssessmentStatus.EXCLUDED,
        }:
            raise ValueError("NA/NR/blank source states cannot be PRESENT or EXCLUDED")
        if self.curation_status is CurationStatus.CURATED:
            from app.phenopackets.curation.definitions import (
                FINDING_DEFINITIONS,
                PHENOTYPE_QUESTIONS,
            )

            questions = {item.source_column: item for item in PHENOTYPE_QUESTIONS}
            definitions = {item.definition_id: item for item in FINDING_DEFINITIONS}
            question = questions.get(self.column)
            if question is None:
                raise ValueError(
                    "phenotype assessment column is not a source definition"
                )
            if len(self.findings) > 1 and question.finding_cardinality == "single":
                raise ValueError("source phenotype definition accepts one finding")
            for finding in self.findings:
                definition = definitions.get(finding.definition_id)
                if (
                    definition is None
                    or finding.definition_id not in question.definition_ids
                    or finding.term.id != definition.term_id
                ):
                    raise ValueError("finding does not match source definition")
                if finding.modifiers and question.allowed_laterality == "none":
                    raise ValueError(
                        "source phenotype definition does not allow laterality"
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

        if self.source.row_hmac_sha256 is None:
            raise ValueError("imported observations require rowHmacSha256")
        if self.observation_id != observation_id_for(
            self.source.provider, self.source.dataset_id, self.identifiers.report_id
        ):
            raise ValueError(
                "imported observationId must be its UUIDv5 source identity"
            )
        required_sections = {
            "publication": self.publication,
            "case": self.case,
            "ages": self.ages,
            "variant": self.variant,
            "classification": self.classification,
            "sourceReview": self.source_review,
            "notes": self.notes,
        }
        missing_sections = sorted(
            name for name, value in required_sections.items() if value is None
        )
        if missing_sections:
            raise ValueError(
                "imported observations require source sections: "
                + ", ".join(missing_sections)
            )
        missing_fields = _missing_imported_source_fields(self)
        if missing_fields:
            raise ValueError(
                "imported observations require all source dimensions: "
                + ", ".join(missing_fields)
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


def _missing_imported_source_fields(observation: ReportObservation) -> list[str]:
    """Return mandatory imported spreadsheet dimensions that would otherwise vanish."""
    required: tuple[tuple[str, object | None], ...] = (
        (
            "identifiers.individualIdentifier",
            observation.identifiers.individual_identifier,
        ),
        ("identifiers.sex", observation.identifiers.sex),
        (
            "publication.sourceKey",
            observation.publication.source_key if observation.publication else None,
        ),
        (
            "publication.publicationType",
            observation.publication.publication_type
            if observation.publication
            else None,
        ),
        (
            "case.duplicateCheck",
            observation.case.duplicate_check if observation.case else None,
        ),
        (
            "case.problematic",
            observation.case.problematic if observation.case else None,
        ),
        ("case.cohort", observation.case.cohort if observation.case else None),
        (
            "case.familyHistory",
            observation.case.family_history if observation.case else None,
        ),
        ("ages.onset", observation.ages.onset if observation.ages else None),
        ("ages.reported", observation.ages.reported if observation.ages else None),
        (
            "variant.variantType",
            observation.variant.variant_type if observation.variant else None,
        ),
        (
            "variant.reported",
            observation.variant.reported if observation.variant else None,
        ),
        (
            "variant.sourceId",
            observation.variant.source_id if observation.variant else None,
        ),
        (
            "variant.hg19Info",
            observation.variant.hg19_info if observation.variant else None,
        ),
        ("variant.hg19", observation.variant.hg19 if observation.variant else None),
        (
            "variant.hg38Info",
            observation.variant.hg38_info if observation.variant else None,
        ),
        ("variant.hg38", observation.variant.hg38 if observation.variant else None),
        (
            "variant.varsome",
            observation.variant.varsome if observation.variant else None,
        ),
        (
            "variant.detectionMethod",
            observation.variant.detection_method if observation.variant else None,
        ),
        (
            "variant.segregation",
            observation.variant.segregation if observation.variant else None,
        ),
        (
            "classification.verdict",
            observation.classification.verdict if observation.classification else None,
        ),
        (
            "classification.criteria",
            observation.classification.criteria if observation.classification else None,
        ),
        (
            "classification.comment",
            observation.classification.comment if observation.classification else None,
        ),
        (
            "classification.system",
            observation.classification.system if observation.classification else None,
        ),
        (
            "classification.date",
            observation.classification.date if observation.classification else None,
        ),
        ("notes.comment", observation.notes.comment if observation.notes else None),
        (
            "sourceReview.reviewerId",
            observation.source_review.reviewer_id
            if observation.source_review
            else None,
        ),
        (
            "sourceReview.reviewerDisplayLabel",
            (
                observation.source_review.reviewer_display_label
                if observation.source_review
                else None
            ),
        ),
        (
            "sourceReview.reviewedOn",
            observation.source_review.reviewed_on
            if observation.source_review
            else None,
        ),
    )
    missing = [name for name, value in required if value is None]
    identity_fields = {
        "identifiers.individualId": observation.identifiers.individual_id,
        "identifiers.sourceSubjectId": observation.identifiers.source_subject_id,
        "identifiers.reportId": observation.identifiers.report_id,
    }
    missing.extend(name for name, value in identity_fields.items() if not value.strip())
    return missing


class CurationCorrection(CurationModel):
    """Append-only correction preserving exact before and after JSON values."""

    correction_id: str
    json_pointer: str
    preimage: JsonValue
    postimage: JsonValue
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
    strategy: ResolutionStrategy
    selected_observation_ids: tuple[str, ...] = ()
    resolved_value: str | tuple[OntologyTerm, ...] | None = None
    reason: str
    resolved_by_user_id: int
    resolved_at: datetime

    @model_validator(mode="after")
    def validate_payload(self) -> "ProjectionResolution":
        """Require an explicit, non-empty payload for supported strategies."""
        if (
            self.strategy is ResolutionStrategy.SELECT_OBSERVATIONS
            and not self.selected_observation_ids
        ):
            raise ValueError("select_observations requires selectedObservationIds")
        if (
            self.strategy is ResolutionStrategy.RESOLVED_VALUE
            and self.resolved_value is None
        ):
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
            if (
                correction.supersedes_correction_id is not None
                and correction.supersedes_correction_id not in self.corrections_by_id
            ):
                raise ValueError("correction supersedes an unknown correction")
        superseded = [
            correction.supersedes_correction_id
            for correction in self.corrections_by_id.values()
            if correction.supersedes_correction_id is not None
        ]
        if len(superseded) != len(set(superseded)):
            raise ValueError("a correction may be superseded only once")
        for key, resolution in self.resolutions_by_id.items():
            if key != resolution.resolution_id:
                raise ValueError("resolutionsById key must equal resolutionId")
        return self
