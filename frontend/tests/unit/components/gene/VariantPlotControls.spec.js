/**
 * Unit tests for the shared VariantPlotControls control bar.
 */
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import VariantPlotControls from '@/components/gene/VariantPlotControls.vue';
import { createDefaultFilterState } from '@/utils/variantFilters';

const variants = [
  { classificationVerdict: 'PATHOGENIC', molecular_consequence: 'Missense' },
  { classificationVerdict: 'VUS', molecular_consequence: 'Missense' },
  { classificationVerdict: 'PATHOGENIC', molecular_consequence: 'Copy Number Loss' },
];

function makeWrapper(modelValue = createDefaultFilterState()) {
  const vuetify = createVuetify({ components, directives });
  return mount(VariantPlotControls, {
    props: { modelValue, variants },
    global: { plugins: [vuetify] },
  });
}

describe('VariantPlotControls', () => {
  it('renders a colour-by toggle and both filter rows', () => {
    const wrapper = makeWrapper();
    expect(wrapper.find('[data-testid="colorby-classification"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="colorby-consequence"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="filter-row-pathogenicity"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="filter-row-consequence"]').exists()).toBe(true);
  });

  it('renders only the categories present in the data, with counts', () => {
    const wrapper = makeWrapper();
    expect(wrapper.find('[data-testid="filter-chip-pathogenicity-PATHOGENIC"]').text()).toContain(
      '2'
    );
    expect(wrapper.find('[data-testid="filter-chip-pathogenicity-VUS"]').text()).toContain('1');
    // No benign/likely-benign variants -> those chips are absent.
    expect(wrapper.find('[data-testid="filter-chip-pathogenicity-BENIGN"]').exists()).toBe(false);
    // CNV bucket present and correctly labelled.
    const cnv = wrapper.find('[data-testid="filter-chip-consequence-cnv_loss"]');
    expect(cnv.exists()).toBe(true);
    expect(cnv.text()).toContain('CN Loss');
  });

  it('emits update:modelValue when switching colour mode', async () => {
    const wrapper = makeWrapper();
    await wrapper.find('[data-testid="colorby-consequence"]').trigger('click');
    const events = wrapper.emitted('update:modelValue');
    expect(events).toBeTruthy();
    expect(events.at(-1)[0].coloringMode).toBe('consequence');
  });

  it('emits a toggled-off state when a visible chip is clicked', async () => {
    const wrapper = makeWrapper();
    await wrapper.find('[data-testid="filter-chip-consequence-missense"]').trigger('click');
    const next = wrapper.emitted('update:modelValue').at(-1)[0];
    expect(next.consequence.missense).toBe(false);
  });

  it('emits an isolated state when "only" is clicked', async () => {
    const wrapper = makeWrapper();
    await wrapper.find('[data-testid="filter-only-pathogenicity-PATHOGENIC"]').trigger('click');
    const next = wrapper.emitted('update:modelValue').at(-1)[0];
    expect(next.pathogenicity.PATHOGENIC).toBe(true);
    expect(next.pathogenicity.VUS).toBe(false);
  });

  it('emits an all-visible state when "All" is clicked', async () => {
    const start = createDefaultFilterState();
    start.consequence.missense = false;
    const wrapper = makeWrapper(start);
    await wrapper.find('[data-testid="filter-all-consequence"]').trigger('click');
    const next = wrapper.emitted('update:modelValue').at(-1)[0];
    expect(Object.values(next.consequence).every(Boolean)).toBe(true);
  });
});
