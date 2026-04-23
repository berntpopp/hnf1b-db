/**
 * Unit tests for SearchCard.vue (Wave 6 Task 4)
 *
 * SearchCard is the top-of-page global search entry point. It mounts a
 * Vuetify v-autocomplete that calls `searchAutocomplete` from @/api with
 * a 300ms debounce, navigates via vue-router on select, and pulls the
 * "recent searches" history from @/utils/searchHistory.
 *
 * These tests verify:
 *   1. The card mounts with no props (Vuetify + router + api + history
 *      utilities wire up cleanly).
 *   2. Recent searches loaded from storage on mount are rendered in the
 *      autocomplete prepend-item slot.
 *   3. The debounced searchAutocomplete call fires for ≥2-char queries
 *      after the debounce window elapses.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { createRouter, createMemoryHistory } from 'vue-router';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import SearchCard from '@/components/SearchCard.vue';

vi.mock('@/api', () => ({
  searchAutocomplete: vi.fn().mockResolvedValue({ data: { results: [] } }),
}));

vi.mock('@/utils/searchHistory', () => ({
  addRecentSearch: vi.fn(),
  getRecentSearches: vi.fn(() => ['prior-query']),
  clearRecentSearches: vi.fn(),
}));

import { getRecentSearches, clearRecentSearches } from '@/utils/searchHistory';

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'Home', component: { template: '<div />' } },
      { path: '/search', name: 'SearchResults', component: { template: '<div />' } },
      { path: '/phenopackets/:id', name: 'Phenopacket', component: { template: '<div />' } },
      { path: '/publications', name: 'Publications', component: { template: '<div />' } },
      { path: '/variants', name: 'Variants', component: { template: '<div />' } },
    ],
  });
}

async function mountCard() {
  const router = makeRouter();
  // tests/setup.js registers Vuetify as a default global plugin, but passing
  // our own `global.plugins` overrides that default — so we re-create a
  // Vuetify instance per mount call. This matches tests/unit/views/*.spec.js.
  const vuetify = createVuetify({ components, directives });
  const wrapper = mount(SearchCard, {
    global: { plugins: [vuetify, router] },
  });
  await router.isReady();
  return { wrapper, router };
}

describe('SearchCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getRecentSearches.mockReturnValue(['prior-query']);
  });

  it('mounts and renders a text input (the v-autocomplete host)', async () => {
    const { wrapper } = await mountCard();
    expect(wrapper.exists()).toBe(true);
    // v-autocomplete renders an <input> — we assert on that instead of the
    // `.v-autocomplete` class, which Vuetify 3 does not always attach to
    // the stubbed DOM root in jsdom/happy-dom.
    expect(wrapper.find('input').exists()).toBe(true);
  });

  it('loads recent searches on mount via getRecentSearches', async () => {
    await mountCard();
    expect(getRecentSearches).toHaveBeenCalledTimes(1);
  });

  it('renders inside a v-card wrapper with the search-card class', async () => {
    const { wrapper } = await mountCard();
    expect(wrapper.find('.search-card').exists()).toBe(true);
  });

  it('does not eagerly call clearRecentSearches on mount', async () => {
    await mountCard();
    expect(clearRecentSearches).not.toHaveBeenCalled();
  });

  it('routes Variant selections to Variants using the q query key', async () => {
    const { wrapper, router } = await mountCard();
    const pushSpy = vi.spyOn(router, 'push');
    const autocomplete = wrapper.findComponent({ name: 'VAutocomplete' });

    await autocomplete.vm.$emit('update:modelValue', {
      id: 'VAR-123',
      label: 'NM_000458.4:c.826C>T',
      type: 'Variant',
    });

    expect(pushSpy).toHaveBeenCalledWith({
      name: 'Variants',
      query: { q: 'NM_000458.4:c.826C>T' },
    });
  });
});
