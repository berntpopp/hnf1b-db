"""Comments REST endpoints for the D.2 feature.

Spec reference: §5.3 of the design doc.

IMPORTANT (routing-order requirement, spec §5.7):
Static paths under /comments/ (if any are added) MUST be declared before
/{id}-parametrized routes. FastAPI matches routes in registration order;
a static path registered after /{id} will be swallowed by the int coercion
on {id} and surface as 422.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    require_comment_author_or_admin,
    require_curator,
)
from app.comments.models import Comment
from app.comments.schemas import (
    CommentCreate,
    CommentEditResponse,
    CommentMentionOut,
    CommentResponse,
    CommentUpdate,
)
from app.comments.service import CommentsService
from app.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comments", tags=["comments"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _build_comment_response(
    svc: CommentsService,
    comment: Comment,
    *,
    mentions_by_id: Optional[Dict[int, List[User]]] = None,
    edited_by_id: Optional[Dict[int, bool]] = None,
) -> CommentResponse:
    """Assemble a CommentResponse from an eager-loaded Comment ORM row.

    When *mentions_by_id* and *edited_by_id* are provided (bulk-loaded by
    list_comments), the function skips per-comment queries entirely.
    When they are None (single-comment callers like create/get/update), the
    function falls back to individual queries to preserve existing behaviour.
    """
    if mentions_by_id is not None:
        mention_users = mentions_by_id.get(comment.id, [])
    else:
        mentions_map = await svc.load_mentions([comment.id])
        mention_users = mentions_map.get(comment.id, [])

    mentions = [
        CommentMentionOut(
            user_id=u.id,
            username=u.username,
            display_name=u.full_name,
            is_active=u.is_active,
        )
        for u in mention_users
    ]

    if edited_by_id is not None:
        edited = edited_by_id.get(comment.id, False)
    else:
        edited = len(await svc.list_edits(comment.id)) > 0

    resolved_by_username = comment.resolved_by.username if comment.resolved_by else None
    return CommentResponse(
        id=comment.id,
        record_type=comment.record_type,
        record_id=str(comment.record_id),
        author_id=comment.author_id,
        author_username=comment.author.username,
        author_display_name=comment.author.full_name,
        body_markdown=comment.body_markdown,
        mentions=mentions,
        edited=edited,
        resolved_at=comment.resolved_at,
        resolved_by_id=comment.resolved_by_id,
        resolved_by_username=resolved_by_username,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        deleted_at=comment.deleted_at,
        deleted_by_id=comment.deleted_by_id,
    )


def _map_service_error(exc: Exception) -> HTTPException:
    """Translate CommentsService errors to HTTP responses."""
    if isinstance(exc, CommentsService.RecordNotFound):
        return HTTPException(
            status_code=404,
            detail={"code": "record_not_found", "message": str(exc)},
        )
    if isinstance(exc, CommentsService.MentionUnknownUser):
        return HTTPException(
            status_code=422,
            detail={"code": "mention_unknown_user", "message": str(exc)},
        )
    if isinstance(exc, CommentsService.NotAuthor):
        return HTTPException(
            status_code=403,
            detail={"code": "forbidden_not_author", "message": str(exc)},
        )
    if isinstance(exc, CommentsService.NotAuthorOrAdmin):
        return HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": str(exc)},
        )
    if isinstance(exc, CommentsService.AlreadyResolved):
        return HTTPException(
            status_code=409,
            detail={"code": "already_resolved", "message": str(exc)},
        )
    if isinstance(exc, CommentsService.NotResolved):
        return HTTPException(
            status_code=409,
            detail={"code": "not_resolved", "message": str(exc)},
        )
    if isinstance(exc, CommentsService.SoftDeleted):
        return HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": str(exc)},
        )
    # Unmapped exception path: log the real cause server-side, return a
    # generic 500 so we don't leak SQL fragments / stack context to the
    # client (Copilot PR #254 routers.py:137).
    logger.exception("Unmapped CommentsService error: %s", exc.__class__.__name__)
    return HTTPException(
        status_code=500,
        detail={"code": "internal_error", "message": "Internal server error"},
    )


# ---------------------------------------------------------------------------
# POST /comments
# ---------------------------------------------------------------------------


@router.post("", response_model=CommentResponse, status_code=201)
async def create_comment(
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> CommentResponse:
    """Create a new comment on a record (curator/admin only)."""
    svc = CommentsService(db)
    try:
        comment = await svc.create(
            record_type=body.record_type,
            record_id=body.record_id,
            body_markdown=body.body_markdown,
            mention_user_ids=body.mention_user_ids,
            actor=current_user,
        )
    except Exception as exc:
        raise _map_service_error(exc) from exc
    return await _build_comment_response(svc, comment)


# ---------------------------------------------------------------------------
# GET /comments (list)
# ---------------------------------------------------------------------------


@router.get("", response_model=Dict[str, Any])
async def list_comments(
    record_type: str = Query(..., alias="filter[record_type]"),
    record_id: UUID = Query(..., alias="filter[record_id]"),
    resolved: Optional[str] = Query(None, alias="filter[resolved]"),
    include: Optional[str] = Query(None),
    page_number: int = Query(1, alias="page[number]", ge=1),
    page_size: int = Query(50, alias="page[size]", ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> Dict[str, Any]:
    """List comments for a record with optional filtering and pagination."""
    include_deleted = include == "deleted"
    resolved_filter: Optional[bool]
    if resolved == "true":
        resolved_filter = True
    elif resolved == "false":
        resolved_filter = False
    else:
        resolved_filter = None

    svc = CommentsService(db)
    rows, total = await svc.list_for_record(
        record_type=record_type,
        record_id=record_id,
        page_number=page_number,
        page_size=page_size,
        include_deleted=include_deleted,
        resolved_filter=resolved_filter,
    )
    # Bulk-load mentions and edit-existence for the whole page in two queries
    # instead of 2×N per-comment queries (fixes N+1 from Copilot review).
    comment_ids = [c.id for c in rows]
    mentions_by_id = await svc.load_mentions(comment_ids)
    edited_by_id = await svc.bulk_edit_existence(comment_ids)
    data = [
        await _build_comment_response(
            svc, c, mentions_by_id=mentions_by_id, edited_by_id=edited_by_id
        )
        for c in rows
    ]
    return {
        "data": [d.model_dump() for d in data],
        "meta": {"total": total, "page": page_number, "page_size": page_size},
    }


# ---------------------------------------------------------------------------
# GET /comments/{id}
# ---------------------------------------------------------------------------


@router.get("/{comment_id}", response_model=CommentResponse)
async def get_comment(
    comment_id: int,
    include: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> CommentResponse:
    """Retrieve a single comment by id."""
    include_deleted = include == "deleted"
    svc = CommentsService(db)
    comment = await svc.get_by_id(comment_id, include_deleted=include_deleted)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    return await _build_comment_response(svc, comment)


# ---------------------------------------------------------------------------
# PATCH /comments/{id}
# ---------------------------------------------------------------------------


@router.patch("/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int,
    body: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> CommentResponse:
    """Edit a comment body (author only — admin cannot edit others' bodies)."""
    svc = CommentsService(db)
    try:
        comment = await svc.update_body(
            comment_id=comment_id,
            body_markdown=body.body_markdown,
            mention_user_ids=body.mention_user_ids,
            actor=current_user,
        )
    except Exception as exc:
        raise _map_service_error(exc) from exc
    return await _build_comment_response(svc, comment)


# ---------------------------------------------------------------------------
# POST /comments/{id}/resolve and /unresolve
# ---------------------------------------------------------------------------


@router.post("/{comment_id}/resolve", response_model=CommentResponse)
async def resolve_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> CommentResponse:
    """Mark a comment as resolved."""
    svc = CommentsService(db)
    try:
        comment = await svc.resolve(comment_id=comment_id, actor=current_user)
    except Exception as exc:
        raise _map_service_error(exc) from exc
    return await _build_comment_response(svc, comment)


@router.post("/{comment_id}/unresolve", response_model=CommentResponse)
async def unresolve_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> CommentResponse:
    """Clear the resolved flag on a comment."""
    svc = CommentsService(db)
    try:
        comment = await svc.unresolve(comment_id=comment_id, actor=current_user)
    except Exception as exc:
        raise _map_service_error(exc) from exc
    return await _build_comment_response(svc, comment)


# ---------------------------------------------------------------------------
# DELETE /comments/{id}
# ---------------------------------------------------------------------------


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_comment_author_or_admin),
) -> Response:
    """Soft-delete a comment (author or admin only)."""
    svc = CommentsService(db)
    try:
        await svc.soft_delete(comment_id=comment_id, actor=current_user)
    except Exception as exc:
        raise _map_service_error(exc) from exc
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# GET /comments/{id}/edits
# ---------------------------------------------------------------------------


@router.get(
    "/{comment_id}/edits",
    response_model=Dict[str, List[CommentEditResponse]],
)
async def list_comment_edits(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> Dict[str, List[CommentEditResponse]]:
    """Return the append-only edit history for a comment."""
    svc = CommentsService(db)
    # Confirm comment exists (even if soft-deleted, edits are still visible)
    if await svc.get_by_id(comment_id, include_deleted=True) is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    edits = await svc.list_edits(comment_id)
    return {
        "data": [
            CommentEditResponse(
                id=e.id,
                editor_id=e.editor_id,
                editor_username=e.editor.username,
                prev_body=e.prev_body,
                edited_at=e.edited_at,
            )
            for e in edits
        ]
    }
