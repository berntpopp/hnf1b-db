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
 * Pathogenicity classification color mapping.
 * Based on ACMG/AMP guidelines for variant interpretation.
 */
const PATHOGENICITY_COLORS = {
  PATHOGENIC: 'red', // Red for pathogenic
  LIKELY_PATHOGENIC: 'orange', // Orange for likely pathogenic
  UNCERTAIN_SIGNIFICANCE: 'yellow-darken-1', // Yellow for VUS
  VUS: 'yellow-darken-1', // Variant of Uncertain Significance (alias)
  LIKELY_BENIGN: 'light-green', // Light green for likely benign
  BENIGN: 'green', // Green for benign
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
 * Get Vuetify color class for a pathogenicity classification.
 *
 * @param {string|null|undefined} pathogenicity - Classification string
 * @returns {string} Vuetify color class
 *
 * @example
 * getPathogenicityColor('PATHOGENIC') // Returns: 'red-lighten-3'
 * getPathogenicityColor('Likely Pathogenic') // Returns: 'orange-lighten-3'
 * getPathogenicityColor('VUS') // Returns: 'yellow-darken-1'
 * getPathogenicityColor(null) // Returns: 'grey-lighten-2'
 */
export function getPathogenicityColor(pathogenicity) {
  if (!pathogenicity) return 'grey-lighten-2';

  // Normalize: uppercase and replace spaces with underscores
  const normalized = pathogenicity.toUpperCase().replace(/\s+/g, '_');

  return PATHOGENICITY_COLORS[normalized] ?? 'grey-lighten-2';
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
