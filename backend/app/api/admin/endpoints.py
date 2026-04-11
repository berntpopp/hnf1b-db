"""Admin API aggregator router.

This module is the entry point for the admin sub-package: it creates a
single ``APIRouter`` mounted at ``/api/v2/admin`` and includes every
domain-specific sub-router (status, sync_publications, sync_variants,
sync_reference). Each sub-router owns its own HTTP logic — this file
is pure composition.

The HTTP surface is byte-identical to the old flat
``app/api/admin_endpoints.py``: routes, response shapes, query params,
and status codes are all preserved. The Wave 4 HTTP surface baseline
in ``tests/fixtures/wave4_http_baselines/admin_status.json`` locks
this in automatically.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.admin.status_routes import router as _status_router
from app.api.admin.sync_publications_routes import router as _pub_router
from app.api.admin.sync_reference_routes import router as _ref_router
from app.api.admin.sync_variants_routes import router as _var_router

router = APIRouter(prefix="/api/v2/admin", tags=["admin"])

# Sub-routers are included without extra prefixes so the final path
# shape matches the old flat file exactly:
#   /api/v2/admin/status
#   /api/v2/admin/statistics
#   /api/v2/admin/reference/status
#   /api/v2/admin/sync/publications
#   /api/v2/admin/sync/publications/status
#   /api/v2/admin/sync/variants
#   /api/v2/admin/sync/variants/status
#   /api/v2/admin/sync/reference/init
#   /api/v2/admin/sync/genes
#   /api/v2/admin/sync/genes/status
router.include_router(_status_router)
router.include_router(_pub_router)
router.include_router(_var_router)
router.include_router(_ref_router)
