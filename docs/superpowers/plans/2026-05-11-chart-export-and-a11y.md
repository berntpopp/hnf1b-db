# Chart Export + Accessibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add PNG/CSV/SVG export and screen-reader accessibility (ARIA + data-table fallback) to all 7 chart components under `frontend/src/components/analyses/`, closing issues #135 and #136 in one focused PR.

**Architecture:** Three new units (`chartExport.js` utility, `ChartExportMenu.vue` component, `useChartAccessibility.js` composable) supply shared functionality. Each of the 7 chart components wraps its existing D3-rendered subtree with an ARIA container, a `<details>` data-table fallback, and the export menu — the D3 subtree itself stays `aria-hidden`. Native SVG serialization (no new deps) handles PNG generation; `file-saver` (already installed) handles the download.

**Tech Stack:** Vue 3 (Options + Composition API), Vuetify 3, D3 v7, Vitest + happy-dom, Playwright, file-saver, axe-core via existing CI.

**Spec:** `docs/superpowers/specs/2026-05-11-chart-export-and-a11y-design.md` (commit `c25ffdd`)

---

## Task 1: Promote `.sr-only` to a global helper class

**Files:**
- Modify: `frontend/src/style.css`
- Modify: `frontend/src/components/common/ExternalLink.vue` (remove now-duplicate scoped rule)

- [ ] **Step 1: Append `.sr-only` to global stylesheet**

Open `frontend/src/style.css` and append at the end:

```css
/* Visually-hidden helper for screen-reader-only content (WCAG 1.1.1 fallback). */
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
```

- [ ] **Step 2: Remove the duplicate scoped rule from ExternalLink.vue**

In `frontend/src/components/common/ExternalLink.vue`, delete lines 43–53 (the `.sr-only { ... }` block inside `<style scoped>`). The global rule takes over.

- [ ] **Step 3: Run the existing ExternalLink spec**

Run from the `frontend/` directory:
```
npm test -- ExternalLink
```
Expected: PASS (the sr-only span is still styled, now via global rule).

- [ ] **Step 4: Commit**

```
git add frontend/src/style.css frontend/src/components/common/ExternalLink.vue
git commit -m "refactor(a11y): promote .sr-only to global stylesheet"
```

---

## Task 2: chartExport.js — filename helper (TDD)

**Files:**
- Create: `frontend/src/utils/chartExport.js`
- Create: `frontend/tests/unit/utils/chartExport.spec.js`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/unit/utils/chartExport.spec.js`:

```js
import { describe, it, expect, vi } from 'vitest';
import { buildExportFilename } from '@/utils/chartExport';

describe('buildExportFilename', () => {
  it('formats as hnf1b-db_<kebab>_<date>.<ext>', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-11T12:00:00Z'));
    expect(buildExportFilename('Sex Distribution', 'png')).toBe(
      'hnf1b-db_sex-distribution_2026-05-11.png'
    );
    vi.useRealTimers();
  });

  it('kebab-cases multi-word names with mixed case and underscores', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-11T00:00:00Z'));
    expect(buildExportFilename('Kaplan_Meier survivalCurve', 'csv')).toBe(
      'hnf1b-db_kaplan-meier-survival-curve_2026-05-11.csv'
    );
    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: Run the test and confirm it fails**

```
npm test -- chartExport
```
Expected: FAIL — module `@/utils/chartExport` not found.

- [ ] **Step 3: Implement the minimum to pass**

Create `frontend/src/utils/chartExport.js`:

```js
/**
 * Build a filename in the format hnf1b-db_<kebab-name>_<YYYY-MM-DD>.<ext>.
 * @param {string} chartName - Human-readable chart name (any case, spaces or underscores allowed).
 * @param {string} ext - File extension without the dot ('png', 'csv', 'svg').
 * @returns {string}
 */
export function buildExportFilename(chartName, ext) {
  const kebab = chartName
    .replace(/([a-z])([A-Z])/g, '$1-$2')
    .replace(/[\s_]+/g, '-')
    .toLowerCase();
  const date = new Date().toISOString().slice(0, 10);
  return `hnf1b-db_${kebab}_${date}.${ext}`;
}
```

- [ ] **Step 4: Run the test and confirm it passes**

```
npm test -- chartExport
```
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```
git add frontend/src/utils/chartExport.js frontend/tests/unit/utils/chartExport.spec.js
git commit -m "feat(charts): buildExportFilename helper"
```

---

## Task 3: chartExport.js — CSV export (TDD)

**Files:**
- Modify: `frontend/src/utils/chartExport.js`
- Modify: `frontend/tests/unit/utils/chartExport.spec.js`

- [ ] **Step 1: Append failing tests**

Append to `frontend/tests/unit/utils/chartExport.spec.js`:

```js
import { exportDataAsCsv } from '@/utils/chartExport';

describe('exportDataAsCsv', () => {
  let saveAsMock;
  beforeEach(() => {
    saveAsMock = vi.fn();
    vi.doMock('file-saver', () => ({ saveAs: saveAsMock, default: { saveAs: saveAsMock } }));
  });

  it('writes BOM + headers + rows with CRLF line endings', async () => {
    const { exportDataAsCsv: fn } = await import('@/utils/chartExport');
    fn(
      [{ label: 'Male', count: 389 }, { label: 'Female', count: 416 }],
      [{ key: 'label', label: 'Group' }, { key: 'count', label: 'N' }],
      'test.csv'
    );
    expect(saveAsMock).toHaveBeenCalledOnce();
    const [blob, filename] = saveAsMock.mock.calls[0];
    expect(filename).toBe('test.csv');
    expect(blob.type).toBe('text/csv;charset=utf-8');
    const text = await blob.text();
    expect(text).toBe('﻿Group,N\r\nMale,389\r\nFemale,416\r\n');
  });

  it('quotes fields containing commas, quotes, or newlines (RFC 4180)', async () => {
    const { exportDataAsCsv: fn } = await import('@/utils/chartExport');
    fn(
      [{ a: 'has, comma', b: 'has "quote"', c: 'has\nnewline' }],
      [{ key: 'a', label: 'A' }, { key: 'b', label: 'B' }, { key: 'c', label: 'C' }],
      'test.csv'
    );
    const [blob] = saveAsMock.mock.calls[0];
    const text = await blob.text();
    expect(text).toBe('﻿A,B,C\r\n"has, comma","has ""quote""","has\nnewline"\r\n');
  });

  it('renders null / undefined as empty fields', async () => {
    const { exportDataAsCsv: fn } = await import('@/utils/chartExport');
    fn(
      [{ a: null, b: undefined, c: 0 }],
      [{ key: 'a', label: 'A' }, { key: 'b', label: 'B' }, { key: 'c', label: 'C' }],
      'test.csv'
    );
    const [blob] = saveAsMock.mock.calls[0];
    const text = await blob.text();
    expect(text).toBe('﻿A,B,C\r\n,,0\r\n');
  });
});
```

- [ ] **Step 2: Run and confirm failure**

```
npm test -- chartExport
```
Expected: FAIL — `exportDataAsCsv` not exported.

- [ ] **Step 3: Implement**

Append to `frontend/src/utils/chartExport.js`:

```js
import { saveAs } from 'file-saver';

const CSV_NEEDS_QUOTING = /[,"\n\r]/;

function escapeCsvField(value) {
  if (value === null || value === undefined) return '';
  const str = String(value);
  if (CSV_NEEDS_QUOTING.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Export an array of row objects to a CSV file (RFC 4180, UTF-8 BOM, CRLF).
 * @param {Array<Object>} rows
 * @param {Array<{key:string,label:string}>} columns
 * @param {string} filename
 */
export function exportDataAsCsv(rows, columns, filename) {
  const header = columns.map((c) => escapeCsvField(c.label)).join(',');
  const body = rows
    .map((row) => columns.map((c) => escapeCsvField(row[c.key])).join(','))
    .join('\r\n');
  const csv = `﻿${header}\r\n${body}${rows.length ? '\r\n' : ''}`;
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  saveAs(blob, filename);
}
```

- [ ] **Step 4: Run and confirm pass**

```
npm test -- chartExport
```
Expected: PASS (5 tests total: 2 from Task 2 + 3 new).

- [ ] **Step 5: Commit**

```
git add frontend/src/utils/chartExport.js frontend/tests/unit/utils/chartExport.spec.js
git commit -m "feat(charts): exportDataAsCsv with RFC 4180 escaping"
```

---

## Task 4: chartExport.js — raw SVG export (TDD)

**Files:**
- Modify: `frontend/src/utils/chartExport.js`
- Modify: `frontend/tests/unit/utils/chartExport.spec.js`

- [ ] **Step 1: Append failing tests**

Append to `frontend/tests/unit/utils/chartExport.spec.js`:

```js
import { exportSvgAsSvg } from '@/utils/chartExport';

describe('exportSvgAsSvg', () => {
  let saveAsMock;
  beforeEach(() => {
    saveAsMock = vi.fn();
    vi.doMock('file-saver', () => ({ saveAs: saveAsMock, default: { saveAs: saveAsMock } }));
  });

  it('serializes the SVG element and saves with image/svg+xml MIME', async () => {
    const { exportSvgAsSvg: fn } = await import('@/utils/chartExport');
    const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svgEl.setAttribute('width', '100');
    svgEl.setAttribute('height', '50');
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', '10');
    circle.setAttribute('cy', '10');
    circle.setAttribute('r', '5');
    svgEl.appendChild(circle);

    fn(svgEl, 'chart.svg');

    expect(saveAsMock).toHaveBeenCalledOnce();
    const [blob, filename] = saveAsMock.mock.calls[0];
    expect(filename).toBe('chart.svg');
    expect(blob.type).toBe('image/svg+xml;charset=utf-8');
    const text = await blob.text();
    expect(text).toContain('<svg');
    expect(text).toContain('<circle');
  });
});
```

- [ ] **Step 2: Run and confirm failure**

```
npm test -- chartExport
```
Expected: FAIL — `exportSvgAsSvg` not exported.

- [ ] **Step 3: Implement**

Append to `frontend/src/utils/chartExport.js`:

```js
/**
 * Export an SVG element as a raw .svg file (vector, editable in Illustrator/Inkscape).
 * @param {SVGElement} svgEl
 * @param {string} filename
 */
export function exportSvgAsSvg(svgEl, filename) {
  const serialized = new XMLSerializer().serializeToString(svgEl);
  const blob = new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' });
  saveAs(blob, filename);
}
```

- [ ] **Step 4: Run and confirm pass**

```
npm test -- chartExport
```
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```
git add frontend/src/utils/chartExport.js frontend/tests/unit/utils/chartExport.spec.js
git commit -m "feat(charts): exportSvgAsSvg raw vector export"
```

---

## Task 5: chartExport.js — SVG→PNG export (TDD)

**Files:**
- Modify: `frontend/src/utils/chartExport.js`
- Modify: `frontend/tests/unit/utils/chartExport.spec.js`

- [ ] **Step 1: Append failing tests**

Append to `frontend/tests/unit/utils/chartExport.spec.js`:

```js
import { exportSvgAsPng } from '@/utils/chartExport';

describe('exportSvgAsPng', () => {
  let saveAsMock;
  let originalImage;
  let originalCreateObjectURL;
  let originalRevokeObjectURL;

  beforeEach(() => {
    saveAsMock = vi.fn();
    vi.doMock('file-saver', () => ({ saveAs: saveAsMock, default: { saveAs: saveAsMock } }));

    originalImage = global.Image;
    global.Image = class {
      constructor() {
        setTimeout(() => this.onload && this.onload(), 0);
      }
      set src(_) {}
      width = 100;
      height = 50;
    };

    originalCreateObjectURL = URL.createObjectURL;
    originalRevokeObjectURL = URL.revokeObjectURL;
    URL.createObjectURL = vi.fn(() => 'blob:mock');
    URL.revokeObjectURL = vi.fn();

    HTMLCanvasElement.prototype.getContext = function () {
      return {
        fillStyle: '',
        fillRect: vi.fn(),
        drawImage: vi.fn(),
      };
    };
    HTMLCanvasElement.prototype.toBlob = function (cb, type) {
      cb(new Blob(['png-bytes'], { type: type || 'image/png' }));
    };
  });

  afterEach(() => {
    global.Image = originalImage;
    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
  });

  it('saves a PNG blob with the supplied filename', async () => {
    const { exportSvgAsPng: fn } = await import('@/utils/chartExport');
    const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svgEl.setAttribute('width', '100');
    svgEl.setAttribute('height', '50');

    await fn(svgEl, { filename: 'chart.png' });

    expect(saveAsMock).toHaveBeenCalledOnce();
    const [blob, filename] = saveAsMock.mock.calls[0];
    expect(filename).toBe('chart.png');
    expect(blob.type).toBe('image/png');
  });

  it('honors scale option for the canvas dimensions', async () => {
    const { exportSvgAsPng: fn } = await import('@/utils/chartExport');
    const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svgEl.setAttribute('width', '100');
    svgEl.setAttribute('height', '50');
    const canvasSpy = vi.spyOn(document, 'createElement');

    await fn(svgEl, { filename: 'chart.png', scale: 3 });

    const canvasCall = canvasSpy.mock.results.find((r) => r.value instanceof HTMLCanvasElement);
    expect(canvasCall.value.width).toBe(300);
    expect(canvasCall.value.height).toBe(150);
    canvasSpy.mockRestore();
  });
});
```

- [ ] **Step 2: Run and confirm failure**

```
npm test -- chartExport
```
Expected: FAIL — `exportSvgAsPng` not exported.

- [ ] **Step 3: Implement**

Append to `frontend/src/utils/chartExport.js`:

```js
/**
 * Inline computed styles from the live DOM onto a cloned SVG subtree so that
 * the serialized SVG renders identically when loaded into a canvas.
 * D3 sets some styles via .style() (inline) and some via class rules; only
 * inline styles survive cloneNode. This walk transfers the rest.
 * @param {Element} liveRoot - The original element still in the DOM.
 * @param {Element} clonedRoot - The cloned element to mutate.
 */
function inlineComputedStyles(liveRoot, clonedRoot) {
  const liveNodes = [liveRoot, ...liveRoot.querySelectorAll('*')];
  const clonedNodes = [clonedRoot, ...clonedRoot.querySelectorAll('*')];
  for (let i = 0; i < liveNodes.length; i++) {
    const computed = window.getComputedStyle(liveNodes[i]);
    let inline = '';
    for (let j = 0; j < computed.length; j++) {
      const prop = computed[j];
      inline += `${prop}:${computed.getPropertyValue(prop)};`;
    }
    clonedNodes[i].setAttribute('style', inline);
  }
}

/**
 * Export an SVG element as a PNG via canvas. No external dependencies for
 * rasterization; uses file-saver for the download trigger.
 * @param {SVGElement} svgEl
 * @param {{filename:string, scale?:number, background?:string}} options
 * @returns {Promise<void>}
 */
export function exportSvgAsPng(svgEl, { filename, scale = 2, background = '#ffffff' }) {
  return new Promise((resolve, reject) => {
    const bbox = {
      width: parseFloat(svgEl.getAttribute('width')) || svgEl.clientWidth,
      height: parseFloat(svgEl.getAttribute('height')) || svgEl.clientHeight,
    };

    const clone = svgEl.cloneNode(true);
    inlineComputedStyles(svgEl, clone);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('width', bbox.width);
    clone.setAttribute('height', bbox.height);

    const serialized = new XMLSerializer().serializeToString(clone);
    const svgBlob = new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);

    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = bbox.width * scale;
      canvas.height = bbox.height * scale;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = background;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      canvas.toBlob((pngBlob) => {
        saveAs(pngBlob, filename);
        resolve();
      }, 'image/png');
    };
    img.onerror = (e) => {
      URL.revokeObjectURL(url);
      reject(e);
    };
    img.src = url;
  });
}
```

- [ ] **Step 4: Run and confirm pass**

```
npm test -- chartExport
```
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```
git add frontend/src/utils/chartExport.js frontend/tests/unit/utils/chartExport.spec.js
git commit -m "feat(charts): exportSvgAsPng with computed-style inlining"
```

---

## Task 6: useChartAccessibility composable (TDD)

**Files:**
- Create: `frontend/src/composables/useChartAccessibility.js`
- Create: `frontend/tests/unit/composables/useChartAccessibility.spec.js`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/unit/composables/useChartAccessibility.spec.js`:

```js
import { describe, it, expect } from 'vitest';
import { ref } from 'vue';
import { useChartAccessibility } from '@/composables/useChartAccessibility';

describe('useChartAccessibility', () => {
  it('returns role="img" plus stable labelledby/describedby IDs', () => {
    const summary = ref('Donut chart with 3 segments.');
    const { titleId, descId, ariaProps } = useChartAccessibility({
      chartName: 'Sex distribution',
      summary,
    });
    expect(ariaProps.role).toBe('img');
    expect(ariaProps['aria-labelledby']).toBe(titleId);
    expect(ariaProps['aria-describedby']).toBe(descId);
    expect(titleId).toMatch(/^chart-title-\d+$/);
    expect(descId).toMatch(/^chart-desc-\d+$/);
  });

  it('produces unique IDs across multiple instances', () => {
    const a = useChartAccessibility({ chartName: 'A', summary: ref('') });
    const b = useChartAccessibility({ chartName: 'B', summary: ref('') });
    expect(a.titleId).not.toBe(b.titleId);
    expect(a.descId).not.toBe(b.descId);
  });

  it('exposes the summary ref unchanged for template binding', () => {
    const summary = ref('first');
    const { description } = useChartAccessibility({ chartName: 'X', summary });
    expect(description.value).toBe('first');
    summary.value = 'second';
    expect(description.value).toBe('second');
  });
});
```

- [ ] **Step 2: Run and confirm failure**

```
npm test -- useChartAccessibility
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `frontend/src/composables/useChartAccessibility.js`:

```js
/**
 * Per-chart accessibility helpers: generates stable unique IDs for ARIA
 * title/description, returns a prop bundle the chart spreads onto its
 * wrapper, and exposes the summary ref for binding into a visually-hidden
 * description element.
 *
 * @param {{ chartName: string, summary: import('vue').Ref<string> }} options
 * @returns {{
 *   titleId: string,
 *   descId: string,
 *   description: import('vue').Ref<string>,
 *   ariaProps: { role: string, 'aria-labelledby': string, 'aria-describedby': string },
 * }}
 */
let counter = 0;

export function useChartAccessibility({ chartName: _chartName, summary }) {
  counter += 1;
  const titleId = `chart-title-${counter}`;
  const descId = `chart-desc-${counter}`;
  return {
    titleId,
    descId,
    description: summary,
    ariaProps: {
      role: 'img',
      'aria-labelledby': titleId,
      'aria-describedby': descId,
    },
  };
}
```

- [ ] **Step 4: Run and confirm pass**

```
npm test -- useChartAccessibility
```
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```
git add frontend/src/composables/useChartAccessibility.js frontend/tests/unit/composables/useChartAccessibility.spec.js
git commit -m "feat(charts): useChartAccessibility composable for ARIA IDs"
```

---

## Task 7: ChartExportMenu component (TDD)

**Files:**
- Create: `frontend/src/components/analyses/ChartExportMenu.vue`
- Create: `frontend/tests/unit/components/analyses/ChartExportMenu.spec.js`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/unit/components/analyses/ChartExportMenu.spec.js`:

```js
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import ChartExportMenu from '@/components/analyses/ChartExportMenu.vue';

const vuetify = createVuetify({ components, directives });

vi.mock('@/utils/chartExport', () => ({
  exportSvgAsPng: vi.fn().mockResolvedValue(),
  exportSvgAsSvg: vi.fn(),
  exportDataAsCsv: vi.fn(),
  buildExportFilename: vi.fn((name, ext) => `hnf1b-db_${name}_${ext}`),
}));

const announceMock = vi.fn();
vi.mock('@/composables/useAccessibility', () => ({
  useAnnouncer: () => ({ announce: announceMock }),
}));

import {
  exportSvgAsPng,
  exportSvgAsSvg,
  exportDataAsCsv,
} from '@/utils/chartExport';

describe('ChartExportMenu', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function makeWrapper(propsOverrides = {}) {
    const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    return mount(ChartExportMenu, {
      global: { plugins: [vuetify] },
      props: {
        svgEl,
        rows: [{ a: 1 }],
        columns: [{ key: 'a', label: 'A' }],
        chartName: 'Test Chart',
        ...propsOverrides,
      },
    });
  }

  it('disables the menu button when svgEl is null', () => {
    const wrapper = mount(ChartExportMenu, {
      global: { plugins: [vuetify] },
      props: {
        svgEl: null,
        rows: [],
        columns: [],
        chartName: 'Test',
      },
    });
    const btn = wrapper.find('button');
    expect(btn.attributes('disabled')).toBeDefined();
  });

  it('invokes PNG export and announces on click', async () => {
    const wrapper = makeWrapper();
    await wrapper.vm.exportPng();
    expect(exportSvgAsPng).toHaveBeenCalledOnce();
    expect(announceMock).toHaveBeenCalledWith('Chart exported as PNG');
  });

  it('invokes CSV export and announces on click', async () => {
    const wrapper = makeWrapper();
    await wrapper.vm.exportCsv();
    expect(exportDataAsCsv).toHaveBeenCalledOnce();
    expect(announceMock).toHaveBeenCalledWith('Chart exported as CSV');
  });

  it('invokes SVG export and announces on click', async () => {
    const wrapper = makeWrapper();
    await wrapper.vm.exportSvg();
    expect(exportSvgAsSvg).toHaveBeenCalledOnce();
    expect(announceMock).toHaveBeenCalledWith('Chart exported as SVG');
  });
});
```

- [ ] **Step 2: Run and confirm failure**

```
npm test -- ChartExportMenu
```
Expected: FAIL — component not found.

- [ ] **Step 3: Implement**

Create `frontend/src/components/analyses/ChartExportMenu.vue`:

```vue
<template>
  <v-menu offset="4">
    <template #activator="{ props: activator }">
      <v-btn
        v-bind="activator"
        :disabled="!svgEl"
        icon="mdi-download"
        size="small"
        variant="text"
        :aria-label="`Export ${chartName}`"
        class="chart-export-menu__btn"
      />
    </template>
    <v-list density="compact">
      <v-list-item @click="exportPng">
        <v-list-item-title>Export as PNG</v-list-item-title>
      </v-list-item>
      <v-list-item @click="exportCsv">
        <v-list-item-title>Export as CSV</v-list-item-title>
      </v-list-item>
      <v-list-item @click="exportSvg">
        <v-list-item-title>Export as SVG</v-list-item-title>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script setup>
import {
  exportSvgAsPng,
  exportSvgAsSvg,
  exportDataAsCsv,
  buildExportFilename,
} from '@/utils/chartExport';
import { useAnnouncer } from '@/composables/useAccessibility';

const props = defineProps({
  svgEl: { type: [Object, Function], default: null },
  rows: { type: Array, default: () => [] },
  columns: { type: Array, default: () => [] },
  chartName: { type: String, required: true },
});

const { announce } = useAnnouncer();

function resolveSvg() {
  return typeof props.svgEl === 'function' ? props.svgEl() : props.svgEl;
}

async function exportPng() {
  const svg = resolveSvg();
  if (!svg) return;
  await exportSvgAsPng(svg, { filename: buildExportFilename(props.chartName, 'png') });
  announce('Chart exported as PNG');
}

function exportCsv() {
  exportDataAsCsv(props.rows, props.columns, buildExportFilename(props.chartName, 'csv'));
  announce('Chart exported as CSV');
}

function exportSvg() {
  const svg = resolveSvg();
  if (!svg) return;
  exportSvgAsSvg(svg, buildExportFilename(props.chartName, 'svg'));
  announce('Chart exported as SVG');
}

defineExpose({ exportPng, exportCsv, exportSvg });
</script>

<style scoped>
.chart-export-menu__btn {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 1;
}
</style>
```

- [ ] **Step 4: Run and confirm pass**

```
npm test -- ChartExportMenu
```
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```
git add frontend/src/components/analyses/ChartExportMenu.vue frontend/tests/unit/components/analyses/ChartExportMenu.spec.js
git commit -m "feat(charts): ChartExportMenu Vuetify dropdown"
```

---

## Task 8: Wire DonutChart (reference implementation)

**Files:**
- Modify: `frontend/src/components/analyses/DonutChart.vue`

This is the reference chart. The same wiring pattern repeats for Tasks 9–14 with chart-specific summary/rows/columns code.

- [ ] **Step 1: Add Composition-API setup hooks alongside existing Options API**

Modify `frontend/src/components/analyses/DonutChart.vue`. Replace the `<script>` opening through the `data()` block so the file reads:

```vue
<script>
import * as d3 from 'd3';
import { ref, computed } from 'vue';
import ChartExportMenu from '@/components/analyses/ChartExportMenu.vue';
import { useChartAccessibility } from '@/composables/useChartAccessibility';

export default {
  name: 'DonutChart',
  components: { ChartExportMenu },
  props: {
    chartData: { type: Object, required: true },
    width: { type: Number, default: 600 },
    height: { type: Number, default: 500 },
    margin: { type: Number, default: 50 },
    colorScheme: {
      type: Array,
      default: () => [...d3.schemeCategory10, ...d3.schemePaired],
    },
    colorMap: { type: Object, default: null },
    chartName: { type: String, default: 'Donut chart' },
  },
  setup(props) {
    const svgEl = ref(null);
    const exportRows = computed(() => {
      const entries = props.chartData?.grouped_counts ?? [];
      const total = props.chartData?.total_count
        ?? entries.reduce((s, e) => s + e.count, 0);
      return entries.map((e) => ({
        group: e._id,
        count: e.count,
        percent: total ? ((e.count / total) * 100).toFixed(1) : '0.0',
      }));
    });
    const exportColumns = [
      { key: 'group', label: 'Group' },
      { key: 'count', label: 'Count' },
      { key: 'percent', label: 'Percent' },
    ];
    const summary = computed(() => {
      const entries = props.chartData?.grouped_counts ?? [];
      const total = props.chartData?.total_count
        ?? entries.reduce((s, e) => s + e.count, 0);
      if (!entries.length) return `${props.chartName}: no data.`;
      const parts = entries.map(
        (e) => `${e._id}: ${e.count} (${total ? ((e.count / total) * 100).toFixed(1) : '0.0'}%)`
      );
      return `${props.chartName}. ${parts.join(', ')}. Total ${total}.`;
    });
    const a11y = useChartAccessibility({ chartName: props.chartName, summary });
    return { svgEl, exportRows, exportColumns, ...a11y };
  },
  data() {
    return {};
  },
```

Keep the rest of the file (`watch`, `mounted`, `methods.renderChart`) unchanged for now. (Note: the `data()` block is now empty since we removed `mdiDownload` — it was unused. Leave the empty `data()` so existing tests that probe `vm.$data` don't break.)

- [ ] **Step 2: Capture the SVG element from renderChart**

In `methods.renderChart`, change the SVG creation block. Find:

```js
const svg = d3
  .select(this.$refs.chart)
  .append('svg')
  .attr('width', width)
  .attr('height', height)
  .attr('viewBox', `0 0 ${width} ${height}`)
  .attr('preserveAspectRatio', 'xMinYMin meet')
  .append('g')
  .attr('transform', `translate(${width / 2}, ${height / 2})`);
```

Replace with:

```js
const svgRoot = d3
  .select(this.$refs.chart)
  .append('svg')
  .attr('width', width)
  .attr('height', height)
  .attr('viewBox', `0 0 ${width} ${height}`)
  .attr('preserveAspectRatio', 'xMinYMin meet');
this.svgEl = svgRoot.node();
const svg = svgRoot
  .append('g')
  .attr('transform', `translate(${width / 2}, ${height / 2})`);
```

- [ ] **Step 3: Replace the template with the accessibility-wrapped version**

Replace the entire `<template>` block at the top of the file with:

```vue
<template>
  <div class="donut-chart-container" v-bind="ariaProps">
    <span :id="titleId" class="sr-only">{{ chartName }}</span>
    <span :id="descId" class="sr-only">{{ description }}</span>
    <ChartExportMenu
      :svg-el="svgEl"
      :rows="exportRows"
      :columns="exportColumns"
      :chart-name="chartName"
    />
    <div class="chart-wrapper">
      <div ref="chart" class="chart" aria-hidden="true" />
      <div ref="legend" class="legend" />
    </div>
    <details class="chart-data-table">
      <summary>View data as table</summary>
      <table>
        <thead>
          <tr><th v-for="c in exportColumns" :key="c.key">{{ c.label }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in exportRows" :key="i">
            <td v-for="c in exportColumns" :key="c.key">{{ r[c.key] }}</td>
          </tr>
        </tbody>
      </table>
    </details>
  </div>
</template>
```

- [ ] **Step 4: Append shared chart-styling to the `<style scoped>` block**

Append to the bottom of the existing `<style scoped>` block (before the closing `</style>`):

```css
.donut-chart-container {
  position: relative;
}

.chart-data-table {
  margin-top: 16px;
  font-size: 14px;
}
.chart-data-table summary {
  cursor: pointer;
  padding: 4px 0;
  color: rgb(var(--v-theme-on-surface), 0.7);
}
.chart-data-table table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
}
.chart-data-table th,
.chart-data-table td {
  padding: 4px 8px;
  border: 1px solid rgb(var(--v-theme-on-surface), 0.12);
  text-align: left;
}
```

- [ ] **Step 5: Run the analyses tests**

```
npm test -- analyses
```
Expected: PASS (no analyses-specific test exists for DonutChart yet; this just confirms nothing breaks).

- [ ] **Step 6: Visual smoke test (dev server)**

In one terminal: `cd frontend && npm run dev`. Open `/aggregations` (or wherever DonutChart is used). Confirm:
- Export button (mdi-download) appears top-right of donut
- Clicking it opens a 3-item menu
- Each export triggers a download
- A `<details>` row appears below the chart with the data table

- [ ] **Step 7: Commit**

```
git add frontend/src/components/analyses/DonutChart.vue
git commit -m "feat(charts): wire export + a11y into DonutChart"
```

---

## Task 9: Wire StackedBarChart

**Files:**
- Modify: `frontend/src/components/analyses/StackedBarChart.vue`

- [ ] **Step 1: Add setup hooks for export rows + summary**

In `frontend/src/components/analyses/StackedBarChart.vue`, modify the `<script>` block. Add these imports at the top:

```js
import { ref, computed } from 'vue';
import ChartExportMenu from '@/components/analyses/ChartExportMenu.vue';
import { useChartAccessibility } from '@/composables/useChartAccessibility';
```

Register the component (`components: { ChartExportMenu }`) and add a `chartName` prop with default `'Phenotypic features'`. Then add a `setup(props)` block:

```js
setup(props) {
  const svgEl = ref(null);
  const exportRows = computed(() => {
    const limited = (props.chartData || []).slice(0, props.displayLimit);
    return limited.map((row) => ({
      feature: row.label,
      present: row.details?.present_count ?? 0,
      absent: row.details?.absent_count ?? 0,
      not_reported: row.details?.not_reported_count ?? 0,
    }));
  });
  const exportColumns = [
    { key: 'feature', label: 'Feature' },
    { key: 'present', label: 'Present' },
    { key: 'absent', label: 'Absent' },
    { key: 'not_reported', label: 'Not reported' },
  ];
  const summary = computed(() => {
    const rows = exportRows.value;
    if (!rows.length) return `${props.chartName}: no data.`;
    const top = rows.slice(0, 5).map(
      (r) => `${r.feature}: ${r.present} present, ${r.absent} absent`
    );
    const tail = rows.length > 5 ? ` and ${rows.length - 5} more, available in the data table` : '';
    return `${props.chartName} across ${rows.length} entries. ${top.join('; ')}${tail}.`;
  });
  const a11y = useChartAccessibility({ chartName: props.chartName, summary });
  return { svgEl, exportRows, exportColumns, ...a11y };
},
```

- [ ] **Step 2: Capture the SVG node in renderChart**

In `methods.renderChart`, locate the line creating the `<svg>` (likely starting `const svg = d3.select(this.$refs.chart).append('svg')`). Split it so the root SVG is captured and assigned:

```js
const svgRoot = d3
  .select(this.$refs.chart)
  .append('svg')
  .attr('width', width)
  .attr('height', height);
this.svgEl = svgRoot.node();
const svg = svgRoot
  .append('g')
  .attr('transform', `translate(${margin.left},${margin.top})`);
```

(Adjust the inner `g` translate to match whatever the existing code uses — keep the existing structure, just split the chain so `svgRoot.node()` is captured.)

- [ ] **Step 3: Replace template**

Replace the `<template>` block with:

```vue
<template>
  <div class="stacked-bar-chart-container" v-bind="ariaProps">
    <span :id="titleId" class="sr-only">{{ chartName }}</span>
    <span :id="descId" class="sr-only">{{ description }}</span>
    <ChartExportMenu
      :svg-el="svgEl"
      :rows="exportRows"
      :columns="exportColumns"
      :chart-name="chartName"
    />
    <div ref="chart" aria-hidden="true" />
    <details class="chart-data-table">
      <summary>View data as table</summary>
      <table>
        <thead>
          <tr><th v-for="c in exportColumns" :key="c.key">{{ c.label }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in exportRows" :key="i">
            <td v-for="c in exportColumns" :key="c.key">{{ r[c.key] }}</td>
          </tr>
        </tbody>
      </table>
    </details>
  </div>
</template>
```

- [ ] **Step 4: Append shared styles**

Add this `<style scoped>` block (or append to existing one):

```css
.stacked-bar-chart-container { position: relative; }
.chart-data-table { margin-top: 16px; font-size: 14px; }
.chart-data-table summary { cursor: pointer; padding: 4px 0; color: rgb(var(--v-theme-on-surface), 0.7); }
.chart-data-table table { width: 100%; border-collapse: collapse; margin-top: 8px; }
.chart-data-table th, .chart-data-table td {
  padding: 4px 8px;
  border: 1px solid rgb(var(--v-theme-on-surface), 0.12);
  text-align: left;
}
```

- [ ] **Step 5: Run tests**

```
npm test -- analyses
```
Expected: PASS (no StackedBar spec exists; just confirms nothing else breaks).

- [ ] **Step 6: Commit**

```
git add frontend/src/components/analyses/StackedBarChart.vue
git commit -m "feat(charts): wire export + a11y into StackedBarChart"
```

---

## Task 10: Wire BoxPlotChart

**Files:**
- Modify: `frontend/src/components/analyses/BoxPlotChart.vue`

- [ ] **Step 1: Read the current file to find existing data shape**

Read `frontend/src/components/analyses/BoxPlotChart.vue` end-to-end so you know the props (likely `boxPlotData` or `chartData`) and the structure of each box (median, q1, q3, min, max, label).

- [ ] **Step 2: Add setup hooks**

Add imports at the top of `<script>`:

```js
import { ref, computed } from 'vue';
import ChartExportMenu from '@/components/analyses/ChartExportMenu.vue';
import { useChartAccessibility } from '@/composables/useChartAccessibility';
```

Register `ChartExportMenu` in `components`. Add a `chartName` prop (default `'DNA distance by domain'`). Add a `setup(props)` block:

```js
setup(props) {
  const svgEl = ref(null);
  const data = computed(() => props.chartData || props.boxPlotData || []);
  const exportRows = computed(() =>
    data.value.map((d) => ({
      label: d.label,
      n: d.values?.length ?? d.n ?? '',
      min: d.min,
      q1: d.q1,
      median: d.median,
      q3: d.q3,
      max: d.max,
    }))
  );
  const exportColumns = [
    { key: 'label', label: 'Group' },
    { key: 'n', label: 'N' },
    { key: 'min', label: 'Min' },
    { key: 'q1', label: 'Q1' },
    { key: 'median', label: 'Median' },
    { key: 'q3', label: 'Q3' },
    { key: 'max', label: 'Max' },
  ];
  const summary = computed(() => {
    const rows = exportRows.value;
    if (!rows.length) return `${props.chartName}: no data.`;
    const parts = rows.map(
      (r) => `${r.label}: median ${r.median}, IQR ${r.q1}–${r.q3}, n=${r.n}`
    );
    return `${props.chartName}. ${parts.join('; ')}.`;
  });
  const a11y = useChartAccessibility({ chartName: props.chartName, summary });
  return { svgEl, exportRows, exportColumns, ...a11y };
},
```

(If the actual prop name differs from `chartData`/`boxPlotData`, adjust the `data` computed accordingly. Use only props that already exist on the component.)

- [ ] **Step 3: Capture SVG node in renderChart**

Apply the same `svgRoot.node()` split shown in Task 8 Step 2 to the existing SVG creation chain.

- [ ] **Step 4: Replace template wrapper**

Replace the outer template `<div>` with the same accessibility wrapper used in Task 9 Step 3, swapping the container class to `.box-plot-chart-container`:

```vue
<template>
  <div class="box-plot-chart-container" v-bind="ariaProps">
    <span :id="titleId" class="sr-only">{{ chartName }}</span>
    <span :id="descId" class="sr-only">{{ description }}</span>
    <ChartExportMenu :svg-el="svgEl" :rows="exportRows" :columns="exportColumns" :chart-name="chartName" />
    <div ref="chart" aria-hidden="true" />
    <details class="chart-data-table">
      <summary>View data as table</summary>
      <table>
        <thead><tr><th v-for="c in exportColumns" :key="c.key">{{ c.label }}</th></tr></thead>
        <tbody>
          <tr v-for="(r, i) in exportRows" :key="i">
            <td v-for="c in exportColumns" :key="c.key">{{ r[c.key] }}</td>
          </tr>
        </tbody>
      </table>
    </details>
  </div>
</template>
```

- [ ] **Step 5: Append shared styles** (same block as Task 9 Step 4, swap the container class):

```css
.box-plot-chart-container { position: relative; }
.chart-data-table { margin-top: 16px; font-size: 14px; }
.chart-data-table summary { cursor: pointer; padding: 4px 0; color: rgb(var(--v-theme-on-surface), 0.7); }
.chart-data-table table { width: 100%; border-collapse: collapse; margin-top: 8px; }
.chart-data-table th, .chart-data-table td {
  padding: 4px 8px;
  border: 1px solid rgb(var(--v-theme-on-surface), 0.12);
  text-align: left;
}
```

- [ ] **Step 6: Run tests**

```
npm test -- analyses
```
Expected: PASS.

- [ ] **Step 7: Commit**

```
git add frontend/src/components/analyses/BoxPlotChart.vue
git commit -m "feat(charts): wire export + a11y into BoxPlotChart"
```

---

## Task 11: Wire PublicationsTimelineChart

**Files:**
- Modify: `frontend/src/components/analyses/PublicationsTimelineChart.vue`

- [ ] **Step 1: Read the file to confirm props and data shape**

The data is likely an array of `{ year, count }` or similar.

- [ ] **Step 2: Add setup hooks**

Add imports + `components` registration as in Task 9. Add `chartName` prop (default `'Publications per year'`). Add `setup(props)`:

```js
setup(props) {
  const svgEl = ref(null);
  const data = computed(() => props.chartData || []);
  const exportRows = computed(() =>
    data.value.map((d) => ({ year: d.year ?? d._id, count: d.count }))
  );
  const exportColumns = [
    { key: 'year', label: 'Year' },
    { key: 'count', label: 'Publications' },
  ];
  const summary = computed(() => {
    const rows = exportRows.value;
    if (!rows.length) return `${props.chartName}: no data.`;
    const total = rows.reduce((s, r) => s + (r.count || 0), 0);
    const peak = rows.reduce((m, r) => (r.count > m.count ? r : m), rows[0]);
    const firstYear = rows[0].year;
    const lastYear = rows[rows.length - 1].year;
    return `${props.chartName}, ${firstYear}–${lastYear}. Peak ${peak.count} in ${peak.year}. Total ${total} publications.`;
  });
  const a11y = useChartAccessibility({ chartName: props.chartName, summary });
  return { svgEl, exportRows, exportColumns, ...a11y };
},
```

(If the data shape differs — e.g., uses `_id` for year — keep the computed mapping above as written; it already supports both.)

- [ ] **Step 3: Capture SVG node** — same split as Task 8 Step 2 applied to the existing SVG creation chain.

- [ ] **Step 4: Replace template** — same wrapper as Task 10 Step 4 with container class `.publications-timeline-chart-container`.

- [ ] **Step 5: Append shared styles** — same block as Task 10 Step 5 with the container class renamed.

- [ ] **Step 6: Run tests**

```
npm test -- analyses
```
Expected: PASS.

- [ ] **Step 7: Commit**

```
git add frontend/src/components/analyses/PublicationsTimelineChart.vue
git commit -m "feat(charts): wire export + a11y into PublicationsTimelineChart"
```

---

## Task 12: Wire KaplanMeierChart (existing spec must stay green)

**Files:**
- Modify: `frontend/src/components/analyses/KaplanMeierChart.vue`
- Modify: `frontend/tests/unit/components/KaplanMeierChart.spec.js` (only if it asserts template structure that changes)

- [ ] **Step 1: Read the existing KaplanMeier spec**

Run `cat frontend/tests/unit/components/KaplanMeierChart.spec.js` and note which template selectors or props it asserts.

- [ ] **Step 2: Add setup hooks**

Add imports + `components` registration + `chartName` prop default `'Survival curve'`. Add `setup(props)`:

```js
setup(props) {
  const svgEl = ref(null);
  const curve = computed(() => props.chartData?.curve ?? props.chartData ?? []);
  const exportRows = computed(() =>
    curve.value.map((p) => ({
      time: p.time,
      survival: p.survival,
      n_at_risk: p.n_at_risk ?? p.atRisk ?? '',
      events: p.events ?? '',
    }))
  );
  const exportColumns = [
    { key: 'time', label: 'Time' },
    { key: 'survival', label: 'Survival probability' },
    { key: 'n_at_risk', label: 'N at risk' },
    { key: 'events', label: 'Events' },
  ];
  const summary = computed(() => {
    const rows = exportRows.value;
    if (!rows.length) return `${props.chartName}: no data.`;
    const totalEvents = rows.reduce((s, r) => s + (Number(r.events) || 0), 0);
    const lastSurvival = rows[rows.length - 1].survival;
    return `${props.chartName}. ${rows.length} time points; final survival probability ${lastSurvival}; ${totalEvents} events.`;
  });
  const a11y = useChartAccessibility({ chartName: props.chartName, summary });
  return { svgEl, exportRows, exportColumns, ...a11y };
},
```

(Adjust the `curve` and field names to match the existing component's actual data shape — read the renderChart method first to find them.)

- [ ] **Step 3: Capture SVG node** — same split as Task 8 Step 2.

- [ ] **Step 4: Replace template** — same wrapper as Task 10 Step 4 with container class `.kaplan-meier-chart-container`.

- [ ] **Step 5: Append shared styles** — same block, container class renamed.

- [ ] **Step 6: Run the KaplanMeier spec**

```
npm test -- KaplanMeierChart
```
Expected: PASS. If selectors changed (e.g., spec asserted `.km-container` directly), update the test to match the new structure — the contract is the rendered chart, not the class name.

- [ ] **Step 7: Commit**

```
git add frontend/src/components/analyses/KaplanMeierChart.vue frontend/tests/unit/components/KaplanMeierChart.spec.js
git commit -m "feat(charts): wire export + a11y into KaplanMeierChart"
```

---

## Task 13: Wire VariantComparisonChart (existing spec must stay green)

**Files:**
- Modify: `frontend/src/components/analyses/VariantComparisonChart.vue`
- Modify: `frontend/tests/unit/components/VariantComparisonChart.spec.js` (only if necessary)

- [ ] **Step 1: Read the existing VariantComparison spec**

Note the props and template assertions.

- [ ] **Step 2: Add setup hooks**

Add imports + registration + `chartName` prop default `'Variant comparison'`. Add `setup(props)`:

```js
setup(props) {
  const svgEl = ref(null);
  const data = computed(() => props.chartData || []);
  const exportRows = computed(() =>
    data.value.map((d) => ({ category: d.label ?? d._id, count: d.count }))
  );
  const exportColumns = [
    { key: 'category', label: 'Category' },
    { key: 'count', label: 'Count' },
  ];
  const summary = computed(() => {
    const rows = exportRows.value;
    if (!rows.length) return `${props.chartName}: no data.`;
    const total = rows.reduce((s, r) => s + (r.count || 0), 0);
    const parts = rows.map((r) => `${r.category}: ${r.count}`);
    return `${props.chartName}. ${parts.join(', ')}. Total ${total}.`;
  });
  const a11y = useChartAccessibility({ chartName: props.chartName, summary });
  return { svgEl, exportRows, exportColumns, ...a11y };
},
```

(Adjust the row mapping to match the actual data shape this chart accepts.)

- [ ] **Step 3: Capture SVG node** — same split as Task 8 Step 2.

- [ ] **Step 4: Replace template** — same wrapper as Task 10 Step 4 with container class `.variant-comparison-chart-container`.

- [ ] **Step 5: Append shared styles** — same block, container class renamed.

- [ ] **Step 6: Run the VariantComparison spec**

```
npm test -- VariantComparisonChart
```
Expected: PASS. Update selectors in the spec if necessary.

- [ ] **Step 7: Commit**

```
git add frontend/src/components/analyses/VariantComparisonChart.vue frontend/tests/unit/components/VariantComparisonChart.spec.js
git commit -m "feat(charts): wire export + a11y into VariantComparisonChart"
```

---

## Task 14: Wire DNADistanceAnalysis

**Files:**
- Modify: `frontend/src/components/analyses/DNADistanceAnalysis.vue`

- [ ] **Step 1: Read the file**

This is an analysis container that may compose multiple D3 panels. Identify the primary `<svg>` (if multiple, expose the main one — for example the violin/box panel). If the file delegates to child chart components already covered (BoxPlotChart etc.), this task may reduce to passing a `chartName` prop through and not adding its own wrapper.

- [ ] **Step 2: Decide wrap-vs-delegate**

If the file renders its own primary SVG, follow Steps 3–7 below to wrap it. If it only composes other charts that already have wrappers, instead just ensure each composed chart receives a `chart-name` prop appropriate to context, and skip to Step 8.

- [ ] **Step 3: Add setup hooks**

Add imports + registration + `chartName` prop default `'DNA distance analysis'`. Add `setup(props)`:

```js
setup(props) {
  const svgEl = ref(null);
  const variants = computed(() => props.variants || props.chartData || []);
  const exportRows = computed(() =>
    variants.value.map((v) => ({
      variant: v.variant_id ?? v.hgvs ?? v.id,
      distance: v.distance,
      domain: v.domain ?? '',
    }))
  );
  const exportColumns = [
    { key: 'variant', label: 'Variant' },
    { key: 'distance', label: 'DNA distance (bp)' },
    { key: 'domain', label: 'Domain' },
  ];
  const summary = computed(() => {
    const rows = exportRows.value;
    if (!rows.length) return `${props.chartName}: no data.`;
    const distances = rows.map((r) => Number(r.distance)).filter(Number.isFinite);
    if (!distances.length) return `${props.chartName}: ${rows.length} variants (distances unavailable).`;
    const sorted = [...distances].sort((a, b) => a - b);
    const median = sorted[Math.floor(sorted.length / 2)];
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    return `${props.chartName}. ${rows.length} variants. Median distance ${median} bp, range ${min}–${max}.`;
  });
  const a11y = useChartAccessibility({ chartName: props.chartName, summary });
  return { svgEl, exportRows, exportColumns, ...a11y };
},
```

- [ ] **Step 4: Capture SVG node** — same split as Task 8 Step 2.

- [ ] **Step 5: Replace template** — same wrapper as Task 10 Step 4 with container class `.dna-distance-analysis-container`.

- [ ] **Step 6: Append shared styles** — same block, container class renamed.

- [ ] **Step 7: Run tests**

```
npm test -- analyses
```
Expected: PASS.

- [ ] **Step 8: Commit**

```
git add frontend/src/components/analyses/DNADistanceAnalysis.vue
git commit -m "feat(charts): wire export + a11y into DNADistanceAnalysis"
```

---

## Task 15: Manual verification gates and PR

**Files:** none (verification only)

- [ ] **Step 1: Full Vitest run**

```
cd frontend && npm test
```
Expected: all unit tests pass (including pre-existing ones for KaplanMeierChart, VariantComparisonChart, ExternalLink).

- [ ] **Step 2: Lint + format**

```
npm run lint
npm run format
```
Expected: no errors, no formatting changes left unstaged. If `format` rewrote anything, `git add` + amend the previous commit, or add a small `chore: prettier` commit.

- [ ] **Step 3: axe-core scan via existing Playwright a11y job**

```
npx playwright test tests/e2e/accessibility.spec.js
```
Expected: PASS. If the spec lists pages, ensure `/aggregations` is included; if not, add the page to its test list.

- [ ] **Step 4: Manual NVDA spot-check (Windows)**

- Start dev server: `npm run dev`
- Open `/aggregations` in Chrome with NVDA running
- Tab to the donut chart; NVDA should announce the chart name + summary
- Tab to the "View data as table" `<summary>`; expand with Enter; arrow through the table

If NVDA reads only "graphic" with no description, re-check that `aria-labelledby` and `aria-describedby` point to actual `<span class="sr-only">` siblings inside the wrapper.

- [ ] **Step 5: Manual PNG / CSV export check**

- Open the donut chart, export PNG. Open the file; verify crisp at 2× DPR, white background, legend visible.
- Export CSV. Open in Excel (or LibreOffice). Verify UTF-8 characters render correctly and Excel does not garble the BOM.

- [ ] **Step 6: Open PR**

```
git push -u origin <branch>
gh pr create --title "feat(charts): export (PNG/CSV/SVG) + a11y across analyses charts" --body "$(cat <<'EOF'
## Summary
- Closes #135 (ARIA labels and accessibility support for charts)
- Closes #136 (chart data export — CSV, PNG)
- Adds PNG (2× DPR), CSV (RFC 4180 + BOM), and raw SVG export to 7 chart components
- Wraps each chart in an ARIA-described container with a `<details>` data-table fallback (WCAG 2.1 A: 1.1.1, 1.4.1, 2.1.1)
- Promotes `.sr-only` to the global stylesheet

Spec: `docs/superpowers/specs/2026-05-11-chart-export-and-a11y-design.md`
Plan: `docs/superpowers/plans/2026-05-11-chart-export-and-a11y.md`

## Out of scope (deliberate, separate issues)
- Colorblind pattern fills (data table fallback satisfies 1.4.1)
- Options-API → `<script setup>` rewrite
- Chart animations (#139), service-worker caching (#138)

## Test plan
- [x] Vitest: chartExport (8 cases), useChartAccessibility (3 cases), ChartExportMenu (4 cases)
- [x] Pre-existing specs for KaplanMeierChart, VariantComparisonChart still pass
- [x] Playwright a11y job (axe-core) on /aggregations green
- [x] NVDA spot-check confirms title + description announced
- [x] PNG export crisp at 2× DPR; CSV opens correctly in Excel
EOF
)"
```

- [ ] **Step 7: Verify CI green**

Watch the PR's GitHub Actions. If any job fails, investigate and fix before requesting review.

---

## Self-Review

**Spec coverage check (against `docs/superpowers/specs/2026-05-11-chart-export-and-a11y-design.md`):**
- 7 chart components updated → Tasks 8–14 (one per chart) ✓
- `chartExport.js` (PNG/CSV/SVG + filename) → Tasks 2–5 ✓
- `ChartExportMenu.vue` → Task 7 ✓
- `useChartAccessibility.js` → Task 6 ✓
- `.sr-only` global → Task 1 ✓
- Native SVG→PNG, no new deps → Task 5 uses `file-saver` (already installed) + native serialization ✓
- RFC 4180 CSV with BOM → Task 3 ✓
- `<details>` data-table fallback → Tasks 8–14 each include it ✓
- `aria-hidden` on D3-managed subtree → Tasks 8–14 each apply it ✓
- Announcer integration on export → Task 7 ✓
- Manual NVDA + axe + PNG/CSV check → Task 15 ✓

**Placeholder scan:** no TBDs, no "implement later", no "similar to Task N" without code repetition. Every chart task repeats the full wrapper template and the chart-specific summary code.

**Type / name consistency:** `svgEl` ref, `exportRows`/`exportColumns` computed/static, `ariaProps`/`titleId`/`descId`/`description` from `useChartAccessibility` — all spelled identically across tasks. `buildExportFilename(name, ext)` signature consistent everywhere. `useAnnouncer().announce(msg)` matches the existing composable (see `frontend/src/composables/useAccessibility.js:147–181`).
