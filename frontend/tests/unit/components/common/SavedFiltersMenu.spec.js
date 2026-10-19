/**
 * Unit tests for SavedFiltersMenu.vue
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import SavedFiltersMenu from '@/components/common/SavedFiltersMenu.vue';

describe('SavedFiltersMenu', () => {
  const scopeKey = 'test_cohort';
  const vuetify = createVuetify({ components, directives });

  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  function mountMenu(props = {}) {
    return mount(SavedFiltersMenu, {
      props: {
        scopeKey,
        currentFilters: { sex: 'MALE', type: 'SNV' },
        attach: true,
        ...props,
      },
      global: {
        plugins: [vuetify],
      },
    });
  }

  it('renders copy cohort link and saved filters buttons', () => {
    const wrapper = mountMenu();
    expect(wrapper.find('[data-testid="copy-cohort-link-btn"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="saved-filters-menu-btn"]').exists()).toBe(true);
  });

  it('copies cohort URL when copy button is clicked', async () => {
    const mockWriteText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: mockWriteText },
      configurable: true,
      writable: true,
    });

    const wrapper = mountMenu();
    const copyBtn = wrapper.find('[data-testid="copy-cohort-link-btn"]');
    await copyBtn.trigger('click');

    expect(mockWriteText).toHaveBeenCalled();
  });

  it('saves current filter state under preset name', async () => {
    const wrapper = mountMenu({
      currentFilters: { sex: 'FEMALE', classification: 'PATHOGENIC' },
    });

    // Open menu
    const menuBtn = wrapper.find('[data-testid="saved-filters-menu-btn"]');
    await menuBtn.trigger('click');

    const input = wrapper.find('[data-testid="save-filter-preset-input"] input');
    await input.setValue('Female Pathogenic');

    const saveBtn = wrapper.find('[data-testid="save-filter-preset-btn"]');
    await saveBtn.trigger('click');

    expect(wrapper.emitted('save')).toBeTruthy();
    expect(wrapper.emitted('save')[0][0].name).toBe('Female Pathogenic');
    expect(wrapper.emitted('save')[0][0].filters).toEqual({
      sex: 'FEMALE',
      classification: 'PATHOGENIC',
    });

    const stored = JSON.parse(
      window.localStorage.getItem(`hnf1b_saved_filters_${scopeKey}`)
    );
    expect(stored).toHaveLength(1);
    expect(stored[0].name).toBe('Female Pathogenic');
  });

  it('emits apply when a preset item is clicked', async () => {
    window.localStorage.setItem(
      `hnf1b_saved_filters_${scopeKey}`,
      JSON.stringify([{ name: 'Preset 1', filters: { sex: 'MALE' } }])
    );

    const wrapper = mountMenu();
    const menuBtn = wrapper.find('[data-testid="saved-filters-menu-btn"]');
    await menuBtn.trigger('click');

    const presetItem = wrapper.find('[data-testid="preset-item"]');
    expect(presetItem.exists()).toBe(true);
    await presetItem.trigger('click');

    expect(wrapper.emitted('apply')).toBeTruthy();
    expect(wrapper.emitted('apply')[0][0]).toEqual({ sex: 'MALE' });
  });

  it('emits delete and removes preset when delete button is clicked', async () => {
    window.localStorage.setItem(
      `hnf1b_saved_filters_${scopeKey}`,
      JSON.stringify([{ name: 'To Delete', filters: { sex: 'MALE' } }])
    );

    const wrapper = mountMenu();
    const menuBtn = wrapper.find('[data-testid="saved-filters-menu-btn"]');
    await menuBtn.trigger('click');

    const deleteBtn = wrapper.find('[data-testid="delete-preset-btn"]');
    expect(deleteBtn.exists()).toBe(true);
    await deleteBtn.trigger('click');

    expect(wrapper.emitted('delete')).toBeTruthy();
    expect(wrapper.emitted('delete')[0][0]).toBe('To Delete');

    const stored = JSON.parse(
      window.localStorage.getItem(`hnf1b_saved_filters_${scopeKey}`)
    );
    expect(stored).toHaveLength(0);
  });
});
