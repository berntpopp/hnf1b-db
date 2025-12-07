/**
 * Centralized UI configuration for phenopacket card components.
 *
 * Provides consistent styling tokens based on COLOR_STYLE_GUIDE.md
 * to ensure visual consistency across all phenopacket-related components.
 *
 * @module utils/cardStyles
 */

/**
 * Card header configurations for phenopacket data sections.
 * Each card type has a consistent color scheme and icon.
 */
export const CARD_HEADERS = {
  subject: {
    icon: 'mdi-account',
    iconColor: 'primary',
    bgColor: 'bg-blue-lighten-5',
    title: 'Subject Information',
  },
  phenotypicFeatures: {
    icon: 'mdi-medical-bag',
    iconColor: 'success',
    bgColor: 'bg-green-lighten-5',
    title: 'Phenotypic Features',
  },
  interpretations: {
    icon: 'mdi-dna',
    iconColor: 'deep-purple',
    bgColor: 'bg-purple-lighten-5',
    title: 'Genomic Interpretations',
  },
  measurements: {
    icon: 'mdi-chart-line',
    iconColor: 'orange',
    bgColor: 'bg-orange-lighten-5',
    title: 'Measurements',
  },
  metadata: {
    icon: 'mdi-information',
    iconColor: 'grey',
    bgColor: 'bg-grey-lighten-4',
    title: 'Metadata',
  },
};

/**
 * Interpretation status colors matching ACMG classification.
 * Used for classification badges and chips.
 */
export const INTERPRETATION_STATUS_COLORS = {
  CAUSATIVE: 'red',
  CONTRIBUTORY: 'orange',
  CANDIDATE: 'blue',
  PATHOGENIC: 'red',
  LIKELY_PATHOGENIC: 'orange',
  UNCERTAIN_SIGNIFICANCE: 'grey',
  LIKELY_BENIGN: 'green-lighten-1',
  BENIGN: 'green',
  NO_KNOWN_DISEASE_RELATIONSHIP: 'grey',
};

/**
 * Interpretation status display labels.
 * Provides human-readable abbreviated labels.
 */
export const INTERPRETATION_STATUS_LABELS = {
  PATHOGENIC: 'Pathogenic',
  LIKELY_PATHOGENIC: 'Likely Path.',
  UNCERTAIN_SIGNIFICANCE: 'VUS',
  LIKELY_BENIGN: 'Likely Benign',
  BENIGN: 'Benign',
  CAUSATIVE: 'Causative',
  CONTRIBUTORY: 'Contributory',
  CANDIDATE: 'Candidate',
};

/**
 * Subject field colors for consistent styling.
 */
export const SUBJECT_FIELD_COLORS = {
  subjectId: 'teal-lighten-4',
  alternateId: 'blue-lighten-4',
  reportId: 'grey-lighten-2',
  age: 'amber-lighten-4',
  karyotype: 'purple-lighten-4',
};

/**
 * Sex-specific colors (imported from sex.js for reference).
 * Use getSexChipColor from sex.js for consistency.
 */
export const SEX_COLORS = {
  MALE: 'blue-lighten-4',
  FEMALE: 'pink-lighten-4',
  OTHER_SEX: 'purple-lighten-4',
  UNKNOWN_SEX: 'grey-lighten-2',
};

/**
 * Phenotypic feature colors and styling.
 */
export const PHENOTYPE_STYLES = {
  presentFeature: {
    color: 'green',
    variant: 'tonal',
  },
  excludedFeature: {
    color: 'grey',
    variant: 'outlined',
  },
  severityColors: {
    severe: 'error',
    moderate: 'warning',
    mild: 'success',
    unknown: 'grey',
  },
};

/**
 * Onset category icons.
 */
export const ONSET_ICONS = {
  prenatal: 'mdi-baby-carriage',
  congenital: 'mdi-baby',
  postnatal: 'mdi-calendar',
};

/**
 * Shared spacing tokens for card layouts.
 */
export const CARD_SPACING = {
  cardPadding: 'pa-3',
  titlePadding: 'py-2',
  chipGap: '6px',
  gridGap: '12px 16px',
};

/**
 * Grid layout configurations for card content.
 */
export const GRID_LAYOUTS = {
  subjectGrid: {
    templateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
    gap: '12px 16px',
  },
  detailGrid: {
    templateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
    gap: '12px 16px',
  },
};

/**
 * Unified typography system for phenopacket cards.
 * Ensures consistent font sizes, weights, and line heights across all components.
 *
 * Design Principles:
 * - Base scale: 11px (labels), 12px (body), 13px (emphasis)
 * - Monospace for code/IDs: 11px
 * - Consistent line heights for readability
 */
export const TYPOGRAPHY = {
  // Font sizes (in pixels, applied via CSS)
  sizes: {
    xs: '10px', // Small code snippets, badges
    sm: '11px', // Labels, secondary text, monospace
    base: '12px', // Body text, chip labels
    md: '13px', // Emphasized text, primary values
    lg: '14px', // Card subtitles (use Vuetify text-subtitle-2)
  },
  // Font weights
  weights: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
  // Line heights
  lineHeights: {
    tight: 1.2,
    normal: 1.4,
    relaxed: 1.6,
  },
  // Monospace font stack
  fontFamilyMono: "'Roboto Mono', 'Consolas', 'Monaco', monospace",
};

/**
 * Unified color tokens using Vuetify color system.
 * Replaces all hardcoded hex colors for consistency.
 */
export const COLORS = {
  // Text colors (use with text-{color} classes or CSS vars)
  text: {
    primary: 'rgba(0, 0, 0, 0.87)', // High emphasis
    secondary: 'rgba(0, 0, 0, 0.6)', // Medium emphasis
    disabled: 'rgba(0, 0, 0, 0.38)', // Disabled/hint
  },
  // Semantic colors for variants/interpretations
  variant: {
    gene: 'deep-purple', // Gene symbols
    cNotation: 'blue-darken-2', // c. notation (transcript)
    pNotation: 'green-darken-2', // p. notation (protein)
    coordinates: 'grey-darken-1', // Genomic coordinates
  },
  // Code background colors
  codeBg: {
    default: 'rgba(0, 0, 0, 0.06)',
    cNotation: 'rgba(33, 150, 243, 0.1)', // Blue tint
    pNotation: 'rgba(76, 175, 80, 0.1)', // Green tint
  },
};

/**
 * Unified chip configuration for consistent sizing.
 * Standard: 'small' for inline chips, 'x-small' for dense displays.
 */
export const CHIP_SIZES = {
  standard: 'small', // Default chip size for most uses
  dense: 'x-small', // For dense/compact displays
  inline: 'small', // For inline with text
};

/**
 * CSS class generators for consistent typography styling.
 * Use these to generate inline styles or CSS classes.
 */
export const getTypographyStyles = {
  /**
   * Label styling (uppercase, small, muted)
   */
  label: () => ({
    fontSize: TYPOGRAPHY.sizes.sm,
    fontWeight: TYPOGRAPHY.weights.medium,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    color: COLORS.text.secondary,
  }),
  /**
   * Value styling (primary emphasis)
   */
  value: () => ({
    fontSize: TYPOGRAPHY.sizes.md,
    fontWeight: TYPOGRAPHY.weights.medium,
    color: COLORS.text.primary,
  }),
  /**
   * Monospace code styling
   */
  code: (variant = 'default') => ({
    fontFamily: TYPOGRAPHY.fontFamilyMono,
    fontSize: TYPOGRAPHY.sizes.sm,
    padding: '2px 6px',
    borderRadius: '4px',
    backgroundColor: COLORS.codeBg[variant] || COLORS.codeBg.default,
  }),
  /**
   * Gene symbol styling
   */
  geneSymbol: () => ({
    fontSize: TYPOGRAPHY.sizes.md,
    fontWeight: TYPOGRAPHY.weights.semibold,
    color: 'var(--v-theme-deep-purple)',
  }),
  /**
   * Secondary/detail text
   */
  secondary: () => ({
    fontSize: TYPOGRAPHY.sizes.sm,
    color: COLORS.text.secondary,
  }),
};

/**
 * Get color for interpretation status.
 *
 * @param {string} status - Interpretation status key
 * @returns {string} Vuetify color string
 */
export function getInterpretationStatusColor(status) {
  return INTERPRETATION_STATUS_COLORS[status] || 'grey';
}

/**
 * Get display label for interpretation status.
 *
 * @param {string} status - Interpretation status key
 * @returns {string} Human-readable label
 */
export function getInterpretationStatusLabel(status) {
  return INTERPRETATION_STATUS_LABELS[status] || status;
}

/**
 * Get severity color based on severity label.
 *
 * @param {object} severity - Severity object with label/id
 * @returns {string} Vuetify color string
 */
export function getSeverityColor(severity) {
  if (!severity) return PHENOTYPE_STYLES.severityColors.unknown;

  const label = (severity.label || severity.id || '').toLowerCase();
  if (label.includes('severe')) return PHENOTYPE_STYLES.severityColors.severe;
  if (label.includes('moderate')) return PHENOTYPE_STYLES.severityColors.moderate;
  if (label.includes('mild')) return PHENOTYPE_STYLES.severityColors.mild;
  return PHENOTYPE_STYLES.severityColors.unknown;
}

/**
 * Get severity icon based on severity label.
 *
 * @param {object} severity - Severity object with label/id
 * @returns {string} MDI icon name
 */
export function getSeverityIcon(severity) {
  if (!severity) return 'mdi-circle-small';

  const label = (severity.label || severity.id || '').toLowerCase();
  if (label.includes('severe')) return 'mdi-alert-circle';
  if (label.includes('moderate')) return 'mdi-alert';
  if (label.includes('mild')) return 'mdi-information';
  return 'mdi-circle-small';
}
