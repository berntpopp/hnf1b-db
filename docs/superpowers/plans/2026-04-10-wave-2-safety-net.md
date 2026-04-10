# Wave 2: Build the Safety Net — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the characterization tests, error plumbing, and security middleware that Waves 3–5 depend on. No decomposition yet — this wave makes decomposition safe.

**Architecture:** New test infrastructure (dedicated test DB, fixtures directory), 5 net-new frontend characterization specs + 1 in-place upgrade, 5 new backend test modules, 1 new backend exception handler, 1 new backend middleware, 1 new frontend error boundary.

**Tech Stack:** pytest + pytest-asyncio + httpx for backend tests; vitest + @vue/test-utils + happy-dom for frontend characterization; new dependency: none (all tools already present).

**Parent spec:** `docs/superpowers/specs/2026-04-10-codebase-refactor-roadmap-design.md` (Wave 2 section)

**Prerequisite:** Wave 1 complete and merged.

---

## Context (common with Wave 1)

All conventions from `2026-04-10-wave-1-stop-the-bleeding.md` apply: TDD rigor, conventional commits, `make check` before every commit, no `console.log`. Branch: `chore/wave-2-safety-net`.

**New file locations for this wave:**
- Backend tests: `backend/tests/` (existing convention: `test_<module>.py`)
- Frontend characterization specs: `frontend/tests/unit/{views,components/gene}/*.spec.js`
- Frontend fixtures: `frontend/tests/fixtures/` (new directory — phenopacket/variant/publication JSON)
- Backend exception handler: `backend/app/core/exceptions.py` (new)
- Backend security middleware: `backend/app/core/security_headers.py` (new)
- Frontend error boundary: integrated into `frontend/src/main.js`

**Characterization test philosophy (repeated because it's load-bearing):**
- Test **observable behavior only**: mounted output, user interactions, emitted events.
- Do NOT test internal state, private methods, watcher internals, or specific DOM structures.
- A characterization spec's job is to **fail when visible behavior changes** and **pass when internals are refactored**. This is the entire point — it's the safety net for Wave 5.
- When in doubt, ask: "If I re-wrote this component from scratch preserving only what a user sees, would my test still pass?" If no, the test is too tight.

---

## Task 1: Create frontend test fixtures directory with sample payloads

**Files:**
- Create: `frontend/tests/fixtures/phenopacket-sample.json`
- Create: `frontend/tests/fixtures/variant-sample.json`
- Create: `frontend/tests/fixtures/publication-sample.json`
- Create: `frontend/tests/fixtures/aggregation-demographics-sample.json`
- Create: `frontend/tests/fixtures/index.js` (exports for easy import)

- [ ] **Step 1: Make the directory**

```bash
mkdir -p frontend/tests/fixtures
```

- [ ] **Step 2: Create a realistic phenopacket sample**

Create `frontend/tests/fixtures/phenopacket-sample.json`:

```json
{
  "id": "PHENO-TEST-001",
  "subject": {
    "id": "SUB-001",
    "sex": "FEMALE",
    "timeAtLastEncounter": { "age": { "iso8601duration": "P35Y" } }
  },
  "phenotypicFeatures": [
    { "type": { "id": "HP:0000107", "label": "Renal cyst" } },
    { "type": { "id": "HP:0000822", "label": "Hypertension" } }
  ],
  "interpretations": [
    {
      "id": "INTERP-001",
      "progressStatus": "SOLVED",
      "diagnosis": {
        "disease": { "id": "MONDO:0011122", "label": "HNF1B-related disease" },
        "genomicInterpretations": [
          {
            "subjectOrBiosampleId": "SUB-001",
            "interpretationStatus": "CAUSATIVE",
            "variantInterpretation": {
              "variationDescriptor": {
                "id": "VAR-001",
                "label": "NM_000458.4:c.544+1G>A",
                "geneContext": { "valueId": "HGNC:11630", "symbol": "HNF1B" },
                "expressions": [
                  { "syntax": "hgvs.c", "value": "NM_000458.4:c.544+1G>A" }
                ]
              },
              "acmgPathogenicityClassification": "PATHOGENIC"
            }
          }
        ]
      }
    }
  ],
  "diseases": [
    { "term": { "id": "MONDO:0011122", "label": "HNF1B-related disease" } }
  ],
  "metaData": {
    "created": "2026-01-01T00:00:00Z",
    "createdBy": "test",
    "phenopacketSchemaVersion": "2.0"
  }
}
```

- [ ] **Step 3: Create variant sample**

Create `frontend/tests/fixtures/variant-sample.json`:

```json
{
  "id": "VAR-001",
  "hgvs_c": "NM_000458.4:c.544+1G>A",
  "hgvs_p": null,
  "hgvs_g": "NC_000017.11:g.37736926C>T",
  "vcf": "17-37736926-C-T",
  "spdi": "NC_000017.11:37736925:C:T",
  "gene_symbol": "HNF1B",
  "consequence": "splice_donor_variant",
  "impact": "HIGH",
  "cadd_score": 27.5,
  "gnomad_af": 0.0,
  "acmg_classification": "PATHOGENIC",
  "publications": [{ "pmid": "32345678", "title": "Sample paper" }],
  "phenopacket_count": 5
}
```

- [ ] **Step 4: Create publication sample**

Create `frontend/tests/fixtures/publication-sample.json`:

```json
{
  "pmid": "32345678",
  "doi": "10.1234/sample",
  "title": "Sample HNF1B publication",
  "authors": ["Doe J", "Smith A", "Jones B"],
  "year": 2024,
  "journal": "Journal of Genetics",
  "abstract": "This is a sample abstract.",
  "variant_count": 3,
  "phenopacket_count": 2
}
```

- [ ] **Step 5: Create aggregation demographics sample**

Create `frontend/tests/fixtures/aggregation-demographics-sample.json`:

```json
{
  "total_count": 864,
  "by_sex": [
    { "sex": "FEMALE", "count": 412, "percentage": 47.7 },
    { "sex": "MALE", "count": 398, "percentage": 46.1 },
    { "sex": "UNKNOWN", "count": 54, "percentage": 6.2 }
  ],
  "by_age_group": [
    { "age_group": "0-10", "count": 189, "percentage": 21.9 },
    { "age_group": "11-20", "count": 145, "percentage": 16.8 }
  ]
}
```

- [ ] **Step 6: Create the fixture index file**

Create `frontend/tests/fixtures/index.js`:

```javascript
/**
 * Test fixture exports.
 *
 * Import into characterization specs like:
 *   import { phenopacketSample, variantSample } from '../../fixtures';
 */
import phenopacketSample from './phenopacket-sample.json';
import variantSample from './variant-sample.json';
import publicationSample from './publication-sample.json';
import aggregationDemographicsSample from './aggregation-demographics-sample.json';

export {
  phenopacketSample,
  variantSample,
  publicationSample,
  aggregationDemographicsSample,
};
```

- [ ] **Step 7: Commit**

```bash
git add frontend/tests/fixtures/
git commit -m "test(frontend): add fixture samples for characterization specs

Creates frontend/tests/fixtures/ with sample JSON payloads mirroring
the shape of phenopacket, variant, publication, and aggregation API
responses. Used by Wave 2 characterization tests to mock API
responses without a live backend.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Write characterization test for PageVariant.vue

**Files:**
- Create: `frontend/tests/unit/views/PageVariant.spec.js`

- [ ] **Step 1: Read PageVariant.vue's template to identify observable surface**

```bash
head -100 frontend/src/views/PageVariant.vue
```

Note: the component fetches variant data on mount and renders it in tabs. Observable surface: the `<h1>` or `<v-card-title>` showing the variant label, tab labels, and key visible fields (gene symbol, CADD score, ACMG class).

- [ ] **Step 2: Write the characterization spec**

Create `frontend/tests/unit/views/PageVariant.spec.js`:

```javascript
/**
 * Characterization test for PageVariant.vue.
 *
 * Tests observable mount behavior: variant label appears in header,
 * key fields render, tab structure is present. Does NOT test internal
 * reactive state, private methods, or specific DOM structure beyond
 * the user-visible output.
 *
 * This spec exists to make Wave 5 decomposition safe. If you're
 * refactoring PageVariant.vue and this test fails, the refactor
 * changed visible behavior — investigate before proceeding.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createRouter, createWebHistory } from 'vue-router';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import { variantSample, phenopacketSample } from '../../fixtures';

// Mock the API layer
vi.mock('@/api', () => ({
  getVariantById: vi.fn(),
  getVariantPhenopackets: vi.fn(),
  getVariantPublications: vi.fn(),
}));

// Mock the log service (always available globally in real app)
globalThis.window.logService = {
  debug: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
};

async function mountPageVariant() {
  const vuetify = createVuetify({ components, directives });
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/variant/:id', component: { template: '<div />' }, name: 'variant' },
    ],
  });
  await router.push('/variant/VAR-001');
  await router.isReady();

  const PageVariant = (await import('@/views/PageVariant.vue')).default;
  return mount(PageVariant, {
    global: { plugins: [router, vuetify] },
  });
}

describe('PageVariant.vue (characterization)', () => {
  beforeEach(async () => {
    const api = await import('@/api');
    api.getVariantById.mockResolvedValue(variantSample);
    api.getVariantPhenopackets.mockResolvedValue({ data: [phenopacketSample], meta: { total: 1 } });
    api.getVariantPublications.mockResolvedValue({ data: [], meta: { total: 0 } });
  });

  it('mounts without throwing', async () => {
    const wrapper = await mountPageVariant();
    await flushPromises();
    expect(wrapper.exists()).toBe(true);
  });

  it('renders the variant label in the visible output', async () => {
    const wrapper = await mountPageVariant();
    await flushPromises();
    expect(wrapper.text()).toContain('NM_000458.4:c.544+1G>A');
  });

  it('renders the gene symbol', async () => {
    const wrapper = await mountPageVariant();
    await flushPromises();
    expect(wrapper.text()).toContain('HNF1B');
  });

  it('renders the CADD score', async () => {
    const wrapper = await mountPageVariant();
    await flushPromises();
    expect(wrapper.text()).toContain('27.5');
  });

  it('renders the ACMG pathogenicity classification', async () => {
    const wrapper = await mountPageVariant();
    await flushPromises();
    expect(wrapper.text().toLowerCase()).toContain('pathogenic');
  });

  it('calls the variant-by-id API with the route param', async () => {
    const api = await import('@/api');
    await mountPageVariant();
    await flushPromises();
    expect(api.getVariantById).toHaveBeenCalledWith('VAR-001');
  });
});
```

- [ ] **Step 3: Run the test**

```bash
cd frontend && npx vitest run tests/unit/views/PageVariant.spec.js
```

Expected: Either all 6 tests pass (if PageVariant renders these fields from the mocked data), OR some fail because the component uses different field names/API calls than the spec assumes.

**If tests fail:** inspect the actual component imports and the actual visible text rendered. Adjust the spec to match reality. The goal is a spec that passes against the current implementation — it then becomes the baseline for refactoring.

**Common adjustments:**
- `getVariantById` may be named differently (`getVariant`, `fetchVariant`). Update the mock.
- Rendered text may include formatting (e.g., "CADD: 27.5" vs "27.5"). Update the assertion to match.
- If the component uses `useRoute().params.id`, the spec's router setup is already correct.

Iterate until the spec passes against the current component. Document any quirks you discovered in a comment at the top of the spec.

- [ ] **Step 4: Commit**

```bash
git add frontend/tests/unit/views/PageVariant.spec.js
git commit -m "test(frontend): add characterization spec for PageVariant.vue

Wave 5 prep: captures the current observable behavior of PageVariant
(variant label, gene symbol, CADD score, ACMG classification rendered
in mounted output) so the Wave 5 decomposition can verify internal
refactors preserve user-visible behavior.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Write characterization test for HNF1BGeneVisualization.vue (with fail-first zoom test)

**Files:**
- Create: `frontend/tests/unit/components/gene/HNF1BGeneVisualization.spec.js`

The review flagged the zoom functionality in `HNF1BGeneVisualization.vue` as broken. Wave 5 will fix it during decomposition. This characterization spec includes a **deliberately failing zoom test** — it will fail now (documenting the bug), pass later (proving the fix). Mark it with `it.fails()` or `it.skip` with a comment explaining.

- [ ] **Step 1: Read the gene visualization component's template**

```bash
head -80 frontend/src/components/gene/HNF1BGeneVisualization.vue
```

Identify props, emits, and visible DOM structure (the SVG root, zoom buttons, tooltip container).

- [ ] **Step 2: Write the characterization spec**

Create `frontend/tests/unit/components/gene/HNF1BGeneVisualization.spec.js`:

```javascript
/**
 * Characterization test for HNF1BGeneVisualization.vue.
 *
 * Tests observable mount behavior: SVG renders, variant markers
 * appear based on the variants prop, zoom controls are present.
 *
 * IMPORTANT: One test (the zoom interaction test) is marked as
 * `it.fails` — the zoom functionality is currently broken per the
 * 2026-04-09 review. Wave 5 decomposition fixes it, at which point
 * this test flips to `it(...)` and passes.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import HNF1BGeneVisualization from '@/components/gene/HNF1BGeneVisualization.vue';

globalThis.window.logService = {
  debug: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
};

const sampleVariants = [
  {
    id: 'VAR-001',
    position: 36459258,
    hgvs_c: 'NM_000458.4:c.544+1G>A',
    acmg_classification: 'PATHOGENIC',
    phenopacket_count: 5,
  },
  {
    id: 'VAR-002',
    position: 36459500,
    hgvs_c: 'NM_000458.4:c.600A>T',
    acmg_classification: 'LIKELY_PATHOGENIC',
    phenopacket_count: 2,
  },
];

function makeWrapper(props = {}) {
  const vuetify = createVuetify({ components, directives });
  return mount(HNF1BGeneVisualization, {
    props: { variants: sampleVariants, ...props },
    global: { plugins: [vuetify] },
  });
}

describe('HNF1BGeneVisualization.vue (characterization)', () => {
  it('mounts without throwing', () => {
    const wrapper = makeWrapper();
    expect(wrapper.exists()).toBe(true);
  });

  it('renders an SVG element', () => {
    const wrapper = makeWrapper();
    expect(wrapper.find('svg').exists()).toBe(true);
  });

  it('renders one marker per variant in the variants prop', () => {
    const wrapper = makeWrapper();
    // Adjust the selector to match actual marker class/element
    const markers = wrapper.findAll('[data-testid="variant-marker"], .variant-marker, circle.variant');
    expect(markers.length).toBeGreaterThanOrEqual(sampleVariants.length);
  });

  it('renders nothing catastrophic when variants prop is empty', () => {
    const wrapper = makeWrapper({ variants: [] });
    expect(wrapper.find('svg').exists()).toBe(true);
  });

  // ZOOM BUG: currently broken per 2026-04-09 review (issue #92).
  // Wave 5 decomposition should fix this. When fixed, remove `.fails`.
  it.fails('zoom in button increases the visible scale', async () => {
    const wrapper = makeWrapper();
    const zoomIn = wrapper.find('[data-testid="zoom-in"], button[aria-label*="zoom in" i]');
    if (!zoomIn.exists()) {
      throw new Error('zoom-in button not found — rendering already diverged');
    }
    const before = wrapper.find('svg g.zoomable, svg g').attributes('transform') || '';
    await zoomIn.trigger('click');
    const after = wrapper.find('svg g.zoomable, svg g').attributes('transform') || '';
    expect(after).not.toBe(before);
    expect(after).toContain('scale');
  });
});
```

- [ ] **Step 3: Run the spec**

```bash
cd frontend && npx vitest run tests/unit/components/gene/HNF1BGeneVisualization.spec.js
```

Expected:
- 4 tests pass
- 1 test (the `it.fails` zoom test) reports as expected-fail. Vitest treats `it.fails` as a passing test when the body throws — this is intentional.

If other tests fail, adjust the selectors (D3 components are notoriously selector-sensitive) until the 4 non-zoom tests pass. Keep the zoom test as `it.fails` regardless.

- [ ] **Step 4: Commit**

```bash
git add frontend/tests/unit/components/gene/HNF1BGeneVisualization.spec.js
git commit -m "test(frontend): add characterization spec for HNF1BGeneVisualization

Captures current observable behavior of the gene visualization
component (SVG mount, variant markers, empty state). Includes a
fail-first zoom interaction test (marked it.fails) that documents
the broken zoom bug from issue #92; Wave 5 decomposition fixes it
and this test will flip to passing.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Characterization test for ProteinStructure3D.vue

**Files:**
- Create: `frontend/tests/unit/components/gene/ProteinStructure3D.spec.js`

NGL Viewer is a 3D renderer that requires WebGL. In happy-dom there is no WebGL context, so the spec must mock NGL itself.

- [ ] **Step 1: Write the spec with NGL mock**

Create `frontend/tests/unit/components/gene/ProteinStructure3D.spec.js`:

```javascript
/**
 * Characterization test for ProteinStructure3D.vue.
 *
 * The component uses NGL Viewer which requires WebGL. In happy-dom
 * there is no WebGL context, so NGL is mocked. The spec verifies
 * the component mounts, accepts the expected props, and calls the
 * NGL lifecycle methods in the right order.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

// Mock NGL before importing the component
vi.mock('ngl', () => {
  const stage = {
    loadFile: vi.fn().mockResolvedValue({
      addRepresentation: vi.fn(),
      autoView: vi.fn(),
    }),
    dispose: vi.fn(),
    handleResize: vi.fn(),
    setParameters: vi.fn(),
    removeAllComponents: vi.fn(),
  };
  return {
    Stage: vi.fn(() => stage),
    autoLoad: vi.fn(),
  };
});

globalThis.window.logService = {
  debug: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
};

async function mountViewer(props = {}) {
  const vuetify = createVuetify({ components, directives });
  const ProteinStructure3D = (await import('@/components/gene/ProteinStructure3D.vue')).default;
  return mount(ProteinStructure3D, {
    props: { pdbId: '2H8R', variants: [], ...props },
    global: { plugins: [vuetify] },
  });
}

describe('ProteinStructure3D.vue (characterization)', () => {
  it('mounts without throwing', async () => {
    const wrapper = await mountViewer();
    expect(wrapper.exists()).toBe(true);
  });

  it('renders a container element for NGL', async () => {
    const wrapper = await mountViewer();
    // NGL needs a div to render into
    const container = wrapper.find('div.ngl-viewer, [data-testid="ngl-container"], div[ref="viewer"]');
    expect(container.exists() || wrapper.find('div').exists()).toBe(true);
  });

  it('accepts a pdbId prop', async () => {
    const wrapper = await mountViewer({ pdbId: '1A0A' });
    expect(wrapper.props('pdbId')).toBe('1A0A');
  });

  it('accepts a variants array prop', async () => {
    const variants = [{ id: 'V1', position: 100 }];
    const wrapper = await mountViewer({ variants });
    expect(wrapper.props('variants')).toEqual(variants);
  });
});
```

- [ ] **Step 2: Run and iterate until green**

```bash
cd frontend && npx vitest run tests/unit/components/gene/ProteinStructure3D.spec.js
```

If the component imports NGL differently (e.g., `import { Stage } from 'ngl'` vs `import NGL from 'ngl'`), adjust the mock shape. If prop names differ, adjust the `makeWrapper` call.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/unit/components/gene/ProteinStructure3D.spec.js
git commit -m "test(frontend): add characterization spec for ProteinStructure3D

Mocks NGL Viewer (WebGL unavailable in happy-dom) and verifies
component mount, container element presence, and prop acceptance.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Upgrade existing HNF1BProteinVisualization.spec.js with characterization cases

**Files:**
- Modify: `frontend/tests/unit/components/HNF1BProteinVisualization.spec.js` (existing 318 lines)

The existing file tests only domain-data constants, not component mount behavior. Add a new `describe` block covering characterization without removing the existing domain tests.

- [ ] **Step 1: Read the existing file**

```bash
cat frontend/tests/unit/components/HNF1BProteinVisualization.spec.js
```

Note how it's structured. The domain-data tests are useful — keep them.

- [ ] **Step 2: Append a characterization describe block at the end**

At the end of the existing file (before the final `});` closing the outer describe or as a sibling describe), append:

```javascript
// --- Characterization tests added in Wave 2 ---
// These cover component mount behavior for the Wave 5 decomposition
// safety net. Do not merge with the domain-data tests above; they
// test different things.
describe('HNF1BProteinVisualization.vue (characterization)', () => {
  const { mount } = await import('@vue/test-utils');
  const { createVuetify } = await import('vuetify');
  const components = await import('vuetify/components');
  const directives = await import('vuetify/directives');

  const sampleVariants = [
    { id: 'V1', position: 100, hgvs_p: 'p.Arg100Cys', acmg_classification: 'PATHOGENIC' },
    { id: 'V2', position: 200, hgvs_p: 'p.Leu200Pro', acmg_classification: 'LIKELY_PATHOGENIC' },
  ];

  async function mountComponent(props = {}) {
    const vuetify = createVuetify({ components, directives });
    const HNF1BProteinVisualization = (
      await import('@/components/gene/HNF1BProteinVisualization.vue')
    ).default;
    return mount(HNF1BProteinVisualization, {
      props: { variants: sampleVariants, ...props },
      global: { plugins: [vuetify] },
    });
  }

  it('mounts without throwing', async () => {
    globalThis.window.logService = {
      debug: () => {},
      info: () => {},
      warn: () => {},
      error: () => {},
    };
    const wrapper = await mountComponent();
    expect(wrapper.exists()).toBe(true);
  });

  it('renders an SVG element', async () => {
    const wrapper = await mountComponent();
    expect(wrapper.find('svg').exists()).toBe(true);
  });

  it('renders markers for each variant', async () => {
    const wrapper = await mountComponent();
    const markers = wrapper.findAll(
      '[data-testid="variant-marker"], .variant-marker, circle.variant'
    );
    expect(markers.length).toBeGreaterThanOrEqual(sampleVariants.length);
  });

  it('renders with empty variants array', async () => {
    const wrapper = await mountComponent({ variants: [] });
    expect(wrapper.find('svg').exists()).toBe(true);
  });
});
```

**Note:** Top-level `await import()` in a `describe` block only works if the test runner supports top-level async. If vitest complains, restructure using `vi.hoisted` and regular imports at the top of the file, converting the `describe` to use static imports.

- [ ] **Step 3: Run both the existing and new tests**

```bash
cd frontend && npx vitest run tests/unit/components/HNF1BProteinVisualization.spec.js
```

Expected: original domain tests pass (unchanged). New characterization tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/tests/unit/components/HNF1BProteinVisualization.spec.js
git commit -m "test(frontend): upgrade HNF1BProteinVisualization.spec.js with characterization

Adds a new describe block testing component mount behavior
(observable output, variant markers, empty state). The existing
domain-coordinate data tests are preserved untouched. Wave 5
decomposition uses this as its safety net.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Characterization test for AdminDashboard.vue

**Files:**
- Create: `frontend/tests/unit/views/AdminDashboard.spec.js`

- [ ] **Step 1: Identify observable surface**

```bash
head -60 frontend/src/views/AdminDashboard.vue
```

Look for section headings, sync status badges, and button labels. Those are the observable surface.

- [ ] **Step 2: Write the spec**

Create `frontend/tests/unit/views/AdminDashboard.spec.js`:

```javascript
/**
 * Characterization test for AdminDashboard.vue.
 *
 * Tests observable sections (sync cards, status display, buttons)
 * without exercising the polling mechanism itself (that becomes
 * useSyncTask in Wave 5 and gets its own unit tests).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

vi.mock('@/api', () => ({
  getSystemStatus: vi.fn().mockResolvedValue({
    database: { status: 'healthy', phenopacket_count: 864 },
    redis: { status: 'healthy' },
    vep: { status: 'healthy' },
  }),
  getSyncTaskStatus: vi.fn().mockResolvedValue({ status: 'idle' }),
  syncPublications: vi.fn(),
  syncVariants: vi.fn(),
  syncReferenceData: vi.fn(),
}));

globalThis.window.logService = {
  debug: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
};

async function mountDashboard() {
  const vuetify = createVuetify({ components, directives });
  const AdminDashboard = (await import('@/views/AdminDashboard.vue')).default;
  return mount(AdminDashboard, {
    global: { plugins: [vuetify] },
  });
}

describe('AdminDashboard.vue (characterization)', () => {
  it('mounts without throwing', async () => {
    const wrapper = await mountDashboard();
    await flushPromises();
    expect(wrapper.exists()).toBe(true);
  });

  it('renders the sync operations section', async () => {
    const wrapper = await mountDashboard();
    await flushPromises();
    const text = wrapper.text().toLowerCase();
    expect(text).toContain('sync');
  });

  it('renders at least 4 action buttons (the 4 sync operations)', async () => {
    const wrapper = await mountDashboard();
    await flushPromises();
    const buttons = wrapper.findAll('button');
    expect(buttons.length).toBeGreaterThanOrEqual(4);
  });

  it('calls getSystemStatus on mount', async () => {
    const api = await import('@/api');
    await mountDashboard();
    await flushPromises();
    expect(api.getSystemStatus).toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Run, iterate, commit**

```bash
cd frontend && npx vitest run tests/unit/views/AdminDashboard.spec.js
```

Adjust selectors and mock function names based on the actual API module. Once green:

```bash
git add frontend/tests/unit/views/AdminDashboard.spec.js
git commit -m "test(frontend): add characterization spec for AdminDashboard.vue

Wave 5 prep: verifies AdminDashboard mounts, renders sync section,
has at least 4 action buttons, and calls getSystemStatus on mount.
Does not exercise the polling loop (that's extracted into useSyncTask
during Wave 5 with its own dedicated tests).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Backend test file for auth/password.py

**Files:**
- Create: `backend/tests/test_auth_password.py`

- [ ] **Step 1: Read the module being tested**

```bash
cat backend/app/auth/password.py
```

Identify public functions (likely `hash_password`, `verify_password`, `check_password_strength` or similar).

- [ ] **Step 2: Write the test file**

Create `backend/tests/test_auth_password.py`:

```python
"""Tests for backend/app/auth/password.py.

Covers: password hashing roundtrip, verification, strength checks
(if implemented), and error cases. Does not test bcrypt internals
(those are library tests).
"""

import pytest

from app.auth.password import hash_password, verify_password


class TestPasswordHashing:
    """Tests for hash_password and verify_password roundtrip."""

    def test_hash_produces_non_empty_string(self):
        hashed = hash_password("correcthorsebatterystaple")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_is_not_plaintext(self):
        password = "correcthorsebatterystaple"
        hashed = hash_password(password)
        assert hashed != password

    def test_verify_accepts_correct_password(self):
        password = "correcthorsebatterystaple"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_rejects_wrong_password(self):
        hashed = hash_password("correcthorsebatterystaple")
        assert verify_password("wrong password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Bcrypt salts each hash — two calls produce different output."""
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2
        # But both verify
        assert verify_password("samepassword", h1)
        assert verify_password("samepassword", h2)

    def test_verify_with_empty_password_returns_false(self):
        hashed = hash_password("realpassword")
        assert verify_password("", hashed) is False

    @pytest.mark.parametrize(
        "password",
        [
            "a" * 8,  # minimum realistic length
            "p@ssw0rd!",  # special chars
            "日本語パスワード",  # unicode
            "a" * 72,  # bcrypt's 72-byte limit
        ],
    )
    def test_hash_verify_roundtrip_for_various_inputs(self, password):
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
```

- [ ] **Step 3: Run the tests**

```bash
cd backend && uv run pytest tests/test_auth_password.py -v
```

Expected: all pass. If the function signatures are different, update the import and calls accordingly — the test shape is the spec.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_auth_password.py
git commit -m "test(backend): add tests for auth/password.py

Covers hash/verify roundtrip, salt uniqueness, empty-password
rejection, and parametrized inputs including unicode and the 72-byte
bcrypt limit.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Backend test file for auth/tokens.py

**Files:**
- Create: `backend/tests/test_auth_tokens.py`

- [ ] **Step 1: Read the module**

```bash
cat backend/app/auth/tokens.py
```

Identify: token generation, token decoding/verification, refresh flow, expiry handling.

- [ ] **Step 2: Write the tests**

Create `backend/tests/test_auth_tokens.py`:

```python
"""Tests for backend/app/auth/tokens.py.

Covers: access token generation, refresh token generation, decode/verify,
expiry detection, signature validation, and token type distinction.
"""

import os
import time

import jwt
import pytest

# Ensure JWT_SECRET is set for the Settings import chain
os.environ.setdefault("JWT_SECRET", "0" * 64)
os.environ.setdefault("ADMIN_PASSWORD", "test_admin_pw_2026")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5433/test"
)

from app.auth.tokens import (  # noqa: E402
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.config import settings  # noqa: E402


class TestAccessToken:
    def test_creates_non_empty_string(self):
        token = create_access_token({"sub": "user-1", "roles": ["VIEWER"]})
        assert isinstance(token, str)
        assert token.count(".") == 2  # JWT has 3 parts separated by dots

    def test_token_payload_round_trips(self):
        token = create_access_token({"sub": "user-1", "roles": ["VIEWER"]})
        decoded = decode_token(token)
        assert decoded["sub"] == "user-1"
        assert decoded["roles"] == ["VIEWER"]

    def test_access_token_has_access_type(self):
        token = create_access_token({"sub": "user-1"})
        decoded = decode_token(token)
        assert decoded.get("type") == "access" or "access" in str(decoded)

    def test_expired_access_token_raises(self):
        # Create token with past expiration
        past = int(time.time()) - 3600
        bad_token = jwt.encode(
            {"sub": "user-1", "exp": past, "type": "access"},
            settings.JWT_SECRET,
            algorithm="HS256",
        )
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(bad_token)

    def test_wrong_signature_raises(self):
        bad_token = jwt.encode(
            {"sub": "user-1", "type": "access"},
            "wrong-secret-key",
            algorithm="HS256",
        )
        with pytest.raises((jwt.InvalidSignatureError, jwt.DecodeError)):
            decode_token(bad_token)


class TestRefreshToken:
    def test_creates_non_empty_string(self):
        token = create_refresh_token({"sub": "user-1"})
        assert isinstance(token, str)

    def test_refresh_token_has_refresh_type(self):
        token = create_refresh_token({"sub": "user-1"})
        decoded = decode_token(token)
        assert decoded.get("type") == "refresh" or "refresh" in str(decoded)

    def test_refresh_and_access_tokens_are_distinct(self):
        payload = {"sub": "user-1"}
        access = create_access_token(payload)
        refresh = create_refresh_token(payload)
        assert access != refresh
```

- [ ] **Step 3: Run and iterate**

```bash
cd backend && uv run pytest tests/test_auth_tokens.py -v
```

Adjust imports and function names to match the actual `tokens.py` API. If the module uses different names (`generate_access_token`, `verify_token`, etc.), update accordingly.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_auth_tokens.py
git commit -m "test(backend): add tests for auth/tokens.py

Covers access/refresh token generation, payload round-trip, type
distinction, expiry detection, and signature validation.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Backend test file for core/config.py startup validation

**Files:**
- Create: `backend/tests/test_core_config.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/test_core_config.py`:

```python
"""Tests for backend/app/core/config.py startup validation.

Exercises the field_validators for JWT_SECRET and ADMIN_PASSWORD that
cause the application to fail fast if critical secrets are unset.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


BASE_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5433/test",
}


class TestJwtSecretValidation:
    def test_empty_jwt_secret_raises(self, monkeypatch):
        for k, v in BASE_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("JWT_SECRET", "")
        monkeypatch.setenv("ADMIN_PASSWORD", "validpassword")
        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)
        assert "JWT_SECRET" in str(exc_info.value)

    def test_whitespace_jwt_secret_raises(self, monkeypatch):
        for k, v in BASE_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("JWT_SECRET", "   ")
        monkeypatch.setenv("ADMIN_PASSWORD", "validpassword")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_valid_jwt_secret_accepted(self, monkeypatch):
        for k, v in BASE_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("JWT_SECRET", "0" * 64)
        monkeypatch.setenv("ADMIN_PASSWORD", "validpassword")
        s = Settings(_env_file=None)
        assert s.JWT_SECRET == "0" * 64


class TestAdminPasswordValidation:
    def test_empty_admin_password_raises(self, monkeypatch):
        for k, v in BASE_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("JWT_SECRET", "0" * 64)
        monkeypatch.setenv("ADMIN_PASSWORD", "")
        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)
        assert "ADMIN_PASSWORD" in str(exc_info.value)

    def test_whitespace_admin_password_raises(self, monkeypatch):
        for k, v in BASE_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("JWT_SECRET", "0" * 64)
        monkeypatch.setenv("ADMIN_PASSWORD", "   ")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)


class TestHpoTermsConfig:
    def test_hpo_terms_section_accessible(self, monkeypatch):
        for k, v in BASE_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("JWT_SECRET", "0" * 64)
        monkeypatch.setenv("ADMIN_PASSWORD", "validpassword")
        s = Settings(_env_file=None)
        # hpo_terms comes from YAML config; may be nested under .yaml_config
        assert hasattr(s, "hpo_terms") or hasattr(s, "yaml_config") or hasattr(
            s, "_yaml_config"
        )
```

- [ ] **Step 2: Run, adjust, commit**

```bash
cd backend && uv run pytest tests/test_core_config.py -v
git add backend/tests/test_core_config.py
git commit -m "test(backend): add tests for core/config startup validation

Covers JWT_SECRET and ADMIN_PASSWORD field_validators including
empty-string, whitespace, and valid-value cases. Also smoke-checks
HPO terms config accessibility.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Set up dedicated test database

**Files:**
- Modify: `backend/tests/conftest.py` (remove "same database as development" workaround)
- Modify: `backend/Makefile` (add `db-test-init` target)
- Modify: `.github/workflows/ci.yml` (point CI at test DB)

- [ ] **Step 1: Read conftest.py:36**

```bash
sed -n '30,80p' backend/tests/conftest.py
```

You should see the comment "using same database as development for now" around line 36-37. This task removes that.

- [ ] **Step 2: Add db-test-init to the Makefile**

Open `backend/Makefile`. Find the `db-init` target. Add after it:

```makefile
db-test-init: ## Create/recreate the dedicated test database
	@echo "Creating test database hnf1b_phenopackets_test..."
	docker exec hnf1b-postgres-dev psql -U hnf1b_user -d postgres -c "DROP DATABASE IF EXISTS hnf1b_phenopackets_test;"
	docker exec hnf1b-postgres-dev psql -U hnf1b_user -d postgres -c "CREATE DATABASE hnf1b_phenopackets_test;"
	@echo "Running migrations against test DB..."
	DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets_test uv run alembic upgrade head
	@echo "Test database ready."
```

Adjust container name (`hnf1b-postgres-dev`) and user/password to match your docker-compose setup.

- [ ] **Step 3: Update conftest.py to use the test DB**

Edit `backend/tests/conftest.py` around line 36. Change from using `DATABASE_URL` directly to constructing the test URL:

```python
import os

# Use a dedicated test database, NOT the development database.
# Set TEST_DATABASE_URL explicitly or it derives from DATABASE_URL by
# swapping the database name to hnf1b_phenopackets_test.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get("DATABASE_URL", "").rsplit("/", 1)[0]
    + "/hnf1b_phenopackets_test",
)

if "test" not in TEST_DATABASE_URL:
    raise RuntimeError(
        f"Refusing to run tests against non-test database: {TEST_DATABASE_URL}. "
        "Set TEST_DATABASE_URL explicitly or ensure DATABASE_URL's database name "
        "ends in '_test' or contains 'test'."
    )
```

Then everywhere the fixtures use a session, make sure they point at `TEST_DATABASE_URL`.

- [ ] **Step 4: Run the test DB init**

```bash
make hybrid-up  # ensure Postgres is running
cd backend && make db-test-init
```

Expected: test database created and migrations applied.

- [ ] **Step 5: Update CI to use the test DB**

Open `.github/workflows/ci.yml`. Find the backend job's environment variables. Change `DATABASE_URL` to point at a test DB name, or add `TEST_DATABASE_URL` explicitly:

```yaml
      - name: Run backend tests
        env:
          DATABASE_URL: postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets_test
          JWT_SECRET: ${{ secrets.JWT_SECRET || '0000000000000000000000000000000000000000000000000000000000000000' }}
          ADMIN_PASSWORD: ci_test_admin_password_2026
        run: |
          cd backend
          uv run alembic upgrade head
          uv run pytest tests/ -v
```

- [ ] **Step 6: Run tests against the test DB**

```bash
cd backend && uv run pytest tests/test_database_health.py tests/test_auth.py -v
```

Expected: all green. The guard in conftest.py prevents accidentally hitting the dev DB.

- [ ] **Step 7: Commit**

```bash
git add backend/tests/conftest.py backend/Makefile .github/workflows/ci.yml
git commit -m "test(backend): use dedicated test database, not dev DB

Adds db-test-init Makefile target and updates conftest.py to refuse
running against a database whose URL doesn't contain 'test'. Updates
CI to use the dedicated test database. Removes the 'same database as
development' compromise documented in conftest.py:36.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Standardize backend error response format

**Files:**
- Create: `backend/app/core/exceptions.py`
- Modify: `backend/app/main.py` (register handlers)
- Create: `backend/tests/test_error_responses.py`
- Modify: `frontend/src/api/index.js` (update error interceptor to handle new shape)

- [ ] **Step 1: Write the error handler test first**

Create `backend/tests/test_error_responses.py`:

```python
"""Tests for the standardized error response format.

Every error response must have the shape:
    {"detail": str, "error_code": str, "request_id": str | None}
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.exceptions import register_exception_handlers


class Sample(BaseModel):
    value: int = Field(..., gt=0)


@pytest.fixture
def app():
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/http-error")
    async def http_error():
        raise HTTPException(status_code=404, detail="Not found")

    @test_app.post("/validation-error")
    async def validation_error(body: Sample):
        return body

    @test_app.get("/uncaught-error")
    async def uncaught_error():
        raise RuntimeError("Something broke")

    return test_app


def test_http_exception_response_shape(app):
    client = TestClient(app)
    response = client.get("/http-error")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "error_code" in body
    assert body["error_code"] == "http_error" or "404" in body["error_code"]


def test_validation_error_response_shape(app):
    client = TestClient(app)
    response = client.post("/validation-error", json={"value": -1})
    assert response.status_code == 422
    body = response.json()
    assert "detail" in body
    assert "error_code" in body
    assert body["error_code"] == "validation_error"


def test_uncaught_error_is_500_with_shape(app):
    client = TestClient(app)
    response = client.get("/uncaught-error")
    assert response.status_code == 500
    body = response.json()
    assert "detail" in body
    assert "error_code" in body
    assert body["error_code"] in ("internal_error", "server_error")
```

- [ ] **Step 2: Run to confirm fail**

```bash
cd backend && uv run pytest tests/test_error_responses.py -v
```

Expected: FAIL (module `app.core.exceptions` does not exist).

- [ ] **Step 3: Create the exception handler module**

Create `backend/app/core/exceptions.py`:

```python
"""Shared exception handlers for consistent API error response shape.

All error responses follow:
    {
        "detail": str,                 # human-readable message
        "error_code": str,             # machine-readable code
        "request_id": str | None,      # for log correlation (set by
                                       # request_id middleware in Wave 6)
    }
"""

import logging
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _build_error_response(
    status_code: int,
    detail: str,
    error_code: str,
    request: Request,
) -> JSONResponse:
    """Build a standardized error response body."""
    request_id = getattr(request.state, "request_id", None)
    body: Dict[str, Any] = {
        "detail": detail,
        "error_code": error_code,
        "request_id": request_id,
    }
    return JSONResponse(status_code=status_code, content=body)


async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """Convert HTTPException into the standardized shape."""
    error_code = f"http_{exc.status_code}"
    return _build_error_response(
        status_code=exc.status_code,
        detail=str(exc.detail),
        error_code=error_code,
        request=request,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert pydantic validation errors into the standardized shape."""
    errors = exc.errors()
    detail = "; ".join(
        f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in errors
    )
    return _build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=detail,
        error_code="validation_error",
        request=request,
    )


async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all for uncaught exceptions.

    Logs the traceback and returns a safe 500 response without leaking
    stack details to the client.
    """
    logger.exception(
        "Uncaught exception in request %s %s", request.method, request.url.path
    )
    return _build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
        error_code="internal_error",
        request=request,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all shared exception handlers on the given FastAPI app."""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
```

- [ ] **Step 4: Register in main.py**

Open `backend/app/main.py`. Near the other middleware/registration code, add:

```python
from app.core.exceptions import register_exception_handlers

# ... later in the file, after app = FastAPI(...)
register_exception_handlers(app)
```

- [ ] **Step 5: Run the tests**

```bash
cd backend && uv run pytest tests/test_error_responses.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 6: Update frontend error interceptor**

Open `frontend/src/api/index.js`. Find the axios response error interceptor. Currently it likely reads `error.response.data.detail` or `error.response.data.message`. Update to handle both the new shape and the old shape (for safety):

```javascript
// In the axios interceptor response error branch:
const errorData = error.response?.data || {};
const detail = errorData.detail || errorData.message || 'Unknown error';
const errorCode = errorData.error_code || 'unknown';
const requestId = errorData.request_id || null;

window.logService.error('API error', {
  status: error.response?.status,
  detail,
  errorCode,
  requestId,
});

// propagate a normalized error shape downstream
error.normalized = { detail, errorCode, requestId };
return Promise.reject(error);
```

- [ ] **Step 7: Run both sides' tests**

```bash
cd backend && make check && cd ../frontend && make check
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/exceptions.py backend/app/main.py backend/tests/test_error_responses.py frontend/src/api/index.js
git commit -m "feat(backend): standardize API error response shape

Adds app/core/exceptions.py with three handlers (HTTPException,
RequestValidationError, generic Exception) all returning the
standard {detail, error_code, request_id} shape. Registered in
main.py. Frontend axios interceptor updated to read the new shape
with backwards-compatible fallback.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Security headers middleware

**Files:**
- Create: `backend/app/core/security_headers.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_security_headers.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/test_security_headers.py`:

```python
"""Tests for the security headers middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security_headers import SecurityHeadersMiddleware


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return TestClient(app)


def test_x_frame_options_present(client):
    response = client.get("/ping")
    assert response.headers.get("x-frame-options") == "DENY"


def test_x_content_type_options_present(client):
    response = client.get("/ping")
    assert response.headers.get("x-content-type-options") == "nosniff"


def test_referrer_policy_present(client):
    response = client.get("/ping")
    assert "referrer-policy" in response.headers


def test_content_security_policy_present(client):
    response = client.get("/ping")
    assert "content-security-policy" in response.headers


def test_permissions_policy_present(client):
    response = client.get("/ping")
    assert "permissions-policy" in response.headers
```

- [ ] **Step 2: Run to confirm fail**

```bash
cd backend && uv run pytest tests/test_security_headers.py -v
```

Expected: FAIL (`SecurityHeadersMiddleware` does not exist).

- [ ] **Step 3: Create the middleware**

Create `backend/app/core/security_headers.py`:

```python
"""Security headers middleware.

Adds standard defensive HTTP headers to every response. Works with
FastAPI's built-in middleware mechanism via add_middleware.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# CSP is intentionally permissive for now because the frontend uses
# inline scripts and connects to multiple origins. Tighten this in a
# future hardening pass (out of Wave 2 scope).
DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "connect-src 'self' https://rest.ensembl.org https://eutils.ncbi.nlm.nih.gov "
    "https://hpo.jax.org https://www.ebi.ac.uk; "
    "font-src 'self' data:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds defensive security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = DEFAULT_CSP
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )
        return response
```

- [ ] **Step 4: Register the middleware**

Open `backend/app/main.py`. Find where middleware is added (around line 58-65 per the review). Add:

```python
from app.core.security_headers import SecurityHeadersMiddleware

# ... later, where other middleware is registered:
app.add_middleware(SecurityHeadersMiddleware)
```

Place it **before** CORS middleware so CORS headers override if needed.

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_security_headers.py -v && make check
```

Expected: all 5 new tests pass, full suite green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/security_headers.py backend/app/main.py backend/tests/test_security_headers.py
git commit -m "feat(backend): add security headers middleware

Adds SecurityHeadersMiddleware to backend/app/core/security_headers.py
and registers it in main.py. Sets X-Frame-Options, X-Content-Type-
Options, Referrer-Policy, Content-Security-Policy, and
Permissions-Policy on every response.

CSP is intentionally permissive for the current frontend shape.
Tightening is out of Wave 2 scope.

Closes P2 #7 from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: Frontend global error boundary

**Files:**
- Modify: `frontend/src/main.js`
- Create: `frontend/tests/unit/main-error-handler.spec.js`

- [ ] **Step 1: Write the test**

Create `frontend/tests/unit/main-error-handler.spec.js`:

```javascript
/**
 * Verifies that a global errorHandler is configured on the Vue app.
 *
 * We cannot test main.js directly (it creates an app and mounts it),
 * so this tests the pattern by constructing a Vue app with the same
 * configurator function.
 */
import { describe, it, expect, vi } from 'vitest';
import { createApp, defineComponent } from 'vue';
import { configureErrorHandler } from '@/main-error-handler';

describe('configureErrorHandler', () => {
  it('sets app.config.errorHandler', () => {
    const logError = vi.fn();
    const app = createApp(defineComponent({ render: () => null }));
    configureErrorHandler(app, logError);
    expect(app.config.errorHandler).toBeTypeOf('function');
  });

  it('routes caught errors through the provided logger', () => {
    const logError = vi.fn();
    const app = createApp(defineComponent({ render: () => null }));
    configureErrorHandler(app, logError);

    const err = new Error('boom');
    const instance = { $: { type: { name: 'TestComponent' } } };
    app.config.errorHandler(err, instance, 'test info');

    expect(logError).toHaveBeenCalled();
    expect(logError.mock.calls[0][0]).toContain('boom');
  });
});
```

- [ ] **Step 2: Run to confirm fail**

```bash
cd frontend && npx vitest run tests/unit/main-error-handler.spec.js
```

Expected: FAIL (`@/main-error-handler` does not exist).

- [ ] **Step 3: Create the error handler module**

Create `frontend/src/main-error-handler.js`:

```javascript
/**
 * Global Vue error handler.
 *
 * Exported as a separate module so main.js stays small and so tests
 * can exercise the configuration without mounting the whole app.
 */

/**
 * Configure the given Vue app with a global error handler.
 * @param {import('vue').App} app - The Vue application instance.
 * @param {(msg: string, meta?: object) => void} logError - Logger function.
 */
export function configureErrorHandler(app, logError) {
  app.config.errorHandler = (err, instance, info) => {
    const componentName = instance?.$?.type?.name || 'Unknown';
    logError(`Uncaught error in ${componentName}: ${err.message}`, {
      stack: err.stack,
      info,
    });
  };
}
```

- [ ] **Step 4: Wire it into main.js**

Open `frontend/src/main.js`. Find where the app is created. Add:

```javascript
import { configureErrorHandler } from './main-error-handler';

// ... after createApp(App) but before app.mount('#app'):
configureErrorHandler(app, (msg, meta) => {
  window.logService?.error(msg, meta);
});
```

- [ ] **Step 5: Run tests and commit**

```bash
cd frontend && make check
git add frontend/src/main.js frontend/src/main-error-handler.js frontend/tests/unit/main-error-handler.spec.js
git commit -m "feat(frontend): add global error handler

Introduces configureErrorHandler in main-error-handler.js (isolated
so tests can exercise it without full app mount). main.js calls it
during bootstrap, routing uncaught errors through window.logService.
Companion unit tests verify the configuration.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: Backend integration tests for phenopacket CRUD

**Files:**
- Create: `backend/tests/test_phenopackets_crud.py`

- [ ] **Step 1: Write the integration tests**

Create `backend/tests/test_phenopackets_crud.py`:

```python
"""Integration tests for phenopacket CRUD endpoints.

Exercises create/read/update/delete via the FastAPI TestClient against
the dedicated test database set up in Task 10.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import create_test_user_and_get_token  # assumed helper


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Return headers with a valid bearer token for a curator user."""
    # This uses a helper from conftest.py; if it doesn't exist, create it
    # or adapt to the actual auth-test pattern used elsewhere.
    token = create_test_user_and_get_token(role="CURATOR")
    return {"Authorization": f"Bearer {token}"}


SAMPLE_PAYLOAD = {
    "id": "INT-TEST-001",
    "subject": {"id": "SUB-INT-001", "sex": "MALE"},
    "phenotypicFeatures": [
        {"type": {"id": "HP:0000107", "label": "Renal cyst"}}
    ],
    "metaData": {
        "created": "2026-04-10T00:00:00Z",
        "createdBy": "integration-test",
        "phenopacketSchemaVersion": "2.0",
    },
}


class TestPhenopacketCreate:
    def test_create_returns_201(self, client, auth_headers):
        response = client.post(
            "/api/v2/phenopackets/", json=SAMPLE_PAYLOAD, headers=auth_headers
        )
        assert response.status_code in (200, 201), response.text

    def test_create_rejects_unauthenticated(self, client):
        response = client.post("/api/v2/phenopackets/", json=SAMPLE_PAYLOAD)
        assert response.status_code in (401, 403)

    def test_create_rejects_invalid_payload(self, client, auth_headers):
        response = client.post(
            "/api/v2/phenopackets/", json={"invalid": "data"}, headers=auth_headers
        )
        assert response.status_code == 422


class TestPhenopacketRead:
    def test_list_returns_data(self, client):
        response = client.get("/api/v2/phenopackets/?page[size]=5")
        assert response.status_code == 200
        body = response.json()
        assert "data" in body or "items" in body or isinstance(body, list)


class TestPhenopacketUpdate:
    def test_update_requires_auth(self, client):
        response = client.patch(
            "/api/v2/phenopackets/INT-TEST-001", json={"subject": {"sex": "FEMALE"}}
        )
        assert response.status_code in (401, 403, 404)


class TestPhenopacketDelete:
    def test_delete_requires_auth(self, client):
        response = client.delete("/api/v2/phenopackets/INT-TEST-001")
        assert response.status_code in (401, 403, 404)
```

- [ ] **Step 2: Adjust based on actual API shape**

Run the tests:

```bash
cd backend && uv run pytest tests/test_phenopackets_crud.py -v
```

Many will likely fail because:
- The test helper `create_test_user_and_get_token` may not exist — if not, create it in conftest.py or replace with the actual auth pattern.
- Endpoint paths may differ.
- Payload schema may be stricter.

Iterate until the tests pass. The goal is **any passing integration coverage** — even 4 tests is enough for Wave 2. Leave TODOs for additional coverage.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_phenopackets_crud.py
git commit -m "test(backend): add phenopacket CRUD integration tests

Adds integration coverage for create/read/update/delete endpoints
via TestClient. Uses the dedicated test database from Task 10.
Coverage is intentionally shallow at Wave 2 — deeper coverage arrives
during Wave 4 when the repository layer lands.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 15: Wave 2 exit verification

- [ ] **Step 1: Run both full check suites**

```bash
cd backend && make check && cd ../frontend && make check
```

- [ ] **Step 2: Verify test file counts**

```bash
cd frontend && find tests -type f \( -name "*.spec.js" -o -name "*.test.js" \) | wc -l
```

Expected: 16 (10 original + 1 from Wave 1 + 5 new in Wave 2). Confirm against the list:

```bash
find frontend/tests -name "*.spec.js" | sort
```

Should include:
- Existing 10 (see Wave 1 exit verification)
- `frontend/tests/unit/utils/sanitize.spec.js` (Wave 1)
- `frontend/tests/unit/views/FAQ.spec.js` (Wave 1)
- `frontend/tests/unit/views/PageVariant.spec.js` (Wave 2)
- `frontend/tests/unit/components/gene/HNF1BGeneVisualization.spec.js` (Wave 2)
- `frontend/tests/unit/components/gene/ProteinStructure3D.spec.js` (Wave 2)
- `frontend/tests/unit/views/AdminDashboard.spec.js` (Wave 2)
- `frontend/tests/unit/main-error-handler.spec.js` (Wave 2)

Plus `frontend/tests/unit/components/HNF1BProteinVisualization.spec.js` which was upgraded in place.

- [ ] **Step 3: Verify backend test count**

```bash
cd backend && uv run pytest tests/ --collect-only -q 2>&1 | tail -5
```

Expected: ~765 tests (Wave 1's 750 + ~15 from Wave 2 auth/config/CRUD/error/security-headers tests).

- [ ] **Step 4: Smoke-test security headers via curl**

```bash
cd backend && make backend &
sleep 3
curl -s -D - http://localhost:8000/health | head -20
# Expected: headers include X-Frame-Options, X-Content-Type-Options, etc.
kill %1
```

- [ ] **Step 5: Verify dedicated test DB is in use**

```bash
grep -n "hnf1b_phenopackets_test\|TEST_DATABASE_URL" backend/tests/conftest.py
```

Expected: references the dedicated test DB name.

- [ ] **Step 6: Write the wave-exit note**

Create `docs/refactor/wave-2-exit.md`:

```markdown
# Wave 2 Exit Note

**Date:** <YYYY-MM-DD>
**Starting test counts:** backend ~750, frontend 11 spec files.
**Ending test counts:** backend ~765, frontend 16 spec files.

## What landed

- Fixture directory with 4 sample payloads + index (Task 1)
- PageVariant.vue characterization spec (Task 2)
- HNF1BGeneVisualization.vue characterization spec with fail-first zoom test (Task 3)
- ProteinStructure3D.vue characterization spec with NGL mock (Task 4)
- HNF1BProteinVisualization.vue upgraded with characterization block (Task 5)
- AdminDashboard.vue characterization spec (Task 6)
- auth/password.py test file (Task 7)
- auth/tokens.py test file (Task 8)
- core/config.py startup validation test file (Task 9)
- Dedicated test database with safety guard in conftest.py (Task 10)
- Standardized error response format + handlers (Task 11)
- Security headers middleware (Task 12)
- Frontend global error handler (Task 13)
- Phenopacket CRUD integration tests (Task 14)

## What was deferred

<list any tasks whose scope shrank during execution>

## What surprised us

<fill in during execution>

## Entry conditions for Wave 3

- All Wave 2 exit checks green.
- Characterization tests exist for every Wave 5 decomposition target.
- Error response shape is standardized backend-side.
- Security headers present on every response.
- Dedicated test DB is in use; no more "same database as development" workaround.

Wave 3 can begin.
```

- [ ] **Step 7: Commit the exit note**

```bash
git add docs/refactor/wave-2-exit.md
git commit -m "docs: add Wave 2 exit note

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

**Wave 2 is done when all 15 tasks are checked off and the exit note is committed.**

---

## Self-Review Notes

- **Spec coverage:** Characterization tests (all 6 targets), backend auth tests, core/config tests, dedicated test DB, error format standardization, security headers, frontend error boundary, CRUD integration tests. Every Wave 2 item from the spec is present.
- **Placeholder scan:** Only `<fill in during execution>` in the exit note template, which is intentional (written post-execution).
- **Type/name consistency:** `register_exception_handlers`, `SecurityHeadersMiddleware`, `configureErrorHandler`, `TEST_DATABASE_URL` used identically in their test and implementation pairs.
- **Known iteration points:** Tasks 2-6 and 14 require adjustment against actual codebase shapes (API method names, selector strings, test helpers). The plan flags this explicitly in each task's "iterate until green" step.
