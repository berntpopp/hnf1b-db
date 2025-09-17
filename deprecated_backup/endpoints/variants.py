# File: app/endpoints/variants.py
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request

from app.dependencies import get_variant_repository
from app.repositories import VariantRepository
from app.utils import build_pagination_meta

router = APIRouter()


@router.get("/", response_model=Dict[str, Any], summary="Get Variants")
async def get_variants(
    request: Request,
    page: int = Query(1, ge=1, description="Current page number"),
    page_size: int = Query(10, ge=1, description="Number of variants per page"),
    variant_repo: VariantRepository = Depends(get_variant_repository),
    sort: Optional[str] = Query(
        None,
        description=(
            "Sort field (e.g. 'variant_id' for ascending or '-variant_id' "
            "for descending order)"
        ),
    ),
    filter_query: Optional[str] = Query(
        None,
        alias="filter",
        description=(
            "Filtering criteria as a JSON string. Example: "
            '{"status": "active", "variant_id": {"gt": "var1000"}}'
        ),
    ),
    q: Optional[str] = Query(
        None,
        description=(
            "Search query to search across predefined fields: "
            "variant_id, hg19, hg19_info, hg38, hg38_info, variant_type, "
            "classifications.verdict, classifications.criteria, "
            "annotations.c_dot, annotations.p_dot, annotations.impact, "
            "annotations.effect"
        ),
    ),
) -> Dict[str, Any]:
    """Retrieve a paginated list of variants.

    Variants can be filtered by a JSON filter and/or a free-text search query.
    The filter parameter should be provided as a JSON string.
    Additionally, if a search query `q` is provided, the endpoint will search across:
      - variant_id
      - hg19, hg19_info
      - hg38, hg38_info
      - variant_type
      - classifications.verdict, classifications.criteria
      - annotations.c_dot, annotations.p_dot, annotations.impact,
        annotations.effect
    """
    try:
        # Get current variants with pagination using repository
        offset = (page - 1) * page_size
        variants_data = await variant_repo.get_current_variants(
            skip=offset, limit=page_size
        )
        variants, total_count = variants_data

        # Format variants data for response
        formatted_variants = []
        for variant in variants:
            # Convert to dict and include related data
            variant_dict = {
                "id": str(variant.id),
                "variant_id": variant.variant_id,
                "variant_type": variant.variant_type,
                "hg19": variant.hg19,
                "hg38": variant.hg38,
                "hg19_info": variant.hg19_info,
                "hg38_info": variant.hg38_info,
                "is_current": variant.is_current,
                "created_at": variant.created_at.isoformat()
                if variant.created_at
                else None,
                "annotations": [
                    {
                        "transcript": ann.transcript,
                        "c_dot": ann.c_dot,
                        "p_dot": ann.p_dot,
                        "impact": ann.impact,
                        "effect": ann.effect,
                        "variant_class": ann.variant_class,
                        "source": ann.source,
                    }
                    for ann in variant.annotations
                ],
                "classifications": [
                    {
                        "verdict": cls.verdict,
                        "criteria": cls.criteria,
                        "system": cls.system,
                        "comment": cls.comment,
                    }
                    for cls in variant.classifications
                ],
            }
            formatted_variants.append(variant_dict)

        # Build pagination metadata
        base_url = str(request.base_url).rstrip("/")
        current_url = f"{base_url}/api/variants"

        pagination_meta = build_pagination_meta(
            base_url=current_url, page=page, page_size=page_size, total=total_count
        )

        return {"data": formatted_variants, "meta": pagination_meta}

    except Exception as e:
        print(f"Error fetching variants: {e}")
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
