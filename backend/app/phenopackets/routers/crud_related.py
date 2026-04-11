"""Phenopacket "related lookup" endpoints.

Owns three read-only endpoints that fan out from a phenopacket id or
an external reference:

- ``GET /{phenopacket_id}/audit`` — audit trail for one phenopacket
- ``GET /by-variant/{variant_id}`` — phenopackets referencing a variant
- ``GET /by-publication/{pmid}`` — phenopackets citing a publication

Extracted during Wave 4 from the monolithic ``crud.py``. The router
still mounts at the same ``/phenopackets`` prefix (via
``routers/__init__.py``), so the HTTP paths are unchanged.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_curator
from app.database import get_db
from app.phenopackets.models import PhenopacketAuditResponse
from app.phenopackets.repositories import PhenopacketRepository
from app.phenopackets.routers.crud_helpers import validate_pmid

logger = logging.getLogger(__name__)

router = APIRouter(tags=["phenopackets-crud"])


@router.get("/{phenopacket_id}/audit", response_model=List[PhenopacketAuditResponse])
async def get_phenopacket_audit_history(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_curator),
):
    """Get the audit history for a phenopacket.

    Returns all audit-trail entries for the specified phenopacket,
    ordered by timestamp (most recent first). Works even for
    soft-deleted phenopackets — we still want to render their old
    edits.
    """
    repo = PhenopacketRepository(db)

    # Verify phenopacket exists (include soft-deleted for history view)
    phenopacket = await repo.get_by_id(phenopacket_id, include_deleted=True)
    if phenopacket is None:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    audit_entries = await repo.list_audit_history(phenopacket_id)

    return [
        PhenopacketAuditResponse(
            id=str(audit.id),
            phenopacket_id=audit.phenopacket_id,
            action=audit.action,
            changed_by=audit.changed_by,
            changed_at=audit.changed_at,
            change_reason=audit.change_reason,
            change_summary=audit.change_summary,
            change_patch=audit.change_patch,
            old_value=audit.old_value,
            new_value=audit.new_value,
        )
        for audit in audit_entries
    ]


@router.get("/by-variant/{variant_id}")
async def get_phenopackets_by_variant(
    variant_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return every phenopacket that contains a specific variant id.

    Uses a parameterised JSONB query so the ``variant_id`` cannot be
    used for SQL injection. Returns a list of plain dicts with the
    raw phenopacket payload — the router does not go through the
    ``PhenopacketResponse`` Pydantic model here because several
    callers only need the embedded phenopacket JSON.
    """
    query = text(
        """
    SELECT id, phenopacket_id, version, phenopacket,
           created_at, updated_at, schema_version
    FROM phenopackets p
    WHERE EXISTS (
        SELECT 1
        FROM jsonb_array_elements(p.phenopacket->'interpretations') as interp,
             jsonb_array_elements(
                 interp->'diagnosis'->'genomicInterpretations'
             ) as gi
        WHERE gi->'variantInterpretation'->'variationDescriptor'->>'id'
              = :variant_id
    )
    ORDER BY p.created_at DESC
    """
    )

    result = await db.execute(query, {"variant_id": variant_id})
    rows = result.mappings().all()

    # Return structured response with metadata and phenopacket data.
    # Note: phenopacket['id'] is the internal ID, not database record ID.
    return [
        {
            "phenopacket_id": row["phenopacket_id"],
            "version": row["version"],
            "phenopacket": row["phenopacket"],
            "created_at": row["created_at"].isoformat()
            if row["created_at"]
            else None,
            "updated_at": row["updated_at"].isoformat()
            if row["updated_at"]
            else None,
            "schema_version": row["schema_version"],
        }
        for row in rows
    ]


@router.get("/by-publication/{pmid}", response_model=Dict)
async def get_by_publication(
    pmid: str,
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Max records (max: 500)"),
    sex: Optional[str] = Query(
        None,
        pattern="^(MALE|FEMALE|OTHER_SEX|UNKNOWN_SEX)$",
        description="Filter by sex",
    ),
    has_variants: Optional[bool] = Query(
        None, description="Filter by variant presence"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get phenopackets citing a specific publication.

    **Security:** PMID is validated to prevent SQL injection.

    **Parameters:**
    - **pmid**: PubMed ID (format: PMID:12345678 or just 12345678)
    - **skip**: Pagination offset (default: 0)
    - **limit**: Max records to return (default: 100, max: 500)
    - **sex**: Filter by sex (MALE|FEMALE|OTHER_SEX|UNKNOWN_SEX)
    - **has_variants**: Filter by variant presence (true/false)

    **Returns:**
    - Phenopackets where metaData.externalReferences contains this PMID
    - Total count of matching phenopackets
    - Pagination metadata

    **Error Codes:**
    - 400: Invalid PMID format or parameters
    - 404: No phenopackets found for this publication
    - 500: Database error
    """
    try:
        pmid = validate_pmid(pmid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # SECURITY: Cap limit to prevent excessive data exposure
    limit = min(limit, 500)

    query = """
        SELECT
            phenopacket_id,
            phenopacket
        FROM phenopackets
        WHERE phenopacket->'metaData'->'externalReferences' @> :pmid_filter
        AND deleted_at IS NULL
    """

    pmid_filter = json.dumps([{"id": pmid}])

    params = {"pmid_filter": pmid_filter, "skip": skip, "limit": limit}

    if sex:
        query += " AND subject_sex = :sex"
        params["sex"] = sex

    if has_variants is not None:
        if has_variants:
            query += " AND jsonb_array_length(phenopacket->'interpretations') > 0"
        else:
            query += (
                " AND (phenopacket->'interpretations' IS NULL OR "
                "jsonb_array_length(phenopacket->'interpretations') = 0)"
            )

    count_query = """
        SELECT COUNT(*)
        FROM phenopackets
        WHERE phenopacket->'metaData'->'externalReferences' @> :pmid_filter
        AND deleted_at IS NULL
    """

    if sex:
        count_query += " AND subject_sex = :sex"
    if has_variants is not None:
        if has_variants:
            count_query += " AND jsonb_array_length(phenopacket->'interpretations') > 0"
        else:
            count_query += (
                " AND (phenopacket->'interpretations' IS NULL OR "
                "jsonb_array_length(phenopacket->'interpretations') = 0)"
            )

    try:
        total_result = await db.execute(text(count_query), params)
        total = total_result.scalar()

        if total == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No phenopackets found citing publication {pmid}",
            )

        query += " ORDER BY phenopacket_id LIMIT :limit OFFSET :skip"

        result = await db.execute(text(query), params)
        rows = result.fetchall()

        return {
            "data": [
                {"phenopacket_id": row.phenopacket_id, "phenopacket": row.phenopacket}
                for row in rows
            ],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        logger.error("Error fetching phenopackets for PMID %s: %s", pmid, exc)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from exc
