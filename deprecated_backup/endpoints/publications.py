# File: app/endpoints/publications.py
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.dependencies import get_publication_repository
from app.repositories import PublicationRepository
from app.schemas import PublicationResponse
from app.utils import (
    build_base_url,
    build_pagination_meta,
    build_repository_filters,
    build_search_fields,
    parse_filter_json,
)

router = APIRouter()


@router.get("/", response_model=Dict[str, Any], summary="Get Publications")
async def get_publications(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of publications per page"),
    sort: Optional[str] = Query(
        None,
        description=(
            "Sort field (e.g. 'publication_id' for ascending or "
            "'-publication_id' for descending order)"
        ),
    ),
    filter_query: Optional[str] = Query(
        None,
        alias="filter",
        description=(
            "Filtering criteria as a JSON string. Example: "
            '{"status": "active", "publication_date": {"gt": "2021-01-01"}}'
        ),
    ),
    q: Optional[str] = Query(
        None,
        description=(
            "Search query to search across predefined fields: "
            "publication_id, publication_type, title, abstract, DOI, PMID, journal"
        ),
    ),
    publication_repo: PublicationRepository = Depends(get_publication_repository),
) -> Dict[str, Any]:
    """Retrieve a paginated list of publications.

    Publications can be filtered by a JSON filter and/or a search query.
    The filter parameter should be provided as a JSON string.
    Additionally, if a search query `q` is provided, the endpoint will search across:
      - publication_id
      - publication_type
      - title
      - abstract
      - DOI
      - PMID
      - journal
    """
    try:
        # Parse filters and search query
        filters = parse_filter_json(filter_query) if filter_query else {}
        search_fields = [
            "publication_id",
            "publication_type",
            "title",
            "abstract",
            "doi",
            "pmid",
            "journal",
        ]
        search_query = build_search_fields(q, search_fields) if q else None

        # Build repository filters
        repo_filters = build_repository_filters(filters, search_query)

        # Get publications from repository
        publications, total_count = await publication_repo.get_multi(
            skip=(page - 1) * page_size, limit=page_size, filters=repo_filters
        )

        if not publications and page == 1:
            raise HTTPException(status_code=404, detail="No publications found")

        # Build pagination metadata
        base_url = build_base_url(request)
        pagination_meta = build_pagination_meta(
            base_url=base_url, page=page, page_size=page_size, total=total_count
        )

        # Convert to response format
        publication_responses = []
        for pub in publications:
            pub_data = {
                "id": str(pub.id),
                "publication_id": pub.publication_id,
                "publication_type": pub.publication_type,
                "title": pub.title,
                "abstract": pub.abstract,
                "doi": pub.doi,
                "pmid": pub.pmid,
                "journal": pub.journal,
                "publication_alias": pub.publication_alias,
                "publication_date": pub.publication_date.isoformat()
                if pub.publication_date
                else None,
                "keywords": pub.keywords or [],
                "medical_specialty": pub.medical_specialty or [],
                "comment": pub.comment,
            }
            publication_responses.append(pub_data)

        return {"data": publication_responses, "meta": pagination_meta}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving publications: {str(e)}"
        )


@router.get(
    "/{publication_id}",
    response_model=PublicationResponse,
    summary="Get Publication by ID",
)
async def get_publication(
    publication_id: str,
    publication_repo: PublicationRepository = Depends(get_publication_repository),
) -> Dict[str, Any]:
    """Get a specific publication by its publication_id (e.g., 'pub0001')."""
    try:
        publication = await publication_repo.get_by_publication_id(publication_id)

        if not publication:
            raise HTTPException(
                status_code=404, detail=f"Publication {publication_id} not found"
            )

        # Convert to response format
        return {
            "id": str(publication.id),
            "publication_id": publication.publication_id,
            "publication_type": publication.publication_type,
            "title": publication.title,
            "abstract": publication.abstract,
            "doi": publication.doi,
            "pmid": publication.pmid,
            "journal": publication.journal,
            "publication_alias": publication.publication_alias,
            "publication_date": publication.publication_date.isoformat()
            if publication.publication_date
            else None,
            "keywords": publication.keywords or [],
            "medical_specialty": publication.medical_specialty or [],
            "comment": publication.comment,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving publication {publication_id}: {str(e)}",
        )
