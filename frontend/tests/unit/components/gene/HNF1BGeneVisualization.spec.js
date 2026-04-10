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
import { describe, it, expect, vi } from 'vitest';
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

// Sample variants using hg38 coordinates within the HNF1B gene region
// (chr17:37,686,430-37,745,059). extractVariantPosition() parses the
// hg38 field via the `chr\d+-\d+-` pattern to determine marker placement.
const sampleVariants = [
  {
    variant_id: 'VAR-001',
    hg38: 'chr17-37741000-G-A',
    hgvs_c: 'NM_000458.4:c.100G>A',
    classificationVerdict: 'PATHOGENIC',
    phenopacket_count: 5,
  },
  {
    variant_id: 'VAR-002',
    hg38: 'chr17-37733700-A-T',
    hgvs_c: 'NM_000458.4:c.600A>T',
    classificationVerdict: 'LIKELY_PATHOGENIC',
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
    // SNV variants are rendered as <circle class="variant-circle"> per
    // the current template (gene/HNF1BGeneVisualization.vue ~line 399).
    const markers = wrapper.findAll(
      '[data-testid="variant-marker"], .variant-circle, circle.variant'
    );
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
