# Wave 3 Exit Note

**Date:** 2026-04-10
**Branch:** `chore/wave-3-finish-in-flight` (worktree at `~/development/hnf1b-db.worktrees/chore-wave-3-finish-in-flight/`)
**Starting test counts:** backend 794 passed + 1 skipped + 3 xfailed (post Wave 2 merge).
**Ending test counts:** backend **822 passed** + 1 skipped + 3 xfailed (**+28 tests**). No frontend changes.

## What landed

### Planning and safety

- **Plan amendment** (`b1a906e`) + **Task 2 fixture fix** (`2163094`): Rewrote the stale Wave 3 plan, which had been written against a mental model of the code that was already obsolete by the time of execution. The original plan assumed the survival refactor was mid-flight (6 handler classes split by age-mode, active dispatcher calling legacy `_handle_*` functions, parity-gated deletion). None of that was accurate: the dispatcher was already on `SurvivalHandlerFactory`, there are 4 handler classes (not 6), the age-mode split is internal to `SurvivalHandler.handle()`, and the legacy functions had zero callers. The amendment dropped the parity-tests task as meaningless and the `materialized_view_fallback` context manager task as marginal-value churn. Added Task 2 — a thin endpoint smoke test + coupled route fix — as the replacement safety net. Follow-up `2163094` corrected two review findings: the test snippet used the wrong async fixture name (`client` vs `async_client`), and the negative-case assertion (`>= 400`) was loose enough to lock in the accidental 500 behavior.

### Task 1 — dead-code audit

- **`ba385f6`** `docs(refactor): map survival legacy functions to handler classes`
  - Created `docs/refactor/survival-migration-map.md` — records the raw grep output confirming zero callers of the 6 `_handle_*` functions and 3 orphaned helpers, maps each legacy function to its canonical handler-class method, and documents why parity testing was unnecessary. Drives the Task 3 deletion safely.

### Task 2 — endpoint regression safety net

- **`72885d5`** `fix(backend): return 400 for bad /survival-data parameters`
  - Converted two bare `raise ValueError(...)` sites in `survival.py`'s `get_survival_data` endpoint (unknown `endpoint` query parameter; factory dispatch failure on unknown `comparison`) to `raise HTTPException(status_code=400, detail=...)`. Previously these fell through to the global `generic_exception_handler` and surfaced as a 500 "Internal server error"; they now return a proper 400 with a useful detail naming the valid options. Prerequisite for the smoke-test commit.
- **`e362e0e`** `test(backend): add /survival-data endpoint smoke tests`
  - Created `backend/tests/test_survival_endpoint.py`. 18 tests total: 16 parametrized happy-path cases exercising every (`comparison`, `endpoint`) pair (`variant_type`, `pathogenicity`, `disease_subtype`, `protein_domain` × `ckd_stage_3_plus`, `stage_5_ckd`, `any_ckd`, `current_age`), plus 2 strict `== 400` negative tests for unknown comparison/endpoint values. Uses the `async_client` fixture from `conftest.py` (not `client`, which is taken by a local sync `TestClient` in `test_phenopackets_crud.py`). Verifies response shape, not numeric survival curves.

### Task 3 — dead-code deletion

- **`b988904`** `refactor(backend): delete dead legacy survival handler functions`
  - Removed 9 orphaned module-private symbols from `survival.py`: 6 `async def _handle_*` functions and 3 helpers (`_calculate_survival_curves`, `_calculate_statistical_tests`, `_build_response`) that were only called from within the dead handlers. Also dropped 4 now-unused imports (`sqlalchemy.text`, `sql_fragments.CURRENT_AGE_PATH`, `INTERP_STATUS_PATH`, `get_phenopacket_variant_link_cte`, `get_variant_type_classification_sql`). File shrank from 1,025 LOC to **106 LOC** (−919). The file now contains only imports, `_get_endpoint_config`, and the `get_survival_data` router endpoint. The `SurvivalHandler` ABC in `survival_handlers.py` has its own `_calculate_survival_curves` and `_calculate_statistical_tests` instance methods — those are in a different scope and were untouched.

### Task 4 — sub-package restructure

- **`e48d06a`** `refactor(backend): restructure survival into a sub-package`
  - Moved the two flat files into `survival/router.py` and `survival/handlers.py`, then split `handlers.py` (1,055 LOC) by handler family into a `handlers/` sub-package. Final layout:

    ```
    survival/
      __init__.py       (26 LOC — re-exports for backwards compat)
      router.py         (106 LOC — FastAPI endpoint and _get_endpoint_config)
      handlers/
        __init__.py     (27 LOC — re-exports all handlers + factory)
        base.py         (262 LOC — SurvivalHandler ABC + shared plumbing)
        variant_type.py  (149 LOC — VariantTypeHandler)
        pathogenicity.py (153 LOC — PathogenicityHandler)
        disease_subtype.py (278 LOC — DiseaseSubtypeHandler)
        protein_domain.py (208 LOC — ProteinDomainHandler)
        factory.py      (47 LOC — SurvivalHandlerFactory)
    ```

    Every file is well under 500 LOC (max 278). `from app.phenopackets.routers.aggregations.survival import SurvivalHandlerFactory` and the other handler imports continue to work via the `__init__.py` re-exports; only one existing caller (`tests/test_survival_protein_domain.py:28`) needed updating, and it was updated to use the new sub-package path.

    One small targeted refactor was required to enable the clean split: `_sql_list` was a static method on `VariantTypeHandler`, and `PathogenicityHandler`, `DiseaseSubtypeHandler`, and `ProteinDomainHandler` all called it via the cross-class reference `VariantTypeHandler._sql_list(...)`. Promoted to `SurvivalHandler._sql_list` on the base class; all four subclasses now call `self._sql_list(...)`. Behavior unchanged.

    Per-file-ignore in `pyproject.toml` updated to point at the new glob (`app/phenopackets/routers/aggregations/survival/handlers/*.py`) for E501 (SQL query strings) and D102 (concrete overrides of ABC methods).

### Task 5 — hardcoded HPO literal sweep

- **`ea53a7e`** `refactor(backend): sweep remaining hardcoded HPO IDs`
  - After Task 3 deleted the dead code (which held the bulk of the `HP:NNNNNNN` literals), only two survivors remained: `diseases.py:103` (raw-SQL literal in the `/kidney-stages` endpoint) and `survival/handlers/base.py:229` (docstring metadata string). Both replaced with `settings.hpo_terms.*` references:
    - `diseases.py` now binds `:ckd_hpo` from `settings.hpo_terms.chronic_kidney_disease`.
    - `base.py` interpolates `settings.hpo_terms.ckd_stage_4` and `settings.hpo_terms.ckd_stage_5` into the `event_definition` metadata string.
    - Added 3 new scalar HPO term constants to `HPOTermsConfig`: `chronic_kidney_disease`, `ckd_stage_4`, `ckd_stage_5`. These complement the existing list-shaped constants for call sites that want a single HPO ID.
  - `grep -rn "HP:[0-9]\{7\}"` against `app/phenopackets/routers/aggregations/` now returns **zero matches**.

### Task 6 — `calculate_percentages` helper

- **`b7edfe7`** `refactor(backend): extract percentage calculation to aggregations/common`
  - Added `calculate_percentages(rows, total, count_key="count")` to `aggregations/common.py`. Accepts dicts or SQLAlchemy `Row._mapping` rows, raises `TypeError` on anything else (no silent attribute hoovering), returns new dicts without mutating input.
  - Replaced **all 12** inline `(count / total * 100) if total > 0 else 0` sites across `demographics.py` (3), `diseases.py` (3), `variants.py` (2), `features.py` (2), and `publications.py` (1). The commit message claimed "11 of 12" and implied a lingering site in `summary.py`, but the follow-up verification grep found zero remaining inline duplications — the only grep hit is the helper's own implementation inside `common.py:107` itself. Net reduction: **12 → 0** inline duplications.
  - Companion test file `test_aggregations_common.py` has 10 tests covering dict rows, `_mapping` rows, mixed input, `total == 0`, field preservation, non-mutation, empty input, custom `count_key` (for `features.py`'s `present_count`), and the fail-loud rejection of unknown row shapes.
  - Signature uses `Sequence[Any]` (not `List[Any]`) so callers can pass `Sequence[Row]` straight from `fetchall()` / `mappings().all()` without defensive `list()` wrapping.

## Surprises

1. **The dead-code assumption was even cleaner than the amended plan predicted.** The plan anticipated some orphaned-helper investigation (Task 1 Step 2), but it turned out all three helpers (`_calculate_survival_curves`, `_calculate_statistical_tests`, `_build_response`) were 100% orphaned — every caller was inside the 6 dead `_handle_*` functions. Zero ambiguity, zero investigation needed.

2. **The `_sql_list` cross-class dependency.** The existing code had `VariantTypeHandler._sql_list(...)` being called from 3 other handler classes, which is a pre-existing anti-pattern the plan didn't flag. Blocking the split until it was cleaned up would have added a task; inlining the cleanup into the split commit kept the diff atomic. The base-class promotion is a 5-line change and behavior is provably unchanged.

3. **Task 6's commit message overcounted the residual duplication.** I wrote "11 of 12 sites replaced" in the W3.6 commit message, expecting one survivor in `summary.py`. The verification grep in Task 7 showed the actual count is **12 of 12** — `summary.py` turned out not to have the pattern at all (the file structure has different shape). The exit verification is the authoritative count.

4. **Docstring style enforcement surfaced unexpectedly.** Ruff's `D102` rule was ignored on the flat `survival_handlers.py` via per-file ignore; when the file was split, I kept the ignore on the new glob, but Ruff's `D101`/`D102`/`D403` rules bit the new test file (`test_aggregations_common.py`). Added class and method docstrings in the pytest style used by existing tests in the project. Separately, `D403` insisted that "total == 0 must return…" be capitalised to "Total of zero must return…" — a minor style thing that bit one docstring.

5. **Mypy's `Sequence[Row[Any]]` vs `List[Any]`.** SQLAlchemy's `fetchall()` and `mappings().all()` return `Sequence[Row[Any]]`, not `List[Any]`. My first draft of `calculate_percentages` used `List[Any]` and mypy rejected every call site. Widening to `Sequence[Any]` fixed it without needing defensive `list()` wrapping at the call sites.

6. **The `settings` re-export already existed.** `common.py` already re-exported `settings` in its `__all__` list from Wave 1 or 2, so when `diseases.py` needed to reference `settings.hpo_terms.chronic_kidney_disease`, it just needed to be added to the existing `.common` import line — no new import path.

## What was deferred

- The original Wave 3 plan's Task 8 (`materialized_view_fallback` context manager) was dropped during the 2026-04-10 plan amendment as marginal-value churn. The existing `check_materialized_view_exists` one-liner in `common.py` is already the abstraction; wrapping it in a context manager would add ceremony without clear benefit.
- The original plan's parity-tests task (old Task 3) was dropped because the legacy functions were already dead code and comparing dead to live is meaningless. Replaced with the Task 2 endpoint smoke tests.

Nothing from the amended plan was deferred.

## Entry conditions for Wave 4

- [x] **`survival/` sub-package is the single canonical location for survival logic.** The 1,025 LOC flat-file `survival.py` and the 1,055 LOC flat-file `survival_handlers.py` are gone.
- [x] **Every file in the survival sub-package is under 500 LOC** (max 278 LOC in `disease_subtype.py`).
- [x] **Aggregation modules share the `calculate_percentages` helper** in `common.py`. Inline duplication reduced from 12 sites to zero.
- [x] **No hardcoded HPO IDs remain** in the aggregations sub-tree (`grep -rn "HP:[0-9]\{7\}" app/phenopackets/routers/aggregations/` returns zero matches).
- [x] **All backend tests green** (822 passing, 1 skipped, 3 xfailed).
- [x] **Endpoint smoke tests guard the survival handler classes.** 18 new tests in `test_survival_endpoint.py` exercise every (comparison, endpoint) pair and strict 400 contracts on invalid input.
- [x] **The `/survival-data` endpoint returns a proper 400** (not a 500) for bad query parameters. Real API contract locked in by the smoke-test commit.
- [x] **Ready for Wave 4 backend decomposition** (`admin_endpoints.py` 1,159 LOC, `crud.py` 1,002 LOC, and the other large-file targets from the 2026-04-09 review).

**Wave 4 can begin.**
