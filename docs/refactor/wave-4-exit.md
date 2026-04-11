# Wave 4 Exit Note

**Date:** 2026-04-11
**Branch:** `chore/wave-4-backend-decomposition` (worktree at `~/development/hnf1b-db.worktrees/chore-wave-4-backend-decomposition/`)
**Starting test counts:** backend **879 passed** + 1 skipped + 3 xfailed (post Wave 3 merge, commit `514c6e8`).
**Ending test counts:** backend **907 passed** + 9 skipped + 3 xfailed (**+28 tests**). No frontend changes.

## What landed (14 commits)

1. `91f3aa6` — **docs(refactor): amend Wave 4 plan to match reality.** Captured drift measured at `514c6e8`: stale LOC numbers (`admin_endpoints.py` 1,159 → 1,164, `variant_validator.py` 968 → 1,008, `publications/endpoints.py` 680 → 690, six smaller ±1 drifts), confirmation that Wave 3 already handled the survival sub-package (line 29), correction of the test-count baseline (879 not 783), and a note that the 2026-04-11 platform-readiness review is Wave 5+ scope.

2. `eb999d3` — **test(backend): capture HTTP surface baseline for Wave 4.** `tests/test_http_surface_baseline.py` with paired capture/verify modes + 8 baseline JSON fixtures under `tests/fixtures/wave4_http_baselines/`. Covers `/admin/status`, `phenopackets/`, `phenopackets/search`, `phenopackets/compare/variant-types`, `phenopackets/aggregate/summary`, `publications/`, `reference/genes`, `search/autocomplete`. Uses the real `async_client` + `admin_headers` conftest fixtures (plan template had a sync `TestClient` that would have shadowed `client` in `test_phenopackets_crud.py` — same gotcha Wave 3 hit).

3. `2ff018c` — **feat(backend): add cache-backed admin sync task state.** New `app/api/admin/task_state.py` with `SyncTaskStore` persisted through the existing `app.core.cache.cache` global `CacheService` (Redis-with-fallback). Replaces the unsafe process-local `_sync_tasks` dict. 20 new unit tests in `test_admin_task_state.py`. Key layout: `admin:sync_task:{task_id}` + `admin:sync_task:latest:{kind}` with 24h TTL.

4. `9f70ec6` — **refactor(backend): decompose admin_endpoints.py into sub-package.** 1,164 LOC flat file → `app/api/admin/` with 10 files (max 355 LOC in `queries.py`). Layout: `endpoints.py` aggregator → `status_routes.py` + `sync_publications_routes.py` + `sync_variants_routes.py` + `sync_reference_routes.py`. Supporting modules: `schemas.py`, `queries.py`, `sync_service.py`, `task_state.py`, `_common.py`. Closes **P2 #5** and **P3 #11** from the 2026-04-09 review.

5. `b3ae37d` — **refactor(backend): introduce PhenopacketRepository and decompose crud.py.** 1,003 LOC → Router → Service → Repository layering. New `phenopackets/repositories/phenopacket_repository.py` (168 LOC), `phenopackets/services/phenopacket_service.py` (269 LOC) with typed `ServiceError` hierarchy. `crud.py` shrank to 293 LOC; the related-lookup (`crud_related.py`, 248) and timeline (`crud_timeline.py`, 194) endpoints got their own files, plus a 100-LOC `crud_helpers.py` for sort parsing and PMID validation. Closes **P5 #22**.

6. `a0186cb` — **refactor(backend): split variant_validator.py into sub-package.** 1,008 LOC → `validation/variant_validator/` with 7 files. The facade class `VariantValidator` (`validator.py`) preserves the pre-Wave-4 public + private attribute surface via properties that forward to `VEPAnnotator` / `VEPRecoder` / `RateLimiter`. `cache` and `settings` are re-exported at the package level and looked up dynamically through `_vv_pkg` in the submodules so the existing `patch("...variant_validator.cache")` regression tests keep working unchanged. `check_rate_limit_headers` kept its `print()` call (tests assert `patch("builtins.print")`).

7. `1e588a7` — **refactor(backend): split comparisons.py into sub-package.** 861 LOC → 6 files (max 205 in `variant_sql.py`). The biggest simplification: the pre-Wave-4 monolith duplicated the 90-LOC truncating-classification SQL across three branches; `variant_sql.build_group_conditions()` now composes it from a single `_TRUNCATING_BASE` constant. Statistical helpers re-exported at the package root so `tests/test_comparisons.py`'s existing imports still work.

8. `0894522` — **refactor(backend): split variants/service.py into sub-package.** 824 LOC → 6 files. `errors.py` / `validators.py` / `cache_ops.py` / `vep_api.py` / `api.py`. Every private helper the regression suites reach into (`is_cnv_variant`, `validate_variant_id`, `_format_variant_for_vep`, `_parse_vep_response`, `_row_to_dict`, `_get_cached_annotation*`, `_store_annotations_batch`, `_fetch_from_vep`, `_extract_primary_transcript`, `_extract_gnomad_frequencies`) is re-exported at the package level.

9. `aaa467b` — **refactor(backend): split aggregation sql_fragments by domain.** 748 LOC → 5 files: `paths.py` (JSONB path constants), `classification.py` (variant-type CASE expressions — the biggest at 315 LOC), `ctes.py` (common table expressions), `protein_domain.py` (HNF1B domain helpers). All 20+ existing import sites continue to work via package-level re-export.

10. `fb04dff` — **refactor(backend): split reference/service.py by domain.** 722 LOC → 6 files: `constants.py` (HNF1B domains/exons, Ensembl URLs), `types.py` (SyncResult / ReferenceDataStatus), `hnf1b_importer.py` (initialization workflow — 299 LOC), `ensembl_sync.py` (chr17q12 sync), `status.py` (reference data status query).

11. `f42f6c4` — **refactor(backend): split variant_validator_endpoint.py into sub-package.** 702 LOC → `schemas.py` + `helpers.py` + 4 route files (`validate_route.py`, `annotate_route.py`, `recode_route.py`, `suggest_route.py`) + aggregator `__init__.py`. The aggregator preserves `/api/v2/variants` so `app.main`'s `include_router(variant_validator_endpoint.router)` call stays unchanged.

12. `fda9290` — **refactor(backend): split publications/endpoints.py into sub-package.** 690 LOC → `schemas.py` + 3 route files + aggregator. `list_route.py` factors out a `_build_where_clauses` helper shared between the main query and the count query — the pre-Wave-4 monolith had the same clauses duplicated twice with a subtle drift risk.

13. `8e04a94` — **refactor(backend): split search/services.py by class.** 513 LOC → 4 files (`pagination.py`, `global_search.py`, `phenopacket_search.py`, `facet.py`). Each class in its own file; the package `__init__.py` re-exports all four for `tests/test_global_search.py`.

14. `096d567` — **docs(refactor): register Wave 4 tech-debt exceptions (empty).** `docs/refactor/tech-debt.md` created as the canonical ledger. **Both the backend and frontend tables are intentionally empty** — every file in `backend/app/` is now under 500 LOC, so no exceptions needed.

## Exit criteria (all green)

- [x] **Every file in `backend/app/` is under 500 LOC.** Verified:
    ```bash
    $ find backend/app -name "*.py" -exec wc -l {} \; | awk '$1 > 500'
    (no results)
    ```
    Top 5 largest files after Wave 4: `variant_query_builder.py` (492), `core/config.py` (489), `clinical_queries.py` (485), `reference/models.py` (484), `reference/router.py` (478). All under the limit.

- [x] **`_sync_tasks` dict is gone.** Only two matches remain, both in docstrings documenting the migration:
    ```
    app/api/admin/task_state.py:3     "Replaces the process-local ``_sync_tasks`` dict..."
    app/api/admin/__init__.py:9       "in-memory ``_sync_tasks`` dict flagged..."
    ```

- [x] **`PhenopacketRepository` exists and is used at ≥ 2 sites.** 4 import sites:
    ```
    app/phenopackets/services/phenopacket_service.py
    app/phenopackets/routers/crud.py
    app/phenopackets/routers/crud_related.py
    app/phenopackets/routers/crud_timeline.py
    ```

- [x] **Backend `make check` green.** 907 passed, 9 skipped, 4 deselected, 3 xfailed. Lint clean, typecheck clean, format clean.

- [x] **HTTP surface baselines green.** All 8 verify tests pass: `admin_status`, `phenopackets_list`, `phenopackets_search`, `phenopackets_compare_variant_types`, `phenopackets_aggregate_summary`, `publications_list`, `reference_genes`, `search_autocomplete`.

- [x] **Bare-except audit clean.** `grep -rn "except Exception" backend/app --include="*.py" | grep -v "# noqa"` returns zero results outside of the documented best-effort handlers that already have `# noqa: BLE001` comments.

- [x] **Frontend `make check` green.** Unchanged from the Wave 3 baseline (23 pre-existing lint warnings, tests and format pass).

## Test count delta

| Wave | Tests | Delta |
|------|------:|------:|
| Post Wave 3 baseline (commit 514c6e8) | 879 | — |
| Task 1: HTTP surface baseline (verify mode) | 887 | +8 |
| Task 2: `test_admin_task_state.py` | 907 | +20 |
| Tasks 3–7: no new test files, refactor only | 907 | 0 |
| **Wave 4 total** | **907** | **+28** |

The 8 "capture" variants of `test_http_surface_baseline.py` skip by default (gated behind `WAVE4_CAPTURE_BASELINE=1`); that's the +8 skipped in the final `make check` run.

## File-size deltas for Wave 4 target files

| File | Before | After (largest split) | Files in split |
|------|:------:|:---------------------:|:--------------:|
| `api/admin_endpoints.py` | 1,164 | 355 (`queries.py`) | 10 |
| `phenopackets/validation/variant_validator.py` | 1,008 | 396 (`vep_recoder.py`) | 7 |
| `phenopackets/routers/crud.py` | 1,003 | 293 (`crud.py`) + 248 (`crud_related.py`) | 4 routers + 2 service/repo files + helpers |
| `phenopackets/routers/comparisons.py` | 861 | 205 (`variant_sql.py`) | 6 |
| `variants/service.py` | 824 | 260 (`vep_api.py`) | 6 |
| `phenopackets/routers/aggregations/sql_fragments.py` | 748 | 315 (`classification.py`) | 5 |
| `reference/service.py` | 722 | 299 (`hnf1b_importer.py`) | 6 |
| `variant_validator_endpoint.py` | 702 | 190 (`recode_route.py`) | 7 |
| `publications/endpoints.py` | 690 | 298 (`list_route.py`) | 5 |
| `search/services.py` | 513 | 206 (`facet.py`) | 5 |

## Surprises

1. **Two-pass test-compatibility for `variant_validator.py`.** First run of the split broke 28 tests because the old flat module had `from app.core.cache import cache` + `from app.core.config import settings` at the top, which the regression suite monkey-patched via `patch("app.phenopackets.validation.variant_validator.cache")`. The fix needed three compat hooks: (1) re-export `cache` and `settings` at the new package `__init__.py` level *before* loading submodules, (2) have `vep_annotate.py` / `vep_recoder.py` look up both names dynamically through the package (`_vv_pkg.cache.get_json(...)`) so the patch affects call-time lookups, and (3) preserve the `_last_request_time` / `_request_count` / `_requests_per_second` / `_max_retries` / `_backoff_factor` / `_cache_ttl` instance attributes via properties that forward to the `RateLimiter` / `VEPAnnotator` / `VEPRecoder` subcomponents. Took two iterations to get right — first pass only did (1), second pass added (2)+(3).

2. **`check_rate_limit_headers` uses `print()` by design.** I almost rewrote it to use `logger.warning(...)` during the split (which is the right call for new code), but the regression suite asserts `patch("builtins.print").assert_called_once()`. Kept the `print` call so the suite stays unchanged — there's a comment in `rate_limiter.py` documenting the legacy contract.

3. **Ruff docstring rules bit both the new `SyncTaskStore` class and the new `FacetService` / `VariantValidator` docstrings.** D102 (Missing docstring in public method) and D416 (Section name should end with a colon) required minor touchups on several files. The per-file-ignore list for tests already waives E501 + D205 + D301 but not D101/D102, so every new test class and method needs a one-line docstring. Not hard to comply with, just caught me off guard given how fast the earlier task refactors went.

4. **`git add -A backend/app/variant_validator_endpoint*` did not stage the deletion of the old flat file** because the glob expansion didn't match a non-existent path, only the new directory. Noticed immediately after `git commit` showed 0 deletions, amended with `git add backend/app/variant_validator_endpoint.py && git commit --amend --no-edit`. Not a real Wave 4 issue, just worth knowing for future package-conversion commits — explicit `git add -A` on the parent directory is safer.

5. **The `publications/endpoints.py` list query had a subtle duplication.** The pre-Wave-4 monolith had the same WHERE clauses repeated verbatim in the main query and the count query, with a real drift risk. During the split I factored out `_build_where_clauses(...)` as a shared helper between the two — not strictly required by the refactor goal, but it removes a class of bugs for free. The commit message flags it.

6. **`sql_fragments.py` already had a very clean internal layering** (paths → variant classification → CTEs → protein domain). The split fell out naturally into 5 files without having to invent groupings. Most of the work was moving constants around and updating the package `__init__.py` re-export list.

## What was deferred

Nothing from the amended plan. Tasks 1-7 all landed on-plan.

## Entry conditions for Wave 5

- [x] **Every file in `backend/app/` is under 500 LOC.** Top 5 largest: `variant_query_builder.py` (492), `core/config.py` (489), `clinical_queries.py` (485), `reference/models.py` (484), `reference/router.py` (478).
- [x] **Router → Service → Repository layering applied to phenopacket CRUD.** Matches the pattern already used in `app/search/`.
- [x] **Admin sync task state is cache-backed (Redis-with-fallback).** Task state now survives worker restarts and is visible across processes.
- [x] **HTTP surface is locked in by 8 baseline JSON fixtures.** Any Wave 5 refactor that accidentally changes a response shape fails `test_http_surface_baseline.py -k verify`.
- [x] **All backend tests green** (907 passing, 9 skipped, 3 xfailed).
- [x] **Frontend `make check` unchanged from Wave 3 baseline** (23 pre-existing lint warnings; tests, lint, format all pass).
- [x] **Tech-debt register exists and is empty.** Future waves have a clear place to add justified exceptions without cluttering commit messages.
- [x] **Ready for Wave 5 frontend decomposition** (the 2026-04-11 platform-readiness review's P0 items are the likely next target — identity lifecycle, ORCID linking, attribution consent, comments, review states, session hardening — but those are a product-scope decision for the next milestone).

**Wave 4 is done.**
