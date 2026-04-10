# Wave 4: Backend Decomposition — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring every backend file in `backend/app/` under 500 LOC. Introduce the `PhenopacketRepository` layer to match the clean pattern already used in the search module. Replace the in-memory `_sync_tasks` dict with Redis-backed task state.

**Architecture:** Router → Service → Repository layering, applied incrementally per oversized file. Each file split is its own PR with HTTP-surface-identical before/after tests.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0 async, Redis 5.x, pytest-asyncio.

**Parent spec:** `docs/superpowers/specs/2026-04-10-codebase-refactor-roadmap-design.md` (Wave 4 section)

**Prerequisites:** Waves 1-3 complete. Critical dependencies:
- Wave 2's dedicated test database (parity testing needs it)
- Wave 2's phenopacket CRUD integration tests (safety net for the crud.py split)
- Wave 3's aggregations/common.py helpers (some admin queries may use them)

---

## Context

All Wave 1-3 conventions apply. Branch: `chore/wave-4-backend-decomposition`.

**Files to decompose (12 total, all over 500 LOC):**

| File | LOC | Planned split |
|------|:---:|---------------|
| admin_endpoints.py | 1,159 | api/admin/ sub-package |
| survival_handlers.py | 1,055 | already handled in Wave 3 (moved to survival/handlers.py); verify under 500 |
| crud.py | 1,002 | repositories/ + services/ + thin router |
| variant_validator.py | 968 | validation/variant_validator/ sub-package |
| comparisons.py | 861 | routers/comparisons/ sub-package |
| variants/service.py | 823 | variants/ sub-package |
| sql_fragments.py | 748 | aggregations/sql/ sub-package |
| reference/service.py | 721 | reference/ sub-package |
| variant_validator_endpoint.py | 702 | variant_validator/ sub-package |
| publications/endpoints.py | 680 | publications/ sub-package |
| search/services.py | 513 | search/ already partly split — verify |

**Golden rule for each split:** the HTTP surface (request shapes, response shapes, status codes, endpoint paths) must remain byte-identical before and after. Every split has a fixture-based before/after diff step.

**PR cadence:** each task is one PR. Merge each PR green before starting the next task (or keep a running branch and merge all at wave end — either is acceptable).

---

## Task 1: Baseline fixture capture for HTTP-surface comparison

**Files:**
- Create: `backend/tests/fixtures/wave4_http_baselines/` (directory for response snapshots)
- Create: `backend/tests/test_http_surface_baseline.py`

Before touching any code, capture the current response shape of every endpoint that will be affected by Wave 4 splits. Each subsequent task's exit criteria includes "HTTP surface matches baseline."

- [ ] **Step 1: Create the baseline fixture directory**

```bash
mkdir -p backend/tests/fixtures/wave4_http_baselines
```

- [ ] **Step 2: Write a baseline capture script**

Create `backend/tests/test_http_surface_baseline.py`:

```python
"""Captures and verifies HTTP-surface baselines for Wave 4 decomposition.

Run in "capture" mode once before starting decomposition work:
    pytest tests/test_http_surface_baseline.py -k "capture" -s

Run in "verify" mode after each task:
    pytest tests/test_http_surface_baseline.py -k "verify"

The capture produces JSON snapshots under tests/fixtures/wave4_http_baselines/.
Verify mode re-hits the endpoints and asserts the response shape matches.
"""

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

BASELINE_DIR = Path(__file__).parent / "fixtures" / "wave4_http_baselines"


# Endpoints affected by Wave 4 decomposition. Each tuple is
# (test_name, method, path, json_body_or_none).
AFFECTED_ENDPOINTS = [
    ("admin_status", "GET", "/api/v2/admin/status", None),
    ("phenopackets_list", "GET", "/api/v2/phenopackets/?page[size]=3", None),
    ("phenopackets_search", "POST", "/api/v2/phenopackets/search", {"query": "renal"}),
    ("variants_annotate", "POST", "/api/v2/variants/annotate?variant=NM_000458.4:c.544%2B1G%3EA", None),
    ("comparisons_test", "POST", "/api/v2/phenopackets/comparisons", {"groups": []}),
    ("publications_list", "GET", "/api/v2/publications/?page[size]=3", None),
    ("reference_genes", "GET", "/api/v2/reference/genes", None),
    ("search_basic", "GET", "/api/v2/search/?q=HNF1B", None),
]


@pytest.fixture
def client():
    return TestClient(app)


def _normalize_response(data):
    """Strip fields that vary between runs (timestamps, IDs, counts)."""
    if isinstance(data, dict):
        return {
            k: (
                "<normalized>"
                if k in {"created_at", "updated_at", "request_id", "total", "count"}
                else _normalize_response(v)
            )
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_normalize_response(item) for item in data[:3]]  # cap at 3 items
    return data


@pytest.mark.parametrize("name,method,path,body", AFFECTED_ENDPOINTS)
def test_capture_baseline(client, name, method, path, body):
    """Capture current response as baseline. Skipped unless CAPTURE_MODE is set."""
    if os.environ.get("WAVE4_CAPTURE_BASELINE") != "1":
        pytest.skip("Baseline capture only runs when WAVE4_CAPTURE_BASELINE=1")

    if method == "GET":
        response = client.get(path)
    else:
        response = client.request(method, path, json=body or {})

    data = {
        "status_code": response.status_code,
        "response_keys": (
            sorted(response.json().keys())
            if isinstance(response.json(), dict)
            else "list"
        )
        if response.status_code < 500
        else None,
        "normalized_body": _normalize_response(response.json())
        if response.status_code < 500
        else None,
    }

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    with (BASELINE_DIR / f"{name}.json").open("w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


@pytest.mark.parametrize("name,method,path,body", AFFECTED_ENDPOINTS)
def test_verify_baseline(client, name, method, path, body):
    """Verify the current response matches the captured baseline."""
    baseline_path = BASELINE_DIR / f"{name}.json"
    if not baseline_path.exists():
        pytest.skip(f"No baseline captured for {name}")

    with baseline_path.open() as f:
        baseline = json.load(f)

    if method == "GET":
        response = client.get(path)
    else:
        response = client.request(method, path, json=body or {})

    assert response.status_code == baseline["status_code"], (
        f"{name}: status code changed from {baseline['status_code']} to {response.status_code}"
    )

    if baseline["normalized_body"] is not None:
        current = _normalize_response(response.json())
        assert current == baseline["normalized_body"], (
            f"{name}: response body shape changed"
        )
```

- [ ] **Step 3: Capture the baseline**

```bash
cd backend && WAVE4_CAPTURE_BASELINE=1 uv run pytest tests/test_http_surface_baseline.py -k "capture" -v -s
```

Expected: each endpoint writes a JSON baseline file to `tests/fixtures/wave4_http_baselines/`. Some may skip or fail if the endpoint requires auth; that's OK — capture what you can.

- [ ] **Step 4: Verify the baseline works**

```bash
cd backend && uv run pytest tests/test_http_surface_baseline.py -k "verify" -v
```

Expected: all captured baselines pass verification against the current code.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_http_surface_baseline.py backend/tests/fixtures/wave4_http_baselines/
git commit -m "test(backend): capture HTTP surface baseline for Wave 4

Captures response-shape snapshots for every endpoint affected by
Wave 4 decomposition. Used by subsequent tasks to verify splits
preserve the HTTP surface byte-for-byte. Capture mode is gated behind
WAVE4_CAPTURE_BASELINE=1; verify mode runs by default.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

**After every subsequent task:** run `uv run pytest tests/test_http_surface_baseline.py -k verify` and confirm green before committing.

---

## Task 2: Decompose admin_endpoints.py into api/admin/ sub-package

**Files:**
- Create: `backend/app/api/admin/__init__.py`
- Create: `backend/app/api/admin/endpoints.py`
- Create: `backend/app/api/admin/sync_service.py`
- Create: `backend/app/api/admin/task_state.py` (Redis-backed)
- Create: `backend/app/api/admin/queries.py`
- Delete: `backend/app/api/admin_endpoints.py`
- Create: `backend/tests/test_admin_sync_service.py`
- Create: `backend/tests/test_admin_task_state.py`

- [ ] **Step 1: Write task_state tests first (Redis replacement for _sync_tasks)**

Create `backend/tests/test_admin_task_state.py`:

```python
"""Tests for Redis-backed admin sync task state.

Replaces the process-local _sync_tasks dict flagged in the 2026-04-09
review as unsafe for multi-worker deployments.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.admin.task_state import (
    SyncTaskState,
    RedisTaskStateBackend,
    TaskStatus,
)


class TestRedisTaskStateBackend:
    @pytest.fixture
    def mock_redis(self):
        redis_client = MagicMock()
        redis_client.set = MagicMock()
        redis_client.get = MagicMock(return_value=None)
        redis_client.delete = MagicMock()
        redis_client.keys = MagicMock(return_value=[])
        return redis_client

    def test_start_creates_redis_key(self, mock_redis):
        backend = RedisTaskStateBackend(mock_redis)
        task = backend.start("publications_sync")
        assert task.task_id is not None
        assert task.status == TaskStatus.RUNNING
        mock_redis.set.assert_called()

    def test_get_returns_none_for_missing_task(self, mock_redis):
        backend = RedisTaskStateBackend(mock_redis)
        mock_redis.get.return_value = None
        result = backend.get("nonexistent")
        assert result is None

    def test_complete_updates_status(self, mock_redis):
        backend = RedisTaskStateBackend(mock_redis)
        import json
        mock_redis.get.return_value = json.dumps(
            {"task_id": "t1", "task_type": "sync", "status": "running", "progress": 0}
        )
        backend.complete("t1")
        assert mock_redis.set.called

    def test_list_active_returns_running_tasks(self, mock_redis):
        import json
        mock_redis.keys.return_value = [b"admin:sync_task:t1", b"admin:sync_task:t2"]
        mock_redis.get.side_effect = [
            json.dumps({"task_id": "t1", "task_type": "sync", "status": "running", "progress": 50}),
            json.dumps({"task_id": "t2", "task_type": "sync", "status": "completed", "progress": 100}),
        ]
        backend = RedisTaskStateBackend(mock_redis)
        active = backend.list_active()
        assert len(active) == 1
        assert active[0].task_id == "t1"
```

- [ ] **Step 2: Create the task_state module**

Create `backend/app/api/admin/task_state.py`:

```python
"""Redis-backed sync task state.

Replaces the process-local _sync_tasks dict from the old
admin_endpoints.py (flagged as unsafe in the 2026-04-09 review).
Task state survives worker restarts and is visible across multiple
FastAPI workers.

Key format: admin:sync_task:{task_id}
"""

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)

KEY_PREFIX = "admin:sync_task:"
DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24h retention


class TaskStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SyncTaskState:
    task_id: str
    task_type: str
    status: TaskStatus
    progress: int = 0
    error: Optional[str] = None


class RedisTaskStateBackend:
    """Persistent task state backed by Redis."""

    def __init__(self, redis_client):
        self._redis = redis_client

    def start(self, task_type: str) -> SyncTaskState:
        task_id = str(uuid.uuid4())
        state = SyncTaskState(
            task_id=task_id, task_type=task_type, status=TaskStatus.RUNNING, progress=0
        )
        self._save(state)
        return state

    def get(self, task_id: str) -> Optional[SyncTaskState]:
        raw = self._redis.get(f"{KEY_PREFIX}{task_id}")
        if raw is None:
            return None
        data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        return SyncTaskState(
            task_id=data["task_id"],
            task_type=data["task_type"],
            status=TaskStatus(data["status"]),
            progress=data.get("progress", 0),
            error=data.get("error"),
        )

    def update_progress(self, task_id: str, progress: int) -> None:
        state = self.get(task_id)
        if state is None:
            logger.warning("Update progress for missing task: %s", task_id)
            return
        state.progress = progress
        self._save(state)

    def complete(self, task_id: str) -> None:
        state = self.get(task_id)
        if state is None:
            return
        state.status = TaskStatus.COMPLETED
        state.progress = 100
        self._save(state)

    def fail(self, task_id: str, error: str) -> None:
        state = self.get(task_id)
        if state is None:
            return
        state.status = TaskStatus.FAILED
        state.error = error
        self._save(state)

    def list_active(self) -> List[SyncTaskState]:
        keys = self._redis.keys(f"{KEY_PREFIX}*")
        result = []
        for key in keys:
            task_id = (
                key.decode().split(":")[-1]
                if isinstance(key, bytes)
                else key.split(":")[-1]
            )
            state = self.get(task_id)
            if state is not None and state.status == TaskStatus.RUNNING:
                result.append(state)
        return result

    def _save(self, state: SyncTaskState) -> None:
        self._redis.set(
            f"{KEY_PREFIX}{state.task_id}",
            json.dumps(asdict(state), default=str),
            ex=DEFAULT_TTL_SECONDS,
        )
```

- [ ] **Step 3: Need `__init__.py` for the package**

Create `backend/app/api/admin/__init__.py`:

```python
"""Admin API sub-package.

Public API:
    router: FastAPI router aggregating admin endpoints
"""
from .endpoints import router

__all__ = ["router"]
```

- [ ] **Step 4: Run task_state tests**

```bash
cd backend && uv run pytest tests/test_admin_task_state.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Split admin_endpoints.py**

Read `backend/app/api/admin_endpoints.py` section by section (1,159 LOC). Identify the logical groupings:

1. **FastAPI route handlers** → `admin/endpoints.py`
2. **Sync orchestration** (publication sync, variant sync, reference sync, phenopacket sync) → `admin/sync_service.py`
3. **Raw SQL helper queries** → `admin/queries.py`

Split mechanically: copy each group to its target file, update imports, leave the originals in `admin_endpoints.py` temporarily. Run the HTTP surface baseline verify after each copy.

Once all sections are in their new homes, update the router in `admin/endpoints.py` to import from the service/queries modules. Delete `admin_endpoints.py` last.

- [ ] **Step 6: Update all imports of admin_endpoints**

```bash
cd backend && grep -rn "admin_endpoints" app tests --include="*.py"
```

Most references are probably in `app/main.py` where the router is registered. Update:

```python
from app.api.admin_endpoints import router as admin_router
# becomes
from app.api.admin import router as admin_router
```

- [ ] **Step 7: Write sync_service tests**

Create `backend/tests/test_admin_sync_service.py` with at least 3 tests exercising the refactored sync service with mocked Redis and mocked external API clients.

- [ ] **Step 8: Verify each file under 500 LOC**

```bash
find backend/app/api/admin -name "*.py" -exec wc -l {} \;
```

Expected: each file under 500 LOC. If any is over, split further.

- [ ] **Step 9: Run baseline verification**

```bash
cd backend && uv run pytest tests/test_http_surface_baseline.py -k verify -v && make check
```

Expected: all green. Admin endpoints' HTTP surface is byte-identical.

- [ ] **Step 10: Commit**

```bash
git add backend/app/api/admin/ backend/app/api/admin_endpoints.py backend/app/main.py backend/tests/test_admin_sync_service.py backend/tests/test_admin_task_state.py
git commit -m "$(cat <<'EOF'
refactor(backend): decompose admin_endpoints.py into sub-package

Splits the 1,159-LOC admin_endpoints.py into a sub-package:

  api/admin/
    __init__.py       (router re-export)
    endpoints.py      (FastAPI routes)
    sync_service.py   (sync orchestration)
    task_state.py     (Redis-backed task state)
    queries.py        (raw SQL helpers)

Every file is under 500 LOC. Replaces the unsafe process-local
_sync_tasks dict with RedisTaskStateBackend; task state now
survives worker restarts. Companion tests cover task state CRUD
and sync-service orchestration with mocked Redis.

HTTP surface baseline verified unchanged.

Closes P2 #5 and P3 #11 from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Introduce PhenopacketRepository and decompose crud.py

**Files:**
- Create: `backend/app/phenopackets/repositories/__init__.py`
- Create: `backend/app/phenopackets/repositories/phenopacket_repository.py`
- Create: `backend/app/phenopackets/services/__init__.py`
- Create: `backend/app/phenopackets/services/phenopacket_service.py`
- Modify: `backend/app/phenopackets/routers/crud.py` (shrink to thin router)
- Create: `backend/tests/test_phenopacket_repository.py`
- Create: `backend/tests/test_phenopacket_service.py`

- [ ] **Step 1: Write repository tests first**

Create `backend/tests/test_phenopacket_repository.py` with these test classes:

```python
"""Tests for PhenopacketRepository.

Repository is a pure data-access layer. These tests use the dedicated
test database and a single async session fixture.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.repositories import PhenopacketRepository


@pytest.fixture
async def repo(test_db_session: AsyncSession):
    return PhenopacketRepository(test_db_session)


@pytest.mark.asyncio
class TestGetById:
    async def test_returns_none_for_missing_id(self, repo):
        result = await repo.get_by_id("NONEXISTENT")
        assert result is None


@pytest.mark.asyncio
class TestListPaginated:
    async def test_returns_page_shape(self, repo):
        results, total = await repo.list_paginated(offset=0, limit=10)
        assert isinstance(results, list)
        assert isinstance(total, int)
        assert total >= len(results)


@pytest.mark.asyncio
class TestListCursor:
    async def test_returns_list_shape(self, repo):
        results, next_cursor = await repo.list_cursor(cursor=None, limit=5)
        assert isinstance(results, list)
        assert next_cursor is None or isinstance(next_cursor, str)


@pytest.mark.asyncio
class TestCountFiltered:
    async def test_count_is_nonnegative(self, repo):
        count = await repo.count_filtered({})
        assert isinstance(count, int)
        assert count >= 0
```

- [ ] **Step 2: Run to confirm fail**

```bash
cd backend && uv run pytest tests/test_phenopacket_repository.py --collect-only
```

Expected: import error for `PhenopacketRepository`.

- [ ] **Step 3: Create the repository**

Create `backend/app/phenopackets/repositories/__init__.py`:

```python
from .phenopacket_repository import PhenopacketRepository

__all__ = ["PhenopacketRepository"]
```

Create `backend/app/phenopackets/repositories/phenopacket_repository.py`:

```python
"""PhenopacketRepository: pure data access layer for phenopackets.

Mirrors the pattern already used in backend/app/search/repositories.py.
All persistence logic (queries, inserts, updates, deletes) lives here;
business rules and HTTP concerns live in phenopacket_service.py and
routers/crud.py respectively.

This class is intentionally stateless except for the injected session.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket

logger = logging.getLogger(__name__)


class PhenopacketRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, phenopacket_id: str) -> Optional[Phenopacket]:
        stmt = select(Phenopacket).where(Phenopacket.id == phenopacket_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_paginated(
        self, offset: int, limit: int, filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Phenopacket], int]:
        base = select(Phenopacket)
        if filters:
            base = self._apply_filters(base, filters)
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()
        data_stmt = base.offset(offset).limit(limit)
        rows = (await self._session.execute(data_stmt)).scalars().all()
        return list(rows), int(total)

    async def list_cursor(
        self, cursor: Optional[str], limit: int, filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Phenopacket], Optional[str]]:
        # Cursor pagination using (created_at, id) composite
        base = select(Phenopacket).order_by(Phenopacket.created_at.desc(), Phenopacket.id.desc())
        if filters:
            base = self._apply_filters(base, filters)
        # cursor decoding is delegated to app.utils.pagination; replicate the call
        from app.utils.pagination import decode_cursor, encode_cursor
        if cursor:
            decoded = decode_cursor(cursor)
            base = base.where(
                (Phenopacket.created_at < decoded["created_at"])
                | (
                    (Phenopacket.created_at == decoded["created_at"])
                    & (Phenopacket.id < decoded["id"])
                )
            )
        base = base.limit(limit + 1)
        rows = list((await self._session.execute(base)).scalars())
        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            next_cursor = encode_cursor({"created_at": last.created_at, "id": last.id})
            rows = rows[:limit]
        return rows, next_cursor

    async def count_filtered(self, filters: Dict[str, Any]) -> int:
        stmt = select(func.count()).select_from(Phenopacket)
        if filters:
            base = self._apply_filters(select(Phenopacket), filters)
            stmt = select(func.count()).select_from(base.subquery())
        return int((await self._session.execute(stmt)).scalar_one())

    async def create(self, data: Dict[str, Any]) -> Phenopacket:
        phenopacket = Phenopacket(**data)
        self._session.add(phenopacket)
        await self._session.flush()
        return phenopacket

    async def update(self, phenopacket_id: str, data: Dict[str, Any]) -> Optional[Phenopacket]:
        stmt = update(Phenopacket).where(Phenopacket.id == phenopacket_id).values(**data).returning(Phenopacket)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, phenopacket_id: str) -> bool:
        stmt = delete(Phenopacket).where(Phenopacket.id == phenopacket_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    def _apply_filters(self, stmt, filters: Dict[str, Any]):
        # Mirrors existing filter logic from crud.py — read that function
        # during the split and port the same conditions here.
        return stmt
```

Note the `_apply_filters` stub — during execution, copy the current filter logic out of `crud.py` into this method. The tests above are shallow by design; they do not exercise filter specifics.

- [ ] **Step 4: Create the service layer**

Create `backend/app/phenopackets/services/__init__.py`:

```python
from .phenopacket_service import PhenopacketService

__all__ = ["PhenopacketService"]
```

Create `backend/app/phenopackets/services/phenopacket_service.py`:

```python
"""PhenopacketService: business rules and orchestration.

Sits between the router (HTTP) and the repository (data access).
Owns: audit logging, JSON Patch generation, validation rules,
transaction coordination.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import Phenopacket
from app.phenopackets.repositories import PhenopacketRepository
from app.utils.audit import create_audit_entry

logger = logging.getLogger(__name__)


class PhenopacketService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._repo = PhenopacketRepository(session)

    async def get(self, phenopacket_id: str) -> Optional[Phenopacket]:
        return await self._repo.get_by_id(phenopacket_id)

    async def list_offset(
        self, page: int, size: int, filters: Dict[str, Any]
    ) -> Tuple[List[Phenopacket], int]:
        offset = (page - 1) * size
        return await self._repo.list_paginated(offset=offset, limit=size, filters=filters)

    async def list_cursor(
        self, cursor: Optional[str], size: int, filters: Dict[str, Any]
    ) -> Tuple[List[Phenopacket], Optional[str]]:
        return await self._repo.list_cursor(cursor=cursor, limit=size, filters=filters)

    async def create(self, data: Dict[str, Any], actor: str) -> Phenopacket:
        phenopacket = await self._repo.create(data)
        await create_audit_entry(
            self._session,
            phenopacket_id=phenopacket.id,
            action="create",
            actor=actor,
            new_value=data,
        )
        await self._session.commit()
        return phenopacket

    async def update(
        self, phenopacket_id: str, patch: List[Dict[str, Any]], actor: str
    ) -> Optional[Phenopacket]:
        existing = await self._repo.get_by_id(phenopacket_id)
        if existing is None:
            return None
        # apply JSON patch to existing.to_dict() here; pseudo-code:
        # new_data = jsonpatch.apply_patch(existing.to_dict(), patch)
        # updated = await self._repo.update(phenopacket_id, new_data)
        # await create_audit_entry(...)
        # await self._session.commit()
        # return updated
        raise NotImplementedError("Port update logic from crud.py during split")

    async def delete(self, phenopacket_id: str, actor: str) -> bool:
        existed = await self._repo.delete(phenopacket_id)
        if existed:
            await create_audit_entry(
                self._session,
                phenopacket_id=phenopacket_id,
                action="delete",
                actor=actor,
            )
            await self._session.commit()
        return existed
```

The `NotImplementedError` in `update()` is a deliberate signpost — the update flow in `crud.py` is complex (involves JSON Patch, validation, partial updates), and copying it verbatim is error-prone. Port it carefully with tests.

- [ ] **Step 5: Rewrite crud.py as a thin router**

This is the core of Task 3. Carefully migrate every endpoint in `crud.py` to call the service. Each endpoint body should become 5-10 lines:

```python
@router.get("/{phenopacket_id}")
async def get_phenopacket(
    phenopacket_id: str,
    session: AsyncSession = Depends(get_db),
):
    service = PhenopacketService(session)
    phenopacket = await service.get(phenopacket_id)
    if phenopacket is None:
        raise HTTPException(status_code=404, detail="Phenopacket not found")
    return phenopacket
```

The goal is `crud.py` under 500 LOC. Expected result: ~300 LOC of pure HTTP plumbing.

- [ ] **Step 6: Run the full test suite**

```bash
cd backend && make check && uv run pytest tests/test_http_surface_baseline.py -k verify -v
```

Expected: all green. The integration tests from Wave 2 are the primary regression net; if any break, the split changed observable behavior — investigate.

- [ ] **Step 7: Verify file sizes**

```bash
wc -l backend/app/phenopackets/routers/crud.py backend/app/phenopackets/services/phenopacket_service.py backend/app/phenopackets/repositories/phenopacket_repository.py
```

Expected: all under 500 LOC.

- [ ] **Step 8: Commit**

```bash
git add backend/app/phenopackets/repositories/ backend/app/phenopackets/services/ backend/app/phenopackets/routers/crud.py backend/tests/test_phenopacket_repository.py
git commit -m "$(cat <<'EOF'
refactor(backend): introduce PhenopacketRepository and PhenopacketService

Splits the 1,002-LOC crud.py into three layers:
  routers/crud.py                          (~300 LOC, HTTP only)
  services/phenopacket_service.py          (business rules, audit)
  repositories/phenopacket_repository.py   (pure SQLAlchemy data access)

Mirrors the layering already used in backend/app/search/. Each file
is under 500 LOC. Existing phenopacket CRUD integration tests from
Wave 2 are the safety net and pass unchanged.

Closes P5 #22 from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Decompose variant_validator.py into a sub-package

**Files:**
- Create: `backend/app/phenopackets/validation/variant_validator/__init__.py`
- Create: `backend/app/phenopackets/validation/variant_validator/hgvs_parser.py`
- Create: `backend/app/phenopackets/validation/variant_validator/vcf_parser.py`
- Create: `backend/app/phenopackets/validation/variant_validator/spdi_parser.py`
- Create: `backend/app/phenopackets/validation/variant_validator/validator.py`
- Delete: `backend/app/phenopackets/validation/variant_validator.py`

The existing 1,660-line `test_variant_validator_enhanced.py` is the safety net.

- [ ] **Step 1: Read the file structure**

```bash
cd backend && grep -n "^class \|^def " app/phenopackets/validation/variant_validator.py
```

Identify:
- The public class (likely `VariantValidator`).
- Private parser functions for HGVS, VCF, SPDI.
- Helper functions.

- [ ] **Step 2: Extract HGVS parsing**

Create `backend/app/phenopackets/validation/variant_validator/hgvs_parser.py` containing all HGVS-specific regex, functions, and class helpers from the original file. Keep the same function signatures so imports can redirect.

- [ ] **Step 3: Extract VCF parsing**

Same treatment for VCF-specific code → `vcf_parser.py`.

- [ ] **Step 4: Extract SPDI parsing**

Same treatment → `spdi_parser.py`.

- [ ] **Step 5: Create the top-level validator.py**

Create `backend/app/phenopackets/validation/variant_validator/validator.py`:

```python
"""Public VariantValidator interface.

Re-exports the validator class, delegating to the specific parsers
in the sub-package.
"""

from .hgvs_parser import parse_hgvs
from .vcf_parser import parse_vcf
from .spdi_parser import parse_spdi
# ... etc

class VariantValidator:
    # Orchestration only — actual parsing is delegated.
    ...
```

- [ ] **Step 6: Create __init__.py with re-exports**

```python
# validation/variant_validator/__init__.py
from .validator import VariantValidator

__all__ = ["VariantValidator"]
```

- [ ] **Step 7: Delete the old flat file**

```bash
rm backend/app/phenopackets/validation/variant_validator.py
```

- [ ] **Step 8: Update imports across the codebase**

```bash
cd backend && grep -rn "from app.phenopackets.validation.variant_validator import\|from app.phenopackets.validation import variant_validator" app tests
```

Update if any path no longer resolves. The package's `__init__.py` re-export should handle most.

- [ ] **Step 9: Run tests**

```bash
cd backend && uv run pytest tests/test_variant_validator_enhanced.py -v && make check && uv run pytest tests/test_http_surface_baseline.py -k verify -v
```

Expected: all green.

- [ ] **Step 10: Verify file sizes**

```bash
find backend/app/phenopackets/validation/variant_validator -name "*.py" -exec wc -l {} \;
```

Expected: every file under 500 LOC.

- [ ] **Step 11: Commit**

```bash
git add backend/app/phenopackets/validation/variant_validator/ backend/app/phenopackets/validation/variant_validator.py
git commit -m "refactor(backend): split variant_validator.py into sub-package

Decomposes the 968-LOC variant_validator.py into:
  variant_validator/
    __init__.py         (re-export)
    validator.py        (public orchestration)
    hgvs_parser.py      (HGVS notation parsing)
    vcf_parser.py       (VCF format parsing)
    spdi_parser.py      (SPDI format parsing)

Every file is under 500 LOC. Existing 1,660-line test file is the
safety net.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Decompose comparisons.py, variants/service.py, sql_fragments.py, reference/service.py, variant_validator_endpoint.py, publications/endpoints.py, search/services.py

Tasks 5a through 5g — one file per sub-task, same pattern. **Each sub-task is its own PR.**

For each file, the pattern is:
1. Read the file and identify 3-5 logical groupings.
2. Create a sub-package directory.
3. Move code to files within the sub-package.
4. Update the parent `__init__.py` to re-export public names.
5. Update imports across the codebase.
6. Delete the flat file.
7. Run the full test suite + HTTP surface verification.
8. Verify every new file is under 500 LOC.
9. Commit.

Below is a sketch of the split for each. Use these as a starting point; adjust based on what the actual file contains.

### Task 5a: `comparisons.py` (861 LOC)

Split:
- `routers/comparisons/__init__.py`
- `routers/comparisons/router.py` (FastAPI endpoints)
- `routers/comparisons/statistical_tests.py` (chi-square, Fisher, Mann-Whitney, etc.)
- `routers/comparisons/result_builder.py` (response construction)

Safety net: the 1,467-line `test_comparisons.py`.

- [ ] Write one PR following the pattern above. Verify file sizes, run baseline check, commit with message: `refactor(backend): split comparisons.py into sub-package`.

### Task 5b: `variants/service.py` (823 LOC)

Split:
- `variants/service.py` (shrunk to public API only, ~150 LOC)
- `variants/vep_client.py` (httpx client, retry, rate limit)
- `variants/parser.py` (variant format parsing helpers — refactor the "test reaches private method" anti-pattern here by promoting helpers)
- `variants/annotation.py` (CADD, gnomAD, consequence processing)

- [ ] Run the existing VEP and variant tests. Commit: `refactor(backend): split variants/service.py into vep_client, parser, annotation modules`.

### Task 5c: `sql_fragments.py` (748 LOC)

Split by domain:
- `aggregations/sql/__init__.py`
- `aggregations/sql/variant_fragments.py`
- `aggregations/sql/clinical_fragments.py`
- `aggregations/sql/demographic_fragments.py`

- [ ] Commit: `refactor(backend): split aggregation sql_fragments by domain`.

### Task 5d: `reference/service.py` (721 LOC)

Split:
- `reference/service.py` (thin public API)
- `reference/ensembl_client.py` (HTTP client)
- `reference/gene_importer.py` (gene-specific import logic)
- `reference/transcript_importer.py` (transcript import logic)

- [ ] Commit: `refactor(backend): split reference service into clients and importers`.

### Task 5e: `variant_validator_endpoint.py` (702 LOC)

Split:
- `variant_validator/__init__.py` (note: this is a different module than the one from Task 4 — that was `validation/variant_validator/`; this is `app/variant_validator/`. Keep them separate.)
- `variant_validator/endpoint.py`
- `variant_validator/request_handlers.py`
- `variant_validator/response_builders.py`

Fix the "reaches through private internals" anti-pattern noted in the review by promoting needed helpers to public methods on `variant_validator/request_handlers.py`.

- [ ] Commit: `refactor(backend): split variant_validator_endpoint.py into sub-package`.

### Task 5f: `publications/endpoints.py` (680 LOC)

Split:
- `publications/__init__.py`
- `publications/router.py` (FastAPI routes)
- `publications/pubmed_handlers.py` (NCBI E-Utils client code)
- `publications/citation_formatters.py` (APA/MLA/Vancouver formatting)

- [ ] Commit: `refactor(backend): split publications endpoints into router, handlers, formatters`.

### Task 5g: `search/services.py` (513 LOC)

The search module already has a repositories.py — it's mostly clean. Just split the 513-LOC services.py into:
- `search/services/query_builder.py`
- `search/services/result_shaper.py`

Or, if the file is close to 500 LOC already, add a `# noqa: WV4-TECHDEBT` comment and document in `docs/refactor/tech-debt.md` rather than splitting. Judgment call based on actual structure.

- [ ] Commit: `refactor(backend): split search/services.py into query and result modules`.

---

## Task 6: Document legitimate tech-debt exceptions

**Files:**
- Create or modify: `docs/refactor/tech-debt.md`

Files allowed to exceed 500 LOC with justification:
- `survival_handlers.py` (if still large after Wave 3) — Strategy pattern with 6 handler classes; splitting would scatter related code.
- Any file where the split made the code **less** clear rather than more — judgment call.

- [ ] **Step 1: Create or update the tech-debt register**

Create `docs/refactor/tech-debt.md` (or append to it if it exists):

```markdown
# Refactor Tech Debt Register

Files intentionally exceeding the 500-LOC rule from
`CLAUDE.md` after Wave 4 decomposition. Each entry has a
justification and a re-evaluation trigger.

## Backend

| File | Lines | Justification | Re-evaluate when |
|------|:-----:|---------------|------------------|
| (fill in during Wave 4 execution) | | | |

## Frontend

| File | Lines | Justification | Re-evaluate when |
|------|:-----:|---------------|------------------|
| (fill in during Wave 5 execution) | | | |
```

Fill in any files that remained over 500 LOC after Task 5 splits, with a concrete justification (not "too complex to split" — that's a symptom, not a reason).

- [ ] **Step 2: Commit**

```bash
git add docs/refactor/tech-debt.md
git commit -m "docs(refactor): register Wave 4 tech-debt exceptions

Documents any backend files still over 500 LOC after Wave 4
decomposition, with per-file justification and re-evaluation
triggers. Used by the Wave 4 exit criteria check.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Wave 4 exit verification

- [ ] **Step 1: Measure all backend files**

```bash
find backend/app -name "*.py" -exec wc -l {} \; | awk '$1 > 500 {print}' | sort -rn
```

Expected: at most 2 files over 500 LOC, each matching an entry in `docs/refactor/tech-debt.md`.

- [ ] **Step 2: Verify _sync_tasks is gone**

```bash
grep -rn "_sync_tasks" backend/app --include="*.py"
```

Expected: zero results (or only matches in comments documenting the migration).

- [ ] **Step 3: Verify PhenopacketRepository exists and is used**

```bash
grep -rn "from app.phenopackets.repositories" backend/app --include="*.py"
```

Expected: at least 2 import sites (service layer + any other consumer).

- [ ] **Step 4: Run full backend checks + HTTP surface verification**

```bash
cd backend && make check && uv run pytest tests/test_http_surface_baseline.py -k verify -v
```

Expected: all green.

- [ ] **Step 5: Verify bare-exceptions audit is still clean (Wave 1 regression check)**

```bash
grep -rn "except Exception" backend/app --include="*.py" | grep -v "# noqa"
```

Expected: zero results.

- [ ] **Step 6: Count tests**

```bash
cd backend && uv run pytest tests/ --collect-only -q 2>&1 | tail -5
```

Expected: ~783 (Wave 2's 765 + ~18 new in Wave 4).

- [ ] **Step 7: Write the wave-exit note**

Create `docs/refactor/wave-4-exit.md` summarizing: what landed per task, file sizes before/after, tech-debt register state, surprises, entry conditions for Wave 5.

- [ ] **Step 8: Commit**

```bash
git add docs/refactor/wave-4-exit.md
git commit -m "docs: add Wave 4 exit note

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

**Wave 4 is done when all 7 tasks (including Task 5 sub-tasks 5a-5g) are checked off and the exit note is committed.**

---

## Self-Review Notes

- **Spec coverage:** admin_endpoints split (Task 2), Redis task state (Task 2), PhenopacketRepository (Task 3), crud.py decomposition (Task 3), variant_validator split (Task 4), the 7 additional file splits from the re-baselined spec (Task 5a-5g), tech-debt register (Task 6), exit verification (Task 7).
- **HTTP surface safety:** every task that touches a router has a baseline-verify step. Task 1 sets up the mechanism.
- **Placeholder scan:** Task 5 sub-tasks 5a-5g are intentionally terse — they follow the same pattern repeatedly and the pattern is explicit at the top of Task 5. Each sub-task includes the expected split structure and a one-line commit message template. No `<fill in>` or `TODO` except in the wave-exit note template.
- **Known risks:** Task 3's `crud.py` split is the highest-risk item. Mitigation: Wave 2's integration tests + Task 1's HTTP baseline. If those two pass, the split is safe.
- **Out of order execution:** Tasks 4 and 5 are mostly independent of each other and could parallelize. Task 3 depends on Task 2 (sync service uses Redis from admin/task_state.py). Task 7 is the gate.
