// src/api/index.js - Complete rewrite for v2 API (GA4GH Phenopackets)
import axios from 'axios';

const apiClient = axios.create({
  // Use Vite proxy in development (avoids CORS), direct URL in production
  baseURL: import.meta.env.VITE_API_URL || '/api/v2',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: Add JWT token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Handle errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

/**
 * Convert page-based pagination to skip/limit.
 * @param {number} page - Page number (1-indexed)
 * @param {number} pageSize - Items per page
 * @returns {Object} { skip, limit }
 */
export function pageToSkipLimit(page, pageSize) {
  return {
    skip: (page - 1) * pageSize,
    limit: pageSize,
  };
}

/* ==================== PHENOPACKETS ENDPOINTS ==================== */

/**
 * Get a list of phenopackets with optional filters.
 * @param {Object} params - Query parameters
 *   - skip: Number of records to skip (default: 0)
 *   - limit: Max records to return (default: 100, max: 1000)
 *   - sex: Filter by sex (MALE, FEMALE, OTHER_SEX, UNKNOWN_SEX)
 *   - has_variants: Filter by variant presence (boolean)
 * @returns {Promise} Axios promise with phenopackets data
 */
export const getPhenopackets = (params) => apiClient.get('/phenopackets/', { params });

/**
 * Get a single phenopacket by ID.
 * @param {string} id - Phenopacket ID
 * @returns {Promise} Axios promise with phenopacket document
 */
export const getPhenopacket = (id) => apiClient.get(`/phenopackets/${id}`);

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
 * Search phenopackets with advanced filters.
 * @param {Object} searchQuery - Search criteria
 *   - query: Text search query (optional)
 *   - hpo_terms: Array of HPO term IDs (optional)
 *   - diseases: Array of disease IDs (optional)
 *   - sex: Sex filter (optional)
 *   - has_variants: Variant presence filter (optional)
 * @returns {Promise} Axios promise with search results
 */
export const searchPhenopackets = (searchQuery) =>
  apiClient.post('/phenopackets/search', searchQuery);

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

/* ==================== AGGREGATION ENDPOINTS ==================== */

/**
 * Get summary statistics.
 * @returns {Promise} Axios promise with summary stats
 */
export const getSummaryStats = () => apiClient.get('/phenopackets/aggregate/summary');

/**
 * Get sex distribution across all phenopackets.
 * @returns {Promise} Axios promise with sex distribution data
 */
export const getSexDistribution = () =>
  apiClient.get('/phenopackets/aggregate/sex-distribution');

/**
 * Get HPO term frequency aggregation.
 * @param {Object} params - Query parameters
 *   - limit: Max number of results (default: 20)
 * @returns {Promise} Axios promise with phenotypic features aggregation
 */
export const getPhenotypicFeaturesAggregation = (params = {}) =>
  apiClient.get('/phenopackets/aggregate/by-feature', { params });

/**
 * Get disease frequency aggregation.
 * @param {Object} params - Query parameters
 *   - limit: Max number of results (default: 20)
 * @returns {Promise} Axios promise with disease aggregation
 */
export const getDiseaseAggregation = (params = {}) =>
  apiClient.get('/phenopackets/aggregate/by-disease', { params });

/**
 * Get variant pathogenicity distribution.
 * @param {Object} params - Query parameters
 * @param {string} params.count_mode - Count mode: 'all' (default) or 'unique'
 * @returns {Promise} Axios promise with pathogenicity counts
 */
export const getVariantPathogenicity = (params = {}) =>
  apiClient.get('/phenopackets/aggregate/variant-pathogenicity', { params });

/**
 * Get kidney disease stage distribution.
 * @returns {Promise} Axios promise with kidney stage data
 */
export const getKidneyStages = () => apiClient.get('/phenopackets/aggregate/kidney-stages');

/**
 * Get variant type distribution (SNV, CNV, etc.).
 * @param {Object} params - Query parameters
 * @param {string} params.count_mode - Count mode: 'all' (default) or 'unique'
 * @returns {Promise} Axios promise with variant type counts
 */
export const getVariantTypes = (params = {}) =>
  apiClient.get('/phenopackets/aggregate/variant-types', { params });

/**
 * Get publications aggregation with citation counts.
 * @returns {Promise} Axios promise with publication statistics
 */
export const getPublicationsAggregation = () =>
  apiClient.get('/phenopackets/aggregate/publications');

/**
 * Get age of onset distribution.
 * @returns {Promise} Axios promise with age of onset data
 */
export const getAgeOfOnsetAggregation = () =>
  apiClient.get('/phenopackets/aggregate/age-of-onset');

/**
 * Get small variants (SNVs) for protein plot visualization.
 * @returns {Promise} Axios promise with small variants data
 */
export const getSmallVariants = () => apiClient.get('/phenopackets/variants/small-variants');

/* ==================== PUBLICATION ENDPOINTS ==================== */

/**
 * Get publication metadata by PMID.
 * Fetches from PubMed API with database caching (90-day TTL).
 * @param {string} pmid - PubMed ID (with or without PMID: prefix)
 * @returns {Promise} Axios promise with publication metadata
 *   - pmid: PubMed ID
 *   - title: Article title
 *   - authors: Array of author objects {name, affiliation}
 *   - journal: Journal name
 *   - year: Publication year
 *   - doi: DOI identifier
 *   - abstract: Article abstract
 *   - data_source: "PubMed"
 *   - fetched_at: ISO timestamp
 */
export const getPublicationMetadata = (pmid) => apiClient.get(`/publications/${pmid}/metadata`);

/* ==================== AUTHENTICATION ENDPOINTS ==================== */

/**
 * Login user and get JWT token.
 * @param {Object} credentials - User credentials
 *   - username: Username
 *   - password: Password
 * @returns {Promise} Axios promise with token response
 */
export const login = (credentials) => apiClient.post('/auth/login', credentials);

/**
 * Get current user information.
 * @returns {Promise} Axios promise with user data
 */
export const getCurrentUser = () => apiClient.get('/auth/me');

/**
 * Logout user (client-side token removal).
 * @returns {Promise} Axios promise with logout confirmation
 */
export const logout = () => apiClient.post('/auth/logout');

/* ==================== HPO AUTOCOMPLETE ==================== */

/**
 * Search HPO terms by query string.
 * @param {string} query - Search query
 * @returns {Promise} Axios promise with HPO term suggestions
 */
export const searchHPOTerms = (query) =>
  apiClient.get('/hpo/autocomplete', { params: { q: query } });

/* ==================== CLINICAL ENDPOINTS ==================== */

/**
 * Get phenopackets with renal insufficiency.
 * @returns {Promise} Axios promise with clinical data
 */
export const getRenalInsufficiencyCases = () => apiClient.get('/clinical/renal-insufficiency');

/**
 * Get phenopackets with genital abnormalities.
 * @returns {Promise} Axios promise with clinical data
 */
export const getGenitalAbnormalitiesCases = () =>
  apiClient.get('/clinical/genital-abnormalities');

/**
 * Get phenopackets with diabetes.
 * @returns {Promise} Axios promise with clinical data
 */
export const getDiabetesCases = () => apiClient.get('/clinical/diabetes');

/**
 * Get phenopackets with hypomagnesemia.
 * @returns {Promise} Axios promise with clinical data
 */
export const getHypomagnesemiaCases = () => apiClient.get('/clinical/hypomagnesemia');

/* ==================== LEGACY COMPATIBILITY (DEPRECATED) ==================== */

/**
 * Helper to convert v1 pagination and warn about deprecation.
 * @private
 */
function deprecatedPaginationWrapper(warningMsg, newFn, params) {
  console.warn(warningMsg);
  const { page = 1, page_size = 10, ...rest } = params || {};
  const { skip, limit } = pageToSkipLimit(page, page_size);
  return newFn({ skip, limit, ...rest });
}

/**
 * Helper to warn about deprecation and call new function.
 * @private
 */
function deprecatedWrapper(warningMsg, newFn, ...args) {
  console.warn(warningMsg);
  return newFn(...args);
}

/**
 * @deprecated Use getPhenopackets() instead.
 * Legacy compatibility wrapper for old API.
 */
export const getIndividuals = (params) =>
  deprecatedPaginationWrapper(
    'getIndividuals() is deprecated. Use getPhenopackets() instead.',
    getPhenopackets,
    params
  );

/**
 * Get aggregated unique variants across all phenopackets.
 *
 * @param {Object} params - Query parameters
 * @param {number} params.page - Page number (1-indexed)
 * @param {number} params.page_size - Items per page
 * @param {string} [params.pathogenicity] - Filter by ACMG pathogenicity classification
 * @param {string} [params.gene] - Filter by gene symbol
 * @returns {Promise} Promise resolving to variants data with pagination metadata
 */
export const getVariants = async (params = {}) => {
  const { page = 1, page_size = 10, pathogenicity, gene } = params;
  const { skip, limit } = pageToSkipLimit(page, page_size);

  const response = await apiClient.get('/phenopackets/aggregate/all-variants', {
    params: {
      skip,
      limit,
      pathogenicity,
      gene,
    },
  });

  // Transform backend response to match expected format
  // Note: Backend returns plain array without total count
  // So we estimate total based on returned data
  const data = response.data || [];

  return {
    data: data.map(variant => ({
      id: variant.simple_id || variant.variant_id,
      simple_id: variant.simple_id,
      variant_id: variant.variant_id,
      label: variant.label,
      geneSymbol: variant.gene_symbol,
      geneId: variant.gene_id,
      variant_type: variant.structural_type,
      hg38: variant.hg38,
      transcript: variant.transcript,
      protein: variant.protein,
      classificationVerdict: variant.pathogenicity,
      individualCount: variant.phenopacket_count,
    })),
    meta: {
      // Since backend doesn't provide total count, we estimate
      // If we got fewer items than requested, we're on the last page
      total: data.length < limit ? skip + data.length : (page + 1) * page_size,
      total_pages: data.length < limit ? page : page + 1,
      current_page: page,
      page_size: page_size,
    },
  };
};

/**
 * @deprecated Publications are now stored in phenopacket.metaData.externalReferences.
 * Legacy compatibility wrapper for old API.
 */
export const getPublications = (params) =>
  deprecatedPaginationWrapper(
    'getPublications() is deprecated. Publications are in phenopacket.metaData.externalReferences.',
    getPhenopackets,
    params
  );

/**
 * @deprecated Use getSexDistribution() instead.
 */
export const getIndividualsSexCount = () =>
  deprecatedWrapper(
    'getIndividualsSexCount() is deprecated. Use getSexDistribution() instead.',
    getSexDistribution
  );

/**
 * @deprecated Use searchPhenopackets() instead.
 */
export const search = (query, collection, reduceDoc = false) =>
  deprecatedWrapper(
    'search() is deprecated. Use searchPhenopackets() instead.',
    searchPhenopackets,
    { query, collection, reduce_doc: reduceDoc }
  );

/**
 * @deprecated Use getSummaryStats() instead.
 */
export const getSummary = () =>
  deprecatedWrapper('getSummary() is deprecated. Use getSummaryStats() instead.', getSummaryStats);

export default apiClient;
