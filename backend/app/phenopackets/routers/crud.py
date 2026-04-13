"""CRUD operations for phenopackets.

Basic create, read, update, delete operations for phenopacket resources.
Offset-based pagination (JSON:API v1.1) with ``page[number]`` and
``page[size]``.

Decomposed during Wave 4 — this module now only owns the thin HTTP
plumbing. Business rules live in
``app.phenopackets.services.phenopacket_service``; data access lives
in ``app.phenopackets.repositories.phenopacket_repository``; the less
common related-lookup and timeline endpoints live in the
``crud_related`` and ``crud_timeline`` sibling modules.

Wave 7 D.1 additions:
- PUT now delegates to PhenopacketStateService.edit_record (§6.1/§6.3)
  so that editing a published record triggers the clone-to-draft path.
- GET list and GET detail apply role-based visibility filters and content
  resolvers from the centralized visibility repository (§8).
- Anonymous / viewer callers see only published records; their response
  contains the head-published revision content and state=None (§7.2).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_optional_user, is_curator_or_admin, require_curator
from app.database import get_db
from app.models.json_api import JsonApiResponse
from app.models.user import User
from app.phenopackets.models import (
    Phenopacket,
    PhenopacketCreate,
    PhenopacketDelete,
    PhenopacketResponse,
    PhenopacketUpdate,
)
from app.phenopackets.query_builders import (
    add_has_variants_filter,
    add_sex_filter,
    build_phenopacket_response,
)
from app.phenopackets.repositories import (
    PhenopacketRepository,
    curator_filter,
    public_filter,
    resolve_curator_content,
    resolve_public_content,
)
from app.phenopackets.routers.crud_helpers import parse_sort_parameter
from app.phenopackets.services.phenopacket_service import (
    PhenopacketService,
    ServiceConflict,
    ServiceDatabaseError,
    ServiceNotFound,
    ServiceValidationError,
)
from app.phenopackets.services.state_service import PhenopacketStateService
from app.phenopackets.validator import PhenopacketSanitizer, PhenopacketValidator
from app.utils.pagination import build_offset_response

router = APIRouter(tags=["phenopackets-crud"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _base_list_query() -> Any:
    """Build a SELECT with all actor eager-loads attached."""
    return select(Phenopacket).options(
        selectinload(Phenopacket.created_by_user),
        selectinload(Phenopacket.updated_by_user),
        selectinload(Phenopacket.deleted_by_user),
        selectinload(Phenopacket.draft_owner),
    )


# =============================================================================
# List / batch / get
# =============================================================================


@router.get("/", response_model=JsonApiResponse)
async def list_phenopackets(
    request: Request,
    # Offset pagination (JSON:API v1.1)
    page_number: int = Query(
        1,
        alias="page[number]",
        ge=1,
        description="Page number (1-indexed)",
    ),
    page_size: int = Query(
        100,
        alias="page[size]",
        ge=1,
        le=1000,
        description="Items per page (max: 1000)",
    ),
    # Filters
    filter_sex: Optional[str] = Query(
        None, alias="filter[sex]", description="Filter by subject sex"
    ),
    filter_has_variants: Optional[bool] = Query(
        None,
        alias="filter[has_variants]",
        description="Filter by variant presence",
    ),
    # Sort
    sort: Optional[str] = Query(
        None, description="Comma-separated fields, prefix with '-' for desc"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """List phenopackets with offset-based pagination.

    Uses ``page[number]`` and ``page[size]`` for direct page access.

    **Visibility (Wave 7 D.1):**
    - Anonymous / viewer callers: only ``state='published'`` records with a
      non-NULL ``head_published_revision_id``.  The ``phenopacket`` field in
      each item is the head-published revision content.
    - Curator / admin callers: all non-archived, non-deleted records; the
      ``phenopacket`` field is the current working copy.

    **Pagination:**
    - ``page[number]``: Page number (1-indexed, default: 1)
    - ``page[size]``: Items per page (default: 100, max: 1000)

    **Filtering:**
    - ``filter[sex]``: MALE, FEMALE, OTHER_SEX, UNKNOWN_SEX
    - ``filter[has_variants]``: true/false

    **Sorting:**
    - ``sort``: Comma-separated fields (e.g., ``-created_at,subject_id``)
    - Supported fields: ``created_at``, ``subject_id``, ``subject_sex``,
      ``features_count``, ``has_variant``
    """
    is_curator = is_curator_or_admin(current_user)

    # Build base query with eager-loads for actor relationships
    base_stmt = _base_list_query()

    # Apply visibility filter
    if is_curator:
        query = curator_filter(base_stmt)
    else:
        query = public_filter(base_stmt)

    # Apply sex and variant filters
    query = add_sex_filter(query, filter_sex)
    query = add_has_variants_filter(query, filter_has_variants)

    # Apply sort
    if sort:
        sort_clauses = parse_sort_parameter(sort)
        query = query.order_by(
            *sort_clauses,
            Phenopacket.created_at.desc(),
            Phenopacket.id.desc(),
        )
    else:
        query = query.order_by(Phenopacket.created_at.desc(), Phenopacket.id.desc())

    # Count (same filters, no sort/pagination)
    count_base = select(func.count()).select_from(Phenopacket)
    if is_curator:
        count_base = curator_filter(count_base)
    else:
        count_base = public_filter(count_base)
    count_base = add_sex_filter(count_base, filter_sex)
    count_base = add_has_variants_filter(count_base, filter_has_variants)
    count_result = await db.execute(count_base)
    total_count = int(count_result.scalar() or 0)

    # Paginate
    offset = (page_number - 1) * page_size
    paginated = query.offset(offset).limit(page_size)
    result = await db.execute(paginated)
    rows: List[Phenopacket] = list(result.scalars().all())

    # Build data items: resolve content per role, then augment with Wave 7
    # D.1 state fields AT THE TOP LEVEL alongside the raw GA4GH content.
    # We keep the existing JSON:API contract (raw phenopacket keys at top
    # level) rather than wrapping content under `.phenopacket`, so existing
    # consumers that expect `item["subject"]` / `item["interpretations"]`
    # keep working. Non-curators get the state fields as null per §7.2.
    data: List[Dict[str, Any]] = []
    for pp in rows:
        content: Dict[str, Any]
        if is_curator:
            content = resolve_curator_content(pp)
        else:
            # Fast-path: head pointer guaranteed non-NULL by public_filter
            public_content = await resolve_public_content(db, pp)
            if public_content is None:
                # Should never happen (public_filter guards head IS NOT NULL),
                # but skip defensively
                continue
            content = public_content
        augmented = dict(content)
        if is_curator:
            augmented["state"] = pp.state
            augmented["head_published_revision_id"] = pp.head_published_revision_id
            augmented["editing_revision_id"] = pp.editing_revision_id
            augmented["draft_owner_id"] = pp.draft_owner_id
            augmented["draft_owner_username"] = (
                pp.draft_owner.username if pp.draft_owner else None
            )
        else:
            augmented["state"] = None
            augmented["head_published_revision_id"] = None
            augmented["editing_revision_id"] = None
            augmented["draft_owner_id"] = None
            augmented["draft_owner_username"] = None
        data.append(augmented)

    filters: Dict[str, Any] = {}
    if filter_sex:
        filters["filter[sex]"] = filter_sex
    if filter_has_variants is not None:
        filters["filter[has_variants]"] = filter_has_variants

    return build_offset_response(
        data=data,
        current_page=page_number,
        page_size=page_size,
        total_records=total_count,
        base_url=str(request.url.path),
        filters=filters,
        sort=sort,
    )


@router.get("/batch", response_model=List[Dict])
async def get_phenopackets_batch(
    phenopacket_ids: str = Query(
        ..., description="Comma-separated list of phenopacket IDs"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Get multiple phenopackets by IDs in a single query.

    Prevents N+1 HTTP requests when fetching multiple phenopackets.

    **Visibility (Wave 7 D.1):**
    - Anonymous / viewer callers: only published records are returned; draft
      IDs are silently omitted (same rule as GET list/detail).
    - Curator / admin callers: all non-deleted records matching the IDs.

    Performance:
        - Single database query using WHERE...IN clause
        - 10x-100x faster than individual requests
    """
    ids = [pid.strip() for pid in phenopacket_ids.split(",") if pid.strip()]
    if not ids:
        return []

    is_curator = is_curator_or_admin(current_user)

    # Build a filtered batch query so draft records are not leaked to
    # anonymous callers (security: public_filter enforces I3).
    stmt = (
        select(Phenopacket)
        .where(Phenopacket.phenopacket_id.in_(ids))
        .options(
            selectinload(Phenopacket.created_by_user),
            selectinload(Phenopacket.updated_by_user),
            selectinload(Phenopacket.deleted_by_user),
            selectinload(Phenopacket.draft_owner),
        )
    )
    if is_curator:
        stmt = curator_filter(stmt)
    else:
        stmt = public_filter(stmt)

    result = await db.execute(stmt)
    phenopackets_list = list(result.scalars().all())

    items = []
    for pp in phenopackets_list:
        if is_curator:
            content: Dict[str, Any] = resolve_curator_content(pp)
        else:
            public_content = await resolve_public_content(db, pp)
            if public_content is None:
                continue
            content = public_content
        items.append(
            {
                "phenopacket_id": pp.phenopacket_id,
                "phenopacket": content,
            }
        )
    return items


@router.get("/{phenopacket_id}", response_model=PhenopacketResponse)
async def get_phenopacket(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Get a single phenopacket by ID with metadata.

    **Visibility (Wave 7 D.1):**
    - Curator / admin: returns the working copy with all state-machine fields.
    - Anonymous / viewer: returns the head-published revision content with
      ``state=None`` (state is not exposed to non-curators per spec §7.2).
      Returns 404 if the record is not published.
    """
    is_curator = is_curator_or_admin(current_user)

    # Eager-load actor relationships + draft_owner for response building
    stmt = (
        select(Phenopacket)
        .where(Phenopacket.phenopacket_id == phenopacket_id)
        .options(
            selectinload(Phenopacket.created_by_user),
            selectinload(Phenopacket.updated_by_user),
            selectinload(Phenopacket.deleted_by_user),
            selectinload(Phenopacket.draft_owner),
        )
    )

    if is_curator:
        stmt = curator_filter(stmt)
    else:
        stmt = public_filter(stmt)

    result = await db.execute(stmt)
    pp = result.scalar_one_or_none()

    if pp is None:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    if is_curator:
        content = resolve_curator_content(pp)
        return build_phenopacket_response(
            pp,
            phenopacket_override=content,
            include_state=True,
        )
    else:
        public_content = await resolve_public_content(db, pp)
        if public_content is None:
            raise HTTPException(status_code=404, detail="Phenopacket not found")
        return build_phenopacket_response(
            pp,
            phenopacket_override=public_content,
            include_state=False,
        )


# =============================================================================
# Create / update / delete
# =============================================================================


@router.post("/", response_model=PhenopacketResponse)
async def create_phenopacket(
    phenopacket_data: PhenopacketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
):
    """Create a new phenopacket (requires curator role).

    Returns:
        201: Phenopacket created successfully
        400: Validation error
        409: Phenopacket with this ID already exists
        500: Database error
    """
    service = PhenopacketService(PhenopacketRepository(db))
    try:
        new_phenopacket = await service.create(
            phenopacket_data, actor_id=current_user.id
        )
    except ServiceValidationError as exc:
        raise HTTPException(
            status_code=400, detail={"validation_errors": exc.errors}
        ) from exc
    except ServiceConflict as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from exc
    except ServiceDatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return build_phenopacket_response(new_phenopacket, include_state=True)


@router.put("/{phenopacket_id}", response_model=PhenopacketResponse)
async def update_phenopacket(
    phenopacket_id: str,
    phenopacket_data: PhenopacketUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
):
    """Update an existing phenopacket.

    **Wave 7 D.1 branching logic:**

    - ``state='published'`` → clone-to-draft (§6.1): a new revision row is
      created, ``editing_revision_id`` and ``draft_owner_id`` are set, the
      public head pointer remains unchanged (I1).
    - ``state ∈ {draft, changes_requested}`` → in-place save (§6.3): the
      working copy is updated in place, no new revision row is written.
    - Any other state → 409 ``invalid_transition`` (withdraw or resubmit first).

    Exception → HTTP mapping:
    - ``RevisionMismatch``  → 409 revision_mismatch
    - ``EditInProgress``    → 409 edit_in_progress
    - ``ForbiddenNotOwner`` → 403 forbidden_not_owner
    - ``InvalidTransition`` → 409 invalid_transition

    Raises:
        404: Phenopacket not found or soft-deleted
        409: Conflict (revision mismatch, edit in progress, invalid state)
        403: Forbidden (not draft owner)
        400: Validation error
    """
    repo = PhenopacketRepository(db)
    pp = await repo.get_by_id(phenopacket_id)
    if pp is None:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    # Validate & sanitise content (reuse existing validator/sanitizer)
    sanitizer = PhenopacketSanitizer()
    validator = PhenopacketValidator()
    sanitized = sanitizer.sanitize_phenopacket(phenopacket_data.phenopacket)
    errors = validator.validate(sanitized)
    if errors:
        raise HTTPException(status_code=400, detail={"validation_errors": errors})

    svc = PhenopacketStateService(db)
    try:
        updated = await svc.edit_record(
            pp.id,
            new_content=sanitized,
            change_reason=phenopacket_data.change_reason,
            expected_revision=(
                phenopacket_data.revision
                if phenopacket_data.revision is not None
                else pp.revision
            ),
            actor=current_user,
        )
    except PhenopacketStateService.RevisionMismatch as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "revision_mismatch", "message": str(exc)},
        ) from exc
    except PhenopacketStateService.EditInProgress as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "edit_in_progress", "message": str(exc)},
        ) from exc
    except PhenopacketStateService.ForbiddenNotOwner as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden_not_owner", "message": str(exc)},
        ) from exc
    except PhenopacketStateService.InvalidTransition as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "invalid_transition", "message": str(exc)},
        ) from exc

    # Re-fetch with actor eager-loads for the response renderer
    reloaded = await repo.get_by_id(phenopacket_id)
    if reloaded is None:
        reloaded = updated

    return build_phenopacket_response(reloaded, include_state=True)


@router.delete("/{phenopacket_id}")
async def delete_phenopacket(
    phenopacket_id: str,
    delete_request: PhenopacketDelete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
):
    """Soft delete a phenopacket with audit trail (requires curator role).

    Implements soft delete pattern to preserve research data integrity.
    Records are marked as deleted but remain in the database for audit
    purposes.

    Raises:
        404: Phenopacket not found or already deleted
        500: Database error
    """
    service = PhenopacketService(PhenopacketRepository(db))
    try:
        return await service.soft_delete(
            phenopacket_id,
            delete_request.change_reason,
            actor_id=current_user.id,
            actor_username=current_user.username,
            expected_revision=delete_request.revision,
        )
    except ServiceNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Phenopacket not found or already deleted",
        ) from exc
    except ServiceConflict as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from exc
    except ServiceDatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
