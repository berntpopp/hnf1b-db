/**
 * Application Configuration
 *
 * Centralized configuration for frontend application settings.
 * All hard-coded values should be defined here for easy maintenance.
 */

/**
 * API Configuration
 */
export const API_CONFIG = {
  /**
   * Maximum number of variants to fetch for priority sorting and visualizations.
   *
   * ⚠️ IMPORTANT LIMITATION:
   * This hard limit assumes the database will not exceed this number of variants.
   * If the database grows beyond this limit, the following features will break:
   *
   * - Priority sorting in Variants table (only first N variants will be sorted)
   * - Gene visualizations on Home page (variants beyond limit won't display)
   * - CNV visualizations (large deletions beyond limit won't be shown)
   *
   * SOLUTION PATHS:
   * 1. Short-term: Monitor variant count and increase this limit
   * 2. Medium-term: Implement server-side priority sorting
   * 3. Long-term: Implement proper pagination with total count tracking
   *
   * Current database size: ~864 variants (as of 2025-11-06)
   * Safety margin: 1000 provides 15% headroom
   *
   * TODO: Add backend endpoint that returns total variant count for monitoring
   * TODO: Add warning in UI when approaching this limit
   *
   * @see https://github.com/berntpopp/hnf1b-db/issues/XX (create issue to track)
   */
  MAX_VARIANTS_FOR_PRIORITY_SORT: import.meta.env.VITE_MAX_VARIANTS || 1000,

  /**
   * Default page size for paginated requests.
   */
  DEFAULT_PAGE_SIZE: 100,

  /**
   * Maximum page size allowed by backend API.
   */
  MAX_PAGE_SIZE: 1000,
};

/**
 * Feature Flags
 */
export const FEATURES = {
  /**
   * Enable console logging for debugging.
   * @see Issue #54 for comprehensive logging refactor plan
   */
  DEBUG_LOGGING: import.meta.env.DEV || false,
};

/**
 * Visualization Configuration
 */
export const VIZ_CONFIG = {
  /**
   * Default SVG width for gene/protein visualizations.
   */
  DEFAULT_SVG_WIDTH: 1000,

  /**
   * Gene coordinate range for HNF1B (GRCh38/hg38).
   */
  HNF1B_GENE: {
    chromosome: '17',
    start: 37680000,
    end: 37750000,
    strand: '-',
  },
};

export default {
  API_CONFIG,
  FEATURES,
  VIZ_CONFIG,
};
