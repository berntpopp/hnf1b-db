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

  it('exports the full untruncated matrix even when the on-screen display is capped', () => {
    const many = {
      phenopacketId: 'p-z',
      subjectId: 'Z',
      features: Array.from({ length: 4 }, (_, i) => f(`HP:000010${i}`, `Term ${i}`)),
    };
    const w = mountHeatmap({ individuals: [many], chartName: 'H', maxTerms: 2 });
    // On-screen display is capped to 2 term columns…
    expect(w.vm.matrix.columns).toHaveLength(2);
    expect(w.vm.matrix.truncated).toBe(true);
    // …but the CSV export carries all 4 terms plus the leading 'individual' column.
    expect(w.vm.exportColumns).toHaveLength(5);
  });
});
