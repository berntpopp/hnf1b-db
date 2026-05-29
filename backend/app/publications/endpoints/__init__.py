"""Publications endpoints sub-package.

Split from the old 690-LOC flat ``publications/endpoints.py`` during
Wave 4. Exposes a single aggregated ``router`` mounted at
``/api/v2/publications`` by ``app.main``.

Routes, grouped by file:

- ``list_route``      → ``GET /``
- ``passages_route``  → ``GET /passages``
- ``metadata_route``  → ``GET /{pmid}/metadata``
- ``sync_route``      → ``POST /sync``

``passages_route`` is included before ``metadata_route`` so the literal
``/passages`` path is matched ahead of the ``/{pmid}/metadata`` template.
"""

from fastapi import APIRouter

from .list_route import router as _list_router
from .metadata_route import router as _metadata_router
from .passages_route import router as _passages_router
from .sync_route import router as _sync_router

router = APIRouter(prefix="/api/v2/publications", tags=["publications"])
router.include_router(_list_router)
router.include_router(_passages_router)
router.include_router(_metadata_router)
router.include_router(_sync_router)

__all__ = ["router"]
