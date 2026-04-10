# Codebase Refactor Roadmap — Design Spec

**Date:** 2026-04-10
**Status:** Draft (pending user review)
**Source review:** `docs/reviews/codebase-best-practices-review-2026-04-09.md`
**Target overall score:** 6.2 → 8.0

---

## Summary

The 2026-04-09 codebase review identified 26 priority action items across 12 quality dimensions. A re-baseline pass on 2026-04-10 verified findings against the current state. **24 of 26 items remain fully present.** Two items show partial progress that rescopes (but does not eliminate) their roadmap work:

- P3 #13 ("aggregation commons"): `backend/app/phenopackets/routers/aggregations/common.py` already exists as a shared-imports module with one MV-existence helper, imported by 6 aggregation modules. However, the `calculate_percentages()` helper and materialized-view fallback pattern are **not** extracted — the duplicated percentage calculation is still present in 10+ call sites (demographics.py 3x, variants.py 2x, features.py 2x, etc). Wave 3 item #4 is rescoped from "create common.py" to "extend common.py with the missing helpers and replace duplicated logic."
- P5 #25 ("top-5 component tests"): `frontend/tests/unit/components/HNF1BProteinVisualization.spec.js` already exists (318 lines) but tests only domain-coordinate data, not component behavior. The Wave 2 characterization work at that path is an **upgrade**, not a net-new file.

**Additional finding from re-baseline:** the review's top-10 oversized file list is not the complete set. The codebase currently has **12 backend files and 17 frontend files over 500 LOC**. Waves 4 and 5 are expanded below to cover all of them, not just the review's top-10.

This document turns the full re-baselined picture into an actionable, sequenced refactoring roadmap.

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
| 1 | All critical security items patched, all cleanup items merged, no regression in 747 backend tests. CI green. `ChangeMe!Admin2025` scrubbed from live config (`backend/.env`, `backend/.env.example`, `backend/app/core/config.py`, `CLAUDE.md`, `.planning/codebase/*.md`, `docker-compose*.yml`) and active planning docs; historical implementation notes (`docs/issues/IMPLEMENTATION-issue-61-user-auth-REVISED.md`) and the source review itself are explicitly permitted to retain the string as historical reference. |
| 2 | Every component slated for Wave 5 decomposition has a characterization test file. `backend/app/auth/` modules have dedicated test files. Test DB isolated. Security headers present on all responses. Frontend error boundary intercepts a forced test error. |
| 3 | `survival.py` has no handler functions (moved to `survival_handlers.py` or a `survival/` sub-package). No hardcoded HPO IDs in survival queries. `calculate_percentages()` and MV-fallback helpers added to existing `common.py`; duplicated percentage logic removed from 5+ aggregation modules. 747+ backend tests green. |
| 4 | Every backend file in `backend/app/` under 500 LOC, with at most 2 documented exceptions in `docs/refactor/tech-debt.md` (each with a written justification and a follow-up ticket). `admin_endpoints.py`, `crud.py`, `variant_validator.py`, `comparisons.py`, `variants/service.py`, `sql_fragments.py`, `reference/service.py`, `variant_validator_endpoint.py`, `publications/endpoints.py`, `search/services.py` all split. `PhenopacketRepository` exists. `_sync_tasks` replaced with Redis-backed persistence. Backend tests green. |
| 5 | Every frontend file in `frontend/src/` under 500 LOC, with at most 3 documented exceptions in `docs/refactor/tech-debt.md`. `api/index.js` split. All 6 giant components split (gene visualization, protein 3D, protein visualization, page-variant, admin dashboard, page-phenopacket). All 11 medium-oversized frontend files also split (PagePublication, AggregationsDashboard, VariantComparisonChart, useSeoMeta, Phenopackets view, InterpretationsCard, Variants view, User view, VariantAnnotator, Home view). `useSyncTask` composable extracted. Characterization tests from Wave 2 still green unchanged. |
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

**3. Replace bare `except Exception:` in production code** (P1 #3, expanded)

Re-baseline found ~10 bare `except Exception:` / `except Exception as e:` occurrences in `backend/app/` (the review's original list of 3 undercounted). Audit and fix every one of them in production code. For each: identify the actual exceptions that can be raised, catch only those, log with context, and re-raise or return a typed failure. Confirmed sites to audit at minimum:

- `backend/app/database.py:84`, `:132`, `:197`
- `backend/app/phenopackets/validation/variant_validator.py:77`, `:500`, `:737`, `:790`, `:960`
- `backend/app/phenopackets/variant_search_validation.py:80`
- `backend/app/phenopackets/routers/crud.py:348`, `:459`, `:532`, `:817`
- `backend/app/api/admin_endpoints.py:329`, `:349`, `:589`, `:609`, `:896`, `:929`
- `backend/app/utils/audit_logger.py:203`
- `backend/app/core/retry.py:115` (may be legitimate in a retry decorator — audit the context)
- `backend/app/core/mv_cache.py:128`
- `backend/app/search/mv_refresh.py:41`, `:88`
- `backend/app/variants/service.py:292`, `:295`
- `backend/app/hpo_proxy.py:111`, `:154`, `:208`, `:306`
- `backend/app/services/ontology_service.py:83`, `:150`, `:178`

**Test-code bare excepts are out of scope for Wave 1.** `backend/tests/conftest.py` and other test teardown fixtures frequently need broad catches for best-effort cleanup; those are addressed in Wave 2 as part of the dedicated-test-DB work, where cleanup semantics are being rewritten anyway.

**4. Bulk cleanup sweep** (P4 #17, #18, #20 + dead code)

- Delete `frontend/src/api/index.js.backup`.
- Delete `frontend/src/api/auth.js` and `frontend/src/utils/auth.js` after grep confirms no imports.
- Delete commented-out model imports in `backend/app/database.py:100-115`.
- Delete unused `VEPNotFoundError` and `VEPTimeoutError` in `backend/app/variants/service.py`.
- Resolve `backend/app/utils.py` + `backend/app/utils/` namespace collision.
- Resolve `backend/app/schemas.py` + `backend/app/schemas/` namespace collision.
- Resolve Pydantic v2 deprecation warnings in `phenopackets/models.py` and `reference/schemas.py`.

**5. Scrub `ChangeMe!Admin2025` from live files and active docs** (P1 #2, cross-cut)

Beyond the config.py fix in item 2, the string appears in 13 files. Remove from the **active set**:

- `backend/.env` (local dev file) — replace with env-var reference.
- `backend/.env.example:15` — replace with `ADMIN_PASSWORD=<required-strong-password>`.
- `CLAUDE.md:528` — replace with `ADMIN_PASSWORD=<required; see .env.example>`.
- `.planning/codebase/INTEGRATIONS.md:209` — replace with placeholder.
- `.planning/codebase/CONCERNS.md:75` — acceptable to retain as a security-concern reference; update to say "was documented" in past tense.
- `plan/01-active/README.md:388` and `plan/01-active/refactoring_optimization_plan.md:280` — replace with placeholder; these are active planning docs.

**Explicitly retained** (historical reference, do not modify):

- `docs/issues/IMPLEMENTATION-issue-61-user-auth-REVISED.md` (4 occurrences — historical implementation record of the original issue).
- `docs/reviews/codebase-best-practices-review-2026-04-09.md` (the review's own finding that triggered this roadmap).
- `docs/superpowers/specs/2026-04-10-codebase-refactor-roadmap-design.md` (this document).

### Exit criteria

- `ChangeMe!Admin2025` removed from all 7 active files listed in item 5; only the 3 explicitly-retained historical files may reference the string.
- `grep -rn "except Exception" backend/app/ | grep -v "# noqa"` returns zero results (production-code scope only; test fixtures are Wave 2).
- `find . -name '*.backup' -not -path '*/node_modules/*' -not -path '*/.git/*'` returns nothing.
- `backend && make check` and `frontend && make check` green.
- XSS characterization test passes (rendering `<script>alert(1)</script>` produces safe HTML).
- Application fails fast on startup when `ADMIN_PASSWORD` env var is unset (tested via `pytest -k test_admin_password_required`).

### Risk

Low-medium. Two concrete risks: (1) namespace collision resolution moving imports — mitigated by running `make check` after each rename and relying on mypy; (2) the expanded bare-exception audit may touch ~10 files at once, so each file is a separate PR, and any catch that turns out to be load-bearing (e.g., in `core/retry.py`) is documented with a justifying comment instead of blindly replaced.

---

## Wave 2 — Build the safety net

**Theme:** Lay down every test and piece of plumbing later waves need, so decomposition is boring instead of terrifying.

### Items

**1. Frontend characterization tests** (blocker for Wave 5)

Add or extend tests for the six components slated for Wave 5 decomposition, plus the FAQ view that received the Wave 1 XSS fix. Each spec exercises observable behavior (mounted output, user interactions, emitted events) but not internals:

- `frontend/tests/unit/views/PageVariant.spec.js` — **new**
- `frontend/tests/unit/components/gene/HNF1BGeneVisualization.spec.js` — **new**, includes a zoom-pan test that currently fails (the review flagged zoom as broken; fail-first proves Wave 5 fixes it)
- `frontend/tests/unit/components/gene/ProteinStructure3D.spec.js` — **new**
- `frontend/tests/unit/components/HNF1BProteinVisualization.spec.js` — **upgrade existing**. The file already exists (318 lines) but tests only domain-coordinate data. Extend with component-mount + observable-behavior cases. Do not delete the existing domain tests; they become one `describe` block alongside a new characterization block.
- `frontend/tests/unit/views/AdminDashboard.spec.js` — **new**
- `frontend/tests/unit/views/FAQ.spec.js` — **new**, extends the XSS test from Wave 1 with broader markdown rendering cases

Tests use mocked API responses (fixtures in `frontend/tests/fixtures/`) so they run without a live backend. Target: each spec fails if the component's visible behavior changes but passes across pure internal refactors.

**Net file count change:** 5 new spec files + 1 upgraded file → +5 new files.

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

- 5 new characterization spec files exist and pass (`PageVariant`, `HNF1BGeneVisualization`, `ProteinStructure3D`, `AdminDashboard`, `FAQ`). 1 existing spec upgraded (`HNF1BProteinVisualization`). Deliberately changing observable behavior in any target component causes its spec to fail.
- 4 new backend test files exist and pass (`test_auth_password.py`, `test_auth_tokens.py`, `test_core_config.py`, `test_phenopackets_crud.py`).
- 1 new backend test file for error-response shapes (`test_error_responses.py`).
- Test DB is a separate Postgres database (`hnf1b_phenopackets_test`), and `make test` no longer mutates dev data.
- CSP header present on every HTTP response; forced render error caught by `app.config.errorHandler`.
- **Test counts after Wave 2:** backend 750 (post Wave 1) → ~765 (+15: 4 auth/config/CRUD + 1 error-response + ~10 small unit tests added along the way). Frontend 11 spec files (post Wave 1) → 16 (+5 new characterization specs, plus 1 upgrade-in-place of HNF1BProteinVisualization).

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

**4. Extend aggregation common utilities** (P3 #13, rescoped)

**Note on partial prior work:** `backend/app/phenopackets/routers/aggregations/common.py` already exists (re-exports shared imports + one `check_materialized_view_exists` helper, imported by 6 modules). However, the duplicated percentage-calculation pattern flagged by the review is still present in 10+ call sites.

Extend the existing module with the missing helpers:

- Add `calculate_percentages(results: list, total: int) -> list` — wraps the `(count / total * 100) if total > 0 else 0` pattern.
- Add `materialized_view_fallback(view_name: str, mv_query, fallback_query)` — decorator or context manager for the existing "check MV → query → fallback" pattern, removing 6+ repetitions.
- Add `AggregationResponse` builder helper if the response construction logic is also duplicated (verify during the PR).

Replace duplicated code in `demographics.py` (3 sites), `variants.py` (2), `features.py` (2), `diseases.py`, `publications.py`, `summary.py`. Existing tests should pass unchanged — this is a pure refactor with no semantic change.

### Exit criteria

- `backend/app/phenopackets/routers/aggregations/survival.py` either no longer exists (moved to `survival/` sub-package) or has shrunk to a router-only shim under 200 LOC.
- `grep -rn "HP:" backend/app/phenopackets/routers/aggregations/survival*` returns zero results outside of docstrings.
- `backend/app/phenopackets/routers/aggregations/common.py` contains `calculate_percentages` and `materialized_view_fallback` exports; `grep -rn "calculate_percentages" backend/app/phenopackets/routers/aggregations/` shows 5+ import sites.
- Percentage calculation pattern `(count / total * 100) if total > 0 else 0` appears fewer than 3 times across the aggregations package (down from 10+).
- Backend tests still green at ~765 (Wave 2 level; Wave 3 adds only parity tests for survival handlers and does not materially change count).

### Risk

Medium. Survival has statistical tests with edge cases; existing backend tests are the safety net. The parity-before-deletion test is the mitigation for numerical drift.

---

## Wave 4 — Backend decomposition

**Theme:** Bring every backend file under 500 LOC. Introduce the repository layer for phenopacket CRUD to match the clean pattern already used in the search module. Covers all 12 backend files currently over 500 LOC, not just the review's top 3.

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

- Apply the same 3-layer split, lighter (`search.py` is closer to the pattern already — the search module already has `repositories.py`, `services.py`, `routers.py`).
- Extract any remaining query building to `backend/app/phenopackets/search_repository.py` if not already covered by the existing `search/repositories.py`.
- Keep `search.py` as thin router. Verify `backend/app/search/services.py` (currently 513 LOC) is also under 500 after cleanup; split into `services/query.py` + `services/result_shaping.py` if needed.

**4. Decompose remaining backend files over 500 LOC**

The review identified 3 top offenders; re-baseline found 9 additional files that must also be split. Each is its own PR. For each, analyze the file's responsibilities and split along concern boundaries — do not blindly slice by line count.

- **`variant_validator.py` (968 LOC)** — `backend/app/phenopackets/validation/variant_validator/`: split into `hgvs_parser.py`, `vcf_parser.py`, `spdi_parser.py`, `validator.py` (public entrypoint). Existing 1,660-line test file covers this; tests should pass unchanged.
- **`comparisons.py` (861 LOC)** — `backend/app/phenopackets/routers/comparisons/`: split into `router.py`, `statistical_tests.py` (chi-square, Fisher, etc), `result_builder.py`. Existing 1,467-line test file is the safety net.
- **`variants/service.py` (823 LOC)** — `backend/app/variants/`: split into `service.py` (public), `vep_client.py` (HTTP), `parser.py` (variant format parsing), `annotation.py` (CADD/gnomAD processing). Removes the "`_format_variant_for_vep` accessed via test" code smell as a side effect.
- **`sql_fragments.py` (748 LOC)** — `backend/app/phenopackets/routers/aggregations/sql/`: split by domain — `variant_fragments.py`, `clinical_fragments.py`, `demographic_fragments.py`. Each under 300 LOC.
- **`reference/service.py` (721 LOC)** — `backend/app/reference/`: split into `service.py` (public), `ensembl_client.py`, `gene_importer.py`, `transcript_importer.py`.
- **`variant_validator_endpoint.py` (702 LOC)** — `backend/app/variant_validator/`: split into `endpoint.py`, `request_handlers.py`, `response_builders.py`. Fix the "reaches through private internals" anti-pattern by promoting the needed helpers to public API.
- **`publications/endpoints.py` (680 LOC)** — `backend/app/publications/`: split into `router.py`, `pubmed_handlers.py`, `citation_formatters.py`.
- **`search/services.py` (513 LOC)** — as noted in item 3, split into `query_builder.py` + `result_shaper.py` if it remains over 500 after Wave 4 item 3.

**Legitimate exceptions (permitted in `docs/refactor/tech-debt.md`):**

- `survival_handlers.py` (1,055 LOC) — Strategy pattern with 6 handler classes, already architecturally clean. Documented as intentional. After Wave 3 restructuring into `survival/handlers.py`, revisit: if still over 500, split by handler family (variant-type, pathogenicity, disease-subtype).

### Exit criteria

- `find backend/app -name "*.py" -exec wc -l {} \; | awk '$1 > 500 {print}'` returns no more than 2 files, and every returned file has a matching entry in `docs/refactor/tech-debt.md` with a written justification.
- `_sync_tasks` dict no longer exists in code.
- Redis keys visible during a sync run: `admin:sync_task:*`.
- `PhenopacketRepository` class exists and is used by CRUD and (via search layering cleanup) the search module.
- Zero bare `except Exception:` remaining in `backend/app/` (all addressed in Wave 1 or during the splits in this wave).
- **Test counts after Wave 4:** backend ~783 (Wave 2's 765 + 18 new tests for repository/admin/task-state/parser splits), all green. Frontend unchanged at 16 files.

### Risk

Medium-high. `crud.py` is the hottest path in the API. Mitigation: keep HTTP surface byte-identical; rely on integration tests added in Wave 2; run a fixture-based request/response diff before and after.

---

## Wave 5 — Frontend decomposition

**Theme:** Bring every frontend file under 500 LOC. The largest and highest-risk wave — this is why we built the characterization tests in Wave 2. Covers all 17 frontend files currently over 500 LOC, not just the review's top 6.

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
- Characterization spec file (upgraded in Wave 2) remains the safety net.

**9. Decompose remaining frontend files over 500 LOC**

The review identified 6 top offenders; re-baseline found 11 additional files that must also be split. Each is its own PR. Characterization tests are not required for these (their existing tests or smoke-level interaction is sufficient), but add a thin render-and-mount test as part of the split PR.

- **`PagePublication.vue` (704 LOC)** — extract `usePublicationPage(pubId)` composable (data fetching + SEO). Extract `PublicationCitationCard.vue` and `PublicationAbstractCard.vue`.
- **`AggregationsDashboard.vue` (693 LOC)** — extract one component per aggregation section (`DemographicsSection.vue`, `ClinicalFeaturesSection.vue`, `VariantsSection.vue`, `PublicationsSection.vue`, `SurvivalSection.vue`). Dashboard becomes layout + tab routing.
- **`PagePhenopacket.vue` (682 LOC)** — same pattern as `PageVariant.vue`: `usePhenopacketPage` composable + tab content components.
- **`VariantComparisonChart.vue` (649 LOC)** — extract organ-system keyword map to `frontend/src/data/organSystemKeywords.js` (fixes review anti-pattern). Extract `useComparisonChartData` composable + pure `chartTransformers.js` util. Remove `document.createElement` direct DOM manipulation.
- **`useSeoMeta.js` (621 LOC)** — the review explicitly flagged this. Split into `useSeoMeta.js` (orchestration), `seoStructuredData.js` (JSON-LD generation), `seoBreadcrumbs.js` (breadcrumb builders), `seoDefaults.js` (static defaults).
- **`Phenopackets.vue` (590 LOC)** — extract `usePhenopacketList` composable (data + pagination + filters) and `PhenopacketListFilters.vue` facet panel.
- **`InterpretationsCard.vue` (557 LOC)** — extract `InterpretationRow.vue` and `useInterpretationFormatting.js` composable.
- **`Variants.vue` (544 LOC)** — fix the broken variant search during the split (review notes the search is currently non-functional). Extract `useVariantList` composable and `VariantListFilters.vue`.
- **`User.vue` (522 LOC)** — extract `UserProfileForm.vue`, `UserPasswordChangeForm.vue`, `UserActivityList.vue`.
- **`VariantAnnotator.vue` (509 LOC)** — extract `useVariantAnnotation` composable + `AnnotationResultCard.vue`. Its Wave 6 characterization test becomes its regression test.
- **`Home.vue` (503 LOC)** — extract hero/stats/features sections into small focused components. Lightest split.

**Legitimate exceptions (permitted in `docs/refactor/tech-debt.md`):** none expected; all 17 files have clear split boundaries.

### Exit criteria

- `find frontend/src \( -name "*.vue" -o -name "*.js" \) -exec wc -l {} \; | awk '$1 > 500 {print}'` returns no more than 3 files, each documented in `docs/refactor/tech-debt.md` with a written justification.
- Every characterization test from Wave 2 still passes **without modification** (internal-refactor-only proof).
- Variant search bug (`Variants.vue`) resolved.
- Zoom bug fixed as a side-effect of `HNF1BGeneVisualization` split (the fail-first test from Wave 2 now passes).
- `v-html` only appears in FAQ/About via the sanitized util.
- **Test counts after Wave 5:** frontend 16 → ~31 files (+15 new unit tests added alongside extracted composables and split components). Backend unchanged at ~783.

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

| Wave | Backend tests | Frontend test files | New test infra |
|------|---------------|---------------------|----------------|
| Start | 747 | 10 files (verified 2026-04-10) | Dev DB = test DB (bad) |
| Wave 1 | +3 | +1 | — |
| Wave 2 | +15 (auth/config/CRUD/error) | +5 new + 1 upgrade-in-place | Dedicated test DB |
| Wave 3 | (stable + parity tests for survival handlers) | — | — |
| Wave 4 | +18 (repository/admin/task-state/parser splits) | — | — |
| Wave 5 | — | +15 (composables + split-component smoke tests) | — |
| Wave 6 | — | +5 (top-5 component tests) | Coverage thresholds, E2E in CI |
| **End** | **~783** | **~36 files** | **Enforced** |

The characterization tests in Wave 2 are the highest-leverage addition: five net-new files + one upgraded file that unlock all of Wave 5 safely. If anything is cut from Wave 2, don't cut those.

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

- `find backend/app -name "*.py" -exec wc -l {} \; | awk '$1 > 500 {print}'` returns no more than 2 files by end of Wave 4, each with a matching entry in `docs/refactor/tech-debt.md`.
- `find frontend/src \( -name "*.vue" -o -name "*.js" \) -exec wc -l {} \; | awk '$1 > 500 {print}'` returns no more than 3 files by end of Wave 5, each with a matching entry in `docs/refactor/tech-debt.md`.
- Backend test count strictly monotonic increasing.
- Frontend test file count strictly monotonic increasing.
- Zero files matching `*.backup` (excluding `node_modules/` and `.git/`).
- `ChangeMe!Admin2025` removed from the 7 active files listed in Wave 1 item 5; only the 3 explicitly-retained historical files may contain the string.
- Zero bare `except Exception:` in `backend/app/` production code (test fixtures excluded — broad catches there are legitimate for best-effort cleanup).
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

All 26 priority action items from the review are mapped.

**Items added beyond the review (discovered during 2026-04-10 re-baseline):**

- Wave 1 item 5: scrub `ChangeMe!Admin2025` from the 7 active files (not just `config.py` as the review implied). Reason: re-baseline found the string in 13 files, not 1.
- Wave 4 item 4: decompose 8 additional backend files over 500 LOC not in the review's top-10 list. Reason: the review's oversized-file list was the top offenders, not exhaustive; re-baseline found 12 total.
- Wave 5 item 9: decompose 11 additional frontend files over 500 LOC not in the review's top-10 list. Reason: same as above; re-baseline found 17 total.

**Items partially completed before the roadmap started (discovered during re-baseline):**

- P3 #13 (aggregation commons): common.py module exists with shared imports + one MV helper. Missing pieces (`calculate_percentages`, MV-fallback decorator) are still scheduled for Wave 3 item 4.
- P5 #25 (HNF1BProteinVisualization test): file exists with domain-data tests only. Wave 2 upgrades in place rather than creates.

No items dropped.
