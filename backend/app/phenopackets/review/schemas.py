"""Stable server-authoritative review capability schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReviewBlockCode = Literal[
    "self_review_forbidden",
    "reviewer_submitted",
    "reviewer_contributed",
    "review_author_unknown",
    "unresolved_review_issues",
    "review_closed",
]
ReviewAction = Literal["request_changes", "approve", "publish"]


class ActionCapability(BaseModel):
    """One actor-specific action and its stable, content-free blockers."""

    model_config = ConfigDict(frozen=True)

    action: ReviewAction
    allowed: bool
    blocked_by: list[ReviewBlockCode] = Field(default_factory=list)


class ReviewCapabilities(BaseModel):
    """Ordered review actions available for one actor and candidate."""

    model_config = ConfigDict(frozen=True)

    actions: list[ActionCapability] = Field(default_factory=list)
