"""Curator-only server-driven review queue and coherent context endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_optional_user, is_curator_or_admin
from app.core.api_models import ApiErrorEnvelope
from app.database import get_db
from app.models.user import User
from app.phenopackets.review.repository import ReviewRepository
from app.phenopackets.review.schemas import (
    ReviewContext,
    ReviewQueueMeta,
    ReviewQueueQuery,
    ReviewQueueResponse,
)

router = APIRouter(tags=["phenopackets-review"])


def _require_review_actor(
    actor: User | None = Depends(get_optional_user),
) -> User:
    """Return an active review actor or the content-free non-disclosure error."""
    if not is_curator_or_admin(actor):
        raise HTTPException(status_code=404, detail="Phenopacket not found")
    assert actor is not None
    return actor


@router.get(
    "/review-queue",
    response_model=ReviewQueueResponse,
    responses={status: {"model": ApiErrorEnvelope} for status in (400, 401, 404, 422)},
    summary="List the server-driven curator review queue",
)
async def list_review_queue(
    page_number: int = Query(1, alias="page[number]", ge=1),
    page_size: int = Query(25, alias="page[size]", ge=1, le=100),
    filter_state: Literal[
        "draft", "in_review", "changes_requested", "approved"
    ] = Query("in_review", alias="filter[state]"),
    filter_owner: str | None = Query(None, alias="filter[owner]"),
    filter_eligibility: Literal["reviewable_by_me", "all"] = Query(
        "all", alias="filter[eligibility]"
    ),
    filter_issues: Literal["open", "none", "all"] = Query(
        "all", alias="filter[issues]"
    ),
    q: str | None = Query(None, max_length=200),
    sort: str | None = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_require_review_actor),
) -> ReviewQueueResponse:
    """Return a fully SQL-filtered queue with actor-specific capabilities."""
    if filter_owner is not None and filter_owner != "mine":
        if not filter_owner.isdecimal() or int(filter_owner) <= 0:
            raise HTTPException(status_code=422, detail="Invalid owner filter")
    if q is not None:
        q = q.strip()
        if not q:
            raise HTTPException(status_code=422, detail="Search query cannot be empty")
    if sort is not None and not sort.strip():
        raise HTTPException(status_code=400, detail="Sort cannot be empty")
    query = ReviewQueueQuery(
        page_number=page_number,
        page_size=page_size,
        state=filter_state,
        owner=filter_owner,
        eligibility=filter_eligibility,
        issues=filter_issues,
        q=q,
        sort=sort,
    )
    repository = ReviewRepository(db)
    try:
        rows, total, state_counts = await repository.list_queue(actor, query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    total_pages = (total + page_size - 1) // page_size if total else 0
    return ReviewQueueResponse(
        data=rows,
        meta=ReviewQueueMeta(
            page_number=page_number,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            state_counts=state_counts,
        ),
    )


@router.get(
    "/{record_id}/review-context",
    response_model=ReviewContext,
    # Keep FastAPI's harmless path-validation 422, but override its schema so
    # the operation documents the envelope emitted by our global handler.
    responses={status: {"model": ApiErrorEnvelope} for status in (401, 404, 422)},
    summary="Get one coherent curator review context",
)
async def get_review_context(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_require_review_actor),
) -> ReviewContext:
    """Return candidate/head/issues/audit materialized under a share lock."""
    context = await ReviewRepository(db).get_context(record_id, actor)
    if context is None:
        raise HTTPException(status_code=404, detail="Phenopacket not found")
    return context
