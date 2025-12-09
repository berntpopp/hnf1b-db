/**
 * Unit tests for the useTableUrlState composable
 *
 * Tests cover:
 * - Default state initialization
 * - Page, pageSize, sort, search state management
 * - Filter state management
 * - Active filter count computation
 * - Reset and clear methods
 * - URL state synchronization helpers
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock vue-router
const mockRoute = {
  query: {},
};
const mockReplace = vi.fn(() => Promise.resolve());
const mockPush = vi.fn(() => Promise.resolve());

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => ({
    replace: mockReplace,
    push: mockPush,
  }),
}));

// Import after mocks are set up
import { useTableUrlState } from '@/composables/useTableUrlState';

describe('useTableUrlState', () => {
  beforeEach(() => {
    // Reset mocks
    mockRoute.query = {};
    mockReplace.mockClear();
  });

  describe('initialization', () => {
    it('should initialize with default values', () => {
      const state = useTableUrlState();

      expect(state.page.value).toBe(1);
      expect(state.pageSize.value).toBe(10);
      expect(state.sort.value).toBe(null);
      expect(state.search.value).toBe('');
    });

    it('should use custom defaults when provided', () => {
      const state = useTableUrlState({
        defaultPageSize: 20,
        defaultSort: '-created_at',
      });

      expect(state.pageSize.value).toBe(20);
      expect(state.sort.value).toBe('-created_at');
    });

    it('should initialize filters from options', () => {
      const state = useTableUrlState({
        filters: { sex: null, type: null },
      });

      expect(state.filters.sex).toBeDefined();
      expect(state.filters.type).toBeDefined();
      expect(state.filters.sex.value).toBe(null);
      expect(state.filters.type.value).toBe(null);
    });
  });

  describe('URL query parsing', () => {
    it('should parse page from URL query', () => {
      mockRoute.query = { page: '3' };
      const state = useTableUrlState();

      expect(state.page.value).toBe(3);
    });

    it('should parse pageSize from URL query', () => {
      mockRoute.query = { pageSize: '50' };
      const state = useTableUrlState();

      expect(state.pageSize.value).toBe(50);
    });

    it('should parse sort from URL query', () => {
      mockRoute.query = { sort: '-name' };
      const state = useTableUrlState();

      expect(state.sort.value).toBe('-name');
    });

    it('should parse search (q) from URL query', () => {
      mockRoute.query = { q: 'test query' };
      const state = useTableUrlState();

      expect(state.search.value).toBe('test query');
    });

    it('should parse filter values from URL query', () => {
      mockRoute.query = { sex: 'MALE', type: 'SNV' };
      const state = useTableUrlState({
        filters: { sex: null, type: null },
      });

      expect(state.filters.sex.value).toBe('MALE');
      expect(state.filters.type.value).toBe('SNV');
    });
  });

  describe('activeFilterCount', () => {
    it('should return 0 when no filters are active', () => {
      const state = useTableUrlState({
        filters: { sex: null, type: null },
      });

      expect(state.activeFilterCount.value).toBe(0);
    });

    it('should count search as a filter', () => {
      mockRoute.query = { q: 'test' };
      const state = useTableUrlState({
        filters: { sex: null },
      });

      expect(state.activeFilterCount.value).toBe(1);
    });

    it('should count active filters', () => {
      mockRoute.query = { q: 'test', sex: 'MALE', type: 'SNV' };
      const state = useTableUrlState({
        filters: { sex: null, type: null },
      });

      expect(state.activeFilterCount.value).toBe(3);
    });
  });

  describe('resetPage', () => {
    it('should reset page to 1', () => {
      mockRoute.query = { page: '5' };
      const state = useTableUrlState();

      expect(state.page.value).toBe(5);

      state.resetPage();

      expect(state.page.value).toBe(1);
    });
  });

  describe('clearAllFilters', () => {
    it('should clear search and all filters', () => {
      mockRoute.query = { q: 'test', sex: 'MALE', type: 'SNV', page: '3' };
      const state = useTableUrlState({
        filters: { sex: null, type: null },
      });

      expect(state.search.value).toBe('test');
      expect(state.filters.sex.value).toBe('MALE');
      expect(state.filters.type.value).toBe('SNV');

      state.clearAllFilters();

      expect(state.search.value).toBe('');
      expect(state.filters.sex.value).toBe(null);
      expect(state.filters.type.value).toBe(null);
      expect(state.page.value).toBe(1);
    });
  });

  describe('clearFilter', () => {
    it('should clear a specific filter', () => {
      mockRoute.query = { sex: 'MALE', type: 'SNV' };
      const state = useTableUrlState({
        filters: { sex: null, type: null },
      });

      expect(state.filters.sex.value).toBe('MALE');
      expect(state.filters.type.value).toBe('SNV');

      state.clearFilter('sex');

      expect(state.filters.sex.value).toBe(null);
      expect(state.filters.type.value).toBe('SNV');
    });

    it('should reset page when clearing a filter', () => {
      mockRoute.query = { sex: 'MALE', page: '3' };
      const state = useTableUrlState({
        filters: { sex: null },
      });

      state.clearFilter('sex');

      expect(state.page.value).toBe(1);
    });
  });

  describe('hasCustomState', () => {
    it('should return false with default state', () => {
      const state = useTableUrlState();

      expect(state.hasCustomState.value).toBe(false);
    });

    it('should return true with custom page', () => {
      mockRoute.query = { page: '2' };
      const state = useTableUrlState();

      expect(state.hasCustomState.value).toBe(true);
    });

    it('should return true with search query', () => {
      mockRoute.query = { q: 'test' };
      const state = useTableUrlState();

      expect(state.hasCustomState.value).toBe(true);
    });

    it('should return true with active filter', () => {
      mockRoute.query = { sex: 'MALE' };
      const state = useTableUrlState({
        filters: { sex: null },
      });

      expect(state.hasCustomState.value).toBe(true);
    });
  });

  describe('buildPaginationParams', () => {
    it('should build JSON:API pagination params', () => {
      mockRoute.query = { page: '2', pageSize: '25' };
      const state = useTableUrlState();

      const params = state.buildPaginationParams();

      expect(params['page[number]']).toBe(2);
      expect(params['page[size]']).toBe(25);
    });
  });

  describe('buildFilterParams', () => {
    it('should build filter params for API request', () => {
      mockRoute.query = { sex: 'MALE', type: 'SNV' };
      const state = useTableUrlState({
        filters: { sex: null, type: null },
      });

      const params = state.buildFilterParams();

      expect(params['filter[sex]']).toBe('MALE');
      expect(params['filter[type]']).toBe('SNV');
    });

    it('should not include empty filters', () => {
      mockRoute.query = { sex: 'MALE' };
      const state = useTableUrlState({
        filters: { sex: null, type: null },
      });

      const params = state.buildFilterParams();

      expect(params['filter[sex]']).toBe('MALE');
      expect(params['filter[type]']).toBeUndefined();
    });
  });

  describe('getCurrentState', () => {
    it('should return current state as plain object', () => {
      mockRoute.query = { page: '2', q: 'test', sex: 'MALE' };
      const state = useTableUrlState({
        defaultPageSize: 20,
        filters: { sex: null },
      });

      const currentState = state.getCurrentState();

      expect(currentState.page).toBe(2);
      expect(currentState.pageSize).toBe(20);
      expect(currentState.search).toBe('test');
      expect(currentState.filters.sex).toBe('MALE');
    });
  });
});
