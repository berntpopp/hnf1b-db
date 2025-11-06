"""Phenopackets API routers.

Split from monolithic endpoints.py for better maintainability and organization.
Each router focuses on a specific domain of functionality.

Routers:
- crud: Basic CRUD operations (list, get, create, update, delete)
- aggregations: Statistical aggregations and summaries
- search: Search and filtering operations
- variants: Variant-related queries
- features: Phenotypic features, diseases, and measurements
"""

from fastapi import APIRouter

# Import will be added as routers are created
# from .crud import router as crud_router
# from .aggregations import router as aggregations_router
# from .search import router as search_router
# from .variants import router as variants_router
# from .features import router as features_router

# Combine all routers under /api/v2/phenopackets prefix
router = APIRouter()

# Routers will be included as they are created
# router.include_router(crud_router)
# router.include_router(aggregations_router)
# router.include_router(search_router)
# router.include_router(variants_router)
# router.include_router(features_router)

__all__ = ["router"]
