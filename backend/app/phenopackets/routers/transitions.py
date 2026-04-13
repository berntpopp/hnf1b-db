"""State-machine endpoints for phenopackets (Wave 7 D.1 §7.1).

Endpoints:
  POST /{phenopacket_id}/transitions
      Perform a state transition.  Delegates to
      ``PhenopacketStateService.transition``.  Requires curator or admin.

  GET  /{phenopacket_id}/revisions
      List immutable revision rows for a phenopacket.  Curator/admin only;
      non-curator callers receive 404 (spec §7.2: "state is not exposed to
      non-curators").

  GET  /{phenopacket_id}/revisions/{revision_id}
      Single revision row with ``content_jsonb`` populated.
      Curator/admin only (404 for others).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user, require_curator
from app.database import get_db
from app.models.user import User
from app.phenopackets.models import (
    Phenopacket,
    PhenopacketRevision,
    RevisionResponse,
    TransitionRequest,
)
from app.phenopackets.query_builders import build_phenopacket_response
from app.phenopackets.repositories import PhenopacketRepository
from app.phenopackets.services.state_service import PhenopacketStateService

router = APIRouter(tags=["phenopackets-state"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_revision_response(
    rev: PhenopacketRevision,
    pp: Phenopacket,
    *,
    include_content: bool = False,
) -> RevisionResponse:
    """Convert a PhenopacketRevision ORM row to the API schema."""
    actor_username: Optional[str] = None
    if rev.actor is not None:
        actor_username = rev.actor.username

    return RevisionResponse(
        id=rev.id,
        record_id=str(rev.record_id),
        phenopacket_id=pp.phenopacket_id,
        revision_number=rev.revision_number,
        state=rev.state,
        from_state=rev.from_state,
        to_state=rev.to_state,
        is_head_published=rev.is_head_published,
        change_reason=rev.change_reason,
        actor_id=rev.actor_id,
        actor_username=actor_username,
        change_patch=rev.change_patch,
        created_at=rev.created_at,
        content_jsonb=rev.content_jsonb if include_content else None,
    )


async def _get_phenopacket_or_404(
    db: AsyncSession,
    phenopacket_id: str,
) -> Phenopacket:
    """Fetch the phenopacket row (any state, no soft-delete filter) or 404."""
    repo = PhenopacketRepository(db)
    pp = await repo.get_by_id(phenopacket_id)
    if pp is None:
        raise HTTPException(status_code=404, detail="Phenopacket not found")
    return pp


# ---------------------------------------------------------------------------
# POST /{phenopacket_id}/transitions
# ---------------------------------------------------------------------------


@router.post(
    "/{phenopacket_id}/transitions",
    response_model=Dict[str, Any],
    summary="Perform a state transition",
)
async def post_transition(
    phenopacket_id: str,
    body: TransitionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> Dict[str, Any]:
    """Perform a state-machine transition on a phenopacket.

    Delegates to ``PhenopacketStateService.transition``.

    Returns ``{"phenopacket": PhenopacketResponse, "revision": RevisionResponse}``.

    HTTP error mapping:
    - ``RevisionMismatch``    → 409  code=revision_mismatch
    - ``InvalidTransition``   → 409  code=invalid_transition
    - ``ForbiddenNotOwner``   → 403  code=forbidden_not_owner
    - ``PermissionError``     → 403  code=forbidden_role
    - unexpected ``RuntimeError`` → 500
    """
    pp = await _get_phenopacket_or_404(db, phenopacket_id)

    svc = PhenopacketStateService(db)
    try:
        pp, rev = await svc.transition(
            pp.id,
            to_state=body.to_state,
            reason=body.reason,
            expected_revision=body.revision,
            actor=current_user,
        )
    except PhenopacketStateService.RevisionMismatch as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "revision_mismatch", "message": str(exc)},
        ) from exc
    except PhenopacketStateService.InvalidTransition as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "invalid_transition", "message": str(exc)},
        ) from exc
    except PhenopacketStateService.ForbiddenNotOwner as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden_not_owner", "message": str(exc)},
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden_role", "message": str(exc)},
        ) from exc
    except RuntimeError as exc:
        logger.exception("Unexpected error during transition of %s", phenopacket_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Re-fetch to get eager-loaded actor relationships for the response builder
    repo = PhenopacketRepository(db)
    pp_reloaded = await repo.get_by_id(phenopacket_id)
    if pp_reloaded is None:
        pp_reloaded = pp

    # Add state fields that build_phenopacket_response doesn't include yet
    pp_response = build_phenopacket_response(pp_reloaded)
    # Augment with state-machine fields
    pp_dict = pp_response.model_dump()
    pp_dict["state"] = pp_reloaded.state
    pp_dict["head_published_revision_id"] = pp_reloaded.head_published_revision_id
    pp_dict["editing_revision_id"] = pp_reloaded.editing_revision_id
    pp_dict["draft_owner_id"] = pp_reloaded.draft_owner_id

    # Reload the revision with actor eager-loaded
    rev_reloaded = (
        await db.execute(
            select(PhenopacketRevision)
            .where(PhenopacketRevision.id == rev.id)
            .options(selectinload(PhenopacketRevision.actor))
        )
    ).scalar_one()

    rev_response = _build_revision_response(
        rev_reloaded, pp_reloaded, include_content=True
    )

    return {
        "phenopacket": pp_dict,
        "revision": rev_response.model_dump(),
    }


# ---------------------------------------------------------------------------
# GET /{phenopacket_id}/revisions  (list)
# ---------------------------------------------------------------------------


@router.get(
    "/{phenopacket_id}/revisions",
    response_model=Dict[str, Any],
    summary="List revisions for a phenopacket (curator/admin only)",
)
async def list_revisions(
    phenopacket_id: str,
    page_size: int = Query(50, alias="page[size]", ge=1, le=500),
    page_number: int = Query(1, alias="page[number]", ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """List revision rows for a phenopacket.

    Curator and admin only — non-curator callers receive 404 (spec §7.2).
    The list response omits ``content_jsonb`` to keep payload size small.
    Use the detail endpoint to fetch a specific revision's content.

    Ordered by ``created_at DESC`` (newest first).
    """
    if not current_user.is_curator:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    pp = await _get_phenopacket_or_404(db, phenopacket_id)

    # Count
    count_result = await db.execute(
        select(func.count()).select_from(PhenopacketRevision).where(
            PhenopacketRevision.record_id == pp.id
        )
    )
    total = int(count_result.scalar() or 0)

    # Paginated list
    offset = (page_number - 1) * page_size
    rows_result = await db.execute(
        select(PhenopacketRevision)
        .where(PhenopacketRevision.record_id == pp.id)
        .options(selectinload(PhenopacketRevision.actor))
        .order_by(PhenopacketRevision.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = rows_result.scalars().all()

    data = [
        _build_revision_response(rev, pp, include_content=False).model_dump()
        for rev in rows
    ]

    return {
        "data": data,
        "meta": {
            "total": total,
            "page": page_number,
            "page_size": page_size,
        },
    }


# ---------------------------------------------------------------------------
# GET /{phenopacket_id}/revisions/{revision_id}  (detail)
# ---------------------------------------------------------------------------


@router.get(
    "/{phenopacket_id}/revisions/{revision_id}",
    response_model=Dict[str, Any],
    summary="Get a single revision with full content (curator/admin only)",
)
async def get_revision(
    phenopacket_id: str,
    revision_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return a single revision row with ``content_jsonb`` populated.

    Curator and admin only — non-curator callers receive 404.
    """
    if not current_user.is_curator:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    pp = await _get_phenopacket_or_404(db, phenopacket_id)

    rev_result = await db.execute(
        select(PhenopacketRevision)
        .where(
            PhenopacketRevision.id == revision_id,
            PhenopacketRevision.record_id == pp.id,
        )
        .options(selectinload(PhenopacketRevision.actor))
    )
    rev = rev_result.scalar_one_or_none()
    if rev is None:
        raise HTTPException(status_code=404, detail="Revision not found")

    return _build_revision_response(rev, pp, include_content=True).model_dump()
