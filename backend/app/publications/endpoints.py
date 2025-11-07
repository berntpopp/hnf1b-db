"""API endpoints for publication metadata."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.publications.service import (
    PubMedAPIError,
    PubMedNotFoundError,
    PubMedRateLimitError,
    PubMedTimeoutError,
    get_publication_metadata,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/publications", tags=["publications"])


# Pydantic response models
class AuthorModel(BaseModel):
    """Author information."""

    name: str
    affiliation: Optional[str] = None


class PublicationMetadataResponse(BaseModel):
    """Publication metadata response model."""

    pmid: str = Field(..., description="PubMed ID in format PMID:12345678")
    title: str = Field(..., description="Publication title")
    authors: list[AuthorModel] = Field(
        ..., description="List of authors with affiliations"
    )
    journal: Optional[str] = Field(None, description="Journal name")
    year: Optional[int] = Field(None, description="Publication year")
    doi: Optional[str] = Field(None, description="DOI identifier")
    abstract: Optional[str] = Field(None, description="Abstract text (may be null)")
    data_source: str = Field(default="PubMed", description="Data source")
    fetched_at: str = Field(..., description="Cache timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pmid": "PMID:30791938",
                "title": "HNF1B-related disorder: clinical characteristics and genetic findings",
                "authors": [
                    {"name": "Smith J", "affiliation": "Department of Medicine"},
                    {"name": "Doe A", "affiliation": "Department of Genetics"},
                ],
                "journal": "Journal of Medical Genetics",
                "year": 2019,
                "doi": "10.1136/jmedgenet-2018-105729",
                "abstract": None,
                "data_source": "PubMed",
                "fetched_at": "2025-10-22T14:30:00",
            }
        }
    )


@router.get(
    "/{pmid}/metadata",
    response_model=PublicationMetadataResponse,
    summary="Get publication metadata from PubMed",
    description="""
    Fetch publication metadata with database caching.

    **Features:**
    - Database caching (90-day TTL)
    - PMID validation (SQL injection prevention)
    - Rate limiting handling
    - Provenance tracking

    **PMID Format:**
    - Accepts: "30791938" or "PMID:30791938"
    - Returns: Normalized "PMID:12345678"

    **Cache Behavior:**
    - Cache hit: < 50ms response
    - Cache miss: < 1000ms (fetches from PubMed)
    - Cache TTL: 90 days

    **Error Handling:**
    - 400: Invalid PMID format
    - 404: Publication not found in PubMed
    - 429: Rate limit exceeded (retry after N seconds)
    - 500: PubMed API error
    - 504: Timeout fetching from PubMed
    """,
    responses={
        200: {
            "description": "Publication metadata retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "pmid": "PMID:30791938",
                        "title": "HNF1B-related disorder",
                        "authors": [
                            {"name": "Smith J", "affiliation": "Dept Medicine"}
                        ],
                        "journal": "J Med Genet",
                        "year": 2019,
                        "doi": "10.1136/jmedgenet-2018-105729",
                        "abstract": None,
                        "data_source": "PubMed",
                        "fetched_at": "2025-10-22T14:30:00",
                    }
                }
            },
        },
        400: {"description": "Invalid PMID format"},
        404: {"description": "Publication not found in PubMed"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "PubMed API error"},
        504: {"description": "Timeout fetching from PubMed"},
    },
)
async def get_publication_metadata_endpoint(
    pmid: str, db: AsyncSession = Depends(get_db)
):
    """Get publication metadata by PMID.

    Args:
        pmid: PubMed ID (format: PMID:12345678 or 12345678)
        db: Database session (injected)

    Returns:
        PublicationMetadataResponse: Publication metadata

    Raises:
        HTTPException: Various error conditions
    """
    try:
        # Fetch metadata with caching
        metadata = await get_publication_metadata(pmid, db, fetched_by="api")

        # Convert datetime to ISO string
        metadata["fetched_at"] = metadata["fetched_at"].isoformat()

        logger.info(f"Successfully retrieved metadata for {pmid}", extra={"pmid": pmid})

        return metadata

    except ValueError as e:
        # Invalid PMID format
        logger.warning(
            f"Invalid PMID format: {pmid}", extra={"pmid": pmid, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid PMID format: {e}"
        )

    except PubMedNotFoundError as e:
        # PMID not found in PubMed
        logger.warning(f"PMID not found: {pmid}", extra={"pmid": pmid})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    except PubMedRateLimitError as e:
        # Rate limit exceeded
        logger.error(f"Rate limit exceeded for {pmid}", extra={"pmid": pmid})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": "60"},
        )

    except PubMedTimeoutError as e:
        # Timeout fetching from PubMed
        logger.error(f"Timeout fetching {pmid}", extra={"pmid": pmid})
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(e))

    except PubMedAPIError as e:
        # General PubMed API error
        logger.error(
            f"PubMed API error for {pmid}: {e}", extra={"pmid": pmid, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PubMed API error: {e}",
        )

    except Exception as e:
        # Unexpected error
        logger.exception(f"Unexpected error fetching {pmid}: {e}", extra={"pmid": pmid})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
