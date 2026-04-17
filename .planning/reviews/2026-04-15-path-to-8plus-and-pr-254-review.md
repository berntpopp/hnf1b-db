# HNF1B-DB Path To >8.0 And PR #254 Review

> Status: Updated 2026-04-17. The 2026-04-15 version of this review treated PR #254
> as open and argued the platform was not yet at >8. Both premises have since
> shifted: PR #254 merged on 2026-04-15 (merge commit `fec235f`), and the
> companion hardening PRs #255–#259 and #261 landed inside the following 48
> hours. Verification against `main` on 2026-04-17 puts the platform at a
> defensible 8.0, with a narrow list of remaining gaps. See the companion
> document `.planning/reviews/2026-04-15-senior-codebase-platform-review.md`
> for the detailed file-level evidence.
>
> The current execution source of truth is
> `.planning/plans/2026-04-15-release-hardening-and-8plus-plan.md`.

Date: 2026-04-15 (original) / 2026-04-17 (revision)
Scope:
- `main` as of commit `195c7c1` (2026-04-17)
- historical plans, exit notes, and deferred items
- PR #254 (merged `fec235f`) and follow-up PRs #255–#259, #261
- current primary best-practice sources (OWASP, SQLAlchemy, Vue, WCAG 2.2,
  GA4GH, Playwright, OpenTelemetry, Sentry)

References reviewed:
- `.planning/reviews/2026-04-12-09-codebase-best-practices-review.md`
- `.planning/reviews/2026-04-11-platform-readiness-review.md`
- `.planning/reviews/2026-04-15-senior-codebase-platform-review.md` (companion)
- `.planning/archive/reviews/wave-5-exit.md`, `wave-5c-exit.md`, `wave-6-exit.md`
- `.planning/archive/plans/2026-04-11-wave-5-scope.md`
- `.planning/plans/2026-04-14-wave-7-d2-comments-and-clone-advancement.md`
- `.planning/specs/2026-04-14-wave-7-d2-comments-and-clone-advancement-design.md`

## Bottom Line (Revised)

The April 15 argument was: "the codebase can get above 8/10, but not by
shipping more workflow features first — close the security and integrity
gaps, then merge #254." That sequencing is now complete:

1. PR #254 merged (wave-7-d2 comments + effective-state routing).
2. PR #255 closed the cross-cutting release blockers.
3. PRs #256 and #257 delivered auth hardening phase 2 (sessions table,
   CSRF, hashed refresh tokens, locked/inactive enforcement).
4. PR #258 closed the timeline visibility leak and the soft-delete race.
5. PR #259 made revision required on delete.
6. PR #261 fixed the publication-edit binding and duplicate-email 409.
7. All targeted test slices — including the ones the original review said
   were failing — now pass (203 tests, 0 failures).

The platform is at 8.0/10 against the revised gates below. One genuine
production hazard (`email.backend: "console"` can silently ship in
production) should block any production-like deploy until fixed.

## Current PR Status

**No open PRs on 2026-04-17.** The branch snapshot used for verification is
`workstream-b-publications-email-conflicts` at `195c7c1`, working tree clean.

PR #254 (`feat(wave-7-d2): effective-state routing + comments/edits/mentions`):
- merged 2026-04-15T07:08Z as `fec235f`
- scope delivered: effective-state routing on the clone cycle, comments
  (tables, ORM, service, 8 REST endpoints), comment edit history,
  mention join table, `DiscussionTab.vue`, Tiptap composer with mention
  autocomplete, frontend + backend tests, E2E comments flow
- polish commits after merge: Copilot PR #4 feedback, mention sanitisation
  (`target` omitted to prevent tabnabbing), dark-theme support, alembic
  import shape, CORS PATCH, mention-suggestion guards

PR #254 did *not* by itself move the platform above 8. The hardening PRs
that landed alongside it did.

## What The Old Plans Left Open — Status on 2026-04-17

### Previously deferred items (Wave 5 scope)

| Item | Status |
|---|---|
| Bundle D comments/review workflow | **Delivered** via PR #254 (Discussion only; full review workflow still partial) |
| Bundle E ORCID + preferences + attribution | **Not yet delivered** |
| Bundle F cookie-based refresh token | **Delivered** (in-memory access + HttpOnly refresh cookie, PRs #256/#257) |
| Sessions table / session inventory UI / forced logout | **Backend delivered** (`RefreshSession`, `session_version`, `_revoke_all_refresh_capability`); UI not delivered |
| Private contributor dashboard | **Not yet delivered** |
| Real SMTP infrastructure | **Partially delivered** — SMTP backend exists; production guard missing |

### What the 2026-04-15 version still said was open

| Finding | Status now | Notes |
|---|---|---|
| Frontend localStorage auth | **Fixed** | `frontend/src/api/session.js:8-62` |
| Token issuance — locked/inactive | **Fixed** | `backend/app/api/auth_endpoints.py:59-72` |
| Refresh-token lifecycle | **Fixed** | `backend/app/models/refresh_session.py:26-27`, SHA-256 hashes |
| Timeline visibility bypass | **Fixed** | `backend/app/phenopackets/routers/crud_timeline.py:155-189` |
| Non-atomic soft-delete | **Fixed** | `phenopacket_service.py:301-330` with `with_for_update()` |
| Phenopacket publication edit regression | **Fixed** | `PhenopacketCreateEdit.vue:282-286` |
| Duplicate-email admin update | **Fixed** | `user_repository.py:112-115, 138-148`, 409 test present |
| Production email console fallback | **Still open** | No `ENVIRONMENT=production` guard in `config.py` |
| Curation history / revision UI | **Partial** | Discussion tab shipped; dedicated audit-trail tab not yet |
| Durable docs pointing into `.planning/` | **Still open** | Five files still link the variant-annotation plan |
| `AGENTS.md` canonicalization | **Done in practice** | CLAUDE.md is a 7-line shim; no stale refs in live docs |
| Backend test slice green | **Green** | 203 passed, 0 failed, ~55 s |

## What Still Blocks A Clean >8 (Revised)

### A. One production-configuration hazard

`backend/app/core/config.py:413-440` validates SMTP only when the backend is
already set to `smtp`. There is no guard that refuses `console` in
production. A misconfigured deploy will silently log reset tokens to stdout.

Fix (add next to `_refuse_dev_auth_in_prod`):

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

### B. Curation history UI

Discussion is delivered, but curators cannot see an authoritative "who did
what when" surface. The data exists in backend audit/revision tables. The
missing piece is `HistoryTab.vue` — reading that data, showing actor
identity, transition reason, and diff summary.

### C. Doc hygiene

Five durable docs still link
`.planning/plans/variant-annotation-implementation-plan.md` as "Developer
Guide" (`docs/api/README.md:116`, `docs/api/variant-annotation.md:899`,
`docs/user-guide/README.md:137`, `docs/user-guide/variant-annotation.md:863`,
`backend/README.md:110`). Either promote to stable `docs/architecture/` or
remove the links.

### D. ADR 0001 now mismatches reality

`docs/adr/0001-jwt-storage.md` still recommends `localStorage`; live code uses
in-memory + HttpOnly cookie. Write ADR 0002 and mark 0001 Superseded. The code
is fine; the paper trail is not.

### E. Operational readiness (medium-term)

- no OpenTelemetry / Sentry wiring yet
- no WebAuthn / TOTP second factor for admin
- no session inventory UI (backend data is there)
- no ORCID / attribution / dashboard

None of these should block a controlled rollout, but they are the real
remaining distance to a durable 9.

## What Is *Good* About PR #254 In Hindsight

- It shipped **with** the hardening, not before it — the original review's
  concern about sequencing did not materialize.
- The comments/mentions layer uses the right mitigations: DOMPurify with
  explicit `ALLOWED_ATTR`, `target` omitted to prevent tabnabbing, safe
  markdown render path, server-side mention validation.
- The E2E comments flow (`test(e2e): comments flow — post, edit, delete
  across curator/admin`) is an unusually thorough landing test for a
  discussion feature of this scope.
- Effective-state routing touched a historically-tangled area and came out
  cleaner (`transitions router drops manual dict augmentation`;
  `_simple_transition uses effective state + I8 gate`).

## Curator Experience And Performance Recommendations

This review was asked to consider the tool's real users — doctors donating
time to curate patient data for sick children — and the users of the output.
The technical work below is the highest-leverage investment for those two
groups.

### Make curation fast

1. **Latency budget (wire into Playwright timings and a dashboard):**
   - mention / autocomplete search: p95 ≤ 200 ms
   - autosave round-trip: p95 ≤ 500 ms
   - detail page TTI: p95 ≤ 1.5 s on a mid-tier tablet
   - save / publish / resolve: p95 ≤ 1 s
   Anchor: Nielsen thresholds (100 ms instant / 1 s flow preserved).
2. **Virtualization** (`VDataTableVirtual`, `v-virtual-scroll`) for
   `CommentList` and any list that can exceed ~200 rows.
   https://vuetifyjs.com/en/components/data-tables/virtual-tables/
3. **`shallowRef`** for large phenopacket JSON payloads and long discussion
   threads. https://vuejs.org/api/reactivity-advanced.html
4. **Autosave + optimistic UI** on the edit form — the current save flow
   is explicit; draft saves on blur/debounce would cut perceived latency.
5. **Eager-load** `Phenopacket.editing_revision` already landed — keep an
   eye on N+1 patterns in `crud_timeline.py` and comments list (the latter
   was already bulk-loaded in a Copilot follow-up).

### Make curation reliable and humane

6. **HistoryTab.vue** — curators will not trust a tool they cannot audit.
   Backend data exists; build the view.
7. **Keyboard shortcuts** for save-and-next, submit, publish, resolve,
   mention, search. High-throughput curators feel these immediately.
8. **Observability** — OpenTelemetry FastAPI auto-instrumentation + Sentry
   on both backend and frontend. Ship before the user base widens; bug
   reports without traces are expensive to resolve.
   https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html
   https://docs.sentry.io/platforms/javascript/guides/vue/

### Make it usable on every device

9. **WCAG 2.2 AA audit** — new criteria relevant on tablets: 2.4.11 Focus
   Not Obscured, 2.5.7 Dragging, 2.5.8 Target Size (≥24×24 CSS px), 3.2.6
   Consistent Help, 3.3.7 Redundant Entry, 3.3.8 Accessible Authentication.
   https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
10. **ARIA APG patterns** — verify `MentionSuggestionList` is a proper
    combobox (arrow keys, `aria-activedescendant`, Esc dismisses); verify
    Discussion / Overview / Timeline tabs meet the tab pattern; add live
    regions around save, resolve, and publish feedback.
    https://www.w3.org/WAI/ARIA/apg/patterns/
11. **Dark-theme contrast** — PR #254 shipped dark mode polish, but the
    WCAG 2.2 3:1 non-text-contrast rule applies to focus rings and chip
    borders; worth a dedicated sweep with a contrast checker.
    https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html
12. **Touch targets** — the TransitionMenu and chips are small on phone.
    Set a baseline `min-block-size: 44px; min-inline-size: 44px` on
    primary curator actions.

### Make the output trustworthy

13. **Phenopackets v2 schema conformance** remains the reference; no v3 is
    in flight. Keep `docs/api/variant-annotation.md` and the export path
    aligned with GA4GH. https://www.ga4gh.org/product/phenopackets/
14. **Provenance test** — one integration test walks save → submit →
    approve → publish → edit → comment → resolve with three distinct
    actors and asserts every `changed_by` and transition reason.

## Revised Path To >8 → 9

Since 8 is now plausibly achieved, the next question is what takes this
to 9. Ordered by cost/benefit:

1. Land the three immediate items (email validator, ADR 0002, durable-doc links).
2. Ship HistoryTab.vue.
3. Wire OpenTelemetry + Sentry; set up the curator-latency dashboard.
4. WCAG 2.2 AA audit pass across edit, transition, discussion, mobile.
5. WebAuthn or TOTP for admin accounts.
6. Session inventory UI (frontend consumer of the existing sessions data).
7. ORCID + attribution preferences (Bundle E).
8. Private contributor dashboard (Bundle E.2).
9. Virtual scroll + `shallowRef` conversions where measured gains exist.
10. Keyboard-shortcut documentation and implementation.

## How To Measure That >8 Really Held

Use gates, not narrative.

### Security gate (all green on 2026-04-17)
- ✅ no access or refresh token in `localStorage`
- ✅ locked/inactive users cannot mint new tokens
- ✅ password reset/change invalidates old refresh capability
- ✅ timeline endpoint obeys the visibility model
- ⏳ production cannot silently fall back to console email

### Integrity gate (green)
- ✅ concurrent delete/update test (`test_phenopackets_delete_revision`)
- ⏳ dedicated mixed-actor provenance test
- ✅ comments + revisions internally consistent after publish/withdraw/resubmit

### Verification gate (green)
- ✅ targeted backend auth slice green
- ✅ targeted backend workflow slice green
- ✅ backend comments slice green
- ✅ frontend auth/admin/edit regression slice green

### Product-platform gate
- ⏳ audit/revision UI (HistoryTab.vue)
- ⏳ session inventory UI
- ⏳ ORCID/preferences — explicitly deferred, not blocking

### Curator-experience gate (new)
- ⏳ p95 latency SLOs wired up
- ⏳ WCAG 2.2 AA audit passed
- ⏳ keyboard shortcuts documented and implemented
- ⏳ virtualization on lists that can exceed ~200 rows

## Sources

- OWASP API Security Top 10 2023: https://owasp.org/API-Security/editions/2023/en/0x00-header/
- OWASP Authentication Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- OWASP JWT Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- FastAPI OAuth2/JWT tutorial: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- SQLAlchemy 2.0 versioning: https://docs.sqlalchemy.org/en/20/orm/versioning.html
- SQLAlchemy 2.0 asyncio: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Vue 3.5 release notes: https://blog.vuejs.org/posts/vue-3-5
- Vue reactivity advanced: https://vuejs.org/api/reactivity-advanced.html
- Vuetify virtual tables: https://vuetifyjs.com/en/components/data-tables/virtual-tables/
- WCAG 2.2 What's New: https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- ARIA APG: https://www.w3.org/WAI/ARIA/apg/patterns/
- GA4GH Phenopackets: https://www.ga4gh.org/product/phenopackets/
- ClinGen VCI (Genome Medicine 2022): https://pmc.ncbi.nlm.nih.gov/articles/PMC8764818/
- OpenTelemetry FastAPI: https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html
- Sentry FastAPI: https://docs.sentry.io/platforms/python/integrations/fastapi/
- Sentry Vue: https://docs.sentry.io/platforms/javascript/guides/vue/
- Playwright best practices: https://playwright.dev/docs/best-practices
