# Wave 2 Exit Note

**Date:** 2026-04-10
**Branch:** `chore/wave-2-safety-net` (off `main` after Wave 1 merged as PR #229)
**Starting test counts:** backend 744 passed + 1 skipped + 3 xfailed (752 collected), frontend 11 spec files.
**Ending test counts:** backend 792 passed + 1 skipped + 3 xfailed (800 collected, **+48 tests**), frontend 15 unit spec files + 2 e2e = 17 total (**+5 unit**).

## What landed

- **Task 1** (15c99ca): `frontend/tests/fixtures/` directory with 4 JSON sample payloads (phenopacket, variant, publication, aggregation-demographics) and `index.js` re-exports.
- **Task 2** (27f5754): `PageVariant.vue` characterization spec. 6 tests. Used inline samples (not fixtures) because the component consumes very different field names than the plan's toy shape — the spec shape was rebuilt to match the real component contract (`variant_id`, `classificationVerdict`, `molecular_consequence`, etc). Weakened one assertion: the CADD-score test targets the molecular-consequence chip instead, because CADD is not rendered in the hero section at mount time.
- **Task 3** (6c946e5): `HNF1BGeneVisualization.vue` characterization spec. 4 passing tests + 1 `it.fails` zoom test documenting the broken zoom bug (issue #92). Marker selector updated to `.variant-circle` (actual class). Variant fixture shape rebuilt to use `hg38` strings (positions inside the HNF1B gene range 37,686,430–37,745,059), not the plan's out-of-range toy positions.
- **Task 4** (11eb5de): `ProteinStructure3D.vue` characterization spec. 5 tests. NGL mock rewritten for the real `import * as NGL from 'ngl'` namespace import and expanded with the methods the component actually calls (`removeAllRepresentations`, `addComponentFromObject`, etc). Real props discovered: `variants`, `currentVariantId`, `showAllVariants` — **not** `pdbId` as the plan assumed. `@/utils/dnaDistanceCalculator` also mocked.
- **Task 5** (f9a990d): `HNF1BProteinVisualization.spec.js` upgraded with 4 characterization tests alongside the existing 29 domain-coordinate tests (all preserved). Marker selector set to `.lollipop-circle` (actual class). Variant sample shape uses `variant_id` + `protein: 'NP_000449.3:p.Arg100Cys'` because the real `extractAAPosition` reads `variant.protein` via `extractPNotation()`, not the plan's `position`/`hgvs_p`.
- **Task 6** (e736813): `AdminDashboard.vue` characterization spec. 4 tests. Real `@/api` method names found and mocked: `getAdminStatus`, `getAdminStatistics`, `startPublicationSync`/`getPublicationSyncStatus`, `startVariantSync`/`getVariantSyncStatus`, `startReferenceInit`, `startGenesSync`/`getGenesSyncStatus`, `getReferenceDataStatus` — not the plan's `getSystemStatus`/`syncPublications`/etc. Added `ResizeObserver` polyfill.
- **Task 7** (7b94bb9): `backend/tests/test_auth_password.py` with 16 tests. Real function is `get_password_hash`, not `hash_password`. Added a `TestPasswordStrength` class covering the 5 strength-validation rules that surfaced in the real module.
- **Task 8** (bb09b5f): `backend/tests/test_auth_tokens.py` with 14 tests. Real API is positional (`create_access_token(subject, role, permissions)`), not dict-based; decoder is `verify_token` (not `decode_token`); it wraps JWT errors in `HTTPException(401)`. Added token-type-confusion tests (access-used-as-refresh, refresh-used-as-access) and `jti` uniqueness tests.
- **Task 9** (7af523d): `backend/tests/test_core_config.py` with 6 tests across `TestJwtSecretValidation`, `TestAdminPasswordValidation`, `TestHpoTermsConfig`. Wave 1's validators already handle whitespace via `.strip()`, so the whitespace test passed as-written. HPO terms exposed as a `@property` proxying to `yaml.hpo_terms` — smoke-checked concrete term IDs.
- **Task 10**: **SKIPPED.** Dedicated test DB was already landed in Wave 1 bonus `55dcce9` (`backend/conftest.py` safety rail + `NullPool` rebind + isolation between tests). The plan's T10 changes (Makefile `db-test-init`, CI env update) are already in place from Wave 1.
- **Task 11** (ca71554 + **741651a** fix): `backend/app/core/exceptions.py` with three handlers (HTTPException, RequestValidationError, generic Exception) returning the standard `{detail, error_code, request_id}` shape. Registered in `main.py`. `frontend/src/api/index.js` interceptor updated to normalize errors into `error.normalized = { detail, errorCode, requestId }` with backwards-compat for legacy list-shaped FastAPI validation errors. 3 new backend tests. **Follow-up fix 741651a**: the original `str(exc.detail)` coercion mangled `HTTPException(detail={...})` instances used by the phenopacket update-conflict endpoint; the handler now preserves str/dict/list/primitive detail unchanged and only coerces unknown non-serializable values. `test_phenopacket_curation::test_update_phenopacket_conflict` restored to passing.
- **Task 12** (3d391a0): `backend/app/core/security_headers.py` with `SecurityHeadersMiddleware` (CSP, X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy strict-origin-when-cross-origin, Permissions-Policy). Registered in `main.py` before CORS. 5 new tests.
- **Task 13** (484db58): `frontend/src/main-error-handler.js` exporting `configureErrorHandler(app, logError)`. Wired into `main.js` so uncaught Vue errors flow through `window.logService.error`. 2 new tests.
- **Task 14** (816bc66): `backend/tests/test_phenopackets_crud.py` with 4 integration tests — list (no auth), create (403), update (PUT, 403), delete (403). Real router uses `PUT` (not `PATCH`) and requires a `change_reason` body. Deeper coverage deferred to Wave 4 when the repository layer lands.

## Surprises

1. **Plan task texts diverged from real code.** Tasks 2, 3, 4, 5, 6, 7, 8 all required real function/prop/field-name discovery because the plan was written against assumed shapes. Characterization tests passed in every case after adjusting to reality — the plan's iteration guidance handled this gracefully.
2. **Plan Task 6 API methods wrong.** AdminDashboard uses `getAdminStatus`/`startPublicationSync`/etc, not `getSystemStatus`/`syncPublications`. Mocks adjusted.
3. **T11 broke a curation test.** The original `str(exc.detail)` coercion mangled the phenopacket update-conflict endpoint's dict detail, producing `TypeError: string indices must be integers` in the existing test. Fixed in follow-up commit `741651a`.
4. **Cherry-pick conflict on `main.py`**: T11 and T12 both registered into `backend/app/main.py`. Resolved by keeping both (exception handlers registered first, then `SecurityHeadersMiddleware` before CORS).
5. **`frontend/tests/setup.js` exists but is not wired** into `vitest.config.js` (`setupFiles` missing), so every new spec had to polyfill `ResizeObserver` and register Vuetify inline. Flagged for Wave 6 (tooling evolution).
6. **Worktree agents**: every fresh worktree needed `uv sync --group test` (backend) or `npm install` (frontend) before tests could run. That's expected but adds ~30s to each agent's startup. Considered out-of-scope for Wave 2.
7. **Backend pre-existing lint**: 21 frontend ESLint warnings persist across unrelated files. Not part of this wave.

## What was deferred

- Nothing from the plan scope. Task 10 was legitimately skipped (already done in Wave 1).
- `frontend/tests/setup.js` not wired into vitest — parked for Wave 6.
- CSP header tightening — plan explicitly marked as out-of-scope for Wave 2.

## Entry conditions for Wave 3

- [x] All Wave 2 exit checks green (backend `make check`: 792 passed; frontend `make check`: all green).
- [x] Characterization tests exist for every Wave 5 decomposition target (PageVariant, HNF1BGeneVisualization, ProteinStructure3D, HNF1BProteinVisualization, AdminDashboard, FAQ).
- [x] Error response shape standardized backend-side; frontend interceptor normalizes with backwards-compat fallback.
- [x] Security headers present on every response.
- [x] Dedicated test DB in use (Wave 1 bonus); no "same database as development" workaround anywhere.
- [x] Frontend global error boundary active.

**Wave 3 can begin.**
