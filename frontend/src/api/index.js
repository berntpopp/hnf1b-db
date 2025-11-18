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

// Flag to prevent infinite refresh loops
let isRefreshing = false;
// Queue for failed requests during token refresh
let failedRequestsQueue = [];

/**
 * Process queued requests after token refresh.
 * @param {Error|null} error - Error if refresh failed
 * @param {string|null} token - New access token if refresh succeeded
 */
function processQueue(error, token = null) {
  failedRequestsQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
    } else {
      promise.resolve(token);
    }
  });
  failedRequestsQueue = [];
}

// Request interceptor: Add JWT token from localStorage
// Note: We use localStorage directly here for performance (synchronous)
// The auth store manages the same tokens and keeps them in sync
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

// Response interceptor: Handle token refresh on 401 errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If 401 and not already retrying, attempt token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Skip refresh for auth endpoints to prevent infinite loops
      if (
        originalRequest.url?.includes('/auth/login') ||
        originalRequest.url?.includes('/auth/refresh')
      ) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        // Another request is already refreshing, queue this one
        return new Promise((resolve, reject) => {
          failedRequestsQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Import auth store dynamically to avoid circular dependency
        const { useAuthStore } = await import('@/stores/authStore');
        const authStore = useAuthStore();

        // Attempt to refresh access token
        const newAccessToken = await authStore.refreshAccessToken();

        // Success! Process queued requests with new token
        processQueue(null, newAccessToken);
        isRefreshing = false;

        // Retry original request with new token
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed - clear queue and redirect to login
        processQueue(refreshError, null);
        isRefreshing = false;

        // Clear auth state and redirect
        window.logService.warn('Token refresh failed, redirecting to login');
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');

        // Only redirect if not already on login page
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }

        return Promise.reject(refreshError);
      }
    }

    // For other errors or if retry failed, just reject
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
 * Get a list of phenopackets with JSON:API pagination and filtering.
 * Supports offset pagination, cursor pagination, and legacy skip/limit for backwards compatibility.
 *
 * **JSON:API Offset Pagination (Simple):**
 * @param {Object} params - Query parameters
 *   - page[number]: Page number (1-indexed, default: 1)
 *   - page[size]: Items per page (default: 100, max: 1000)
 *   - filter[sex]: Filter by sex (MALE, FEMALE, OTHER_SEX, UNKNOWN_SEX)
 *   - filter[has_variants]: Filter by variant presence (boolean)
 *   - sort: Comma-separated fields to sort by (prefix with '-' for descending)
 *
 * **JSON:API Cursor Pagination (Stable, Recommended):**
 *   - page[after]: Cursor token for next page (opaque token from meta.page.endCursor)
 *   - page[before]: Cursor token for previous page (opaque token from meta.page.startCursor)
 *   - page[size]: Items per page (default: 100, max: 1000)
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
  apiClient.get(`/phenopackets/by-variant/${variantId}`);

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
export const getSexDistribution = () => apiClient.get('/phenopackets/aggregate/sex-distribution');

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
export const getAgeOfOnsetAggregation = () => apiClient.get('/phenopackets/aggregate/age-of-onset');

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
export const getGenitalAbnormalitiesCases = () => apiClient.get('/clinical/genital-abnormalities');

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

/**
 * Get aggregated unique variants across all phenopackets with search and filters.
 * Implements backend search endpoint from Issue #64.
 *
 * @param {Object} params - Query parameters
 * @param {number} params.page - Page number (1-indexed)
 * @param {number} params.page_size - Items per page
 * @param {string} [params.query] - Text search (HGVS, variant ID, coordinates)
 * @param {string} [params.variant_type] - Filter by variant type (SNV, deletion, etc.)
 * @param {string} [params.classification] - Filter by ACMG classification
 * @param {string} [params.consequence] - Filter by molecular consequence
 * @param {string} [params.pathogenicity] - DEPRECATED: use classification instead
 * @param {string} [params.sort] - Sort field (prefix with '-' for descending order)
 * @returns {Promise} Promise resolving to variants data with pagination metadata
 */
export const getVariants = async (params = {}) => {
  const {
    page = 1,
    page_size = 10,
    query,
    variant_type,
    classification,
    consequence,
    domain,
    pathogenicity,
    sort,
  } = params;
  const { skip, limit } = pageToSkipLimit(page, page_size);

  const response = await apiClient.get('/phenopackets/aggregate/all-variants', {
    params: {
      skip,
      limit,
      query,
      variant_type,
      classification: classification || pathogenicity, // Support both new and legacy params
      consequence,
      domain,
      sort,
    },
  });

  // Backend now returns { data: [...], total: N, skip: N, limit: N }
  const responseData = response.data || {};
  const data = responseData.data || [];
  const total = responseData.total || 0;

  return {
    data: data.map((variant) => ({
      // 'id' uses 'simple_id' if present, otherwise falls back to 'variant_id'.
      // This fallback may cause ambiguity; ideally, the backend should always provide 'simple_id'.
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
      molecular_consequence: variant.molecular_consequence,
    })),
    meta: {
      // Backend provides accurate total count
      total: total,
      total_pages: Math.ceil(total / page_size),
      current_page: page,
      page_size: page_size,
    },
  };
};

/* ==================== REFERENCE GENOME ENDPOINTS ==================== */

/**
 * Get list of all available genome assemblies.
 * @returns {Promise} Axios promise with genome assemblies
 */
export const getReferenceGenomes = () => apiClient.get('/reference/genomes');

/**
 * Query genes by symbol or chromosome.
 * @param {Object} params - Query parameters
 *   - symbol: Gene symbol to filter (e.g., "HNF1B")
 *   - chromosome: Chromosome to filter (e.g., "17")
 *   - genome_build: Genome assembly name (default: GRCh38)
 * @returns {Promise} Axios promise with genes array
 */
export const getReferenceGenes = (params = {}) => apiClient.get('/reference/genes', { params });

/**
 * Get gene details with transcripts.
 * @param {string} symbol - Gene symbol (e.g., "HNF1B")
 * @param {string} genomeBuild - Genome assembly name (default: GRCh38)
 * @returns {Promise} Axios promise with gene details
 */
export const getReferenceGene = (symbol, genomeBuild = 'GRCh38') =>
  apiClient.get(`/reference/genes/${symbol}`, {
    params: { genome_build: genomeBuild },
  });

/**
 * Get all transcript isoforms for a gene with exon coordinates.
 * @param {string} symbol - Gene symbol (e.g., "HNF1B")
 * @param {string} genomeBuild - Genome assembly name (default: GRCh38)
 * @returns {Promise} Axios promise with transcripts array
 */
export const getReferenceGeneTranscripts = (symbol, genomeBuild = 'GRCh38') =>
  apiClient.get(`/reference/genes/${symbol}/transcripts`, {
    params: { genome_build: genomeBuild },
  });

/**
 * Get protein domains for a gene's canonical transcript.
 * @param {string} symbol - Gene symbol (e.g., "HNF1B")
 * @param {string} genomeBuild - Genome assembly name (default: GRCh38)
 * @returns {Promise} Axios promise with protein domains
 *   - gene: Gene symbol
 *   - protein: RefSeq protein ID
 *   - uniprot: UniProt accession
 *   - length: Protein length (amino acids)
 *   - domains: Array of domain objects with name, start, end, function
 *   - genome_build: Genome assembly
 *   - updated_at: Last update timestamp
 */
export const getReferenceGeneDomains = (symbol, genomeBuild = 'GRCh38') =>
  apiClient.get(`/reference/genes/${symbol}/domains`, {
    params: { genome_build: genomeBuild },
  });

/**
 * Get all genes in a genomic region.
 * @param {string} region - Genomic region in format "chr:start-end" (e.g., "17:36000000-37000000")
 * @param {string} genomeBuild - Genome assembly name (default: GRCh38)
 * @returns {Promise} Axios promise with genes in region
 */
export const getReferenceGenomicRegion = (region, genomeBuild = 'GRCh38') =>
  apiClient.get(`/reference/regions/${region}`, {
    params: { genome_build: genomeBuild },
  });

/* ==================== VARIANT ANNOTATION ENDPOINTS ==================== */

/**
 * Annotate a variant using Ensembl Variant Effect Predictor (VEP).
 * Returns comprehensive variant annotations including consequence predictions,
 * impact severity, CADD scores, and gnomAD frequencies.
 *
 * @param {string} variant - Variant notation in one of these formats:
 *   - HGVS: "NM_000458.4:c.544+1G>A" or "NC_000017.11:g.36459258A>G"
 *   - VCF: "17-36459258-A-G" or "chr17-36459258-A-G"
 *   - rsID: "rs56116432"
 * @returns {Promise} Axios promise with VEP annotation data
 *   - id: Variant identifier
 *   - input: Original input notation
 *   - allele_string: Reference/alternate alleles
 *   - most_severe_consequence: Most severe predicted consequence (e.g., "missense_variant")
 *   - transcript_consequences: Array of transcript annotations
 *   - colocated_variants: Array of known variants (rsIDs, gnomAD)
 *   - cadd: CADD scores object (PHRED, raw) if available
 *   - gnomad: gnomAD allele frequency object if available
 *   - impact: Impact severity (HIGH, MODERATE, LOW, MODIFIER)
 */
export const annotateVariant = (variant) =>
  apiClient.post('/variants/annotate', null, {
    params: { variant },
  });

export default apiClient;
