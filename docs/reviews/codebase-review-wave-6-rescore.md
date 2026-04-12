# Codebase Quality Re-Score — Wave 6 Exit

**Date:** 2026-04-12
**Previous review:** [docs/reviews/codebase-best-practices-review-2026-04-09.md](codebase-best-practices-review-2026-04-09.md) (score 6.2)
**Roadmap:** [docs/superpowers/specs/2026-04-10-codebase-refactor-roadmap-design.md](../superpowers/specs/2026-04-10-codebase-refactor-roadmap-design.md)

## Overall Score: 8.1 / 10

Target was ≥ 8.0 at Wave 6 exit. **Target met.**

## Metrics at a glance

- **Backend LOC:** 26,430 across `backend/app/` (Python)
- **Frontend LOC:** 32,095 across `frontend/src/` (Vue + JS)
- **Backend tests:** 1,131 collected (up from ~780 at Wave 5 exit; Wave 5c identity lifecycle added ~350)
- **Frontend tests:** 31 spec files (26 new component tests in Wave 6 not individually counted — single-file multi-test)
- **Bare `except Exception`:** 2 (down from ~30+ pre-Wave 1; both remaining are in `app/auth/password.py` and are intentional — see Remaining Debt below)
- **Files > 500 LOC:** backend 3, frontend 16 (see Remaining Debt)

## 12-Dimension Scorecard

| # | Aspect | Previous | Current | Delta | Wave | Evidence |
|---|--------|:--------:|:-------:|:-----:|:----:|----------|
| 1 | DRY | 5.5 | 8.0 | +2.5 | 3, 5 | Aggregations common helpers extended; `useSyncTask` composable replaced 4 copy-paste poll loops; identity lifecycle flows share a single token-service module |
| 2 | SOLID | 6.0 | 8.0 | +2.0 | 3, 4, 5 | `PhenopacketRepository` isolates persistence; sub-packages (`phenopackets/`, `ontology/`, `publications/`, `reference/`) have single responsibilities; composables split presentation from data |
| 3 | KISS | 5.5 | 8.0 | +2.5 | 3, 4, 5 | 17 file splits across the codebase; every remaining >500-LOC file has (or will have) a tech-debt entry with a re-evaluation trigger |
| 4 | Modularization | 6.5 | 8.5 | +2.0 | 3, 4, 5 | Sub-packages throughout backend; frontend views decomposed into feature composables + components |
| 5 | Anti-Patterns | 5.5 | 8.0 | +2.5 | 1, 3 | ~30 bare excepts narrowed to named exceptions; 2 remaining in `password.py` are deliberate security choices; 4 dead files deleted |
| 6 | Testing | 6.5 | 8.0 | +1.5 | 2, 4, 5, 6 | Characterization harness + per-wave unit tests + 5 new component tests + Playwright E2E scaffolded in CI; 1,131 backend tests total |
| 7 | Error Handling | 7.0 | 8.5 | +1.5 | 2, 6 | Standardized `{detail, error_code, request_id}` shape; Wave 6 populates `request_id` via middleware so frontend and backend logs correlate |
| 8 | Security | 6.5 | 8.5 | +2.0 | 1, 2, 5a, 5c | XSS fix via `sanitize()` + characterization test; CSP + security headers middleware; mandatory `ADMIN_PASSWORD` env; pwdlib Argon2id; ADR 0001 for JWT storage decision |
| 9 | Performance | 8.0 | 8.0 | 0 | — | Maintained — cursor pagination, MV cache, Redis task state all still in place |
| 10 | Coupling | 5.0 | 7.5 | +2.5 | 4, 5, 6 | `PhenopacketRepository` broke direct-ORM coupling; auth store consolidated; request ID middleware decouples correlation from business logic |
| 11 | Documentation | 4.0 | 7.5 | +3.5 | 6 | Root `README.md` exists and resolves from sub-READMEs; `docs/adr/0001-jwt-storage.md`; stale Node/Vite/API references fixed; every wave has an exit note; tech-debt register lists architectural compromises with re-evaluation triggers |
| 12 | Tooling | 7.0 | 9.0 | +2.0 | 6 | CI: frontend build gate (Wave 5a) + backend 70% coverage fail-under + frontend 30% coverage floor + Playwright E2E job + lint-staged/husky pre-commit gate + `npm run build` prod gate already live; ruff + mypy + pytest pre-existing |

**Weighted mean:** 8.1 — the "Documentation" dimension is the single largest mover (+3.5), driven by Wave 6 landing the root README, ADR, and fixing stale references all in one wave.

## Per-Wave Contribution Summary

- **Wave 1 — Stop the bleeding (15 tasks):** XSS patched, admin password required, ~30 bare `except Exception` narrowed, 4 dead files deleted.
- **Wave 2 — Safety net (15 tasks):** fixtures, 6 characterization specs, 5 backend test modules, dedicated test database in CI, standardized error shape, security headers middleware, frontend error boundary.
- **Wave 3 — In-flight refactors (9 tasks):** survival legacy handlers deleted, sub-package created, HPO IDs moved to settings, aggregation common helpers extended.
- **Wave 4 — Backend decomposition (7 tasks):** 12 backend files split under 500 LOC, `PhenopacketRepository` extracted, Redis-backed task state.
- **Wave 5 — Frontend decomposition (10 tasks, 20+ sub-tasks):** 17 frontend files split under 500 LOC, zoom bug fixed, variant search fixed, `useSyncTask` composable, dev-auth quick-login (Wave 5a, five-layer defense), admin endpoints (Wave 5b), identity lifecycle — invite/reset/verify — (Wave 5c, 350+ tests).
- **Wave 6 — Tooling + Evolution (7 tasks, this wave):** CI tightened (coverage thresholds + Playwright E2E), request ID middleware + frontend correlation, root README + stale docs fixed, top-5 component tests, ADR 0001 for JWT storage, this re-score.

## Remaining Debt

### Backend files exceeding 500 LOC (tech-debt register needs updating)

After Wave 5c, three backend files are above the 500-LOC rule but not listed in `docs/refactor/tech-debt.md`:

| File | Lines | Reason | Next step |
|------|:-----:|--------|-----------|
| `backend/app/api/auth_endpoints.py` | 983 | Wave 5c landed invite/reset/verify + admin mgmt endpoints in a single router | Split into `auth/login.py`, `auth/invite.py`, `auth/reset.py`, `auth/verify.py`, `auth/admin.py` when the next auth-touching wave begins |
| `backend/app/core/config.py` | 568 | Settings surface grew with dev-auth, identity lifecycle, and SMTP config | Group into sub-models (`AuthConfig`, `EmailConfig`, already partially done) and `compose()` |
| `backend/app/phenopackets/models.py` | 545 | JSONB data-class mirroring phenopackets v2 schema | Acceptable — this is spec-driven data shape; not intrinsically splittable without obscuring the schema |

**Action:** raise a follow-up to add register entries for the first two; the third is a justified exception that should be recorded as such.

### Frontend files exceeding 500 LOC

16 frontend files remain above 500 LOC. The largest are gene/protein visualization components (1,421 / 1,130 / 1,063 LOC) that encapsulate D3.js rendering — splitting them risks breaking the rendering pipeline without test coverage. Ranking of next candidates:

- `PageVariant.vue` (1,032) — split by section (overview / annotations / cohort) in a future wave.
- `AdminDashboard.vue` (752) — extract per-card composables.
- `PagePublication.vue` (704), `AggregationsDashboard.vue` (693), `PagePhenopacket.vue` (682) — all candidates for the same per-section split pattern.

### Remaining bare `except Exception`

Two instances in `backend/app/auth/password.py` — both in password verification (`verify_password`, `verify_and_update`). They swallow pwdlib exceptions and return a failure value, which is the correct security posture (never leak why verification failed). **Recommendation:** keep, but add a `# noqa: BLE001` with an inline comment explaining the security rationale so the CI pattern-check stays green while the decision is documented.

### Frontend `localStorage` JWT

See [ADR 0001](../adr/0001-jwt-storage.md). Deferred by policy, not by oversight.

### `package.json` pre-commit hook

The hook forbids staging `package.json` without `package-lock.json`, which blocks pure-script-only changes (no dep delta). Non-blocking, but a future hook refinement could diff package.json and only require a lockfile update when `dependencies` / `devDependencies` / `peerDependencies` actually change.

## Next Roadmap Candidates

1. **Coverage ratchet wave** — bump frontend floor 30 → 50 → 70, backend floor 70 → 80 as tests land.
2. **Auth router split** — break up the 983-LOC `auth_endpoints.py` per the table above.
3. **Gene visualization decomposition** — the 1,421-LOC `HNF1BGeneVisualization.vue` needs D3 pipeline tests before it can be safely split.
4. **CSP tightening** — remove `'unsafe-inline'` once every inline `<script>` in the index shell is audited.
5. **Typed logger abstraction** — replace the scattered `window.logService` with a typed facade; the underlying sanitization logic can stay.
6. **SMTP delivery** — implement `SMTPEmailSender` using `aiosmtplib` and add Mailpit to `docker-compose.dev.yml` (already scaffolded into the Wave 6 plan).

The roadmap from 2026-04-10 is **complete**: every one of its 26 priority items has been addressed. This record triggers the archive step described in `CLAUDE.md` and the `/gsd-audit-milestone` workflow.
