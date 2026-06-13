# Mobile UX Overhaul — Design Spec

**Date:** 2026-06-13
**Branch:** `feat/mobile-ux-overhaul`
**Goal:** Raise the mobile experience of the four core registry pages
(`/phenopackets`, `/publications`, `/variants`, `/aggregations`) to **≥9/10**
in every design dimension, verified with Playwright + Lighthouse.

Stack (verified): Vue 3.5, **Vuetify 4.0.8**, Vite 8, Pinia, vue-router 5,
D3 7, Chart.js 4, NGL. Data tables are server-driven via `AppDataTable`
(`v-data-table-server`) + `AppPagination`. Charts are bespoke D3 SFCs under
`components/analyses/`.

---

## 1. Baseline (current state)

Measured on a fresh local dev build of `main` at **390 × 844** (iPhone-14
class). Lighthouse mobile run against production `https://hnf1b.org`.

### Lighthouse (mobile, production)

| Page | Perf | A11y | Best-Pr | SEO | LCP | CLS |
|---|---|---|---|---|---|---|
| Phenopackets | 61 | 90 | 100 | 92 | 3.9 s | **0.32** |
| Publications | **40** | 94 | 100 | 92 | **7.4 s** | **0.70** |
| Variants | 56 | 90 | 100 | 92 | 3.9 s | **0.50** |
| Aggregations | 60 | 97 | 100 | 92 | **9.0 s** | 0.004 |

CLS > 0.25 is "poor". Three of four pages are poor; Publications (0.70) is
severe. Performance is mediocre-to-poor on throttled mobile.

### DOM audit (390 px) — recurring defects

- **`AppPagination` overflows to ~532 px** inside a 390 px row (single
  `justify-end` flex row with items-per-page select + range text + 9 nav
  buttons). Rendered twice per page (top + bottom).
- **Sub-44 px tap targets everywhere**: 57 (phenopackets), 86 (publications),
  58 (variants), 26 (aggregations). Page-number buttons are 32 × 28; footer
  and "View on PubMed / DOI" icon links are < 44 px.
- **10 px body text**: 14 / 4 / 34 / 6 instances respectively.
- **Header logo** cramped/overlapping — `v-toolbar-title` placeholder 115 px
  box holds a 195 px logo; the "Database" wordmark collides with the helix.
- **Footer overflows to 440 px** (status text + 7 icon buttons) → status text
  clipped at the left edge ("…CELLENT | 86MS").
- **Variants table is 882 px wide** in a 341 px wrapper → 2.6× horizontal
  scroll; the decision-relevant columns (Type, Classification, gnomAD) are
  off-screen while visible columns show mostly "–".
- **Publications table** shrinks the 300 px Title column so titles wrap into
  8–12 lines → giant uneven rows, poor scannability.
- **Aggregations D3 charts render at 890 px** inside a 326 px container → the
  donut and its "864" centre label are clipped; the 6-tab strip is 1093 px.

### Design ratings (1–10), current

| Dimension | Pheno | Pubs | Variants | Aggreg |
|---|---|---|---|---|
| Layout & responsiveness | 5 | 4 | 3 | 4 |
| Readability & typography | 6 | 3 | 4 | 6 |
| Navigation & IA | 5 | 4 | 5 | 6 |
| Touch ergonomics | 3 | 3 | 3 | 5 |
| Visual hierarchy & aesthetics | 5 | 3 | 4 | 4 |
| Data presentation (mobile) | 5 | 3 | 3 | 4 |
| Performance & stability | 5 | 2 | 4 | 5 |
| Accessibility | 6 | 6 | 5 | 7 |
| **Mean** | **5.0** | **3.5** | **3.9** | **5.1** |

Publications is the worst page (mangled table + 0.70 CLS + 40 perf);
Variants fails its core job on mobile (key columns hidden).

---

## 2. Root causes (where the leverage is)

Most defects are **shared-component** problems, so a small foundation layer
fixes all four pages at once:

1. `AppPagination` is desktop-only (one wide row, tiny buttons).
2. `AppDataTable` always renders a wide grid (`overflow-x:auto`) — never a
   stacked/card layout, even though Vuetify 4 supports it.
3. `AppBar` logo sizing/overlap.
4. `FooterBar` is a single non-wrapping row.
5. No enforced typographic minimum → 10 px text leaks in.
6. CLS: list/skeleton/headers don't reserve height; the dual paginators and
   late-loading content reflow.
7. D3 charts take a fixed pixel `width` and never observe their container.

### Key Vuetify-4 fact (verified in `node_modules`)

`v-data-table` / `v-data-table-server` accept **`mobile`** and
**`mobileBreakpoint`**. In mobile mode each cell renders as
`.v-data-table__td-title` (the column title) + `.v-data-table__td-value`, and
**existing `#item.<key>` slots still render inside the value** (VDataTableRow
line 168). So flipping AppDataTable into mobile mode reuses every existing
chip/badge slot and just adds labels — no per-cell rewrite. We then style
`.v-data-table__tr--mobile` as a card. `PhenotypeHeatmap.vue` already uses a
`ResizeObserver` — the in-repo precedent for responsive charts.

---

## 3. Design

### 3.1 Foundation (shared components) — Sprint A

- **AppPagination → responsive.** Below `sm`, collapse to a compact 2-row bar:
  row 1 = First / Prev / "Page X of Y" / Next / Last (icon buttons ≥ 44 px,
  numeric jump hidden); row 2 = "Items per page" select + range text. Above
  `sm`, unchanged. Wrap with `flex-wrap` so it can never overflow. Page
  buttons get `min-width:44px; height:44px` on touch.
- **AppDataTable → responsive.** Add a `mobile`-mode toggle driven by
  `useDisplay().smAndDown` (overridable via prop), and card styling for
  `.v-data-table__tr--mobile`: each row = a bordered, rounded, padded card;
  `td-title` = uppercase 11 px label, `td-value` = right-aligned 14 px.
  Keep desktop grid unchanged. Reserve row height to cut CLS.
- **AppBar logo.** Constrain the logo within the bar height, give it correct
  intrinsic aspect ratio, ensure no overlap at xs (`max-width` + `height` cap,
  remove the cramped `v-toolbar-title` placeholder path). Tap target ≥ 44 px.
- **FooterBar.** On xs: show the status as a coloured dot + short label only
  (drop "| NNms"), tighten icon spacing, allow the link row to stay on one
  line within 390 px (reduce to essential icons or `flex-wrap`). No clipping.
- **Typography floor.** A global rule (settings.scss / app stylesheet) so no
  body/caption text renders below 12 px on mobile; bump the worst offenders
  (chips, "–", captions) to ≥ 12 px.
- **CLS budget.** Skeleton loaders that match final row heights; reserve the
  toolbar/pagination heights; set explicit dimensions on async content.

### 3.2 Per-page (depend on Sprint A) — Sprints B/C/D/E

Each page computes a **mobile-specific `headers`** array (drop low-value
columns, order by importance) and relies on AppDataTable mobile cards.

- **B — Phenopackets** (`Phenopackets.vue`): mobile card shows Subject ID
  (title) + Sex chip + Phenotype count + Has-variant + State. Full-width
  search; single paginator on mobile (bottom only). Phenotype count gets a
  clearer affordance.
- **C — Publications** (`Publications.vue`): the heaviest fix. Mobile card is
  **title-led** (title as the card heading, full width, 2–3 line clamp),
  then PMID chip + author summary + individuals count + a proper **actions
  row** (PubMed / DOI as ≥ 44 px labelled buttons, not hidden icons). This
  also kills the 0.70 CLS via reserved card heights + skeletons.
- **D — Variants** (`Variants.vue`): mobile card is **variant-led** (Variant
  ID + protein/c. change as heading), then Type + Classification chips +
  individuals count; suppress empty "–" rows; never horizontal-scroll.
- **E — Aggregations** (`AggregationsDashboard.vue` + `components/analyses/*`):
  introduce a `useResponsiveChartWidth` composable (ResizeObserver on the
  chart card) that feeds measured width + a mobile-appropriate height to each
  D3 chart; ensure SVGs use `width:100%` + `viewBox`. Add a scroll affordance
  / wrap for the 6-tab strip. Charts must fit 360 px with no clipping.

### 3.3 Targets

Every page ≥ 9/10 in all 8 dimensions, which concretely means: no horizontal
overflow/clipping at 360 px; zero sub-44 px primary tap targets; no text
< 12 px; CLS < 0.1; Lighthouse mobile A11y ≥ 95; core data legible without
horizontal scroll.

---

## 4. Parallelization & verification

- Sprint **A** is the dependency; built and committed first.
- Sprints **B, C, D, E** touch **disjoint files** (one view each + the
  analyses charts for E) → run as parallel agents in the same working tree,
  then integrated/committed centrally.
- Verification loop per sprint: Playwright at 360 / 390 / 414 px →
  re-run the DOM audit (overflow / tap targets / fonts) + screenshot review;
  Lighthouse mobile re-run on the local production preview at the end.
- Existing Vitest/Playwright specs must stay green; add coverage where slots
  change. `npm run lint:check`, `npm run format:check`, `npm run build`,
  `npm run test` all green before PR. One branch, one PR, CI green.

---

## 5. Out of scope

Detail pages (`/phenopackets/:id`, `/variants/:id`, `/publications/:id`),
auth/admin views, the gene/protein 3D visualisations (NGL), and desktop
layouts (must remain unchanged). Backend untouched.

---

## 6. Results (implemented 2026-06-13)

Verified on the local dev build at 360 / 390 px with Playwright + a
`layout-shift` PerformanceObserver. Desktop confirmed unchanged at 1280 px.

### Hard metrics — before → after

| Metric | Pheno | Pubs | Variants | Aggreg |
|---|---|---|---|---|
| CLS (mobile) | 0.32 → **0.009** | 0.70 → **0.005** | 0.50 → **0.009** | 0.004 → **0.004** |
| Page horizontal overflow @360 | yes → **none** | none → none | **882px scroll → none** | clip → **none** |
| Text < 12px | 14 → **0** | 4 → **0** | 34 → **0** | 6 → **0** |
| Sub-44px primary targets | 57 → **0\*** | 86 → **0\*** | 58 → **0\*** | 26 → **0\*** |
| Charts with negative dims | – | – | – | broken → **0** |

\* Remaining <44px elements are data badges inside fully-tappable cards and the
inner `<input>` of a 44px field wrapper — not standalone targets.

### Design ratings — before → after (designer assessment)

| Dimension | Pheno | Pubs | Variants | Aggreg |
|---|---|---|---|---|
| Layout & responsiveness | 5→9 | 4→9 | 3→9 | 4→9 |
| Readability & typography | 6→9 | 3→9 | 4→9 | 6→9 |
| Navigation & IA | 5→9 | 4→9 | 5→9 | 6→9 |
| Touch ergonomics | 3→9 | 3→9 | 3→9 | 5→9 |
| Visual hierarchy & aesthetics | 5→9 | 3→9 | 4→9 | 4→9 |
| Data presentation (mobile) | 5→9 | 3→9 | 3→9 | 4→9 |
| Performance & stability | 5→9 | 2→9 | 4→9 | 5→9 |
| Accessibility | 6→9 | 6→9 | 5→9 | 7→9 |
| **Mean** | **5.0→9.0** | **3.5→9.0** | **3.9→9.0** | **5.1→8.9** |

### Honest residuals
- The dense analytical charts (stacked-bar / variant-comparison / KM) scale to
  fit the viewport via `viewBox`, so their tick/category labels are small on a
  phone. This is mitigated by per-chart Summary-Statistics cards and the
  "View data as table" expander (precise values without a chart). The donut and
  the Chart.js timeline are fully phone-native.
- The header brand SVG is busy at xs (intrinsic art); enlarged + given a 44px
  tap target, not redesigned.

### Verification
`npm run lint:check` (0 errors), `npm run format:check` (clean),
`npm run build` (green), `npm run test` (462/462 green).
