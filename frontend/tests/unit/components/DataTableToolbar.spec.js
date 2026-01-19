/**
 * Unit tests for DataTableToolbar component
 *
 * Tests cover:
 * - Search input with debounce
 * - Result count display
 * - Active filter chips
 * - Column visibility settings
 * - Actions slot
 * - Loading state
 * - Clear all functionality
 *
 * Note: Uses shallowMount with Vuetify stubs to avoid full Vuetify resolution.
 * Focus is on component logic, props, emits, and methods testing.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { shallowMount } from '@vue/test-utils';
import DataTableToolbar from '@/components/common/DataTableToolbar.vue';

// Stub Vuetify components to avoid resolution errors
const vuetifyStubs = {
  'v-text-field': {
    template:
      '<input :value="modelValue" :placeholder="placeholder" @input="$emit(\'update:modelValue\', $event.target.value)" @keyup.enter="$emit(\'keyup\', $event)" />',
    props: [
      'modelValue',
      'placeholder',
      'loading',
      'clearable',
      'hideDetails',
      'variant',
      'density',
      'prependInnerIcon',
    ],
  },
  'v-chip': {
    template: '<span class="v-chip" :class="{ closable }"><slot /></span>',
    props: ['color', 'size', 'variant', 'closable'],
    emits: ['click:close'],
  },
  'v-icon': {
    template: '<i class="v-icon"><slot /></i>',
    props: ['start', 'size'],
  },
  'v-btn': {
    template: '<button :aria-label="ariaLabel" @click="$emit(\'click\')"><slot /></button>',
    props: ['variant', 'size', 'color', 'icon', 'ariaLabel'],
    emits: ['click'],
  },
  'v-spacer': { template: '<div class="v-spacer" />' },
  'v-menu': { template: '<div class="v-menu"><slot /><slot name="activator" :props="{}" /></div>' },
  'v-card': { template: '<div class="v-card"><slot /></div>' },
  'v-card-title': { template: '<div class="v-card-title"><slot /></div>' },
  'v-card-text': { template: '<div class="v-card-text"><slot /></div>' },
  'v-checkbox': {
    template:
      '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
    props: ['modelValue', 'label', 'density', 'hideDetails'],
    emits: ['update:modelValue'],
  },
};

/**
 * Helper function to mount DataTableToolbar with common options
 * @param {Object} props - Component props
 * @param {Object} slots - Component slots
 * @returns {Wrapper} Vue test utils wrapper
 */
function mountToolbar(props = {}, slots = {}) {
  return shallowMount(DataTableToolbar, {
    props,
    slots,
    global: {
      stubs: vuetifyStubs,
    },
  });
}

describe('DataTableToolbar', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('search functionality', () => {
    it('renders search input with placeholder', () => {
      const wrapper = mountToolbar({ searchPlaceholder: 'Search items...' });
      const input = wrapper.find('input');
      expect(input.attributes('placeholder')).toBe('Search items...');
    });

    it('renders search input with default placeholder', () => {
      const wrapper = mountToolbar();
      const input = wrapper.find('input');
      expect(input.attributes('placeholder')).toBe('Search...');
    });

    it('emits update:searchQuery on input', async () => {
      const wrapper = mountToolbar();
      const input = wrapper.find('input');
      await input.setValue('test query');
      expect(wrapper.emitted('update:searchQuery')[0]).toEqual(['test query']);
    });

    it('debounces search event', async () => {
      const wrapper = mountToolbar({ debounceDelay: 300 });
      // Call onSearchInput directly since our stub doesn't wire through to parent
      wrapper.vm.onSearchInput('test');

      // Search not emitted immediately
      expect(wrapper.emitted('search')).toBeUndefined();

      // Advance timers
      vi.advanceTimersByTime(300);

      // Now search should be emitted
      expect(wrapper.emitted('search')?.[0]).toEqual(['test']);
    });

    it('emits search immediately on Enter via onSearchSubmit', () => {
      const wrapper = mountToolbar({ searchQuery: 'query' });
      wrapper.vm.onSearchSubmit();
      expect(wrapper.emitted('search')?.[0]).toEqual(['query']);
    });

    it('emits clear-search when cleared', () => {
      const wrapper = mountToolbar({ searchQuery: 'test' });
      wrapper.vm.onClearSearch();
      expect(wrapper.emitted('update:searchQuery')[0]).toEqual(['']);
      expect(wrapper.emitted('clear-search')).toHaveLength(1);
    });
  });

  describe('result count', () => {
    it('shows result count when showResultCount is true', () => {
      const wrapper = mountToolbar({ resultCount: 42, showResultCount: true });
      expect(wrapper.text()).toContain('42');
    });

    it('hides result chip when showResultCount is false', () => {
      const wrapper = mountToolbar({ resultCount: 42, showResultCount: false });
      expect(wrapper.find('.result-chip').exists()).toBe(false);
    });

    it('formats large result counts with locale', () => {
      const wrapper = mountToolbar({ resultCount: 1234567 });
      expect(wrapper.text()).toContain('1,234,567');
    });

    it('uses custom result label', () => {
      const wrapper = mountToolbar({ resultCount: 5, resultLabel: 'variants' });
      expect(wrapper.text()).toContain('5 variants');
    });

    it('uses default result label', () => {
      const wrapper = mountToolbar({ resultCount: 10 });
      expect(wrapper.text()).toContain('10 results');
    });
  });

  describe('active filters', () => {
    it('shows filter row when filters exist', () => {
      const filters = [{ key: 'sex', label: 'Male' }];
      const wrapper = mountToolbar({ activeFilters: filters });
      expect(wrapper.find('.filter-row').exists()).toBe(true);
    });

    it('hides filter row when no filters and no search', () => {
      const wrapper = mountToolbar({ activeFilters: [], searchQuery: '' });
      expect(wrapper.find('.filter-row').exists()).toBe(false);
    });

    it('shows search query as filter chip text', () => {
      const wrapper = mountToolbar({ searchQuery: 'test query' });
      expect(wrapper.text()).toContain('"test query"');
    });

    it('shows Clear All button when searchQuery exists', () => {
      const wrapper = mountToolbar({ searchQuery: 'test' });
      expect(wrapper.text()).toContain('Clear All');
    });

    it('truncates long search queries in chip', () => {
      const wrapper = mountToolbar({
        searchQuery: 'this is a very long search query that should be truncated',
      });
      expect(wrapper.text()).toContain('...');
    });

    it('does not truncate short search queries', () => {
      const wrapper = mountToolbar({ searchQuery: 'short' });
      expect(wrapper.text()).toContain('"short"');
      expect(wrapper.text()).not.toContain('...');
    });

    it('renders filter labels', () => {
      const filters = [{ key: 'sex', label: 'Male', icon: 'mdi-gender-male' }];
      const wrapper = mountToolbar({ activeFilters: filters });
      expect(wrapper.text()).toContain('Male');
    });

    it('renders multiple filters', () => {
      const filters = [
        { key: 'sex', label: 'Male' },
        { key: 'status', label: 'Active' },
      ];
      const wrapper = mountToolbar({ activeFilters: filters });
      expect(wrapper.text()).toContain('Male');
      expect(wrapper.text()).toContain('Active');
    });
  });

  describe('column settings', () => {
    const columns = [
      { key: 'name', title: 'Name', visible: true },
      { key: 'age', title: 'Age', visible: false },
    ];

    it('shows column settings menu when enabled with columns', () => {
      const wrapper = mountToolbar({ showColumnSettings: true, columns });
      expect(wrapper.find('.v-menu').exists()).toBe(true);
    });

    it('hides column settings menu when disabled', () => {
      const wrapper = mountToolbar({ showColumnSettings: false, columns });
      // Menu should not be in the DOM when showColumnSettings is false
      // We need to check for the conditional rendering
      const menuWithButton = wrapper
        .findAll('button')
        .find((b) => b.attributes('aria-label') === 'Column settings');
      expect(menuWithButton).toBeUndefined();
    });

    it('hides column settings when columns array is empty', () => {
      const wrapper = mountToolbar({ showColumnSettings: true, columns: [] });
      const menuWithButton = wrapper
        .findAll('button')
        .find((b) => b.attributes('aria-label') === 'Column settings');
      expect(menuWithButton).toBeUndefined();
    });
  });

  describe('actions slot', () => {
    it('renders actions slot content', () => {
      const wrapper = mountToolbar({}, { actions: '<button id="export">Export</button>' });
      expect(wrapper.find('#export').exists()).toBe(true);
    });

    it('renders multiple action items', () => {
      const wrapper = mountToolbar(
        {},
        {
          actions: '<button id="btn1">Btn1</button><button id="btn2">Btn2</button>',
        }
      );
      expect(wrapper.find('#btn1').exists()).toBe(true);
      expect(wrapper.find('#btn2').exists()).toBe(true);
    });
  });

  describe('loading state', () => {
    it('passes loading prop to component', () => {
      const wrapper = mountToolbar({ loading: true });
      expect(wrapper.props('loading')).toBe(true);
    });

    it('loading is false by default', () => {
      const wrapper = mountToolbar();
      expect(wrapper.props('loading')).toBe(false);
    });
  });

  describe('clear all functionality', () => {
    it('clears search and emits clear-all-filters', () => {
      const filters = [{ key: 'sex', label: 'Male' }];
      const wrapper = mountToolbar({ activeFilters: filters, searchQuery: 'test' });

      wrapper.vm.onClearAll();

      expect(wrapper.emitted('update:searchQuery')[0]).toEqual(['']);
      expect(wrapper.emitted('clear-search')).toHaveLength(1);
      expect(wrapper.emitted('clear-all-filters')).toHaveLength(1);
    });
  });

  describe('truncateText method', () => {
    it('returns text unchanged if shorter than maxLength', () => {
      const wrapper = mountToolbar();
      expect(wrapper.vm.truncateText('short', 20)).toBe('short');
    });

    it('truncates text and adds ellipsis if longer than maxLength', () => {
      const wrapper = mountToolbar();
      expect(wrapper.vm.truncateText('this is a long text', 10)).toBe('this is a ...');
    });

    it('handles null text', () => {
      const wrapper = mountToolbar();
      expect(wrapper.vm.truncateText(null, 20)).toBe(null);
    });

    it('handles empty text', () => {
      const wrapper = mountToolbar();
      expect(wrapper.vm.truncateText('', 20)).toBe('');
    });

    it('handles text exactly at maxLength', () => {
      const wrapper = mountToolbar();
      expect(wrapper.vm.truncateText('exactly20characters!', 20)).toBe('exactly20characters!');
    });
  });

  describe('hasActiveFilters computed', () => {
    it('returns truthy when searchQuery exists', () => {
      const wrapper = mountToolbar({ searchQuery: 'test' });
      expect(wrapper.vm.hasActiveFilters).toBeTruthy();
    });

    it('returns truthy when activeFilters exist', () => {
      const wrapper = mountToolbar({ activeFilters: [{ key: 'a', label: 'A' }] });
      expect(wrapper.vm.hasActiveFilters).toBeTruthy();
    });

    it('returns truthy when both searchQuery and activeFilters exist', () => {
      const wrapper = mountToolbar({
        searchQuery: 'test',
        activeFilters: [{ key: 'a', label: 'A' }],
      });
      expect(wrapper.vm.hasActiveFilters).toBeTruthy();
    });

    it('returns falsy when no search and no filters', () => {
      const wrapper = mountToolbar({ searchQuery: '', activeFilters: [] });
      expect(wrapper.vm.hasActiveFilters).toBeFalsy();
    });
  });

  describe('component structure', () => {
    it('has data-table-toolbar class on root', () => {
      const wrapper = mountToolbar();
      expect(wrapper.find('.data-table-toolbar').exists()).toBe(true);
    });

    it('has toolbar-row for main content', () => {
      const wrapper = mountToolbar();
      expect(wrapper.find('.toolbar-row').exists()).toBe(true);
    });
  });

  describe('default props', () => {
    it('has correct default values', () => {
      const wrapper = mountToolbar();
      expect(wrapper.props('searchQuery')).toBe('');
      expect(wrapper.props('searchPlaceholder')).toBe('Search...');
      expect(wrapper.props('resultCount')).toBe(0);
      expect(wrapper.props('resultLabel')).toBe('results');
      expect(wrapper.props('showResultCount')).toBe(true);
      expect(wrapper.props('loading')).toBe(false);
      expect(wrapper.props('debounceDelay')).toBe(300);
      expect(wrapper.props('activeFilters')).toEqual([]);
      expect(wrapper.props('columns')).toEqual([]);
      expect(wrapper.props('showColumnSettings')).toBe(false);
    });
  });

  describe('emits', () => {
    it('declares all expected emits', () => {
      const wrapper = mountToolbar();
      const emits = wrapper.vm.$options.emits;
      expect(emits).toContain('update:searchQuery');
      expect(emits).toContain('search');
      expect(emits).toContain('clear-search');
      expect(emits).toContain('remove-filter');
      expect(emits).toContain('clear-all-filters');
      expect(emits).toContain('column-toggle');
    });
  });

  describe('debounce behavior', () => {
    it('creates debouncedSearch on created', () => {
      const wrapper = mountToolbar({ debounceDelay: 500 });
      expect(wrapper.vm.debouncedSearch).toBeDefined();
      expect(typeof wrapper.vm.debouncedSearch).toBe('function');
    });

    it('uses custom debounce delay', () => {
      const wrapper = mountToolbar({ debounceDelay: 500 });
      wrapper.vm.onSearchInput('test');

      // Not emitted after 300ms
      vi.advanceTimersByTime(300);
      expect(wrapper.emitted('search')).toBeUndefined();

      // Emitted after 500ms total
      vi.advanceTimersByTime(200);
      expect(wrapper.emitted('search')?.[0]).toEqual(['test']);
    });

    it('debounces multiple rapid inputs', () => {
      const wrapper = mountToolbar({ debounceDelay: 300 });

      wrapper.vm.onSearchInput('a');
      vi.advanceTimersByTime(100);
      wrapper.vm.onSearchInput('ab');
      vi.advanceTimersByTime(100);
      wrapper.vm.onSearchInput('abc');

      // Only the last value should be emitted after debounce
      vi.advanceTimersByTime(300);
      const searchEmits = wrapper.emitted('search');
      expect(searchEmits?.[searchEmits.length - 1]).toEqual(['abc']);
    });
  });
});
