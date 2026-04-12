// src/api/domain/hpo.js — HPO autocomplete endpoints
import { apiClient } from '../transport';

/**
 * Get HPO term suggestions for autocomplete.
 * @param {string} query - Search query
 * @param {number} limit - Max results
 * @returns {Promise} Axios promise with HPO term suggestions
 */
export const getHPOAutocomplete = (query, limit = 10) => {
  return apiClient.get('/ontology/hpo/autocomplete', {
    params: { q: query, limit },
  });
};

/**
 * Search HPO terms by query string.
 * @param {string} query - Search query
 * @returns {Promise} Axios promise with HPO term suggestions
 */
export const searchHPOTerms = (query) =>
  apiClient.get('/hpo/autocomplete', { params: { q: query } });
