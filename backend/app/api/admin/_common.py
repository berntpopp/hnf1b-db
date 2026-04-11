"""Shared helpers for the admin route modules.

Small internal utilities lifted out of ``endpoints.py`` so the
domain-specific route files (``status``, ``sync_publications``,
``sync_variants``, ``sync_reference``) can share response-building
logic without a circular import.
"""

from __future__ import annotations

from app.api.admin.schemas import SyncProgressResponse
from app.api.admin.task_state import SyncTaskState, TaskStatus


def progress_response_from_state(state: SyncTaskState) -> SyncProgressResponse:
    """Build a ``SyncProgressResponse`` from a ``SyncTaskState`` snapshot."""
    return SyncProgressResponse(
        task_id=state.task_id,
        status=state.status.value
        if isinstance(state.status, TaskStatus)
        else state.status,
        progress=state.progress,
        processed=state.processed,
        total=state.total,
        errors=state.errors,
        started_at=state.started_at,
        completed_at=state.completed_at,
    )


def idle_progress_response(
    synced: int, total: int, task_id: str = "none"
) -> SyncProgressResponse:
    """Build the "no active task" progress response.

    Mirrors the old admin_endpoints.py idle branches: status "idle",
    progress derived from the DB view, empty timestamps.
    """
    if total and total == synced:
        progress = 100.0
    elif total > 0:
        progress = synced / total * 100
    else:
        progress = 0.0
    return SyncProgressResponse(
        task_id=task_id,
        status="idle",
        progress=progress,
        processed=synced or 0,
        total=total or 0,
        errors=0,
        started_at=None,
        completed_at=None,
    )
