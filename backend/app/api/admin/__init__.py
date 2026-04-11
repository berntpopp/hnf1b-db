"""Admin API sub-package.

Split from the old flat ``app/api/admin_endpoints.py`` during Wave 4.
Organised as:

- ``schemas``       — Pydantic request/response models
- ``queries``       — raw SQL helper queries (DB statistics, sync views)
- ``task_state``    — cache-backed sync task state (replaces the old
  in-memory ``_sync_tasks`` dict flagged in the 2026-04-09 review as
  unsafe for multi-worker deployments)
- ``sync_service``  — background-task orchestration for pub/variant/ref syncs
- ``endpoints``     — thin FastAPI router delegating to the services above

Public re-export::

    from app.api.admin import router
"""

from .endpoints import router

__all__ = ["router"]
