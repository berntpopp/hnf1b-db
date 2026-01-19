/**
 * UI Constants
 *
 * User interface configuration values for consistent behavior
 * across the application.
 */

/** Maximum recent searches to store in history */
export const MAX_RECENT_SEARCHES = 5;

/** Cache TTL in milliseconds (5 minutes) */
export const CACHE_TTL_MS = 5 * 60 * 1000;

/** Default debounce delay (ms) for search inputs */
export const DEBOUNCE_DELAY_MS = 300;

/**
 * Tooltip dimensions and positioning
 */
export const TOOLTIP = {
  /** Maximum tooltip width in pixels */
  MAX_WIDTH: 300,
  /** Maximum tooltip height in pixels */
  MAX_HEIGHT: 200,
  /** Horizontal offset from cursor in pixels */
  OFFSET_X: 15,
  /** Vertical offset from cursor in pixels */
  OFFSET_Y: 10,
};
