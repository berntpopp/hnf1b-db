# Chart Export + Accessibility — Design

**Date:** 2026-05-11
**Closes:** [#136](https://github.com/berntpopp/hnf1b-db/issues/136) (chart export), [#135](https://github.com/berntpopp/hnf1b-db/issues/135) (chart a11y)
**Milestone:** Final polish (#6)
**Reviewer:** Claude Code (Opus 4.7)

## Goal

Bundle chart data export (PNG, CSV, SVG) and screen-reader accessibility into one focused PR across all seven `components/analyses/` chart components. Both features touch the same files, so doing them together avoids re-opening the same components for serial PRs.

## Why these two together

- Chart export is the single highest-leverage user-visible feature for a biomedical reference database — researchers want to drop charts into papers, slides, and supplementary data.
- ARIA-described charts piggyback on the export work at marginal cost: both add wrapper structure and metadata to the same SVG-bearing components.
- The codebase already has a partial foundation: `useAccessibility.js` provides `usePrefersReducedMotion` and `useAnnouncer`; `DonutChart.vue` already declares an unused `exportable` prop.

## Scope

### Files modified (7 chart components)

- `frontend/src/components/analyses/DonutChart.vue`
- `frontend/src/components/analyses/StackedBarChart.vue`
- `frontend/src/components/analyses/BoxPlotChart.vue`
- `frontend/src/components/analyses/PublicationsTimelineChart.vue`
- `frontend/src/components/analyses/KaplanMeierChart.vue`
- `frontend/src/components/analyses/VariantComparisonChart.vue`
- `frontend/src/components/analyses/DNADistanceAnalysis.vue`

The issue lists name 5 (#135) or 5 (#136), with overlap; covering all 7 avoids leaving BoxPlot and Timeline orphaned with inconsistent affordances.

### Files added

- `frontend/src/utils/chartExport.js` — SVG→PNG, data→CSV, raw SVG, filename helper
- `frontend/src/utils/__tests__/chartExport.spec.js`
- `frontend/src/components/analyses/ChartExportMenu.vue` — Vuetify `v-menu` with PNG / CSV / SVG actions
- `frontend/src/components/analyses/__tests__/ChartExportMenu.spec.js`
- `frontend/src/composables/useChartAccessibility.js` — generates stable IDs + ARIA prop bundle
- `frontend/src/composables/__tests__/useChartAccessibility.spec.js`
- `frontend/src/style.css` — add a global `.sr-only` helper class (currently scoped-local in `components/common/ExternalLink.vue` only)

### Out of scope (deferred)

- **Pattern fills for colorblind support.** WCAG 1.4.1 is satisfied by the data-table fallback (see Architecture). Per-chart `<defs><pattern>` work is substantial and tunes differently for each color scale — worth a clean follow-up issue.
- **Rewriting Options-API charts to `<script setup>`.** Existing component shapes stay; minimum churn.
- **Chart animations** (#139), **service worker** (#138) — separate issues.
- **Cross-browser export quality testing.** Chromium-only for v1; documented in PR body.

## Context

### Current state of charts

All 7 chart components use the Options API and let D3 manage the SVG subtree inside a `<div ref="chart">`. The D3-rendered subtree contains:
- An `<svg>` with `viewBox` and `preserveAspectRatio` already set
- Inline styles via D3 `.style()` calls
- A D3-managed tooltip div (sibling to the SVG, not screen-reader accessible)
- A separate legend div on most charts

`DonutChart.vue` declares `exportable: Boolean` in props but never renders an export button — the export feature was scaffolded but never wired up.

### Existing a11y infrastructure

`frontend/src/composables/useAccessibility.js`:
- `usePrefersReducedMotion()` — reactive media query
- `usePrefersDarkMode()` — reactive media query
- `useIsMobile(breakpoint)` — reactive viewport check
- `useAccessibleScroll()` — reduced-motion-aware `scrollIntoView`
- `useAnnouncer()` — creates global `#a11y-announcer` ARIA live region with `announce(msg, priority)`

The existing automated a11y scan (commit `630dfde`) gates PRs via axe-core.

### WCAG 2.1 targets

- **1.1.1 Non-text Content (Level A):** charts get title + description + data-table fallback
- **1.4.1 Use of Color (Level A):** data-table fallback removes color dependency
- **2.1.1 Keyboard (Level A):** export menu uses Vuetify button (already keyboard-accessible)

## Architecture

### chartExport.js — three pure functions

```js
exportSvgAsPng(svgEl, { filename, scale = 2, background = '#fff' })
exportDataAsCsv(rows, columns, filename)
exportSvgAsSvg(svgEl, filename)
```

**SVG→PNG flow** (native, zero new deps):

1. `svgEl.cloneNode(true)` — never mutate the live DOM.
2. Walk the clone; inline computed styles per node (D3 uses both inline `.style()` and CSS class rules; cloning preserves only inline).
3. Set explicit `width`/`height` attributes from the bounding box.
4. `XMLSerializer().serializeToString(clone)` → `data:image/svg+xml;charset=utf-8,...` data URL.
5. Load into `new Image()`; on `onload`, create a canvas sized `bbox.width * scale × bbox.height * scale`, fill `background` (PNG transparency is rarely what users want for figures), `ctx.drawImage(img, 0, 0, ...)`.
6. `canvas.toBlob('image/png')` → trigger download via temporary `<a download>`.

**CSV flow:**

1. Prefix output with BOM (`﻿`) so Excel detects UTF-8.
2. Header row from `columns[i].label`.
3. RFC 4180 escaping: if a field contains `,`, `"`, `\n`, or `\r`, wrap in `"..."` and double any internal `"`.
4. Join with `\r\n` (RFC 4180 line ending).
5. Same `<a download>` trigger; MIME `text/csv;charset=utf-8`.

**Filename helper:**

```
hnf1b-db_{kebab-chart-name}_{YYYY-MM-DD}.{ext}
```

### ChartExportMenu.vue — Vuetify menu

```vue
<ChartExportMenu
  :svg-el="svgRef"          <!-- Element or () => Element -->
  :rows="exportRows"        <!-- Array<Object>, already shaped for CSV -->
  :columns="exportColumns"  <!-- [{ key, label }] -->
  chart-name="sex-distribution"
/>
```

- Self-contained; emits no events.
- `v-btn` with `mdi-download` icon → opens `v-menu` with `v-list-item` × 3 (PNG, CSV, SVG).
- Disabled when `svgEl` is null (chart still rendering).
- On click, invokes the matching `chartExport.js` function and calls `useAnnouncer().announce('Chart exported as PNG')` for screen-reader confirmation.
- Top-right corner of every chart, absolutely positioned so it doesn't affect chart layout.

### useChartAccessibility.js — one helper, one shape

```js
const { titleId, descId, description, ariaProps } = useChartAccessibility({
  chartName: 'Sex distribution',
  summary: computed(() => generateSummary(props.chartData)),
})
```

- `titleId` / `descId`: stable unique IDs using a module-level counter (so multiple charts mounted on the same page don't collide).
- `ariaProps` returns `{ role: 'img', 'aria-labelledby': titleId, 'aria-describedby': descId }` — each chart spreads onto its outermost rendered element via `v-bind="ariaProps"`.
- `description` is the reactive `summary` re-exposed for the template binding (kept on the composable so the consumer only imports one symbol).

### Per-chart template pattern

```vue
<template>
  <div class="chart-container" v-bind="ariaProps">
    <span :id="titleId" class="sr-only">{{ chartName }}</span>
    <span :id="descId" class="sr-only">{{ description }}</span>
    <ChartExportMenu
      :svg-el="svgEl"
      :rows="exportRows"
      :columns="exportColumns"
      :chart-name="chartName"
    />
    <div ref="chart" class="chart" aria-hidden="true" />
    <details class="chart-data-table">
      <summary>View data as table</summary>
      <table>
        <thead><tr><th v-for="c in exportColumns" :key="c.key">{{ c.label }}</th></tr></thead>
        <tbody><tr v-for="r in exportRows" :key="rowKey(r)"><td v-for="c in exportColumns" :key="c.key">{{ r[c.key] }}</td></tr></tbody>
      </table>
    </details>
  </div>
</template>
```

- The D3-managed `<div ref="chart">` gets `aria-hidden="true"` — its DOM is noise (paths, mouseover handlers). The ARIA description carries the semantic signal.
- `<details>` is the WCAG-recommended fallback for complex charts and doubles as a "view raw data" affordance for sighted users — no separate "show data" button needed.
- `sr-only` class is the standard visually-hidden pattern (`position: absolute; width: 1px; height: 1px; ...`) — already implicit in `useAnnouncer`'s inline styles and currently scoped-local to `ExternalLink.vue`; this PR promotes it into `style.css` so the charts (and any future consumer) can use it without duplication.

### Per-chart description generators

Each chart's `<script>` builds a 1-paragraph summary string from its own data shape (too chart-specific to share):

- **Donut:** `"Sex distribution: 45% male (389), 48% female (416), 7% unknown (59). Total 864."`
- **Stacked bar:** `"Phenotypic features across 864 phenopackets. Renal cysts: 612 present, 198 absent, 54 unknown. ... and 12 more features, available in data table below."`
- **Kaplan–Meier:** `"Survival curve. Median survival 42 months, 95% CI 38–48. n=864 with 312 events."`
- **Box plot:** `"DNA distance distribution by domain. Median X bp, IQR Y–Z. n=N variants."`
- **Publications timeline:** `"Publications per year, 1998–2025. Peak 47 in 2021. Total N publications."`
- **Variant comparison:** `"Variant types compared. SNV: 412, indel: 89, large deletion: 23. ..."`
- **DNA distance analysis:** `"DNA distances for N variants across M domains. Median X bp, range Y–Z."`

Generators live in each chart's setup block; tested through the chart's own spec (no shared generator module — over-abstraction risk).

## Verification

### Automated (Vitest + Playwright)

- `chartExport.spec.js` — CSV BOM, RFC 4180 escaping for `,` / `"` / `\n`, header from `columns[].label`, empty rows; PNG serializer output is valid SVG, canvas size honors `scale`, background fill; filename format `hnf1b-db_{kebab}_{YYYY-MM-DD}.{ext}`.
- `ChartExportMenu.spec.js` — disabled when `svgEl` is null; PNG/CSV/SVG actions invoke matching utility; announcer fires on each click.
- `useChartAccessibility.spec.js` — IDs unique across two instances mounted simultaneously; `ariaProps` shape; `description` reactivity when `summary` changes.
- One Playwright spec on the Aggregations page: open export menu on Donut chart, assert download triggered and live-region content updated.

### Manual gates (PR checklist)

- axe-core scan on `/aggregations` page reports no new violations.
- NVDA spot-check (Windows, free) on one chart confirms title + description read aloud and the `<details>` data table is reachable via Tab.
- Open a PNG export at full size; crisp at 2× DPR, no clipped legends.
- Open a CSV export in Excel; UTF-8 (e.g., µ, Greek letters in phenotype names) renders correctly.

### CI

Existing Vitest, Playwright, and axe-core jobs gate the PR — no new CI config.

## What we are NOT doing

- No `dom-to-image-more` / `html2canvas` dependency; native SVG serialization is ~80 lines and avoids a transitive dep liability.
- No D3 rendering tests (already covered elsewhere).
- No cross-browser PNG quality testing for v1 (Chromium-only acceptable; documented in PR body).
- No Options-API → `<script setup>` rewrite of existing charts.
- No `<defs><pattern>` colorblind fills (deferred to follow-up; data table satisfies WCAG 1.4.1).
- No chart animations (#139), no service-worker caching (#138).
- No re-opening of the export-menu UX for non-aggregation charts (the 7 listed are the complete current set in `components/analyses/`).

## Risk + Rollback

**Highest-risk surface:** SVG→PNG style inlining. If D3's `.style()` calls and CSS class rules diverge between the live DOM and the cloned DOM, exported PNGs could render with default browser styles instead of the chart's intended appearance. Mitigation: the style-inlining walk uses `getComputedStyle` on each live node, transferred to the clone — captures both inline and stylesheet-derived styles. Unit test asserts a representative styled node round-trips.

**Rollback:** the PR is purely additive — `git revert` the squash commit removes the menu, the new files, and reverts the per-chart template changes. No data, schema, or API changes to undo.

## Execution

Detailed task breakdown produced by the `writing-plans` skill (next step). High-level phases:

1. Utilities + composable + tests (no UI change yet)
2. ChartExportMenu component + tests
3. Per-chart wiring (DonutChart first as the reference, then the other 6 following the same pattern)
4. Add `.sr-only` to `frontend/src/style.css` (and remove the duplicate scoped rule from `ExternalLink.vue` if linting flags it)
5. Manual verification gates

## References

- Issue [#135](https://github.com/berntpopp/hnf1b-db/issues/135) — ARIA labels and accessibility support for charts
- Issue [#136](https://github.com/berntpopp/hnf1b-db/issues/136) — Chart data export (CSV, PNG)
- PR #130 — origin of both review items
- `frontend/src/composables/useAccessibility.js` — existing a11y primitives
- WCAG 2.1: [1.1.1](https://www.w3.org/WAI/WCAG21/Understanding/non-text-content), [1.4.1](https://www.w3.org/WAI/WCAG21/Understanding/use-of-color), [2.1.1](https://www.w3.org/WAI/WCAG21/Understanding/keyboard)
- RFC 4180 — CSV format
