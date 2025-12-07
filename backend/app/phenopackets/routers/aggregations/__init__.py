"""Aggregation endpoints package for phenopackets.

This package provides modular aggregation endpoints organized by domain:
- summary: Home page statistics
- features: HPO term aggregations
- diseases: Disease and kidney stage aggregations
- demographics: Sex distribution and age of onset
- variants: Variant pathogenicity and type aggregations
- publications: Publication statistics and timeline

Complex endpoints (all-variants, survival-data) are imported from _legacy.py
until they are refactored into separate modules.

Usage:
    from app.phenopackets.routers.aggregations import router
"""

from fastapi import APIRouter

# Import sub-routers from modular files
from .demographics import router as demographics_router
from .diseases import router as diseases_router
from .features import router as features_router
from .publications import router as publications_router
from .summary import router as summary_router
from .variants import router as variants_router

# Import complex endpoints from legacy file
# These will be extracted to separate modules in future refactoring
from ._legacy import (
    aggregate_all_variants,
    get_survival_data,
)

# Create main router with common configuration
router = APIRouter(prefix="/aggregate", tags=["phenopackets-aggregations"])

# Include all modular sub-routers
router.include_router(summary_router)
router.include_router(features_router)
router.include_router(diseases_router)
router.include_router(demographics_router)
router.include_router(variants_router)
router.include_router(publications_router)

# Register complex endpoints from legacy file directly on the router
# These maintain their original routes: /all-variants, /survival-data
router.add_api_route(
    "/all-variants",
    aggregate_all_variants,
    methods=["GET"],
    name="aggregate_all_variants",
)
router.add_api_route(
    "/survival-data",
    get_survival_data,
    methods=["GET"],
    name="get_survival_data",
)

# Export the router for external use
__all__ = ["router"]
