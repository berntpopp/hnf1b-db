/**
 * Color mapping utilities for variant classifications and types.
 *
 * Provides consistent color schemes across all components for:
 * - Pathogenicity classifications (ACMG guidelines)
 * - Variant types (SNV, deletion, duplication, etc.)
 *
 * @module utils/colors
 */

/**
 * Pathogenicity classification Vuetify color mapping.
 * Based on ACMG/AMP guidelines for variant interpretation.
 */
const PATHOGENICITY_VUETIFY_COLORS = {
  PATHOGENIC: 'red-lighten-1',
  LIKELY_PATHOGENIC: 'orange-lighten-1',
  UNCERTAIN_SIGNIFICANCE: 'yellow-darken-1',
  VUS: 'yellow-darken-1',
  LIKELY_BENIGN: 'light-green-lighten-1',
  BENIGN: 'green-lighten-1',
};

/**
 * Pathogenicity classification hex color mapping.
 * Used for D3/SVG visualizations where hex colors are required.
 */
const PATHOGENICITY_HEX_COLORS = {
  PATHOGENIC: '#EF5350', // red-lighten-1
  LIKELY_PATHOGENIC: '#FF9800', // orange
  UNCERTAIN_SIGNIFICANCE: '#FBC02D', // yellow-darken-1
  VUS: '#FBC02D', // yellow-darken-1
  LIKELY_BENIGN: '#9CCC65', // light-green-lighten-1
  BENIGN: '#66BB6A', // green-lighten-1
};

/**
 * Pathogenicity score mapping for sorting/prioritization.
 * Higher scores = more clinically significant.
 */
const PATHOGENICITY_SCORES = {
  PATHOGENIC: 5,
  LIKELY_PATHOGENIC: 4,
  UNCERTAIN_SIGNIFICANCE: 3,
  VUS: 3,
  LIKELY_BENIGN: 2,
  BENIGN: 1,
};

/**
 * Variant type color mapping.
 * Provides visual distinction between different mutation types.
 */
const VARIANT_TYPE_COLORS = {
  SNV: 'purple-lighten-3',
  deletion: 'red-lighten-3',
  duplication: 'blue-lighten-3',
  insertion: 'green-lighten-3',
  indel: 'pink-lighten-3',
  inversion: 'orange-lighten-3',
  CNV: 'amber-lighten-3',
};

/**
 * Normalize a classification string to a standard key.
 * Handles various input formats (spaces, underscores, mixed case).
 *
 * @param {string|null|undefined} classification - Raw classification string
 * @returns {string|null} Normalized key or null if invalid
 * @private
 */
function normalizeClassification(classification) {
  if (!classification) return null;

  const normalized = classification.toUpperCase().trim();

  // Check for exact matches first
  if (normalized.includes('PATHOGENIC') && !normalized.includes('LIKELY')) {
    return 'PATHOGENIC';
  }
  if (normalized.includes('LIKELY_PATHOGENIC') || normalized.includes('LIKELY PATHOGENIC')) {
    return 'LIKELY_PATHOGENIC';
  }
  if (normalized.includes('UNCERTAIN') || normalized === 'VUS') {
    return 'VUS';
  }
  if (normalized.includes('LIKELY_BENIGN') || normalized.includes('LIKELY BENIGN')) {
    return 'LIKELY_BENIGN';
  }
  if (normalized.includes('BENIGN') && !normalized.includes('LIKELY')) {
    return 'BENIGN';
  }

  return null;
}

/**
 * Get Vuetify color class for a pathogenicity classification.
 *
 * @param {string|null|undefined} pathogenicity - Classification string
 * @returns {string} Vuetify color class
 *
 * @example
 * getPathogenicityColor('PATHOGENIC') // Returns: 'red-lighten-1'
 * getPathogenicityColor('Likely Pathogenic') // Returns: 'orange-lighten-1'
 * getPathogenicityColor('VUS') // Returns: 'yellow-darken-1'
 * getPathogenicityColor(null) // Returns: 'grey-lighten-1'
 */
export function getPathogenicityColor(pathogenicity) {
  const key = normalizeClassification(pathogenicity);
  return key ? PATHOGENICITY_VUETIFY_COLORS[key] : 'grey-lighten-1';
}

/**
 * Get hex color for a pathogenicity classification.
 * Used for D3/SVG visualizations where hex colors are required.
 *
 * @param {string|null|undefined} pathogenicity - Classification string
 * @returns {string} Hex color code
 *
 * @example
 * getPathogenicityHexColor('PATHOGENIC') // Returns: '#EF5350'
 * getPathogenicityHexColor('VUS') // Returns: '#FBC02D'
 * getPathogenicityHexColor(null) // Returns: '#BDBDBD'
 */
export function getPathogenicityHexColor(pathogenicity) {
  const key = normalizeClassification(pathogenicity);
  return key ? PATHOGENICITY_HEX_COLORS[key] : '#BDBDBD';
}

/**
 * Get numeric score for a pathogenicity classification.
 * Used for sorting variants by clinical significance.
 *
 * @param {string|null|undefined} pathogenicity - Classification string
 * @returns {number} Score (5=pathogenic, 1=benign, 0=unknown)
 *
 * @example
 * getPathogenicityScore('PATHOGENIC') // Returns: 5
 * getPathogenicityScore('VUS') // Returns: 3
 * getPathogenicityScore(null) // Returns: 0
 */
export function getPathogenicityScore(pathogenicity) {
  const key = normalizeClassification(pathogenicity);
  return key ? PATHOGENICITY_SCORES[key] : 0;
}

/**
 * Check if a classification matches a specific pathogenicity category.
 * Used for filtering variants by classification.
 *
 * @param {string|null|undefined} classification - Classification string to check
 * @param {string} category - Category to match (PATHOGENIC, LIKELY_PATHOGENIC, VUS, LIKELY_BENIGN, BENIGN)
 * @returns {boolean} True if classification matches category
 *
 * @example
 * matchesPathogenicityCategory('Pathogenic', 'PATHOGENIC') // Returns: true
 * matchesPathogenicityCategory('Likely Pathogenic', 'PATHOGENIC') // Returns: false
 * matchesPathogenicityCategory('VUS', 'VUS') // Returns: true
 */
export function matchesPathogenicityCategory(classification, category) {
  const normalizedClassification = normalizeClassification(classification);
  const normalizedCategory = normalizeClassification(category);
  return normalizedClassification === normalizedCategory;
}

/**
 * Get Vuetify color class for a variant type.
 *
 * @param {string|null|undefined} variantType - Variant type string
 * @returns {string} Vuetify color class
 *
 * @example
 * getVariantTypeColor('SNV') // Returns: 'purple-lighten-3'
 * getVariantTypeColor('deletion') // Returns: 'red-lighten-3'
 * getVariantTypeColor('CNV') // Returns: 'amber-lighten-3'
 * getVariantTypeColor(null) // Returns: 'grey-lighten-2'
 */
export function getVariantTypeColor(variantType) {
  if (!variantType) return 'grey-lighten-2';

  return VARIANT_TYPE_COLORS[variantType] ?? 'grey-lighten-2';
}

/**
 * Get Vuetify color class for a classification (alias for pathogenicity).
 * Used in contexts where "classification" terminology is preferred.
 *
 * @param {string|null|undefined} classification - Classification string
 * @returns {string} Vuetify color class
 */
export function getClassificationColor(classification) {
  return getPathogenicityColor(classification);
}
