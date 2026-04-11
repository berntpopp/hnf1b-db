"""Survival analysis endpoint for phenopackets.

Thin FastAPI router that dispatches to the SurvivalHandlerFactory in
the sibling ``handlers`` module. All concrete Kaplan-Meier, log-rank,
and SQL logic lives in the handler classes — this file is
intentionally kept small so the routing and endpoint configuration
concerns stay in one place.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import get_db

router = APIRouter()


# HPO terms now loaded from configuration (settings.hpo_terms)
# Access via: settings.hpo_terms.cakut, settings.hpo_terms.genital, etc.


def _get_endpoint_config() -> Dict[str, Dict[str, Any]]:
    """Get endpoint configuration using HPO terms from settings.

    Returns dynamically constructed config using centralized HPO terms,
    enabling configuration changes without code modifications.
    """
    return {
        "ckd_stage_3_plus": {
            "hpo_terms": settings.hpo_terms.ckd_stage_3_plus,
            "label": "CKD Stage 3+ (GFR <60)",
        },
        "stage_5_ckd": {
            "hpo_terms": settings.hpo_terms.stage_5_ckd,
            "label": "Stage 5 CKD (ESRD)",
        },
        "any_ckd": {
            "hpo_terms": settings.hpo_terms.ckd_stages,
            "label": "Any CKD",
        },
        "current_age": {
            "hpo_terms": None,  # Special case: use current age
            "label": "Age at Last Follow-up",
        },
    }


@router.get("/survival-data", response_model=Dict[str, Any])
async def get_survival_data(
    comparison: str = Query(
        ...,
        description=(
            "Comparison type: variant_type, pathogenicity, "
            "disease_subtype, or protein_domain"
        ),
    ),
    endpoint: str = Query(
        "ckd_stage_3_plus",
        description=(
            "Clinical endpoint: ckd_stage_3_plus (default), "
            "stage_5_ckd, any_ckd, current_age"
        ),
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get Kaplan-Meier survival data with configurable clinical endpoints.

    Compares survival curves using different grouping strategies:
    - variant_type: CNV vs Truncating vs Non-truncating
    - disease_subtype: CAKUT vs CAKUT+MODY vs MODY
    - pathogenicity: P/LP vs VUS vs LB
    - protein_domain: POU-S vs POU-H vs TAD vs Other (missense only)

    Supports multiple clinical endpoints:
    - ckd_stage_3_plus: CKD Stage 3+ (GFR <60)
    - stage_5_ckd: Stage 5 CKD (ESRD)
    - any_ckd: Any CKD diagnosis
    - current_age: Age at last follow-up (universal endpoint)

    Returns:
        Survival curves with Kaplan-Meier estimates, 95% CIs, and log-rank tests
    """
    from .handlers import SurvivalHandlerFactory

    endpoint_config = _get_endpoint_config()
    if endpoint not in endpoint_config:
        valid_options = ", ".join(endpoint_config.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown endpoint: {endpoint}. Valid options: {valid_options}",
        )

    config = endpoint_config[endpoint]
    endpoint_hpo_terms: Optional[List[str]] = config["hpo_terms"]
    endpoint_label: str = config["label"]

    # Use factory to get appropriate handler for comparison type
    try:
        handler = SurvivalHandlerFactory.get_handler(comparison)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return await handler.handle(db, endpoint_label, endpoint_hpo_terms)
