"""Aggregation endpoints package for phenopackets.

This package provides modular aggregation endpoints organized by domain:
- summary: Home page statistics
- features: HPO term aggregations
- diseases: Disease and kidney stage aggregations
- demographics: Sex distribution and age of onset
- variants: Variant pathogenicity and type aggregations
- publications: Publication statistics and timeline
- all_variants: Comprehensive variant search with filtering
- survival: Kaplan-Meier survival analysis

Usage:
    from app.phenopackets.routers.aggregations import router
"""

from fastapi import APIRouter

# Import sub-routers from modular files
from .all_variants import router as all_variants_router
from .demographics import router as demographics_router
from .diseases import router as diseases_router
from .features import router as features_router
from .publications import router as publications_router
from .summary import router as summary_router
from .survival import router as survival_router
from .variants import router as variants_router

# Create main router with common configuration
router = APIRouter(prefix="/aggregate", tags=["phenopackets-aggregations"])

# Include all modular sub-routers
router.include_router(summary_router)
router.include_router(features_router)
router.include_router(diseases_router)
router.include_router(demographics_router)
router.include_router(variants_router)
router.include_router(publications_router)
router.include_router(all_variants_router)
router.include_router(survival_router)

# Export the router for external use
__all__ = ["router"]
