// src/api/domain/search.js — Global search endpoints
import { apiClient } from '../transport';

/**
 * Get autocomplete suggestions for global search.
 * @param {string} q - Search query
 * @param {number} limit - Max results
 * @returns {Promise} Axios promise with search suggestions
 */
export const searchAutocomplete = (q, limit = 10) =>
  apiClient.get('/search/autocomplete', { params: { q, limit } });

/**
 * Perform a global full-text search.
 * @param {string} q - Search query
 * @param {number} page - Page number
 * @param {number} pageSize - Page size
 * @param {string} type - Filter by type
 * @returns {Promise} Axios promise with search results
 */
export const searchGlobal = (q, page = 1, pageSize = 20, type = null) =>
  apiClient.get('/search/global', { params: { q, page, page_size: pageSize, type } });
