"""Tests for the cache-backed admin sync task state.

Covers the :class:`SyncTaskStore` class introduced in Wave 4 to replace
the unsafe process-local ``_sync_tasks`` dict from the old flat
``admin_endpoints.py``. The store is exercised against a fresh
``CacheService`` instance forced into its in-memory fallback mode, which
is what ``app.core.cache.cache`` already does in the test environment
(no Redis daemon required).
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from app.api.admin.task_state import (
    KEY_PREFIX,
    LATEST_PREFIX,
    SyncTaskState,
    SyncTaskStore,
    TaskKind,
    TaskStatus,
    get_sync_task_store,
    reset_sync_task_store,
)
from app.core.cache import CacheService


@pytest.fixture(autouse=True)
def _reset_store_singleton() -> None:
    """Clear the module-level ``_store_singleton`` between every test.

    Otherwise one test's ``get_sync_task_store()`` call would poison the
    next test's state by returning a store wired to an already-populated
    in-memory fallback cache.
    """
    reset_sync_task_store()
    yield
    reset_sync_task_store()


@pytest_asyncio.fixture
async def store() -> SyncTaskStore:
    """Return a task store wired to an isolated in-memory cache service."""
    cache_service = CacheService()
    cache_service.use_fallback_only()  # never touch Redis in unit tests
    return SyncTaskStore(cache_service)


class TestCreate:
    """Cover ``SyncTaskStore.create`` — id generation, persistence, latest pointer."""

    @pytest.mark.asyncio
    async def test_create_assigns_id_with_kind_prefix(self, store: SyncTaskStore):
        """New task ids embed the kind prefix so log scraping still works."""
        state = await store.create(TaskKind.PUBLICATION, total=42)
        assert state.task_id.startswith("pub_sync_")
        assert state.kind == TaskKind.PUBLICATION
        assert state.status == TaskStatus.PENDING
        assert state.total == 42

    @pytest.mark.asyncio
    async def test_create_task_ids_are_unique(self, store: SyncTaskStore):
        """Sub-second concurrent creates must not collide."""
        first = await store.create(TaskKind.PUBLICATION)
        second = await store.create(TaskKind.PUBLICATION)
        assert first.task_id != second.task_id

    @pytest.mark.asyncio
    async def test_create_sets_latest_pointer(self, store: SyncTaskStore):
        """``create`` must make the task the new "latest of kind"."""
        state = await store.create(TaskKind.VARIANT, total=7)
        latest = await store.get_latest(TaskKind.VARIANT)
        assert latest is not None
        assert latest.task_id == state.task_id

    @pytest.mark.asyncio
    async def test_create_persists_state(self, store: SyncTaskStore):
        """Freshly-created tasks must be retrievable by their own id."""
        state = await store.create(TaskKind.REFERENCE, total=15)
        fetched = await store.get(state.task_id)
        assert fetched is not None
        assert fetched.kind == TaskKind.REFERENCE
        assert fetched.total == 15


class TestGetAndGetLatest:
    """Cover ``get`` and ``get_latest`` lookups."""

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(self, store: SyncTaskStore):
        """``get`` with an unknown id must return None, not raise."""
        assert await store.get("does-not-exist") is None

    @pytest.mark.asyncio
    async def test_get_latest_returns_none_for_missing_kind(self, store: SyncTaskStore):
        """``get_latest`` with no tasks of a kind returns None."""
        assert await store.get_latest(TaskKind.VARIANT) is None

    @pytest.mark.asyncio
    async def test_latest_pointer_updates_on_new_create(self, store: SyncTaskStore):
        """A second create of the same kind makes it the new latest; the
        older task is still retrievable by its id.
        """
        older = await store.create(TaskKind.PUBLICATION, total=5)
        newer = await store.create(TaskKind.PUBLICATION, total=9)
        latest = await store.get_latest(TaskKind.PUBLICATION)
        assert latest is not None
        assert latest.task_id == newer.task_id
        assert (await store.get(older.task_id)) is not None

    @pytest.mark.asyncio
    async def test_latest_pointer_is_per_kind(self, store: SyncTaskStore):
        """Latest pointers for different kinds are independent."""
        pub = await store.create(TaskKind.PUBLICATION)
        var = await store.create(TaskKind.VARIANT)
        assert (await store.get_latest(TaskKind.PUBLICATION)).task_id == pub.task_id
        assert (await store.get_latest(TaskKind.VARIANT)).task_id == var.task_id


class TestProgressUpdates:
    """Cover progress mutation (``mark_running``, ``update_counts``, increments)."""

    @pytest.mark.asyncio
    async def test_mark_running_sets_status_and_timestamp(self, store: SyncTaskStore):
        """``mark_running`` flips status and stamps ``started_at``."""
        state = await store.create(TaskKind.PUBLICATION, total=10)
        await store.mark_running(state.task_id)
        updated = await store.get(state.task_id)
        assert updated.status == TaskStatus.RUNNING
        assert updated.started_at is not None

    @pytest.mark.asyncio
    async def test_update_counts_recomputes_progress(self, store: SyncTaskStore):
        """processed/total changes recompute the ``progress`` percentage."""
        state = await store.create(TaskKind.VARIANT, total=4)
        await store.update_counts(state.task_id, processed=1, errors=0)
        updated = await store.get(state.task_id)
        assert updated.processed == 1
        assert updated.progress == pytest.approx(25.0)

    @pytest.mark.asyncio
    async def test_update_counts_total_zero_is_100_percent(self, store: SyncTaskStore):
        """Total of zero (empty queue) must surface as 100% "nothing to do"."""
        state = await store.create(TaskKind.PUBLICATION, total=0)
        await store.update_counts(state.task_id, processed=0)
        updated = await store.get(state.task_id)
        assert updated.progress == 100.0

    @pytest.mark.asyncio
    async def test_update_counts_is_noop_on_missing_task(self, store: SyncTaskStore):
        """Updating a missing task logs a warning and returns None."""
        result = await store.update_counts("missing", processed=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_increment_processed_advances_progress(self, store: SyncTaskStore):
        """Each ``increment_processed`` bumps the counter and progress."""
        state = await store.create(TaskKind.PUBLICATION, total=2)
        await store.increment_processed(state.task_id)
        first = await store.get(state.task_id)
        assert first.processed == 1
        assert first.progress == pytest.approx(50.0)
        await store.increment_processed(state.task_id)
        second = await store.get(state.task_id)
        assert second.processed == 2
        assert second.progress == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_increment_errors_accumulates(self, store: SyncTaskStore):
        """``increment_errors`` accepts an explicit batch count."""
        state = await store.create(TaskKind.VARIANT, total=10)
        await store.increment_errors(state.task_id, count=3)
        await store.increment_errors(state.task_id, count=2)
        updated = await store.get(state.task_id)
        assert updated.errors == 5


class TestTerminalStates:
    """Cover ``complete`` and ``fail``."""

    @pytest.mark.asyncio
    async def test_complete_sets_status_and_progress(self, store: SyncTaskStore):
        """``complete`` forces status to COMPLETED and progress to 100."""
        state = await store.create(TaskKind.PUBLICATION, total=3)
        await store.update_counts(state.task_id, processed=1)
        await store.complete(state.task_id)
        finished = await store.get(state.task_id)
        assert finished.status == TaskStatus.COMPLETED
        assert finished.progress == 100.0
        assert finished.completed_at is not None

    @pytest.mark.asyncio
    async def test_fail_records_error_and_timestamp(self, store: SyncTaskStore):
        """``fail`` records the error string and stamps ``completed_at``."""
        state = await store.create(TaskKind.VARIANT, total=5)
        await store.fail(state.task_id, "boom")
        failed = await store.get(state.task_id)
        assert failed.status == TaskStatus.FAILED
        assert failed.error == "boom"
        assert failed.completed_at is not None

    @pytest.mark.asyncio
    async def test_complete_and_fail_noop_on_missing(self, store: SyncTaskStore):
        """Completing / failing an unknown task must not raise."""
        await store.complete("missing")
        await store.fail("missing", "nothing to see")


class TestSerialization:
    """Cover the ``to_dict`` / ``from_dict`` round-trip on ``SyncTaskState``."""

    def test_to_dict_roundtrip(self):
        """Encoded state decodes back to an equal object."""
        state = SyncTaskState(
            task_id="pub_sync_20260411_000000_abcdef01",
            kind=TaskKind.PUBLICATION,
            status=TaskStatus.RUNNING,
            progress=42.5,
            processed=17,
            total=40,
            errors=1,
            started_at="2026-04-11T00:00:00+00:00",
            completed_at=None,
            error=None,
        )
        data = state.to_dict()
        assert data["kind"] == "pub_sync"
        assert data["status"] == "running"
        restored = SyncTaskState.from_dict(data)
        assert restored == state


class TestCacheKeys:
    """Cover the operational cache-key contract.

    The key layout is part of the operational contract — if it ever
    changes, running sync state across a rolling deploy would break.
    """

    @pytest.mark.asyncio
    async def test_key_layout_matches_documented_format(self, store: SyncTaskStore):
        """State is stored under ``admin:sync_task:{task_id}`` and the
        latest pointer under ``admin:sync_task:latest:{kind}``.
        """
        state = await store.create(TaskKind.PUBLICATION, total=1)
        raw = await store._cache.get_json(f"{KEY_PREFIX}{state.task_id}")
        assert raw is not None
        assert raw["task_id"] == state.task_id
        latest = await store._cache.get(f"{LATEST_PREFIX}{TaskKind.PUBLICATION.value}")
        assert latest == state.task_id


class TestSingleton:
    """Cover the module-level ``get_sync_task_store`` helper."""

    def test_get_sync_task_store_returns_same_instance(self):
        """Repeated calls return the same store (cheap singleton)."""
        a = get_sync_task_store()
        b = get_sync_task_store()
        assert a is b
