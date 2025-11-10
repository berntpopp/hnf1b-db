/**
 * Pagination and sorting utilities for Vue components.
 * Provides reusable functions for JSON:API compliant pagination and sorting.
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
 * Build JSON:API pagination parameters from page number and size.
 *
 * @param {number} page - Page number (1-indexed)
 * @param {number} pageSize - Number of items per page
 * @returns {Object} JSON:API pagination parameters
 *   Example: { 'page[number]': 1, 'page[size]': 20 }
 *
 * @example
 * const params = buildPaginationParameters(2, 50);
 * // Returns: { 'page[number]': 2, 'page[size]': 50 }
 */
export function buildPaginationParameters(page, pageSize) {
  return {
    'page[number]': page,
    'page[size]': pageSize,
  };
}

/**
 * Calculate range text for pagination display.
 *
 * @param {number} page - Current page number (1-indexed)
 * @param {number} pageSize - Number of items per page
 * @param {number} totalItems - Total number of items
 * @returns {string} Range text (e.g., "1-20 of 864" or "0 of 0")
 *
 * @example
 * const rangeText = calculateRangeText(1, 20, 864);
 * // Returns: "1-20 of 864"
 *
 * @example
 * const rangeText = calculateRangeText(1, 20, 0);
 * // Returns: "0 of 0"
 */
export function calculateRangeText(page, pageSize, totalItems) {
  if (totalItems === 0) {
    return '0 of 0';
  }

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, totalItems);

  return `${start}-${end} of ${totalItems}`;
}

/**
 * Extract pagination metadata from JSON:API response.
 * Supports both offset pagination and cursor pagination.
 *
 * @param {Object} response - Axios response object
 * @returns {Object} Pagination metadata
 *   Offset pagination:
 *     - totalRecords: Total number of records
 *     - totalPages: Total number of pages
 *     - currentPage: Current page number
 *     - pageSize: Number of items per page
 *     - type: 'offset'
 *   Cursor pagination:
 *     - pageSize: Number of items per page
 *     - hasNextPage: Whether there's a next page
 *     - hasPreviousPage: Whether there's a previous page
 *     - startCursor: Cursor for the first item (opaque token)
 *     - endCursor: Cursor for the last item (opaque token)
 *     - type: 'cursor'
 *
 * @example
 * // Offset pagination
 * const meta = extractPaginationMeta(response);
 * // Returns: { type: 'offset', totalRecords: 864, totalPages: 44, currentPage: 1, pageSize: 20 }
 *
 * @example
 * // Cursor pagination
 * const meta = extractPaginationMeta(response);
 * // Returns: { type: 'cursor', pageSize: 20, hasNextPage: true, hasPreviousPage: false, startCursor: '...', endCursor: '...' }
 */
export function extractPaginationMeta(response) {
  const data = response.data || {};
  const meta = data.meta || {};
  const page = meta.page || {};

  // Detect pagination type by presence of cursor-specific fields
  const isCursorPagination = 'hasNextPage' in page || 'hasPreviousPage' in page;

  if (isCursorPagination) {
    // Cursor pagination
    return {
      type: 'cursor',
      pageSize: page.pageSize || 20,
      hasNextPage: page.hasNextPage || false,
      hasPreviousPage: page.hasPreviousPage || false,
      startCursor: page.startCursor || null,
      endCursor: page.endCursor || null,
    };
  } else {
    // Offset pagination
    return {
      type: 'offset',
      totalRecords: page.totalRecords || 0,
      totalPages: page.totalPages || 0,
      currentPage: page.currentPage || 1,
      pageSize: page.pageSize || 20,
    };
  }
}

/**
 * Build cursor pagination parameters for next/previous page.
 *
 * @param {string|null} cursor - Cursor token (startCursor or endCursor from pagination meta)
 * @param {number} pageSize - Number of items per page
 * @param {'after'|'before'} direction - Direction to paginate
 * @returns {Object} JSON:API cursor pagination parameters
 *   Example: { 'page[after]': 'eyJpZCI6IjEyMyJ9', 'page[size]': 20 }
 *
 * @example
 * const nextParams = buildCursorPaginationParameters(meta.endCursor, 20, 'after');
 * // Returns: { 'page[after]': 'eyJpZCI6IjEyMyJ9', 'page[size]': 20 }
 *
 * @example
 * const prevParams = buildCursorPaginationParameters(meta.startCursor, 20, 'before');
 * // Returns: { 'page[before]': 'eyJpZCI6IjEyMyJ9', 'page[size]': 20 }
 */
export function buildCursorPaginationParameters(cursor, pageSize, direction = 'after') {
  if (!cursor) {
    // No cursor - return initial page with empty cursor to trigger cursor pagination mode
    // Backend detects cursor pagination by presence of page[after]/page[before] param
    return {
      'page[after]': '', // Empty string triggers cursor pagination mode
      'page[size]': pageSize,
    };
  }

  return {
    [`page[${direction}]`]: cursor,
    'page[size]': pageSize,
  };
}
