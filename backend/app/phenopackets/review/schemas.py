"""Stable server-authoritative review capability schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypeAliasType

from app.comments.schemas import CommentResponse

ReviewBlockCode = Literal[
    "self_review_forbidden",
    "reviewer_submitted",
    "reviewer_contributed",
    "review_author_unknown",
    "unresolved_review_issues",
    "review_closed",
]
ReviewAction = Literal[
    "create_issue",
    "request_changes",
    "approve",
    "publish",
    "resolve",
    "reopen",
]
ReviewState = Literal["draft", "in_review", "changes_requested", "approved"]
SemanticSection = Literal[
    "Subject",
    "Phenotypes",
    "Diseases",
    "Variants/Interpretations",
    "Measurements",
    "Metadata",
]
SemanticOperation = Literal["added", "removed", "changed"]
SemanticJsonValue = TypeAliasType(  # type: ignore[misc]
    "SemanticJsonValue",
    Union[
        list["SemanticJsonValue"],  # type: ignore[misc]
        dict[str, "SemanticJsonValue"],  # type: ignore[misc]
        str,
        int,
        float,
        bool,
        None,
    ],
)


class ActionCapability(BaseModel):
    """One actor-specific action and its stable, content-free blockers."""

    model_config = ConfigDict(frozen=True)

    action: ReviewAction
    allowed: bool
    blocked_by: tuple[ReviewBlockCode, ...] = ()


class ReviewCapabilities(BaseModel):
    """Ordered review actions available for one actor and candidate."""

    model_config = ConfigDict(frozen=True)

    actions: list[ActionCapability] = Field(default_factory=list)


class ActorSummary(BaseModel):
    """Lean actor identity safe for curator-only review surfaces."""

    id: int
    username: str
    display_name: str | None = None


class StateCounts(BaseModel):
    """Queue facet counts under the active non-state filters."""

    draft: int = 0
    in_review: int = 0
    changes_requested: int = 0
    approved: int = 0


class ReviewQueueQuery(BaseModel):
    """Validated internal representation of the server queue query."""

    page_number: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
    state: ReviewState = "in_review"
    owner: str | None = None
    eligibility: Literal["reviewable_by_me", "all"] = "all"
    issues: Literal["open", "none", "all"] = "all"
    q: str | None = None
    sort: str | None = None


class ReviewQueueRow(BaseModel):
    """Lean queue projection with no ambiguous lifecycle state field."""

    record_id: UUID
    phenopacket_id: str
    subject_label: str
    physical_state: str
    effective_state: ReviewState
    owner: ActorSummary | None
    submitted_by: ActorSummary | None
    submitted_at: datetime | None
    record_revision: int
    candidate_revision_id: int | None
    candidate_content_sha256: str | None
    approved_revision_id: int | None
    approved_content_sha256: str | None
    active_cycle_change_count: int
    open_issue_count: int
    has_published_head: bool
    capabilities: list[ActionCapability] = Field(default_factory=list)


class ReviewQueueMeta(BaseModel):
    """Stable page and facet metadata for the server-driven queue."""

    page_number: int
    page_size: int
    total: int
    total_pages: int
    state_counts: StateCounts


class ReviewQueueResponse(BaseModel):
    """Typed review queue response envelope."""

    data: list[ReviewQueueRow]
    meta: ReviewQueueMeta


class SemanticChange(BaseModel):
    """One literal, sectioned server-computed candidate change."""

    section: SemanticSection
    operation: SemanticOperation
    path: str
    before: SemanticJsonValue
    after: SemanticJsonValue


class ReviewRevisionSummary(BaseModel):
    """Immutable revision identity and actor metadata."""

    id: int
    revision_number: int
    state: str
    content_sha256: str | None
    created_at: datetime
    actor: ActorSummary


class ReviewRevision(ReviewRevisionSummary):
    """An exact immutable revision including its complete content snapshot."""

    content: dict[str, Any]


class ReviewAudit(BaseModel):
    """Owner and immutable lifecycle authorship for the active review cycle."""

    owner: ActorSummary | None
    submission: ReviewRevisionSummary | None
    contributors: list[ActorSummary] = Field(default_factory=list)
    approval: ReviewRevisionSummary | None
    publication: ReviewRevisionSummary | None


class DiscussionSummary(BaseModel):
    """Counts that distinguish discussion from blocking review issues."""

    total_comments: int
    ordinary_comments: int
    blocking_issues: int
    open_blocking_issues: int


class ReviewIssue(CommentResponse):
    """Revision-bound comment with server-authoritative issue actions."""

    capabilities: list[ActionCapability] = Field(default_factory=list)


class ReviewContext(BaseModel):
    """One coherent locked snapshot for the curator review workspace."""

    record_id: UUID
    phenopacket_id: str
    subject_label: str
    physical_state: str
    effective_state: ReviewState
    record_revision: int
    has_published_head: bool
    owner: ActorSummary | None
    candidate: ReviewRevision
    baseline: ReviewRevision | None
    approved: ReviewRevision | None
    semantic_changes: list[SemanticChange] = Field(default_factory=list)
    audit: ReviewAudit
    discussion_summary: DiscussionSummary
    issues: list[ReviewIssue] = Field(default_factory=list)
    capabilities: list[ActionCapability] = Field(default_factory=list)
