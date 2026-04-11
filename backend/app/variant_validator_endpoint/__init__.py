"""Variant validator endpoints sub-package.

Split from the old 702-LOC flat ``variant_validator_endpoint.py`` during
Wave 4. Exposes a single aggregated ``router`` mounted at
``/api/v2/variants`` by ``app.main``.

Routes, grouped by file:

- ``validate_route``  → ``POST /validate``
- ``annotate_route``  → ``POST /annotate``
- ``recode_route``    → ``POST /recode``, ``POST /recode/batch``
- ``suggest_route``   → ``GET /suggest/{partial_notation}``

The HTTP surface is byte-identical to the pre-Wave-4 flat module;
``app.main`` still does::

    from app import variant_validator_endpoint
    app.include_router(variant_validator_endpoint.router)
"""

from fastapi import APIRouter

from .annotate_route import router as _annotate_router
from .recode_route import router as _recode_router
from .suggest_route import router as _suggest_router
from .validate_route import router as _validate_router

router = APIRouter(prefix="/api/v2/variants", tags=["variant-validation"])
router.include_router(_validate_router)
router.include_router(_annotate_router)
router.include_router(_recode_router)
router.include_router(_suggest_router)

__all__ = ["router"]
