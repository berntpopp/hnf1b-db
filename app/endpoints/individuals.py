# app/endpoints/individuals.py
"""Individuals endpoint - migrated to use PostgreSQL."""

import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.dependencies import (
    get_individual_repository,
    get_report_repository,
    parse_pagination,
    parse_sort_order,
)
from app.repositories import IndividualRepository, ReportRepository
from app.schemas import IndividualResponse, PaginatedResponse
from app.utils import (
    INDIVIDUAL_FIELD_MAPPING,
    build_base_url,
    build_pagination_meta,
    build_repository_filters,
    build_search_fields,
    parse_deep_object_filters,
    parse_filter_json,
)

router = APIRouter()


@router.get("/", response_model=PaginatedResponse, summary="Get Individuals")
async def get_individuals(
    request: Request,
    skip_limit: tuple[int, int] = Depends(parse_pagination),
    sort_info: tuple[Optional[str], bool] = Depends(parse_sort_order),
    filter_query: Optional[str] = Query(
        None,
        alias="filter",
        description=(
            "Filtering criteria as a JSON string. Example: "
            '{"Sex": "male", "individual_id": {"gt": "ind0930"}}'
        ),
    ),
    q: Optional[str] = Query(
        None,
        description=(
            "Search query to search across predefined fields: "
            "individual_id, Sex, individual_DOI, IndividualIdentifier, "
            "family_history, age_onset, cohort"
        ),
    ),
    individual_repo: IndividualRepository = Depends(get_individual_repository),
) -> Dict[str, Any]:
    """Retrieve a paginated list of individuals.

    Optionally filtered by a JSON filter and/or a search query.

    The filter parameter should be provided as a JSON string.
    Additionally, if a search query `q` is provided, the endpoint will search
    across:
      - individual_id
      - Sex (mapped to sex)
      - individual_DOI (mapped to individual_doi)
      - IndividualIdentifier (mapped to individual_identifier)
      - family_history (searches in related reports)
      - age_onset (searches in related reports)
      - cohort (searches in related reports)

    Example:
      /individuals?sort=-individual_id&page=1&page_size=10&filter={"Sex":
      "male"}&q=ind0930
    """
    start_time = time.perf_counter()
    skip, limit = skip_limit
    sort_field, sort_desc = sort_info

    # Parse and convert the JSON filter (if provided)
    raw_filter = parse_filter_json(filter_query)
    parsed_filters = parse_deep_object_filters(raw_filter)

    # Apply field mapping to convert API field names to model field names
    repository_filters = build_repository_filters(
        parsed_filters, INDIVIDUAL_FIELD_MAPPING
    )

    # Handle search query
    search_fields = None
    if q:
        # Map API field names to model field names for search
        api_search_fields = [
            "individual_id",
            "Sex",
            "individual_DOI",
            "IndividualIdentifier",
        ]
        search_fields = build_search_fields(
            q, api_search_fields, INDIVIDUAL_FIELD_MAPPING
        )

        # Note: family_history, age_onset, and cohort are in reports table
        # For now, we'll search only in individual fields
        # Complex cross-table search can be implemented later in the repository

    # Query individuals
    try:
        individuals, total = await individual_repo.get_multi(
            skip=skip,
            limit=limit,
            filters=repository_filters,
            search=q,
            search_fields=search_fields,
            order_by=sort_field,
            order_desc=sort_desc,
            load_relationships=[],  # Don't load relationships for list view
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    if not individuals:
        raise HTTPException(status_code=404, detail="No individuals found")

    # Convert SQLAlchemy models to response format
    response_data = []
    for individual in individuals:
        # Convert model to dict and apply reverse field mapping for API compatibility
        individual_dict = {
            "id": str(individual.id),
            "individual_id": individual.individual_id,
            "Sex": individual.sex,
            "individual_DOI": individual.individual_doi,
            "DupCheck": individual.dup_check,
            "IndividualIdentifier": individual.individual_identifier,
            "Problematic": individual.problematic,
            "created_at": individual.created_at,
            "updated_at": individual.updated_at,
        }
        response_data.append(individual_dict)

    # Build pagination metadata
    base_url = build_base_url(request)
    page = (skip // limit) + 1
    page_size = limit

    # Include current query parameters in pagination links
    extra_params: Dict[str, Any] = {}
    if sort_field:
        sort_param = f"-{sort_field}" if sort_desc else sort_field
        extra_params["sort"] = sort_param
    if filter_query:
        extra_params["filter"] = filter_query
    if q:
        extra_params["q"] = q

    end_time = time.perf_counter()
    execution_time = end_time - start_time

    meta = build_pagination_meta(
        base_url,
        page,
        page_size,
        total,
        query_params=extra_params,
        execution_time=execution_time,
    )

    return {"data": response_data, "meta": meta}


@router.get(
    "/{individual_id}",
    response_model=IndividualResponse,
    summary="Get Individual by ID",
)
async def get_individual(
    individual_id: str,
    include_reports: bool = Query(False, description="Include associated reports"),
    include_variants: bool = Query(False, description="Include associated variants"),
    individual_repo: IndividualRepository = Depends(get_individual_repository),
) -> Dict[str, Any]:
    """Get a specific individual by their individual_id (e.g., 'ind0001')."""
    try:
        # Determine what relationships to load
        load_relationships = []
        if include_reports:
            load_relationships.append("reports")
        if include_variants:
            load_relationships.append("variants")

        individual = await individual_repo.get_by_individual_id(
            individual_id, include_reports=bool(load_relationships)
        )

        if not individual:
            raise HTTPException(
                status_code=404, detail=f"Individual {individual_id} not found"
            )

        # Convert to response format with field mapping
        response_data = {
            "id": str(individual.id),
            "individual_id": individual.individual_id,
            "Sex": individual.sex,
            "individual_DOI": individual.individual_doi,
            "DupCheck": individual.dup_check,
            "IndividualIdentifier": individual.individual_identifier,
            "Problematic": individual.problematic,
            "created_at": individual.created_at,
            "updated_at": individual.updated_at,
        }

        # Add relationships if requested
        if include_reports and individual.reports:
            response_data["reports"] = [
                {
                    "id": str(report.id),
                    "report_id": report.report_id,
                    "phenotypes": report.phenotypes,
                    "review_date": report.review_date,
                    "report_date": report.report_date,
                    "comment": report.comment,
                    "family_history": report.family_history,
                    "age_reported": report.age_reported,
                    "age_onset": report.age_onset,
                    "cohort": report.cohort,
                }
                for report in individual.reports
            ]

        if include_variants and individual.variants:
            response_data["variants"] = [
                {
                    "id": str(variant.id),
                    "variant_id": variant.variant_id,
                    "is_current": variant.is_current,
                }
                for variant in individual.variants
            ]

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/{individual_id}/reports", summary="Get Reports for Individual")
async def get_individual_reports(
    individual_id: str,
    report_repo: ReportRepository = Depends(get_report_repository),
    individual_repo: IndividualRepository = Depends(get_individual_repository),
) -> Dict[str, Any]:
    """Get all reports for a specific individual."""
    try:
        # First verify the individual exists
        individual = await individual_repo.get_by_individual_id(individual_id)
        if not individual:
            raise HTTPException(
                status_code=404, detail=f"Individual {individual_id} not found"
            )

        # Get reports for this individual
        reports = await report_repo.get_by_individual_id(individual.id)

        response_data = [
            {
                "id": str(report.id),
                "report_id": report.report_id,
                "phenotypes": report.phenotypes,
                "review_date": report.review_date,
                "report_date": report.report_date,
                "comment": report.comment,
                "family_history": report.family_history,
                "age_reported": report.age_reported,
                "age_onset": report.age_onset,
                "cohort": report.cohort,
                "reviewed_by": str(report.reviewed_by) if report.reviewed_by else None,
                "publication_ref": str(report.publication_ref)
                if report.publication_ref
                else None,
            }
            for report in reports
        ]

        return {
            "data": response_data,
            "individual_id": individual_id,
            "total": len(response_data),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/{individual_id}/variants", summary="Get Variants for Individual")
async def get_individual_variants(
    individual_id: str,
    individual_repo: IndividualRepository = Depends(get_individual_repository),
) -> Dict[str, Any]:
    """Get all variants for a specific individual."""
    try:
        # Get individual with variants
        individual = await individual_repo.get_by_individual_id(individual_id)
        if not individual:
            raise HTTPException(
                status_code=404, detail=f"Individual {individual_id} not found"
            )

        # Load variants for this individual
        individual_with_variants = await individual_repo.get_with_variants(
            individual.id
        )
        variants = individual_with_variants.variants if individual_with_variants else []

        response_data = [
            {
                "id": str(variant.id),
                "variant_id": variant.variant_id,
                "is_current": variant.is_current,
                "created_at": variant.created_at,
                "updated_at": variant.updated_at,
            }
            for variant in variants
        ]

        return {
            "data": response_data,
            "individual_id": individual_id,
            "total": len(response_data),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
