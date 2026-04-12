// src/api/domain/aggregations.js — Aggregation and statistics endpoints
import { apiClient } from '../transport';

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
 * Get publications by type (for line chart visualization).
 * Returns publications with PMID, type, phenopacket count, and year from cached metadata.
 * Note: Requires `make publications-sync` to be run first to populate year data.
 * @returns {Promise} Axios promise with publications array including year
 */
export const getPublicationsByType = () =>
  apiClient.get('/phenopackets/aggregate/publications-by-type');

/**
 * Get pre-aggregated timeline data for publications chart.
 * Returns data aggregated by year and publication type, ready for visualization.
 * This avoids the need to query PubMed API from the frontend.
 * Note: Requires `make publications-sync` to be run first to populate year data.
 * @returns {Promise} Axios promise with timeline data array
 *   - year: Publication year
 *   - publication_type: Type of publication (case_series, research, etc.)
 *   - publication_count: Number of publications in this year/type
 *   - phenopacket_count: Total phenopackets from these publications
 */
export const getPublicationsTimelineData = () =>
  apiClient.get('/phenopackets/aggregate/publications-timeline-data');

/**
 * Get publication type distribution (for donut chart).
 * Returns aggregated counts by publication type (case_series, research, case_report, etc.).
 * @returns {Promise} Axios promise with publication type aggregation
 */
export const getPublicationTypes = () => apiClient.get('/phenopackets/aggregate/publication-types');

/**
 * Get age of onset distribution.
 * @returns {Promise} Axios promise with age of onset data
 */
export const getAgeOfOnsetAggregation = () => apiClient.get('/phenopackets/aggregate/age-of-onset');

/**
 * Get survival analysis data (Kaplan-Meier curves).
 * @param {Object} params - Query parameters
 * @param {string} params.comparison - Comparison type ('variant_type', 'pathogenicity', 'disease_subtype')
 * @returns {Promise} Axios promise with survival data including groups and statistical tests
 */
export const getSurvivalData = (params = {}) =>
  apiClient.get('/phenopackets/aggregate/survival-data', { params });

/**
 * Compare phenotype distributions between variant type groups.
 * @param {Object} params - Query parameters
 * @param {string} params.comparison - Type of comparison ('truncating_vs_non_truncating' or 'cnv_vs_point_mutation')
 * @param {number} params.limit - Maximum number of phenotypes to return (default: 20, max: 100)
 * @param {number} params.min_prevalence - Minimum prevalence (0-1) in at least one group (default: 0.05)
 * @param {string} params.sort_by - Sort by 'p_value', 'effect_size', or 'prevalence_diff' (default: 'p_value')
 * @returns {Promise} Axios promise with comparison results
 */
export const compareVariantTypes = (params) =>
  apiClient.get('/phenopackets/compare/variant-types', { params });

/**
 * Get small variants (SNVs) for protein plot visualization.
 * @returns {Promise} Axios promise with small variants data
 */
export const getSmallVariants = () => apiClient.get('/phenopackets/variants/small-variants');
