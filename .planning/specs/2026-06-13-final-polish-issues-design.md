# Design: Final-Polish Open Issues (#7, #140, #133, #48)

- **Date:** 2026-06-13
- **Author:** autonomous execution session (grounded in 4 parallel codebase recon passes)
- **Scope:** Four independent open GitHub issues, each shipped as its **own branch + PR** for
  parallelized review/merge/CI. No cross-issue dependencies.
- **Mode:** Autonomous end-to-end per project goal; decisions documented inline rather than gated.

## Recon corrections to the issues (read first)

The issue bodies were written months ago and several premises are now stale/wrong:

| Issue | Stated premise | Ground truth (verified) |
|---|---|---|
| #140 | TODO at `aggregations.py:1247` | File split into `aggregations/` package; the live site is `aggregations/all_variants.py:240` (`user_id=None`). The TODO comment string is gone; only the `None` remains. **One** endpoint affected. |
| #140 | Needs audit-logging infrastructure | Infra already exists (`log_variant_search`, `get_optional_user`). It is a ~3-line wiring change. |
| #133 | `<script setup>`, 1106 lines, 2 usable composables, a hover tooltip | It is **Options API**, **1132 lines**. The 2 composables are **dead code** (zero consumers). There is **no hover tooltip** → `StructureTooltip.vue` would be net-new feature work, not extraction → **dropped**. |
| #48 | "6 failed locally" implies broken suite | CI gate is green (CI injects `E2E_ADMIN_PASSWORD`). 5/6 local failures are an **admin-password env mismatch** at `apiLogin`. 1 candidate real regression: authenticated-detail axe a11y scan. No selector drift. |
| #7 | (empty body) | App version `2.0.0` is **hardcoded 5×** in `main.py`, disagrees with `pyproject.toml` `0.1.1`. No single source. No runtime Alembic-revision helper. |

---

## Issue #7 — Single version source of truth + `GET /api/v2/version`

### User directive (authoritative)
> "no hardcoding, one single source of truth, we are still in beta e.g. 0.X.Y"

So the app version is the **beta `0.X.Y`** in `pyproject.toml` (`0.1.1`), **not** `2.0.0`. Every reported
version must derive from **one** source with **no** hardcoded copies.

### Runtime constraints (verified)
- Project is **not** an installed distribution → `importlib.metadata.version("hnf1b-api")` fails in dev venv
  and in the running container.
- `tomllib` is available (Python 3.11.15).
- `Dockerfile.prod` runtime stage copies `./app ./alembic alembic.ini config.yaml scripts` but **not**
  `pyproject.toml`. The current dev container happens to have it (built via `COPY . .`).

### Design
1. **`app/core/version.py`** — single resolver, cached at import:
   - `APP_VERSION`: try `importlib.metadata.version("hnf1b-api")` → fall back to walking parents of
     `__file__` for `pyproject.toml` and parsing `[project].version` via `tomllib`
     (guard import: `tomllib` else `tomli`) → final fail-soft sentinel `"0.0.0+unknown"` (never crash).
   - `PHENOPACKET_SCHEMA_VERSION = "2.0.0"` — distinct GA4GH domain constant, defined **once** here
     (it is NOT the app version; it legitimately stays `2.0.0`).
   - `API_PATH_VERSION = "v2"` — the URL-contract major version.
2. **Refactor `app/main.py`** — replace all hardcoded `"2.0.0"` app-version sites (lines ~59, 140, 181,
   195, 218) with `APP_VERSION`, and the `phenopackets_schema`/`phenopackets_version` sites (lines ~182,
   196, 219) with `PHENOPACKET_SCHEMA_VERSION`. FastAPI `version=APP_VERSION`.
   *(Ontology reference-data versions at lines 228–232 are data, not app version → out of scope.)*
3. **`Dockerfile.prod`** — add `COPY --chown=hnf1b:hnf1b ./pyproject.toml ./` to the runtime stage so the
   single source ships to production.
4. **DB schema revision helper** — `app/core/db_version.py` (or within the version service):
   - `applied`: `SELECT version_num FROM alembic_version` via the injected async session.
   - `head`: `alembic.script.ScriptDirectory.from_config(...)` `.get_current_head()` (reads
     `alembic/versions`, which IS shipped to prod).
   - `in_sync`: `applied == head`.
5. **`VersionResponse` schema** (house style: per-package `schemas.py`, `Field(..., description=...)`):
   `api_version`, `api_path_version`, `phenopacket_schema_version`,
   `db_schema_revision` (applied), `db_schema_head`, `db_schema_in_sync`.
6. **Version router** mounted at `prefix="/api/v2"` → `GET /api/v2/version`. Does not duplicate
   `/health`/`/livez`/`/info` (none report DB schema revision). Read-only, unauthenticated.

### Tests
- `tests/test_version.py`: `APP_VERSION` matches `pyproject.toml`, is a valid `0.X.Y` PEP 440 string, not
  `"2.0.0"`, not the sentinel; endpoint returns 200 with all fields; `db_schema_in_sync is True` against the
  migrated test DB; `applied == head`.
- Update any existing assertion expecting `version == "2.0.0"` from `/health`/`/info` (recon: frontend
  `healthService` reads `/health.version` but only displays connection status — no visible break).

### Acceptance
- No literal app-version string anywhere except `pyproject.toml`.
- `/health`, `/livez`, `/info`, `/` and `/api/v2/version` all report `0.1.1`.
- `/api/v2/version` reports the live Alembic revision + head + in-sync flag.

### Branch / PR
`feat/version-source-of-truth` → PR titled `feat(api): single version source of truth + GET /api/v2/version (#7)`.

---

## Issue #140 — user_id tracking for `/all-variants` aggregation

### Decision: log identifier
Pass **`user.email`** (not `str(user.id)`). Rationale: `log_variant_search`'s `user_id: Optional[str]`
param, its docstring example (`"user@example.com"`), and the existing test
(`test_audit_logging.py` asserts `record.user_id == "user@example.com"`) already encode email as the
contract. Following the established, tested interface is the lowest-risk choice. `None` → `"anonymous"`
coercion already exists for unauthenticated requests. (Numeric PK noted as alt; rejected to avoid signature
churn + contract break.)

### Design (3 edits, one file `aggregations/all_variants.py`)
1. Imports: `from app.auth.dependencies import get_optional_user`, `from app.models.user import User`.
2. Signature of `aggregate_all_variants`: add `user: Optional[User] = Depends(get_optional_user),` after `db`
   (matches `search.py:50` pattern).
3. Line 240: `user_id=None,` → `user_id=user.email if user else None,`.

### Tests
- `tests/test_audit_logging.py`: keep the `None → "anonymous"` case; the email case is already covered — no
  change needed there, but add an endpoint-level assertion.
- `tests/test_variant_search.py`: add a case asserting an authenticated `/all-variants` request propagates
  the user email into the audit log (`caplog` + auth dependency override), and the anonymous request logs
  `"anonymous"`.
- Re-run `tests/test_openapi_contract.py` (a new `Depends` param can shift the OpenAPI schema; regenerate
  `_generated_models` if it drifts — known gotcha).

### Branch / PR
`feat/aggregation-user-tracking` → PR `feat(api): track authenticated user in /all-variants audit log (#140)`.

---

## Issue #133 — Extract `ProteinStructure3D.vue` into sub-components (p1-high)

### House pattern (verified)
Options API throughout; props-down / emits-up; **no** provide/inject, **no** Pinia for component-tree state
(exemplar: `components/phenopacket/*` consumed by `PagePhenopacket.vue`). The refactor stays Options API.

### Crux: imperative NGL state
`nglStage`, `nglStructureComponent`, representation handles, and `distanceCalculator` are module-level
imperative handles. They **cannot** be props. The variant panel's filter/sort AND the distance-stats card
both transitively need `distanceCalculator`. → The owner must **pre-compute per-variant distances** (already
cached in `variantDistanceCache` via `calculateAllVariantDistances`) and pass them **down as data**.

### Design (4 components + 1 revived composable)
```
components/gene/
├── ProteinStructure3D.vue        # SMART CONTAINER (~250–350 lines)
└── protein-structure/
    ├── StructureViewer.vue        # presentational: nglContainer ref + loading/error
    ├── StructureControls.vue      # presentational: rep toggle / DNA / domain / reset / distance-line
    ├── VariantPanel.vue           # presentational: filter+sort selects + variant v-list + empty state
    └── DistanceStatsCard.vue      # presentational: distance-to-DNA alert + legend
```
- **`useNGLStructure` composable (revive the dead-code one):** owns `stage`, `structureComponent`,
  representation handles, lifecycle (load `/2h8r.cif`, dispose, resize), wraps `DNADistanceCalculator`.
  Port the two gaps the dead composable lacks: hardcoded CIF path + `useLegacyLights` warning suppression.
- **`ProteinStructure3D.vue` (parent):** keeps **exact** `props` (`variants`, `currentVariantId`,
  `showAllVariants`) + `emits('variant-clicked')` — the unit test and `PageVariant.vue`/`Home.vue` call sites
  depend on this contract; it MUST NOT change. Holds reactive UI state + `variantDistanceCache` + all
  computed; drives the composable via `watch`; passes data down, receives `update:`/`select`/`hover` up.
- **`StructureViewer`** exposes its container ref upward (`@ready` event or `ref`) so the composable can
  mount the NGL stage — the one place props-down/emits-up is awkward.
- **Drop `StructureTooltip.vue`** — no source to extract; net-new, out of scope.

### Verification (no e2e net exists)
- Keep the existing characterization unit test green (`ProteinStructure3D.spec.js`: mounts, renders
  `.ngl-viewport`, accepts 3 props). Add focused unit tests for the new presentational children
  (props render, emits fire) — pure, NGL-free, fast.
- **Manual Playwright verification mandatory** of all 3 modes: single-variant (PageVariant), all-variants
  panel (Home), distance line toggle. Done against a locally started frontend on a free port.

### Branch / PR
`refactor/protein-structure-3d` → PR `refactor(frontend): split ProteinStructure3D into sub-components (#133)`.

---

## Issue #48 — Reliable E2E suite + fix real regressions (p3-low)

### Root-cause split (verified)
- **5/6 local failures**: `apiLogin` uses default password `ChangeMe!Admin2025`; the seeded local admin
  differs; CI injects `E2E_ADMIN_PASSWORD` so CI passes. Setup throws before the browser opens.
- **1 candidate real bug**: authenticated phenopacket-detail **axe** scan — possibly a genuine
  serious/critical a11y violation introduced after the baseline (`PagePhenopacket.vue` "curator history
  tab"). Must inspect.
- **No selector drift.** Playwright wants `:5173` (`--strictPort`), decoupled from the `:3000` dev
  convention; locally `:5173` is occupied by an unrelated `sysndd_app` container (env coupling, not a bug).

### Scope (focused, p3-low — NOT a full 90%-coverage rebuild)
1. **Harden auth**: centralize a single `loginAsAdmin` helper used by all auth specs; add a dev-auth
   fallback (`dev-admin/DevAdmin!2026`, mirroring `accessibility.spec.js`); on credential failure, throw a
   **clear, actionable** error naming `E2E_ADMIN_PASSWORD` (no opaque setup crash).
2. **Fix the real a11y regression** if confirmed: read the axe violations against `PagePhenopacket.vue`,
   fix the app (real value), keep the scan in the suite.
3. **DX**: add `e2e` / `e2e:ui` npm scripts; document local run (env, ports, the `:5173` vs `:3000`
   reality) in `docs/` or `frontend/tests/e2e/README.md`.
4. **Defer** broad new coverage (aggregations charts, variant flow) to a narrower follow-up issue — log it,
   don't silently drop it.

### Verification
- Source of truth = the CI `e2e` gate (must stay green on the PR).
- Where the local env permits, run the specific auth specs against a frontend on a free port + the running
  API with dev-seeded users to confirm the hardened helper.

### Branch / PR
`test/e2e-reliability` → PR `test(frontend): harden E2E auth + fix a11y regression (#48)`.

---

## Execution order (parallel CI)
1. **#140** (tiny) and **#7** (backend) → implement, push, open PRs first so their CI runs while frontend work proceeds.
2. **#133** (large, p1-high) → careful refactor + manual Playwright verify.
3. **#48** (frontend/CI) → harden + investigate a11y.

All four are independent (2 backend files, 2 frontend areas, zero overlap) → safe to have all PRs open
concurrently. Each PR must end CI-green per AGENTS.md before being called done.
