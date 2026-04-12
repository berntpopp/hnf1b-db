// src/api/domain/phenopackets.js — Phenopacket CRUD, batch, search, and filter endpoints
import { apiClient } from '../transport';

/**
 * DEPRECATED: Use cursor pagination instead.
 * This function is kept for backwards compatibility during migration.
 * @deprecated Use buildCursorParams from @/utils/pagination instead
 */
export function pageToSkipLimit(page, pageSize) {
  return {
    skip: (page - 1) * pageSize,
    limit: pageSize,
  };
}

/**
 * Get a list of phenopackets with JSON:API pagination and filtering.
 * Supports offset pagination, cursor pagination, and legacy skip/limit for backwards compatibility.
 *
 * **JSON:API Offset Pagination (Simple):**
 * @param {Object} params - Query parameters
 *   - page[number]: Page number (1-indexed, default: 1)
 *   - page[size]: Items per page (default: 100, max: 500)
 *   - filter[sex]: Filter by sex (MALE, FEMALE, OTHER_SEX, UNKNOWN_SEX)
 *   - filter[has_variants]: Filter by variant presence (boolean)
 *   - sort: Comma-separated fields to sort by (prefix with '-' for descending)
 *
 * **JSON:API Cursor Pagination (Stable, Recommended):**
 *   - page[after]: Cursor token for next page (opaque token from meta.page.endCursor)
 *   - page[before]: Cursor token for previous page (opaque token from meta.page.startCursor)
 *   - page[size]: Items per page (default: 100, max: 500)
 *   - Cursors provide stable results even when data changes during browsing
 *
 * **Legacy Parameters (Deprecated, auto-converted to JSON:API):**
 *   - skip: Number of records to skip (converted to page[number])
 *   - limit: Max records to return (converted to page[size])
 *   - sex: Filter by sex (converted to filter[sex])
 *   - has_variants: Filter by variant presence (converted to filter[has_variants])
 *
 * **Response Format (JSON:API):**
 * Returns { data, meta, links } where:
 *   - data: Array of phenopacket documents
 *   - meta.page: Offset pagination → { currentPage, pageSize, totalPages, totalRecords }
 *   - meta.page: Cursor pagination → { pageSize, hasNextPage, hasPreviousPage, startCursor, endCursor }
 *   - links: { self, first, prev, next, last } (or { self, first, prev, next } for cursor)
 *
 * @returns {Promise} Axios promise resolving to JSON:API response
 *
 * @example
 * // Offset pagination (simple, may skip/duplicate records if data changes)
 * getPhenopackets({
 *   'page[number]': 1,
 *   'page[size]': 20,
 *   'filter[sex]': 'MALE',
 *   'sort': '-created_at'
 * })
 *
 * @example
 * // Cursor pagination (stable, recommended for browsing)
 * const response1 = await getPhenopackets({ 'page[size]': 20 })
 * const nextCursor = response1.meta.page.endCursor
 * const response2 = await getPhenopackets({ 'page[after]': nextCursor, 'page[size]': 20 })
 *
 * @example
 * // Legacy style (auto-converted to JSON:API)
 * getPhenopackets({ skip: 0, limit: 20, sex: 'MALE' })
 */
export const getPhenopackets = (params) => apiClient.get('/phenopackets/', { params });

/**
 * Get a single phenopacket by ID.
 * @param {string} id - Phenopacket ID
 * @returns {Promise} Axios promise with phenopacket document
 */
export const getPhenopacket = (id) => apiClient.get(`/phenopackets/${id}`);

/**
 * Get phenotype timeline for an individual phenopacket.
 * Returns temporal data for phenotypic features with onset ages and evidence.
 * @param {string} id - Phenopacket ID
 * @returns {Promise} Axios promise with timeline data
 *   - subject_id: Subject identifier
 *   - current_age: Current age (ISO8601 duration)
 *   - features: Array of phenotypic features with onset/evidence
 */
export const getPhenotypeTimeline = (id) => apiClient.get(`/phenopackets/${id}/timeline`);

/**
 * Create a new phenopacket (requires curator role).
 * @param {Object} phenopacketData - Phenopacket data following GA4GH Phenopackets v2 standard
 * @returns {Promise} Axios promise with created phenopacket
 */
export const createPhenopacket = (phenopacketData) =>
  apiClient.post('/phenopackets/', phenopacketData);

/**
 * Update an existing phenopacket (requires curator role).
 * @param {string} id - Phenopacket ID
 * @param {Object} data - Update data object
 * @param {Object} data.phenopacket - Updated phenopacket data
 * @param {number} data.revision - Current revision for optimistic locking
 * @param {string} data.change_reason - Reason for the change (audit trail)
 * @returns {Promise} Axios promise with updated phenopacket
 */
export const updatePhenopacket = (id, data) =>
  apiClient.put(`/phenopackets/${id}`, {
    phenopacket: data.phenopacket,
    revision: data.revision,
    change_reason: data.change_reason,
  });

/**
 * Delete a phenopacket (soft delete, requires curator role).
 * @param {string} id - Phenopacket ID
 * @param {string} changeReason - Reason for deletion (required for audit trail)
 * @returns {Promise} Axios promise with deletion confirmation
 */
export const deletePhenopacket = (id, changeReason) =>
  apiClient.delete(`/phenopackets/${id}`, {
    params: { change_reason: changeReason },
  });

/**
 * Get audit history for a phenopacket.
 * @param {string} id - Phenopacket ID
 * @returns {Promise} Axios promise with array of audit entries
 */
export const getPhenopacketAuditHistory = (id) => apiClient.get(`/phenopackets/${id}/audit`);

/**
 * Get multiple phenopackets by IDs in a single request.
 * Prevents N+1 query problem.
 * @param {Array<string>} phenopacketIds - Array of phenopacket IDs
 * @returns {Promise} Axios promise with array of phenopacket documents
 */
export const getPhenopacketsBatch = (phenopacketIds) =>
  apiClient.get('/phenopackets/batch', {
    params: { phenopacket_ids: phenopacketIds.join(',') },
  });

/**
 * Search phenopackets with advanced filters using GET request.
 * @param {Object} params - Search criteria as query parameters
 *   - q: Full-text search query (optional)
 *   - hpo_id: HPO term ID (optional)
 *   - sex: Subject sex (optional)
 *   - gene: Gene symbol (optional)
 *   - pmid: Publication PMID (optional)
 *   - rank_by_relevance: Sort by search rank (optional, default: true)
 * @returns {Promise} Axios promise with search results
 */
export const searchPhenopackets = (params) => apiClient.get('/phenopackets/search', { params });

/**
 * Get facet counts for search filters based on current search criteria.
 * @param {Object} params - Search criteria as query parameters
 *   - q: Full-text search query (optional)
 *   - hpo_id: HPO term ID (optional)
 *   - sex: Subject sex (optional)
 *   - gene: Gene symbol (optional)
 *   - pmid: Publication PMID (optional)
 * @returns {Promise} Axios promise with facet counts for filters
 */
export const getSearchFacets = (params) => apiClient.get('/phenopackets/search/facets', { params });

/**
 * Get phenopackets filtered by sex.
 * @param {string} sex - Sex value (MALE, FEMALE, OTHER_SEX, UNKNOWN_SEX)
 * @param {Object} params - Additional query parameters
 * @returns {Promise} Axios promise with filtered phenopackets
 */
export const getPhenopacketsBySex = (sex, params = {}) =>
  apiClient.get('/phenopackets/', { params: { ...params, sex } });

/**
 * Get phenopackets that contain genomic interpretations.
 * @param {Object} params - Query parameters
 * @returns {Promise} Axios promise with phenopackets containing variants
 */
export const getPhenopacketsWithVariants = (params = {}) =>
  apiClient.get('/phenopackets/', { params: { ...params, has_variants: true } });

/**
 * Get phenopackets citing a specific publication.
 * Server-side filtering for better performance.
 * @param {string} pmid - PubMed ID (with or without PMID: prefix)
 * @param {Object} params - Query parameters
 *   - skip: Pagination offset (default: 0)
 *   - limit: Max records (default: 100, max: 500)
 *   - sex: Filter by sex (optional)
 *   - has_variants: Filter by variant presence (optional)
 * @returns {Promise} Axios promise with filtered phenopackets and pagination info
 */
export const getPhenopacketsByPublication = (pmid, params = {}) =>
  apiClient.get(`/phenopackets/by-publication/${pmid}`, { params });

/**
 * Get phenotypic features for multiple phenopackets (batch).
 * @param {string} phenopacketIds - Comma-separated phenopacket IDs
 * @returns {Promise} Axios promise with features data
 */
export const getPhenotypicFeaturesBatch = (phenopacketIds) =>
  apiClient.get('/phenopackets/features/batch', {
    params: { phenopacket_ids: phenopacketIds },
  });

/**
 * Get variants for multiple phenopackets (batch).
 * @param {string} phenopacketIds - Comma-separated phenopacket IDs
 * @returns {Promise} Axios promise with variants data
 */
export const getVariantsBatch = (phenopacketIds) =>
  apiClient.get('/phenopackets/variants/batch', {
    params: { phenopacket_ids: phenopacketIds },
  });

/**
 * Get all phenopackets that contain a specific variant.
 * @param {string} variantId - The variant ID to search for
 * @returns {Promise} Axios promise with phenopackets containing this variant
 */
export const getPhenopacketsByVariant = (variantId) =>
  apiClient.get(`/phenopackets/by-variant/${encodeURIComponent(variantId)}`);
