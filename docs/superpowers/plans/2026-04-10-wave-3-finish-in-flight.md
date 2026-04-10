# Wave 3: Finish In-Flight Refactors — Implementation Plan (Amended 2026-04-10)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Amendment note (2026-04-10):** The original Wave 3 plan assumed the survival refactor was mid-flight: 6 handler classes (`VariantTypeCurrentAgeHandler`, `VariantTypeStandardHandler`, …), an active dispatcher still calling the legacy `_handle_*` functions, and a parity-gated deletion. None of that is accurate. The dispatcher at `survival.py:1006-1025` already uses `SurvivalHandlerFactory.get_handler(comparison).handle(db, endpoint_label, endpoint_hpo_terms)`. A `grep -rn "_handle_variant_type\|_handle_pathogenicity\|_handle_disease_subtype" backend` confirms the legacy functions have **zero callers** — they are orphaned dead code sharing a file with the live dispatcher. Age-mode split is internal to `SurvivalHandler.handle()` (branches on `endpoint_hpo_terms is None`), not a per-class distinction. Actual handler classes (survival_handlers.py): `VariantTypeHandler`, `PathogenicityHandler`, `DiseaseSubtypeHandler`, `ProteinDomainHandler` (net-new, no legacy equivalent), plus `SurvivalHandlerFactory`. This amendment drops the parity test task (comparing dead code to live code is meaningless), simplifies deletion to a straight prune, adds a thin endpoint regression smoke test (no endpoint-level test currently exists), and drops the original Task 8 (`materialized_view_fallback` context manager) as marginal-value churn — the existing `check_materialized_view_exists` one-liner helper is already the abstraction.

**Goal:** Delete the ~840 LOC of dead legacy handler code in `survival.py` (and its orphaned helpers), restructure survival into a `survival/` sub-package, sweep remaining hardcoded HPO literals, and extract the real `calculate_percentages` duplication from the 12 aggregation sites into `aggregations/common.py`.

**Architecture:** No new external dependencies. All changes are internal reorganization and deletion. Safety story is "zero callers + new endpoint smoke test" instead of parity testing, because the legacy code is already decoupled from the runtime.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy async, pytest.

**Parent spec:** `docs/superpowers/specs/2026-04-10-codebase-refactor-roadmap-design.md` (Wave 3 section)

**Prerequisite:** Waves 1 and 2 complete. Wave 2's dedicated test database and CRUD integration tests are the safety substrate.

**Branch:** `chore/wave-3-finish-in-flight` (worktree at `~/development/hnf1b-db.worktrees/chore-wave-3-finish-in-flight/` per the project's sibling-worktree convention).

---

## Context

Read Wave 1's "Context engineers need" section for conventions. This wave is all backend — no frontend changes.

**Key files:**
- Target of deletion: the 6 `_handle_*` functions in `backend/app/phenopackets/routers/aggregations/survival.py` (defined at lines 126, 230, 375, 467, 621, 748) and the 3 module-private helpers that only serve them (`_calculate_survival_curves`, `_calculate_statistical_tests`, `_build_response` at lines 56–123). Verify orphan status by grep before deleting the helpers.
- Canonical live path: `survival.py:1006-1025` → `SurvivalHandlerFactory.get_handler(...).handle(...)` in `survival_handlers.py` (1055 LOC, 4 handler classes + factory + abstract base).
- Restructuring target: `backend/app/phenopackets/routers/aggregations/survival/` (new sub-package).
- Extension target: `backend/app/phenopackets/routers/aggregations/common.py` (currently 63 LOC — `check_materialized_view_exists` helper + re-exports).
- Aggregation modules with `(count / total * 100) if total > 0` duplication (12 verified sites as of 2026-04-10): `demographics.py` (3), `diseases.py` (3), `variants.py` (2), `features.py` (2), `publications.py` (1), plus any in `summary.py`.

**Dead-code confirmation grep (run this first in Task 1):**
```bash
cd backend && grep -rn "_handle_variant_type\|_handle_pathogenicity\|_handle_disease_subtype" app tests --include="*.py"
```
Expected: matches only inside `survival.py` itself (the function definitions). Zero matches in dispatchers, tests, or any other module. If a match appears outside `survival.py`, STOP and investigate — the dead-code assumption is wrong.

---

## Task 1: Document the dead-code finding (migration map)

**Files:**
- Create: `docs/refactor/survival-migration-map.md`

No code changes. The engineer confirms the dead-code finding, documents the 1:1 mapping between legacy functions and the canonical handler methods, and records why parity testing is unnecessary.

- [ ] **Step 1: Run the dead-code grep**

```bash
cd backend && grep -rn "_handle_variant_type\|_handle_pathogenicity\|_handle_disease_subtype" app tests --include="*.py"
```

Expected: 6 matches, all inside `survival.py` (the function definitions themselves). If any match appears outside `survival.py`, STOP.

- [ ] **Step 2: Confirm the helper trio is also orphaned**

```bash
cd backend && grep -rn "_calculate_survival_curves\|_calculate_statistical_tests\|_build_response" app tests --include="*.py"
```

Expected: matches only inside `survival.py`, and only on the calling side from within the 6 dead `_handle_*` functions. (Note: `survival_handlers.py` has its own `_calculate_survival_curves` and `_calculate_statistical_tests` **as instance methods of `SurvivalHandler`** — these are different scope and do not count.) If the helpers are called from the live dispatcher or any other file, keep them in Task 3 and only delete the 6 handler functions.

- [ ] **Step 3: Read the live dispatcher**

```bash
sed -n '970,1026p' backend/app/phenopackets/routers/aggregations/survival.py
```

Confirm it already uses `SurvivalHandlerFactory.get_handler(comparison).handle(db, endpoint_label, endpoint_hpo_terms)` and never references the `_handle_*` functions.

- [ ] **Step 4: Read the handler class headers**

```bash
grep -n "^class " backend/app/phenopackets/routers/aggregations/survival_handlers.py
```

Expected classes: `SurvivalHandler(ABC)`, `VariantTypeHandler`, `PathogenicityHandler`, `DiseaseSubtypeHandler`, `ProteinDomainHandler`, `SurvivalHandlerFactory`.

- [ ] **Step 5: Write the migration map**

Create `docs/refactor/survival-migration-map.md`:

```markdown
# Survival Handler Migration Map

**Wave 3 reference document (2026-04-10).** Documents the relationship
between the 6 legacy `_handle_*` functions in `survival.py` and the
canonical `SurvivalHandler` subclasses in `survival_handlers.py`, and
records the zero-caller confirmation that makes Task 3's deletion safe.

## Dead-code confirmation

Grep output from `grep -rn "_handle_variant_type\|_handle_pathogenicity\|_handle_disease_subtype" backend/app backend/tests`:

```
<paste the actual grep output here>
```

All matches are function definitions inside `survival.py`. Zero callers
in the live dispatcher, endpoints, tests, or any other module. The
legacy functions are orphaned dead code.

## Why no parity tests

The original plan proposed byte-identical parity tests as a
deletion gate. That approach assumed the dispatcher was still calling
the legacy functions and that the new handler classes were an
untested parallel path. Both assumptions are wrong: the dispatcher has
already been migrated (see `survival.py:1006-1025`), the handler
classes are the only path the endpoint uses in production, and the
legacy functions are unreachable from any caller. Parity testing
would compare dead code to live code — the result is either "identical"
(wasted effort) or "different" (reveals the dead code drifted, which is
informative but doesn't block deletion because the dead code is
unreachable anyway).

The deletion safety story is instead:

1. **Zero callers** (this document, Task 1).
2. **Endpoint smoke test** added in Task 2 — exercises every comparison
   type through the live dispatcher, gives a regression signal for the
   handler classes themselves, and runs before and after Task 3's
   deletion.
3. **Full `make check`** before and after deletion.

## Handler mapping

The legacy functions split by comparison type × age-mode (6 functions).
The new handler classes split only by comparison type (4 classes,
including `ProteinDomainHandler` which has no legacy counterpart). Age
mode is an internal branch inside `SurvivalHandler.handle()`:

```python
async def handle(self, db, endpoint_label, endpoint_hpo_terms=None):
    if endpoint_hpo_terms is None:
        return await self._handle_current_age(db, endpoint_label)
    return await self._handle_standard(db, endpoint_label, endpoint_hpo_terms)
```

| Legacy function | survival.py line | Canonical handler | survival_handlers.py line |
|-----------------|:----------------:|-------------------|:------------------------:|
| `_handle_variant_type_current_age`   | 126 | `VariantTypeHandler._handle_current_age`   | via 273 |
| `_handle_variant_type_standard`      | 230 | `VariantTypeHandler._handle_standard`      | via 273 |
| `_handle_pathogenicity_current_age`  | 375 | `PathogenicityHandler._handle_current_age` | via 415 |
| `_handle_pathogenicity_standard`     | 467 | `PathogenicityHandler._handle_standard`    | via 415 |
| `_handle_disease_subtype_current_age`| 621 | `DiseaseSubtypeHandler._handle_current_age`| via 560 |
| `_handle_disease_subtype_standard`   | 748 | `DiseaseSubtypeHandler._handle_standard`   | via 560 |

`ProteinDomainHandler` (survival_handlers.py:826) is a net-new
comparison type that was added *after* the legacy functions. It has no
legacy equivalent. Nothing to migrate for it; just carry it through the
Task 4 sub-package restructure.

## Orphaned helper functions

These module-private helpers in `survival.py` are only called from the
dead `_handle_*` functions and should be deleted in Task 3 alongside
the handlers:

| Helper | survival.py lines | Used by |
|--------|:-----------------:|---------|
| `_calculate_survival_curves` | 56–68 | Dead handlers only (verify in Task 1 Step 2) |
| `_calculate_statistical_tests` | 71–96 | Dead handlers only (verify in Task 1 Step 2) |
| `_build_response` | 99–123 | Dead handlers only (verify in Task 1 Step 2) |

Note that `SurvivalHandler` in `survival_handlers.py` has its own
`_calculate_survival_curves` and `_calculate_statistical_tests` as
instance methods — these are in a different scope and are not
affected.

`_get_endpoint_config` (survival.py:30–53) is KEPT — it is called by
the live dispatcher at `survival.py:1008`.
```

- [ ] **Step 6: Commit the map**

```bash
git add docs/refactor/survival-migration-map.md
git commit -m "$(cat <<'EOF'
docs(refactor): map survival legacy functions to handler classes

Task 1 of Wave 3: records the zero-caller confirmation for the 6
legacy _handle_* functions in survival.py and the 3 orphaned
module-private helpers (_calculate_survival_curves,
_calculate_statistical_tests, _build_response). Documents why
parity testing is unnecessary — the dispatcher is already on the
SurvivalHandlerFactory path, and the legacy functions are
unreachable from any live caller.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add survival endpoint regression smoke test

**Files:**
- Create: `backend/tests/test_survival_endpoint.py`

The existing survival tests (`test_survival_analysis.py` for pure functions, `test_survival_protein_domain.py` for handler registration + unit tests) do not exercise the `/survival-data` endpoint itself. Before deleting ~900 LOC of dead code in Task 3, we add a thin smoke test that goes through the live dispatcher for every comparison type × endpoint combination. On an empty test DB the `groups` list will be empty, but the response shape is fully exercised and any import/wiring break will fail loudly.

- [ ] **Step 1: Write the smoke test**

Create `backend/tests/test_survival_endpoint.py`:

```python
"""Smoke tests for the /survival-data endpoint.

Exercises the live SurvivalHandlerFactory dispatch path for every
supported comparison × endpoint combination. On an empty test
database, the `groups` list will be empty, but the response shape,
imports, factory wiring, and SQL generation are all exercised. This
is the regression safety net for Wave 3's deletion of the legacy
_handle_* functions.

This test does NOT assert numeric survival curves — for that, see the
pure-function tests in test_survival_analysis.py.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

COMPARISONS = ["variant_type", "pathogenicity", "disease_subtype", "protein_domain"]
ENDPOINTS = ["ckd_stage_3_plus", "stage_5_ckd", "any_ckd", "current_age"]


@pytest.mark.asyncio
class TestSurvivalEndpointSmoke:
    """Exercise every (comparison, endpoint) pair through the live dispatcher."""

    @pytest.mark.parametrize("comparison", COMPARISONS)
    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    async def test_returns_well_formed_response(
        self, client: AsyncClient, comparison: str, endpoint: str
    ) -> None:
        """Every (comparison, endpoint) pair returns a 200 with the expected shape."""
        response = await client.get(
            "/api/v2/phenopackets/aggregate/survival-data",
            params={"comparison": comparison, "endpoint": endpoint},
        )
        assert response.status_code == 200, response.text

        body = response.json()
        assert body["comparison_type"] == comparison
        assert "endpoint" in body
        assert "groups" in body
        assert isinstance(body["groups"], list)
        assert "statistical_tests" in body
        assert isinstance(body["statistical_tests"], list)
        assert "metadata" in body
        assert isinstance(body["metadata"], dict)
        # Metadata always carries the group definitions and criteria
        assert "group_definitions" in body["metadata"]
        assert "inclusion_criteria" in body["metadata"]

    async def test_invalid_comparison_returns_error(self, client: AsyncClient) -> None:
        """Unknown comparison types surface a 4xx/5xx, not a 200 with garbage."""
        response = await client.get(
            "/api/v2/phenopackets/aggregate/survival-data",
            params={"comparison": "not_a_real_type", "endpoint": "ckd_stage_3_plus"},
        )
        assert response.status_code >= 400

    async def test_invalid_endpoint_returns_error(self, client: AsyncClient) -> None:
        """Unknown endpoint values surface a 4xx/5xx, not a 200 with garbage."""
        response = await client.get(
            "/api/v2/phenopackets/aggregate/survival-data",
            params={"comparison": "variant_type", "endpoint": "not_a_real_endpoint"},
        )
        assert response.status_code >= 400
```

- [ ] **Step 2: Verify the correct endpoint path**

```bash
cd backend && grep -rn "survival-data\|/aggregate/survival" app --include="*.py" | head -5
```

The test assumes the path is `/api/v2/phenopackets/aggregate/survival-data`. If the aggregations router is mounted under a different prefix, update the `client.get(...)` URL in the test. If the prefix includes `/aggregations/` (plural), use that.

- [ ] **Step 3: Verify the `client` fixture exists**

```bash
cd backend && grep -n "def client\|async def client\|@pytest.fixture" tests/conftest.py | head -10
```

Most of the backend integration tests (e.g., `test_phenopackets_crud.py` from Wave 2) use an async HTTP client fixture. Use the same fixture name the existing tests use. If it's named differently (e.g., `async_client`, `api_client`), rename in the new test file. If no async fixture exists, copy the pattern from `test_phenopackets_crud.py`.

- [ ] **Step 4: Run the new test**

```bash
cd backend && uv run pytest tests/test_survival_endpoint.py -v
```

Expected: all 16 parametrized cases + 2 error cases pass (18 total). If any case fails:
- A 500 error may indicate an unhandled `ValueError` from the dispatcher. The dispatcher at `survival.py:1021` wraps `get_handler` errors in `ValueError`. If FastAPI returns 500 on `ValueError`, the smoke test should tolerate that (the "4xx/5xx" assertion handles both). But if the factory raises something else entirely, investigate.
- A 404 probably means the endpoint path is wrong — go back to Step 2.
- A parameter validation error may mean the comparison/endpoint strings don't match the dispatcher's expected values — double-check against `_get_endpoint_config()` keys in `survival.py:30`.

- [ ] **Step 5: Run the full backend check to confirm no regression**

```bash
cd backend && make check
```

Expected: 794 + ~18 = ~812 passing, 0 failures.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_survival_endpoint.py
git commit -m "$(cat <<'EOF'
test(backend): add /survival-data endpoint smoke tests

Wave 3 Task 2: exercises the live SurvivalHandlerFactory dispatch
path for every supported (comparison, endpoint) pair, plus error
cases for unknown comparison/endpoint values. On an empty test DB
the groups list is empty, but the response shape, imports, factory
wiring, and SQL generation are all covered.

This is the regression safety net for the Task 3 deletion of the
dead legacy _handle_* functions — if the dispatcher or any handler
wiring breaks, these tests fail before the deletion ships.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Delete the dead legacy functions

**Files:**
- Modify: `backend/app/phenopackets/routers/aggregations/survival.py` (delete the 6 `_handle_*` functions and the 3 orphaned helpers if Task 1 Step 2 confirmed they are dead)

Only proceed if Task 1 Step 1 and Step 2 were green (zero external callers).

- [ ] **Step 1: Verify once more before touching the file**

```bash
cd backend && grep -rn "_handle_variant_type\|_handle_pathogenicity\|_handle_disease_subtype" app tests --include="*.py"
```

Expected: only the 6 `async def _handle_*` definitions in `survival.py`. If anything else shows up, STOP and reconcile.

- [ ] **Step 2: Delete the 6 `_handle_*` functions**

Use the Read tool to find the exact bounds of each function (name lookup, not line numbers — line numbers shift as you edit). The 6 functions live in this order in `survival.py`:

```
async def _handle_variant_type_current_age(db, endpoint_label):
async def _handle_variant_type_standard(db, endpoint_label):
async def _handle_pathogenicity_current_age(db, endpoint_label):
async def _handle_pathogenicity_standard(db, endpoint_label):
async def _handle_disease_subtype_current_age(db, endpoint_label):
async def _handle_disease_subtype_standard(db, endpoint_label):
```

Each function ends immediately before the next `async def`, or (for the last one) before the `@router.get("/survival-data", ...)` decorator at approximately line 971. Delete all 6 function bodies.

- [ ] **Step 3: Delete the orphaned helpers (if Task 1 confirmed them dead)**

Only if Task 1 Step 2 confirmed they are orphaned, delete these three helpers from `survival.py`:

- `_calculate_survival_curves` (lines 56–68)
- `_calculate_statistical_tests` (lines 71–96)
- `_build_response` (lines 99–123)

The imports `apply_bonferroni_correction`, `calculate_log_rank_test`, `parse_iso8601_age`, `calculate_kaplan_meier`, `get_phenopacket_variant_link_cte`, `get_variant_type_classification_sql`, `CURRENT_AGE_PATH`, `INTERP_STATUS_PATH` may also become unused after the deletion — run ruff or mypy to find any that `survival.py` no longer needs, then delete them.

**Keep** `_get_endpoint_config` (lines 30–53). It is called by the live dispatcher at line 1008.

- [ ] **Step 4: Run the full backend check**

```bash
cd backend && make check
```

Expected: still all green, including the new Task 2 smoke tests. If anything fails, the dead-code assumption was wrong somewhere — revert the deletion (`git restore backend/app/phenopackets/routers/aggregations/survival.py`), investigate which file still references the deleted symbol, and either (a) also migrate that caller off the legacy path or (b) restore the specific function.

- [ ] **Step 5: Verify the file shrank and contains only router + dispatcher**

```bash
wc -l backend/app/phenopackets/routers/aggregations/survival.py
```

Expected: ~120–160 LOC (was 1025). The file should now contain only: imports, `_get_endpoint_config`, and the `get_survival_data` router endpoint.

- [ ] **Step 6: Commit**

```bash
git add backend/app/phenopackets/routers/aggregations/survival.py
git commit -m "$(cat <<'EOF'
refactor(backend): delete dead legacy survival handler functions

Removes the 6 _handle_* functions and 3 orphaned module-private
helpers (_calculate_survival_curves, _calculate_statistical_tests,
_build_response) from survival.py. These were unreachable from any
live caller — the dispatcher at survival.py:1006 has been on the
SurvivalHandlerFactory path for some time, and the legacy functions
were orphaned dead code sharing a file with it.

survival.py shrinks from 1,025 LOC to ~140 LOC. The file now contains
only the router endpoint and its _get_endpoint_config helper.

See docs/refactor/survival-migration-map.md for the dead-code audit
and why no parity test was needed. The Wave 3 Task 2 endpoint smoke
tests added in the previous commit exercise the live dispatcher path
and guard against regressions in the handler classes themselves.

Closes P2 #6 from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Restructure survival into a `survival/` sub-package

**Files:**
- Create: `backend/app/phenopackets/routers/aggregations/survival/__init__.py`
- Create: `backend/app/phenopackets/routers/aggregations/survival/router.py`
- Create: `backend/app/phenopackets/routers/aggregations/survival/handlers.py` (or a `handlers/` sub-package if it exceeds 500 LOC after the move)
- Delete: `backend/app/phenopackets/routers/aggregations/survival.py` (moved to `survival/router.py`)
- Delete: `backend/app/phenopackets/routers/aggregations/survival_handlers.py` (moved to `survival/handlers.py`)

Post-Task-3, `survival.py` is ~140 LOC and `survival_handlers.py` is 1055 LOC. The sub-package layout depends on whether `handlers.py` can live as a single file (≤500 LOC target per CLAUDE.md's 500-line rule) or needs splitting.

- [ ] **Step 1: Create the sub-package directory**

```bash
cd backend && mkdir -p app/phenopackets/routers/aggregations/survival
touch app/phenopackets/routers/aggregations/survival/__init__.py
```

- [ ] **Step 2: Move router code to `survival/router.py`**

```bash
cd backend && git mv app/phenopackets/routers/aggregations/survival.py app/phenopackets/routers/aggregations/survival/router.py
```

Then open `router.py` and update the import:

```python
# Before (at the bottom of the endpoint function):
from .survival_handlers import SurvivalHandlerFactory

# After:
from .handlers import SurvivalHandlerFactory
```

Note the `.` is now a single level — `router.py` is inside `survival/`, and `handlers.py` is a sibling. No changes to `sql_fragments` import — that's still in the parent `aggregations/` package, so `from ..sql_fragments import ...`.

- [ ] **Step 3: Move handler code to `survival/handlers.py`**

```bash
cd backend && git mv app/phenopackets/routers/aggregations/survival_handlers.py app/phenopackets/routers/aggregations/survival/handlers.py
```

Then open `handlers.py` and fix imports. The old file imported `from .sql_fragments import ...` (same package); the new location is one level deeper, so:

```python
# Before:
from .sql_fragments import (
    CURRENT_AGE_PATH,
    HNF1B_PROTEIN_DOMAINS,
    ...
)

# After:
from ..sql_fragments import (
    CURRENT_AGE_PATH,
    HNF1B_PROTEIN_DOMAINS,
    ...
)
```

Same for any other parent-package imports (e.g., `from app.core.config import settings` is fine unchanged because it's absolute; only the relative `.sql_fragments` needs updating).

- [ ] **Step 4: Wire the sub-package's `__init__.py` for backwards-compat re-exports**

```python
# backend/app/phenopackets/routers/aggregations/survival/__init__.py
"""Survival analysis sub-package.

Public API re-exports mirror the old flat-file module paths so that
any remaining `from app.phenopackets.routers.aggregations.survival
import ...` callers keep working.
"""
from .router import router
from .handlers import (
    DiseaseSubtypeHandler,
    PathogenicityHandler,
    ProteinDomainHandler,
    SurvivalHandler,
    SurvivalHandlerFactory,
    VariantTypeHandler,
)

__all__ = [
    "router",
    "SurvivalHandler",
    "SurvivalHandlerFactory",
    "VariantTypeHandler",
    "PathogenicityHandler",
    "DiseaseSubtypeHandler",
    "ProteinDomainHandler",
]
```

- [ ] **Step 5: Fix any parent imports that referenced the old flat paths**

```bash
cd backend && grep -rn "from app.phenopackets.routers.aggregations.survival_handlers\|from .survival_handlers\|import survival_handlers" app tests --include="*.py"
```

Every match needs updating to the new path (either `from .survival import SurvivalHandlerFactory` via re-export, or the direct `.survival.handlers` path). The existing test `tests/test_survival_protein_domain.py:28` imports from `survival_handlers` — update it.

```bash
cd backend && grep -rn "from app.phenopackets.routers.aggregations import survival\|from .survival import\|import aggregations.survival" app tests --include="*.py"
```

These imports hit the package, not the flat file, and should continue to work via the `__init__.py` re-exports. Verify by running tests.

Also check `aggregations/__init__.py` or any central router that wires `survival.router` into the app:

```bash
cd backend && grep -rn "survival" app/phenopackets/routers/aggregations/__init__.py app/phenopackets/routers/__init__.py app/main.py 2>/dev/null
```

Update if any file imports `from .survival import router` or similar — the `__init__.py` re-export makes this work unchanged, but confirm.

- [ ] **Step 6: Run the full backend check**

```bash
cd backend && make check
```

Expected: still all green. Any import error here means Step 5's sweep missed a caller — fix and re-run.

- [ ] **Step 7: Check `handlers.py` line count and decide whether to split**

```bash
wc -l backend/app/phenopackets/routers/aggregations/survival/handlers.py
```

- **If ≤ 500 LOC:** Keep it as a single file. Task 4 is done.
- **If > 500 LOC:** Split by handler family. Create `survival/handlers/` as a sub-package with `base.py` (`SurvivalHandler` ABC + `SurvivalHandlerFactory`), `variant_type.py` (`VariantTypeHandler`), `pathogenicity.py` (`PathogenicityHandler`), `disease_subtype.py` (`DiseaseSubtypeHandler`), `protein_domain.py` (`ProteinDomainHandler`). Re-export everything from `survival/handlers/__init__.py` so the `survival/__init__.py` re-exports still work.

Current state (pre-Task-3) is 1055 LOC; after deleting the docstring-level HPO literal at line 239 (Task 5) and any other Task-3 cleanup, expect ~1050 LOC — the split will likely be needed.

- [ ] **Step 8: If split was needed, run `make check` again and update `survival/__init__.py` re-exports**

```bash
cd backend && make check
```

- [ ] **Step 9: Verify every file in the sub-package is under 500 LOC**

```bash
find backend/app/phenopackets/routers/aggregations/survival -name "*.py" -exec wc -l {} \;
```

Expected: all files under 500 LOC.

- [ ] **Step 10: Commit**

```bash
git add backend/app/phenopackets/routers/aggregations/survival/ backend/app/phenopackets/routers/aggregations/__init__.py backend/tests/test_survival_protein_domain.py
git commit -m "$(cat <<'EOF'
refactor(backend): restructure survival into a sub-package

Moves the survival analysis code from two flat files (survival.py
and survival_handlers.py) into a proper sub-package:

  survival/
    __init__.py       (public re-exports — backwards compat)
    router.py         (FastAPI endpoint and _get_endpoint_config)
    handlers.py       (SurvivalHandler + 4 concrete handlers +
                       SurvivalHandlerFactory; split into
                       handlers/<family>.py if >500 LOC)

Every file is under 500 LOC. Callers using
`from app.phenopackets.routers.aggregations import survival`
continue to work via the __init__.py re-exports. The one internal
import in tests/test_survival_protein_domain.py was updated to the
new path.

Closes P5 #23 from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Sweep remaining hardcoded HPO literals

**Files:**
- Modify: `backend/app/phenopackets/routers/aggregations/survival/handlers.py` (or the split handler family files if Task 4 Step 7 split them)
- Modify: `backend/app/phenopackets/routers/aggregations/diseases.py`

After Task 3 deletes the ~840 LOC of dead code, the vast majority of hardcoded `HP:NNNNNNN` literals in `survival.py` are gone (they lived inside the deleted functions). This task is a surgical sweep for the few remaining literals.

- [ ] **Step 1: Find all remaining literals**

```bash
cd backend && grep -rn "HP:[0-9]\{7\}" app/phenopackets/routers/aggregations/ 2>/dev/null
```

Expected (as of 2026-04-10 baseline, accounting for the Task 3 deletion):
- `survival/handlers.py:239` — one literal inside a metadata docstring string (`"Kidney failure: CKD Stage 4 (HP:0012626) or Stage 5/ESRD (HP:0003774)"`). This is a human-readable description, **not** SQL logic — it's shown to the user in the `event_definition` metadata field.
- `diseases.py:103` — one literal `'HP:0012622'` in raw SQL.
- Any others that surface — investigate each.

- [ ] **Step 2: Decide on the docstring literal**

The `event_definition` metadata string is user-facing. Three options:

1. **Leave it alone** — it's documentation, not logic. Pros: simple, no code change. Cons: a Wave 3 exit check might flag it.
2. **Interpolate from settings** — `f"Kidney failure: CKD Stage 4 ({settings.hpo_terms.ckd_stage_4}) or Stage 5/ESRD ({settings.hpo_terms.stage_5_ckd})"`. Pros: single source of truth. Cons: slightly more complex.
3. **Move the human-readable string to config.yaml** — overkill.

**Choose option 2** if `settings.hpo_terms.ckd_stage_4` and `settings.hpo_terms.stage_5_ckd` already exist. Otherwise fall back to option 1 and document the exception in the wave exit note.

```bash
grep -n "ckd_stage_4\|stage_5_ckd" backend/app/core/config.py backend/config.yaml 2>/dev/null
```

- [ ] **Step 3: Fix `diseases.py:103`**

```bash
cd backend && sed -n '95,110p' app/phenopackets/routers/aggregations/diseases.py
```

Read the surrounding context. The literal `'HP:0012622'` appears to be a kidney-related term. Find its constant name in `settings.hpo_terms.*`:

```bash
grep -n "HP:0012622" backend/config.yaml 2>/dev/null
grep -n "HP:0012622" backend/app/core/config.py 2>/dev/null
```

If it's in the config, replace the literal with `settings.hpo_terms.<name>`. If it's missing from the config, add it to `config.yaml` and the `HPOTermsConfig` model in `config.py`, then reference it.

- [ ] **Step 4: Run the backend check**

```bash
cd backend && make check
```

Expected: still all green. Aggregation endpoints should return identical output — only the source of the HPO IDs changed.

- [ ] **Step 5: Verify the sweep**

```bash
cd backend && grep -rn "HP:[0-9]\{7\}" app/phenopackets/routers/aggregations/ 2>/dev/null
```

Expected: zero matches, OR matches only inside clearly-labeled docstrings/comments (Step 2 option 1).

- [ ] **Step 6: Commit**

```bash
git add backend/app/phenopackets/routers/aggregations/ backend/app/core/config.py backend/config.yaml
git commit -m "$(cat <<'EOF'
refactor(backend): sweep remaining hardcoded HPO IDs

Replaces the last HP:NNNNNNN literals in the aggregations sub-tree
with settings.hpo_terms.* references. Most literals lived inside
the dead code deleted in Task 3 and went away with it; this task
handles the survivors:

- survival/handlers.py event_definition metadata string
  (interpolated from settings)
- diseases.py raw SQL literal

Closes P3 #16 from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Extract `calculate_percentages` helper to `aggregations/common.py`

**Files:**
- Modify: `backend/app/phenopackets/routers/aggregations/common.py`
- Create: `backend/tests/test_aggregations_common.py`
- Modify: `backend/app/phenopackets/routers/aggregations/demographics.py`
- Modify: `backend/app/phenopackets/routers/aggregations/variants.py`
- Modify: `backend/app/phenopackets/routers/aggregations/features.py`
- Modify: `backend/app/phenopackets/routers/aggregations/diseases.py`
- Modify: `backend/app/phenopackets/routers/aggregations/publications.py`

This is the real DRY win. As of 2026-04-10, `grep -n "/ total \* 100.*if total > 0"` finds 12 call sites across 5 files:

| File | Sites |
|------|:-----:|
| `demographics.py` | 3 (lines 48, 78, 115) |
| `diseases.py` | 3 (lines 48, 82, 120) |
| `variants.py` | 2 (lines 89, 173) |
| `features.py` | 2 (lines 56, 109) |
| `publications.py` | 1 (line 57) |

Each site mixes two input shapes: plain dict rows (`row["count"]`) and SQLAlchemy row-mapping rows (`row._mapping["count"]`). The helper must handle both.

- [ ] **Step 1: Write the tests first**

Create `backend/tests/test_aggregations_common.py`:

```python
"""Tests for the helpers in aggregations/common.py (Wave 3 additions)."""

import pytest

from app.phenopackets.routers.aggregations.common import calculate_percentages


class _FakeMappingRow:
    """Mimic a SQLAlchemy Row that exposes ._mapping and __getitem__."""

    def __init__(self, **fields):
        self._mapping = fields

    def __getitem__(self, key):
        return self._mapping[key]


class TestCalculatePercentages:
    def test_basic_percentages_with_dict_rows(self):
        rows = [{"count": 50}, {"count": 30}, {"count": 20}]
        result = calculate_percentages(rows, total=100)
        assert [r["percentage"] for r in result] == [50.0, 30.0, 20.0]

    def test_basic_percentages_with_mapping_rows(self):
        rows = [_FakeMappingRow(count=75), _FakeMappingRow(count=25)]
        result = calculate_percentages(rows, total=100)
        assert [r["percentage"] for r in result] == [75.0, 25.0]

    def test_mixed_input_shapes(self):
        rows = [{"count": 40}, _FakeMappingRow(count=60)]
        result = calculate_percentages(rows, total=100)
        assert [r["percentage"] for r in result] == [40.0, 60.0]

    def test_total_zero_returns_zero_percentages(self):
        rows = [{"count": 10}, {"count": 5}]
        result = calculate_percentages(rows, total=0)
        for row in result:
            assert row["percentage"] == 0

    def test_preserves_other_fields(self):
        rows = [
            {"count": 10, "label": "alpha", "group": "a"},
            {"count": 90, "label": "beta", "group": "b"},
        ]
        result = calculate_percentages(rows, total=100)
        assert result[0]["label"] == "alpha"
        assert result[0]["group"] == "a"
        assert result[1]["label"] == "beta"
        assert result[1]["group"] == "b"

    def test_preserves_other_fields_from_mapping_row(self):
        rows = [_FakeMappingRow(count=10, label="alpha")]
        result = calculate_percentages(rows, total=10)
        assert result[0]["label"] == "alpha"
        assert result[0]["percentage"] == 100.0

    def test_does_not_mutate_dict_input(self):
        rows = [{"count": 10}]
        calculate_percentages(rows, total=100)
        assert "percentage" not in rows[0]

    def test_empty_input(self):
        assert calculate_percentages([], total=100) == []

    def test_custom_count_key(self):
        rows = [{"present_count": 40, "label": "a"}]
        result = calculate_percentages(rows, total=100, count_key="present_count")
        assert result[0]["percentage"] == 40.0
        assert result[0]["present_count"] == 40

    def test_rejects_unknown_row_shape(self):
        """Non-dict, non-mapping rows should raise, not silently hoover attrs."""
        class Opaque:
            count = 10

        with pytest.raises((TypeError, AttributeError)):
            calculate_percentages([Opaque()], total=100)
```

- [ ] **Step 2: Run to confirm fail**

```bash
cd backend && uv run pytest tests/test_aggregations_common.py -v
```

Expected: FAIL on import — `calculate_percentages` does not exist in `common.py`.

- [ ] **Step 3: Add `calculate_percentages` to `common.py`**

Open `backend/app/phenopackets/routers/aggregations/common.py`. Add after the existing `check_materialized_view_exists` function:

```python
def calculate_percentages(
    rows: List[Any],
    total: int,
    count_key: str = "count",
) -> List[Dict[str, Any]]:
    """Add a 'percentage' field to each row based on (count / total) * 100.

    Accepts either plain dict rows or SQLAlchemy row objects with a
    ``._mapping`` attribute. Any other row shape raises TypeError so the
    caller notices, instead of silently hoovering attributes via ``dir()``.

    Returns a new list of new dicts — the input rows are not mutated.

    Args:
        rows: Sequence of query result rows (dict or SQLAlchemy Row).
        total: Denominator for percentage calculation. If 0, percentage is 0.
        count_key: Field name holding the count (default "count").

    Returns:
        List of new dicts with every original field plus ``percentage``.

    Raises:
        TypeError: If any row is neither a dict nor exposes ``._mapping``.
    """
    result: List[Dict[str, Any]] = []
    for row in rows:
        if hasattr(row, "_mapping"):
            data = dict(row._mapping)
        elif isinstance(row, dict):
            data = dict(row)
        else:
            raise TypeError(
                f"calculate_percentages expects dict or SQLAlchemy Row, "
                f"got {type(row).__name__}"
            )

        count_value = int(data.get(count_key, 0))
        data["percentage"] = (count_value / total * 100) if total > 0 else 0
        result.append(data)
    return result
```

Add `"calculate_percentages"` to `common.py`'s `__all__` list.

- [ ] **Step 4: Run the tests**

```bash
cd backend && uv run pytest tests/test_aggregations_common.py -v
```

Expected: all 10 pass. If a test fails, adjust the helper to match — the tests are the spec.

- [ ] **Step 5: Replace duplicated code in `demographics.py`, `diseases.py`, `variants.py`, `features.py`, `publications.py`**

For each file, find every occurrence of the inline calculation:

```python
percentage=(int(row["count"]) / total * 100) if total > 0 else 0,
# or
percentage=(int(row._mapping["count"]) / total * 100) if total > 0 else 0,
# or the features.py variant using "present_count"
```

The call sites usually look like this:

```python
return AggregationResult(
    items=[
        dict(
            row._mapping,
            percentage=(int(row._mapping["count"]) / total * 100) if total > 0 else 0,
        )
        for row in rows
    ],
    total=total,
)
```

Replace with:

```python
from .common import calculate_percentages

# ... inside the endpoint:
rows_with_percentages = calculate_percentages(rows, total=total)
return AggregationResult(
    items=rows_with_percentages,
    total=total,
)
```

For `features.py` (which uses `count_key="present_count"`):

```python
rows_with_percentages = calculate_percentages(rows, total=total, count_key="present_count")
```

Handle each site individually — some sites may have additional fields being computed in the same comprehension that can't be replaced wholesale. In those cases, call `calculate_percentages` first and then layer the extra fields on top.

- [ ] **Step 6: Run the full backend check**

```bash
cd backend && make check
```

Expected: all green. Aggregation endpoint tests should return identical output — the JSON response shape is unchanged, only the source of the `percentage` field moved.

- [ ] **Step 7: Verify duplication is reduced**

```bash
cd backend && grep -rn "/ total \* 100.*if total > 0" app/phenopackets/routers/aggregations/ 2>/dev/null | wc -l
```

Expected: 2 or fewer. (Down from 12. A couple may remain if a call site was complex enough to justify keeping inline — document any survivors in the wave exit note.)

- [ ] **Step 8: Commit**

```bash
git add backend/app/phenopackets/routers/aggregations/common.py backend/app/phenopackets/routers/aggregations/demographics.py backend/app/phenopackets/routers/aggregations/diseases.py backend/app/phenopackets/routers/aggregations/variants.py backend/app/phenopackets/routers/aggregations/features.py backend/app/phenopackets/routers/aggregations/publications.py backend/tests/test_aggregations_common.py
git commit -m "$(cat <<'EOF'
refactor(backend): extract percentage calculation to aggregations/common

Adds calculate_percentages() to common.py and replaces ~12 inline
(int(row[count_key]) / total * 100) if total > 0 else 0 sites across
demographics, diseases, variants, features, and publications. The
helper accepts plain dict rows and SQLAlchemy Row._mapping rows and
raises TypeError on anything else (no silent attribute hoovering).

Companion test file covers both row shapes, mixed input, custom
count_key (for features.py's present_count), empty input, total=0,
field preservation, and the fail-loud rejection of unknown shapes.

Closes P3 #13 from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Wave 3 exit verification

- [ ] **Step 1: Run full backend check one last time**

```bash
cd backend && make check
```

Expected: ~814+ tests passing (baseline 794 + ~18 new smoke tests + ~10 new common helper tests), 0 failures.

- [ ] **Step 2: Verify the flat survival files are gone**

```bash
ls backend/app/phenopackets/routers/aggregations/survival.py 2>&1
ls backend/app/phenopackets/routers/aggregations/survival_handlers.py 2>&1
ls -la backend/app/phenopackets/routers/aggregations/survival/
```

Expected: first two `ls` commands report "No such file"; the third lists the sub-package contents.

- [ ] **Step 3: Verify no hardcoded HPO IDs in the aggregation tree**

```bash
grep -rn "HP:[0-9]\{7\}" backend/app/phenopackets/routers/aggregations/ 2>/dev/null
```

Expected: zero matches (or, if Task 5 Step 2 chose option 1, matches only inside clearly-labeled docstrings — document the exceptions in the exit note).

- [ ] **Step 4: Verify `common.py` has the new helper**

```bash
grep -n "def calculate_percentages" backend/app/phenopackets/routers/aggregations/common.py
```

Expected: 1 match.

- [ ] **Step 5: Verify duplication is reduced**

```bash
grep -rn "/ total \* 100.*if total > 0" backend/app/phenopackets/routers/aggregations/ | wc -l
```

Expected: ≤ 2 (down from 12).

- [ ] **Step 6: Verify every file in the survival sub-package is under 500 LOC**

```bash
find backend/app/phenopackets/routers/aggregations/survival -name "*.py" -exec wc -l {} \;
```

Expected: every file ≤ 500 LOC.

- [ ] **Step 7: Write the exit note**

Create `docs/refactor/wave-3-exit.md`:

```markdown
# Wave 3 Exit Note

**Date:** <YYYY-MM-DD>
**Branch:** `chore/wave-3-finish-in-flight` (worktree at `~/development/hnf1b-db.worktrees/chore-wave-3-finish-in-flight/`)
**Starting test counts:** backend 794 passed + 1 skipped + 3 xfailed (post Wave 2 merge).
**Ending test counts:** backend <N> passed (+smoke tests, +common helper tests).

## What landed

- **Task 1** (`<commit>`): Survival migration map documenting the dead-code finding — the 6 legacy `_handle_*` functions had zero callers and were orphaned dead code sharing a file with the live `SurvivalHandlerFactory` dispatcher. Parity tests were unnecessary because the legacy path was already dead.
- **Task 2** (`<commit>`): `tests/test_survival_endpoint.py` — endpoint smoke tests for every (comparison, endpoint) pair plus error cases. <N> parametrized tests. Runs through the live dispatcher and guards the handler classes.
- **Task 3** (`<commit>`): Deleted 6 `_handle_*` functions + 3 orphaned module-private helpers from `survival.py`. File shrank from 1,025 LOC to <N> LOC.
- **Task 4** (`<commit>`): Restructured into `survival/` sub-package (`router.py`, `handlers.py` or `handlers/<family>.py`). Every file under 500 LOC. `__init__.py` re-exports maintain backwards compatibility for existing `from ...aggregations.survival import ...` callers.
- **Task 5** (`<commit>`): Swept the remaining hardcoded HPO literals from `survival/handlers.py` docstring metadata and `diseases.py` raw SQL, replacing with `settings.hpo_terms.*` references.
- **Task 6** (`<commit>`): `calculate_percentages()` helper extracted to `common.py`. Replaced <N> of 12 inline sites across 5 aggregation modules. Companion test file with <N> tests.

## What was deferred

- The original plan's Task 8 (`materialized_view_fallback` context manager) was dropped during the 2026-04-10 amendment as marginal-value churn — the existing `check_materialized_view_exists` one-liner is already the abstraction and wrapping it in a context manager adds ceremony without clear benefit.
- <anything else>

## Surprises

- <fill in during execution>

## Entry conditions for Wave 4

- [x] `survival/` sub-package is the single canonical location for survival logic. The 1,025 LOC flat-file `survival.py` and the 1,055 LOC flat-file `survival_handlers.py` are gone.
- [x] Aggregation modules share the `calculate_percentages` helper in `common.py`. Inline duplication reduced from 12 sites to ≤ 2.
- [x] No hardcoded HPO IDs remain in the aggregations sub-tree (or only labeled exceptions in docstrings).
- [x] All backend tests green (<N> passing).
- [x] Endpoint smoke tests guard the survival handler classes.
- [x] Ready for Wave 4 backend decomposition (`admin_endpoints.py`, `crud.py`, etc).

**Wave 4 can begin.**
```

- [ ] **Step 8: Commit the exit note**

```bash
git add docs/refactor/wave-3-exit.md
git commit -m "docs: add Wave 3 exit note

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

**Wave 3 is done when all 7 tasks are checked off and the exit note is committed.** After that, use `superpowers:finishing-a-development-branch` to decide merge strategy (PR vs. direct merge).

---

## Self-Review Notes (Amended)

- **Spec coverage:** Deleting legacy handlers (Task 3), restructuring into sub-package (Task 4), replacing hardcoded HPO IDs (Task 5), extending `common.py` with `calculate_percentages` (Task 6). Every non-dropped Wave 3 item from the spec is covered.
- **Dropped from original plan:**
  - Old Task 3 (parity tests) — legacy code is already dead, parity between dead and live code is meaningless.
  - Old Task 8 (`materialized_view_fallback` context manager) — the existing `check_materialized_view_exists` one-liner is already the abstraction.
- **Added to amended plan:**
  - New Task 2 (endpoint smoke tests) — replaces parity testing as the deletion safety net. Exercises the live dispatcher for every (comparison, endpoint) pair.
- **Placeholder scan:** Only `<fill in>` in the exit note template and the migration map dead-code grep output slot.
- **Type/name consistency:** Real class names verified against `survival_handlers.py` — `VariantTypeHandler`, `PathogenicityHandler`, `DiseaseSubtypeHandler`, `ProteinDomainHandler`, `SurvivalHandler` (ABC), `SurvivalHandlerFactory`. No `*CurrentAgeHandler` or `*StandardHandler` classes exist.
- **Known risks:**
  - Task 4 Step 7: `handlers.py` may need splitting if post-move it's still >500 LOC. Explicitly addressed with a fallback sub-module structure.
  - Task 2: the existing `client` async fixture name may differ from the one in `test_phenopackets_crud.py` — Step 3 calls this out.
  - Task 5 Step 2: the docstring literal decision (leave vs. interpolate) depends on whether `settings.hpo_terms.ckd_stage_4` exists — Step 2 asks to check before committing to an approach.
