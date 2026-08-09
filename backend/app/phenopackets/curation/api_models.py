"""HTTP contracts for the curator-only source-observation API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue

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
    resolved_value: str | tuple[dict[str, str], ...] | None = None
    reason: str = Field(min_length=1)
    revision: int | None = None

    def as_resolution_payload(
        self, *, resolution_id: str, actor_id: int, resolved_at: Any
    ) -> ProjectionResolution:
        """Build the stored resolution with server-owned audit fields."""
        resolved_value: str | tuple[OntologyTerm, ...] | None
        if isinstance(self.resolved_value, tuple):
            resolved_value = tuple(
                OntologyTerm.model_validate(item) for item in self.resolved_value
            )
        else:
            resolved_value = self.resolved_value
        return ProjectionResolution(
            resolution_id=resolution_id,
            conflict_key=self.conflict_key,
            candidate_set_digest=self.candidate_set_digest,
            strategy=self.strategy,
            selected_observation_ids=self.selected_observation_ids,
            resolved_value=resolved_value,
            reason=self.reason,
            resolved_by_user_id=actor_id,
            resolved_at=resolved_at,
        )
