/**
 * Unit tests for VariantPanel.vue.
 *
 * Presentational sub-component of ProteinStructure3D (all-variants mode).
 * Renders the sort/filter selects, the variant list, and the empty state.
 * Distances are pre-resolved by the parent and attached as `_distanceInfo`,
 * so this component needs no NGL involvement — pure props/emits.
 */
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import VariantPanel from '@/components/gene/protein-structure/VariantPanel.vue';

const SAMPLE_VARIANTS = [
  {
    variant_id: 'V1',
    protein: 'p.Arg100Gly',
    classificationVerdict: 'Pathogenic',
    _distanceInfo: { category: 'close', distance: 3.1, distanceFormatted: '3.1' },
  },
  {
    variant_id: 'V2',
    protein: 'p.Lys200Asn',
    classificationVerdict: 'VUS',
    _distanceInfo: null,
  },
];

function mountPanel(props = {}) {
  const vuetify = createVuetify({ components, directives });
  return mount(VariantPanel, {
    props: {
      variants: SAMPLE_VARIANTS,
      totalInStructure: 2,
      selectedVariantId: null,
      hoveredVariantId: null,
      sortBy: 'position',
      filterDistance: null,
      ...props,
    },
    global: { plugins: [vuetify] },
  });
}

describe('VariantPanel', () => {
  it('renders a list item for each variant', () => {
    const wrapper = mountPanel();
    const items = wrapper.findAll('.v-list-item');
    expect(items.length).toBe(2);
    expect(wrapper.text()).toContain('p.Arg100Gly');
    expect(wrapper.text()).toContain('p.Lys200Asn');
  });

  it('shows the resolved distance chip for variants that have distance info', () => {
    const wrapper = mountPanel();
    expect(wrapper.text()).toContain('3.1 Å');
  });

  it('emits select with the variant when a list item is clicked', async () => {
    const wrapper = mountPanel();
    await wrapper.findAll('.v-list-item')[0].trigger('click');
    expect(wrapper.emitted('select')).toBeTruthy();
    expect(wrapper.emitted('select')[0][0].variant_id).toBe('V1');
  });

  it('emits hover and unhover on mouse enter/leave', async () => {
    const wrapper = mountPanel();
    const item = wrapper.findAll('.v-list-item')[1];
    await item.trigger('mouseenter');
    await item.trigger('mouseleave');
    expect(wrapper.emitted('hover')[0][0].variant_id).toBe('V2');
    expect(wrapper.emitted('unhover')).toBeTruthy();
  });

  it('renders the empty state and a Clear Filters button when filters hide all variants', async () => {
    const wrapper = mountPanel({
      variants: [],
      totalInStructure: 2,
    });
    expect(wrapper.text()).toContain('No variants match filters');
    const clearBtn = wrapper.findAll('button').find((b) => b.text().includes('Clear Filters'));
    expect(clearBtn).toBeTruthy();
    await clearBtn.trigger('click');
    expect(wrapper.emitted('clear-filters')).toBeTruthy();
  });

  it('renders the no-variants-in-range empty state without a Clear Filters button', () => {
    const wrapper = mountPanel({ variants: [], totalInStructure: 0 });
    expect(wrapper.text()).toContain('No variants in structure range');
    const clearBtn = wrapper.findAll('button').find((b) => b.text().includes('Clear Filters'));
    expect(clearBtn).toBeUndefined();
  });
});
