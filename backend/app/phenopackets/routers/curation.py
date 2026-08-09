"""Curator-only source-observation curation routes."""

from __future__ import annotations

from typing import Any, NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_curator
from app.database import get_db
from app.models.user import User
from app.phenopackets.curation.api_models import (
    CorrectionAppendRequest,
    CurationError,
    ProjectionPreviewRequest,
    ReportPatchRequest,
    ResolutionAppendRequest,
)
from app.phenopackets.repositories import PhenopacketRepository
from app.phenopackets.services.curation_service import (
    CurationService,
    CurationServiceError,
)
from app.phenopackets.services.state_service import PhenopacketStateService

router = APIRouter(tags=["phenopackets-curation"])


def _expected_revision(revision: int | None, if_match: str | None) -> int:
    """Read a required revision from body or strong ETag precondition."""
    if revision is not None:
        return revision
    if if_match is None:
        raise HTTPException(
            status_code=428,
            detail={
                "code": "precondition_required",
                "message": "revision or If-Match is required",
            },
        )
    try:
        return int(if_match.strip().strip('"'))
    except ValueError as exc:
        raise HTTPException(
            status_code=428,
            detail={
                "code": "precondition_required",
                "message": "If-Match must contain a revision",
            },
        ) from exc


async def _record_or_404(db: AsyncSession, phenopacket_id: str):
    record = await PhenopacketRepository(db).get_by_id(phenopacket_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Phenopacket not found")
    return record


def _raise_service_error(error: CurationServiceError) -> NoReturn:
    conflict_codes = {"stale_conflict", "correction_preimage_mismatch"}
    status = 409 if error.code in conflict_codes else 422
    raise HTTPException(
        status_code=status,
        detail=CurationError(code=error.code, errors=error.issues).model_dump(
            mode="json"
        ),
    ) from error


def _map_state_error(error: Exception) -> NoReturn:
    if isinstance(error, PhenopacketStateService.RecordNotFound):
        raise HTTPException(status_code=404, detail="Phenopacket not found") from error
    if isinstance(error, PhenopacketStateService.RevisionMismatch):
        raise HTTPException(
            status_code=409,
            detail={"code": "revision_mismatch", "message": str(error)},
        ) from error
    if isinstance(error, PhenopacketStateService.EditInProgress):
        raise HTTPException(
            status_code=409,
            detail={"code": "edit_in_progress", "message": str(error)},
        ) from error
    if isinstance(error, PhenopacketStateService.ForbiddenNotOwner):
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden_not_owner", "message": str(error)},
        ) from error
    if isinstance(error, PhenopacketStateService.InvalidTransition):
        raise HTTPException(
            status_code=409,
            detail={"code": "invalid_transition", "message": str(error)},
        ) from error
    raise error


@router.get("/{phenopacket_id}/curation", response_model=dict[str, Any])
async def get_curation(
    phenopacket_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_curator),
) -> dict[str, Any]:
    """Return the full private ledger and deterministic canonical projection."""
    record = await _record_or_404(db, phenopacket_id)
    try:
        payload = CurationService(db).read(record)
    except CurationServiceError as error:
        _raise_service_error(error)
    response.headers["ETag"] = f'"{record.revision}"'
    return payload


@router.post("/{phenopacket_id}/curation/preview", response_model=dict[str, Any])
async def preview_curation(
    phenopacket_id: str,
    body: ProjectionPreviewRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_curator),
) -> dict[str, Any]:
    """Validate and project an unsaved observation replacement without writing."""
    record = await _record_or_404(db, phenopacket_id)
    try:
        return CurationService(db).preview(record, body)
    except CurationServiceError as error:
        _raise_service_error(error)


async def _write_response(
    record: Any, response: Response, db: AsyncSession
) -> dict[str, Any]:
    await db.commit()
    await db.refresh(record)
    payload = CurationService(db).read(record)
    response.headers["ETag"] = f'"{record.revision}"'
    return payload


@router.patch(
    "/{phenopacket_id}/reports/{observation_id}", response_model=dict[str, Any]
)
async def patch_report(
    phenopacket_id: str,
    observation_id: str,
    body: ReportPatchRequest,
    response: Response,
    if_match: str | None = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_curator),
) -> dict[str, Any]:
    """Save exactly one observation through the append-only state service."""
    if body.observation.observation_id != observation_id:
        raise HTTPException(status_code=422, detail={"code": "observation_id_mismatch"})
    record = await _record_or_404(db, phenopacket_id)
    try:
        updated = await CurationService(db).replace_report(
            record, body, actor, _expected_revision(body.revision, if_match)
        )
        return await _write_response(updated, response, db)
    except CurationServiceError as error:
        _raise_service_error(error)
    except (
        PhenopacketStateService.RecordNotFound,
        PhenopacketStateService.RevisionMismatch,
        PhenopacketStateService.EditInProgress,
        PhenopacketStateService.ForbiddenNotOwner,
        PhenopacketStateService.InvalidTransition,
    ) as error:
        _map_state_error(error)


@router.post("/{phenopacket_id}/curation/corrections", response_model=dict[str, Any])
async def append_correction(
    phenopacket_id: str,
    body: CorrectionAppendRequest,
    response: Response,
    if_match: str | None = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_curator),
) -> dict[str, Any]:
    """Append a correction; source raw fields and prior corrections remain immutable."""
    record = await _record_or_404(db, phenopacket_id)
    try:
        updated = await CurationService(db).append_correction(
            record, body, actor, _expected_revision(body.revision, if_match)
        )
        return await _write_response(updated, response, db)
    except CurationServiceError as error:
        _raise_service_error(error)
    except (
        PhenopacketStateService.RecordNotFound,
        PhenopacketStateService.RevisionMismatch,
        PhenopacketStateService.EditInProgress,
        PhenopacketStateService.ForbiddenNotOwner,
        PhenopacketStateService.InvalidTransition,
    ) as error:
        _map_state_error(error)


@router.post("/{phenopacket_id}/curation/resolutions", response_model=dict[str, Any])
async def append_resolution(
    phenopacket_id: str,
    body: ResolutionAppendRequest,
    response: Response,
    if_match: str | None = Header(None, alias="If-Match"),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_curator),
) -> dict[str, Any]:
    """Append a resolution only when its conflict candidate digest is current."""
    record = await _record_or_404(db, phenopacket_id)
    try:
        updated = await CurationService(db).append_resolution(
            record, body, actor, _expected_revision(body.revision, if_match)
        )
        return await _write_response(updated, response, db)
    except CurationServiceError as error:
        _raise_service_error(error)
    except (
        PhenopacketStateService.RecordNotFound,
        PhenopacketStateService.RevisionMismatch,
        PhenopacketStateService.EditInProgress,
        PhenopacketStateService.ForbiddenNotOwner,
        PhenopacketStateService.InvalidTransition,
    ) as error:
        _map_state_error(error)
