"""``GET /api/v2/publications/{pmid}/metadata`` endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.publications.service import (
    PubMedAPIError,
    PubMedNotFoundError,
    PubMedRateLimitError,
    PubMedTimeoutError,
    get_publication_metadata,
)

from .schemas import PublicationMetadataResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["publications"])


@router.get(
    "/{pmid}/metadata",
    response_model=PublicationMetadataResponse,
    summary="Get publication metadata from PubMed",
    description="""
    Fetch publication metadata with permanent database storage.

    **Features:**
    - Permanent database storage (fetched once, stored forever)
    - PMID validation (SQL injection prevention)
    - Automatic retry with exponential backoff for transient failures
    - Rate limit handling
    - Standards compliance (GA4GH Phenopackets v2)

    **PMID Format:**
    - Accepts: `PMID:12345678` or `12345678`
    - Returns: Normalized `PMID:12345678` format

    **Data Source:** PubMed E-Utilities API
    """,
    response_description="Publication metadata with authors, journal, year, DOI",
    responses={
        200: {
            "description": "Successfully retrieved metadata (from cache or PubMed)",
        },
        400: {
            "description": "Invalid PMID format",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid PMID format: abc123"}
                }
            },
        },
        404: {
            "description": "PMID not found in PubMed",
            "content": {
                "application/json": {
                    "example": {"detail": "PMID 99999999 not found in PubMed"}
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded, retry after 60 seconds"
                    }
                }
            },
        },
        504: {
            "description": "Gateway timeout fetching from PubMed",
        },
        500: {
            "description": "Internal server error",
        },
    },
)
async def get_publication_metadata_endpoint(
    pmid: str, db: AsyncSession = Depends(get_db)
):
    """Get publication metadata by PMID."""
    try:
        metadata = await get_publication_metadata(pmid, db, fetched_by="api")
        metadata["fetched_at"] = metadata["fetched_at"].isoformat()
        logger.info(
            "Successfully retrieved metadata for %s", pmid, extra={"pmid": pmid}
        )
        return metadata

    except ValueError as exc:
        logger.warning(
            "Invalid PMID format: %s", pmid, extra={"pmid": pmid, "error": str(exc)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid PMID format: {exc}",
        )

    except PubMedNotFoundError as exc:
        logger.warning("PMID not found: %s", pmid, extra={"pmid": pmid})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        )

    except PubMedRateLimitError as exc:
        logger.error("Rate limit exceeded for %s", pmid, extra={"pmid": pmid})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": "60"},
        )

    except PubMedTimeoutError as exc:
        logger.error("Timeout fetching %s", pmid, extra={"pmid": pmid})
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)
        )

    except PubMedAPIError as exc:
        logger.error(
            "PubMed API error for %s: %s",
            pmid,
            exc,
            extra={"pmid": pmid, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PubMed API error: {exc}",
        )

    except Exception as exc:  # noqa: BLE001
        # Catch-all for truly unexpected errors. Narrowing further would
        # let unknown exceptions leak as raw 500s with tracebacks in
        # the response body. Known PubMed failure modes are handled
        # above.
        logger.exception(
            "Unexpected error fetching %s: %s", pmid, exc, extra={"pmid": pmid}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
