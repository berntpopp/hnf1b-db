"""Phenopacket-centric API endpoints."""

import json
import logging
import re
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.database import get_db
from app.middleware.rate_limiter import check_rate_limit, get_client_ip
from app.phenopackets.models import (
    AggregationResult,
    Phenopacket,
    PhenopacketCreate,
    PhenopacketResponse,
    PhenopacketSearchQuery,
    PhenopacketUpdate,
)
from app.phenopackets.molecular_consequence import (
    compute_molecular_consequence,
    filter_by_consequence,
)
from app.phenopackets.validator import PhenopacketSanitizer, PhenopacketValidator
from app.phenopackets.variant_search_validation import (
    validate_classification,
    validate_gene,
    validate_molecular_consequence,
    validate_search_query,
    validate_variant_type,
)
from app.utils.audit_logger import log_variant_search

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2/phenopackets", tags=["phenopackets"])

validator = PhenopacketValidator()
sanitizer = PhenopacketSanitizer()


@router.get("/", response_model=List[PhenopacketResponse])
async def list_phenopackets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sex: Optional[str] = Query(None, description="Filter by sex"),
    has_variants: Optional[bool] = Query(
        None, description="Filter by variant presence"
    ),
    db: AsyncSession = Depends(get_db),
):
    """List all phenopackets with optional filtering."""
    query = select(Phenopacket)

    if sex:
        query = query.where(Phenopacket.subject_sex == sex)

    if has_variants is not None:
        if has_variants:
            query = query.where(
                func.jsonb_array_length(Phenopacket.phenopacket["interpretations"]) > 0
            )
        else:
            query = query.where(
                func.coalesce(
                    func.jsonb_array_length(Phenopacket.phenopacket["interpretations"]),
                    0,
                )
                == 0
            )

    query = query.offset(skip).limit(limit).order_by(Phenopacket.created_at.desc())

    result = await db.execute(query)
    phenopackets = result.scalars().all()

    return [
        PhenopacketResponse(
            id=str(pp.id),
            phenopacket_id=pp.phenopacket_id,
            version=pp.version,
            phenopacket=pp.phenopacket,
            created_at=pp.created_at,
            updated_at=pp.updated_at,
            schema_version=pp.schema_version,
        )
        for pp in phenopackets
    ]


@router.get("/batch", response_model=List[Dict])
async def get_phenopackets_batch(
    phenopacket_ids: str = Query(
        ..., description="Comma-separated list of phenopacket IDs"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get multiple phenopackets by IDs in a single query.

    Prevents N+1 HTTP requests when fetching multiple phenopackets.

    Args:
        phenopacket_ids: Comma-separated phenopacket IDs (e.g., "id1,id2,id3")

    Returns:
        List of phenopacket documents

    Performance:
        - Single database query using WHERE...IN clause
        - 10x-100x faster than individual requests
    """
    ids = [id.strip() for id in phenopacket_ids.split(",") if id.strip()]

    if not ids:
        return []

    # Single query for all phenopackets (no N+1)
    result = await db.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id.in_(ids))
    )
    phenopackets = result.scalars().all()

    return [
        {
            "phenopacket_id": pp.phenopacket_id,
            "phenopacket": pp.phenopacket,
        }
        for pp in phenopackets
    ]


def validate_pmid(pmid: str) -> str:
    """Validate and normalize PMID format.

    Args:
        pmid: PubMed ID (with or without PMID: prefix)

    Returns:
        Normalized PMID (format: PMID:12345678)

    Raises:
        ValueError: If PMID format is invalid
    """
    if not pmid.startswith("PMID:"):
        pmid = f"PMID:{pmid}"

    # Validate format: PMID followed by 1-8 digits only
    if not re.match(r"^PMID:\d{1,8}$", pmid):
        raise ValueError(f"Invalid PMID format: {pmid}. Expected PMID:12345678")

    return pmid


@router.get("/by-publication/{pmid}", response_model=Dict)
async def get_by_publication(
    pmid: str,
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Max records (max: 500)"),
    sex: Optional[str] = Query(
        None, regex="^(MALE|FEMALE|OTHER_SEX|UNKNOWN_SEX)$", description="Filter by sex"
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
        # SECURITY: Validate PMID format to prevent SQL injection
        pmid = validate_pmid(pmid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # SECURITY: Cap limit to prevent excessive data exposure
    limit = min(limit, 500)

    # Build query with JSONB filtering
    query = """
        SELECT
            phenopacket_id,
            phenopacket
        FROM phenopackets
        WHERE phenopacket->'metaData'->'externalReferences' @> :pmid_filter
    """

    # Build JSONB filter for PMID (parameterized - safe from injection)
    pmid_filter = json.dumps([{"id": pmid}])

    params = {"pmid_filter": pmid_filter, "skip": skip, "limit": limit}

    # Add optional filters with parameterized queries
    if sex:
        query += " AND subject_sex = :sex"
        params["sex"] = sex

    if has_variants is not None:
        if has_variants:
            query += " AND jsonb_array_length(phenopacket->'interpretations') > 0"
        else:
            query += " AND (phenopacket->'interpretations' IS NULL OR jsonb_array_length(phenopacket->'interpretations') = 0)"

    # Count query (same filters)
    count_query = """
        SELECT COUNT(*)
        FROM phenopackets
        WHERE phenopacket->'metaData'->'externalReferences' @> :pmid_filter
    """

    # Add same filters to count query
    if sex:
        count_query += " AND subject_sex = :sex"
    if has_variants is not None:
        if has_variants:
            count_query += " AND jsonb_array_length(phenopacket->'interpretations') > 0"
        else:
            count_query += " AND (phenopacket->'interpretations' IS NULL OR jsonb_array_length(phenopacket->'interpretations') = 0)"

    try:
        # Execute count query
        total_result = await db.execute(text(count_query), params)
        total = total_result.scalar()

        # Return 404 if no results found
        if total == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No phenopackets found citing publication {pmid}",
            )

        # Add pagination (parameters prevent injection)
        query += " ORDER BY phenopacket_id LIMIT :limit OFFSET :skip"

        # Execute query
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
        # Re-raise HTTP exceptions (404, 400)
        raise
    except Exception as e:
        logger.error(f"Error fetching phenopackets for PMID {pmid}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{phenopacket_id}", response_model=Dict)
async def get_phenopacket(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single phenopacket by ID."""
    result = await db.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
    )
    phenopacket = result.scalar_one_or_none()

    if not phenopacket:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    return phenopacket.phenopacket


@router.post("/search", response_model=List[PhenopacketResponse])
async def search_phenopackets(
    search_query: PhenopacketSearchQuery,
    db: AsyncSession = Depends(get_db),
):
    """Advanced search across phenopackets."""
    base_query = select(Phenopacket)

    # Search by phenotypes (HPO terms)
    if search_query.phenotypes:
        for hpo_term in search_query.phenotypes:
            base_query = base_query.where(
                Phenopacket.phenopacket["phenotypicFeatures"].contains(
                    [{"type": {"id": hpo_term}}]
                )
            )

    # Search by diseases (MONDO terms)
    if search_query.diseases:
        for disease_term in search_query.diseases:
            base_query = base_query.where(
                Phenopacket.phenopacket["diseases"].contains(
                    [{"term": {"id": disease_term}}]
                )
            )

    # Search by variants
    if search_query.variants:
        for variant in search_query.variants:
            base_query = base_query.where(
                func.jsonb_path_exists(
                    Phenopacket.phenopacket,
                    f"$.interpretations[*].diagnosis.genomicInterpretations[*]"
                    f".variantInterpretation.variationDescriptor.label ? "
                    f'(@ like_regex "{variant}")',
                )
            )

    # Search by measurements
    if search_query.measurements:
        for measurement in search_query.measurements:
            base_query = base_query.where(
                Phenopacket.phenopacket["measurements"].contains(
                    [{"assay": {"id": measurement.get("loinc_code")}}]
                )
            )

    # Filter by sex
    if search_query.sex:
        # Use the JSON field directly since subject_sex column might not be populated
        base_query = base_query.where(
            func.jsonb_extract_path_text(Phenopacket.phenopacket, "subject", "sex")
            == search_query.sex
        )

    # Filter by age range using ISO8601 duration parsing
    if search_query.min_age is not None or search_query.max_age is not None:
        age_conditions = []

        # Extract age from ISO8601 duration in the JSON path
        # Age location: phenopacket.subject.timeAtLastEncounter.age.iso8601duration
        age_extraction = text(r"""
            (
                COALESCE(
                    (regexp_match(
                        phenopacket->'subject'->'timeAtLastEncounter'->'age'->>'iso8601duration',
                        'P(\d+)Y'
                    ))[1]::int,
                    0
                ) +
                COALESCE(
                    (regexp_match(
                        phenopacket->'subject'->'timeAtLastEncounter'->'age'->>'iso8601duration',
                        'P\d*Y?(\d+)M'
                    ))[1]::float / 12,
                    0
                ) +
                COALESCE(
                    (regexp_match(
                        phenopacket->'subject'->'timeAtLastEncounter'->'age'->>'iso8601duration',
                        'P\d*Y?\d*M?(\d+)D'
                    ))[1]::float / 365.25,
                    0
                )
            )
        """)

        if search_query.min_age is not None:
            # Age must be >= minimum age
            age_conditions.append(
                text(f"""
                    phenopacket->'subject'->'timeAtLastEncounter'->
                    'age'->>'iso8601duration' IS NOT NULL
                    AND {age_extraction.text} >= :min_age
                """).bindparams(min_age=search_query.min_age)
            )

        if search_query.max_age is not None:
            # Age must be <= maximum age
            age_conditions.append(
                text(f"""
                    phenopacket->'subject'->'timeAtLastEncounter'->
                    'age'->>'iso8601duration' IS NOT NULL
                    AND {age_extraction.text} <= :max_age
                """).bindparams(max_age=search_query.max_age)
            )

        if age_conditions:
            base_query = base_query.where(and_(*age_conditions))

    result = await db.execute(base_query)
    phenopackets = result.scalars().all()

    return [
        PhenopacketResponse(
            id=str(pp.id),
            phenopacket_id=pp.phenopacket_id,
            version=pp.version,
            phenopacket=pp.phenopacket,
            created_at=pp.created_at,
            updated_at=pp.updated_at,
            schema_version=pp.schema_version,
        )
        for pp in phenopackets
    ]


@router.get("/features/batch", response_model=List[Dict])
async def get_phenotypic_features_batch(
    phenopacket_ids: str = Query(
        ..., description="Comma-separated list of phenopacket IDs"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get phenotypic features from multiple phenopackets in a single query.

    Prevents N+1 HTTP requests when fetching features for multiple phenopackets.

    Args:
        phenopacket_ids: Comma-separated phenopacket IDs (e.g., "id1,id2,id3")

    Returns:
        List of objects with phenopacket_id and features

    Performance:
        - Single database query using WHERE...IN clause
        - 10x-100x faster than individual requests
    """
    ids = [id.strip() for id in phenopacket_ids.split(",") if id.strip()]

    if not ids:
        return []

    # Single query for all phenotypic features (no N+1)
    result = await db.execute(
        select(
            Phenopacket.phenopacket_id,
            Phenopacket.phenopacket["phenotypicFeatures"].label("features"),
        ).where(Phenopacket.phenopacket_id.in_(ids))
    )

    rows = result.fetchall()

    return [
        {
            "phenopacket_id": row.phenopacket_id,
            "features": row.features if row.features else [],
        }
        for row in rows
    ]


@router.get("/{phenopacket_id}/features", response_model=List[Dict])
async def get_phenotypic_features(
    phenopacket_id: str,
    group: Optional[str] = Query(None, description="Filter by feature group"),
    db: AsyncSession = Depends(get_db),
):
    """Get phenotypic features from a phenopacket."""
    result = await db.execute(
        select(Phenopacket.phenopacket["phenotypicFeatures"]).where(
            Phenopacket.phenopacket_id == phenopacket_id
        )
    )
    features = result.scalar_one_or_none()

    if features is None:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    # Filter by group if specified
    if group:
        # This would require a mapping of HPO terms to groups
        # For now, return all features
        pass

    return features if features else []


@router.get("/variants/batch", response_model=List[Dict])
async def get_variants_batch(
    phenopacket_ids: str = Query(
        ..., description="Comma-separated list of phenopacket IDs"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get variants/interpretations from multiple phenopackets in a single query.

    Prevents N+1 HTTP requests when fetching variants for multiple phenopackets.

    Args:
        phenopacket_ids: Comma-separated phenopacket IDs (e.g., "id1,id2,id3")

    Returns:
        List of objects with phenopacket_id and interpretations

    Performance:
        - Single database query using WHERE...IN clause
        - 10x-100x faster than individual requests
    """
    ids = [id.strip() for id in phenopacket_ids.split(",") if id.strip()]

    if not ids:
        return []

    # Single query for all variants/interpretations (no N+1)
    result = await db.execute(
        select(
            Phenopacket.phenopacket_id,
            Phenopacket.phenopacket["interpretations"].label("interpretations"),
        ).where(Phenopacket.phenopacket_id.in_(ids))
    )

    rows = result.fetchall()

    return [
        {
            "phenopacket_id": row.phenopacket_id,
            "interpretations": row.interpretations if row.interpretations else [],
        }
        for row in rows
    ]


@router.get("/{phenopacket_id}/variants", response_model=List[Dict])
async def get_variants(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get variants/interpretations from a phenopacket."""
    result = await db.execute(
        select(Phenopacket.phenopacket["interpretations"]).where(
            Phenopacket.phenopacket_id == phenopacket_id
        )
    )
    interpretations = result.scalar_one_or_none()

    if interpretations is None:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    return interpretations if interpretations else []


@router.get("/{phenopacket_id}/diseases", response_model=List[Dict])
async def get_diseases(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get diseases from a phenopacket."""
    result = await db.execute(
        select(Phenopacket.phenopacket["diseases"]).where(
            Phenopacket.phenopacket_id == phenopacket_id
        )
    )
    diseases = result.scalar_one_or_none()

    if diseases is None:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    return diseases if diseases else []


@router.get("/{phenopacket_id}/measurements", response_model=List[Dict])
async def get_measurements(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get measurements from a phenopacket."""
    result = await db.execute(
        select(Phenopacket.phenopacket["measurements"]).where(
            Phenopacket.phenopacket_id == phenopacket_id
        )
    )
    measurements = result.scalar_one_or_none()

    if measurements is None:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    return measurements if measurements else []


@router.get("/variants/small-variants", response_model=List[Dict])
async def get_small_variants(
    db: AsyncSession = Depends(get_db),
):
    """Get all small variants (SNVs) across all phenopackets.

    Useful for protein plot visualizations and variant analysis.
    Returns variants filtered to exclude large CNVs.
    """
    query = """
    SELECT DISTINCT
        vd->>'id' as variant_id,
        vd->>'label' as label,
        vd->>'description' as description,
        vd->'geneContext'->>'symbol' as gene_symbol,
        vd->'structuralType'->>'label' as variant_type,
        vd->'molecularConsequences'->0->>'label' as consequence,
        gi->>'interpretationStatus' as pathogenicity,
        phenopacket_id
    FROM
        phenopackets,
        jsonb_array_elements(phenopacket->'interpretations') as interp,
        jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
        LATERAL (SELECT gi->'variantInterpretation'->'variationDescriptor' as vd) sub
    WHERE
        gi->'variantInterpretation'->'variationDescriptor' IS NOT NULL
        AND (
            vd->>'moleculeContext' = 'genomic'
            OR vd->'structuralType'->>'label' NOT IN ('deletion', 'duplication', 'insertion')
        )
    ORDER BY
        gene_symbol, variant_id
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    return [
        {
            "variant_id": row.variant_id,  # type: ignore
            "label": row.label,  # type: ignore
            "description": row.description,  # type: ignore
            "gene_symbol": row.gene_symbol,  # type: ignore
            "variant_type": row.variant_type,  # type: ignore
            "consequence": row.consequence,  # type: ignore
            "pathogenicity": row.pathogenicity,  # type: ignore
            "phenopacket_id": row.phenopacket_id,  # type: ignore
        }
        for row in rows
    ]


@router.post("/", response_model=PhenopacketResponse)
async def create_phenopacket(
    phenopacket_data: PhenopacketCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_auth),
):
    """Create a new phenopacket.

    Returns:
        201: Phenopacket created successfully
        400: Validation error
        409: Phenopacket with this ID already exists
        500: Database error
    """
    # Sanitize the phenopacket
    sanitized = sanitizer.sanitize_phenopacket(phenopacket_data.phenopacket)

    # Validate phenopacket structure
    errors = validator.validate(sanitized)
    if errors:
        raise HTTPException(status_code=400, detail={"validation_errors": errors})

    # Create new phenopacket
    # Database UNIQUE constraint will prevent duplicates atomically
    new_phenopacket = Phenopacket(
        phenopacket_id=sanitized["id"],
        phenopacket=sanitized,
        subject_id=sanitized["subject"]["id"],
        subject_sex=sanitized["subject"].get("sex", "UNKNOWN_SEX"),
        created_by=phenopacket_data.created_by or current_user.username,
    )

    db.add(new_phenopacket)

    try:
        await db.commit()
        await db.refresh(new_phenopacket)
    except Exception as e:
        await db.rollback()
        # Check for integrity errors (duplicate keys, foreign key violations, etc.)
        error_str = str(e).lower()
        if (
            "duplicate" in error_str or "unique" in error_str
        ) and "phenopacket_id" in error_str:
            raise HTTPException(
                status_code=409,
                detail=f"Phenopacket with ID '{sanitized['id']}' already exists",
            ) from e
        # Re-raise other database errors
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}") from e

    return PhenopacketResponse(
        id=str(new_phenopacket.id),
        phenopacket_id=new_phenopacket.phenopacket_id,
        version=new_phenopacket.version,
        phenopacket=new_phenopacket.phenopacket,
        created_at=new_phenopacket.created_at,
        updated_at=new_phenopacket.updated_at,
        schema_version=new_phenopacket.schema_version,
    )


@router.put("/{phenopacket_id}", response_model=PhenopacketResponse)
async def update_phenopacket(
    phenopacket_id: str,
    phenopacket_data: PhenopacketUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_auth),
):
    """Update an existing phenopacket."""
    result = await db.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
    )
    existing = result.scalar_one_or_none()

    if not existing:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    # Sanitize the updated phenopacket
    sanitized = sanitizer.sanitize_phenopacket(phenopacket_data.phenopacket)

    # Validate updated phenopacket
    errors = validator.validate(sanitized)
    if errors:
        raise HTTPException(status_code=400, detail={"validation_errors": errors})

    # Update the phenopacket
    existing.phenopacket = sanitized
    existing.subject_id = sanitized["subject"]["id"]
    existing.subject_sex = sanitized["subject"].get("sex", "UNKNOWN_SEX")
    existing.updated_by = phenopacket_data.updated_by or current_user.username

    try:
        await db.commit()
        await db.refresh(existing)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return PhenopacketResponse(
        id=str(existing.id),
        phenopacket_id=existing.phenopacket_id,
        version=existing.version,
        phenopacket=existing.phenopacket,
        created_at=existing.created_at,
        updated_at=existing.updated_at,
        schema_version=existing.schema_version,
    )


@router.delete("/{phenopacket_id}")
async def delete_phenopacket(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_auth),
):
    """Delete a phenopacket."""
    result = await db.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
    )
    phenopacket = result.scalar_one_or_none()

    if not phenopacket:
        raise HTTPException(status_code=404, detail="Phenopacket not found")

    await db.delete(phenopacket)

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return {"message": f"Phenopacket {phenopacket_id} deleted successfully"}


# Aggregation endpoints
@router.get("/aggregate/by-feature", response_model=List[AggregationResult])
async def aggregate_by_feature(
    db: AsyncSession = Depends(get_db),
):
    """Aggregate phenopackets by phenotypic features."""
    query = """
    SELECT
        feature->'type'->>'id' as hpo_id,
        feature->'type'->>'label' as label,
        COUNT(*) as count
    FROM
        phenopackets,
        jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature
    WHERE
        NOT COALESCE((feature->>'excluded')::boolean, false)
    GROUP BY
        feature->'type'->>'id',
        feature->'type'->>'label'
    ORDER BY
        count DESC
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(row.count for row in rows)  # type: ignore

    return [
        AggregationResult(
            label=row.label or row.hpo_id,  # type: ignore
            count=row.count,  # type: ignore
            percentage=(row.count / total * 100) if total > 0 else 0,  # type: ignore
            details={"hpo_id": row.hpo_id},  # type: ignore
        )
        for row in rows
    ]


@router.get("/aggregate/by-disease", response_model=List[AggregationResult])
async def aggregate_by_disease(
    db: AsyncSession = Depends(get_db),
):
    """Aggregate phenopackets by disease."""
    query = """
    SELECT
        disease->'term'->>'id' as disease_id,
        disease->'term'->>'label' as label,
        COUNT(*) as count
    FROM
        phenopackets,
        jsonb_array_elements(phenopacket->'diseases') as disease
    GROUP BY
        disease->'term'->>'id',
        disease->'term'->>'label'
    ORDER BY
        count DESC
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(row.count for row in rows)  # type: ignore

    return [
        AggregationResult(
            label=row.label or row.disease_id,  # type: ignore
            count=row.count,  # type: ignore
            percentage=(row.count / total * 100) if total > 0 else 0,  # type: ignore
            details={"disease_id": row.disease_id},  # type: ignore
        )
        for row in rows
    ]


@router.get("/aggregate/kidney-stages", response_model=List[AggregationResult])
async def aggregate_kidney_stages(
    db: AsyncSession = Depends(get_db),
):
    """Get distribution of kidney disease stages."""
    query = """
    SELECT
        modifier->>'label' as stage,
        COUNT(*) as count
    FROM
        phenopackets,
        jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature,
        jsonb_array_elements(COALESCE(feature->'modifiers', '[]'::jsonb)) as modifier
    WHERE
        feature->'type'->>'id' = 'HP:0012622'
        AND modifier->>'label' LIKE '%Stage%'
    GROUP BY
        modifier->>'label'
    ORDER BY
        stage
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(row.count for row in rows)  # type: ignore

    return [
        AggregationResult(
            label=row.stage,  # type: ignore
            count=row.count,  # type: ignore
            percentage=(row.count / total * 100) if total > 0 else 0,  # type: ignore
        )
        for row in rows
    ]


@router.get("/aggregate/sex-distribution", response_model=List[AggregationResult])
async def aggregate_sex_distribution(
    db: AsyncSession = Depends(get_db),
):
    """Get sex distribution of subjects."""
    query = """
    SELECT
        subject_sex as sex,
        COUNT(*) as count
    FROM
        phenopackets
    GROUP BY
        subject_sex
    ORDER BY
        count DESC
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(row.count for row in rows)  # type: ignore

    return [
        AggregationResult(
            label=row.sex,  # type: ignore
            count=row.count,  # type: ignore
            percentage=(row.count / total * 100) if total > 0 else 0,  # type: ignore
        )
        for row in rows
    ]


@router.get("/aggregate/variant-pathogenicity", response_model=List[AggregationResult])
async def aggregate_variant_pathogenicity(
    count_mode: str = Query("all", regex="^(all|unique)$", description="Count mode: 'all' (default) counts all variant instances, 'unique' counts distinct variants"),
    db: AsyncSession = Depends(get_db),
):
    """Get distribution of variant pathogenicity classifications.

    Args:
        count_mode:
            - "all" (default): Count all variant instances across phenopackets (e.g., 864 total)
            - "unique": Count only unique variants (deduplicates by variant ID)
    """
    if count_mode == "unique":
        # Count unique variants by variant ID
        query = """
        SELECT
            gi->>'interpretationStatus' as classification,
            COUNT(DISTINCT vd->>'id') as count
        FROM
            phenopackets,
            jsonb_array_elements(phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
            LATERAL (SELECT gi->'variantInterpretation'->'variationDescriptor' as vd) sub
        WHERE
            gi->'variantInterpretation'->'variationDescriptor' IS NOT NULL
        GROUP BY
            gi->>'interpretationStatus'
        ORDER BY
            count DESC
        """
    else:
        # Count all variant instances (original behavior)
        query = """
        SELECT
            gi->>'interpretationStatus' as classification,
            COUNT(*) as count
        FROM
            phenopackets,
            jsonb_array_elements(phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
        GROUP BY
            gi->>'interpretationStatus'
        ORDER BY
            count DESC
        """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(row.count for row in rows)  # type: ignore

    return [
        AggregationResult(
            label=row.classification,  # type: ignore
            count=row.count,  # type: ignore
            percentage=(row.count / total * 100) if total > 0 else 0,  # type: ignore
        )
        for row in rows
    ]


@router.get("/aggregate/variant-types", response_model=List[AggregationResult])
async def aggregate_variant_types(
    count_mode: str = Query("all", regex="^(all|unique)$", description="Count mode: 'all' (default) counts all variant instances, 'unique' counts distinct variants"),
    db: AsyncSession = Depends(get_db),
):
    """Get distribution of variant types (SNV, CNV, etc.).

    Args:
        count_mode:
            - "all" (default): Count all variant instances across phenopackets (e.g., 864 total)
            - "unique": Count only unique variants (deduplicates by variant ID)
    """
    if count_mode == "unique":
        # Count unique variants by variant ID
        query = """
        WITH variant_types AS (
            SELECT DISTINCT
                vd->>'id' as variant_id,
                CASE
                    WHEN vd->'vcfRecord'->>'alt' ~ '^<(DEL|DUP|INS|INV|CNV)' THEN 'CNV'
                    WHEN vd->>'moleculeContext' = 'genomic' THEN 'SNV'
                    ELSE 'OTHER'
                END as variant_type
            FROM
                phenopackets,
                jsonb_array_elements(phenopacket->'interpretations') as interp,
                jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
                LATERAL (SELECT gi->'variantInterpretation'->'variationDescriptor' as vd) sub
            WHERE
                gi->'variantInterpretation'->'variationDescriptor' IS NOT NULL
        )
        SELECT
            variant_type,
            COUNT(*) as count
        FROM variant_types
        GROUP BY variant_type
        ORDER BY count DESC
        """
    else:
        # Count all variant instances (original behavior)
        query = """
        SELECT
            CASE
                WHEN vd->'vcfRecord'->>'alt' ~ '^<(DEL|DUP|INS|INV|CNV)' THEN 'CNV'
                WHEN vd->>'moleculeContext' = 'genomic' THEN 'SNV'
                ELSE 'OTHER'
            END as variant_type,
            COUNT(*) as count
        FROM
            phenopackets,
            jsonb_array_elements(phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
            LATERAL (SELECT gi->'variantInterpretation'->'variationDescriptor' as vd) sub
        WHERE
            gi->'variantInterpretation'->'variationDescriptor' IS NOT NULL
        GROUP BY
            variant_type
        ORDER BY
            count DESC
        """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(row.count for row in rows)  # type: ignore

    return [
        AggregationResult(
            label=row.variant_type,  # type: ignore
            count=row.count,  # type: ignore
            percentage=(row.count / total * 100) if total > 0 else 0,  # type: ignore
        )
        for row in rows
    ]


@router.get("/aggregate/publications", response_model=List[Dict])
async def aggregate_publications(
    db: AsyncSession = Depends(get_db),
):
    """Get publication statistics with detailed information.

    Returns detailed publication data including PMID, URL, DOI, phenopacket count.
    Suitable for publications table view.
    """
    query = """
    SELECT
        ext_ref->>'id' as pmid,
        ext_ref->>'reference' as url,
        ext_ref->>'description' as description,
        COUNT(DISTINCT phenopacket_id) as phenopacket_count,
        MIN(created_at) as first_added
    FROM
        phenopackets,
        jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
    WHERE
        ext_ref->>'id' LIKE 'PMID:%'
    GROUP BY
        ext_ref->>'id',
        ext_ref->>'reference',
        ext_ref->>'description'
    ORDER BY
        phenopacket_count DESC, pmid
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    return [
        {
            "pmid": row.pmid.replace("PMID:", "") if row.pmid else None,  # type: ignore
            "url": row.url,  # type: ignore
            "doi": row.description.replace("DOI:", "")
            if row.description and row.description.startswith("DOI:")
            else None,  # type: ignore
            "phenopacket_count": row.phenopacket_count,  # type: ignore
            "first_added": row.first_added.isoformat() if row.first_added else None,  # type: ignore
        }
        for row in rows
    ]


@router.get("/aggregate/all-variants", response_model=List[Dict])
async def aggregate_all_variants(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    query: Optional[str] = Query(None, description="Search in HGVS notations, variant ID, or genomic coordinates"),
    variant_type: Optional[str] = Query(None, description="Filter by variant type (SNV, deletion, etc.)"),
    classification: Optional[str] = Query(None, description="Filter by ACMG classification"),
    gene: Optional[str] = Query(None, description="Filter by gene symbol"),
    consequence: Optional[str] = Query(None, description="Filter by molecular consequence"),
    pathogenicity: Optional[str] = Query(None, description="DEPRECATED: use 'classification' instead"),
    sort: Optional[str] = Query(None, description="Sort field with optional '-' prefix for descending"),
    db: AsyncSession = Depends(get_db),
):
    """Search and filter variants across all phenopackets.

    Aggregates variants from all phenopackets and returns unique variants
    with their details and the count of individuals carrying each variant.

    **Search Fields (8 total):**
    1. **Transcript (c. notation)**: e.g., "c.1654-2A>T"
    2. **Protein (p. notation)**: e.g., "p.Arg177Ter"
    3. **Variant ID**: e.g., "Var1", "ga4gh:VA.xxx"
    4. **HG38 Coordinates**: e.g., "chr17:36098063", "17:36459258-37832869"
    5. **Variant Type**: SNV, deletion, duplication, insertion, inversion, CNV
    6. **Classification**: PATHOGENIC, LIKELY_PATHOGENIC, etc.
    7. **Gene Symbol**: HNF1B
    8. **Molecular Consequence**: Frameshift, Nonsense, Missense, etc.

    Args:
        query: Text search across HGVS notations, variant IDs, and coordinates
        variant_type: Filter by variant structural type
        classification: Filter by ACMG pathogenicity classification
        gene: Filter by gene symbol (e.g., "HNF1B")
        consequence: Filter by molecular consequence (e.g., "Frameshift")
        limit: Maximum number of variants to return (default: 100, max: 1000)
        skip: Number of variants to skip for pagination (default: 0)
        sort: Sort field with optional '-' prefix for descending
            (e.g., 'simple_id', '-individualCount')
        pathogenicity: DEPRECATED - use 'classification' instead
        db: Database session

    Returns:
        List of unique variants with:
        - simple_id: User-friendly variant ID (e.g., "Var1")
        - variant_id: VRS ID or custom identifier
        - label: Human-readable variant description
        - gene_symbol: Gene symbol (e.g., "HNF1B")
        - gene_id: HGNC ID (e.g., "HGNC:5024")
        - structural_type: Variant type (e.g., "deletion", "SNV")
        - pathogenicity: ACMG classification
        - phenopacket_count: Number of individuals with this variant
        - hg38: Genomic coordinates or VCF string
        - transcript: HGVS c. notation
        - protein: HGVS p. notation
        - molecular_consequence: Computed molecular consequence

    Security:
        - All inputs validated with character whitelists
        - HGVS format validation
        - SQL injection prevention via parameterized queries
        - Length limits enforced (max 200 chars)

    Examples:
        # Search by HGVS notation
        GET /aggregate/all-variants?query=c.1654-2A>T

        # Search by genomic coordinates
        GET /aggregate/all-variants?query=chr17:36098063

        # Filter pathogenic deletions
        GET /aggregate/all-variants?variant_type=deletion&classification=PATHOGENIC

        # Search with molecular consequence filter
        GET /aggregate/all-variants?query=frameshift&consequence=Frameshift

        # Combined search and filters
        GET /aggregate/all-variants?query=HNF1B&variant_type=SNV&classification=PATHOGENIC
    """
    # Rate limiting (security layer)
    check_rate_limit(request)

    # Input validation (security layer)
    validated_query = validate_search_query(query)
    validated_variant_type = validate_variant_type(variant_type)
    validated_gene = validate_gene(gene)
    validated_consequence = validate_molecular_consequence(consequence)

    # Handle legacy 'pathogenicity' parameter (maintain backwards compatibility)
    classification_param = classification or pathogenicity
    validated_classification = validate_classification(classification_param)

    # Build query with optional filters
    where_clauses = []
    params = {"limit": limit, "offset": skip}

    # Text search: Search across HGVS notations, variant IDs, and coordinates
    if validated_query:
        where_clauses.append(
            """(
                vd->>'id' ILIKE :query
                OR vd->>'label' ILIKE :query
                OR vd->>'description' ILIKE :query
                OR EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') AS expr
                    WHERE expr->>'value' ILIKE :query
                )
                OR COALESCE(
                    NULLIF(CONCAT(
                        COALESCE(vd->'vcfRecord'->>'chrom', ''), ':',
                        COALESCE(vd->'vcfRecord'->>'pos', ''), ':',
                        COALESCE(vd->'vcfRecord'->>'ref', ''), ':',
                        COALESCE(vd->'vcfRecord'->>'alt', '')
                    ), ':::'),
                    ''
                ) ILIKE :query
            )"""
        )
        params["query"] = f"%{validated_query}%"

    # Variant type filter
    # Filter logic must match frontend display in getVariantType()
    if validated_variant_type:
        if validated_variant_type == "CNV":
            # CNVs: Large structural variants with coordinate range format
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'value' ~ ':\\d+-\\d+:'
                )"""
            )
        elif validated_variant_type == "deletion":
            # Small deletions: Has 'del' in c. notation but NOT a CNV
            where_clauses.append(
                """(
                    EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'syntax' = 'hgvs.c'
                        AND elem->>'value' ~ 'del'
                        AND elem->>'value' !~ 'dup'
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'value' ~ ':\\d+-\\d+:'
                    )
                )"""
            )
        elif validated_variant_type == "duplication":
            # Small duplications: Has 'dup' in c. notation but NOT a CNV
            where_clauses.append(
                """(
                    EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'syntax' = 'hgvs.c'
                        AND elem->>'value' ~ 'dup'
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'value' ~ ':\\d+-\\d+:'
                    )
                )"""
            )
        elif validated_variant_type == "insertion":
            # Insertions: Has 'ins' in c. notation but NOT a CNV
            where_clauses.append(
                """(
                    EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'syntax' = 'hgvs.c'
                        AND elem->>'value' ~ 'ins'
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'value' ~ ':\\d+-\\d+:'
                    )
                )"""
            )
        elif validated_variant_type == "SNV":
            # SNVs: Match genomic context but exclude deletions/insertions/duplications
            # True SNVs are substitutions (>) without del/ins/dup keywords
            where_clauses.append(
                """(
                    vd->>'moleculeContext' = 'genomic'
                    AND NOT EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(vd->'expressions') elem
                        WHERE elem->>'value' ~ 'del|ins|dup|delins'
                    )
                )"""
            )
        else:
            # Fallback for other types
            where_clauses.append(
                """COALESCE(
                    vd->'structuralType'->>'label',
                    CASE
                        WHEN vd->'vcfRecord'->>'alt' ~ '^<(DEL|DUP|INS|INV|CNV)' THEN 'CNV'
                        WHEN vd->>'moleculeContext' = 'genomic' THEN 'SNV'
                        ELSE 'OTHER'
                    END
                ) = :variant_type"""
            )
            params["variant_type"] = validated_variant_type

    # Classification filter
    if validated_classification:
        where_clauses.append(
            "vi->>'acmgPathogenicityClassification' = :classification"
        )
        params["classification"] = validated_classification

    # Gene filter
    if validated_gene:
        where_clauses.append(
            "vd->'geneContext'->>'symbol' = :gene"
        )
        params["gene"] = validated_gene

    # Molecular consequence filter (SQL-based for correct pagination)
    # Translate Python consequence logic to SQL WHERE clauses
    if validated_consequence:
        if validated_consequence == "Frameshift":
            # Protein notation contains 'fs' (frameshift)
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.p'
                    AND elem->>'value' ~* 'fs'
                )"""
            )
        elif validated_consequence == "Nonsense":
            # Protein notation contains 'Ter' or '*' (stop gained)
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.p'
                    AND (elem->>'value' ~* 'ter' OR elem->>'value' ~ '\\*')
                )"""
            )
        elif validated_consequence == "Missense":
            # Protein notation is amino acid substitution (e.g., p.Arg177Cys)
            # Pattern: three-letter amino acid, digits, three-letter amino acid
            # NOT containing 'Ter', 'fs', 'del', 'ins', or '='
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.p'
                    AND elem->>'value' ~ '[A-Z][a-z]{2}\\d+[A-Z][a-z]{2}'
                    AND elem->>'value' !~* 'ter|fs|del|ins|='
                )"""
            )
        elif validated_consequence == "Splice Donor":
            # Transcript notation with +1 to +6 (e.g., c.544+1G>T)
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.c'
                    AND elem->>'value' ~ '\\+[1-6]'
                )"""
            )
        elif validated_consequence == "Splice Acceptor":
            # Transcript notation with -1 to -3 (e.g., c.1654-2A>T)
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.c'
                    AND elem->>'value' ~ '-[1-3]'
                )"""
            )
        elif validated_consequence == "In-frame Deletion":
            # Protein notation contains 'del' but NOT 'fs' (frameshift)
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.p'
                    AND elem->>'value' ~* 'del'
                    AND elem->>'value' !~* 'fs'
                )"""
            )
        elif validated_consequence == "In-frame Insertion":
            # Protein notation contains 'ins' but NOT 'fs' (frameshift)
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.p'
                    AND elem->>'value' ~* 'ins'
                    AND elem->>'value' !~* 'fs'
                )"""
            )
        elif validated_consequence == "Synonymous":
            # Protein notation contains '=' (no amino acid change)
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.p'
                    AND elem->>'value' ~ '='
                )"""
            )
        elif validated_consequence == "Intronic Variant":
            # Transcript notation with +/- positions beyond splice sites
            where_clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' = 'hgvs.c'
                    AND (
                        elem->>'value' ~ '\\+[7-9]|\\+\\d{2,}'
                        OR elem->>'value' ~ '-[4-9]|-\\d{2,}'
                    )
                )"""
            )

    where_sql = "AND " + " AND ".join(where_clauses) if where_clauses else ""

    # Build ORDER BY clause from sort parameter
    # Map frontend field names to SQL column names
    sort_field_map = {
        "simple_id": "simple_id",
        "variant_id": "variant_id",
        "transcript": "transcript",
        "protein": "protein",
        "variant_type": "structural_type",
        "hg38": "hg38",
        "classificationVerdict": "pathogenicity",
        "individualCount": "phenopacket_count",
    }

    order_by = "phenopacket_count DESC, gene_symbol ASC"  # Default sort
    if sort:
        # Check if descending (starts with '-')
        if sort.startswith('-'):
            field_name = sort[1:]
            direction = "DESC"
        else:
            field_name = sort
            direction = "ASC"

        # Map field name to SQL column
        sql_column = sort_field_map.get(field_name)
        if sql_column:
            order_by = f"{sql_column} {direction}, gene_symbol ASC"

    query = f"""
    WITH all_variants_unfiltered AS (
        -- Extract ALL variants WITHOUT filters to establish stable IDs
        SELECT DISTINCT ON (vd->>'id', p.id)
            vd->>'id' as variant_id,
            vd->'geneContext'->>'symbol' as gene_symbol,
            p.id as phenopacket_id
        FROM
            phenopackets p,
            jsonb_array_elements(p.phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
            LATERAL (SELECT gi->'variantInterpretation' as vi) vi_lateral,
            LATERAL (SELECT vi_lateral.vi->'variationDescriptor' as vd) vd_lateral
        WHERE
            vi_lateral.vi IS NOT NULL
            AND vd_lateral.vd IS NOT NULL
    ),
    all_variants_agg AS (
        -- Aggregate all variants to count occurrences
        SELECT
            variant_id,
            MAX(gene_symbol) as gene_symbol,
            COUNT(DISTINCT phenopacket_id) as phenopacket_count
        FROM all_variants_unfiltered
        GROUP BY variant_id
    ),
    all_variants_with_stable_id AS (
        -- Assign stable IDs to ALL variants based on unfiltered dataset
        SELECT
            ROW_NUMBER() OVER (
                ORDER BY phenopacket_count DESC, gene_symbol ASC
            ) as simple_id,
            variant_id
        FROM all_variants_agg
    ),
    variant_raw AS (
        -- NOW apply filtering for the actual results
        SELECT DISTINCT ON (vd->>'id', p.id)
            vd->>'id' as variant_id,
            vd->>'label' as label,
            vd->'geneContext'->>'symbol' as gene_symbol,
            vd->'geneContext'->>'valueId' as gene_id,
            COALESCE(
                vd->'structuralType'->>'label',
                CASE
                    WHEN vd->'vcfRecord'->>'alt' ~ '^<(DEL|DUP|INS|INV|CNV)' THEN 'CNV'
                    WHEN vd->>'moleculeContext' = 'genomic' THEN 'SNV'
                    ELSE 'OTHER'
                END
            ) as structural_type,
            COALESCE(
                vi->>'acmgPathogenicityClassification',
                gi->>'interpretationStatus'
            ) as pathogenicity,
            COALESCE(
                NULLIF(CONCAT(
                    COALESCE(vd->'vcfRecord'->>'chrom', ''), ':',
                    COALESCE(vd->'vcfRecord'->>'pos', ''), ':',
                    COALESCE(vd->'vcfRecord'->>'ref', ''), ':',
                    COALESCE(vd->'vcfRecord'->>'alt', '')
                ), ':::'),
                (
                    SELECT elem->>'value'
                    FROM jsonb_array_elements(vd->'expressions') elem
                    WHERE elem->>'syntax' IN ('vcf', 'ga4gh', 'text')
                    LIMIT 1
                ),
                vd->>'description'
            ) as hg38,
            (
                SELECT elem->>'value'
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.c'
                LIMIT 1
            ) as transcript,
            (
                SELECT elem->>'value'
                FROM jsonb_array_elements(vd->'expressions') elem
                WHERE elem->>'syntax' = 'hgvs.p'
                LIMIT 1
            ) as protein,
            p.id as phenopacket_id
        FROM
            phenopackets p,
            jsonb_array_elements(p.phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
            LATERAL (SELECT gi->'variantInterpretation' as vi) vi_lateral,
            LATERAL (SELECT vi_lateral.vi->'variationDescriptor' as vd) vd_lateral
        WHERE
            vi_lateral.vi IS NOT NULL
            AND vd_lateral.vd IS NOT NULL
            {where_sql}
    ),
    variant_agg AS (
        -- Aggregate filtered variants
        SELECT
            variant_id,
            MAX(label) as label,
            MAX(gene_symbol) as gene_symbol,
            MAX(gene_id) as gene_id,
            MAX(structural_type) as structural_type,
            MAX(pathogenicity) as pathogenicity,
            MAX(hg38) as hg38,
            MAX(transcript) as transcript,
            MAX(protein) as protein,
            COUNT(DISTINCT phenopacket_id) as phenopacket_count
        FROM variant_raw
        GROUP BY variant_id
    ),
    variant_with_stable_id AS (
        -- Join filtered results with pre-calculated stable IDs
        SELECT
            avwsi.simple_id,  -- Stable ID from unfiltered dataset
            va.variant_id,
            va.label,
            va.gene_symbol,
            va.gene_id,
            va.structural_type,
            va.pathogenicity,
            va.phenopacket_count,
            va.hg38,
            va.transcript,
            va.protein
        FROM variant_agg va
        INNER JOIN all_variants_with_stable_id avwsi ON va.variant_id = avwsi.variant_id
    )
    SELECT *
    FROM variant_with_stable_id
    ORDER BY {order_by}
    LIMIT :limit
    OFFSET :offset
    """

    result = await db.execute(text(query), params)
    rows = result.fetchall()

    # simple_id is calculated using default sort order (by individual count)
    # This ensures each variant has a stable ID regardless of current sort
    variants = [
        {
            "simple_id": f"Var{row.simple_id}",  # type: ignore
            "variant_id": row.variant_id,  # type: ignore
            "label": row.label,  # type: ignore
            "gene_symbol": row.gene_symbol,  # type: ignore
            "gene_id": row.gene_id,  # type: ignore
            "structural_type": row.structural_type,  # type: ignore
            "pathogenicity": row.pathogenicity,  # type: ignore
            "phenopacket_count": row.phenopacket_count,  # type: ignore
            "hg38": row.hg38,  # type: ignore
            "transcript": row.transcript,  # type: ignore
            "protein": row.protein,  # type: ignore
            "molecular_consequence": compute_molecular_consequence(
                transcript=row.transcript,  # type: ignore
                protein=row.protein,  # type: ignore
                variant_type=row.structural_type  # type: ignore
            ),
        }
        for row in rows
    ]

    # Audit logging (GDPR compliance)
    log_variant_search(
        client_ip=get_client_ip(request),
        user_id=None,  # TODO: Get from auth when available
        query=validated_query,
        variant_type=validated_variant_type,
        classification=validated_classification,
        gene=validated_gene,
        consequence=validated_consequence,
        result_count=len(variants),
        request_path=str(request.url.path),
    )

    return variants


@router.get("/by-variant/{variant_id}", response_model=List[PhenopacketResponse])
async def get_phenopackets_by_variant(
    variant_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all phenopackets that contain a specific variant.

    Args:
        variant_id: The variant ID to search for

    Returns:
        List of phenopackets containing this variant
    """
    query = """
    SELECT DISTINCT p.*
    FROM phenopackets p,
         jsonb_array_elements(p.phenopacket->'interpretations') as interp,
         jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
    WHERE gi->'variantInterpretation'->'variationDescriptor'->>'id' = :variant_id
    ORDER BY p.created_at DESC
    """

    result = await db.execute(text(query), {"variant_id": variant_id})
    phenopackets = result.fetchall()

    return [
        PhenopacketResponse(
            id=str(pp.id),
            phenopacket_id=pp.phenopacket_id,
            version=pp.version,
            phenopacket=pp.phenopacket,
            created_at=pp.created_at,
            updated_at=pp.updated_at,
            schema_version=pp.schema_version,
        )
        for pp in phenopackets
    ]


@router.get("/aggregate/age-of-onset", response_model=List[AggregationResult])
async def aggregate_age_of_onset(
    db: AsyncSession = Depends(get_db),
):
    """Get distribution of age of disease onset."""
    query = """
    SELECT
        disease->'onset'->'ontologyClass'->>'label' as onset_label,
        disease->'onset'->'ontologyClass'->>'id' as onset_id,
        COUNT(*) as count
    FROM
        phenopackets,
        jsonb_array_elements(phenopacket->'diseases') as disease
    WHERE
        disease->'onset'->'ontologyClass'->>'label' IS NOT NULL
    GROUP BY
        disease->'onset'->'ontologyClass'->>'label',
        disease->'onset'->'ontologyClass'->>'id'
    ORDER BY
        count DESC
    """

    result = await db.execute(text(query))
    rows = result.fetchall()

    total = sum(row.count for row in rows)  # type: ignore

    return [
        AggregationResult(
            label=row.onset_label,  # type: ignore
            count=row.count,  # type: ignore
            percentage=(row.count / total * 100) if total > 0 else 0,  # type: ignore
            details={"hpo_id": row.onset_id},  # type: ignore
        )
        for row in rows
    ]


@router.get("/aggregate/summary", response_model=Dict[str, int])
async def get_summary_statistics(db: AsyncSession = Depends(get_db)):
    """Get lightweight summary statistics for home page.

    Returns:
        Dictionary with counts:
        - total_phenopackets: Total number of phenopackets
        - with_variants: Phenopackets containing interpretations
        - distinct_hpo_terms: Number of unique HPO terms used
        - distinct_publications: Number of unique publication references
        - distinct_variants: Number of unique genetic variants
        - male: Number of male subjects
        - female: Number of female subjects
        - unknown_sex: Number of subjects with unknown sex
    """
    # 1. Total phenopackets
    total_result = await db.execute(select(func.count()).select_from(Phenopacket))
    total_phenopackets = total_result.scalar()

    # 2. With variants (interpretations exist)
    with_variants_result = await db.execute(
        text("""
            SELECT COUNT(*)
            FROM phenopackets
            WHERE jsonb_array_length(phenopacket->'interpretations') > 0
        """)
    )
    with_variants = with_variants_result.scalar()

    # 3. Distinct HPO terms
    distinct_hpo_result = await db.execute(
        text("""
            SELECT COUNT(DISTINCT feature->'type'->>'id')
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature
            WHERE feature->'type'->>'id' IS NOT NULL
        """)
    )
    distinct_hpo_terms = distinct_hpo_result.scalar() or 0

    # 4. Distinct publications
    distinct_publications_result = await db.execute(
        text("""
            SELECT COUNT(DISTINCT ext_ref->>'id')
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
            WHERE ext_ref->>'id' LIKE 'PMID:%'
        """)
    )
    distinct_publications = distinct_publications_result.scalar() or 0

    # 5. Distinct variants (unique variants across all phenopackets)
    distinct_variants_result = await db.execute(
        text("""
            SELECT COUNT(DISTINCT vd->>'id')
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                 jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
                 LATERAL (
                     SELECT gi->'variantInterpretation'->'variationDescriptor' as vd
                 ) vd_lateral
            WHERE vd_lateral.vd IS NOT NULL
              AND vd_lateral.vd->>'id' IS NOT NULL
        """)
    )
    distinct_variants = distinct_variants_result.scalar() or 0

    # 6. Sex distribution
    sex_distribution_result = await db.execute(
        text("""
            SELECT
                subject_sex,
                COUNT(*) as count
            FROM phenopackets
            GROUP BY subject_sex
        """)
    )
    sex_rows = sex_distribution_result.fetchall()

    # Parse sex distribution
    male = 0
    female = 0
    unknown_sex = 0
    for row in sex_rows:
        if row.subject_sex == "MALE":  # type: ignore
            male = row.count  # type: ignore
        elif row.subject_sex == "FEMALE":  # type: ignore
            female = row.count  # type: ignore
        else:
            unknown_sex += row.count  # type: ignore

    return {
        "total_phenopackets": total_phenopackets,
        "with_variants": with_variants,
        "distinct_hpo_terms": distinct_hpo_terms,
        "distinct_publications": distinct_publications,
        "distinct_variants": distinct_variants,
        "male": male,
        "female": female,
        "unknown_sex": unknown_sex,
    }
