/**
 * Aggregation Dashboard Configuration
 *
 * Centralized configuration for the AggregationsDashboard component.
 * Extracted to reduce component size and improve maintainability.
 *
 * @module utils/aggregationConfig
 */

/**
 * Semantic color maps for specific aggregations.
 * Maps data labels to consistent colors across the application.
 */
export const AGGREGATION_COLOR_MAPS = {
  // Pathogenicity: red=pathogenic, orange=LP, yellow=VUS, green=benign
  getVariantPathogenicity: {
    Pathogenic: '#D32F2F', // Red
    'Likely Pathogenic': '#FF9800', // Orange
    'Uncertain Significance': '#FDD835', // Bright yellow for VUS
    'Likely Benign': '#81C784', // Light green
    Benign: '#388E3C', // Dark green
  },
  // Variant types
  getVariantTypes: {
    'Copy Number Loss': '#D32F2F', // Red
    'Copy Number Gain': '#1976D2', // Blue
    SNV: '#388E3C', // Green
    Deletion: '#FF9800', // Orange
    Duplication: '#9C27B0', // Purple
    Insertion: '#00BCD4', // Cyan
    Indel: '#E91E63', // Pink
    NA: '#9E9E9E', // Grey
  },
  // Sex distribution
  getSexDistribution: {
    MALE: '#1976D2', // Blue
    FEMALE: '#E91E63', // Pink
    OTHER_SEX: '#9C27B0', // Purple
    UNKNOWN_SEX: '#9E9E9E', // Grey
  },
  // Publication types
  getPublicationTypes: {
    'Case Series': '#1976D2', // Blue
    Research: '#4CAF50', // Green
    'Case Report': '#FF9800', // Orange
    'Review And Cases': '#9C27B0', // Purple
    'Screening Multiple': '#00BCD4', // Cyan
    Review: '#F44336', // Red
  },
};

/**
 * Donut chart category configurations.
 * Defines available aggregations for each data category.
 */
export const DONUT_CATEGORIES = [
  {
    label: 'Phenopackets',
    aggregations: [
      { label: 'Sex Distribution', value: 'getSexDistribution' },
      { label: 'Age of Onset', value: 'getAgeOfOnsetAggregation' },
      { label: 'Kidney Disease Stages', value: 'getKidneyStages' },
    ],
  },
  {
    label: 'Variants',
    aggregations: [
      {
        label: 'Pathogenicity Classification',
        value: 'getVariantPathogenicity',
        supportsCountMode: true,
      },
      {
        label: 'Variant Types (SNV/Indel/CNV)',
        value: 'getVariantTypes',
        supportsCountMode: true,
      },
    ],
  },
  {
    label: 'Publications',
    aggregations: [{ label: 'Publication Types', value: 'getPublicationTypes' }],
  },
];

/**
 * Count mode options for variant aggregations.
 */
export const COUNT_MODE_OPTIONS = [
  { label: 'All Variant Instances', value: 'all' },
  { label: 'Unique Variants', value: 'unique' },
];

/**
 * Display limit options for stacked bar charts.
 */
export const DISPLAY_LIMIT_OPTIONS = [
  { label: 'Top 10', value: 10, threshold: 10 },
  { label: 'Top 20', value: 20, threshold: 20 },
  { label: 'Top 30', value: 30, threshold: 30 },
  { label: 'Top 50', value: 50, threshold: 50 },
  { label: 'All Features', value: 9999, threshold: 0 },
];

/**
 * Variant comparison type options.
 */
export const COMPARISON_TYPES = [
  { label: 'Truncating vs Non-truncating', value: 'truncating_vs_non_truncating' },
  {
    label: 'Truncating vs Non-truncating (excl. CNVs)',
    value: 'truncating_vs_non_truncating_excl_cnv',
  },
  { label: 'CNVs vs Non-CNV variants', value: 'cnv_vs_point_mutation' },
];

/**
 * Sort options for variant comparison.
 */
export const SORT_BY_OPTIONS = [
  { label: 'P-value (most significant first)', value: 'p_value' },
  { label: 'Effect size (largest first)', value: 'effect_size' },
  { label: 'Prevalence difference', value: 'prevalence_diff' },
];

/**
 * Organ system filter options.
 */
export const ORGAN_SYSTEM_OPTIONS = [
  { label: 'All Systems', value: 'all' },
  { label: 'Renal', value: 'renal' },
  { label: 'Metabolic', value: 'metabolic' },
  { label: 'Neurological', value: 'neurological' },
  { label: 'Pancreatic/Endocrine', value: 'pancreatic' },
  { label: 'Other', value: 'other' },
];

/**
 * Survival analysis comparison type options.
 */
export const SURVIVAL_COMPARISON_TYPES = [
  {
    label: 'Variant Type',
    value: 'variant_type',
    description: 'Compare CNV vs Truncating vs Non-truncating variants',
  },
  {
    label: 'Pathogenicity',
    value: 'pathogenicity',
    description: 'Compare Pathogenic/Likely Pathogenic vs VUS',
  },
  {
    label: 'Disease Subtype',
    value: 'disease_subtype',
    description: 'Compare CAKUT vs CAKUT+MODY vs MODY vs Other phenotypes',
  },
];

/**
 * Survival endpoint options.
 */
export const SURVIVAL_ENDPOINT_OPTIONS = [
  {
    label: 'CKD Stage 3+ (GFR <60)',
    value: 'ckd_stage_3_plus',
    description: 'Time to CKD Stage 3 or higher (composite endpoint)',
  },
  {
    label: 'Stage 5 CKD (ESRD)',
    value: 'stage_5_ckd',
    description: 'Time to End-Stage Renal Disease (historical endpoint)',
  },
  {
    label: 'Any CKD',
    value: 'any_ckd',
    description: 'Time to any chronic kidney disease diagnosis',
  },
  {
    label: 'Age at Last Follow-up',
    value: 'current_age',
    description: 'Current/reported age (universal endpoint)',
  },
];

/**
 * Format API labels to human-readable display labels.
 * Converts UPPER_SNAKE_CASE to Title Case.
 *
 * @param {string} label - Raw label string
 * @returns {string} Formatted label
 *
 * @example
 * formatLabel('LIKELY_PATHOGENIC') // Returns: 'Likely Pathogenic'
 * formatLabel('UNKNOWN_SEX') // Returns: 'Unknown Sex'
 */
export function formatLabel(label) {
  if (!label) return 'Unknown';
  return label
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Calculate stacked bar statistics from chart data.
 *
 * @param {Array} data - Stacked bar chart data array
 * @returns {Object|null} Statistics object or null if no data
 */
export function calculateStackedBarStats(data) {
  if (!data || data.length === 0) {
    return null;
  }

  // Calculate total features
  const totalFeatures = data.length;

  // Calculate most common feature
  const mostCommon = data.reduce((max, feature) => {
    const present = feature.details?.present_count || 0;
    const maxPresent = max.details?.present_count || 0;
    return present > maxPresent ? feature : max;
  }, data[0]);

  const mostCommonPresent = mostCommon.details?.present_count || 0;
  const mostCommonAbsent = mostCommon.details?.absent_count || 0;
  const mostCommonReported = mostCommonPresent + mostCommonAbsent;
  const mostCommonPenetrance =
    mostCommonReported > 0 ? ((mostCommonPresent / mostCommonReported) * 100).toFixed(1) : '0.0';

  // Calculate average penetrance
  let totalPenetrance = 0;
  let featuresWithReports = 0;

  data.forEach((feature) => {
    const present = feature.details?.present_count || 0;
    const absent = feature.details?.absent_count || 0;
    const reported = present + absent;

    if (reported > 0) {
      totalPenetrance += (present / reported) * 100;
      featuresWithReports++;
    }
  });

  const avgPenetrance =
    featuresWithReports > 0 ? (totalPenetrance / featuresWithReports).toFixed(1) : '0.0';

  // Calculate data completeness
  let totalPresent = 0;
  let totalAbsent = 0;
  let totalNotReported = 0;

  data.forEach((feature) => {
    totalPresent += feature.details?.present_count || 0;
    totalAbsent += feature.details?.absent_count || 0;
    totalNotReported += feature.details?.not_reported_count || 0;
  });

  const totalDataPoints = totalPresent + totalAbsent + totalNotReported;
  const reportingRate =
    totalDataPoints > 0
      ? (((totalPresent + totalAbsent) / totalDataPoints) * 100).toFixed(1)
      : '0.0';

  return {
    totalFeatures,
    mostCommon: {
      label: mostCommon.label || 'N/A',
      penetrance: mostCommonPenetrance,
    },
    avgPenetrance,
    reportingRate,
  };
}
