"""Curator endpoints for a publication's ``medical_specialty`` (issue #11).

``GET  /{pmid}/specialty`` — saved value + rule-based suggestions with evidence.
``PUT  /{pmid}/specialty`` — save the curated value.
"""

from __future__ import annotations

import logging
from typing import get_args

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_curator
from app.core.config import settings
from app.database import get_db
from app.models.user import User
from app.publications.service import (
    PubMedError,
    PubMedNotFoundError,
    get_publication_metadata,
)
from app.publications.specialty import MedicalSpecialty, fetch_specialty_suggestions

from .schemas import (
    MedicalSpecialtyUpdate,
    SpecialtySuggestionItem,
    SpecialtySuggestionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["publications"])


async def _ensure_metadata(pmid: str, db: AsyncSession) -> dict:
    """Validate the PMID and make sure its publication_metadata row exists."""
    try:
        return await get_publication_metadata(pmid, db, fetched_by="curator")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid PMID: {exc}")
    except PubMedNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PubMedError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"PubMed: {exc}")


@router.get(
    "/{pmid}/specialty",
    response_model=SpecialtySuggestionResponse,
    summary="Curated medical specialty plus rule-based suggestions",
    description=(
        "Returns the saved medical_specialty and suggestions scored from the "
        "journal (NLM Catalog MeSH + title, weight 2) and the first/last "
        "author affiliations (weight 1 each). Curator-only; calls NCBI live and "
        "degrades to empty suggestions + suggestion_error if NCBI fails."
    ),
)
async def get_specialty(
    pmid: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_curator),
) -> SpecialtySuggestionResponse:
    """Return the saved specialty and live suggestions for one PMID."""
    metadata = await _ensure_metadata(pmid, db)
    apis = settings.external_apis
    result: dict = {}
    error = None
    try:
        async with aiohttp.ClientSession() as session:
            result = await fetch_specialty_suggestions(
                [metadata["pmid"]],
                session=session,
                base_url=apis.efetch.base_url,
                api_key=settings.PUBMED_API_KEY,
                timeout=apis.efetch.timeout_seconds,
            )
    except (aiohttp.ClientError, TimeoutError) as exc:
        # Degrade, don't fail: the curator can still pick from the vocabulary.
        logger.warning("Specialty suggestion fetch failed for %s: %s", pmid, exc)
        error = "NCBI unavailable, suggestions could not be loaded"
    suggestion = result.get(metadata["pmid"].replace("PMID:", ""))
    items = (
        [
            SpecialtySuggestionItem(
                specialty=name,
                score=suggestion.scores[name],
                evidence=suggestion.evidence[name],
            )
            for name in suggestion.ranked
        ]
        if suggestion
        else []
    )
    return SpecialtySuggestionResponse(
        pmid=metadata["pmid"],
        medical_specialty=metadata.get("medical_specialty") or [],
        vocabulary=list(get_args(MedicalSpecialty)),
        suggestions=items,
        suggestion_error=error,
    )


@router.put(
    "/{pmid}/specialty",
    response_model=MedicalSpecialtyUpdate,
    summary="Save the curated medical specialty",
)
async def put_specialty(
    pmid: str,
    body: MedicalSpecialtyUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_curator),
) -> MedicalSpecialtyUpdate:
    """Persist the curator's ordered specialty list (empty list clears it)."""
    metadata = await _ensure_metadata(pmid, db)
    value = list(dict.fromkeys(body.medical_specialty))  # dedupe, keep order
    await db.execute(
        text(
            "UPDATE publication_metadata SET medical_specialty = :value "
            "WHERE pmid = :pmid"
        ),
        {"value": value or None, "pmid": metadata["pmid"]},
    )
    await db.commit()
    logger.info(
        "medical_specialty set",
        extra={"pmid": metadata["pmid"], "value": value, "user": user.username},
    )
    return MedicalSpecialtyUpdate(medical_specialty=value)
