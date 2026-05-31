# Design Spec — Phenopacket & Variant page UX improvements

- **Date:** 2026-05-31
- **Status:** Approved (design); pending implementation plan
- **Branch:** `feat/pheno-variant-ui-improvements`
- **Scope:** Frontend only. No backend, API, schema, DB, or migration changes.

## 1. Motivation

Two curated detail pages have data that is already fetched but under-surfaced:

1. **Phenopacket detail** (`/phenopackets/phenopacket-892`) — the "Genomic
   Interpretations" card shows a `Pathogenic` badge with no rationale, and the
   link to the full variant is a bare, unlabeled arrow icon that users miss.
2. **Variant detail** (`/variants/<vrs-id>`) — the "Affected Individuals" table
   shows only Subject ID / Sex / Added and wastes its horizontal space; the rich
   per-individual phenotype data is fetched then discarded, and there is no
   visual summary of phenotypes across the variant's carriers.

All four improvements below are achievable with **frontend-only** changes
because the underlying data is already present in responses the pages already
make.

## 2. Goals

- **G1.** Hover tooltip on the phenopacket ACMG classification badge showing the
  applied criteria as color-coded chips with plain-English meanings.
- **G2.** Make the phenopacket→variant link obvious: a labelled "View variant"
  button instead of a bare arrow.
- **G3.** Add a Phenotypes column to the variant page's Affected Individuals
  table: a present-only count chip with a hover tooltip listing all terms
  (excluded terms grouped separately).
- **G4.** Add a graphical individual × phenotype heatmap on the variant page,
  colored by organ system, below the Affected Individuals table.

## 3. Non-goals / out of scope

- **No backend changes.** The variant *detail-page header* badge
  (`PageVariant.vue`, bound to the `/all-variants` `classificationVerdict`
  field) does **not** carry ACMG criteria; adding a criteria tooltip *there*
  would require a new backend field and is explicitly out of scope. G1 targets
  only the **phenopacket-page** badge, where the criteria already ride inside
  the full phenopacket JSON.
- **No cross-database statistical comparison** on the heatmap. The reference
  Variant Comparison chart (`/aggregations?tab=variant-comparison`) is a
  two-group Fisher/FDR cohort comparison; a single variant's carrier set has no
  comparison group, so the heatmap shows this variant's carriers only (no
  p-values / Cohen's h, which would be misleading on tiny cohorts).
- No change to the MCP server (its `get_individual`/`get_variant` shapes are
  independent of these REST-fed pages).

## 4. Data sources (already available — verified live)

### 4.1 ACMG criteria (Feature G1)

Path inside the phenopacket JSON the page already fetches via
`getPhenopacket(id)` → `GET /phenopackets/{id}` (and equally present in
`GET /phenopackets/by-variant/{id}`):

```
interpretations[].diagnosis.genomicInterpretations[].variantInterpretation
  .extensions[]  where  name === "classification_criteria"
    .value.guidelines  // "ACMG" | "ClinGen CNV"
    .value.criteria    // comma-separated string (format depends on guideline)
```

The frontend currently never reads `variantInterpretation.extensions` (it only
reads `variationDescriptor.extensions` for coordinates). A repo-wide grep for
`classification_criteria` returns zero hits in `frontend/src`.

**Verified DB coverage / formats** (live `hnf1b_phenopackets`):

- `ACMG` — 441 records, 49 distinct strings. Format: comma-separated
  `CODE_Strength` tokens. Distinct codes in data: `PVS1, PS2, PS3, PM1, PM2,
  PM4, PM5, PP1, PP2, PP3, PP5, BS1, BP4`. Strengths in data: `VeryStrong,
  Strong, Moderate, Supporting`. Example:
  `PM1_Moderate, PM2_Supporting, PM5_Moderate, PP2_Supporting, PP3_Supporting, PS2_Strong`.
- `ClinGen CNV` — 423 records, 2 distinct strings. Format: comma-separated
  section tokens `<section><x N>(<points>)`. Distinct section codes in data:
  `1A, 2A, 3A, 4C, 4L`. Example:
  `1A, 2A, 3A, 4Cx1(0.15), 4Lx1(0.15)`.
- Some interpretations may have **no** `classification_criteria` extension →
  tooltip must degrade to verdict-only.

### 4.2 Per-individual phenotypes (Features G3, G4)

`PageVariant.vue` already calls `getPhenopacketsByVariant(variantId)` →
`GET /phenopackets/by-variant/{variant_id}`, whose response carries, per
affected individual, the **full** GA4GH `phenopacket` object including:

```
phenopacket.phenotypicFeatures[] = {
  type: { id: "HP:0000107", label: "Renal cyst" },
  excluded?: boolean,            // true = explicitly absent; absent/false = present
  onset?: { id, label },
  modifiers?: [{ id, label }],
  severity?: { id, label }
}
```

Today the component's `.map()` (PageVariant.vue ~L798-807) reduces each row to
`{ phenopacket_id, subject_id, subject_sex, created_at }` and **drops**
`phenotypicFeatures`. The only change needed is to retain it.

## 5. Feature designs

### G1 — ACMG criteria tooltip

**New util `frontend/src/utils/acmgCriteria.js`:**

```
parseClassificationCriteria(criteriaString, guidelines) -> {
  guideline: "ACMG" | "ClinGen CNV",
  pathogenic: Criterion[],   // ACMG P* codes
  benign:     Criterion[],   // ACMG B* codes
  cnv:        CnvCriterion[], // ClinGen CNV sections
  totalPoints?: number,      // CNV only (sum of points)
  raw: string
}
```

- **ACMG token** `PS2_Strong` → `{ code:'PS2', strength:'Strong',
  direction:'pathogenic', label:<from ACMG_CRITERIA map> }`. Direction by first
  letter: `P*` → pathogenic, `B*` → benign. Color: pathogenic = `red`/`orange`
  by strength tier; benign = `green`. Unknown code → chip with code only,
  `label: ''` (never throws).
- **CNV token** `4Cx1(0.15)` → `{ section:'4C', count:1, points:0.15,
  label:<from CLINGEN_CNV map> }`; `totalPoints` = Σ points. Color by sign of
  points (≥0 → amber/red dosage evidence; <0 → green).
- Pure, synchronous, no I/O. Robust to whitespace, missing strength
  (`BP4` with no `_x`), empty string, and `null`.

Description maps live in the same util (see Appendix A & B). The ACMG map
contains the **full** ACMG/AMP 2015 set (28 codes) for future-proofing, not just
the 13 currently in data.

**Render (in `InterpretationsCard.vue`):** wrap the existing classification
`<v-chip>` (L54-61) in a `<v-tooltip location="top" max-width="360">` using the
`#activator="{ props }"` + `v-bind="props"` pattern cloned verbatim from
`PhenotypicFeaturesCard.vue` (L15-92), reusing its `.tooltip-content` /
`.tooltip-header` / `.tooltip-row` / `.tooltip-footer` CSS.

- Header: verdict label (e.g. "Pathogenic") + guideline ("ACMG/AMP" or
  "ClinGen CNV").
- Body (ACMG): two groups — **"Pathogenic evidence"** and **"Benign evidence"**
  (omit an empty group). Each row = a chip `[PS2 · Strong]` (colored by
  direction/strength) + the plain-English meaning.
- Body (CNV): one list of section chips `[4C ×1 · +0.15]` + meaning; footer =
  "Total score: <totalPoints>".
- Empty / missing criteria → body = "No ACMG criteria recorded."
- Accessibility: activator gets `tabindex="0"`, `style="cursor: help"`, and an
  `:aria-label` summarizing verdict + criteria; tooltip content is decorative
  duplicate.

The criteria are read from the interpretation object the card already loops
over: add a `getClassificationCriteria(interpretation)` method that reads
`...genomicInterpretations[0].variantInterpretation.extensions.find(e => e.name
=== 'classification_criteria')?.value`.

### G2 — "View variant" button

Replace `InterpretationsCard.vue` L64-73 (`<v-btn icon="mdi-arrow-right" …>`)
with a labelled button:

```html
<v-tooltip location="top" text="Open full variant details">
  <template #activator="{ props }">
    <v-btn
      v-bind="props"
      v-if="getVariantId(interpretation)"
      :to="`/variants/${encodeURIComponent(getVariantId(interpretation))}`"
      color="deep-purple" variant="tonal" size="small"
      prepend-icon="mdi-arrow-right"
      aria-label="View full variant details"
    >View variant</v-btn>
  </template>
</v-tooltip>
```

`deep-purple` matches the interpretations-domain color
(`CARD_HEADERS.interpretations.iconColor`). Keeps the same route target and
`encodeURIComponent` behavior.

### G3 — Phenotypes column

In `PageVariant.vue`:

1. Retain phenotype data in the row map (~L798-807):
   `phenotypic_features: pp.phenopacket?.phenotypicFeatures ?? []`,
   `phenotype_count: <count where !excluded>`.
2. Add a `Phenotypes` header to `headers` (L653-671), `value: 'phenotype_count'`,
   `sortable: true`, width ~160px, placed between Sex and Added.
3. Custom cell slot: a count chip — `<v-chip size="x-small"
   :color="count > 0 ? 'green-lighten-3' : 'grey-lighten-2'">{{ count }}
   phenotype(s)</v-chip>` — wrapped in a `v-tooltip` whose body lists each
   **present** term as `label (HP:id)` and, if any, an **"Excluded"** subsection
   listing excluded terms. Cap the visible tooltip list height with scroll for
   very long lists. Mirrors the existing `features_count` pattern in
   `PagePublication.vue` (L304-309) plus the tooltip pattern from
   `PhenotypicFeaturesCard.vue`.

Count semantics: **present-only** (`!excluded`) for the chip number and the
sort key; excluded terms appear only inside the tooltip.

### G4 — Phenotype heatmap

**New component `frontend/src/components/analyses/PhenotypeHeatmap.vue`** (D3/SVG,
following the conventions of `StackedBarChart.vue` / `VariantComparisonChart.vue`).

**Props:**

```
individuals: Array<{
  phenopacket_id: string,
  subject_id: string,
  phenotypicFeatures: Array<{ type:{id,label}, excluded?:boolean, onset?:{...} }>
}>
maxTerms?: number   // default e.g. 30; cap with expand toggle
chartName?: string  // for export menu
```

**Layout:**

- **Rows** = affected individuals. Row label = `subject_id`, linking to
  `/phenopackets/{phenopacket_id}`. Default order: descending present-count
  (most-phenotyped first), `subject_id` tiebreak.
- **Columns** = union of HPO terms across the cohort, **grouped by organ
  system** (via `getOrganSystem(hpoId)` / `ORGAN_SYSTEMS` / `getCategoryColor`
  from `utils/ageParser.js`), a thin colored band + label per group; within a
  group, columns ordered by descending cohort frequency.
- **Cell encoding (tri-state):** present = filled cell in the column's
  organ-system color; excluded = hollow/outlined muted cell (distinct from
  not-reported); not-reported (term absent from that individual's list) =
  empty/very-faint cell.
- **Hover tooltip:** HPO label + `HP:id` + organ system + status
  (present/excluded/not reported) + onset label when available.
- **Scaling:** if the term union exceeds `maxTerms`, show the top-N most
  frequent and an "Show all N terms" expand toggle; rows scroll vertically when
  the cohort is large. Responsive `viewBox` + `preserveAspectRatio` like sibling
  charts.
- **Reuse:** `ChartExportMenu.vue` (PNG/CSV/SVG; CSV = individual × term
  present/absent matrix) and `useChartAccessibility` (role=img, aria-labelledby,
  sr-only summary) exactly as the other analyses charts do.
- **Empty state:** when no individual has any phenotype, render a friendly
  "No phenotype data recorded for this variant's carriers" placeholder instead
  of an empty grid.

**Wire-in:** in `PageVariant.vue`, render `<PhenotypeHeatmap>` in its own
`<v-card>` titled "Phenotype Profile" directly below the Affected Individuals
card, `v-if="phenopacketsWithVariant.length > 0"`, fed from the same
`phenopacketsWithVariant` rows (now carrying `phenotypic_features`).

**Theme-awareness (approved default):** this is the first theme-aware chart in
the app — axis/label/gridline colors and the hover tooltip use
`rgb(var(--v-theme-*))` tokens (existing charts hardcode `#666` and a white
tooltip). Organ-system fill hues are chosen to remain legible on both light and
dark backgrounds. Cell strokes use theme tokens.

## 6. Files touched

**New:**
- `frontend/src/utils/acmgCriteria.js` — parser + ACMG & ClinGen CNV maps.
- `frontend/src/components/analyses/PhenotypeHeatmap.vue` — heatmap.
- Unit tests: `acmgCriteria.spec.js`, `PhenotypeHeatmap.spec.js` (+ light tests
  for the new InterpretationsCard / PageVariant behavior as fits existing test
  layout).

**Edited:**
- `frontend/src/components/phenopacket/InterpretationsCard.vue` — G1 tooltip + G2 button.
- `frontend/src/views/PageVariant.vue` — G3 column + G4 heatmap wire-in + retain `phenotypicFeatures`.

## 7. Testing & verification

- **Unit (vitest):** `parseClassificationCriteria` across ACMG multi-criterion
  strings, single `BP4_Supporting`, benign+pathogenic mix, ClinGen CNV with
  points + total, unknown code, empty string, `null`. Heatmap aggregation
  (present/excluded/not-reported tri-state, organ-system grouping, ordering,
  maxTerms cap).
- **Lint/format/build:** the frontend CI gate runs vitest + eslint + prettier
  (`src` & `tests`) + build. Run `prettier --write` before commit.
- **Playwright manual verification:** `/phenopackets/phenopacket-892` (hover the
  badge → criteria tooltip; "View variant" button visible & navigates) and
  `/variants/ga4gh:VA.PuNUJ-j-dgkKwAF2ZRDuY1usqx5VyJYG` (Phenotypes column +
  tooltip; heatmap renders, hover a cell, export menu) — in **both** light and
  dark themes.

## 8. Risks

- **ClinGen CNV description accuracy** — section-letter wording should follow the
  ClinGen 2019 CNV scoring metric (Riggs et al. 2020); Appendix B is a starter
  map and may be refined. Unknown sections degrade gracefully (code-only chip).
- **Wide term unions** on highly-phenotyped cohorts — mitigated by organ-system
  grouping + top-N cap + expand toggle.
- **Theme-aware chart is net-new** in this codebase — contained to one component;
  fall back to sibling-chart hardcoded fills if theming proves fiddly.

## Appendix A — ACMG/AMP 2015 criteria descriptions (map content)

Pathogenic: `PVS1` null variant (LoF mechanism) · `PS1` same aa change as known
pathogenic · `PS2` de novo (maternity+paternity confirmed) · `PS3` well-established
functional damage · `PS4` increased prevalence in affecteds · `PM1` mutational
hotspot / critical domain · `PM2` absent/rare in population databases · `PM3`
in trans with pathogenic (recessive) · `PM4` protein length change (non-repeat) ·
`PM5` novel missense at a known pathogenic residue · `PM6` assumed de novo ·
`PP1` cosegregation with disease · `PP2` missense in low-benign-rate gene · `PP3`
computational evidence of damage · `PP4` phenotype highly specific for gene ·
`PP5` reputable source reports pathogenic.

Benign: `BA1` AF >5% (stand-alone) · `BS1` AF greater than disorder expects ·
`BS2` seen in healthy adult (full-penetrance disorder) · `BS3` functional studies
show no damage · `BS4` lack of segregation · `BP1` missense where only truncating
is pathogenic · `BP2` in trans/cis with pathogenic · `BP3` in-frame indel in
repeat region · `BP4` computational evidence of no impact · `BP5` alternate
molecular basis found · `BP6` reputable source reports benign · `BP7` synonymous,
no predicted splice impact.

## Appendix B — ClinGen CNV section descriptions (starter map)

- `1A`/`1B` — Section 1: initial assessment (contains protein-coding/functional
  elements vs none).
- `2A`… — Section 2: overlap with established dosage-sensitive (HI/TS) genes or
  established benign regions.
- `3A`/`3B`/`3C` — Section 3: number of protein-coding genes (0–24 / 25–34 / ≥35).
- `4C`,`4L`,… — Section 4: detailed evidence (literature, case-control,
  de novo, segregation, phenotype specificity); points carried in the data.
- `5A`… — Section 5: inheritance / family-history evidence.

Refine wording against the ClinGen 2019 CNV interpretation standard during
implementation.
