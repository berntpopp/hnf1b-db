# Codebase Refactor Roadmap — Design Spec

**Date:** 2026-04-10
**Status:** Draft (pending user review)
**Source review:** `docs/reviews/codebase-best-practices-review-2026-04-09.md`
**Target overall score:** 6.2 → 8.0

---

## Summary

The 2026-04-09 codebase review identified 26 priority action items across 12 quality dimensions. All 26 findings were verified against the current codebase on 2026-04-10 and remain present. This document turns that review into an actionable, sequenced refactoring roadmap.

**Design constraints (set during brainstorming):**

- Full roadmap covering all 26 items, sequenced end-to-end.
- Strict decomposition target: every file under 500 LOC (matches `CLAUDE.md` rule).
- Test harness first: characterization tests before risky decomposition.
- Free to break: pre-1.0 treatment, breaking changes allowed with documentation.

**Out of scope:**

- No new user-facing features.
- No dependency major-version upgrades.
- No database schema changes except for Redis-backed task state.
- No changes to the GA4GH Phenopackets v2 data model.
- No HttpOnly cookie migration (decision documented only).

---

## Architecture

### Six sequenced waves

```
Wave 1: Stop the bleeding        ────►  quick security + cleanup
Wave 2: Build the safety net     ────►  tests + error plumbing + middleware
Wave 3: Finish in-flight work    ────►  survival refactor completion
Wave 4: Backend decomposition    ────►  admin, crud, repository layer
Wave 5: Frontend decomposition   ────►  api/index split, 5 giant components
Wave 6: Tooling + evolution      ────►  CI, docs, component tests, long-term
```

Each wave is a tracked milestone, not a single PR. Within a wave, individual items land as small focused PRs. A wave is "done" only when every item is merged, CI-green, and has passed the end-of-wave verification pass.

### Ordering rationale

1. **Wave 1 first** — XSS is an unacceptable live vulnerability, hardcoded admin password is a credential leak in git history, and the quick cleanup items cost nothing to fix and make later waves cleaner.
2. **Wave 2 before any decomposition** — Wave 5's frontend decomposition is the riskiest work in the plan. Splitting a 1,421-line D3+Vue component without characterization tests is how you ship silent regressions. Wave 2 also ships security-headers middleware and error-format standardization needed by later waves.
3. **Wave 3 before Wave 4** — `survival.py` is a half-finished refactor. Decomposing anything else while the old and new paths coexist means every change has to be reasoned about twice.
4. **Wave 4 before Wave 5** — Several frontend items depend on backend API stabilization. `api/index.js`'s domain modules will be easier to split after the backend error format is standardized (Wave 2) and admin orchestration has moved behind a clean service layer (Wave 4).
5. **Wave 6 last** — tightening CI coverage thresholds and E2E gates only makes sense after the test harness (Wave 2) and new structure (Waves 4–5) land.

### Acceptance criteria per wave

| Wave | Done when |
|------|-----------|
| 1 | All critical security items patched, all cleanup items merged, no regression in 747 backend tests. CI green. `grep -r "ChangeMe!Admin" backend/` returns nothing. |
| 2 | Every component slated for Wave 5 decomposition has a characterization test file. `backend/app/auth/` modules have dedicated test files. Test DB isolated. Security headers present on all responses. Frontend error boundary intercepts a forced test error. |
| 3 | `survival.py` has no handler functions (moved to `survival_handlers.py` or a `survival/` sub-package). No hardcoded HPO IDs in survival queries. Aggregation commons extracted. 747+ backend tests green. |
| 4 | No backend file over 500 LOC. `admin_endpoints.py` split. `crud.py` split. `PhenopacketRepository` exists. `_sync_tasks` replaced with Redis-backed persistence. Backend tests green. |
| 5 | No frontend file over 500 LOC. `api/index.js` split. All 5 giant components split. `useSyncTask` composable extracted. Characterization tests from Wave 2 still green unchanged. |
| 6 | CI enforces frontend build, coverage thresholds, and E2E. Stale docs fixed. Request ID middleware active. JWT storage decision documented as ADR. Re-scored review ≥ 8.0. |

### Verification between waves

```bash
# Backend
cd backend && make check       # ruff + mypy + pytest
# Frontend
cd frontend && make check      # vitest + eslint + prettier
# Integration smoke
make phenopackets-migrate-test && curl http://localhost:8000/health
```

Each wave ends with a short exit note in `docs/refactor/wave-N-exit.md` summarizing what landed, what was deferred, what surprised us, and the entry conditions for the next wave.

---

## Wave 1 — Stop the bleeding

**Theme:** Ship the emergency security fixes alongside every zero-risk cleanup item so the rest of the plan starts from a clean foundation.

### Items

**1. Fix XSS in FAQ.vue and About.vue** (review P1 #1)

- Install `dompurify` via npm.
- Create `frontend/src/utils/sanitize.js` wrapping `DOMPurify.sanitize()` with a hardened config (strip scripts, event handlers, `javascript:` URLs, whitelist tags markdown actually emits).
- Replace inline `renderMarkdown()` in `frontend/src/views/FAQ.vue` and `frontend/src/views/About.vue` with `sanitize(renderMarkdown(md))`.
- Add a component test rendering a known-malicious payload; assert no `<script>` survives.
- One PR covering both files + the util + the test.

**2. Require `ADMIN_PASSWORD` at startup** (P1 #2)

- Remove hardcoded default in `backend/app/core/config.py:286`. Make `ADMIN_PASSWORD` required via `Field(...)`.
- Add startup validation matching the `JWT_SECRET` pattern — application exits if missing.
- Update `backend/.env.example` to show a placeholder (not a usable password).
- Remove documented default from `CLAUDE.md:528`.
- Update `docker-compose*.yml` environments to reference env vars without defaults.
- Add test asserting `create_admin_user()` raises without env var set.

**3. Replace bare `except Exception:`** (P1 #3)

- `backend/app/phenopackets/validation/variant_validator.py:77` — catch specific parsing exceptions, log with context, re-raise or return typed failure.
- `backend/app/phenopackets/variant_search_validation.py:80` — same treatment.
- `backend/tests/conftest.py:64` — scope to specific DB-cleanup exception types.

**4. Bulk cleanup sweep** (P4 #17, #18, #20 + dead code)

- Delete `frontend/src/api/index.js.backup`.
- Delete `frontend/src/api/auth.js` and `frontend/src/utils/auth.js` after grep confirms no imports.
- Delete commented-out model imports in `backend/app/database.py:100-115`.
- Delete unused `VEPNotFoundError` and `VEPTimeoutError` in `backend/app/variants/service.py`.
- Resolve `backend/app/utils.py` + `backend/app/utils/` namespace collision.
- Resolve `backend/app/schemas.py` + `backend/app/schemas/` namespace collision.
- Resolve Pydantic v2 deprecation warnings in `phenopackets/models.py` and `reference/schemas.py`.

### Exit criteria

- `grep -r "ChangeMe!Admin" . --exclude-dir=.git` returns nothing.
- `grep -r "except Exception" backend/app/phenopackets/` returns only specific, justified instances.
- `find . -name '*.backup'` returns nothing.
- `backend && make check` and `frontend && make check` green.
- XSS characterization test passes.

### Risk

Very low. Biggest risk is namespace collision resolution moving imports; mitigated by running `make test` after each rename and relying on mypy to catch broken imports.

---

## Wave 2 — Build the safety net

**Theme:** Lay down every test and piece of plumbing later waves need, so decomposition is boring instead of terrifying.

### Items

**1. Frontend characterization tests** (blocker for Wave 5)

Add one test file per giant component, exercising observable behavior (mounted output, user interactions, emitted events) but not internals:

- `frontend/tests/unit/views/PageVariant.spec.js`
- `frontend/tests/unit/components/gene/HNF1BGeneVisualization.spec.js`
- `frontend/tests/unit/components/gene/ProteinStructure3D.spec.js`
- `frontend/tests/unit/components/gene/HNF1BProteinVisualization.spec.js`
- `frontend/tests/unit/views/AdminDashboard.spec.js`
- `frontend/tests/unit/views/FAQ.spec.js` (extends the XSS test from Wave 1)

Tests use mocked API responses (fixtures in `frontend/tests/fixtures/`) so they run without a live backend. Target: each spec fails if the component's visible behavior changes but passes across pure internal refactors.

**2. Backend missing critical tests** (P3 #12)

- `backend/tests/test_auth_password.py` — password hashing roundtrip, min-length enforcement, account lockout integration.
- `backend/tests/test_auth_tokens.py` — token generation, expiry, refresh flow, invalid signature, wrong type.
- `backend/tests/test_core_config.py` — startup validation (JWT_SECRET empty, ADMIN_PASSWORD missing), HPO term config integrity, settings overrides.
- `backend/tests/test_phenopackets_crud.py` — integration tests for create/update/delete with auth.

**3. Dedicated test database** (P3 #14)

- Update `backend/tests/conftest.py:36-37` to use a separate `hnf1b_phenopackets_test` database.
- Add `make db-test-init` target that creates/resets the test database.
- Wire CI to point at the test DB, not the app DB.

**4. Standardize error response format** (P2 #9)

- Create shared exception handler in `backend/app/core/exceptions.py` converting `HTTPException`, `ValidationError`, and uncaught errors into `{"detail": ..., "error_code": ..., "request_id": ...}`.
- Register via `app.add_exception_handler` in `backend/app/main.py`.
- Update endpoints that manually construct `{"message": ...}` to raise typed exceptions instead.
- Update frontend axios error interceptor in `frontend/src/api/index.js` to read the new shape.
- Add `backend/tests/test_error_responses.py` for each handler.

**5. Security headers middleware** (P2 #7)

- New `backend/app/core/security_headers.py` middleware adding CSP, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`.
- Register in `backend/app/main.py:58-65`.
- Test asserting headers on every response.

**6. Frontend global error boundary** (P2 #9 continued)

- Add `app.config.errorHandler` in `frontend/src/main.js` routing uncaught errors to `logService.error` + a user-visible Vuetify snackbar.
- Test that forces a render error and asserts the boundary catches it.

### Exit criteria

- All 5 characterization test files exist and pass. Deliberately changing observable behavior causes the spec to fail.
- 4 new auth/config/CRUD test files exist and pass.
- Test DB is separate from app DB.
- CSP header present on every HTTP response; error boundary catches forced errors.
- Backend tests at ~765 (747 + 18 new). Frontend test files at 18 (11 + 7 new).

### Risk

Medium-low. Characterization tests can be flaky if they test too deeply; keep them observable-only.

---

## Wave 3 — Finish in-flight refactors

**Theme:** Resolve the `survival.py` / `survival_handlers.py` ambiguity before decomposing anything else.

### Items

**1. Delete legacy survival handlers from survival.py** (P2 #6)

- Verify each of the 6 `_handle_*` functions in `survival.py` lines 126–968 has an equivalent handler class in `survival_handlers.py`. Write a migration doc mapping old → new.
- Switch every caller to the handler-class path. Run full test suite.
- **Parity test before deletion:** add a numerical-assertion test comparing old vs new handler output for all statistical paths. Don't delete legacy until parity proven.
- Delete the 6 legacy functions. File shrinks from 1,025 → ~150 LOC.

**2. Restructure survival module into sub-package** (P5 #23)

Create `backend/app/phenopackets/routers/aggregations/survival/`:

- `__init__.py` — re-exports router and key classes for backwards-compat imports.
- `router.py` — FastAPI endpoints.
- `handlers.py` — handler classes (moved from `survival_handlers.py`).
- `statistics.py` — Kaplan-Meier, log-rank, statistical tests.
- `queries.py` — SQL fragment builders.

Each file under 500 LOC.

**3. Replace hardcoded HPO IDs** (P3 #16)

- Find all 6+ hardcoded HPO IDs in survival queries.
- Replace with `settings.hpo_terms.*` references.
- Ensure `HPOTermsConfig` in `core/config.py` covers all referenced terms.

**4. Extract aggregation common utilities** (P3 #13)

Create `backend/app/phenopackets/routers/aggregations/common.py`:

- `calculate_percentages(results, total)` helper.
- `materialized_view_fallback(mv_query, fallback_query)` decorator or context manager.

Replace duplicated code in demographics, features, diseases, variants, publications.

### Exit criteria

- `survival.py` does not exist in flat form (shrunk or replaced by `survival/` package).
- `grep "HP:" backend/app/phenopackets/routers/aggregations/survival/` returns nothing.
- `common.py` exists and is imported by at least 5 aggregation modules.
- 747+ backend tests green.

### Risk

Medium. Survival has statistical tests with edge cases; existing backend tests are the safety net. The parity-before-deletion test is the mitigation for numerical drift.

---

## Wave 4 — Backend decomposition

**Theme:** Bring every backend file under 500 LOC. Introduce the repository layer for phenopacket CRUD to match the clean pattern already used in the search module.

### Items

**1. Decompose `admin_endpoints.py` (1,159 LOC)** (P2 #5, P3 #11)

Target structure:

```
backend/app/api/admin/
  __init__.py          # router aggregation
  endpoints.py         # FastAPI routes only; delegate to services
  sync_service.py      # sync orchestration (publications, variants, references, phenopackets)
  task_state.py        # Redis-backed task state (replaces _sync_tasks dict)
  queries.py           # raw SQL admin queries
```

- Each file under 500 LOC.
- **Replace `_sync_tasks` dict with Redis task state.** Use existing Redis client; keys `admin:sync_task:{id}` with TTL. Preserves state across restarts and workers.
- Migrate the 4 sync flows to use the new service.
- New tests: `test_admin_sync_service.py`, `test_admin_task_state.py`.

**2. Decompose `crud.py` (1,002 LOC) + introduce PhenopacketRepository** (P5 #22)

Target structure:

```
backend/app/phenopackets/
  repositories/
    __init__.py
    phenopacket_repository.py    # pure data access (async SQLAlchemy)
  services/
    phenopacket_service.py        # business rules, audit, validation
  routers/
    crud.py                       # HTTP only, delegates to service
```

- Repository exposes: `get_by_id`, `list_paginated`, `list_cursor`, `create`, `update`, `delete`, `count_filtered`.
- Service coordinates audit logging, JSON Patch generation, validation.
- Router: one method per endpoint, ~5 lines each, calls service via `Depends()`.
- Each file under 500 LOC.
- Existing tests should keep passing without changes if the HTTP surface is preserved.

**3. Clean up phenopackets/routers/search.py layering**

- Apply the same 3-layer split, lighter (search.py is closer to the pattern already).
- Extract query building to `backend/app/phenopackets/search_repository.py`.
- Keep `search.py` as thin router.

### Exit criteria

- `find backend/app -name "*.py" -exec wc -l {} \; | awk '$1 > 500'` returns nothing (or only legitimate exceptions documented in `docs/refactor/tech-debt.md`).
- `_sync_tasks` dict no longer exists in code.
- Redis keys visible during a sync run: `admin:sync_task:*`.
- `PhenopacketRepository` class exists and is used by at least CRUD and search layers.
- Backend tests at ~775 (Wave 2's 765 + 10 new repository/admin tests), all green.

### Risk

Medium-high. `crud.py` is the hottest path in the API. Mitigation: keep HTTP surface byte-identical; rely on integration tests added in Wave 2; run a fixture-based request/response diff before and after.

---

## Wave 5 — Frontend decomposition

**Theme:** Bring every frontend file under 500 LOC. The largest and highest-risk wave — this is why we built the characterization tests in Wave 2.

### Items (each component = its own PR)

**1. Split `api/index.js` (953 LOC)** (P2 #4)

Target structure:

```
frontend/src/api/
  http.js              # axios instance, base config
  session.js           # token refresh interceptor, request queue, storage
  endpoints/
    phenopackets.js
    variants.js
    publications.js
    aggregations.js
    search.js
    auth.js
    admin.js
    reference.js
    ontology.js
  index.js             # barrel re-exports for backwards compat
```

- Each file under 300 LOC.
- Remove the circular dependency workaround (dynamic `import()`); the new module boundaries break the cycle naturally.

**2. Consolidate frontend auth ownership** (P3 #15)

- Currently spread across `api/index.js`, `stores/authStore.js`, `router/index.js`.
- Single source of truth: `stores/authStore.js`. Token refresh lives in `api/session.js` but publishes events the store listens to. Router guards read only from the store.
- Delete duplicate state. Add unit tests for the store.

**3. Extract `useSyncTask` composable** (P2 #8)

- 4 polling flows in `AdminDashboard.vue:669-831` collapse into one composable accepting `{ startFn, statusFn, pollInterval, onComplete }`.
- New file: `frontend/src/composables/useSyncTask.js` (< 150 LOC).
- Test: `frontend/tests/unit/composables/useSyncTask.spec.js` with fake timers.

**4. Split `AdminDashboard.vue` (905 LOC)** (P3 #10)

```
frontend/src/views/admin/
  AdminDashboard.vue            # layout only, composes sections (< 200 LOC)
  sections/
    SyncOperationsSection.vue   # 4 sync cards using useSyncTask
    SystemStatusSection.vue
    RecentActivitySection.vue
```

**5. Split `PageVariant.vue` (1,032 LOC)** (P3 #10)

- Extract `useVariantPage(variantId)` composable for data fetching + SEO.
- Extract tab content components: `VariantDetailsTab.vue`, `VariantAnnotationTab.vue`, `VariantPublicationsTab.vue`, `VariantVisualizationTab.vue`.
- `PageVariant.vue` becomes layout + tab routing only.

**6. Split `HNF1BGeneVisualization.vue` (1,421 LOC)** (P3 #10)

- Extract composables: `useGenePlotScales.js`, `useGenePlotZoom.js`, `useVariantFiltering.js`, `useTooltip.js`.
- Extract D3 rendering functions into pure JS utils under `frontend/src/utils/d3/`.
- Component becomes orchestration + template.
- **Fix the zoom bug as part of the split** — the review notes zoom is currently dysfunctional.

**7. Split `ProteinStructure3D.vue` (1,130 LOC)**

- Extract NGL integration into `useNGLViewer.js` composable.
- Extract UI controls into `ProteinViewerControls.vue`.
- Fix `console.warn` hijacking (review #5 medium).

**8. Split `HNF1BProteinVisualization.vue` (1,063 LOC)**

- Same composable + pure-util extraction pattern as HNF1BGeneVisualization.

### Exit criteria

- `find frontend/src -name "*.vue" -exec wc -l {} \; | awk '$1 > 500'` returns nothing.
- Every characterization test from Wave 2 still passes unchanged.
- 17 → 30+ frontend test files.
- Zoom bug fixed as a side-effect of HNF1BGeneVisualization split.
- `v-html` only appears in FAQ/About via the sanitized util.

### Risk

High. Mitigation: characterization tests from Wave 2, one-component-per-PR, manual smoke test of each view after merge.

---

## Wave 6 — Tooling + evolution

**Theme:** Lock in improvements via CI and finish long-term evolution items.

### Items

**1. Tighten CI** (P4 #21)

- Add frontend `npm run build` step to `.github/workflows/ci.yml`.
- Add `npm run test:coverage` with threshold (initial 30%, ratchet up).
- Add backend coverage threshold to `pytest-cov` (initial 70%).
- Add Playwright E2E run in CI on push to main.

**2. Request ID middleware** (P5 #24)

- New `backend/app/core/request_id.py` middleware generating UUID per request, propagating via `X-Request-ID` header, attaching to all log records.
- Frontend axios interceptor echoes header back on errors for correlation.

**3. Fix stale documentation** (P4 #19)

- Create root `README.md` referenced by all sub-READMEs.
- Update `frontend/README.md:16,72,104` to reflect current Vite/Node versions.
- Fix `docs/README.md:41` missing reference.

**4. Top-5 component tests** (P5 #25)

- `SearchCard`, `FacetedFilters`, `AppDataTable`, `HPOAutocomplete`, `VariantAnnotator`.

**5. Document JWT storage decision** (P5 #26)

- Either migrate to HttpOnly cookies (adds CSRF handling) or document accepted risk given Wave 1 XSS fix + Wave 2 security headers.
- Record decision in `docs/adr/0001-jwt-storage.md`.

### Exit criteria

- CI blocks merges on frontend build failure, coverage regression, or failing E2E.
- Every request in logs has a `request_id` field.
- Root README exists and is current.
- 5 new component test files exist.
- ADR for JWT storage committed.
- **Re-scored review ≥ 8.0.**

### Risk

Very low.

---

## Cross-cutting concerns

### PR strategy

- **One logical change per PR.** Splitting `PageVariant.vue` is one PR. Extracting `useSyncTask` is one PR. Never combine a security fix with a refactor.
- **Tests land in the same PR as the code they cover.** Characterization tests in Wave 2 are the only exception — they intentionally land before their target is touched.
- **Every PR must pass `make check` on both sides before merge.** No skipping hooks.
- **PR titles follow Conventional Commits** (repo standard).
- **Wave boundaries are hard checkpoints.** Between waves: full verification suite, re-measure file sizes, write a wave-exit note in `docs/refactor/wave-N-exit.md`.

### How tests evolve across waves

| Wave | Backend tests | Frontend tests | New test infra |
|------|---------------|----------------|----------------|
| Start | 747 | 11 files | Dev DB = test DB (bad) |
| Wave 1 | +3 | +1 | — |
| Wave 2 | +15 | +6 | Dedicated test DB |
| Wave 3 | (stable; existing load-bearing) | — | — |
| Wave 4 | +10 | — | — |
| Wave 5 | — | +13 | — |
| Wave 6 | — | +5 | Coverage thresholds, E2E in CI |
| **End** | **~775** | **~36 files** | **Enforced** |

The characterization tests in Wave 2 are the highest-leverage addition: six small files that unlock all of Wave 5 safely. If anything is cut from Wave 2, don't cut those.

### Risk map

| Risk | Where | Likelihood | Impact | Mitigation |
|------|-------|:----------:|:------:|------------|
| Namespace collision rename breaks imports | Wave 1 | M | M | mypy + full test suite after each rename; rename in its own PR |
| `ADMIN_PASSWORD` env var breaks existing deployments | Wave 1 | H | L | Announce in wave-exit note; only known deployment is the user's |
| Characterization tests too tightly coupled to internals | Wave 2 | M | M | Explicit "observable behavior only" rule; review tests for implementation coupling before merge |
| Survival handler migration loses statistical correctness | Wave 3 | L | H | Parity-assertion test comparing old vs new output before deletion |
| `crud.py` HTTP surface subtly changes during service extraction | Wave 4 | M | H | Wave 2 integration tests; fixture-based request/response diff before and after |
| Gene visualization split makes zoom bug worse | Wave 5 | M | M | Zoom-specific test in Wave 2 characterization; target fixing the bug during the split |
| `api/index.js` split breaks dynamic import cycle workaround | Wave 5 | M | M | Trace cycle explicitly in PR description; verify with build after split |
| Frontend coverage threshold ratcheted too aggressively | Wave 6 | L | L | Start at 30%, raise by 10% per wave-exit retrospective |

### Success metrics

**Mechanical (measurable after every wave):**

- `find backend/app -name "*.py" -exec wc -l {} \; | awk '$1 > 500 {print}'` → empty by end of Wave 4.
- `find frontend/src \( -name "*.vue" -o -name "*.js" \) | xargs wc -l | awk '$1 > 500 {print}'` → empty by end of Wave 5.
- Backend test count strictly monotonic increasing.
- Frontend test file count strictly monotonic increasing.
- Zero files matching `*.backup`.
- Zero occurrences of `ChangeMe!Admin2025` in any tracked file.
- Zero bare `except Exception:` outside documented specific cases.
- All characterization tests from Wave 2 still pass at end of Wave 5 without modification.

**Qualitative (re-assessed at end of Wave 6):**

Re-run the review methodology from `codebase-best-practices-review-2026-04-09.md`. Target overall score ≥ 8.0 (up from 6.2). Sub-score targets:

| Dimension | Current | Target |
|-----------|:-------:|:------:|
| DRY | 5.5 | 8.0 |
| SOLID | 6.0 | 8.0 |
| KISS | 5.5 | 7.5 |
| Modularization | 6.5 | 8.5 |
| Anti-Patterns | 5.5 | 8.0 |
| Testing | 6.5 | 8.0 |
| Error Handling | 7.0 | 8.5 |
| Security | 6.5 | 8.5 |
| Performance | 8.0 | 8.0 (maintain) |
| Coupling | 5.0 | 7.5 |
| Documentation | 4.0 | 7.0 |
| Tooling | 7.0 | 8.5 |

### What happens after Wave 6

The roadmap ends with a re-scored review. Depending on the outcome, possible next efforts:

- Incremental test coverage campaigns (ratcheting thresholds up).
- E2E test expansion.
- Separate work for HttpOnly cookies migration, request queueing for external APIs, or further visualization polish.

All of that is future work, out of scope for this roadmap.

---

## Source of findings

Every item in this roadmap traces back to a numbered priority in the 2026-04-09 review:

| Wave | Review items addressed |
|------|------------------------|
| 1 | P1 #1 (XSS), P1 #2 (admin pw), P1 #3 (bare excepts), P4 #17 (legacy artifacts), P4 #18 (namespace collisions), P4 #20 (Pydantic deprecations) |
| 2 | P2 #7 (security headers), P2 #9 (error format), P3 #12 (missing tests), P3 #14 (test DB) |
| 3 | P2 #6 (dead survival handlers), P3 #13 (aggregation commons), P3 #16 (hardcoded HPO IDs), P5 #23 (survival sub-package) |
| 4 | P2 #5 (admin_endpoints split), P3 #11 (Redis task state), P5 #22 (PhenopacketRepository) |
| 5 | P2 #4 (api/index.js split), P2 #8 (useSyncTask), P3 #10 (giant components), P3 #15 (auth consolidation) |
| 6 | P4 #19 (stale docs), P4 #21 (CI tightening), P5 #24 (request ID), P5 #25 (component tests), P5 #26 (JWT storage) |

All 26 priority action items from the review are mapped. No items dropped, no items added.
