"""Pydantic schemas for the D.2 comments API.

Spec reference: §5.4 of the design doc.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, PositiveInt


class CommentMentionOut(BaseModel):
    """Serialized mention entry embedded in a CommentResponse."""

    user_id: int
    username: str
    display_name: Optional[str] = None
    is_active: bool


class CommentResponse(BaseModel):
    """Full comment representation returned by the API."""

    id: int
    record_type: str
    record_id: str  # UUID serialized
    author_id: int
    author_username: str
    author_display_name: Optional[str] = None
    body_markdown: str
    mentions: List[CommentMentionOut] = Field(default_factory=list)
    edited: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by_id: Optional[int] = None
    resolved_by_username: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    deleted_by_id: Optional[int] = None


class CommentCreate(BaseModel):
    """Request body for creating a new comment."""

    record_type: Literal["phenopacket"]
    record_id: UUID
    body_markdown: str = Field(min_length=1, max_length=10000)
    mention_user_ids: List[int] = Field(default_factory=list, max_length=50)
    record_revision: Optional[NonNegativeInt] = None
    review_revision_id: Optional[PositiveInt] = None


class _ReviewIssueRequest(BaseModel):
    """Strict optimistic-concurrency input shared by issue actions."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    record_revision: NonNegativeInt
    rationale: str = Field(min_length=1, max_length=500)


class ReviewIssueResolveRequest(_ReviewIssueRequest):
    """Evidence required to resolve or retract one blocking review issue."""

    disposition: Literal[
        "addressed",
        "accepted_with_rationale",
        "retracted",
        "superseded",
    ]


class ReviewIssueReopenRequest(_ReviewIssueRequest):
    """Evidence required to reopen one blocking review issue."""


class CommentUpdate(BaseModel):
    """Request body for editing an existing comment body."""

    body_markdown: str = Field(min_length=1, max_length=10000)
    mention_user_ids: List[int] = Field(default_factory=list, max_length=50)


class CommentEditResponse(BaseModel):
    """Single entry from the append-only edit history of a comment."""

    id: int
    editor_id: int
    editor_username: str
    prev_body: str
    edited_at: datetime


class MentionableUserOut(BaseModel):
    """Minimal user projection used by the @-mention autocomplete endpoint."""

    id: int
    username: str
    display_name: Optional[str] = None
