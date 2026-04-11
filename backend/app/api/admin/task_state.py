"""Cache-backed sync task state for admin operations.

Replaces the process-local ``_sync_tasks`` dict from the old flat
``app/api/admin_endpoints.py`` — flagged in the 2026-04-09 codebase
review as unsafe for multi-worker deployments because the dict lives
in one worker's memory and is invisible to the others.

This module persists task state through the existing
``app.core.cache.cache`` global ``CacheService``. That service
transparently falls through to Redis when available and an in-memory
LRU otherwise (see ``CacheService.connect``), so the task store keeps
working in unit tests without a Redis daemon running.

Key layout
----------

- ``admin:sync_task:{task_id}``     — JSON-encoded ``SyncTaskState``
- ``admin:sync_task:latest:{kind}`` — task_id of the most recent task of
  that kind; used by the ``/status`` endpoints that accept an optional
  ``task_id`` query parameter and fall back to "latest of this kind"

Both keys share a 24h TTL — plenty for an admin refreshing a running sync
and long enough to see the final state after completion.

Task kinds
----------

``TaskKind.PUBLICATION`` maps to the legacy ``pub_sync_*`` id prefix.
``TaskKind.VARIANT``     maps to the legacy ``var_sync_*`` id prefix.
``TaskKind.REFERENCE``   covers both ``ref_init_*`` and ``genes_sync_*`` —
  these were grouped together in the old code via
  ``if k.startswith("genes_sync_") or k.startswith("ref_init_")``.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from app.core.cache import CacheService
from app.core.cache import cache as default_cache

logger = logging.getLogger(__name__)

KEY_PREFIX = "admin:sync_task:"
LATEST_PREFIX = "admin:sync_task:latest:"
DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24 hours


class TaskStatus(str, Enum):
    """Lifecycle states of a sync task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    IDLE = "idle"


class TaskKind(str, Enum):
    """Sync-task families.

    Drives the cache key for the "latest of this kind" pointer and the
    ``task_id`` prefix used when generating new ids.
    """

    PUBLICATION = "pub_sync"
    VARIANT = "var_sync"
    REFERENCE = "ref_sync"


@dataclass
class SyncTaskState:
    """Serialisable snapshot of a background sync task.

    Mirrors the fields that the old in-memory dict used to carry, so
    existing response-builder code can continue to read them with the
    same attribute names.
    """

    task_id: str
    kind: TaskKind
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    processed: int = 0
    total: int = 0
    errors: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-friendly dict (enums → their string values)."""
        data = asdict(self)
        data["kind"] = (
            self.kind.value if isinstance(self.kind, TaskKind) else self.kind
        )
        data["status"] = (
            self.status.value if isinstance(self.status, TaskStatus) else self.status
        )
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyncTaskState":
        """Rehydrate from the dict shape produced by :meth:`to_dict`."""
        return cls(
            task_id=data["task_id"],
            kind=TaskKind(data["kind"]),
            status=TaskStatus(data["status"]),
            progress=float(data.get("progress", 0.0)),
            processed=int(data.get("processed", 0)),
            total=int(data.get("total", 0)),
            errors=int(data.get("errors", 0)),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
        )


class SyncTaskStore:
    """Async cache-backed task state store.

    Takes an optional ``CacheService`` so tests can inject a dedicated
    instance; production code uses the default ``app.core.cache.cache``
    global (via :func:`get_sync_task_store`).

    Concurrency contract
    --------------------

    The update methods (``increment_processed`` / ``increment_errors`` /
    ``update_counts``) are **read-modify-write** against the cache and
    are **not atomic**. This is safe by design because every admin sync
    task spawns exactly one writer coroutine for a given ``task_id``
    (see ``sync_service.run_*``), so counter updates never race. If a
    future refactor parallelises a single task across workers, replace
    these helpers with a Redis ``HINCRBY``-style atomic path before
    letting the parallel writers loose.
    """

    def __init__(self, cache_service: Optional[CacheService] = None) -> None:
        """Wire the store to a cache service; falls back to the global default."""
        self._cache = cache_service or default_cache

    # ------------------------------------------------------------------ create

    async def create(self, kind: TaskKind, total: int = 0) -> SyncTaskState:
        """Allocate a new task, persist it, and mark it as the latest of its kind.

        Returns the newly-created state so callers can pass ``state.task_id``
        back to the scheduler without a follow-up ``get``.
        """
        task_id = self._generate_task_id(kind)
        state = SyncTaskState(task_id=task_id, kind=kind, total=total)
        await self._save(state)
        await self._set_latest(kind, task_id)
        return state

    # -------------------------------------------------------------------- read

    async def get(self, task_id: str) -> Optional[SyncTaskState]:
        """Fetch a task by id; returns ``None`` when it has expired or never existed."""
        data = await self._cache.get_json(f"{KEY_PREFIX}{task_id}")
        if data is None:
            return None
        return SyncTaskState.from_dict(data)

    async def get_latest(self, kind: TaskKind) -> Optional[SyncTaskState]:
        """Return the most-recent task of a given kind, if any."""
        task_id = await self._cache.get(f"{LATEST_PREFIX}{kind.value}")
        if not task_id:
            return None
        return await self.get(task_id)

    # ------------------------------------------------------------------ update

    async def mark_running(self, task_id: str) -> None:
        """Flip status to RUNNING and stamp ``started_at``."""
        state = await self.get(task_id)
        if state is None:
            logger.warning("mark_running called on missing task: %s", task_id)
            return
        state.status = TaskStatus.RUNNING
        state.started_at = datetime.now(timezone.utc).isoformat()
        await self._save(state)

    async def update_counts(
        self,
        task_id: str,
        *,
        processed: Optional[int] = None,
        total: Optional[int] = None,
        errors: Optional[int] = None,
    ) -> Optional[SyncTaskState]:
        """Update processed/total/errors counters and recompute ``progress``.

        Any unspecified field is left untouched. Returns the updated state so
        callers can chain a save with a ``log.info`` without issuing a second
        ``get``.
        """
        state = await self.get(task_id)
        if state is None:
            logger.warning("update_counts called on missing task: %s", task_id)
            return None
        if processed is not None:
            state.processed = processed
        if total is not None:
            state.total = total
        if errors is not None:
            state.errors = errors
        state.progress = (
            (state.processed / state.total * 100) if state.total > 0 else 100.0
        )
        await self._save(state)
        return state

    async def increment_processed(self, task_id: str) -> None:
        """Bump ``processed`` by one and recompute ``progress``."""
        state = await self.get(task_id)
        if state is None:
            return
        state.processed += 1
        state.progress = (
            (state.processed / state.total * 100) if state.total > 0 else 100.0
        )
        await self._save(state)

    async def increment_errors(self, task_id: str, count: int = 1) -> None:
        """Bump the ``errors`` counter (accepts a per-batch count)."""
        state = await self.get(task_id)
        if state is None:
            return
        state.errors += count
        await self._save(state)

    async def complete(self, task_id: str) -> None:
        """Mark a task COMPLETED, set progress to 100, stamp completion time."""
        state = await self.get(task_id)
        if state is None:
            return
        state.status = TaskStatus.COMPLETED
        state.progress = 100.0
        state.completed_at = datetime.now(timezone.utc).isoformat()
        await self._save(state)

    async def fail(self, task_id: str, error: str) -> None:
        """Mark a task failed, record the error message, stamp ``completed_at``."""
        state = await self.get(task_id)
        if state is None:
            return
        state.status = TaskStatus.FAILED
        state.error = error
        state.completed_at = datetime.now(timezone.utc).isoformat()
        await self._save(state)

    # ----------------------------------------------------------------- helpers

    def _generate_task_id(self, kind: TaskKind) -> str:
        """Produce a human-parseable, monotonically-ordered task id.

        Keeps the legacy ``pub_sync_YYYYMMDD_HHMMSS`` prefix layout so old
        task ids remain recognisable in logs, but adds a short uuid suffix to
        guarantee uniqueness under sub-second concurrent starts.
        """
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        suffix = uuid.uuid4().hex[:8]
        return f"{kind.value}_{stamp}_{suffix}"

    async def _save(self, state: SyncTaskState) -> None:
        await self._cache.set_json(
            f"{KEY_PREFIX}{state.task_id}",
            state.to_dict(),
            ttl=DEFAULT_TTL_SECONDS,
        )

    async def _set_latest(self, kind: TaskKind, task_id: str) -> None:
        await self._cache.set(
            f"{LATEST_PREFIX}{kind.value}",
            task_id,
            ttl=DEFAULT_TTL_SECONDS,
        )


_store_singleton: Optional[SyncTaskStore] = None


def get_sync_task_store() -> SyncTaskStore:
    """Return the process-wide SyncTaskStore.

    The store is a thin wrapper around the cache singleton, so the cost of
    holding a module-level instance is negligible. A function (rather than
    a module-level attribute) lets tests swap the cache backing without
    reimporting.
    """
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = SyncTaskStore()
    return _store_singleton


def reset_sync_task_store() -> None:
    """Clear the module-level singleton (test-only helper).

    Used by an autouse pytest fixture to stop one test's store state
    leaking into the next when tests hit the production code path via
    ``get_sync_task_store()`` rather than instantiating their own
    ``SyncTaskStore`` directly.
    """
    global _store_singleton
    _store_singleton = None
