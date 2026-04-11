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
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_curator
from app.database import get_db
from app.models.json_api import JsonApiResponse
from app.phenopackets.models import (
    Phenopacket,
    PhenopacketCreate,
    PhenopacketDelete,
    PhenopacketResponse,
    PhenopacketUpdate,
)
from app.phenopackets.query_builders import build_phenopacket_response
from app.phenopackets.repositories import PhenopacketRepository
from app.phenopackets.routers.crud_helpers import parse_sort_parameter
from app.phenopackets.services.phenopacket_service import (
    PhenopacketService,
    ServiceConflict,
    ServiceDatabaseError,
    ServiceNotFound,
    ServiceValidationError,
)
from app.utils.pagination import build_offset_response

router = APIRouter(tags=["phenopackets-crud"])
logger = logging.getLogger(__name__)


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
):
    """List phenopackets with offset-based pagination.

    Uses ``page[number]`` and ``page[size]`` for direct page access.

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
    repo = PhenopacketRepository(db)

    query = repo.base_list_query(
        filter_sex=filter_sex,
        filter_has_variants=filter_has_variants,
    )

    if sort:
        sort_clauses = parse_sort_parameter(sort)
        query = query.order_by(
            *sort_clauses,
            Phenopacket.created_at.desc(),
            Phenopacket.id.desc(),
        )
    else:
        query = query.order_by(Phenopacket.created_at.desc(), Phenopacket.id.desc())

    total_count = await repo.count_filtered(
        filter_sex=filter_sex,
        filter_has_variants=filter_has_variants,
    )

    offset = (page_number - 1) * page_size
    rows, _ = await repo.list_paginated(query, offset=offset, limit=page_size)

    filters: Dict[str, Any] = {}
    if filter_sex:
        filters["filter[sex]"] = filter_sex
    if filter_has_variants is not None:
        filters["filter[has_variants]"] = filter_has_variants

    return build_offset_response(
        data=[pp.phenopacket for pp in rows],
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
):
    """Get multiple phenopackets by IDs in a single query.

    Prevents N+1 HTTP requests when fetching multiple phenopackets.

    Performance:
        - Single database query using WHERE...IN clause
        - 10x-100x faster than individual requests
    """
    ids = [pid.strip() for pid in phenopacket_ids.split(",") if pid.strip()]
    if not ids:
        return []

    repo = PhenopacketRepository(db)
    phenopackets = await repo.get_batch(ids)
    return [
        {
            "phenopacket_id": pp.phenopacket_id,
            "phenopacket": pp.phenopacket,
        }
        for pp in phenopackets
    ]


@router.get("/{phenopacket_id}", response_model=PhenopacketResponse)
async def get_phenopacket(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single phenopacket by ID with metadata (excludes soft-deleted)."""
    repo = PhenopacketRepository(db)
    phenopacket = await repo.get_by_id(phenopacket_id)
    if phenopacket is None:
        raise HTTPException(status_code=404, detail="Phenopacket not found")
    return build_phenopacket_response(phenopacket)


# =============================================================================
# Create / update / delete
# =============================================================================


@router.post("/", response_model=PhenopacketResponse)
async def create_phenopacket(
    phenopacket_data: PhenopacketCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_curator),
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
    return build_phenopacket_response(new_phenopacket)


@router.put("/{phenopacket_id}", response_model=PhenopacketResponse)
async def update_phenopacket(
    phenopacket_id: str,
    phenopacket_data: PhenopacketUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_curator),
):
    """Update an existing phenopacket with optimistic locking and audit trail.

    Implements:
    - Optimistic locking via revision field (prevents lost updates)
    - Complete audit trail with JSON Patch
    - Conflict detection for concurrent edits
    - Soft-deleted records are filtered out

    Raises:
        404: Phenopacket not found or soft-deleted
        409: Conflict - revision mismatch (concurrent edit detected)
        400: Validation error
    """
    service = PhenopacketService(PhenopacketRepository(db))
    try:
        updated = await service.update(
            phenopacket_id, phenopacket_data, actor_id=current_user.id
        )
    except ServiceNotFound as exc:
        raise HTTPException(status_code=404, detail="Phenopacket not found") from exc
    except ServiceConflict as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from exc
    except ServiceValidationError as exc:
        raise HTTPException(
            status_code=400, detail={"validation_errors": exc.errors}
        ) from exc
    except ServiceDatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return build_phenopacket_response(updated)


@router.delete("/{phenopacket_id}")
async def delete_phenopacket(
    phenopacket_id: str,
    delete_request: PhenopacketDelete,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_curator),
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
