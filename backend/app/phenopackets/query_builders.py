"""Query builder utilities for phenopacket queries.

Eliminates duplicate SQL query patterns across endpoints by providing
reusable functions for common filtering and transformation operations.

This module follows the DRY (Don't Repeat Yourself) principle by extracting
repeated query logic from endpoints.py into focused, testable functions.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.sql import Select

from app.phenopackets.models import Phenopacket, PhenopacketResponse


def add_has_variants_filter(query: Select, has_variants: Optional[bool]) -> Select:
    """Add filter for phenopackets with/without variants.

    Used in: list_phenopackets, search_phenopackets

    Args:
        query: SQLAlchemy select query object
        has_variants: True (has variants), False (no variants), None (all)

    Returns:
        Modified query object with filter applied

    Example:
        query = select(Phenopacket)
        query = add_has_variants_filter(query, has_variants=True)
        # Returns only phenopackets with interpretations array length > 0
    """
    if has_variants is None:
        return query

    if has_variants:
        return query.where(
            func.jsonb_array_length(Phenopacket.phenopacket["interpretations"]) > 0
        )

    return query.where(
        func.coalesce(
            func.jsonb_array_length(Phenopacket.phenopacket["interpretations"]), 0
        )
        == 0
    )


def add_sex_filter(query: Select, sex: Optional[str]) -> Select:
    """Add sex filter to query using generated column.

    Used in: list_phenopackets, search_phenopackets, aggregate endpoints

    Args:
        query: SQLAlchemy select query object
        sex: 'MALE', 'FEMALE', 'OTHER_SEX', 'UNKNOWN_SEX', or None

    Returns:
        Modified query object with sex filter applied

    Example:
        query = select(Phenopacket)
        query = add_sex_filter(query, sex='MALE')
        # Uses optimized generated column: subject_sex
    """
    if sex:
        return query.where(Phenopacket.subject_sex == sex)
    return query


def build_phenopacket_response(
    pp: Phenopacket,
    *,
    phenopacket_override: Optional[Dict[str, Any]] = None,
    include_state: bool = True,
) -> PhenopacketResponse:
    """Transform database model to response model.

    Used in: All CRUD endpoints (list, get, create, update, batch)

    This function encapsulates the repetitive pattern of creating PhenopacketResponse
    objects from Phenopacket database models. It ensures consistent response structure
    across all endpoints.

    Resolves the ``created_by`` / ``updated_by`` username strings from
    the eager-loaded audit-actor relationships (``created_by_user`` /
    ``updated_by_user``). The repository is responsible for attaching
    the ``selectinload`` options; reading the attribute here would
    otherwise trip ``lazy='raise'``.

    Args:
        pp: Phenopacket database model instance
        phenopacket_override: If provided, use this dict as the ``phenopacket``
            field instead of ``pp.phenopacket``.  Used by the public read path
            to substitute the head-published revision content while leaving the
            ORM row (and its working copy) untouched.
        include_state: When ``False`` the Wave 7 D.1 state-machine fields
            (``state``, ``editing_revision_id``, ``head_published_revision_id``,
            ``draft_owner_id``, ``draft_owner_username``) are set to ``None``
            in the response, hiding internal workflow metadata from non-curator
            callers (spec §7.2).

    Returns:
        PhenopacketResponse Pydantic model for API response

    Example:
        phenopacket = await db.get(Phenopacket, phenopacket_id)
        return build_phenopacket_response(phenopacket)
    """
    created_by = pp.created_by_user.username if pp.created_by_user else None
    updated_by = pp.updated_by_user.username if pp.updated_by_user else None
    content = (
        phenopacket_override if phenopacket_override is not None else pp.phenopacket
    )

    draft_owner_username: Optional[str] = None
    if include_state and pp.draft_owner is not None:
        draft_owner_username = pp.draft_owner.username

    # D.2 effective state (spec §4.2.4): in-flight revision's state
    # takes precedence over pp.state when an edit is in progress.
    effective_state_value = None
    if include_state:
        effective_state_value = (
            pp.editing_revision.state
            if pp.editing_revision_id is not None and pp.editing_revision is not None
            else pp.state
        )

    return PhenopacketResponse(
        id=str(pp.id),
        phenopacket_id=pp.phenopacket_id,
        version=pp.version,
        revision=pp.revision,
        phenopacket=content,
        created_at=pp.created_at,
        updated_at=pp.updated_at,
        schema_version=pp.schema_version,
        created_by=created_by,
        updated_by=updated_by,
        # Wave 7 D.1 state-machine fields (hidden from non-curators)
        state=pp.state if include_state else None,
        head_published_revision_id=(
            pp.head_published_revision_id if include_state else None
        ),
        editing_revision_id=pp.editing_revision_id if include_state else None,
        draft_owner_id=pp.draft_owner_id if include_state else None,
        draft_owner_username=draft_owner_username if include_state else None,
        effective_state=effective_state_value,
    )


def add_classification_filter(
    where_clauses: List[str], params: Dict, classification: Optional[str]
) -> None:
    """Add variant classification filter to WHERE clauses.

    Used in: get_variants, search_phenopackets, aggregate_all_variants

    This modifies the where_clauses list in-place and adds the classification
    parameter to the params dict for safe SQL parameter binding.

    Args:
        where_clauses: List of SQL WHERE conditions (modified in-place)
        params: Query parameters dict (modified in-place)
        classification: ACMG classification (e.g., 'PATHOGENIC', 'LIKELY_PATHOGENIC')

    Example:
        where_clauses = []
        params = {}
        add_classification_filter(where_clauses, params, 'PATHOGENIC')
        # where_clauses = ["gi->>'interpretationStatus' = :classification"]
        # params = {"classification": "PATHOGENIC"}
    """
    if classification:
        where_clauses.append("gi->>'interpretationStatus' = :classification")
        params["classification"] = classification


def build_variant_query_filters(
    variant_type: Optional[str] = None,
    classification: Optional[str] = None,
    consequence: Optional[str] = None,
    query: Optional[str] = None,
) -> tuple[List[str], Dict]:
    """Build WHERE clauses and params for variant filtering.

    Used in: get_variants, aggregate_all_variants, search endpoints

    This function consolidates all variant-related filtering logic into a single
    reusable function, eliminating code duplication across multiple endpoints.

    Args:
        variant_type: Variant type filter (e.g., 'SNV', 'deletion', 'CNV')
        classification: ACMG classification filter
        consequence: Molecular consequence filter (e.g., 'Nonsense', 'Missense')
        query: Text search query for HGVS notation, gene symbols, etc.

    Returns:
        Tuple of (where_clauses, params) for SQL query construction

    Example:
        where_clauses, params = build_variant_query_filters(
            variant_type='SNV',
            classification='PATHOGENIC',
            query='p.Arg177'
        )
        # Returns WHERE clauses and safe parameters for SQL execution
    """
    where_clauses = []
    params = {}

    if variant_type:
        where_clauses.append("v->>'structuralType' = :variant_type")
        params["variant_type"] = variant_type

    if classification:
        where_clauses.append("gi->>'interpretationStatus' = :classification")
        params["classification"] = classification

    if consequence:
        where_clauses.append(
            "v->'molecularConsequence'->0->'term'->>'label' = :consequence"
        )
        params["consequence"] = consequence

    if query:
        # Add HGVS search conditions for transcript, protein, genomic, label
        search_conditions = [
            "v->>'transcript' ILIKE :query",
            "v->>'protein' ILIKE :query",
            "v->>'hg38' ILIKE :query",
            "v->>'label' ILIKE :query",
        ]
        where_clauses.append(f"({' OR '.join(search_conditions)})")
        params["query"] = f"%{query}%"

    return where_clauses, params
