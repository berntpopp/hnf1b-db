# Mobile UX Overhaul — Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use `- [ ]` checkboxes.
> Spec: `.planning/specs/2026-06-13-mobile-ux-overhaul-design.md`.

**Goal:** Raise `/phenopackets`, `/publications`, `/variants`, `/aggregations`
mobile UX to ≥9/10 in all 8 design dimensions, verified by Playwright +
Lighthouse, without regressing desktop.

**Architecture:** Fix shared components first (Sprint A: AppPagination,
AppDataTable mobile cards, AppBar, FooterBar, typography floor, CLS), then
adapt each page's column set + card content in parallel (Sprints B/C/D/E).
Charts get a ResizeObserver-driven responsive width composable.

**Tech Stack:** Vue 3.5 `<script setup>`, Vuetify 4.0.8 (`mobile`/
`mobileBreakpoint` on `v-data-table-server`, `useDisplay`), D3 7, Vite 8,
Vitest, Playwright.

**Dev env:** dockerized API on :8000; local Vite dev on **:5174**
(`npm run dev -- --port 5174`). Verify on :5174, not the stale :3000 image.

**Verification harness (reused every sprint):** navigate Playwright to the
page at 360 / 390 / 414 px, run the DOM audit (page overflow, scrollers with
`scrollWidth>clientWidth`, sub-44px tap targets, fonts <12px), screenshot
review, and re-check `npm run lint:check`, `npm run test`, `npm run build`.

**Touch standard:** primary interactive controls ≥ 44 × 44 px; no text < 12px;
no horizontal page/section overflow at 360px; CLS < 0.1.

---

## Sprint A — Foundations (shared, do first, blocks B/C/D)

### Task A1: AppPagination responsive + 44px tap targets

**Files:** Modify `frontend/src/components/common/AppPagination.vue`;
Test `frontend/tests/unit/AppPagination.spec.js` (create if absent).

- [ ] Wrap root in `flex-wrap` so it can never overflow; add `useDisplay`.
- [ ] Below `sm` (`smAndDown`): render a compact layout — row 1: First/Prev
      icon-btns + a centered `Page {{currentPage}} of {{totalPages}}` label +
      Next/Last; hide the numbered page buttons + ellipses on mobile. Row 2:
      "Items per page" select + range text, `justify-space-between`.
- [ ] `sm`+: keep current layout unchanged.
- [ ] Touch sizing: page/icon buttons `min-width:44px; height:44px` when
      `smAndDown` (override the `28px`/`32px` styles via a `.is-mobile` class).
- [ ] Keep all emits (`update:pageSize`, `go-to-page`) and props identical.
- [ ] Unit test: renders "Page 2 of 5" text in mobile mode (stub `useDisplay`
      to mobile), emits `go-to-page` on Next, hides numbered buttons.
- [ ] Verify: re-audit any list page — `app-pagination` no longer in the
      overflow/scroller list; pagination buttons ≥44px.
- [ ] Commit: `feat(frontend): responsive AppPagination with 44px touch targets`

### Task A2: AppDataTable mobile card mode

**Files:** Modify `frontend/src/components/common/AppDataTable.vue`.

- [ ] Add `useDisplay` + prop `mobileBreakpoint` (default `'sm'`) and pass
      `:mobile="undefined"` so Vuetify uses its `mobileBreakpoint`; OR compute
      `:mobile="smAndDown"`. Apply to both `v-data-table-server` and
      `v-data-table`. Expose an escape-hatch prop `disableMobile` (default
      false) for tables that should stay grid.
- [ ] Add scoped CSS for `.v-data-table__tr--mobile`: each mobile row → a card
      (`border:1px solid rgba(0,0,0,.08); border-radius:12px; margin:8px;
      padding:4px 8px; box-shadow` subtle). `.v-data-table__td--mobile`:
      `display:flex; justify-content:space-between; gap:12px; min-height:44px;
      border:none`. `.v-data-table__td-title`: 11px uppercase medium-emphasis
      label. `.v-data-table__td-value`: 14px, text-align right, allow wrap.
- [ ] Hide the native header row in mobile mode (labels come from td-title).
- [ ] Reserve min row height to reduce CLS.
- [ ] Verify: phenopackets at 390px renders stacked cards reusing existing
      chip slots; no horizontal scroll.
- [ ] Commit: `feat(frontend): AppDataTable responsive mobile card layout`

### Task A3: AppBar logo no-overlap + 44px

**Files:** Modify `frontend/src/components/AppBar.vue` (+ inspect
`/public/HNF1B-db_logo.svg` intrinsic ratio).

- [ ] Diagnose the overlap with a cropped header screenshot at 360/390px.
- [ ] Constrain logo: set explicit `height` (cap to bar height − padding, ~36px
      xs / 40px sm) and `width:auto` with `max-width` so aspect ratio is from
      the SVG, never squished; ensure `.logo-container` doesn't clip.
- [ ] Logo container tap target ≥44px height.
- [ ] Verify: header at 360px shows the full wordmark, no overlap, no
      `v-toolbar-title` overflow in audit.
- [ ] Commit: `fix(frontend): app bar logo sizing/overlap on mobile`

### Task A4: FooterBar responsive (no clip)

**Files:** Modify `frontend/src/components/FooterBar.vue`.

- [ ] `useDisplay`; on `xs` show status as the coloured health icon + short
      word only (hide `| {{responseTime}}ms`), reduce icon button horizontal
      margins (`mx-1`→`mx-0` tight), and allow the row to fit 360px (if still
      tight, collapse About/FAQ/MCP/logs into a single `mdi-dots-vertical`
      overflow `v-menu` on xs).
- [ ] Ensure footer never overflows: audit `footer` no longer a scroller.
- [ ] Keep all links/aria intact.
- [ ] Verify: 360px — status text fully visible, no clipping.
- [ ] Commit: `fix(frontend): responsive footer, no clipping on mobile`

### Task A5: Typography floor + CLS budget

**Files:** Modify `frontend/src/styles/settings.scss` (or the global app
stylesheet); inspect chip/caption usages producing 10px.

- [ ] Add a mobile rule: clamp the smallest text — ensure `.text-caption`,
      table cells, and chips render ≥12px on `xs`. Find the 10px sources
      (variants had 34) and bump them.
- [ ] Add/verify skeleton loaders match row heights on the three list pages
      (reserve height) to cut CLS; ensure list container has a min-height
      during load.
- [ ] Verify: audit shows no fonts <12px on all four pages; re-measure CLS
      via Lighthouse on local preview after page sprints.
- [ ] Commit: `style(frontend): mobile typography floor (>=12px) + CLS reserves`

---

## Sprint B — Phenopackets (depends on A)

**Files:** Modify `frontend/src/views/Phenopackets.vue`.

- [ ] Add `useDisplay`; compute a **mobile headers** array (Subject ID, Sex,
      Phenotypes, Has Variant, State — drop nothing critical but order by
      importance; State only if present) vs the existing desktop headers.
- [ ] Make the search field full-width on mobile (placeholder not truncated).
- [ ] Render only the **bottom** AppPagination on mobile (hide the top one via
      `v-if="!smAndDown"`), keep both on desktop.
- [ ] Ensure phenotype count chip has a ≥44px tap target / clear label.
- [ ] Verify (Playwright 360/390/414): stacked cards, no overflow, no sub-44px
      primary targets, search usable.
- [ ] Commit: `feat(frontend): phenopackets mobile card layout`

## Sprint C — Publications (depends on A) — heaviest, worst CLS/perf

**Files:** Modify `frontend/src/views/Publications.vue`.

- [ ] Mobile headers: title-led card. Title becomes the card heading (full
      width, `-webkit-line-clamp:3`), then PMID chip, authors summary,
      individuals count, and an **actions row**: PubMed + DOI as labelled
      buttons ≥44px (move the `external_links` slot content out of a hidden
      column into the visible card actions).
- [ ] Single paginator on mobile (bottom).
- [ ] Reserve card heights + skeleton rows to drive CLS from 0.70 → <0.1.
- [ ] Verify (Playwright + Lighthouse local preview): no 8–12 line title wrap;
      tap targets ≥44px; CLS <0.1; perf improved.
- [ ] Commit: `feat(frontend): publications mobile title-led cards + CLS fix`

## Sprint D — Variants (depends on A) — fixes hidden-columns failure

**Files:** Modify `frontend/src/views/Variants.vue`.

- [ ] Mobile headers: variant-led card — Variant ID + protein (p.) / c. change
      as heading; then Type chip, Classification verdict chip, Individuals
      count. Suppress rows whose value is "–"/empty so cards stay tight.
- [ ] No horizontal scroll on mobile (cards, not the 882px grid).
- [ ] Verify (Playwright 360/390/414): decision columns (Type, Classification)
      visible without horizontal scroll; no sub-44px primary targets; no <12px.
- [ ] Commit: `feat(frontend): variants mobile card layout (decision columns visible)`

## Sprint E — Aggregations + charts (independent of A's table work)

**Files:** Create `frontend/src/composables/useResponsiveChartWidth.js`;
Modify `frontend/src/views/AggregationsDashboard.vue` and
`frontend/src/components/analyses/{DonutChart,StackedBarChart,
PublicationsTimelineChart,VariantComparisonChart,KaplanMeierChart,
BoxPlotChart}.vue`.

- [ ] Composable: `ResizeObserver` on a passed container ref → reactive
      `width` (debounced), with a `height` derived for mobile (e.g.
      `min(width*0.8, 360)`); mirror the existing `PhenotypeHeatmap.vue`
      pattern.
- [ ] In AggregationsDashboard, wrap each chart in a measured container and
      pass `:width`/`:height` from the composable; ensure the active tab's
      chart re-measures when shown.
- [ ] In each D3 chart, render the SVG with `width:100%` + `viewBox` (keep the
      internal coordinate system) and re-render on width change so axis labels
      stay legible. Charts must fit 360px (no clipping, donut label centered).
- [ ] Tab strip: add a scroll affordance (Vuetify `show-arrows` / fade) or
      allow wrap on mobile.
- [ ] Verify (Playwright 360/390/414): no `chart-wrapper`/`slide-group`
      overflow beyond viewport clipping; donut fully visible; "view as table"
      still works.
- [ ] Commit: `feat(frontend): responsive D3 charts + aggregations mobile layout`

---

## Integration & ship

- [ ] Full re-audit of all 4 pages at 360/390/414; re-score the 8 dimensions
      (target ≥9 each); save after-screenshots to evidence.
- [ ] Lighthouse mobile on local production preview (`npm run build` +
      `vite preview`) for all 4 pages; confirm CLS <0.1, A11y ≥95, perf not
      regressed.
- [ ] `cd frontend && npm run lint:check && npm run format:check &&
      npm run test && npm run build` — all green.
- [ ] Update memory; open one PR; ensure GitHub Actions CI gate green.

---

## Self-review notes

- Spec coverage: A1↔pagination, A2↔table, A3↔logo, A4↔footer, A5↔typography+CLS,
  B/C/D↔per-page tables, E↔charts+tabs. All §3 items mapped.
- No placeholders: each task names exact files + concrete Vuetify-4 mechanism.
- Consistency: `mobile`/`mobileBreakpoint`, `useDisplay().smAndDown`,
  `useResponsiveChartWidth` used consistently across tasks.
