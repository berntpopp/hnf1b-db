# Phenopacket & Variant Page UX Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface already-fetched-but-hidden data on two pages — an ACMG-criteria tooltip and a clear "View variant" button on the phenopacket page, and a phenotype-count column plus an organ-system-colored individual×phenotype heatmap on the variant page.

**Architecture:** 100% frontend (Vue 3 + Vuetify 3 + D3). Two new pure utils (`acmgCriteria.js`, `phenotypeMatrix.js`) hold all parsing/aggregation logic and are unit-tested in isolation (TDD). Two existing Options-API components are edited (`InterpretationsCard.vue`, `PageVariant.vue`) and one new hybrid Options-API+`setup()` D3 chart component is added (`PhenotypeHeatmap.vue`) following the exact conventions of the existing `StackedBarChart.vue`.

**Tech Stack:** Vue 3, Vuetify 3, D3 v7, Vitest (`tests/unit/**/*.spec.js`), `@vue/test-utils`, happy-dom.

**Spec:** `.planning/specs/2026-05-31-pheno-variant-page-ux-design.md`

**Branch:** `feat/pheno-variant-ui-improvements` (already checked out).

**Working directory for all commands:** `frontend/` (run `cd frontend` first; all paths below are relative to `frontend/` unless prefixed with `frontend/`).

---

## Conventions every task follows

- **TDD:** failing test → run (red) → minimal impl → run (green) → commit.
- **Run a single test file:** `npx vitest run tests/unit/<path>.spec.js`
- **CI-equivalent gate before EACH commit that touches `src/` or `tests/`** (CI checks `{src,tests}`, but `npm run format` only covers `src/` — so always use the glob form):
  1. `npx vitest run` (or the single file during a task)
  2. `npm run lint`
  3. `npx prettier --write "{src,tests}/**/*.{js,jsx,vue,json,css,scss,md}"`
  4. `npx prettier --check "{src,tests}/**/*.{js,jsx,vue,json,css,scss,md}"`
- **Final build gate (once, Task 9):** `npm run build`.
- **Commit messages:** Conventional Commits; end with the Co-Authored-By trailer used in this repo.

---

## File structure (decomposition)

**New files:**
- `frontend/src/utils/acmgCriteria.js` — parse ACMG / ClinGen-CNV criteria strings + description maps + chip-color helpers. Pure, no I/O.
- `frontend/src/utils/phenotypeMatrix.js` — `summarizePhenotypes()` (count + present/excluded lists) and `buildPhenotypeMatrix()` (grouped, ordered individual×term matrix). Pure, no I/O.
- `frontend/src/components/analyses/PhenotypeHeatmap.vue` — D3 SVG heatmap consuming `buildPhenotypeMatrix()`.
- `frontend/tests/unit/utils/acmgCriteria.spec.js`
- `frontend/tests/unit/utils/phenotypeMatrix.spec.js`
- `frontend/tests/unit/components/analyses/PhenotypeHeatmap.spec.js`

**Edited files:**
- `frontend/src/components/phenopacket/InterpretationsCard.vue` — G1 ACMG tooltip + G2 "View variant" button.
- `frontend/src/views/PageVariant.vue` — retain `phenotypicFeatures`; migrate Affected-Individuals table to `AppDataTable`; G3 Phenotypes column; G4 heatmap wire-in.
- `frontend/tests/unit/views/PageVariant.spec.js` — extend for retained phenotypes + column.

**Reused unchanged:** `components/common/AppDataTable.vue`, `components/analyses/ChartExportMenu.vue`, `composables/useChartAccessibility.js`, `utils/ageParser.js`, `utils/cardStyles.js`, `components/phenopacket/PhenotypicFeaturesCard.vue` (CSS reference).

---

## Task 1: `acmgCriteria.js` util (parse + maps)

**Files:**
- Create: `frontend/src/utils/acmgCriteria.js`
- Test: `frontend/tests/unit/utils/acmgCriteria.spec.js`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/unit/utils/acmgCriteria.spec.js`:

```js
/**
 * Unit tests for the ACMG / ClinGen-CNV classification-criteria parser.
 *
 * Tests cover: ACMG token parsing (code + strength + direction + label),
 * pathogenic/benign grouping, ClinGen CNV section parsing with points + total,
 * unknown codes, and empty/null input.
 */
import { describe, it, expect } from 'vitest';
import {
  parseClassificationCriteria,
  acmgChipColor,
  cnvChipColor,
  ACMG_CRITERIA,
} from '@/utils/acmgCriteria';

describe('parseClassificationCriteria — ACMG', () => {
  it('parses a multi-criterion ACMG string into grouped pathogenic/benign entries', () => {
    const r = parseClassificationCriteria(
      'PM1_Moderate, PM2_Supporting, PP3_Supporting, PS2_Strong, BP4_Supporting',
      'ACMG',
    );
    expect(r.guideline).toBe('ACMG');
    expect(r.pathogenic.map((c) => c.code)).toEqual(['PM1', 'PM2', 'PP3', 'PS2']);
    expect(r.benign.map((c) => c.code)).toEqual(['BP4']);
    const ps2 = r.pathogenic.find((c) => c.code === 'PS2');
    expect(ps2).toMatchObject({ code: 'PS2', strength: 'Strong', direction: 'pathogenic' });
    expect(ps2.label).toBe(ACMG_CRITERIA.PS2);
    expect(r.label).toBeUndefined(); // sanity: no stray field
  });

  it('parses a single benign criterion with no pathogenic entries', () => {
    const r = parseClassificationCriteria('BP4_Supporting', 'ACMG');
    expect(r.pathogenic).toEqual([]);
    expect(r.benign).toHaveLength(1);
    expect(r.benign[0]).toMatchObject({ code: 'BP4', strength: 'Supporting', direction: 'benign' });
  });

  it('handles an unknown ACMG code without throwing and with empty label', () => {
    const r = parseClassificationCriteria('ZZ9_Strong', 'ACMG');
    expect(r.pathogenic[0]).toMatchObject({ code: 'ZZ9', strength: 'Strong', label: '' });
  });

  it('handles a criterion with no strength suffix', () => {
    const r = parseClassificationCriteria('BP4', 'ACMG');
    expect(r.benign[0]).toMatchObject({ code: 'BP4', strength: '', direction: 'benign' });
  });
});

describe('parseClassificationCriteria — ClinGen CNV', () => {
  it('parses sections with counts and points and sums the total', () => {
    const r = parseClassificationCriteria('1A, 2A, 3A, 4Cx1(0.15), 4Lx1(0.15)', 'ClinGen CNV');
    expect(r.guideline).toBe('ClinGen CNV');
    expect(r.pathogenic).toEqual([]);
    expect(r.benign).toEqual([]);
    expect(r.cnv.map((c) => c.section)).toEqual(['1A', '2A', '3A', '4C', '4L']);
    const fourC = r.cnv.find((c) => c.section === '4C');
    expect(fourC).toMatchObject({ section: '4C', count: 1, points: 0.15 });
    expect(r.totalPoints).toBeCloseTo(0.3, 5);
  });

  it('treats the parenthesized value as the section total (not per-occurrence)', () => {
    const r = parseClassificationCriteria('4Cx6(0.9)', 'ClinGen CNV');
    expect(r.cnv[0]).toMatchObject({ section: '4C', count: 6, points: 0.9 });
    expect(r.totalPoints).toBeCloseTo(0.9, 5);
  });
});

describe('parseClassificationCriteria — empty/null', () => {
  it('returns empty groups for empty string', () => {
    const r = parseClassificationCriteria('', 'ACMG');
    expect(r.pathogenic).toEqual([]);
    expect(r.benign).toEqual([]);
    expect(r.cnv).toEqual([]);
    expect(r.raw).toBe('');
  });

  it('returns empty groups for null criteria', () => {
    const r = parseClassificationCriteria(null, null);
    expect(r.guideline).toBe('ACMG'); // default guideline
    expect(r.pathogenic).toEqual([]);
  });
});

describe('chip color helpers', () => {
  it('colors pathogenic by strength and benign green', () => {
    expect(acmgChipColor({ direction: 'pathogenic', strength: 'Strong' })).toBe('red');
    expect(acmgChipColor({ direction: 'pathogenic', strength: 'Moderate' })).toBe('deep-orange');
    expect(acmgChipColor({ direction: 'pathogenic', strength: 'Supporting' })).toBe('orange');
    expect(acmgChipColor({ direction: 'benign', strength: 'Strong' })).toBe('green');
  });

  it('colors CNV chips by point sign', () => {
    expect(cnvChipColor(0.15)).toBe('orange');
    expect(cnvChipColor(-0.3)).toBe('green');
    expect(cnvChipColor(null)).toBe('grey');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/unit/utils/acmgCriteria.spec.js`
Expected: FAIL — "Failed to resolve import '@/utils/acmgCriteria'".

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/utils/acmgCriteria.js`:

```js
/**
 * Parse ACMG/AMP and ClinGen-CNV classification-criteria strings into
 * structured, render-ready data, plus chip-color helpers and description maps.
 *
 * Data formats (verified against the live database):
 *   ACMG:         "PM1_Moderate, PM2_Supporting, PS2_Strong"   (CODE_Strength, comma-separated)
 *   ClinGen CNV:  "1A, 2A, 3A, 4Cx1(0.15), 4Lx1(0.15)"          (section[xCount](points))
 *
 * Source: variantInterpretation.extensions[name='classification_criteria'].value
 * Pure module, no I/O.
 */

// Full ACMG/AMP 2015 (Richards et al.) criterion → short plain-English meaning.
export const ACMG_CRITERIA = {
  // Pathogenic
  PVS1: 'Null variant in a gene where loss of function is a known mechanism',
  PS1: 'Same amino-acid change as an established pathogenic variant',
  PS2: 'De novo (maternity and paternity confirmed)',
  PS3: 'Well-established functional studies show a damaging effect',
  PS4: 'Prevalence in affected individuals significantly increased vs controls',
  PM1: 'Located in a mutational hotspot / critical functional domain',
  PM2: 'Absent or at extremely low frequency in population databases',
  PM3: 'For recessive disorders, detected in trans with a pathogenic variant',
  PM4: 'Protein length change (in-frame indel / stop-loss) in a non-repeat region',
  PM5: 'Novel missense at a residue where a different pathogenic missense is known',
  PM6: 'Assumed de novo (without confirmation of parentage)',
  PP1: 'Cosegregation with disease in multiple affected family members',
  PP2: 'Missense in a gene with a low rate of benign missense variation',
  PP3: 'Multiple computational lines of evidence support a damaging effect',
  PP4: "Patient's phenotype/family history highly specific for the gene",
  PP5: 'Reputable source reports the variant as pathogenic',
  // Benign
  BA1: 'Allele frequency >5% in population databases (stand-alone benign)',
  BS1: 'Allele frequency greater than expected for the disorder',
  BS2: 'Observed in a healthy adult for a fully-penetrant early-onset disorder',
  BS3: 'Well-established functional studies show no damaging effect',
  BS4: 'Lack of segregation in affected family members',
  BP1: 'Missense in a gene where only truncating variants cause disease',
  BP2: 'Observed in trans/in cis with a pathogenic variant',
  BP3: 'In-frame indel in a repetitive region without known function',
  BP4: 'Multiple computational lines of evidence suggest no impact',
  BP5: 'Found in a case with an alternate molecular basis for disease',
  BP6: 'Reputable source reports the variant as benign',
  BP7: 'Synonymous variant with no predicted splice impact',
};

// ClinGen CNV (Riggs et al. 2020) scoring sections → short meaning. Starter map;
// unknown sections degrade to a code-only chip.
export const CLINGEN_CNV_SECTIONS = {
  '1A': 'Section 1: contains protein-coding or other functional elements',
  '1B': 'Section 1: no protein-coding or functional elements',
  '2A': 'Section 2: overlaps an established dosage-sensitive (HI/TS) gene or region',
  '3A': 'Section 3: 0–24 protein-coding genes',
  '3B': 'Section 3: 25–34 protein-coding genes',
  '3C': 'Section 3: 35+ protein-coding genes',
  '4C': 'Section 4: case evidence (literature / case-level data)',
  '4L': 'Section 4: case–control / observational evidence',
  '5A': 'Section 5: inheritance / family-history evidence',
};

/**
 * @param {string|null} criteria  comma-separated criteria string
 * @param {string|null} guidelines  "ACMG" | "ClinGen CNV" (defaults to ACMG)
 * @returns {{guideline:string, pathogenic:Array, benign:Array, cnv:Array, totalPoints:(number|null), raw:string}}
 */
export function parseClassificationCriteria(criteria, guidelines) {
  const raw = typeof criteria === 'string' ? criteria.trim() : '';
  const guideline = guidelines === 'ClinGen CNV' ? 'ClinGen CNV' : 'ACMG';
  const result = { guideline, pathogenic: [], benign: [], cnv: [], totalPoints: null, raw };
  if (!raw) return result;

  const tokens = raw
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean);

  if (guideline === 'ClinGen CNV') {
    let total = 0;
    let sawPoints = false;
    for (const tok of tokens) {
      const m = tok.match(/^([0-9]+[A-Za-z]+)(?:x(\d+))?(?:\(([-\d.]+)\))?$/);
      const section = m ? m[1].toUpperCase() : tok;
      const count = m && m[2] ? parseInt(m[2], 10) : 1;
      let points = null;
      if (m && m[3] != null) {
        const p = parseFloat(m[3]);
        if (!Number.isNaN(p)) {
          points = p;
          total += p; // parenthesized value is the section TOTAL (already x count)
          sawPoints = true;
        }
      }
      result.cnv.push({ section, count, points, label: CLINGEN_CNV_SECTIONS[section] || '' });
    }
    result.totalPoints = sawPoints ? Math.round(total * 100) / 100 : null;
    return result;
  }

  // ACMG
  for (const tok of tokens) {
    const us = tok.indexOf('_');
    const code = us === -1 ? tok : tok.slice(0, us);
    const strength = us === -1 ? '' : tok.slice(us + 1);
    const direction = /^B/i.test(code) ? 'benign' : 'pathogenic';
    const entry = { code, strength, direction, label: ACMG_CRITERIA[code] || '' };
    (direction === 'benign' ? result.benign : result.pathogenic).push(entry);
  }
  return result;
}

/** Vuetify color for an ACMG criterion chip. */
export function acmgChipColor({ direction, strength } = {}) {
  if (direction === 'benign') {
    return strength === 'Supporting' ? 'green-lighten-1' : 'green';
  }
  if (strength === 'VeryStrong' || strength === 'Strong') return 'red';
  if (strength === 'Moderate') return 'deep-orange';
  return 'orange';
}

/** Vuetify color for a ClinGen-CNV section chip, by point sign. */
export function cnvChipColor(points) {
  if (points == null || Number.isNaN(points)) return 'grey';
  return points >= 0 ? 'orange' : 'green';
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/unit/utils/acmgCriteria.spec.js`
Expected: PASS (all cases).

- [ ] **Step 5: Format, lint, commit**

```bash
npx prettier --write "{src,tests}/**/*.{js,jsx,vue,json,css,scss,md}"
npm run lint
git add src/utils/acmgCriteria.js tests/unit/utils/acmgCriteria.spec.js
git commit -m "feat(frontend): add ACMG/ClinGen-CNV criteria parser util

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: ACMG criteria tooltip in `InterpretationsCard.vue` (G1)

**Files:**
- Modify: `frontend/src/components/phenopacket/InterpretationsCard.vue` (template badge ~L53-61; script imports L108-118 and methods L166+; add scoped CSS before `</style>` at L558)

This card is **Options API** (`export default { props, computed, methods }`, no `<script setup>`). The per-interpretation loop alias is `interpretation` over `uniqueInterpretations`. Accessors read `interpretation.diagnosis?.genomicInterpretations?.[0]`.

- [ ] **Step 1: Add the parser import + a `getCriteria` method**

In the `<script>` import area (after line 118 `import { extractCNotation, extractPNotation } from '@/utils/hgvs';`), add:

```js
import {
  parseClassificationCriteria,
  acmgChipColor,
  cnvChipColor,
} from '@/utils/acmgCriteria';
```

In `methods`, immediately after the existing `getVariantId(interpretation) { ... }` method (ends ~line 179), add:

```js
    getCriteria(interpretation) {
      const gi = interpretation.diagnosis?.genomicInterpretations?.[0];
      const ext = gi?.variantInterpretation?.extensions?.find(
        (e) => e.name === 'classification_criteria',
      );
      const value = ext?.value || {};
      return parseClassificationCriteria(value.criteria, value.guidelines);
    },

    acmgChipColor,
    cnvChipColor,

    criteriaAriaLabel(interpretation) {
      const status = this.getStatusLabel(this.getInterpretationStatus(interpretation));
      const c = this.getCriteria(interpretation);
      const all = [...c.pathogenic, ...c.benign].map((x) =>
        x.strength ? `${x.code} ${x.strength}` : x.code,
      );
      const cnv = c.cnv.map((x) => x.section);
      const codes = [...all, ...cnv];
      return codes.length
        ? `${status} per ${c.guideline}: ${codes.join(', ')}`
        : `${status} — no classification criteria recorded`;
    },
```

- [ ] **Step 2: Wrap the badge in a tooltip**

Replace the existing badge block (lines 53-61):

```vue
            <!-- Classification badge -->
            <v-chip
              :color="getStatusColor(getInterpretationStatus(interpretation))"
              size="x-small"
              variant="flat"
              class="classification-chip"
            >
              {{ getStatusLabel(getInterpretationStatus(interpretation)) }}
            </v-chip>
```

with this tooltip-wrapped version (criteria revealed on hover, focus, AND click/tap):

```vue
            <!-- Classification badge with ACMG criteria tooltip -->
            <v-tooltip
              location="top"
              max-width="360"
              open-on-hover
              open-on-focus
              open-on-click
              :aria-label="criteriaAriaLabel(interpretation)"
            >
              <template #activator="{ props }">
                <v-chip
                  v-bind="props"
                  :color="getStatusColor(getInterpretationStatus(interpretation))"
                  size="x-small"
                  variant="flat"
                  class="classification-chip acmg-badge"
                  tabindex="0"
                  role="button"
                  :aria-label="criteriaAriaLabel(interpretation)"
                >
                  {{ getStatusLabel(getInterpretationStatus(interpretation)) }}
                </v-chip>
              </template>

              <div class="acmg-tooltip">
                <div class="acmg-tooltip-header">
                  <strong>{{ getStatusLabel(getInterpretationStatus(interpretation)) }}</strong>
                  <span class="acmg-guideline">{{ getCriteria(interpretation).guideline }}</span>
                </div>

                <!-- ACMG: grouped pathogenic / benign evidence -->
                <template
                  v-if="
                    getCriteria(interpretation).pathogenic.length ||
                    getCriteria(interpretation).benign.length
                  "
                >
                  <div
                    v-if="getCriteria(interpretation).pathogenic.length"
                    class="acmg-group"
                  >
                    <div class="acmg-group-title">Pathogenic evidence</div>
                    <div
                      v-for="c in getCriteria(interpretation).pathogenic"
                      :key="c.code"
                      class="acmg-row"
                    >
                      <v-chip :color="acmgChipColor(c)" size="x-small" variant="flat" label>
                        {{ c.code }}<template v-if="c.strength"> · {{ c.strength }}</template>
                      </v-chip>
                      <span class="acmg-desc">{{ c.label }}</span>
                    </div>
                  </div>

                  <div v-if="getCriteria(interpretation).benign.length" class="acmg-group">
                    <div class="acmg-group-title">Benign evidence</div>
                    <div
                      v-for="c in getCriteria(interpretation).benign"
                      :key="c.code"
                      class="acmg-row"
                    >
                      <v-chip :color="acmgChipColor(c)" size="x-small" variant="flat" label>
                        {{ c.code }}<template v-if="c.strength"> · {{ c.strength }}</template>
                      </v-chip>
                      <span class="acmg-desc">{{ c.label }}</span>
                    </div>
                  </div>
                </template>

                <!-- ClinGen CNV: scored sections -->
                <template v-else-if="getCriteria(interpretation).cnv.length">
                  <div class="acmg-group">
                    <div
                      v-for="c in getCriteria(interpretation).cnv"
                      :key="c.section"
                      class="acmg-row"
                    >
                      <v-chip :color="cnvChipColor(c.points)" size="x-small" variant="flat" label>
                        {{ c.section
                        }}<template v-if="c.count > 1"> ×{{ c.count }}</template
                        ><template v-if="c.points != null">
                          · {{ c.points > 0 ? '+' : '' }}{{ c.points }}</template
                        >
                      </v-chip>
                      <span class="acmg-desc">{{ c.label }}</span>
                    </div>
                    <div
                      v-if="getCriteria(interpretation).totalPoints != null"
                      class="acmg-footer"
                    >
                      Total score: {{ getCriteria(interpretation).totalPoints }}
                    </div>
                  </div>
                </template>

                <div v-else class="acmg-empty">No classification criteria recorded.</div>
              </div>
            </v-tooltip>
```

- [ ] **Step 3: Add scoped CSS for the tooltip**

Immediately before the closing `</style>` (line 558), add:

```css
.acmg-badge {
  cursor: help;
}
.acmg-tooltip {
  padding: 2px 0;
  font-size: 12px;
  line-height: 1.35;
}
.acmg-tooltip-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 6px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}
.acmg-guideline {
  font-size: 10px;
  opacity: 0.8;
}
.acmg-group {
  margin-top: 6px;
}
.acmg-group-title {
  font-size: 11px;
  font-weight: 600;
  opacity: 0.85;
  margin-bottom: 4px;
}
.acmg-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.acmg-desc {
  font-size: 11px;
}
.acmg-footer {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
  font-size: 11px;
  opacity: 0.85;
}
.acmg-empty {
  font-size: 11px;
  opacity: 0.8;
}
```

- [ ] **Step 4: Manual smoke test (dev server already running on :3000)**

Run: `npx vitest run` (ensure nothing else broke; no test targets this template yet)
Expected: PASS (existing suite green).

Then verify in the browser (Task 9 does the full Playwright pass): the "Pathogenic" badge on `/phenopackets/phenopacket-892` shows a tooltip listing `PS2 · Strong`, `PM1 · Moderate`, etc. with descriptions.

- [ ] **Step 5: Format, lint, commit**

```bash
npx prettier --write "{src,tests}/**/*.{js,jsx,vue,json,css,scss,md}"
npm run lint
git add src/components/phenopacket/InterpretationsCard.vue
git commit -m "feat(frontend): ACMG criteria tooltip on phenopacket classification badge

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: "View variant" button in `InterpretationsCard.vue` (G2)

**Files:**
- Modify: `frontend/src/components/phenopacket/InterpretationsCard.vue` (button block L63-73)

- [ ] **Step 1: Replace the bare arrow button**

Replace the existing block (lines 63-73):

```vue
            <!-- View details button -->
            <v-btn
              v-if="getVariantId(interpretation)"
              :to="`/variants/${encodeURIComponent(getVariantId(interpretation))}`"
              color="deep-purple"
              variant="text"
              size="x-small"
              icon="mdi-arrow-right"
              density="compact"
              class="ml-1"
            />
```

with a labelled, tooltip-wrapped button:

```vue
            <!-- View variant button -->
            <v-tooltip location="top" text="Open full variant details">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  v-if="getVariantId(interpretation)"
                  :to="`/variants/${encodeURIComponent(getVariantId(interpretation))}`"
                  color="deep-purple"
                  variant="tonal"
                  size="small"
                  prepend-icon="mdi-arrow-right"
                  class="ml-1"
                  aria-label="View full variant details"
                >
                  View variant
                </v-btn>
              </template>
            </v-tooltip>
```

Preserves the `v-if` guard and the `encodeURIComponent`-wrapped `:to` route.

- [ ] **Step 2: Verify suite still green**

Run: `npx vitest run`
Expected: PASS.

- [ ] **Step 3: Format, lint, commit**

```bash
npx prettier --write "{src,tests}/**/*.{js,jsx,vue,json,css,scss,md}"
npm run lint
git add src/components/phenopacket/InterpretationsCard.vue
git commit -m "feat(frontend): labelled 'View variant' button replacing bare arrow link

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `summarizePhenotypes()` in `phenotypeMatrix.js`

**Files:**
- Create: `frontend/src/utils/phenotypeMatrix.js`
- Test: `frontend/tests/unit/utils/phenotypeMatrix.spec.js`

Operates on the GA4GH phenotypic-feature shape: `{ type: { id, label }, excluded?: boolean }`.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/unit/utils/phenotypeMatrix.spec.js`:

```js
/**
 * Unit tests for phenotype summarization + matrix building.
 *
 * Tests cover: present-only counting, present/excluded split, per-individual
 * dedupe with present-wins precedence, and (in the next task) matrix grouping.
 */
import { describe, it, expect } from 'vitest';
import { summarizePhenotypes } from '@/utils/phenotypeMatrix';

const f = (id, label, excluded = false) => ({ type: { id, label }, excluded });

describe('summarizePhenotypes', () => {
  it('counts present-only and splits present vs excluded', () => {
    const s = summarizePhenotypes([
      f('HP:0000107', 'Renal cyst'),
      f('HP:0004904', 'MODY'),
      f('HP:0000365', 'Hearing impairment', true),
    ]);
    expect(s.presentCount).toBe(2);
    expect(s.present.map((p) => p.id)).toEqual(['HP:0000107', 'HP:0004904']);
    expect(s.excluded.map((p) => p.id)).toEqual(['HP:0000365']);
  });

  it('dedupes a repeated term within one individual (present wins over excluded)', () => {
    const s = summarizePhenotypes([
      f('HP:0000107', 'Renal cyst'),
      f('HP:0000107', 'Renal cyst', true),
    ]);
    expect(s.presentCount).toBe(1);
    expect(s.present).toHaveLength(1);
    expect(s.excluded).toHaveLength(0);
  });

  it('handles empty / missing input', () => {
    expect(summarizePhenotypes([]).presentCount).toBe(0);
    expect(summarizePhenotypes(undefined).present).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/unit/utils/phenotypeMatrix.spec.js`
Expected: FAIL — "Failed to resolve import '@/utils/phenotypeMatrix'".

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/utils/phenotypeMatrix.js`:

```js
/**
 * Pure helpers to summarize and matrix-ify GA4GH phenotypicFeatures across a
 * variant's affected individuals. No I/O.
 *
 * Feature shape: { type: { id: 'HP:xxxxxxx', label: '...' }, excluded?: boolean }
 */
import { getOrganSystem, getCategoryColor, ORGAN_SYSTEMS } from '@/utils/ageParser';

/**
 * Summarize one individual's features.
 * Dedupe by HPO id; if a term is both present and excluded, present wins.
 * @param {Array} features
 * @returns {{presentCount:number, present:Array<{id,label}>, excluded:Array<{id,label}>}}
 */
export function summarizePhenotypes(features) {
  const present = new Map();
  const excluded = new Map();
  for (const feat of features || []) {
    const id = feat?.type?.id;
    if (!id) continue;
    const term = { id, label: feat.type.label || id };
    if (feat.excluded) {
      if (!present.has(id)) excluded.set(id, term);
    } else {
      present.set(id, term);
      excluded.delete(id); // present wins
    }
  }
  return {
    presentCount: present.size,
    present: [...present.values()],
    excluded: [...excluded.values()],
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/unit/utils/phenotypeMatrix.spec.js`
Expected: PASS.

- [ ] **Step 5: Format, lint, commit**

```bash
npx prettier --write "{src,tests}/**/*.{js,jsx,vue,json,css,scss,md}"
npm run lint
git add src/utils/phenotypeMatrix.js tests/unit/utils/phenotypeMatrix.spec.js
git commit -m "feat(frontend): add summarizePhenotypes util (present-only count, dedupe)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `buildPhenotypeMatrix()` in `phenotypeMatrix.js`

**Files:**
- Modify: `frontend/src/utils/phenotypeMatrix.js`
- Modify: `frontend/tests/unit/utils/phenotypeMatrix.spec.js`

Input contract: `individuals: [{ phenopacketId, subjectId, features: [GA4GH feature] }]`.

- [ ] **Step 1: Add the failing test**

Append to `frontend/tests/unit/utils/phenotypeMatrix.spec.js`:

```js
import { buildPhenotypeMatrix } from '@/utils/phenotypeMatrix';

const ind = (phenopacketId, subjectId, features) => ({ phenopacketId, subjectId, features });

describe('buildPhenotypeMatrix', () => {
  const individuals = [
    ind('p-1', '56', [f('HP:0000107', 'Renal cyst'), f('HP:0004904', 'MODY')]),
    ind('p-2', '288', [f('HP:0000107', 'Renal cyst'), f('HP:0000078', 'Genital', true)]),
    ind('p-3', '399', [f('HP:0000107', 'Renal cyst')]),
  ];

  it('orders rows by descending present count', () => {
    const m = buildPhenotypeMatrix(individuals);
    expect(m.rows.map((r) => r.subjectId)).toEqual(['56', '288', '399']);
    expect(m.rows[0].presentCount).toBe(2);
  });

  it('builds columns grouped by organ system, ranked by present frequency', () => {
    const m = buildPhenotypeMatrix(individuals);
    const renalCol = m.columns.find((c) => c.id === 'HP:0000107');
    expect(renalCol.organSystem).toBe('renal');
    expect(renalCol.frequency).toBe(3); // present in all three
    expect(m.columns[0].id).toBe('HP:0000107'); // most frequent first
    // each column carries an organ-system color + label
    expect(renalCol.color).toMatch(/^#/);
    expect(renalCol.organLabel).toBe('Renal');
  });

  it('encodes cell status present/excluded/not-reported', () => {
    const m = buildPhenotypeMatrix(individuals);
    expect(m.cells['p-2']['HP:0000107']).toBe('present');
    expect(m.cells['p-2']['HP:0000078']).toBe('excluded');
    expect(m.cells['p-1']['HP:0000078']).toBe('not-reported');
  });

  it('flags present+excluded conflicts and lets present win', () => {
    const m = buildPhenotypeMatrix([
      ind('p-x', 'X', [f('HP:0000107', 'Renal cyst'), f('HP:0000107', 'Renal cyst', true)]),
    ]);
    expect(m.cells['p-x']['HP:0000107']).toBe('present');
    expect(m.conflicts.has('p-x::HP:0000107')).toBe(true);
  });

  it('caps to maxTerms by frequency and reports truncation', () => {
    const many = ind(
      'p-z',
      'Z',
      Array.from({ length: 5 }, (_, i) => f(`HP:000010${i}`, `Term ${i}`)),
    );
    const m = buildPhenotypeMatrix([many], { maxTerms: 2 });
    expect(m.columns).toHaveLength(2);
    expect(m.totalTerms).toBe(5);
    expect(m.shownTerms).toBe(2);
    expect(m.truncated).toBe(true);
  });

  it('returns an empty-but-valid structure for no phenotypes', () => {
    const m = buildPhenotypeMatrix([ind('p-0', '0', [])]);
    expect(m.columns).toEqual([]);
    expect(m.groups).toEqual([]);
    expect(m.truncated).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/unit/utils/phenotypeMatrix.spec.js`
Expected: FAIL — "buildPhenotypeMatrix is not a function".

- [ ] **Step 3: Implement `buildPhenotypeMatrix`**

Append to `frontend/src/utils/phenotypeMatrix.js`:

```js
const ORGAN_LABEL = (key) => ORGAN_SYSTEMS.find((s) => s.value === key)?.label || 'Other';
// Stable display order for organ-system groups (matches ORGAN_SYSTEMS, minus the
// never-produced 'diabetes', plus a trailing 'other').
const ORGAN_ORDER = ORGAN_SYSTEMS.map((s) => s.value).filter((v) => v !== 'diabetes');

/**
 * Build a grouped, ordered individual x phenotype matrix.
 * @param {Array<{phenopacketId:string, subjectId:string, features:Array}>} individuals
 * @param {{maxTerms?:number}} [opts]
 * @returns {{
 *   rows: Array<{phenopacketId,subjectId,presentCount}>,
 *   columns: Array<{id,label,organSystem,organLabel,color,frequency}>,
 *   groups: Array<{organSystem,label,color,startIndex,span}>,
 *   cells: Object<string,Object<string,'present'|'excluded'|'not-reported'>>,
 *   conflicts: Set<string>,
 *   totalTerms:number, shownTerms:number, truncated:boolean
 * }}
 */
export function buildPhenotypeMatrix(individuals, opts = {}) {
  const list = individuals || [];
  const conflicts = new Set();

  // Per-individual present/excluded sets (dedupe via summarizePhenotypes).
  const perRow = list.map((ind) => {
    const present = new Set();
    const excluded = new Set();
    const seenPresent = new Set();
    const seenExcluded = new Set();
    for (const feat of ind.features || []) {
      const id = feat?.type?.id;
      if (!id) continue;
      if (feat.excluded) seenExcluded.add(id);
      else seenPresent.add(id);
    }
    for (const id of seenPresent) {
      present.add(id);
      if (seenExcluded.has(id)) conflicts.add(`${ind.phenopacketId}::${id}`);
    }
    for (const id of seenExcluded) if (!seenPresent.has(id)) excluded.add(id);
    return { ind, present, excluded };
  });

  // Term metadata + present frequency across the cohort.
  const termMeta = new Map(); // id -> { id, label, organSystem, organLabel, color, frequency }
  for (const { ind, present, excluded } of perRow) {
    for (const feat of ind.features || []) {
      const id = feat?.type?.id;
      if (!id || termMeta.has(id)) continue;
      const organSystem = getOrganSystem(id);
      termMeta.set(id, {
        id,
        label: feat.type.label || id,
        organSystem,
        organLabel: ORGAN_LABEL(organSystem),
        color: getCategoryColor(organSystem),
        frequency: 0,
      });
    }
    for (const id of present) {
      const meta = termMeta.get(id);
      if (meta) meta.frequency += 1;
    }
    // ensure excluded-only terms still have meta (frequency 0)
    for (const id of excluded) {
      if (!termMeta.get(id)) continue;
    }
  }

  const totalTerms = termMeta.size;

  // Order columns: by organ-system group order, then present-frequency desc, then label.
  let columns = [...termMeta.values()].sort((a, b) => {
    const ga = ORGAN_ORDER.indexOf(a.organSystem);
    const gb = ORGAN_ORDER.indexOf(b.organSystem);
    if (ga !== gb) return ga - gb;
    if (b.frequency !== a.frequency) return b.frequency - a.frequency;
    return a.label.localeCompare(b.label);
  });

  // Cap to maxTerms by global present frequency (keep most-frequent terms).
  const maxTerms = opts.maxTerms;
  let truncated = false;
  if (typeof maxTerms === 'number' && columns.length > maxTerms) {
    const keep = new Set(
      [...columns]
        .sort((a, b) => b.frequency - a.frequency || a.label.localeCompare(b.label))
        .slice(0, maxTerms)
        .map((c) => c.id),
    );
    columns = columns.filter((c) => keep.has(c.id));
    truncated = true;
  }

  // Groups (contiguous runs of the same organ system in the ordered columns).
  const groups = [];
  columns.forEach((col, i) => {
    const last = groups[groups.length - 1];
    if (last && last.organSystem === col.organSystem) {
      last.span += 1;
    } else {
      groups.push({
        organSystem: col.organSystem,
        label: col.organLabel,
        color: col.color,
        startIndex: i,
        span: 1,
      });
    }
  });

  // Cells.
  const shownIds = new Set(columns.map((c) => c.id));
  const cells = {};
  for (const { ind, present, excluded } of perRow) {
    const row = {};
    for (const id of shownIds) {
      if (present.has(id)) row[id] = 'present';
      else if (excluded.has(id)) row[id] = 'excluded';
      else row[id] = 'not-reported';
    }
    cells[ind.phenopacketId] = row;
  }

  // Rows ordered by present count desc, subjectId tiebreak.
  const rows = perRow
    .map(({ ind, present }) => ({
      phenopacketId: ind.phenopacketId,
      subjectId: ind.subjectId,
      presentCount: present.size,
    }))
    .sort((a, b) => b.presentCount - a.presentCount || String(a.subjectId).localeCompare(String(b.subjectId)));

  return {
    rows,
    columns,
    groups,
    cells,
    conflicts,
    totalTerms,
    shownTerms: columns.length,
    truncated,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/unit/utils/phenotypeMatrix.spec.js`
Expected: PASS (all cases).

- [ ] **Step 5: Format, lint, commit**

```bash
npx prettier --write "{src,tests}/**/*.{js,jsx,vue,json,css,scss,md}"
npm run lint
git add src/utils/phenotypeMatrix.js tests/unit/utils/phenotypeMatrix.spec.js
git commit -m "feat(frontend): add buildPhenotypeMatrix (grouped, ordered, capped matrix)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Variant page — retain phenotypes, AppDataTable migration, Phenotypes column (G3)

**Files:**
- Modify: `frontend/src/views/PageVariant.vue` (imports L563-566; `components` L584-588; `data().headers` L653-671; table template L503-548; `loadVariantData` map L797-807)
- Modify: `frontend/tests/unit/views/PageVariant.spec.js`

`PageVariant.vue` is **Options API** (with a thin SEO `setup()`). Register new components via `components: {}`. Use `this.`.

- [ ] **Step 1: Write the failing test (retained phenotypes + count)**

Add to `frontend/tests/unit/views/PageVariant.spec.js`. First extend the inline `phenopacketSample` (lines 38-44) to include phenotypic features:

```js
const phenopacketSample = {
  phenopacket_id: 'PHENO-TEST-001',
  created_at: '2024-01-15T00:00:00Z',
  phenopacket: {
    subject: { id: 'SUB-001', sex: 'FEMALE' },
    phenotypicFeatures: [
      { type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: false },
      { type: { id: 'HP:0004904', label: 'MODY' } },
      { type: { id: 'HP:0000365', label: 'Hearing impairment' }, excluded: true },
    ],
  },
};
```

Then add a test inside the existing top-level `describe`:

```js
  it('retains phenotypic features and exposes a present-only phenotype count', async () => {
    const wrapper = await mountPageVariant();
    await flushPromises();
    const row = wrapper.vm.phenopacketsWithVariant[0];
    expect(row.phenotype_count).toBe(2); // excluded Hearing impairment not counted
    expect(row.phenotypic_features).toHaveLength(3);
    expect(wrapper.html()).toContain('2 phenotypes');
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/unit/views/PageVariant.spec.js`
Expected: FAIL — `row.phenotype_count` is `undefined`.

- [ ] **Step 3: Retain phenotypes + count in the row map**

In `loadVariantData()`, replace the `.map()` projection (lines 798-807):

```js
        this.phenopacketsWithVariant = phenopacketsResponse.data.map((pp) => ({
          phenopacket_id: pp.phenopacket_id,
          subject_id: pp.phenopacket?.subject?.id || 'N/A',
          subject_sex: pp.phenopacket?.subject?.sex || 'UNKNOWN_SEX',
          created_at: new Date(pp.created_at).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
          }),
        }));
```

with (adds `phenotypic_features` + `phenotype_count` via `summarizePhenotypes`):

```js
        this.phenopacketsWithVariant = phenopacketsResponse.data.map((pp) => {
          const features = pp.phenopacket?.phenotypicFeatures ?? [];
          const summary = summarizePhenotypes(features);
          return {
            phenopacket_id: pp.phenopacket_id,
            subject_id: pp.phenopacket?.subject?.id || 'N/A',
            subject_sex: pp.phenopacket?.subject?.sex || 'UNKNOWN_SEX',
            created_at: new Date(pp.created_at).toLocaleDateString('en-US', {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
            }),
            phenotypic_features: features,
            phenotype_count: summary.presentCount,
            phenotype_present: summary.present,
            phenotype_excluded: summary.excluded,
          };
        });
```

Add the import near line 575 (`import { getSexIcon, getSexChipColor, formatSex } from '@/utils/sex';`):

```js
import { summarizePhenotypes } from '@/utils/phenotypeMatrix';
```

- [ ] **Step 4: Register `AppDataTable` + migrate the table and add the column**

Add imports after line 566 (`import ProteinStructure3D from '@/components/gene/ProteinStructure3D.vue';`):

```js
import AppDataTable from '@/components/common/AppDataTable.vue';
```

Add to `components: {}` (lines 584-588):

```js
  components: {
    HNF1BGeneVisualization,
    HNF1BProteinVisualization,
    ProteinStructure3D,
    AppDataTable,
  },
```

Add the `Phenotypes` header to the `headers` array (insert between the `Sex` and `Added` entries, lines 658-670):

```js
        {
          title: 'Sex',
          value: 'subject_sex',
          sortable: true,
          width: '120px',
        },
        {
          title: 'Phenotypes',
          value: 'phenotype_count',
          sortable: true,
          width: '170px',
          align: 'start',
        },
        {
          title: 'Added',
          value: 'created_at',
          sortable: true,
          width: '150px',
        },
```

Replace the raw `<v-data-table>` element (lines 517-547) — keep the surrounding `<v-card>` and header div — with `AppDataTable` (client-side) plus the new Phenotypes cell:

```vue
            <AppDataTable
              :headers="headers"
              :items="phenopacketsWithVariant"
              :server-side="false"
              :items-per-page="10"
              density="comfortable"
              class="elevation-0"
            >
              <!-- Subject ID as clickable chip with icon -->
              <template #item.subject_id="{ item }">
                <v-chip
                  :to="`/phenopackets/${item.phenopacket_id}`"
                  color="teal-lighten-3"
                  size="small"
                  variant="flat"
                  link
                >
                  <v-icon start size="small">mdi-card-account-details</v-icon>
                  {{ item.subject_id }}
                </v-chip>
              </template>

              <!-- Sex with icon as chip -->
              <template #item.subject_sex="{ item }">
                <v-chip :color="getSexChipColor(item.subject_sex)" size="small" variant="flat">
                  <v-icon start size="small">
                    {{ getSexIcon(item.subject_sex) }}
                  </v-icon>
                  {{ formatSex(item.subject_sex) }}
                </v-chip>
              </template>

              <!-- Phenotype count chip with hover/focus/tap tooltip listing terms -->
              <template #item.phenotype_count="{ item }">
                <v-tooltip
                  location="top"
                  max-width="340"
                  open-on-hover
                  open-on-focus
                  open-on-click
                  :aria-label="`${item.phenotype_count} phenotype(s)`"
                >
                  <template #activator="{ props }">
                    <v-chip
                      v-bind="props"
                      :color="item.phenotype_count > 0 ? 'green-lighten-3' : 'grey-lighten-2'"
                      size="x-small"
                      variant="flat"
                      tabindex="0"
                      role="button"
                      class="pheno-count-chip"
                      :aria-label="`${item.phenotype_count} phenotype(s); activate for details`"
                    >
                      {{ item.phenotype_count }} phenotype{{ item.phenotype_count === 1 ? '' : 's' }}
                    </v-chip>
                  </template>

                  <div class="pheno-tooltip">
                    <div v-if="item.phenotype_present.length" class="pheno-tooltip-group">
                      <div class="pheno-tooltip-title">Present</div>
                      <div v-for="t in item.phenotype_present" :key="t.id" class="pheno-tooltip-row">
                        {{ t.label }} <span class="pheno-tooltip-id">{{ t.id }}</span>
                      </div>
                    </div>
                    <div v-if="item.phenotype_excluded.length" class="pheno-tooltip-group">
                      <div class="pheno-tooltip-title">Excluded</div>
                      <div v-for="t in item.phenotype_excluded" :key="t.id" class="pheno-tooltip-row">
                        {{ t.label }} <span class="pheno-tooltip-id">{{ t.id }}</span>
                      </div>
                    </div>
                    <div
                      v-if="!item.phenotype_present.length && !item.phenotype_excluded.length"
                      class="pheno-tooltip-row"
                    >
                      No phenotypes recorded.
                    </div>
                  </div>
                </v-tooltip>
              </template>
            </AppDataTable>
```

Add scoped CSS (inside `PageVariant.vue`'s `<style scoped>`; if none exists, add a `<style scoped>` block before the file's final closing tag):

```css
.pheno-count-chip {
  cursor: help;
}
.pheno-tooltip {
  font-size: 12px;
  line-height: 1.35;
  max-height: 260px;
  overflow-y: auto;
}
.pheno-tooltip-group {
  margin-bottom: 6px;
}
.pheno-tooltip-title {
  font-size: 11px;
  font-weight: 600;
  opacity: 0.85;
  margin-bottom: 2px;
}
.pheno-tooltip-row {
  font-size: 11px;
}
.pheno-tooltip-id {
  font-family: 'Roboto Mono', 'Consolas', 'Monaco', monospace;
  font-size: 10px;
  opacity: 0.75;
}
```

- [ ] **Step 5: Run the view test to verify green**

Run: `npx vitest run tests/unit/views/PageVariant.spec.js`
Expected: PASS (existing tests + the new phenotype test). If an existing test asserted the presence of a raw `v-data-table`, update it to assert the rendered rows/text instead (the `AppDataTable` wrapper still renders a `v-data-table` internally with `:server-side="false"`, so row content assertions hold).

- [ ] **Step 6: Format, lint, commit**

```bash
npx prettier --write "{src,tests}/**/*.{js,jsx,vue,json,css,scss,md}"
npm run lint
git add src/views/PageVariant.vue tests/unit/views/PageVariant.spec.js
git commit -m "feat(frontend): phenotype column on variant Affected Individuals (AppDataTable)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: `PhenotypeHeatmap.vue` component (G4)

**Files:**
- Create: `frontend/src/components/analyses/PhenotypeHeatmap.vue`
- Test: `frontend/tests/unit/components/analyses/PhenotypeHeatmap.spec.js`

Follows the StackedBarChart hybrid pattern: Options API with a thin `setup()` returning export/a11y refs; `renderChart` in `methods`; D3 appends an `<svg>` into `<div ref="chart" aria-hidden="true">`; `ChartExportMenu` + `useChartAccessibility`; an always-present `<details>` data table is the accessible, theme-aware, keyboard-navigable representation (with real router-links), consistent with sibling charts. Theme-awareness via Vuetify `useTheme()` for SVG text/gridlines/tooltip.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/unit/components/analyses/PhenotypeHeatmap.spec.js`:

```js
/**
 * Unit tests for PhenotypeHeatmap.
 *
 * Tests cover: it renders the accessible data-table rows/columns from the
 * matrix, shows an empty state when no phenotypes, and exposes router-links
 * for individuals.
 */
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createRouter, createWebHistory } from 'vue-router';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import PhenotypeHeatmap from '@/components/analyses/PhenotypeHeatmap.vue';

globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

function mountHeatmap(props) {
  const vuetify = createVuetify({ components, directives });
  const router = createRouter({
    history: createWebHistory(),
    routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }],
  });
  return mount(PhenotypeHeatmap, {
    props,
    global: { plugins: [router, vuetify] },
  });
}

const f = (id, label, excluded = false) => ({ type: { id, label }, excluded });

describe('PhenotypeHeatmap', () => {
  const individuals = [
    { phenopacketId: 'p-1', subjectId: '56', features: [f('HP:0000107', 'Renal cyst')] },
    { phenopacketId: 'p-2', subjectId: '288', features: [f('HP:0000107', 'Renal cyst')] },
  ];

  it('renders the accessible data table with a row per individual', () => {
    const w = mountHeatmap({ individuals, chartName: 'Phenotype heatmap' });
    const text = w.text();
    expect(text).toContain('Renal cyst');
    expect(text).toContain('56');
    expect(text).toContain('288');
  });

  it('renders an empty state when no phenotypes', () => {
    const w = mountHeatmap({
      individuals: [{ phenopacketId: 'p-0', subjectId: '0', features: [] }],
      chartName: 'Phenotype heatmap',
    });
    expect(w.text()).toContain('No phenotype data');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/unit/components/analyses/PhenotypeHeatmap.spec.js`
Expected: FAIL — cannot resolve `@/components/analyses/PhenotypeHeatmap.vue`.

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/analyses/PhenotypeHeatmap.vue`:

```vue
<template>
  <div class="phenotype-heatmap-container" v-bind="ariaProps">
    <span :id="titleId" class="sr-only">{{ chartName }}</span>
    <span :id="descId" class="sr-only">{{ description }}</span>

    <ChartExportMenu
      :svg-el="svgEl"
      :rows="exportRows"
      :columns="exportColumns"
      :chart-name="chartName"
    />

    <div v-if="matrix.columns.length === 0" class="heatmap-empty">
      No phenotype data recorded for this variant's carriers.
    </div>

    <template v-else>
      <div ref="chart" aria-hidden="true" />
      <div v-if="matrix.truncated" class="heatmap-truncation">
        Showing the {{ matrix.shownTerms }} most frequent of {{ matrix.totalTerms }} phenotypes.
        <button type="button" class="heatmap-expand" @click="showAll = !showAll">
          {{ showAll ? 'Show top phenotypes' : `Show all ${matrix.totalTerms}` }}
        </button>
      </div>

      <details class="chart-data-table">
        <summary>View data as table</summary>
        <table>
          <thead>
            <tr>
              <th>Individual</th>
              <th v-for="c in matrix.columns" :key="c.id">{{ c.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in matrix.rows" :key="r.phenopacketId">
              <td>
                <router-link :to="`/phenopackets/${r.phenopacketId}`">{{ r.subjectId }}</router-link>
              </td>
              <td v-for="c in matrix.columns" :key="c.id">
                {{ cellLabel(matrix.cells[r.phenopacketId][c.id]) }}
              </td>
            </tr>
          </tbody>
        </table>
      </details>
    </template>
  </div>
</template>

<script>
import { ref, computed } from 'vue';
import { useTheme } from 'vuetify';
import * as d3 from 'd3';
import ChartExportMenu from '@/components/analyses/ChartExportMenu.vue';
import { useChartAccessibility } from '@/composables/useChartAccessibility';
import { buildPhenotypeMatrix } from '@/utils/phenotypeMatrix';
import { TIMELINE_COLORS } from '@/utils/ageParser';

export default {
  name: 'PhenotypeHeatmap',
  components: { ChartExportMenu },
  props: {
    individuals: { type: Array, default: () => [] },
    chartName: { type: String, default: 'Phenotype heatmap' },
    maxTerms: { type: Number, default: 30 },
  },
  setup(props) {
    const theme = useTheme();
    const svgEl = ref(null);
    const showAll = ref(false);

    const matrix = computed(() =>
      buildPhenotypeMatrix(props.individuals, {
        maxTerms: showAll.value ? undefined : props.maxTerms,
      }),
    );

    const exportColumns = computed(() => [
      { key: 'individual', label: 'Individual' },
      ...matrix.value.columns.map((c) => ({ key: c.id, label: c.label })),
    ]);
    const exportRows = computed(() =>
      matrix.value.rows.map((r) => {
        const row = { individual: r.subjectId };
        for (const c of matrix.value.columns) {
          row[c.id] = matrix.value.cells[r.phenopacketId][c.id];
        }
        return row;
      }),
    );

    const summary = computed(() => {
      const m = matrix.value;
      if (!m.columns.length) return `${props.chartName}: no phenotype data.`;
      return `${props.chartName}: ${m.rows.length} individuals by ${m.shownTerms} phenotypes, colored by organ system.`;
    });

    const a11y = useChartAccessibility({ chartName: props.chartName, summary });
    const themeName = computed(() => theme.global.name.value);

    return { theme, themeName, svgEl, showAll, matrix, exportRows, exportColumns, ...a11y };
  },
  watch: {
    individuals: { handler() { this.renderChart(); }, deep: true },
    showAll() { this.renderChart(); },
    themeName() { this.renderChart(); },
  },
  mounted() {
    this.renderChart();
    window.addEventListener('resize', this.renderChart);
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.renderChart);
  },
  methods: {
    cellLabel(status) {
      if (status === 'present') return 'Present';
      if (status === 'excluded') return 'Excluded';
      return 'Not reported';
    },
    themeColor(token, fallback) {
      const c = this.theme.current.value?.colors?.[token];
      return c || fallback;
    },
    renderChart() {
      const host = this.$refs.chart;
      if (!host) return;
      d3.select(host).selectAll('*').remove();

      const m = this.matrix;
      if (!m.columns.length) return;

      const onSurface = this.themeColor('on-surface', '#1d1b20');
      const surface = this.themeColor('surface', '#ffffff');

      const cell = 26;
      const labelW = 90;
      const headerH = 150;
      const groupBandH = 8;
      const width = labelW + m.columns.length * cell + 12;
      const height = headerH + m.rows.length * cell + 24;

      const svgRoot = d3
        .select(host)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');
      this.svgEl = svgRoot.node();

      const g = svgRoot.append('g').attr('transform', `translate(${labelW},${headerH})`);

      // Tooltip (theme-aware) anchored to the container.
      const tooltip = d3
        .select(host)
        .append('div')
        .attr('class', 'heatmap-tooltip')
        .style('opacity', 0)
        .style('position', 'absolute')
        .style('background-color', surface)
        .style('color', onSurface)
        .style('border', `1px solid ${onSurface}33`)
        .style('padding', '8px')
        .style('border-radius', '5px')
        .style('pointer-events', 'none')
        .style('z-index', '1000')
        .style('font-size', '12px')
        .style('box-shadow', '0 2px 6px rgba(0,0,0,0.25)');

      // Organ-system group bands + labels (above the column labels).
      m.groups.forEach((grp) => {
        g.append('rect')
          .attr('x', grp.startIndex * cell)
          .attr('y', -headerH)
          .attr('width', grp.span * cell)
          .attr('height', groupBandH)
          .attr('fill', grp.color)
          .attr('rx', 2);
        g.append('text')
          .attr('x', grp.startIndex * cell + (grp.span * cell) / 2)
          .attr('y', -headerH - 4)
          .attr('text-anchor', 'middle')
          .attr('font-size', '10px')
          .attr('fill', onSurface)
          .text(grp.label);
      });

      // Column (term) labels, rotated.
      m.columns.forEach((col, ci) => {
        g.append('text')
          .attr('transform', `translate(${ci * cell + cell / 2}, ${-groupBandH - 6}) rotate(-55)`)
          .attr('text-anchor', 'start')
          .attr('font-size', '10px')
          .attr('fill', onSurface)
          .text(col.label.length > 22 ? `${col.label.slice(0, 21)}…` : col.label)
          .append('title')
          .text(`${col.label} (${col.id})`);
      });

      // Row (individual) labels — clickable (SPA navigation).
      m.rows.forEach((row, ri) => {
        const t = g
          .append('text')
          .attr('x', -8)
          .attr('y', ri * cell + cell / 2 + 4)
          .attr('text-anchor', 'end')
          .attr('font-size', '11px')
          .attr('fill', onSurface)
          .style('cursor', 'pointer')
          .text(row.subjectId)
          .on('click', () => this.$router.push(`/phenopackets/${row.phenopacketId}`));
        t.append('title').text('View individual');
      });

      // Cells.
      const statusFill = (status, color) => {
        if (status === 'present') return color;
        if (status === 'excluded') return TIMELINE_COLORS.excluded;
        return 'transparent';
      };

      m.rows.forEach((row, ri) => {
        m.columns.forEach((col, ci) => {
          const status = m.cells[row.phenopacketId][col.id];
          const conflict = m.conflicts.has(`${row.phenopacketId}::${col.id}`);
          g.append('rect')
            .attr('x', ci * cell + 2)
            .attr('y', ri * cell + 2)
            .attr('width', cell - 4)
            .attr('height', cell - 4)
            .attr('rx', 3)
            .attr('fill', statusFill(status, col.color))
            .attr('stroke', `${onSurface}22`)
            .attr('stroke-width', status === 'not-reported' ? 0.5 : 1)
            .style('cursor', 'default')
            .on('mouseover', function (event) {
              d3.select(this).attr('stroke', onSurface).attr('stroke-width', 1.5);
              const label = status === 'present' ? 'Present' : status === 'excluded' ? 'Excluded' : 'Not reported';
              tooltip
                .html(
                  `<strong>${row.subjectId}</strong><br>${col.label} <em>(${col.id})</em><br>${col.organLabel} · ${label}` +
                    (conflict ? '<br><em>also reported excluded</em>' : ''),
                )
                .transition()
                .duration(150)
                .style('opacity', 1);
            })
            .on('mousemove', (event) => {
              const rect = host.getBoundingClientRect();
              tooltip
                .style('left', `${event.clientX - rect.left + 12}px`)
                .style('top', `${event.clientY - rect.top - 10}px`);
            })
            .on('mouseleave', function () {
              d3.select(this)
                .attr('stroke', `${onSurface}22`)
                .attr('stroke-width', status === 'not-reported' ? 0.5 : 1);
              tooltip.transition().duration(150).style('opacity', 0);
            });
        });
      });
    },
  },
};
</script>

<style scoped>
.phenotype-heatmap-container {
  max-width: 100%;
  width: 100%;
  margin: auto;
  position: relative;
  overflow-x: auto;
}
.heatmap-empty {
  padding: 32px;
  text-align: center;
  color: rgb(var(--v-theme-on-surface), 0.6);
}
.heatmap-truncation {
  margin-top: 8px;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface), 0.7);
}
.heatmap-expand {
  background: none;
  border: none;
  color: rgb(var(--v-theme-primary));
  cursor: pointer;
  text-decoration: underline;
  font-size: 12px;
}
.chart-data-table {
  margin-top: 16px;
  font-size: 13px;
}
.chart-data-table summary {
  cursor: pointer;
  padding: 4px 0;
  color: rgb(var(--v-theme-on-surface), 0.7);
}
.chart-data-table table {
  border-collapse: collapse;
  margin-top: 8px;
}
.chart-data-table th,
.chart-data-table td {
  padding: 4px 8px;
  border: 1px solid rgb(var(--v-theme-on-surface), 0.12);
  text-align: left;
  white-space: nowrap;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/unit/components/analyses/PhenotypeHeatmap.spec.js`
Expected: PASS (data table renders rows/cols; empty state shows). The D3 SVG render is `aria-hidden` and not asserted; the `<details>` table provides the asserted content.

- [ ] **Step 5: Format, lint, commit**

```bash
npx prettier --write "{src,tests}/**/*.{js,jsx,vue,json,css,scss,md}"
npm run lint
git add src/components/analyses/PhenotypeHeatmap.vue tests/unit/components/analyses/PhenotypeHeatmap.spec.js
git commit -m "feat(frontend): add organ-system PhenotypeHeatmap chart component

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Wire `PhenotypeHeatmap` into the variant page (G4)

**Files:**
- Modify: `frontend/src/views/PageVariant.vue` (imports/components; template below the Affected-Individuals `<v-card>` ~L548)

- [ ] **Step 1: Import + register the component**

Add import after the `AppDataTable` import (Task 6):

```js
import PhenotypeHeatmap from '@/components/analyses/PhenotypeHeatmap.vue';
```

Add to `components: {}`:

```js
    AppDataTable,
    PhenotypeHeatmap,
```

- [ ] **Step 2: Add a "Phenotype Profile" card after the Affected-Individuals card**

Immediately after the closing `</v-card>` of the Affected-Individuals card (after line 548), add:

```vue
          <!-- PHENOTYPE PROFILE HEATMAP -->
          <v-card
            v-if="phenopacketsWithVariant.length > 0"
            variant="outlined"
            class="border-opacity-12 mt-4"
            rounded="lg"
          >
            <div class="d-flex align-center px-4 py-2 bg-grey-lighten-4 border-bottom">
              <v-icon color="purple-darken-2" class="mr-2">mdi-grid</v-icon>
              <span class="text-h6 font-weight-medium">Phenotype Profile</span>
            </div>
            <div class="pa-4">
              <PhenotypeHeatmap
                :individuals="heatmapIndividuals"
                chart-name="Phenotype profile across affected individuals"
              />
            </div>
          </v-card>
```

- [ ] **Step 3: Add the `heatmapIndividuals` computed**

In `computed: {}` of `PageVariant.vue`, add:

```js
    heatmapIndividuals() {
      return this.phenopacketsWithVariant.map((row) => ({
        phenopacketId: row.phenopacket_id,
        subjectId: row.subject_id,
        features: row.phenotypic_features || [],
      }));
    },
```

- [ ] **Step 4: Add a wiring test**

Add to `frontend/tests/unit/views/PageVariant.spec.js`:

```js
  it('renders the phenotype heatmap fed by retained features', async () => {
    const wrapper = await mountPageVariant();
    await flushPromises();
    expect(wrapper.findComponent({ name: 'PhenotypeHeatmap' }).exists()).toBe(true);
    expect(wrapper.vm.heatmapIndividuals[0].features).toHaveLength(3);
  });
```

Run: `npx vitest run tests/unit/views/PageVariant.spec.js`
Expected: PASS.

> Note: `PhenotypeHeatmap` pulls in D3. If the existing PageVariant spec's intent is to avoid heavy children, this is acceptable here because the heatmap renders into an `aria-hidden` div and its `<details>` table is lightweight; D3 import is fine under happy-dom (the existing chartExport util test already imports chart code). If mount becomes slow/flaky, stub it with `vi.mock('@/components/analyses/PhenotypeHeatmap.vue', () => ({ default: { name: 'PhenotypeHeatmap', template: '<div class=\"mock-heatmap\" />' } }))` and drop the `features` length assertion.

- [ ] **Step 5: Format, lint, commit**

```bash
npx prettier --write "{src,tests}/**/*.{js,jsx,vue,json,css,scss,md}"
npm run lint
git add src/views/PageVariant.vue tests/unit/views/PageVariant.spec.js
git commit -m "feat(frontend): wire PhenotypeHeatmap into variant page

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Full gate + Playwright verification

**Files:** none (verification only).

- [ ] **Step 1: Full unit suite**

Run: `npx vitest run`
Expected: PASS (entire frontend suite, including the 3 new specs).

- [ ] **Step 2: Lint + format check (CI-equivalent)**

```bash
npm run lint
npx prettier --check "{src,tests}/**/*.{js,jsx,vue,json,css,scss,md}"
```
Expected: lint clean; prettier reports all matched files formatted.

- [ ] **Step 3: Production build**

Run: `npm run build`
Expected: build succeeds with no errors.

- [ ] **Step 4: Playwright manual verification (dev stack already on :3000)**

Verify, in BOTH light and dark theme (toggle in the app bar):

1. `http://localhost:3000/phenopackets/phenopacket-892`
   - Hover the "Pathogenic" badge → tooltip lists `PS2 · Strong`, `PM1 · Moderate`, `PM2 · Supporting`, `PM5 · Moderate`, `PP2 · Supporting`, `PP3 · Supporting` with plain-English descriptions, grouped under "Pathogenic evidence".
   - Tab to the badge with the keyboard → tooltip opens on focus. Tap/click → tooltip opens.
   - The "View variant" button is clearly labelled and navigates to the variant page.
2. `http://localhost:3000/variants/ga4gh:VA.PuNUJ-j-dgkKwAF2ZRDuY1usqx5VyJYG`
   - Affected Individuals table shows a "Phenotypes" column with count chips; hovering/focusing/tapping a chip lists the terms (and any "Excluded" group).
   - The "Phenotype Profile" heatmap renders below the table, columns grouped/colored by organ system; hovering a cell shows the HPO id + organ system + status; the organ-system color bands are visible; row labels navigate to the individual; the export menu (download icon) is enabled and "View data as table" expands an accessible matrix with working individual links.
   - Both views are legible in dark mode (heatmap text/gridlines/tooltip adapt).

- [ ] **Step 5: Push the branch and open a PR**

```bash
git push -u origin feat/pheno-variant-ui-improvements
gh pr create --fill --base main
```

Then verify CI is green (`gh pr checks`), investigating and fixing any failure until the "CI gate" check passes.

---

## Self-review (completed by plan author)

**Spec coverage:**
- G1 ACMG tooltip → Tasks 1 (parser) + 2 (render). ✅ (verdict source = `genomicInterpretations[0].interpretationStatus`, criteria from same `[0]`, per spec §G1.)
- G2 View-variant button → Task 3. ✅
- G3 Phenotypes column + AppDataTable migration → Tasks 4 (summarize) + 6. ✅ (present-only count; excluded grouped in tooltip; hover+focus+tap.)
- G4 heatmap → Tasks 5 (matrix) + 7 (component) + 8 (wire-in). ✅ (organ-system grouping/colors; dedupe present-wins; conflict flag; top-N cap + expand; export-full-matrix via `<details>`/ChartExportMenu; theme-aware via `useTheme`; accessible data table with router-links.)
- Testing/CI gate → Task 9, and per-task gates. ✅ (CI-equivalent prettier `{src,tests}` glob + build.)

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✅

**Type/name consistency:** `parseClassificationCriteria`, `acmgChipColor`, `cnvChipColor`, `ACMG_CRITERIA` (Task 1) match their imports in Task 2. `summarizePhenotypes` (Task 4) matches use in Task 6. `buildPhenotypeMatrix` return shape (`rows/columns/groups/cells/conflicts/totalTerms/shownTerms/truncated`, Task 5) matches consumption in Task 7. Row fields `phenotypic_features`/`phenotype_count`/`phenotype_present`/`phenotype_excluded` (Task 6) match `heatmapIndividuals` + tooltip use (Tasks 6, 8). `AppDataTable` requires `:server-side="false"` (Task 6) — accounted for. ✅

**Known soft spots (acceptable, called out):** the `<details>` accessible table — rather than focusable SVG cells — is the keyboard/AT path (matches every sibling chart; SVG is `aria-hidden`); `sr-only` is defined locally in the heatmap to avoid depending on an unverified global; ClinGen-CNV descriptions are a starter map (spec §8 risk).
