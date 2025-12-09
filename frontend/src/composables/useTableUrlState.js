/**
 * Composable for table-specific URL state synchronization.
 *
 * Extends useUrlState with table-specific defaults for pagination,
 * sorting, searching, and filtering. Creates shareable/bookmarkable
 * URLs for table views.
 *
 * @param {Object} options - Configuration options
 * @param {number} options.defaultPageSize - Default items per page (default: 10)
 * @param {string} options.defaultSort - Default sort field with optional '-' prefix (default: null)
 * @param {Object} options.filters - Filter configuration { filterName: defaultValue }
 * @returns {Object} Reactive refs and helper functions for table state
 *
 * @example
 * const {
 *   page, pageSize, sort, search, filters,
 *   resetAll, hasCustomState, shareableUrl
 * } = useTableUrlState({
 *   defaultPageSize: 20,
 *   defaultSort: '-created_at',
 *   filters: { sex: null, type: null }
 * });
 */

import { useUrlState } from './useUrlState';
import { computed, watch } from 'vue';

export function useTableUrlState(options = {}) {
  const { defaultPageSize = 10, defaultSort = null, filters = {}, onStateChange = null } = options;

  // Build schema from options
  const schema = {
    page: { default: 1, type: 'number' },
    pageSize: { default: defaultPageSize, type: 'number' },
    sort: { default: defaultSort, type: 'string' },
    q: { default: '', type: 'string' },
  };

  // Add filter parameters to schema
  for (const [key, defaultValue] of Object.entries(filters)) {
    schema[key] = {
      default: defaultValue,
      type: typeof defaultValue === 'boolean' ? 'boolean' : 'string',
    };
  }

  const urlState = useUrlState(schema);

  // Create filter refs object for easier access
  const filterRefs = {};
  for (const key of Object.keys(filters)) {
    filterRefs[key] = urlState[key];
  }

  // Computed for active filter count
  const activeFilterCount = computed(() => {
    let count = 0;
    if (urlState.q.value) count++;
    for (const key of Object.keys(filters)) {
      if (urlState[key].value) count++;
    }
    return count;
  });

  // Watch for any state change and notify callback
  if (onStateChange) {
    const allKeys = Object.keys(schema);
    watch(
      allKeys.map((key) => urlState[key]),
      () => {
        onStateChange(getCurrentState());
      },
      { immediate: true }
    );
  }

  /**
   * Get current state as plain object
   */
  function getCurrentState() {
    const state = {
      page: urlState.page.value,
      pageSize: urlState.pageSize.value,
      sort: urlState.sort.value,
      search: urlState.q.value,
      filters: {},
    };
    for (const key of Object.keys(filters)) {
      state.filters[key] = urlState[key].value;
    }
    return state;
  }

  /**
   * Reset pagination to page 1 (useful when filters change)
   */
  function resetPage() {
    urlState.page.value = 1;
  }

  /**
   * Clear all filters and search, reset to page 1
   */
  function clearAllFilters() {
    urlState.q.value = '';
    for (const key of Object.keys(filters)) {
      urlState[key].value = filters[key];
    }
    urlState.page.value = 1;
  }

  /**
   * Clear a specific filter
   */
  function clearFilter(key) {
    if (urlState[key]) {
      urlState[key].value = filters[key] ?? null;
      urlState.page.value = 1;
    }
  }

  /**
   * Build JSON:API pagination params from current state
   */
  function buildPaginationParams() {
    return {
      'page[number]': urlState.page.value,
      'page[size]': urlState.pageSize.value,
    };
  }

  /**
   * Build filter params for API request
   */
  function buildFilterParams() {
    const params = {};
    for (const key of Object.keys(filters)) {
      const value = urlState[key].value;
      if (value !== null && value !== undefined && value !== '') {
        params[`filter[${key}]`] = value;
      }
    }
    return params;
  }

  return {
    // Core pagination state
    page: urlState.page,
    pageSize: urlState.pageSize,
    sort: urlState.sort,
    search: urlState.q,

    // Filter refs
    filters: filterRefs,

    // Computed
    activeFilterCount,
    hasCustomState: urlState.hasCustomState,
    shareableUrl: urlState.shareableUrl,

    // Methods
    resetPage,
    resetAll: urlState.resetAll,
    clearAllFilters,
    clearFilter,
    getCurrentState,
    buildPaginationParams,
    buildFilterParams,
  };
}
