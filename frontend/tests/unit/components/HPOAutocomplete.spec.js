/**
 * Unit tests for HPOAutocomplete.vue (Wave 6 Task 4)
 *
 * HPOAutocomplete wraps a Vuetify v-autocomplete and delegates the
 * actual HPO search to the `useHPOAutocomplete` composable. It emits
 * update:modelValue on select and exposes the usual Vuetify field
 * props (label, hint, density, variant, disabled, clearable).
 *
 * These tests verify:
 *   1. Mounts cleanly with default props.
 *   2. The `label` prop is rendered (either visible text or the
 *      underlying v-autocomplete label attr).
 *   3. The search composable is called once the input receives a
 *      ≥2-character query.
 *   4. Queries shorter than 2 characters do not trigger search.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

const search = vi.fn();
const terms = ref([]);
const loading = ref(false);
const error = ref(null);

vi.mock('@/composables/useHPOAutocomplete', () => ({
  useHPOAutocomplete: () => ({ terms, loading, error, search }),
}));

import HPOAutocomplete from '@/components/HPOAutocomplete.vue';

function mountAutocomplete(props = {}) {
  const vuetify = createVuetify({ components, directives });
  return mount(HPOAutocomplete, {
    props,
    global: { plugins: [vuetify] },
  });
}

describe('HPOAutocomplete', () => {
  beforeEach(() => {
    search.mockReset();
    terms.value = [];
    loading.value = false;
    error.value = null;
  });

  it('mounts with default props and renders a v-autocomplete', () => {
    const wrapper = mountAutocomplete();
    expect(wrapper.exists()).toBe(true);
    expect(wrapper.findComponent({ name: 'VAutocomplete' }).exists()).toBe(true);
  });

  it('forwards the label prop to the v-autocomplete', () => {
    const wrapper = mountAutocomplete({ label: 'Phenotype' });
    const auto = wrapper.findComponent({ name: 'VAutocomplete' });
    expect(auto.props('label')).toBe('Phenotype');
  });

  it('calls the search composable for 2+ character queries', async () => {
    const wrapper = mountAutocomplete();
    const auto = wrapper.findComponent({ name: 'VAutocomplete' });
    await auto.vm.$emit('update:search', 'ab');
    expect(search).toHaveBeenCalledWith('ab');
  });

  it('does not call search for 1-character queries', async () => {
    const wrapper = mountAutocomplete();
    const auto = wrapper.findComponent({ name: 'VAutocomplete' });
    await auto.vm.$emit('update:search', 'a');
    expect(search).not.toHaveBeenCalled();
  });

  it('forwards the disabled prop', () => {
    const wrapper = mountAutocomplete({ disabled: true });
    const auto = wrapper.findComponent({ name: 'VAutocomplete' });
    expect(auto.props('disabled')).toBe(true);
  });
});
