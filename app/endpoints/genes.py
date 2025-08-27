# File: app/endpoints/genes.py
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request

from app.dependencies import get_gene_repository
from app.repositories import GeneRepository
from app.utils import build_pagination_meta

router = APIRouter()


@router.get("/", response_model=Dict[str, Any], summary="Get Genes")
async def get_genes(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of genes per page"),
    gene_repo: GeneRepository = Depends(get_gene_repository),
    sort: Optional[str] = Query(
        None,
        description=(
            "Sort field (e.g. 'gene_symbol' for ascending or '-gene_symbol' "
            "for descending order)"
        ),
    ),
) -> Dict[str, Any]:
    """Retrieve a paginated list of genes with structure data."""
    try:
        # Get genes with pagination
        offset = (page - 1) * page_size
        genes_data = await gene_repo.get_multi(skip=offset, limit=page_size)
        genes, total_count = genes_data

        # Format genes data for response
        formatted_genes = []
        for gene in genes:
            gene_dict = {
                "id": str(gene.id),
                "gene_symbol": gene.gene_symbol,
                "ensembl_gene_id": gene.ensembl_gene_id,
                "transcript": gene.transcript,
                "exons": gene.exons,
                "hg38": gene.hg38,
                "hg19": gene.hg19,
                "created_at": gene.created_at.isoformat() if gene.created_at else None,
            }
            formatted_genes.append(gene_dict)

        # Build pagination metadata
        base_url = str(request.base_url).rstrip("/")
        current_url = f"{base_url}/api/genes"

        pagination_meta = build_pagination_meta(
            base_url=current_url, page=page, page_size=page_size, total=total_count
        )

        return {"data": formatted_genes, "meta": pagination_meta}

    except Exception as e:
        print(f"Error fetching genes: {e}")
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
