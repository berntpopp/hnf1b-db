"""Publications endpoints sub-package.

Split from the old 690-LOC flat ``publications/endpoints.py`` during
Wave 4. Exposes a single aggregated ``router`` mounted at
``/api/v2/publications`` by ``app.main``.

Routes, grouped by file:

- ``metadata_route``  → ``GET /{pmid}/metadata``
- ``list_route``      → ``GET /``
- ``sync_route``      → ``POST /sync``

The HTTP surface is byte-identical to the pre-Wave-4 flat module;
``app.main`` continues to call
``app.include_router(publication_endpoints.router)`` unchanged.
"""

from fastapi import APIRouter

from .list_route import router as _list_router
from .metadata_route import router as _metadata_router
from .sync_route import router as _sync_router

router = APIRouter(prefix="/api/v2/publications", tags=["publications"])
router.include_router(_list_router)
router.include_router(_metadata_router)
router.include_router(_sync_router)

__all__ = ["router"]
