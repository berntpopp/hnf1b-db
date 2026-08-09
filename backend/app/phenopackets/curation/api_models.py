"""HTTP contracts for the curator-only source-observation API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.phenopackets.curation.models import (
    CurationCorrection,
    OntologyTerm,
    ProjectionResolution,
    ReportObservation,
    ResolutionStrategy,
)


def _camel_case(name: str) -> str:
    """Serialize public API fields using the existing curation JSON spelling."""
    head, *tail = name.split("_")
    return head + "".join(part.title() for part in tail)


class CurationApiModel(BaseModel):
    """Base API model using the stored JSON's camel-case spelling."""

    model_config = ConfigDict(
        populate_by_name=True, extra="forbid", alias_generator=_camel_case
    )


class CurationIssue(CurationApiModel):
    """A machine-addressable validation or projection issue."""

    code: str
    message: str
    path: tuple[str, ...] = ()
    observation_id: str | None = None
    assessment_id: str | None = None
    conflict_key: str | None = None
    candidate_set_digest: str | None = None
    severity: str = "error"


class CurationError(CurationApiModel):
    """Stable structured error envelope returned by curation routes."""

    code: str
    errors: tuple[CurationIssue, ...]


class CurationErrorEnvelope(BaseModel):
    """The application's runtime envelope around a curation error payload."""

    detail: CurationError
    error_code: str
    request_id: str | None = None


class ProjectionPayload(CurationApiModel):
    """Canonical GA4GH output and its projection diagnostics."""

    phenopacket: dict[str, Any]
    observations_digest: str
    output_digest: str
    issues: tuple[CurationIssue, ...] = ()


class CurationLedgerResponse(CurationApiModel):
    """Private curator ledger together with its active canonical projection."""

    phenopacket_id: str
    revision: int
    # Source-status is derived by the profile model but retained in the
    # serialized source ledger. Keep this exact, forward-compatible evidence
    # object opaque at the response boundary rather than re-parsing it and
    # accidentally rejecting its derived field.
    observations: tuple[dict[str, Any], ...]
    corrections: tuple[CurationCorrection, ...]
    resolutions: tuple[ProjectionResolution, ...]
    projection: ProjectionPayload


class CurationPreviewResponse(CurationApiModel):
    """Unsaved projected candidate response."""

    revision: int
    projection: ProjectionPayload


class ReportPatchRequest(CurationApiModel):
    """Replace one report observation while retaining the rest of the ledger."""

    observation: ReportObservation
    revision: int | None = None
    change_reason: str = Field(min_length=1)


class ProjectionPreviewRequest(CurationApiModel):
    """Project an unsaved replacement for a single source observation."""

    observation: ReportObservation


class CorrectionAppendRequest(CurationApiModel):
    """Client-controlled portion of a new append-only correction."""

    json_pointer: str = Field(min_length=1)
    preimage: JsonValue
    postimage: JsonValue
    reason: str = Field(min_length=1)
    supersedes_correction_id: str | None = None
    revision: int | None = None


class ResolutionAppendRequest(CurationApiModel):
    """Client-controlled portion of a new append-only resolution."""

    conflict_key: str = Field(min_length=1)
    candidate_set_digest: str = Field(min_length=1)
    strategy: ResolutionStrategy
    selected_observation_ids: tuple[str, ...] = ()
    resolved_value: str | tuple[OntologyTerm, ...] | None = None
    reason: str = Field(min_length=1)
    revision: int | None = None

    @model_validator(mode="after")
    def validate_resolution_payload(self) -> "ResolutionAppendRequest":
        """Reject strategy/value combinations before a ledger write is attempted."""
        if self.strategy is ResolutionStrategy.SELECT_OBSERVATIONS:
            if not self.selected_observation_ids or self.resolved_value is not None:
                raise ValueError(
                    "select_observations requires selectedObservationIds only"
                )
            return self
        if self.selected_observation_ids or self.resolved_value is None:
            raise ValueError("resolved_value requires resolvedValue only")
        if self.conflict_key == "subject:sex":
            if not isinstance(self.resolved_value, str) or self.resolved_value not in {
                "MALE",
                "FEMALE",
                "OTHER_SEX",
                "UNKNOWN_SEX",
            }:
                raise ValueError("subject sex resolvedValue must be a GA4GH sex enum")
        elif self.conflict_key.startswith("phenotype:"):
            if not isinstance(self.resolved_value, str) or self.resolved_value not in {
                "PRESENT",
                "EXCLUDED",
            }:
                raise ValueError(
                    "phenotype polarity resolvedValue must be PRESENT or EXCLUDED"
                )
        elif isinstance(self.resolved_value, str):
            raise ValueError("resolvedValue must be ontology terms for this conflict")
        return self

    def as_resolution_payload(
        self, *, resolution_id: str, actor_id: int, resolved_at: Any
    ) -> ProjectionResolution:
        """Build the stored resolution with server-owned audit fields."""
        return ProjectionResolution(
            resolution_id=resolution_id,
            conflict_key=self.conflict_key,
            candidate_set_digest=self.candidate_set_digest,
            strategy=self.strategy,
            selected_observation_ids=self.selected_observation_ids,
            resolved_value=self.resolved_value,
            reason=self.reason,
            resolved_by_user_id=actor_id,
            resolved_at=resolved_at,
        )
