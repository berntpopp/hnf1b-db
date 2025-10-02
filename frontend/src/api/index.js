// src/api/index.js
import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 10000,
});

// Optional interceptor to unwrap JSON:API responses that have "data" and "meta"
apiClient.interceptors.response.use(
  (response) => {
    if (response.data && typeof response.data === 'object' && 'data' in response.data) {
      return {
        data: response.data.data,
        meta: response.data.meta || {},
      };
    }
    return response;
  },
  (error) => Promise.reject(error)
);

/**
 * Get a list of individuals.
 *
 * @param {Object} params - Parameters for the API call.
 *   Expected keys:
 *     - page: The current page number.
 *     - page_size: The number of items per page.
 * @returns {Promise} Axios promise with the individuals data.
 */
export const getIndividuals = (params) => apiClient.get('/individuals/', { params });

/**
 * Get a list of publications.
 *
 * @param {Object} params - Parameters for the API call.
 * @returns {Promise} Axios promise with the publications data.
 */
export const getPublications = (params) => apiClient.get('/publications/', { params });

/**
 * Get a list of variants.
 *
 * @param {Object} params - Parameters for the API call.
 * @returns {Promise} Axios promise with the variants data.
 */
export const getVariants = (params) => apiClient.get('/variants/', { params });

/* --- Aggregation Endpoints --- */

/* Individuals Aggregations */
export const getIndividualsSexCount = () => apiClient.get('/aggregations/individuals/sex-count');

export const getIndividualsVariantTypeCount = () =>
  apiClient.get('/aggregations/variants/individual-count-by-type');

export const getIndividualsAgeOnsetCount = () =>
  apiClient.get('/aggregations/individuals/age-onset-count');

export const getIndividualsCohortCount = () =>
  apiClient.get('/aggregations/individuals/cohort-count');

export const getIndividualsFamilyHistoryCount = () =>
  apiClient.get('/aggregations/individuals/family-history-count');

export const getIndividualsDetectionMethodCount = () =>
  apiClient.get('/aggregations/individuals/detection-method-count');

export const getIndividualsSegregationCount = () =>
  apiClient.get('/aggregations/individuals/segregation-count');

/* Variants Aggregations */
export const getVariantsTypeCount = () => apiClient.get('/aggregations/variants/type-count');

export const getVariantsNewestClassificationVerdictCount = () =>
  apiClient.get('/aggregations/variants/newest-classification-verdict-count');

/* Publications Aggregations */
export const getPublicationsTypeCount = () =>
  apiClient.get('/aggregations/publications/type-count');

export const getPublicationsCumulativeCount = () =>
  apiClient.get('/aggregations/publications/cumulative-count');

/* Individuals Aggregations */
export const getPhenotypeDescribedCount = () =>
  apiClient.get('/aggregations/individuals/phenotype-described-count');

/* --- New Endpoints for Protein Plot --- */

/**
 * Get protein structure data.
 * Expected to return an array of protein objects.
 */
export const getProteins = () => apiClient.get('/proteins/');

/**
 * Get small variant data (mutations) for proteins.
 * Expected to return an object with a "small_variants" array.
 */
export const getVariantsSmallVariants = () =>
  apiClient.get('/aggregations/variants/small_variants');

/* --- New Endpoints for Search --- */

/**
 * Perform a case-insensitive search across Individuals, Variants, and Publications.
 *
 * @param {string} query - The user-entered query string.
 * @param {string} [collection] - (Optional) One of "individuals", "variants", or "publications".
 * @param {boolean} [reduceDoc] - If true, return only minimal fields.
 * @returns {Promise} Axios Promise resolving to the search results.
 */
export const search = (query, collection, reduceDoc = false) => {
  const params = { q: query };
  if (collection) {
    params.collection = collection;
  }
  if (reduceDoc) {
    params.reduce_doc = true;
  }
  return apiClient.get('/search/', { params });
};

/**
 * Fetch top-level summary stats:
 * {
 *   "individuals": 864,
 *   "total_reports": 939,
 *   "variants": 200,
 *   "publications": 160
 * }
 */
export const getSummary = () => apiClient.get('/aggregations/summary');
