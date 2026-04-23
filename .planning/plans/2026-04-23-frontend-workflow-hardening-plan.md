# Frontend Workflow Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the remaining frontend correctness and workflow-confidence gaps called out by the 2026-04-23 review without broad redesign.

**Architecture:** Keep the current router/store/API structure and server-driven tables. Focus on small, test-backed corrections: search handoff correctness, session-expiry return intent, actual Vuetify plugin mounting, and a first-class curator history surface built on existing backend APIs.

**Tech Stack:** Vue 3, Vuetify 4, Vue Router, Pinia, Axios, Vitest, Playwright.

---

## Task 1: Fix SearchCard -> Variants routing mismatch

**Files:**
- Modify: `frontend/src/components/SearchCard.vue`
- Modify: `frontend/tests/unit/components/SearchCard.spec.js`
- Modify: `frontend/tests/e2e/table-url-state.spec.js`

- [ ] Change variant selection routing so it lands on the variants experience with the parameter shape the table reads.

- [ ] Preferred behavior:
  - use `q`
  - keep Publications behavior aligned if needed after checking `Publications.vue`

- [ ] Add unit assertions that router navigation for `Variant` items uses the correct query key.

- [ ] Add or update one E2E assertion proving the variants page initializes from the routed search query.

- [ ] Run:

```bash
cd frontend && npm test -- tests/unit/components/SearchCard.spec.js tests/unit/composables/useTableUrlState.spec.js
```

- [ ] Run:

```bash
cd frontend && npx playwright test tests/e2e/table-url-state.spec.js
```

- [ ] Commit:

```bash
git add frontend/src/components/SearchCard.vue frontend/tests/unit/components/SearchCard.spec.js frontend/tests/e2e/table-url-state.spec.js
git commit -m "fix(frontend): preserve variant filters from global search"
```

## Task 2: Preserve return intent on session expiry

**Files:**
- Modify: `frontend/src/api/transport.js`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/stores/authStore.js` only if needed
- Create: `frontend/tests/unit/api/transport-session-expiry.spec.js`

- [ ] Replace hard redirect behavior on refresh failure with SPA-safe navigation that preserves the current location as a `redirect` query param.

- [ ] Do not break the existing anonymous bootstrap behavior.

- [ ] Add unit coverage for:
  - session refresh failure from an authenticated page
  - redirect preserves original path/query
  - anonymous refresh rejection does not create a bogus return path

- [ ] Run:

```bash
cd frontend && npm test -- tests/unit/api/transport.spec.js tests/unit/api/transport-session-expiry.spec.js tests/unit/stores/authStore.spec.js
```

- [ ] Commit:

```bash
git add frontend/src/api/transport.js frontend/src/router/index.js frontend/src/stores/authStore.js frontend/tests/unit/api/transport-session-expiry.spec.js frontend/tests/unit/api/transport.spec.js
git commit -m "fix(auth): preserve return intent on session expiry"
```

## Task 3: Mount the actual Vuetify plugin

**Files:**
- Modify: `frontend/src/main.js`
- Modify if needed: `frontend/src/plugins/vuetify.js`
- Modify: `frontend/tests/setup.js`
- Modify affected unit tests only if they assume a bare Vuetify instance

- [ ] Replace the bare `createVuetify()` instance in `main.js` with the configured export from `src/plugins/vuetify.js`.

- [ ] Keep current icons and theme behavior working in both unit tests and the production build.

- [ ] Update shared test setup if needed so component tests use the same Vuetify configuration.

- [ ] Run:

```bash
cd frontend && npm test -- tests/unit/views/AdminUsers.spec.js tests/unit/views/ForgotPassword.spec.js tests/unit/components/common/AppDataTable.spec.js
```

- [ ] Run:

```bash
cd frontend && npm run build
```

- [ ] Commit:

```bash
git add frontend/src/main.js frontend/src/plugins/vuetify.js frontend/tests/setup.js
git commit -m "fix(ui): mount shared vuetify configuration"
```

## Task 4: Add curator history/revisions tab on PagePhenopacket

**Files:**
- Modify: `frontend/src/views/PagePhenopacket.vue`
- Modify: `frontend/src/composables/usePhenopacketState.js`
- Modify if needed: `frontend/src/api/domain/phenopackets.js`
- Create: `frontend/src/components/phenopacket/HistoryTab.vue`
- Create if needed: `frontend/tests/unit/components/phenopacket/HistoryTab.spec.js`
- Create or Modify: `frontend/tests/unit/views/PagePhenopacket.spec.js`

- [ ] Add a new `History` tab visible to curator/admin users on phenopacket detail pages.

- [ ] Use existing backend endpoints:
  - `getPhenopacketAuditHistory`
  - `fetchRevisions`
  - `fetchRevisionDetail` only if the UI needs drill-down

- [ ] Minimum useful history surface:
  - revision number
  - state if present
  - actor
  - timestamp
  - reason / summary

- [ ] Keep the existing clinical `Timeline` tab unchanged.

- [ ] Add unit coverage for:
  - tab visibility gating
  - loading and error states
  - populated history rows

- [ ] Run:

```bash
cd frontend && npm test -- tests/unit/components/phenopacket/HistoryTab.spec.js tests/unit/views/PagePhenopacket.spec.js
```

- [ ] Commit:

```bash
git add frontend/src/views/PagePhenopacket.vue frontend/src/composables/usePhenopacketState.js frontend/src/api/domain/phenopackets.js frontend/src/components/phenopacket/HistoryTab.vue frontend/tests/unit/components/phenopacket/HistoryTab.spec.js frontend/tests/unit/views/PagePhenopacket.spec.js
git commit -m "feat(phenopackets): add curator history tab"
```

## Task 5: Improve accessibility test breadth

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/tests/e2e/ui-hardening-a11y.spec.js`
- Create if chosen: `frontend/tests/e2e/accessibility.spec.js`

- [ ] Add one broader automated accessibility scan path.

- [ ] Preferred implementation:
  - add `@axe-core/playwright`
  - scan the homepage and one authenticated phenopacket page state

- [ ] Keep the existing custom assertions for skip-link and anchor hardening.

- [ ] Run:

```bash
cd frontend && npm install
cd frontend && npx playwright test tests/e2e/ui-hardening-a11y.spec.js tests/e2e/accessibility.spec.js
```

- [ ] Commit:

```bash
git add frontend/package.json frontend/package-lock.json frontend/tests/e2e/ui-hardening-a11y.spec.js frontend/tests/e2e/accessibility.spec.js
git commit -m "test(a11y): add automated accessibility scans"
```

## Task 6: Lane verification

**Files:**
- No code changes required unless fixes are needed

- [ ] Run the frontend lane verification bundle:

```bash
cd frontend && npm test -- \
  tests/unit/components/SearchCard.spec.js \
  tests/unit/api/transport.spec.js \
  tests/unit/api/transport-session-expiry.spec.js \
  tests/unit/views/AdminUsers.spec.js \
  tests/unit/views/ForgotPassword.spec.js \
  tests/unit/views/PagePhenopacket.spec.js \
  tests/unit/components/phenopacket/HistoryTab.spec.js
```

- [ ] Run:

```bash
cd frontend && npm run build
```

- [ ] Run:

```bash
cd frontend && npx playwright test \
  tests/e2e/ui-hardening-a11y.spec.js \
  tests/e2e/table-url-state.spec.js \
  tests/e2e/comments.spec.js
```

- [ ] Commit any final lane-only follow-up:

```bash
git add frontend
git commit -m "test(frontend): finalize workflow hardening verification"
```

