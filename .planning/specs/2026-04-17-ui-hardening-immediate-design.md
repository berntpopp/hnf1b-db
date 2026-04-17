# UI Hardening Immediate Batch Design

Date: 2026-04-17
Status: Draft for review
Branch: `ui-hardening-immediate` (off `main` @ `1bde64b`)

## Goal

Ship the Critical and High findings — plus the `M12` log hygiene fix called
out in the same "Immediate" column — from
`.planning/reviews/2026-04-17-ui-ux-design-review.md` as a single
Playwright-verified PR. Move the review's overall UI/UX score from **7.0
toward 8.0** by closing the gates the review itself defined:

- Every public page renders a real `h1`.
- Every `target="_blank"` carries `rel="noopener noreferrer"`.
- `/aggregations` either renders content or a real empty/error state.
- `/phenopackets/new` resolves sensibly.
- Tiptap composer passes axe-core "region has accessible name".
- Dark-theme detail header passes WCAG 1.4.3 (4.5:1).
- Keyboard-only curator can complete "view list → open record".

## Scope

### In Scope (Critical + High + Immediate M12)

- **C1** `/aggregations` blank page
- **C2** `/phenopackets/new` dual-state error
- **H1** External links missing `rel="noopener noreferrer"`
- **H2** Missing document-level headings on list + create pages
- **H3** Clickable rows mouse-only
- **H4** `/aggregations` empty-state (resolved by C1)
- **H5** Tiptap composer has no accessible name
- **H6** Dark-theme contrast fail on detail header
- **M10** Hardcoded `localhost:8000` in API docs footer link
- **M12** Anonymous token-refresh logged at ERROR
- **L6** Skip-link at top of every page

### Out Of Scope

- Near-term recommendations (dynamic Required badges, mobile pager
  redesign, fieldset grouping) — tracked as a follow-up batch.
- Medium-term recommendations (keyboard shortcut layer, autosave,
  virtualization, OpenTelemetry wiring).
- Design-system hygiene items (vocabulary unification, auth verb pick,
  ADR updates) — tracked separately.
- Backend changes. If the root cause of C1 is backend-side (anon 401 on
  an endpoint that should be public), the frontend scope becomes
  "route-guard + loud error card"; the backend gap is documented as a
  follow-up.

## Delivery Shape

- Single branch `ui-hardening-immediate` off fresh `main`.
- Single PR into `main`.
- Commits grouped by finding so each is independently revertable.
- All changes frontend-only.

## Section 1 — Router Fixes (C2)

**File:** `frontend/src/router/index.js`

Add redirect entry **before** the `/phenopackets/:phenopacket_id` route:

```js
{ path: '/phenopackets/new', redirect: '/phenopackets/create' },
```

**File:** `frontend/src/views/PagePhenopacket.vue`

The current template shows both the error alert and the loading spinner
simultaneously when the API rejects the `new` ID. Guard the loading
state with `v-if="loading && !error"` so the two states are mutually
exclusive; error always wins when both are present.

## Section 2 — ExternalLink Component + Link Sweep (H1)

**New file:** `frontend/src/components/common/ExternalLink.vue`

Props: `href` (required, string), `ariaLabel` (optional, string),
`showIcon` (optional, boolean, default `true`).

Template emits an `<a>` with `target="_blank"` + `rel="noopener
noreferrer"`, plus an `mdi-open-in-new` icon and a
visually-hidden "(opens in new tab)" suffix. Styling matches the
existing teal link color used across `FooterBar`.

**Sweep targets:**

| File | Lines | Strategy |
|---|---|---|
| `views/Publications.vue` | 98, 115 | `v-btn` — add `rel="noopener noreferrer"` attribute |
| `views/PagePublication.vue` | 54, 116 | `<ExternalLink>` |
| `views/PageVariant.vue` | 213, 238, 263, 291, 304, 317, 330, 343, 358, 371 | `<ExternalLink>` |
| `views/About.vue` | 166 | `<ExternalLink>` |
| `views/About.vue` | 191 | upgrade partial `rel="noopener"` → `noopener noreferrer` |
| `views/FAQ.vue` | 196, 260 | `<ExternalLink>` |
| `components/FooterBar.vue` | 70 | already correct — no change |

**Unit test:** `frontend/tests/unit/components/common/ExternalLink.spec.js`
asserts `rel` value, icon render behavior, and `ariaLabel`
propagation.

## Section 3 — List/Create Page Headings + Keyboard Row Activation (H2, H3)

**File:** `frontend/src/components/common/AppDataTable.vue`

Add a prop `titleTag` (default `'h1'`). Replace the title `<div>` with
`<component :is="titleTag">` preserving the existing classes.

**Per-page adjustments:**

- `views/Phenopackets.vue` — `AppDataTable` default `titleTag="h1"`.
- `views/Publications.vue` — same.
- `views/Variants.vue` — same.
- `views/PhenopacketCreateEdit.vue:5` — change
  `<v-card-title class="text-h4">` to `<h1 class="v-card-title text-h4">`
  so the visual styling is preserved.

**Keyboard row activation (H3):**

Convert the primary identity chip in each list to a `<v-chip :to>`
internal-link anchor. Vuetify renders `v-chip` with `to` as an `<a>`
via `router-link`, giving the chip native keyboard focusability +
Enter activation.

- `Phenopackets.vue:118` — subject-ID chip lacks `:to`. Add
  `:to="{ name: 'PagePhenopacket', params: { phenopacket_id:
  item.phenopacket_id } }"`.
- `Variants.vue:102` — primary chip lacks `:to`. Add
  `:to="/variants/${encodeURIComponent(item.variant_id)}"` (matching
  the existing `handleRowClick` target on line 533).
- `Publications.vue:70-82` — PMID chip already has `:to`, no change.

The row `@click:row` handler stays in place as progressive enhancement
for mouse users. Keyboard users reach the chip anchor; mouse users
keep the full-row click. No row-level `tabindex`/`role` fallback is
added — redundant given native `<a>` semantics on the chip.

**Unit test:** `frontend/tests/unit/components/common/AppDataTable.spec.js`
asserts `titleTag` renders the requested heading element.

## Section 4 — Tiptap Composer A11y (H5)

**File:** `frontend/src/components/comments/CommentComposer.vue`

1. Attach `aria-label="Comment body"` to the `EditorContent` component
   (propagates to the underlying `contenteditable` div).
2. Give the existing character counter `id="composer-char-count"` and
   add `aria-describedby="composer-char-count"` to the editor.
3. Add a minimal formatting toolbar above the editor: Bold, Italic,
   Link, Mention. Each is a `v-btn` icon button with explicit
   `aria-label` and keyboard-accessible tooltip. The Mention button
   inserts an `@` character to surface the `@mention` convention.

Styling and markup stay inside `.comment-composer` — no parent
component touches.

## Section 5 — `/aggregations` Blank Page (C1, H4)

Root cause is **not verified** from static exploration. The executing
phase begins with a reproduction step:

1. Start `make backend` + `make frontend`.
2. Playwright visit `/aggregations` anonymously.
3. Capture console errors and network responses.
4. Identify the failing call site.

Likely remediations, applied as needed:

- Wrap each tab's async fetch in try/catch that sets a per-tab error
  state; render a loading skeleton → empty/error card inside each
  `<v-tabs-window-item>` so a failed fetch leaves visible chrome.
- Add a top-of-page `<h1>Aggregations</h1>` (covers H2 on this view
  too), rendered above the tabs so it is visible regardless of tab
  content state.
- If the cause is an unhandled promise rejection in a chart
  component, patch the chart component to render a placeholder when
  `chartData` is empty or malformed.

If the cause turns out to require a backend fix (e.g., an anon 401
from an endpoint that must stay public for the dashboard to render),
the frontend PR's scope for this finding shrinks to:

- Always render the `h1` + tab chrome.
- Render an explicit "Authentication required" or "Data unavailable"
  error card per tab.
- Add a route-guard step only if the backend cannot be trusted to
  return 401 consistently.

The backend-side fix is captured as a follow-up finding rather than
expanding this PR.

## Section 6 — Dark-Theme Contrast on Detail Header (H6)

**File:** `frontend/src/views/PagePhenopacket.vue` (CSS block at line
781+)

Replace the static gradient with CSS custom properties that flip on
Vuetify's `v-theme--dark` class:

```css
.hero-section {
  background: linear-gradient(
    135deg,
    var(--hero-start) 0%,
    var(--hero-mid) 50%,
    var(--hero-end) 100%
  );
  border-bottom: 1px solid var(--hero-border);
}

:deep(.v-theme--light) .hero-section {
  --hero-start: #e0f2f1;
  --hero-mid: #b2dfdb;
  --hero-end: #f5f7fa;
  --hero-border: rgba(0, 0, 0, 0.05);
}

:deep(.v-theme--dark) .hero-section {
  --hero-start: #102a2b;
  --hero-mid: #1e3a3a;
  --hero-end: #0d1b1c;
  --hero-border: rgba(255, 255, 255, 0.08);
}
```

Also audit foreground elements — `h1` "Individual Details", tab
labels (OVERVIEW / TIMELINE / RAW JSON), "STATE ACTIONS" button —
and set theme-sensitive text colors (e.g.,
`text-teal-lighten-3` under `v-theme--dark`) so each hits ≥ 4.5:1
against the dark gradient.

No change to `plugins/vuetify.js` — fix scoped to this view.

## Section 7 — Logging, Env Fallback, Skip-Link (M12, M10, L6)

### M12 — Demote Anonymous Token Refresh Log

**File:** `frontend/src/stores/authStore.js:135-141`

Split the catch block by whether the user was authenticated before the
refresh attempt:

```js
} catch (err) {
  const wasAuthenticated = !!this.user;
  if (wasAuthenticated) {
    window.logService.error('Token refresh failed', { error: err.message });
  } else {
    window.logService.debug('Anonymous session refresh rejected (expected)', {
      error: err.message,
    });
  }
  await logout(true);
  throw err;
}
```

Apply the same pattern to the `"Failed to initialize user session"`
log site (exact location located during execution).

**File:** `frontend/src/api/transport.js:184` — already at `warn`; keep
unless the unit test demands a split.

### M10 — Hide API Docs Link When VITE_API_URL Unset In Prod

**File:** `frontend/src/components/FooterBar.vue:176-178`

Change the computed `apiDocsUrl` so it returns `null` when
`import.meta.env.PROD === true` and `import.meta.env.VITE_API_URL` is
unset. Template guards the link with `v-if="apiDocsUrl"`.

A `logService.warn` on component mount when `apiDocsUrl` is null and we
are in prod, so operators see the misconfiguration in logs.

### L6 — Skip-Link

**File:** `frontend/src/App.vue`

Add at the top of the `<v-app>` template, before `<AppBar>`:

```vue
<a href="#main-content" class="skip-link">Skip to main content</a>
```

Add `id="main-content"` to `<v-main>`. Style `.skip-link` as
visually-hidden (clip-path / absolute positioning), revealed on
`:focus`. Existing pattern: no dependency changes.

## Testing

### Playwright (`frontend/tests/e2e/`)

- `ui-hardening-critical.spec.js`
  - `/aggregations` anon: visible `h1`; either tab content or real
    error alert; no pure-white viewport.
  - `/phenopackets/new`: redirect to `/phenopackets/create`, `h1`
    present.
  - `/phenopackets/genuinely-missing-id`: single error state, no
    concurrent loading indicator.

- `ui-hardening-a11y.spec.js`
  - `a[target="_blank"]` audit: every external anchor on `/publications`,
    `/publications/:id`, `/variants/:id`, `/about`, `/faq` carries
    `rel` containing `noopener` and `noreferrer`.
  - Exactly one `h1` on `/phenopackets`, `/publications`, `/variants`,
    `/phenopackets/create`, `/aggregations`.
  - Keyboard flow: Tab to first subject chip on `/phenopackets`,
    press Enter, lands on detail page.
  - Comment composer exposes `aria-label="Comment body"`.
  - First tabbable element on `/` is the skip-link; Enter lands on
    `#main-content`.

- `ui-hardening-dark-theme.spec.js`
  - Toggle dark theme on detail page; assert `.hero-section`
    background resolves to the dark gradient; assert `h1` and tab
    label contrast ratio ≥ 4.5:1 via DOM probe.

### Unit (`frontend/tests/unit/`)

- `components/common/ExternalLink.spec.js`
- `components/common/AppDataTable.spec.js` (extend existing)
- `stores/authStore.spec.js` (extend existing) — anonymous refresh
  failure logs at `debug`.

### Local Verification Before Commit

- `make frontend-test`
- `make frontend-e2e`
- `make frontend-lint`
- `make backend-test` (smoke, to confirm no contract regression)
- Manual: dev server, visit dark-mode detail page at 1440×900 and
  390×844.

### CI Gate

Every commit in the PR must land with CI green. CI failure halts
execution, triggers a debug cycle, and is fixed before the next
commit.

## Commit Plan

One PR, twelve commits:

1. `docs(planning): update reviews and add 2026-04-17 UI/UX review`
2. `feat(frontend): add ExternalLink component + apply to external links (H1)`
3. `fix(frontend): route /phenopackets/new to /create and dedupe loading state (C2)`
4. `fix(frontend): render list and create page titles as h1 (H2)`
5. `feat(frontend): keyboard-activate table rows via chip anchors (H3)`
6. `fix(frontend): add accessible name + toolbar to Tiptap composer (H5)`
7. `fix(frontend): respect dark theme on phenopacket hero header (H6)`
8. `fix(frontend): reproduce and repair /aggregations blank page (C1)`
9. `chore(frontend): demote anonymous token-refresh log to debug (M12)`
10. `fix(frontend): hide API docs link when VITE_API_URL unset in prod (M10)`
11. `feat(frontend): add skip-to-main-content link (L6)`
12. `test(frontend): add ui-hardening Playwright + Vitest coverage`

## Exit Criteria

- All Critical + High findings from
  `.planning/reviews/2026-04-17-ui-ux-design-review.md` have either
  shipped fixes or documented backend-dependent follow-ups.
- M10, M12, L6 shipped.
- New Playwright + Vitest tests pass locally and in CI.
- Manual dark-theme verification at desktop + mobile viewports.
- PR open, CI green, ready for review.

## Follow-Ups Not In This PR

- Near-term recommendations: fieldset/legend grouping (M2), dynamic
  Required badges (M3), mobile pager (M7), Login welcome widening
  (M6), dark-theme sweep beyond the detail page, chart
  virtualization, autosave, inline validation preview.
- Keyboard shortcut layer + `?` help overlay (L5).
- HistoryTab surface (platform review cross-reference).
- Design-system hygiene batch (M4 naming, L4 vocabulary, ADR 0002
  + dark-theme ADR).
- Investigation: `/phenopackets` sex column shows "Unknown" for every
  row (L3 — data/ops, not UI).

## Sources

- `.planning/reviews/2026-04-17-ui-ux-design-review.md`
- WCAG 2.2 AA: https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- MDN `rel="noopener"`: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/rel#noopener
- ARIA APG Combobox / Tabs: https://www.w3.org/WAI/ARIA/apg/patterns/
- Vuetify Data Tables: https://vuetifyjs.com/en/components/data-tables/
