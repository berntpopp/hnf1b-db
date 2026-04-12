/**
 * Unit tests for FacetedFilters.vue (Wave 6 Task 4)
 *
 * FacetedFilters renders expansion panels with checkbox-driven filter
 * groups (sex, pathogenicity). It is a controlled component — state is
 * mirrored to the parent via v-model and a `filter-change` event.
 *
 * These tests verify:
 *   1. Mounting with the required `facets` prop succeeds.
 *   2. The "Clear All" button is disabled when no filters are active
 *      and enabled once a filter has been selected via modelValue.
 *   3. Clicking "Clear All" emits both update:modelValue and
 *      filter-change with the cleared state.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import FacetedFilters from '@/components/FacetedFilters.vue';

const DEFAULT_FACETS = {
  sex: [
    { label: 'Male', value: 'MALE', count: 400 },
    { label: 'Female', value: 'FEMALE', count: 450 },
  ],
  pathogenicity: [
    { label: 'Pathogenic', value: 'PATHOGENIC', count: 200 },
    { label: 'Benign', value: 'BENIGN', count: 50 },
  ],
};

function mountFilters(props = {}) {
  const vuetify = createVuetify({ components, directives });
  return mount(FacetedFilters, {
    props: {
      facets: DEFAULT_FACETS,
      ...props,
    },
    global: { plugins: [vuetify] },
  });
}

describe('FacetedFilters', () => {
  it('mounts with the required facets prop', () => {
    const wrapper = mountFilters();
    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain('Filters');
    expect(wrapper.text()).toContain('Clear All Filters');
  });

  it('disables Clear All when no filters are active', () => {
    const wrapper = mountFilters({ modelValue: { sex: [], pathogenicity: [] } });
    const clearBtn = wrapper.findComponent({ name: 'VBtn' });
    expect(clearBtn.props('disabled')).toBe(true);
  });

  it('enables Clear All once modelValue has a selected sex filter', () => {
    const wrapper = mountFilters({
      modelValue: { sex: ['MALE'], pathogenicity: [] },
    });
    const clearBtn = wrapper.findComponent({ name: 'VBtn' });
    expect(clearBtn.props('disabled')).toBe(false);
  });

  it('clearing emits update:modelValue + filter-change with empty arrays', async () => {
    const wrapper = mountFilters({
      modelValue: { sex: ['MALE'], pathogenicity: ['PATHOGENIC'] },
    });
    const clearBtn = wrapper.findComponent({ name: 'VBtn' });
    await clearBtn.trigger('click');

    const emittedModel = wrapper.emitted('update:modelValue');
    const emittedChange = wrapper.emitted('filter-change');
    expect(emittedModel).toBeTruthy();
    expect(emittedChange).toBeTruthy();
    expect(emittedModel[0][0]).toEqual({ sex: [], pathogenicity: [] });
    expect(emittedChange[0][0]).toEqual({ sex: [], pathogenicity: [] });
  });
});
