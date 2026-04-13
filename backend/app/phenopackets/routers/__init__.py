"""Phenopackets API routers.

Split from monolithic endpoints.py for better maintainability and
organization. Each router focuses on a specific domain of functionality.

Routers:
- crud          : Basic CRUD operations (list, get, create, update, delete)
- crud_related  : Related lookups (/audit, /by-variant, /by-publication)
- crud_timeline : Phenotype timeline view
- aggregations  : Statistical aggregations and summaries
- comparisons   : Statistical comparisons between variant type groups
- search        : Search and filtering operations
"""

from fastapi import APIRouter

from .aggregations import router as aggregations_router
from .comparisons import router as comparisons_router
from .crud import router as crud_router
from .crud_related import router as crud_related_router
from .crud_timeline import router as crud_timeline_router
from .search import router as search_router
from .transitions import router as transitions_router

# Combine all routers under /api/v2/phenopackets prefix
router = APIRouter(prefix="/phenopackets")

# Include routers. Search is included first to keep its /search path
# registered before crud_router's catch-all /{phenopacket_id} route.
# crud_related and crud_timeline also need to be registered before
# crud_router's /{phenopacket_id} so their more specific /{id}/audit
# and /{id}/timeline paths are reached first.
# transitions_router must also precede crud_router so that
# /{phenopacket_id}/transitions and /{phenopacket_id}/revisions are
# matched before the catch-all /{phenopacket_id} GET.
router.include_router(search_router)
router.include_router(crud_related_router)
router.include_router(crud_timeline_router)
router.include_router(transitions_router)
router.include_router(crud_router)
router.include_router(aggregations_router)
router.include_router(comparisons_router)

__all__ = ["router"]
