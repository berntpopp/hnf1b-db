# HNF1B-DB Senior Codebase Platform Review

> Status: Updated 2026-04-17 after PRs #254–#261 landed. The prior version of this
> review (2026-04-15) treated findings 1–6 and 8 as open; verification against
> `main` shows almost all of them closed. The remaining live gaps are narrower
> and are listed in the "Open Findings" section below.
>
> The current execution source of truth is
> `.planning/plans/2026-04-15-release-hardening-and-8plus-plan.md`.

Date: 2026-04-15 (original) / 2026-04-17 (revision)
Reviewer: Codex (original) + Claude Opus 4.7 with 5 parallel verification agents (revision)
References:
- `.planning/reviews/2026-04-11-platform-readiness-review.md`
- `.planning/reviews/2026-04-12-09-codebase-best-practices-review.md`
- `.planning/reviews/2026-04-15-path-to-8plus-and-pr-254-review.md` (companion)
- Merged PRs since 2026-04-15: #254 (wave-7-d2), #255 (release-hardening batch 1),
  #256/#257 (auth hardening phase 2), #258 (workflow integrity + timeline
  visibility), #259 (delete revision required), #261 (publication save +
  email conflicts)

## Executive Summary

The 2026-04-15 review identified six critical/high and six medium findings.
Verification against `main` on 2026-04-17 — including a full run of the
targeted test slices the original review said were failing — shows:

- **Findings 1, 2, 3, 4, 5, 6, 8 — FIXED** and covered by regression tests.
- **Finding 7 (revision provenance)** — covered by the green state-flow and
  transitions slice; still worth a dedicated multi-actor test plan before
  closing.
- **Finding 9 (production email fallback)** — **STILL OPEN**. `console`
  backend is not rejected when `ENVIRONMENT=production`.
- **Finding 10 (history/provenance UI)** — **PARTIAL**. Discussion tab shipped;
  a first-class revision/audit tab is still missing.
- **Finding 11 (durable docs linking into `.planning/`)** — **STILL OPEN**.
  Five files still expose `.planning/plans/variant-annotation-implementation-plan.md`
  as a "Developer Guide".
- **Finding 12 (AGENTS.md canonicalization)** — **ESSENTIALLY DONE**. `CLAUDE.md`
  is a 7-line shim; no stale references in `docs/` or the frontend/backend READMEs.

The targeted backend slice called out as failing in the original review
(`test_pwdlib_rehash`, `test_dev_endpoints`, `test_auth*`, `test_state_flows`,
`test_api_transitions`, `test_phenopackets_delete_revision`,
`test_crud_related_and_timeline`, plus the new `test_comments_*`) runs
**203 tests, 0 failures, 0 errors** in ~55 s on the current branch.

Net: the platform has moved materially beyond "promising but risky". The
remaining findings are narrow, well-scoped, and do not by themselves justify
holding a controlled multi-user rollout — with the exception of Finding 9,
which is a real production mis-config hazard and should be fixed before any
production-like deploy.

## Overall Rating

**Overall score: 8.0 / 10** (revised up from 6.2 after verification)

| Area | Rating | Direction vs. 2026-04-15 |
|---|:---:|---|
| Security & session management | 8.0 | Locked/inactive enforcement, SHA-256 refresh sessions, CSRF, session_version bump on role/password change |
| Workflow / data integrity | 7.5 | Timeline visibility enforced; soft-delete uses `with_for_update()`; revision required on delete |
| Frontend platform readiness | 7.5 | In-memory access + HttpOnly refresh cookie; publication binding fixed; dark theme polished |
| Testing & change safety | 8.0 | Targeted slices green; comments/mentions test matrix landed; E2E comments flow shipped |
| Architecture & modularity | 7.5 | Discussion tab + effective-state routing cleanly added; comments service well-isolated |
| Operational readiness | 7.0 | Email console fallback still silent; ADR 0001 (localStorage) not yet superseded despite implementation moving off localStorage; observability (OTel/Sentry) not yet wired |

## What Moved Since 2026-04-15

All claims below were verified against concrete file paths and tests.

### Security and session management

- `backend/app/api/auth_endpoints.py:59-72` `_assert_user_can_receive_tokens()`
  rejects `is_active=false` and unexpired `locked_until` before issuing tokens
  in both `login()` (L278) and `refresh_access_token()` (L341).
- `backend/app/models/refresh_session.py:26-27` stores SHA-256 hashes of refresh
  tokens, not the tokens themselves; `RefreshSession` rows carry JTI + family.
- Password change (L467), password reset (L1056), and deactivation (L694) call
  `_revoke_all_refresh_capability()` which bumps `User.session_version` and
  marks all session rows revoked.
- `backend/app/auth/dependencies.py:210-213` `require_csrf_token()` enforces the
  double-submit cookie pattern on state-changing endpoints.
- `backend/tests/test_auth.py`, `test_auth_refresh_sessions.py`,
  `test_auth_user_management_endpoints.py` cover locked login, deactivated
  refresh, rotation family revoke, and deactivated-cookie rejection.

### Workflow integrity

- `backend/app/phenopackets/routers/crud_timeline.py:155-189` now applies
  `curator_filter()` / `public_filter()` based on role; `test_crud_related_and_timeline.py`
  covers draft-hide-public, deleted-hide-public, deleted-hide-curator (34 passed).
- `backend/app/phenopackets/services/phenopacket_service.py:301-330`
  `soft_delete()` uses `select(...).with_for_update()` before the revision
  compare — race-safe.
- `backend/tests/test_phenopackets_delete_revision.py` covers stale-revision
  409 and concurrent-update-beats-stale-delete across sessions.

### Frontend

- `frontend/src/api/session.js:8-62` keeps the access token in a module-scoped
  `let accessToken = null`; `purgeLegacyBrowserTokenStorage()` actively removes
  any legacy `localStorage` entries on boot.
- `frontend/src/api/transport.js:48-61` uses `withCredentials: true` on `/auth/*`
  routes so the HttpOnly refresh cookie flows automatically.
- `frontend/src/views/PhenopacketCreateEdit.vue:282-286` unifies publications
  under `phenopacket.publications`; `buildSubmissionPhenopacket()` round-trips
  them back into `metaData.externalReferences`. Regression tests in
  `frontend/tests/unit/views/PhenopacketCreateEdit.spec.js:141-179`.
- Tiptap + mention autocomplete, DiscussionTab, and E2E comments flow all
  shipped under PR #254 with Copilot follow-up polish in #254.x.

### Test verification

Ran the exact slices flagged as failing in the 2026-04-15 version:

| Slice | Result |
|---|---|
| `test_pwdlib_rehash.py` | 3 passed |
| `test_dev_endpoints.py` | 7 passed |
| `test_auth*.py` (13 files) | 107 passed |
| `test_state_flows.py` | 12 passed |
| `test_api_transitions.py` | 7 passed |
| `test_phenopackets_delete_revision.py` | 6 passed |
| `test_crud_related_and_timeline.py` | 34 passed |
| `test_comments_*.py` (10 files) | 27 passed |
| **Total** | **203 passed, 0 failed, ~55 s** |

## Open Findings

### 1. Medium → still High in effect: Production email backend can silently fall back to console

`backend/app/core/config.py:413-440` `_validate_smtp_config()` only validates
`SMTP_HOST` / credentials *if* `email.backend == "smtp"`. There is no companion
check that says: "when `ENVIRONMENT=production`, `email.backend` MUST be
`smtp`". A production deploy with `email.backend: "console"` (the default)
logs password-reset, verify-email, and invite tokens to stdout while the app
reports success to the UI.

Recommended fix (mirrors `_refuse_dev_auth_in_prod`):

```python
@model_validator(mode="after")
def _refuse_console_email_in_prod(self) -> "Settings":
    if self.environment == "production" and self.yaml.email.backend == "console":
        raise ValueError(
            "REFUSING TO START: email.backend='console' is only permitted "
            "outside production. Set email.backend: 'smtp' and provide SMTP_HOST."
        )
    return self
```

This is the single remaining finding that is genuinely production-blocking.

### 2. Medium: Revision / curation-history surface is still behind the backend

- `frontend/src/views/PagePhenopacket.vue:168-185` exposes Overview, Timeline,
  and Discussion tabs. Discussion is now real (Tiptap, mentions, resolve).
- The backend carries revision numbers, state transitions, and audit rows, but
  the frontend never renders an authoritative "who changed what when" surface.
- Timeline renders clinical phenotype events, not curation actions.

This is intentional per the D.2 spec (Discussion ≠ audit trail). It still
matters for curator trust. Concrete next step: add `HistoryTab.vue` that reads
the existing audit/revision data and shows actor identity, transition reason,
and a diff summary. Target this in the next hardening window rather than a new
wave.

### 3. Medium: Durable docs still link into `.planning/`

Five files still present `.planning/plans/variant-annotation-implementation-plan.md`
as "Developer Guide":

- `docs/api/README.md:116`
- `docs/api/variant-annotation.md:899`
- `docs/user-guide/README.md:137`
- `docs/user-guide/variant-annotation.md:863`
- `backend/README.md:110`

This violates the `.planning/` vs `docs/` boundary the 2026-04-15 planning
cleanup established. Either promote the variant-annotation architecture into
a stable `docs/architecture/variant-annotation.md` and repoint the links, or
drop the link entirely and rely on the existing `docs/api/variant-annotation.md`
reference material.

### 4. Low: `docs/adr/0001-jwt-storage.md` is superseded in practice but not on paper

ADR 0001 (2026-04-12, status "Accepted") still recommends `localStorage` with
sanitize + CSP mitigations. The live code has since moved to in-memory access
tokens + HttpOnly refresh cookie. Write ADR 0002 ("Move JWT to in-memory +
HttpOnly cookie"), mark 0001 as Superseded, and update `frontend/README.md`
so future reviewers don't chase a ghost. This is paperwork, but it matters for
anyone reading the code against the ADR index.

### 5. Low: Revision provenance deserves a dedicated multi-actor test

`test_state_flows.py` and `test_api_transitions.py` pass, but the original
review flagged multi-actor provenance specifically. Add one test that walks
save → submit → approve → publish → edit → comment → resolve with three
distinct actors, and asserts that every revision row's `changed_by` and
transition reason matches expectation. Cheap to write; removes the last
hand-wave on Finding 7.

## New Findings From Current Best-Practice Sources (2026)

The original review cited Google, FastAPI, SQLAlchemy, OWASP, and Vue. The
verification pass this round pulled in primary sources that were either
missing or incomplete in the original write-up. Each point below cites the
primary source and names a concrete next step.

### Security

- OWASP API Security Top 10 is still on the 2023 edition; no 2024/2025
  refresh. API1 (BOLA), API2 (Broken Auth), API3 (BOPLA) remain the right
  lens for HNF1B-DB. https://owasp.org/API-Security/editions/2023/en/0x00-header/
- OWASP Authentication Cheat Sheet: per-account (not per-IP) lockout counters
  with exponential delay, and MFA where possible. HNF1B-DB has lockout; it
  does not yet have a TOTP or WebAuthn second factor for admin accounts.
  Consider adding WebAuthn for the `admin` role before widening rollout.
- OWASP JWT Cheat Sheet: a revocation denylist is the recommended revocation
  pattern; HNF1B-DB's `RefreshSession` table is effectively that, and the
  SHA-256 column puts it ahead of most FastAPI reference apps.
  https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html

### SQLAlchemy async

- SQLAlchemy 2.0 calls out two patterns that apply directly here: `version_id_col`
  for optimistic concurrency (it emits `UPDATE ... WHERE version_id = :expected`
  for tracked instances), and the rule that `AsyncSession` is not safe across
  concurrent tasks. The current code uses `with_for_update()` which is stronger
  but also serializes; if delete throughput becomes a pain point, migrating to
  `version_id_col` would preserve safety at lower lock cost.
  https://docs.sqlalchemy.org/en/20/orm/versioning.html
  https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

### Frontend performance for curators

- Vue 3.5 (current through April 2026) ships a reactivity refactor worth
  −56% memory and up to 10× faster deep arrays. Vapor mode is still in 3.6
  beta — do not ship it in a clinical tool yet.
  https://blog.vuejs.org/posts/vue-3-5
- `shallowRef` is the documented path for large phenopacket JSON blobs and
  long discussion threads. https://vuejs.org/api/reactivity-advanced.html
- Vuetify 3 has `VDataTableVirtual` and `v-virtual-scroll`; the current
  `CommentList` and any "all phenopackets" table should switch to them once
  typical record counts exceed ~200.
  https://vuetifyjs.com/en/components/data-tables/virtual-tables/

### Accessibility (WCAG 2.2)

- WCAG 2.2 added six AA criteria directly relevant to curators on tablets:
  2.4.11 Focus Not Obscured (Min), 2.5.7 Dragging Movements, 2.5.8 Target
  Size (≥24×24 CSS px), 3.2.6 Consistent Help, 3.3.7 Redundant Entry, 3.3.8
  Accessible Authentication. Next step: audit all touch targets in
  `PhenopacketCreateEdit.vue`, transition menu, and comment composer against
  24×24 px, and confirm dark-theme focus-ring contrast ≥ 3:1.
  https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- ARIA Authoring Practices Guide patterns for the comment composer
  (combobox + listbox for mentions), tabs (Discussion / Overview / Timeline),
  and live regions for save/resolve feedback. Verify `MentionSuggestionList`
  matches the combobox pattern (arrow keys, Esc to dismiss, `aria-activedescendant`).
  https://www.w3.org/WAI/ARIA/apg/patterns/

### Curation latency budget

- GA4GH Phenopackets v2 remains the authoritative schema; no v3. ClinGen VCI
  four-state workflow (In-progress / Provisional / Approved / New-Provisional)
  maps onto the current state machine cleanly.
  https://www.ga4gh.org/product/phenopackets/
  https://pmc.ncbi.nlm.nih.gov/articles/PMC8764818/
- No consortium publishes a specific latency budget, so anchor on Nielsen's
  well-established thresholds: ≤100 ms "feels instant", ≤1 s "keeps flow",
  ≤10 s "user disengages". Recommended SLOs for HNF1B-DB:
  - autocomplete / mention search: p95 ≤ 200 ms
  - autosave round-trip: p95 ≤ 500 ms
  - detail page TTI: p95 ≤ 1.5 s on a 3G-ish mobile profile
  - publication save: p95 ≤ 1 s
  These should be wired into Playwright timings and an observability
  dashboard, not just guessed.

### Observability

- OpenTelemetry has a stable FastAPI auto-instrumentation
  (`opentelemetry-instrumentation-fastapi` 0.62b0 as of April 2026).
  https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html
- Sentry FastAPI + Vue integrations are straightforward to wire
  (`@sentry/vue` with `browserTracingIntegration` + `replayIntegration`).
  https://docs.sentry.io/platforms/python/integrations/fastapi/
  https://docs.sentry.io/platforms/javascript/guides/vue/
- HNF1B-DB currently has structured logging; it does not have request
  tracing or frontend error capture. Add both before the next user-facing
  milestone, not after — curator bug reports without traces are very hard
  to resolve.

### Playwright

- Playwright best practices (still the 2025/2026 guidance): `getByRole`
  over CSS, web-first assertions (`toBeVisible()` not `isVisible()`), avoid
  fixed waits, keep each test isolated. The current comments E2E already
  simplified to a single admin session, which matches the guidance.
  https://playwright.dev/docs/best-practices

## Recommendations (ordered)

### Immediate (block on these before any production-like deploy)

1. Add the `_refuse_console_email_in_prod` validator to `backend/app/core/config.py`.
2. Write ADR 0002 superseding 0001; update `frontend/README.md` to describe the
   in-memory + HttpOnly cookie model so the code and the docs agree.
3. Remove or redirect the five `.planning/plans/variant-annotation-implementation-plan.md`
   references in durable docs. Promote the content into `docs/architecture/` if
   it genuinely belongs to the stable corpus.

### Near-term (curator experience and platform quality)

4. Add `HistoryTab.vue` backed by the existing audit/revision tables. Show
   actor identity, transition reason, and diff summary.
5. Add the multi-actor provenance test described above.
6. Add TOTP or WebAuthn second factor for admin accounts.
7. Wire OpenTelemetry FastAPI auto-instrumentation + Sentry (backend + frontend).
   Start collecting p95 for the four curator-latency SLOs.
8. Audit WCAG 2.2 AA compliance in the edit, transition, and discussion flows —
   specifically target size, focus appearance in dark theme, and the combobox
   pattern on mentions.
9. Swap `CommentList` and any list views that can exceed ~200 rows to
   `v-virtual-scroll` / `VDataTableVirtual`. Convert large phenopacket JSON
   blobs on detail pages to `shallowRef`.

### Medium-term (finish the platform bundle)

10. ORCID link/unlink + attribution preferences (Bundle E).
11. Session inventory UI (per-device active sessions, "log everyone else out").
12. Private contributor dashboard (my created, my reviewed, unresolved
    discussions, recent activity).
13. Keyboard-first curation: document and implement shortcut keys for
    save-and-next, submit, publish, resolve, and mention — high-throughput
    curators will notice the difference.

## Final Assessment

HNF1B-DB cleared almost every blocker identified on 2026-04-15 within 48 hours,
with verifiable tests and clean code. This is an unusually strong close-out
rate for a review of this depth.

The remaining work is narrow, well-understood, and mostly non-security:
- one real production hazard (email console fallback),
- one ADR to supersede,
- one doc-hygiene sweep,
- and a handful of curator-UX, observability, and a11y upgrades that will
  matter as the user base expands.

**Recommendation:** land the immediate three items, then treat the next
milestone as "curator-experience and operational polish" — history UI,
observability, WCAG 2.2 audit, virtualization, keyboard shortcuts. The core
platform is now credible for controlled multi-user rollout once the email
validator lands.

## Sources

Security + auth:
- OWASP API Security Top 10 2023: https://owasp.org/API-Security/editions/2023/en/0x00-header/
- OWASP Authentication Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- OWASP JWT Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- OWASP CSRF Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- FastAPI OAuth2/JWT tutorial: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/

Data integrity:
- SQLAlchemy 2.0 versioning: https://docs.sqlalchemy.org/en/20/orm/versioning.html
- SQLAlchemy 2.0 asyncio: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

Frontend + accessibility:
- Vue 3.5 release notes: https://blog.vuejs.org/posts/vue-3-5
- Vue reactivity advanced: https://vuejs.org/api/reactivity-advanced.html
- Vuetify virtual tables: https://vuetifyjs.com/en/components/data-tables/virtual-tables/
- WCAG 2.2 What's New: https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- ARIA APG patterns: https://www.w3.org/WAI/ARIA/apg/patterns/

Clinical curation context:
- GA4GH Phenopackets: https://www.ga4gh.org/product/phenopackets/
- ClinGen VCI (Genome Medicine 2022): https://pmc.ncbi.nlm.nih.gov/articles/PMC8764818/

Observability + testing:
- OpenTelemetry FastAPI: https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html
- Sentry FastAPI: https://docs.sentry.io/platforms/python/integrations/fastapi/
- Sentry Vue: https://docs.sentry.io/platforms/javascript/guides/vue/
- Playwright best practices: https://playwright.dev/docs/best-practices

Code review framing:
- Google Engineering Practices: https://google.github.io/eng-practices/review/reviewer/looking-for.html
- SmartBear Code Review Process: https://smartbear.com/learn/code-review/guide-to-code-review-process/
