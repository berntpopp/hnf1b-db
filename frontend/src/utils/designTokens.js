/**
 * Design Tokens - Single source of truth for all visual design values.
 *
 * Three-tier architecture:
 * 1. GLOBAL TOKENS - Brand colors (COLORS)
 * 2. SEMANTIC TOKENS - Domain-specific colors with dual format (SEX_COLORS, PATHOGENICITY_COLORS, DATA_COLORS)
 * 3. SPACING TOKENS - Vuetify-aligned spacing system (SPACING)
 *
 * Each semantic token provides both:
 * - `vuetify`: Vuetify color class (e.g., 'blue-lighten-3')
 * - `hex`: Hex color code (e.g., '#64B5F6')
 *
 * This enables consistent colors between Vuetify chips and D3 charts.
 *
 * @module utils/designTokens
 */

// =============================================================================
// GLOBAL TOKENS - Brand colors
// =============================================================================

/**
 * Global brand colors for the HNF1B Database theme.
 * Used by Vuetify theme configuration.
 *
 * @constant
 */
export const COLORS = {
  // Primary brand color - Teal
  PRIMARY: '#009688',
  PRIMARY_DARKEN_1: '#00796B',
  PRIMARY_LIGHTEN_3: '#4DB6AC',
  PRIMARY_LIGHTEN_4: '#80CBC4',

  // Secondary color - Slate
  SECONDARY: '#37474F',
  SECONDARY_DARKEN_1: '#263238',

  // Accent color - Gold/Amber (changed from coral per CONTEXT.md)
  ACCENT: '#FFB300',
  ACCENT_LIGHTEN_3: '#FFE082',

  // Background colors
  BACKGROUND: '#F5F7FA',
  SURFACE: '#FFFFFF',

  // Status colors
  ERROR: '#B00020',
  SUCCESS: '#4CAF50',
  WARNING: '#FB8C00',
  INFO: '#2196F3',
};

// =============================================================================
// SEMANTIC TOKENS - Domain-specific colors with dual format
// =============================================================================

/**
 * Sex/gender colors for chips and charts.
 * Maps GA4GH Phenopackets v2 sex values to consistent colors.
 *
 * @constant
 */
export const SEX_COLORS = {
  MALE: {
    vuetify: 'blue-lighten-3',
    hex: '#64B5F6',
  },
  FEMALE: {
    vuetify: 'pink-lighten-3',
    hex: '#F48FB1',
  },
  OTHER_SEX: {
    vuetify: 'purple-lighten-3',
    hex: '#BA68C8',
  },
  UNKNOWN_SEX: {
    vuetify: 'grey-lighten-2',
    hex: '#EEEEEE',
  },
};

/**
 * Pathogenicity classification colors (ACMG guidelines).
 * Used for variant chips and pathogenicity charts.
 *
 * @constant
 */
export const PATHOGENICITY_COLORS = {
  PATHOGENIC: {
    vuetify: 'red-lighten-1',
    hex: '#EF5350',
  },
  LIKELY_PATHOGENIC: {
    vuetify: 'orange-lighten-1',
    hex: '#FF9800',
  },
  VUS: {
    vuetify: 'yellow-darken-1',
    hex: '#FBC02D',
  },
  UNCERTAIN_SIGNIFICANCE: {
    vuetify: 'yellow-darken-1',
    hex: '#FBC02D',
  },
  LIKELY_BENIGN: {
    vuetify: 'light-green-lighten-1',
    hex: '#9CCC65',
  },
  BENIGN: {
    vuetify: 'green-lighten-1',
    hex: '#66BB6A',
  },
};

/**
 * Data category colors for visual identification.
 * Used for phenopacket, variant, publication, and phenotype chips/charts.
 *
 * @constant
 */
export const DATA_COLORS = {
  PHENOPACKET: {
    vuetify: 'teal-lighten-3',
    hex: '#4DB6AC',
  },
  VARIANT: {
    vuetify: 'pink-lighten-3',
    hex: '#F48FB1',
  },
  PUBLICATION: {
    vuetify: 'orange-lighten-3',
    hex: '#FFB74D',
  },
  PHENOTYPE: {
    vuetify: 'green-lighten-3',
    hex: '#81C784',
  },
};

// =============================================================================
// SPACING TOKENS - Vuetify-aligned spacing system
// =============================================================================

/**
 * Spacing tokens documenting Vuetify's 4px base system.
 * Use Vuetify classes (ma-1, pa-2, etc.) - these values are for reference.
 *
 * @constant
 */
export const SPACING = {
  /** 4px - ma-1, pa-1 */
  XS: 4,
  /** 8px - ma-2, pa-2 */
  SM: 8,
  /** 16px - ma-4, pa-4 */
  MD: 16,
  /** 24px - ma-6, pa-6 */
  LG: 24,
  /** 32px - ma-8, pa-8 */
  XL: 32,
};

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Get hex color for D3 charts.
 *
 * @param {string} category - Token category ('sex', 'pathogenicity', 'data')
 * @param {string} value - Value within category (e.g., 'MALE', 'PATHOGENIC')
 * @returns {string} Hex color code, or grey fallback
 *
 * @example
 * getChartColor('sex', 'MALE') // Returns: '#64B5F6'
 * getChartColor('pathogenicity', 'PATHOGENIC') // Returns: '#EF5350'
 */
export function getChartColor(category, value) {
  const categoryMap = {
    sex: SEX_COLORS,
    pathogenicity: PATHOGENICITY_COLORS,
    data: DATA_COLORS,
  };

  const tokens = categoryMap[category];
  if (!tokens) {
    return '#BDBDBD'; // grey fallback
  }

  const token = tokens[value];
  return token?.hex ?? '#BDBDBD';
}

/**
 * Get Vuetify color class for chips.
 *
 * @param {string} category - Token category ('sex', 'pathogenicity', 'data')
 * @param {string} value - Value within category (e.g., 'MALE', 'PATHOGENIC')
 * @returns {string} Vuetify color class, or grey fallback
 *
 * @example
 * getVuetifyColor('sex', 'FEMALE') // Returns: 'pink-lighten-3'
 * getVuetifyColor('data', 'PUBLICATION') // Returns: 'orange-lighten-3'
 */
export function getVuetifyColor(category, value) {
  const categoryMap = {
    sex: SEX_COLORS,
    pathogenicity: PATHOGENICITY_COLORS,
    data: DATA_COLORS,
  };

  const tokens = categoryMap[category];
  if (!tokens) {
    return 'grey-lighten-2';
  }

  const token = tokens[value];
  return token?.vuetify ?? 'grey-lighten-2';
}

/**
 * Build a complete color map for D3 charts.
 * Returns an object mapping all values in a category to their hex colors.
 *
 * @param {string} category - Token category ('sex', 'pathogenicity', 'data')
 * @returns {Object} Map of value -> hex color
 *
 * @example
 * buildChartColorMap('sex')
 * // Returns: { MALE: '#64B5F6', FEMALE: '#F48FB1', ... }
 */
export function buildChartColorMap(category) {
  const categoryMap = {
    sex: SEX_COLORS,
    pathogenicity: PATHOGENICITY_COLORS,
    data: DATA_COLORS,
  };

  const tokens = categoryMap[category];
  if (!tokens) {
    return {};
  }

  const colorMap = {};
  for (const [key, value] of Object.entries(tokens)) {
    colorMap[key] = value.hex;
  }
  return colorMap;
}
