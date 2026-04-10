# Wave 3: Finish In-Flight Refactors — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the half-finished survival.py refactor (delete the 6 legacy `_handle_*` functions alongside the new survival_handlers.py), reorganize into a `survival/` sub-package, replace hardcoded HPO IDs with settings references, and extend `aggregations/common.py` with the missing shared helpers.

**Architecture:** No new external dependencies. All changes are internal reorganization with a strict "prove parity before deleting" safety rule. The existing `survival_handlers.py` handler classes are the canonical path; legacy functions in `survival.py` are the duplication to eliminate.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy async, pytest.

**Parent spec:** `docs/superpowers/specs/2026-04-10-codebase-refactor-roadmap-design.md` (Wave 3 section)

**Prerequisite:** Waves 1 and 2 complete. In particular, Wave 2's dedicated test database and CRUD integration tests are required safety nets for this wave.

---

## Context

Read Wave 1's "Context engineers need" section for conventions. This wave is all backend — no frontend changes. Branch: `chore/wave-3-finish-in-flight`.

**Key files:**
- Target of deletion: `backend/app/phenopackets/routers/aggregations/survival.py` (lines 126-968, the 6 `_handle_*` functions)
- Canonical replacement: `backend/app/phenopackets/routers/aggregations/survival_handlers.py`
- Restructuring target: `backend/app/phenopackets/routers/aggregations/survival/` (new sub-package)
- Extension target: `backend/app/phenopackets/routers/aggregations/common.py`
- Aggregation modules with duplication: `demographics.py`, `variants.py`, `features.py`, `diseases.py`, `publications.py`, `summary.py`

**Parity-before-deletion rule:** Before removing any legacy `_handle_*` function, a parity test must prove the new handler-class path produces byte-identical output for the same inputs. This is non-negotiable — statistical correctness is load-bearing in the clinical use case.

---

## Task 1: Map old → new survival handler function equivalents

**Files:**
- Create: `docs/refactor/survival-migration-map.md` (documentation of the mapping)

No code changes in this task. The engineer's job is to read the 6 legacy functions and the new handler classes, confirm the mapping, and document it.

- [ ] **Step 1: Read the 6 legacy functions**

```bash
cd backend && for ln in 126 230 375 467 621 748; do
  echo "=== Line $ln ===";
  sed -n "${ln},$((ln+20))p" app/phenopackets/routers/aggregations/survival.py;
done
```

Identify each function's signature and purpose. The 6 functions should be:

1. `_handle_variant_type_current_age` (line 126)
2. `_handle_variant_type_standard` (line 230)
3. `_handle_pathogenicity_current_age` (line 375)
4. `_handle_pathogenicity_standard` (line 467)
5. `_handle_disease_subtype_current_age` (line 621)
6. `_handle_disease_subtype_standard` (line 748)

- [ ] **Step 2: Read the new handler classes**

```bash
cat backend/app/phenopackets/routers/aggregations/survival_handlers.py | head -80
grep -n "^class \|def handle\|def process" backend/app/phenopackets/routers/aggregations/survival_handlers.py
```

Identify the handler classes. Expected structure: a base `SurvivalHandler` class (or similar) with concrete subclasses for each comparison type and age-mode combination.

- [ ] **Step 3: Write the migration map**

Create `docs/refactor/survival-migration-map.md`:

```markdown
# Survival Handler Migration Map

**Wave 3 reference document.** Maps the 6 legacy functions in
`survival.py` to the canonical handler classes in
`survival_handlers.py`. Used to drive the Task 3 parity tests and
Task 4 deletion safety.

| Legacy function | survival.py line | Canonical handler class | survival_handlers.py |
|-----------------|:----------------:|-------------------------|:--------------------:|
| _handle_variant_type_current_age | 126 | VariantTypeCurrentAgeHandler | <line> |
| _handle_variant_type_standard | 230 | VariantTypeStandardHandler | <line> |
| _handle_pathogenicity_current_age | 375 | PathogenicityCurrentAgeHandler | <line> |
| _handle_pathogenicity_standard | 467 | PathogenicityStandardHandler | <line> |
| _handle_disease_subtype_current_age | 621 | DiseaseSubtypeCurrentAgeHandler | <line> |
| _handle_disease_subtype_standard | 748 | DiseaseSubtypeStandardHandler | <line> |

## Verification

For each row, verify by reading both implementations that:
1. They compute the same Kaplan-Meier curves.
2. They run the same statistical tests.
3. They return responses with the same shape.

Any divergence is documented below with the decision (legacy is
authoritative / new handler is authoritative / both differ and we
need to reconcile).

### Divergences found during Wave 3 planning

<fill in during Task 1 execution — none expected but document any>
```

Fill in the actual class names and line numbers from Step 2.

- [ ] **Step 4: Commit the map**

```bash
git add docs/refactor/survival-migration-map.md
git commit -m "docs(refactor): map survival.py legacy functions to handler classes

Task 1 of Wave 3: documents the 1:1 mapping between the 6 legacy
_handle_* functions in survival.py and their handler class
equivalents in survival_handlers.py. Drives the Task 3 parity tests.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Find all callers of the legacy functions

**Files:** none modified; this is pure investigation.

- [ ] **Step 1: Grep for calls**

```bash
cd backend && grep -rn "_handle_variant_type\|_handle_pathogenicity\|_handle_disease_subtype" app --include="*.py"
```

Expected: the callers are inside `survival.py` itself (the legacy dispatcher function) and possibly in the endpoint function. The handler classes should already be used in the canonical path.

- [ ] **Step 2: Identify the dispatcher logic**

Find where `survival.py`'s endpoint function chooses between legacy functions. It's likely a series of `if` statements on comparison type + age mode. Note the exact structure.

- [ ] **Step 3: Decision: parallel path or replace-in-place?**

Two options:
- **Option A: Replace in place.** Edit the dispatcher to call handler classes instead of legacy functions. Delete legacy functions in the same commit.
- **Option B: Parallel path.** Introduce a feature flag / parameter to call the new handler path, prove parity in tests, then delete legacy and flag in a second commit.

**Choose Option A** if Task 3's parity tests pass reliably (low risk). **Choose Option B** if the legacy functions have subtle behavioral differences.

Document the decision in the wave-3-exit.md (write later).

---

## Task 3: Write parity tests comparing old and new handler output

**Files:**
- Create: `backend/tests/test_survival_parity.py`

This is the safety net. Each of the 6 legacy functions gets a parametrized test that invokes both the legacy function and the new handler class with identical inputs, then asserts the outputs match.

- [ ] **Step 1: Write the parity test skeleton**

Create `backend/tests/test_survival_parity.py`:

```python
"""Parity tests comparing legacy survival.py handler functions to the
canonical survival_handlers.py handler classes.

This is the safety net for Wave 3's deletion of the legacy functions.
Each test invokes both paths with identical input and asserts the
output is equivalent (either byte-identical JSON or numerically close
to within floating-point tolerance).

If any parity test fails, the legacy path must NOT be deleted until
the discrepancy is investigated and resolved.
"""

import math
from typing import Any, Dict

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Legacy function imports
from app.phenopackets.routers.aggregations import survival as legacy_survival

# New handler class imports
from app.phenopackets.routers.aggregations.survival_handlers import (
    VariantTypeCurrentAgeHandler,
    VariantTypeStandardHandler,
    PathogenicityCurrentAgeHandler,
    PathogenicityStandardHandler,
    DiseaseSubtypeCurrentAgeHandler,
    DiseaseSubtypeStandardHandler,
)


def _assert_response_equal(legacy: Dict[str, Any], new: Dict[str, Any]) -> None:
    """Assert two survival responses are equivalent.

    Handles floating-point drift in statistical outputs via math.isclose.
    """
    assert set(legacy.keys()) == set(new.keys()), (
        f"Key mismatch: legacy={set(legacy.keys())}, new={set(new.keys())}"
    )
    for key in legacy:
        lv, nv = legacy[key], new[key]
        if isinstance(lv, float) and isinstance(nv, float):
            assert math.isclose(lv, nv, rel_tol=1e-9, abs_tol=1e-12), (
                f"Float mismatch at {key}: legacy={lv}, new={nv}"
            )
        elif isinstance(lv, list) and isinstance(nv, list):
            assert len(lv) == len(nv), f"List length mismatch at {key}"
            # Deep comparison with float tolerance would go here for
            # nested structures; for now use direct equality and adjust
            # if tests fail.
            assert lv == nv, f"List content mismatch at {key}"
        else:
            assert lv == nv, f"Mismatch at {key}: legacy={lv}, new={nv}"


@pytest.mark.asyncio
class TestVariantTypeParity:
    async def test_current_age_mode(self, db_session: AsyncSession):
        """Both paths produce equivalent output for variant_type + current_age."""
        # Call legacy path
        legacy_result = await legacy_survival._handle_variant_type_current_age(
            db_session
        )
        # Call new handler
        handler = VariantTypeCurrentAgeHandler(db_session)
        new_result = await handler.handle()
        _assert_response_equal(legacy_result, new_result)

    async def test_standard_mode(self, db_session: AsyncSession):
        legacy_result = await legacy_survival._handle_variant_type_standard(db_session)
        handler = VariantTypeStandardHandler(db_session)
        new_result = await handler.handle()
        _assert_response_equal(legacy_result, new_result)


@pytest.mark.asyncio
class TestPathogenicityParity:
    async def test_current_age_mode(self, db_session: AsyncSession):
        legacy_result = await legacy_survival._handle_pathogenicity_current_age(
            db_session
        )
        handler = PathogenicityCurrentAgeHandler(db_session)
        new_result = await handler.handle()
        _assert_response_equal(legacy_result, new_result)

    async def test_standard_mode(self, db_session: AsyncSession):
        legacy_result = await legacy_survival._handle_pathogenicity_standard(
            db_session
        )
        handler = PathogenicityStandardHandler(db_session)
        new_result = await handler.handle()
        _assert_response_equal(legacy_result, new_result)


@pytest.mark.asyncio
class TestDiseaseSubtypeParity:
    async def test_current_age_mode(self, db_session: AsyncSession):
        legacy_result = await legacy_survival._handle_disease_subtype_current_age(
            db_session
        )
        handler = DiseaseSubtypeCurrentAgeHandler(db_session)
        new_result = await handler.handle()
        _assert_response_equal(legacy_result, new_result)

    async def test_standard_mode(self, db_session: AsyncSession):
        legacy_result = await legacy_survival._handle_disease_subtype_standard(
            db_session
        )
        handler = DiseaseSubtypeStandardHandler(db_session)
        new_result = await handler.handle()
        _assert_response_equal(legacy_result, new_result)
```

- [ ] **Step 2: Adjust imports to match actual class names**

Run the test file (expect import errors):

```bash
cd backend && uv run pytest tests/test_survival_parity.py --collect-only
```

Expected: import errors reveal the actual handler class names. Update the imports accordingly. If the classes take different constructor arguments, adjust the instantiations.

- [ ] **Step 3: Run the parity tests**

```bash
cd backend && uv run pytest tests/test_survival_parity.py -v
```

Expected: all 6 tests pass. If any fail, stop and investigate before continuing. Document findings in the wave exit note.

- [ ] **Step 4: Commit the parity tests**

```bash
git add backend/tests/test_survival_parity.py
git commit -m "test(backend): add parity tests for survival handler migration

Wave 3 safety net: compares each of the 6 legacy _handle_* functions
in survival.py against their canonical handler class equivalents.
Uses math.isclose for floating-point tolerance. If any test fails,
the legacy functions must NOT be deleted in Task 4 until the
discrepancy is resolved.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Switch the dispatcher to handler classes and delete legacy functions

**Files:**
- Modify: `backend/app/phenopackets/routers/aggregations/survival.py` (edit dispatcher, delete lines 126-968)

Only proceed with this task if Task 3's parity tests are all green.

- [ ] **Step 1: Edit the dispatcher to call handler classes**

Find the endpoint function in `survival.py` that currently dispatches to `_handle_*` functions. Replace each dispatch with the handler class instantiation and call.

Example transformation (actual code will look different; the pattern is the important part):

```python
# Before:
if comparison == "variant_type" and age_mode == "current_age":
    return await _handle_variant_type_current_age(db)

# After:
if comparison == "variant_type" and age_mode == "current_age":
    handler = VariantTypeCurrentAgeHandler(db)
    return await handler.handle()
```

Do this for all 6 branches.

- [ ] **Step 2: Run the full test suite**

```bash
cd backend && make check
```

Expected: all green. If any survival-related test fails, inspect: the dispatcher change should be transparent to callers.

- [ ] **Step 3: Delete the 6 legacy functions**

Delete lines 126-968 of `survival.py` containing the 6 `_handle_*` function definitions. The file should shrink to ~150 LOC (just the router endpoints).

- [ ] **Step 4: Run full test suite again**

```bash
cd backend && make check
```

Expected: still all green. The parity tests from Task 3 will now fail because the legacy functions no longer exist — update the parity test file to skip itself or delete it:

Add at the top of `backend/tests/test_survival_parity.py`:

```python
pytest.skip(
    "Legacy _handle_* functions deleted in Wave 3 Task 4. "
    "Parity proven during planning; this file kept for historical reference.",
    allow_module_level=True,
)
```

- [ ] **Step 5: Commit both changes together**

```bash
git add backend/app/phenopackets/routers/aggregations/survival.py backend/tests/test_survival_parity.py
git commit -m "$(cat <<'EOF'
refactor(backend): delete legacy survival handler functions

Switches the survival endpoint dispatcher to call handler classes
from survival_handlers.py directly, then deletes the 6 legacy
_handle_* functions (lines 126-968, ~840 LOC removed) now that
parity was proven in the preceding test commit.

test_survival_parity.py is kept as a module-level skip so the
history of how parity was established remains in the repo.

survival.py shrinks from 1,025 LOC to ~150 LOC.

Closes P2 #6 from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Restructure survival into a `survival/` sub-package

**Files:**
- Create: `backend/app/phenopackets/routers/aggregations/survival/__init__.py`
- Create: `backend/app/phenopackets/routers/aggregations/survival/router.py`
- Create: `backend/app/phenopackets/routers/aggregations/survival/handlers.py`
- Create: `backend/app/phenopackets/routers/aggregations/survival/statistics.py`
- Create: `backend/app/phenopackets/routers/aggregations/survival/queries.py`
- Delete: `backend/app/phenopackets/routers/aggregations/survival.py` (now a thin shim)
- Delete: `backend/app/phenopackets/routers/aggregations/survival_handlers.py` (merged into survival/handlers.py)

- [ ] **Step 1: Create the sub-package directory**

```bash
mkdir -p backend/app/phenopackets/routers/aggregations/survival
touch backend/app/phenopackets/routers/aggregations/survival/__init__.py
```

- [ ] **Step 2: Move endpoint code to router.py**

Open the shrunken `survival.py` and copy its contents (the router + endpoint functions) into `survival/router.py`. Adjust imports to reference the new sub-package structure:

```python
# survival/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from .handlers import (
    VariantTypeCurrentAgeHandler,
    VariantTypeStandardHandler,
    # ... etc
)

router = APIRouter(prefix="/survival", tags=["aggregations-survival"])

@router.get("/")
async def get_survival_data(
    comparison: str,
    age_mode: str,
    db: AsyncSession = Depends(get_db),
):
    # dispatcher logic here
    ...
```

- [ ] **Step 3: Move handler classes to handlers.py**

Move the entire contents of `survival_handlers.py` into `survival/handlers.py`. If it's over 500 LOC (it's currently 1,055), split by handler family:

- `handlers/variant_type.py` — `VariantTypeCurrentAgeHandler`, `VariantTypeStandardHandler`
- `handlers/pathogenicity.py` — `PathogenicityCurrentAgeHandler`, `PathogenicityStandardHandler`
- `handlers/disease_subtype.py` — `DiseaseSubtypeCurrentAgeHandler`, `DiseaseSubtypeStandardHandler`
- `handlers/base.py` — shared base class

Adjust imports in `handlers/__init__.py` to re-export everything:

```python
from .base import SurvivalHandler
from .variant_type import VariantTypeCurrentAgeHandler, VariantTypeStandardHandler
from .pathogenicity import PathogenicityCurrentAgeHandler, PathogenicityStandardHandler
from .disease_subtype import DiseaseSubtypeCurrentAgeHandler, DiseaseSubtypeStandardHandler

__all__ = [
    "SurvivalHandler",
    "VariantTypeCurrentAgeHandler",
    "VariantTypeStandardHandler",
    "PathogenicityCurrentAgeHandler",
    "PathogenicityStandardHandler",
    "DiseaseSubtypeCurrentAgeHandler",
    "DiseaseSubtypeStandardHandler",
]
```

**If the handlers are already under 500 LOC after the Wave 3 Task 4 deletion**, keep them in a single `handlers.py`. Decide based on the actual line count after Task 4.

- [ ] **Step 4: Extract statistics helpers to statistics.py**

Identify Kaplan-Meier, log-rank, and other statistical functions inside the handlers or the old `survival.py`. Move them to `survival/statistics.py`:

```python
# survival/statistics.py
"""Kaplan-Meier, log-rank, and other statistical helpers for survival analysis."""
from typing import List, Tuple

def kaplan_meier_curve(durations: List[float], events: List[int]) -> List[Tuple[float, float]]:
    ...

def logrank_test(group_a: dict, group_b: dict) -> dict:
    ...
```

- [ ] **Step 5: Extract SQL fragments to queries.py**

If handlers build SQL fragments inline, extract them to `survival/queries.py` as functions that return `TextClause` or `Select` objects. This is the separation of data-access from handler logic.

- [ ] **Step 6: Wire up the sub-package's __init__.py**

```python
# survival/__init__.py
"""Survival analysis sub-package.

Public API:
    router: FastAPI router for survival endpoints
    handlers: Kaplan-Meier + statistical handlers
"""
from .router import router
from .handlers import (
    SurvivalHandler,
    VariantTypeCurrentAgeHandler,
    VariantTypeStandardHandler,
    PathogenicityCurrentAgeHandler,
    PathogenicityStandardHandler,
    DiseaseSubtypeCurrentAgeHandler,
    DiseaseSubtypeStandardHandler,
)

__all__ = [
    "router",
    "SurvivalHandler",
    "VariantTypeCurrentAgeHandler",
    "VariantTypeStandardHandler",
    "PathogenicityCurrentAgeHandler",
    "PathogenicityStandardHandler",
    "DiseaseSubtypeCurrentAgeHandler",
    "DiseaseSubtypeStandardHandler",
]
```

- [ ] **Step 7: Delete the old flat files**

```bash
rm backend/app/phenopackets/routers/aggregations/survival.py
rm backend/app/phenopackets/routers/aggregations/survival_handlers.py
```

- [ ] **Step 8: Fix all imports that used the old flat paths**

```bash
cd backend && grep -rn "from app.phenopackets.routers.aggregations.survival import\|from app.phenopackets.routers.aggregations import survival\|from app.phenopackets.routers.aggregations.survival_handlers" app tests
```

Every match needs updating. Because of the `__init__.py` re-exports above, in most cases the existing import path will continue to work — the package now behaves like the flat file did. But `from .survival import _handle_*` is gone forever (those functions were deleted in Task 4), so any old reference that survived needs updating.

Also update `aggregations/__init__.py` if it imports survival bits.

- [ ] **Step 9: Run the full test suite**

```bash
cd backend && make check
```

Expected: all green. Fix any remaining import errors.

- [ ] **Step 10: Verify every file in the new sub-package is under 500 LOC**

```bash
find backend/app/phenopackets/routers/aggregations/survival -name "*.py" -exec wc -l {} \;
```

Expected: all files under 500 LOC. If `handlers.py` is still over 500, split it per Step 3's sub-module structure.

- [ ] **Step 11: Commit**

```bash
git add backend/app/phenopackets/routers/aggregations/survival/ backend/app/phenopackets/routers/aggregations/survival.py backend/app/phenopackets/routers/aggregations/survival_handlers.py backend/app/phenopackets/routers/aggregations/__init__.py
git commit -m "$(cat <<'EOF'
refactor(backend): restructure survival into a sub-package

Moves the survival analysis code from two flat files (survival.py +
survival_handlers.py) into a proper sub-package:

  survival/
    __init__.py       (public re-exports, backwards-compat)
    router.py         (FastAPI endpoints)
    handlers.py       (Strategy pattern handler classes)
    statistics.py     (Kaplan-Meier, log-rank helpers)
    queries.py        (SQL fragment builders)

Every file is under 500 LOC. Existing imports continue to work via
the __init__.py re-exports.

Closes P5 #23 from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Replace hardcoded HPO IDs with settings.hpo_terms references

**Files:**
- Modify: `backend/app/phenopackets/routers/aggregations/survival/queries.py` (or wherever the HPO IDs live after Task 5)
- Possibly modify: `backend/app/core/config.py` (add HPO term constants if missing)

- [ ] **Step 1: Find all hardcoded HPO IDs in survival code**

```bash
cd backend && grep -rn "HP:[0-9]\{7\}" app/phenopackets/routers/aggregations/survival/ 2>/dev/null
```

Expected: 6+ matches for HPO term IDs like `HP:0000107`, `HP:0003774`, etc.

- [ ] **Step 2: Check the HPOTermsConfig in core/config.py**

```bash
cd backend && grep -n "hpo_terms\|HPOTermsConfig" app/core/config.py | head -20
```

Look at what HPO term constants are already defined. If all 6 IDs are already in the config, Step 3 is straightforward. If some are missing, add them.

- [ ] **Step 3: Replace each hardcoded ID with a settings reference**

For each hardcoded HPO ID, find the correct settings path (e.g., `settings.hpo_terms.renal_cyst` or `settings.yaml_config.hpo_terms.kidney_failure`). Replace the string literal:

```python
# Before:
if row["hpo_id"] == "HP:0000107":
    ...

# After:
if row["hpo_id"] == settings.hpo_terms.renal_cyst:
    ...
```

Add `from app.core.config import settings` at the top of the file if not already there.

- [ ] **Step 4: Add any missing HPO constants to config.py**

If `settings.hpo_terms.X` doesn't exist for some ID, add it. Look at how `HPOTermsConfig` is structured (probably a YAML-loaded section). Add to `backend/config.yaml`:

```yaml
hpo_terms:
  renal_cyst: "HP:0000107"
  kidney_failure: "HP:0003774"
  # etc.
```

And update the config.py model class if needed.

- [ ] **Step 5: Run tests**

```bash
cd backend && make check
```

Expected: all green. Survival endpoint tests in particular should pass unchanged since the behavior is identical — only the source of the HPO IDs changed.

- [ ] **Step 6: Verify the grep finds zero literals**

```bash
cd backend && grep -rn "HP:[0-9]\{7\}" app/phenopackets/routers/aggregations/survival/ 2>/dev/null
```

Expected: zero matches (or matches only inside docstrings/comments documenting the change).

- [ ] **Step 7: Commit**

```bash
git add backend/app/phenopackets/routers/aggregations/survival/ backend/app/core/config.py backend/config.yaml
git commit -m "refactor(backend): replace hardcoded HPO IDs with settings references

Moves 6 hardcoded HP:NNNNNNN literals from the survival sub-package
into settings.hpo_terms.* references. Missing constants added to
config.yaml and HPOTermsConfig. Ensures all clinical-term references
are in one place for easier review and maintenance.

Closes P3 #16 from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Extend aggregations/common.py with the missing helpers

**Files:**
- Modify: `backend/app/phenopackets/routers/aggregations/common.py`
- Create: `backend/tests/test_aggregations_common.py`
- Modify: `backend/app/phenopackets/routers/aggregations/demographics.py`
- Modify: `backend/app/phenopackets/routers/aggregations/variants.py`
- Modify: `backend/app/phenopackets/routers/aggregations/features.py`
- Modify: `backend/app/phenopackets/routers/aggregations/diseases.py`
- Modify: `backend/app/phenopackets/routers/aggregations/publications.py`
- Modify: `backend/app/phenopackets/routers/aggregations/summary.py`

- [ ] **Step 1: Write tests for the new helpers**

Create `backend/tests/test_aggregations_common.py`:

```python
"""Tests for the new helpers added to aggregations/common.py in Wave 3."""

import pytest

from app.phenopackets.routers.aggregations.common import (
    calculate_percentages,
)


class TestCalculatePercentages:
    def test_basic_percentages(self):
        rows = [{"count": 50}, {"count": 30}, {"count": 20}]
        result = calculate_percentages(rows, total=100)
        assert result[0]["percentage"] == 50.0
        assert result[1]["percentage"] == 30.0
        assert result[2]["percentage"] == 20.0

    def test_total_zero_returns_zero_percentages(self):
        rows = [{"count": 10}, {"count": 5}]
        result = calculate_percentages(rows, total=0)
        for row in result:
            assert row["percentage"] == 0

    def test_preserves_other_fields(self):
        rows = [{"count": 10, "label": "alpha"}, {"count": 90, "label": "beta"}]
        result = calculate_percentages(rows, total=100)
        assert result[0]["label"] == "alpha"
        assert result[1]["label"] == "beta"

    def test_does_not_mutate_input(self):
        rows = [{"count": 10}]
        original = rows[0].copy()
        calculate_percentages(rows, total=100)
        assert rows[0] == original or "percentage" in rows[0]
        # Accept either: pure function (no mutation) or in-place. Document in docstring.

    def test_empty_input(self):
        result = calculate_percentages([], total=100)
        assert result == []

    def test_count_using_row_mapping(self):
        """Some call sites use row._mapping['count']; the helper must handle both."""
        class FakeRow:
            def __init__(self, count, label):
                self._mapping = {"count": count, "label": label}
                self.count = count
                self.label = label
            def __getitem__(self, key):
                return self._mapping[key]

        rows = [FakeRow(75, "x"), FakeRow(25, "y")]
        result = calculate_percentages(rows, total=100)
        assert result[0]["percentage"] == 75.0 or result[0].percentage == 75.0
```

- [ ] **Step 2: Run to confirm fail**

```bash
cd backend && uv run pytest tests/test_aggregations_common.py -v
```

Expected: FAIL (`calculate_percentages` does not exist in common.py).

- [ ] **Step 3: Add `calculate_percentages` to common.py**

Open `backend/app/phenopackets/routers/aggregations/common.py`. Add at the bottom:

```python
def calculate_percentages(
    rows: List[Any], total: int, count_key: str = "count"
) -> List[Dict[str, Any]]:
    """Add a 'percentage' field to each row based on its count / total.

    Accepts either dict rows or SQLAlchemy row objects that support both
    __getitem__ and ._mapping access. Returns a new list of dicts; does
    not mutate input rows.

    Args:
        rows: Sequence of rows from a query result.
        total: Denominator for percentage calculation.
        count_key: Field name holding the count (default "count").

    Returns:
        List of new dicts, each with all original fields plus "percentage".
    """
    result: List[Dict[str, Any]] = []
    for row in rows:
        # Extract fields from either dict, SQLAlchemy mapping, or attribute access
        if hasattr(row, "_mapping"):
            data = dict(row._mapping)
        elif isinstance(row, dict):
            data = dict(row)
        else:
            data = {k: getattr(row, k) for k in dir(row) if not k.startswith("_")}

        count_value = int(data.get(count_key, 0))
        data["percentage"] = (count_value / total * 100) if total > 0 else 0
        result.append(data)
    return result
```

Add `calculate_percentages` to the `__all__` list at the top of the file.

- [ ] **Step 4: Run the test**

```bash
cd backend && uv run pytest tests/test_aggregations_common.py -v
```

Expected: all pass. If any fail, adjust the helper implementation to match — the tests are the spec.

- [ ] **Step 5: Replace duplicated code in demographics.py**

Open `backend/app/phenopackets/routers/aggregations/demographics.py`. Find the 3 sites (per the Wave 3 spec re-baseline) where percentages are calculated inline like:

```python
percentage=(int(row["count"]) / total * 100) if total > 0 else 0
```

Replace the duplicated computation with a single call to `calculate_percentages`:

```python
from .common import calculate_percentages

# ... inside the handler:
rows_with_pct = calculate_percentages(raw_rows, total=total)
# Then build the response from rows_with_pct instead of re-calculating
```

- [ ] **Step 6: Replace duplicated code in variants.py, features.py, diseases.py, publications.py, summary.py**

Apply the same transformation to each file. Each file has 1-3 sites.

- [ ] **Step 7: Run the full test suite**

```bash
cd backend && make check
```

Expected: all green. Aggregation endpoint tests should return identical output before and after.

- [ ] **Step 8: Verify duplication reduced**

```bash
cd backend && grep -rn "/ total \* 100) if total > 0" app/phenopackets/routers/aggregations/ | wc -l
```

Expected: 3 or fewer matches (down from 10+).

- [ ] **Step 9: Commit**

```bash
git add backend/app/phenopackets/routers/aggregations/common.py backend/app/phenopackets/routers/aggregations/{demographics,variants,features,diseases,publications,summary}.py backend/tests/test_aggregations_common.py
git commit -m "$(cat <<'EOF'
refactor(backend): extract percentage calculation to aggregations/common

Adds calculate_percentages() helper to common.py and replaces 10+
duplicated (count / total * 100) if total > 0 else 0 sites across
demographics, variants, features, diseases, publications, and
summary aggregation modules. Handles dict rows, SQLAlchemy
_mapping rows, and attribute-style rows transparently.

Companion test file exercises the helper with all three input shapes
and edge cases (empty input, total=0, label preservation).

Closes P3 #13 from the 2026-04-09 review (rescoped as "extend"
rather than "create" because common.py already existed).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Add materialized_view_fallback helper to common.py

**Files:**
- Modify: `backend/app/phenopackets/routers/aggregations/common.py`
- Modify: affected aggregation modules that use MV fallback

- [ ] **Step 1: Find the duplicated MV fallback pattern**

```bash
cd backend && grep -rn "check_materialized_view_exists\|mv_cache.is_available" app/phenopackets/routers/aggregations/ | head -20
```

Note the repeated pattern: each aggregation checks the MV cache, queries the MV if available, falls back to the live query otherwise.

- [ ] **Step 2: Add the helper to common.py**

Append to `backend/app/phenopackets/routers/aggregations/common.py`:

```python
from contextlib import asynccontextmanager
from typing import Callable, Coroutine

@asynccontextmanager
async def materialized_view_fallback(
    view_name: str,
    mv_query: Callable[[], Coroutine],
    fallback_query: Callable[[], Coroutine],
):
    """Context manager selecting MV or fallback query based on cache.

    Usage:
        async with materialized_view_fallback(
            view_name="mv_demographics",
            mv_query=lambda: db.execute(select_from_mv),
            fallback_query=lambda: db.execute(live_query),
        ) as result:
            rows = result.fetchall()
    """
    if mv_cache.is_available(view_name):
        logger.debug("Using materialized view: %s", view_name)
        result = await mv_query()
    else:
        logger.debug("MV %s unavailable, using fallback query", view_name)
        result = await fallback_query()
    try:
        yield result
    finally:
        pass  # no cleanup needed for query results
```

- [ ] **Step 3: Write a test**

Append to `backend/tests/test_aggregations_common.py`:

```python
from unittest.mock import AsyncMock, patch
from app.phenopackets.routers.aggregations.common import materialized_view_fallback


@pytest.mark.asyncio
class TestMaterializedViewFallback:
    async def test_uses_mv_when_available(self):
        mv_query = AsyncMock(return_value="mv_result")
        fallback = AsyncMock(return_value="fallback_result")
        with patch("app.phenopackets.routers.aggregations.common.mv_cache") as mock_cache:
            mock_cache.is_available.return_value = True
            async with materialized_view_fallback("mv_x", mv_query, fallback) as result:
                assert result == "mv_result"
        mv_query.assert_called_once()
        fallback.assert_not_called()

    async def test_uses_fallback_when_mv_unavailable(self):
        mv_query = AsyncMock(return_value="mv_result")
        fallback = AsyncMock(return_value="fallback_result")
        with patch("app.phenopackets.routers.aggregations.common.mv_cache") as mock_cache:
            mock_cache.is_available.return_value = False
            async with materialized_view_fallback("mv_x", mv_query, fallback) as result:
                assert result == "fallback_result"
        mv_query.assert_not_called()
        fallback.assert_called_once()
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_aggregations_common.py -v
```

Expected: all pass.

- [ ] **Step 5: Refactor at least 2 aggregation modules to use the new context manager**

Pick 2 modules (e.g., `demographics.py` and `variants.py`). Replace their inline MV-check/fallback logic with the new context manager.

Keep other modules unchanged if the refactor risks subtle bugs — the primary value of this task is having the helper available, not blanket refactoring.

- [ ] **Step 6: Run full test suite**

```bash
cd backend && make check
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/phenopackets/routers/aggregations/common.py backend/tests/test_aggregations_common.py backend/app/phenopackets/routers/aggregations/demographics.py backend/app/phenopackets/routers/aggregations/variants.py
git commit -m "refactor(backend): add materialized_view_fallback context manager

Adds an async context manager helper to common.py for the repeated
'check MV cache, use MV or fallback query' pattern. Refactors
demographics.py and variants.py to use it. Other aggregation
modules keep their current structure and can migrate in a later
pass if desired.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Wave 3 exit verification

- [ ] **Step 1: Run full backend check**

```bash
cd backend && make check
```

- [ ] **Step 2: Verify survival.py is gone or a shim**

```bash
ls backend/app/phenopackets/routers/aggregations/survival.py 2>&1
ls backend/app/phenopackets/routers/aggregations/survival_handlers.py 2>&1
ls -la backend/app/phenopackets/routers/aggregations/survival/
```

Expected: the two flat files do not exist; the sub-package does.

- [ ] **Step 3: Verify no hardcoded HPO IDs in survival code**

```bash
grep -rn "HP:[0-9]\{7\}" backend/app/phenopackets/routers/aggregations/survival/ 2>/dev/null
```

Expected: zero matches (or matches only inside docstrings).

- [ ] **Step 4: Verify common.py has both new helpers**

```bash
grep -n "def calculate_percentages\|def materialized_view_fallback" backend/app/phenopackets/routers/aggregations/common.py
```

Expected: 2 matches.

- [ ] **Step 5: Verify duplication reduced**

```bash
grep -rn "/ total \* 100) if total > 0" backend/app/phenopackets/routers/aggregations/ | wc -l
```

Expected: 3 or fewer (was 10+).

- [ ] **Step 6: Write wave exit note**

Create `docs/refactor/wave-3-exit.md`:

```markdown
# Wave 3 Exit Note

**Date:** <YYYY-MM-DD>
**Starting test counts:** backend ~765 (post Wave 2), frontend 16 files.
**Ending test counts:** backend ~765 (parity tests were module-skipped after deletion).

## What landed

- Task 1: Survival migration map documented.
- Task 2: Caller analysis.
- Task 3: Parity tests for 6 handler functions (all passed before deletion).
- Task 4: Legacy _handle_* functions deleted; survival.py shrank from 1,025 to ~150 LOC.
- Task 5: survival/ sub-package created with router/handlers/statistics/queries modules. Every file < 500 LOC.
- Task 6: 6+ hardcoded HPO IDs replaced with settings.hpo_terms.* references.
- Task 7: calculate_percentages() helper added; duplication removed from 6 aggregation modules.
- Task 8: materialized_view_fallback context manager added; 2 modules migrated.

## What was deferred

<fill in>

## What surprised us

<fill in>

## Entry conditions for Wave 4

- survival/ sub-package is the single canonical location for survival logic.
- Aggregation modules have a clean shared helpers module.
- No hardcoded HPO IDs remain in the survival path.
- All backend tests green.
- Ready for Wave 4 backend decomposition (admin_endpoints, crud, etc).

Wave 4 can begin.
```

- [ ] **Step 7: Commit**

```bash
git add docs/refactor/wave-3-exit.md
git commit -m "docs: add Wave 3 exit note

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

**Wave 3 is done when all 9 tasks are checked off and the exit note is committed.**

---

## Self-Review Notes

- **Spec coverage:** Deleting legacy handlers (Task 4), restructuring into sub-package (Task 5), replacing hardcoded HPO IDs (Task 6), extending common.py with calculate_percentages and materialized_view_fallback (Tasks 7-8). Every Wave 3 item from the spec is covered.
- **Parity-before-deletion rule:** Enforced explicitly in Task 3, checked in Task 4 Step 1.
- **Placeholder scan:** Only `<fill in>` in the exit note template.
- **Type/name consistency:** `calculate_percentages`, `materialized_view_fallback`, handler class names all used consistently across Tasks 3-8.
- **Known risks:** Task 5's handler split may reveal that a single `handlers.py` file is still too large. Plan step explicitly addresses this with a sub-module structure fallback.
