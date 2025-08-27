# File: app/endpoints/proteins.py
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request

from app.dependencies import get_protein_repository
from app.repositories import ProteinRepository
from app.utils import build_pagination_meta

router = APIRouter()


@router.get("/", response_model=Dict[str, Any], summary="Get Proteins")
async def get_proteins(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of proteins per page"),
    protein_repo: ProteinRepository = Depends(get_protein_repository),
    sort: Optional[str] = Query(
        None,
        description=(
            "Sort field (e.g. 'gene' for ascending or '-gene' for descending order). "
            "Defaults to sorting by gene."
        ),
    ),
) -> Dict[str, Any]:
    """Retrieve a paginated list of proteins with structure and domain data."""
    try:
        # Get proteins with pagination
        offset = (page - 1) * page_size
        proteins_data = await protein_repo.get_multi(skip=offset, limit=page_size)
        proteins, total_count = proteins_data

        # Format proteins data for response
        formatted_proteins = []
        for protein in proteins:
            protein_dict = {
                "id": str(protein.id),
                "gene": protein.gene,
                "transcript": protein.transcript,
                "protein": protein.protein,
                "features": protein.features,
                "created_at": protein.created_at.isoformat()
                if protein.created_at
                else None,
            }
            formatted_proteins.append(protein_dict)

        # Build pagination metadata
        base_url = str(request.base_url).rstrip("/")
        current_url = f"{base_url}/api/proteins"

        pagination_meta = build_pagination_meta(
            base_url=current_url, page=page, page_size=page_size, total=total_count
        )

        return {"data": formatted_proteins, "meta": pagination_meta}

    except Exception as e:
        print(f"Error fetching proteins: {e}")
        return {
            "data": [],
            "meta": {
                "page": page,
                "page_size": page_size,
                "total": 0,
                "total_pages": 0,
                "has_next": False,
                "has_prev": False,
                "next_page": None,
                "prev_page": None,
            },
        }
