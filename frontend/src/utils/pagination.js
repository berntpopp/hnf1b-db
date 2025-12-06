/**
 * Offset pagination utilities for Vue components.
 * All pagination uses offset-based JSON:API v1.1 (page[number]/page[size]).
 */

/**
 * Build JSON:API sort parameter from Vuetify sortBy array.
 *
 * Maps frontend column keys to backend field names and formats
 * the sort parameter according to JSON:API conventions.
 *
 * @param {Array} sortBy - Vuetify sortBy array from v-data-table
 *   Example: [{ key: 'subject_id', order: 'desc' }]
 * @param {Object} sortFieldMap - Mapping of frontend keys to backend fields
 *   Example: { subject_id: 'subject_id', sex: 'subject_sex' }
 * @returns {string} JSON:API sort parameter (e.g., '-subject_id' for descending)
 *
 * @example
 * const sortParam = buildSortParameter(
 *   [{ key: 'created_at', order: 'desc' }],
 *   { created_at: 'created_at', name: 'subject_id' }
 * );
 * // Returns: '-created_at'
 */
export function buildSortParameter(sortBy, sortFieldMap) {
  if (!Array.isArray(sortBy) || sortBy.length === 0) {
    return '';
  }

  const { key, order } = sortBy[0];
  const backendField = sortFieldMap[key];

  if (!backendField) {
    window.logService?.warn('Unknown sort field', { key, sortFieldMap });
    return '';
  }

  // JSON:API convention: prefix with '-' for descending order
  return (order === 'desc' ? '-' : '') + backendField;
}

/**
 * Build offset pagination parameters for API requests.
 *
 * @param {Object} options - Pagination options
 * @param {number} options.page - Page number (1-indexed)
 * @param {number} options.pageSize - Number of items per page
 * @returns {Object} JSON:API offset pagination parameters
 *
 * @example
 * // First page
 * buildOffsetParams({ page: 1, pageSize: 20 });
 * // Returns: { 'page[number]': 1, 'page[size]': 20 }
 *
 * @example
 * // Third page
 * buildOffsetParams({ page: 3, pageSize: 20 });
 * // Returns: { 'page[number]': 3, 'page[size]': 20 }
 */
export function buildOffsetParams({ page = 1, pageSize = 20 }) {
  return {
    'page[number]': page,
    'page[size]': pageSize,
  };
}

/**
 * Extract offset pagination metadata from JSON:API response.
 *
 * @param {Object} response - Axios response object with JSON:API structure
 * @returns {Object} Offset pagination metadata
 *   - currentPage: Current page number (1-indexed)
 *   - pageSize: Number of items per page
 *   - totalPages: Total number of pages
 *   - totalRecords: Total count of items
 *
 * @example
 * const meta = extractPaginationMeta(response);
 * // Returns: {
 * //   currentPage: 1,
 * //   pageSize: 20,
 * //   totalPages: 44,
 * //   totalRecords: 864
 * // }
 */
export function extractPaginationMeta(response) {
  const data = response.data || {};
  const meta = data.meta || {};
  const page = meta.page || {};

  return {
    currentPage: page.currentPage || 1,
    pageSize: page.pageSize || 20,
    totalPages: page.totalPages || 0,
    totalRecords: page.totalRecords || 0,
  };
}

/**
 * Calculate display text for offset pagination.
 *
 * Shows range with total count: "1-20 of 864"
 *
 * @param {number} currentCount - Number of items on current page
 * @param {number} currentPage - Current page number (1-indexed)
 * @param {number} pageSize - Items per page
 * @param {number} totalRecords - Total count
 * @returns {string} Range text (e.g., "1-20 of 864")
 *
 * @example
 * calculateRangeText(20, 1, 20, 864);   // "1-20 of 864"
 * calculateRangeText(15, 44, 20, 864);  // "861-875 of 864"
 * calculateRangeText(0, 1, 20, 0);      // "0-0 of 0"
 */
export function calculateRangeText(currentCount, currentPage, pageSize, totalRecords) {
  if (currentCount === 0 && totalRecords === 0) {
    return '0-0 of 0';
  }

  if (currentCount === 0) {
    return 'No results';
  }

  const start = (currentPage - 1) * pageSize + 1;
  const end = start + currentCount - 1;

  return `${start}-${end} of ${totalRecords}`;
}

/**
 * Create an offset pagination state object for Vue components.
 *
 * Use this to initialize pagination reactive state in components.
 *
 * @param {number} pageSize - Default page size
 * @returns {Object} Initial pagination state
 *
 * @example
 * const pagination = reactive(createPaginationState(20));
 * // Returns: {
 * //   currentPage: 1,
 * //   pageSize: 20,
 * //   totalPages: 0,
 * //   totalRecords: 0
 * // }
 */
export function createPaginationState(pageSize = 20) {
  return {
    currentPage: 1,
    pageSize,
    totalPages: 0,
    totalRecords: 0,
  };
}

/**
 * Update pagination state after API response.
 *
 * @param {Object} state - Reactive pagination state object
 * @param {Object} meta - Pagination metadata from extractPaginationMeta
 */
export function updatePaginationState(state, meta) {
  state.currentPage = meta.currentPage;
  state.totalPages = meta.totalPages;
  state.totalRecords = meta.totalRecords;
}

/**
 * Calculate visible page numbers for pagination UI.
 *
 * Returns an array of page numbers to display, with ellipsis support.
 *
 * @param {number} currentPage - Current page number (1-indexed)
 * @param {number} totalPages - Total number of pages
 * @param {number} maxVisible - Maximum number of page buttons to show (default: 5)
 * @returns {Array} Array of page numbers to display
 *
 * @example
 * getVisiblePages(1, 10, 5);   // [1, 2, 3, 4, 5]
 * getVisiblePages(5, 10, 5);   // [3, 4, 5, 6, 7]
 * getVisiblePages(10, 10, 5);  // [6, 7, 8, 9, 10]
 */
export function getVisiblePages(currentPage, totalPages, maxVisible = 5) {
  if (totalPages <= maxVisible) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const half = Math.floor(maxVisible / 2);
  let start = Math.max(1, currentPage - half);
  let end = Math.min(totalPages, start + maxVisible - 1);

  // Adjust start if we're near the end
  if (end - start + 1 < maxVisible) {
    start = Math.max(1, end - maxVisible + 1);
  }

  return Array.from({ length: end - start + 1 }, (_, i) => start + i);
}
