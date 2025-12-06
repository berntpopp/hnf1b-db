"""HPO Proxy endpoints to handle CORS and caching for frontend.

Proxies requests to the OLS API for HPO term search and autocomplete.
Uses Redis for distributed caching (with in-memory fallback).
Configuration is loaded from config.yaml via app.core.config.
"""

import logging
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.cache import cache
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/hpo", tags=["hpo"])


class HPOTerm(BaseModel):
    """HPO term model."""

    id: str
    name: str
    definition: Optional[str] = None
    comment: Optional[str] = None
    synonyms: Optional[List[str]] = None
    xrefs: Optional[List[str]] = None


@router.get("/search")
async def search_hpo_terms(
    q: str = Query(..., min_length=2, description="Search query"),
    max_results: int = Query(20, ge=1, le=100, description="Maximum results"),
):
    """Proxy search requests to HPO JAX API.

    This endpoint forwards search queries to the official HPO API
    and returns results, handling any CORS issues that might arise
    when the frontend tries to call the HPO API directly.

    Args:
        q: Search query (minimum 2 characters)
        max_results: Maximum number of results to return

    Returns:
        Search results from HPO JAX API
    """
    # Check cache first (Redis with fallback)
    cache_key = f"hpo:search:{q}:{max_results}"
    cached = await cache.get_json(cache_key)
    if cached:
        logger.info(f"Cache hit for HPO search: {q}")
        return cached

    # Get config values
    ols_base = settings.external_apis.ols.base_url
    ols_timeout = settings.external_apis.ols.timeout_seconds
    cache_ttl = settings.external_apis.ols.cache_ttl_seconds

    try:
        async with httpx.AsyncClient(timeout=ols_timeout) as client:
            # Using OLS API for HPO term search
            response = await client.get(
                f"{ols_base}/search",
                params={
                    "q": q,
                    "ontology": "hp",
                    "rows": max_results,
                    "local": "true",
                    "fieldList": "id,label,description,synonym",
                },
            )
            response.raise_for_status()
            data = response.json()

            # Transform OLS response to match expected format
            if "response" in data and "docs" in data["response"]:
                terms = []
                for doc in data["response"]["docs"]:
                    # Only include actual HPO terms (starting with HP)
                    obo_id = doc.get("obo_id", "")
                    if obo_id.startswith("HP:"):
                        terms.append(
                            {
                                "id": obo_id,
                                "name": doc.get("label", ""),
                                "definition": doc.get("description", [""])[0]
                                if doc.get("description")
                                else "",
                                "synonyms": doc.get("synonym", []),
                            }
                        )
                data = {"terms": terms}

            # Cache the result in Redis (with TTL for automatic expiration)
            await cache.set_json(cache_key, data, ttl=cache_ttl)

            return data

    except httpx.TimeoutException as e:
        raise HTTPException(status_code=504, detail="HPO API request timed out") from e
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"HPO API error: {e.response.text}",
        ) from e
    except Exception as e:
        logger.error(f"Error proxying HPO search: {e}")
        raise HTTPException(status_code=500, detail="Error searching HPO terms") from e


@router.get("/term/{term_id}")
async def get_hpo_term(term_id: str):
    """Get details for a specific HPO term.

    Args:
        term_id: HPO term ID (e.g., "HP:0001234" or "HP_0001234")

    Returns:
        Detailed information about the HPO term
    """
    # Normalize term ID format
    term_id = term_id.replace("_", ":")

    # Get config values
    ols_base = settings.external_apis.ols.base_url
    ols_timeout = settings.external_apis.ols.timeout_seconds

    try:
        async with httpx.AsyncClient(timeout=ols_timeout) as client:
            # Using OLS API to get term details
            response = await client.get(
                f"{ols_base}/ontologies/hp/terms",
                params={
                    "iri": f"http://purl.obolibrary.org/obo/{term_id.replace(':', '_')}"
                },
            )
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=404, detail=f"HPO term {term_id} not found"
            ) from e
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"HPO API error: {e.response.text}",
        ) from e
    except Exception as e:
        logger.error(f"Error fetching HPO term {term_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching HPO term") from e


@router.get("/autocomplete")
async def autocomplete_hpo_terms(
    q: str = Query(..., min_length=2, description="Partial term to complete"),
    limit: int = Query(10, ge=1, le=50, description="Maximum suggestions"),
):
    """Autocomplete endpoint optimized for frontend typeahead/dropdown.

    Returns a simplified list of terms suitable for dropdown displays.

    Args:
        q: Partial search term
        limit: Maximum number of suggestions

    Returns:
        List of HPO terms with ID and name
    """
    # Get config values
    ols_base = settings.external_apis.ols.base_url
    ols_timeout = settings.external_apis.ols.timeout_seconds

    try:
        async with httpx.AsyncClient(timeout=ols_timeout) as client:
            response = await client.get(
                f"{ols_base}/search",
                params={"q": q, "ontology": "hp", "rows": limit, "local": "true"},
            )
            response.raise_for_status()
            data = response.json()

            # Transform OLS response for autocomplete
            if "response" in data and "docs" in data["response"]:
                results = []
                for doc in data["response"]["docs"]:
                    obo_id = doc.get("obo_id", "")
                    if obo_id.startswith("HP:"):
                        results.append(
                            {
                                "id": obo_id,
                                "label": doc.get("label", ""),
                                "definition": (
                                    doc.get("description", [""])[0][:200]
                                    if doc.get("description")
                                    else ""
                                ),
                            }
                        )
                return results
            return []

    except Exception as e:
        logger.error(f"Error in HPO autocomplete: {e}")
        # Return empty list on error to not break frontend autocomplete
        return []


@router.get("/common-terms")
async def get_common_hpo_terms(
    category: Optional[str] = Query(
        None, description="Category filter: renal, metabolic, developmental"
    ),
):
    """Get commonly used HPO terms for HNF1B-related conditions.

    This endpoint returns a curated list of frequently used HPO terms
    to help users quickly select relevant phenotypes.

    Args:
        category: Optional category filter

    Returns:
        List of common HPO terms
    """
    # Common HPO terms for HNF1B
    common_terms = {
        "renal": [
            {"id": "HP:0000083", "label": "Renal insufficiency"},
            {"id": "HP:0000107", "label": "Renal cyst"},
            {"id": "HP:0012622", "label": "Chronic kidney disease"},
            {"id": "HP:0000089", "label": "Renal hypoplasia"},
            {"id": "HP:0100611", "label": "Multiple glomerular cysts"},
        ],
        "metabolic": [
            {"id": "HP:0000819", "label": "Diabetes mellitus"},
            {"id": "HP:0002917", "label": "Hypomagnesemia"},
            {"id": "HP:0002149", "label": "Hyperuricemia"},
            {"id": "HP:0001997", "label": "Gout"},
            {"id": "HP:0004904", "label": "Maturity-onset diabetes of the young"},
        ],
        "developmental": [
            {"id": "HP:0000078", "label": "Genital abnormality"},
            {"id": "HP:0001737", "label": "Pancreatic cysts"},
            {"id": "HP:0001738", "label": "Exocrine pancreatic insufficiency"},
            {"id": "HP:0001732", "label": "Abnormality of the pancreas"},
        ],
    }

    if category and category in common_terms:
        return common_terms[category]

    # Return all common terms if no category specified
    all_terms = []
    for terms in common_terms.values():
        all_terms.extend(terms)
    return all_terms


@router.get("/validate")
async def validate_hpo_terms(
    term_ids: str = Query(..., description="Comma-separated list of HPO term IDs"),
):
    """Validate a list of HPO term IDs.

    Useful for validating user input before submission.
    Uses local ontology service for fast validation (no N+1 API calls).

    Args:
        term_ids: Comma-separated HPO term IDs (e.g., "HP:0001234,HP:0005678")

    Returns:
        Validation results for each term

    Performance:
        - Uses local ontology mappings (instant validation)
        - Falls back to cached API results
        - Avoids N+1 external API calls
    """
    from app.services.ontology_service import ontology_service

    ids = [id.strip() for id in term_ids.split(",")]
    results = {}

    # Use local ontology service instead of N API calls
    for term_id in ids:
        try:
            # get_term uses local mappings + cache (fast!)
            term = ontology_service.get_term(term_id)
            if term:
                results[term_id] = {
                    "valid": True,
                    "name": term.label,
                    "source": term.source.value,
                }
            else:
                results[term_id] = {
                    "valid": False,
                    "error": "Term not found in local ontology or APIs",
                }
        except Exception as e:
            results[term_id] = {"valid": False, "error": str(e)}

    return results
