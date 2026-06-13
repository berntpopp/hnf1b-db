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
 * Molecular-consequence (variant-effect) taxonomy.
 *
 * Normalizes the curated `molecular_consequence` field (e.g. "Missense",
 * "Copy Number Loss", "Splice Donor") into a small set of stable, colorable
 * buckets used by the variant visualizations' "colour by type" mode and by the
 * effect-type filter chips. The bucket keys, ordering, labels and colours are
 * the single source of truth shared across the protein and gene plots.
 *
 * The palette is colourblind-aware and aligned with the SysNDD effect palette
 * where the categories overlap (missense/frameshift/stop_gained/splice/etc.),
 * extended with HNF1B-specific copy-number categories (loss/gain) and intronic.
 */
export const CONSEQUENCE_ORDER = [
  'missense',
  'nonsense',
  'frameshift',
  'splice',
  'inframe_indel',
  'synonymous',
  'intronic',
  'cnv_loss',
  'cnv_gain',
  'other',
];

const CONSEQUENCE_LABELS = {
  missense: 'Missense',
  nonsense: 'Nonsense',
  frameshift: 'Frameshift',
  splice: 'Splice',
  inframe_indel: 'In-frame indel',
  synonymous: 'Synonymous',
  intronic: 'Intronic',
  cnv_loss: 'CN Loss',
  cnv_gain: 'CN Gain',
  other: 'Other',
};

const CONSEQUENCE_HEX_COLORS = {
  missense: '#1F77B4', // blue
  nonsense: '#9467BD', // purple (stop-gained)
  frameshift: '#D62728', // red
  splice: '#FF7F0E', // orange
  inframe_indel: '#2CA02C', // green
  synonymous: '#7F7F7F', // gray
  intronic: '#17BECF', // cyan
  cnv_loss: '#B2182B', // dark red
  cnv_gain: '#2166AC', // dark blue
  other: '#BCBD22', // olive
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
 * Normalize a pathogenicity/classification string to its canonical key.
 * Exposes the internal normalizer for filter logic that needs to bucket a
 * verdict into one of PATHOGENIC | LIKELY_PATHOGENIC | VUS | LIKELY_BENIGN |
 * BENIGN.
 *
 * @param {string|null|undefined} pathogenicity - Classification string
 * @returns {string|null} Canonical key, or null if unrecognized
 */
export function normalizePathogenicity(pathogenicity) {
  return normalizeClassification(pathogenicity);
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

/**
 * Normalize a raw molecular-consequence string into a stable taxonomy key.
 *
 * Accepts both the curated display values ("Missense", "Copy Number Loss",
 * "Splice Donor", "In-frame Deletion", ...) and VEP-style tokens
 * ("missense_variant", "stop_gained", "frameshift_variant",
 * "splice_donor_variant", ...) so the same logic works regardless of source.
 *
 * @param {string|null|undefined} consequence - Raw molecular_consequence value
 * @returns {string} One of {@link CONSEQUENCE_ORDER} (defaults to 'other')
 */
export function normalizeConsequence(consequence) {
  if (!consequence) return 'other';

  const n = String(consequence).toLowerCase();

  // Copy-number first — "copy number loss/gain" must not fall through to other.
  if (n.includes('copy number loss') || n.includes('copy_number_loss') || n.includes('cn loss')) {
    return 'cnv_loss';
  }
  if (n.includes('copy number gain') || n.includes('copy_number_gain') || n.includes('cn gain')) {
    return 'cnv_gain';
  }
  if (n.includes('missense')) return 'missense';
  if (n.includes('frameshift') || n.includes('frame shift') || n.includes('frame_shift')) {
    return 'frameshift';
  }
  if (n.includes('nonsense') || n.includes('stop_gained') || n.includes('stop gained')) {
    return 'nonsense';
  }
  if (n.includes('splice')) return 'splice';
  if (n.includes('inframe') || n.includes('in-frame') || n.includes('in frame')) {
    return 'inframe_indel';
  }
  if (n.includes('synonymous')) return 'synonymous';
  if (n.includes('intron')) return 'intronic';

  return 'other';
}

/**
 * Get the human-readable label for a molecular consequence.
 *
 * @param {string|null|undefined} consequence - Raw molecular_consequence value
 * @returns {string} Display label (e.g. 'Missense', 'CN Loss')
 */
export function getConsequenceLabel(consequence) {
  return CONSEQUENCE_LABELS[normalizeConsequence(consequence)];
}

/**
 * Get the hex colour for a molecular consequence (for D3/SVG rendering).
 *
 * @param {string|null|undefined} consequence - Raw molecular_consequence value
 * @returns {string} Hex colour code (defaults to grey for unknown input)
 *
 * @example
 * getConsequenceHexColor('Missense')         // '#1F77B4'
 * getConsequenceHexColor('Copy Number Loss') // '#B2182B'
 * getConsequenceHexColor(null)               // '#BDBDBD'
 */
export function getConsequenceHexColor(consequence) {
  if (!consequence) return '#BDBDBD';
  return CONSEQUENCE_HEX_COLORS[normalizeConsequence(consequence)] ?? '#BDBDBD';
}

/**
 * Ordered consequence taxonomy entries ({ key, label, color }), useful for
 * building legends without re-deriving the order/label/colour mappings.
 *
 * @returns {Array<{key: string, label: string, color: string}>}
 */
export function getConsequenceTaxonomy() {
  return CONSEQUENCE_ORDER.map((key) => ({
    key,
    label: CONSEQUENCE_LABELS[key],
    color: CONSEQUENCE_HEX_COLORS[key],
  }));
}
