// src/api/domain/variants.js — Variant aggregation endpoints
import { apiClient } from '../transport';

/**
 * Get aggregated unique variants across all phenopackets with search and filters.
 * Uses offset-based pagination (JSON:API v1.1).
 *
 * @param {Object} params - Query parameters
 * @param {number} params.page - Page number (1-indexed, default: 1)
 * @param {number} params.pageSize - Items per page (default: 10)
 * @param {string} [params.query] - Text search (HGVS, variant ID, coordinates)
 * @param {string} [params.variant_type] - Filter by variant type (SNV, deletion, etc.)
 * @param {string} [params.classification] - Filter by ACMG classification
 * @param {string} [params.consequence] - Filter by molecular consequence
 * @param {string} [params.sort] - Sort field (prefix with '-' for descending order)
 * @returns {Promise} Promise resolving to variants data with offset pagination metadata
 */
export const getVariants = async (params = {}) => {
  const {
    page = 1,
    pageSize = 10,
    query,
    variant_type,
    classification,
    consequence,
    domain,
    sort,
  } = params;

  const response = await apiClient.get('/phenopackets/aggregate/all-variants', {
    params: {
      'page[number]': page,
      'page[size]': pageSize,
      query,
      variant_type,
      classification,
      consequence,
      domain,
      sort,
    },
  });

  // Backend returns JSON:API offset response
  const responseData = response.data || {};
  const data = responseData.data || [];
  const meta = responseData.meta?.page || {};

  return {
    data: data.map((variant) => ({
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
      pathogenicity: variant.pathogenicity, // Alias for DNA Distance Analysis
      individualCount: variant.phenopacket_count,
      molecular_consequence: variant.molecular_consequence,
    })),
    meta: {
      currentPage: meta.currentPage || page,
      pageSize: meta.pageSize || pageSize,
      totalPages: meta.totalPages || 0,
      totalRecords: meta.totalRecords || 0,
    },
  };
};
