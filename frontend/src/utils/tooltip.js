/**
 * Tooltip Positioning Utilities
 *
 * Provides consistent tooltip positioning logic across visualization components.
 * Handles viewport edge detection to prevent tooltip overflow.
 *
 * @module utils/tooltip
 */

/**
 * Default tooltip dimensions for overflow calculations.
 */
const DEFAULT_TOOLTIP_WIDTH = 300;
const DEFAULT_TOOLTIP_HEIGHT = 200;
const DEFAULT_OFFSET = 15;
const MIN_EDGE_PADDING = 10;

/**
 * Calculate optimal tooltip position that avoids viewport edges.
 *
 * @param {MouseEvent} event - Mouse event with clientX and clientY
 * @param {Object} options - Optional configuration
 * @param {number} options.tooltipWidth - Approximate tooltip width (default: 300)
 * @param {number} options.tooltipHeight - Approximate tooltip height (default: 200)
 * @param {number} options.offset - Distance from cursor (default: 15)
 * @returns {Object} Position object with x and y coordinates
 *
 * @example
 * const pos = calculateTooltipPosition(event);
 * // Returns: { x: 150, y: 200 }
 *
 * const pos = calculateTooltipPosition(event, { tooltipWidth: 400 });
 * // Returns position accounting for 400px wide tooltip
 */
export function calculateTooltipPosition(event, options = {}) {
  const {
    tooltipWidth = DEFAULT_TOOLTIP_WIDTH,
    tooltipHeight = DEFAULT_TOOLTIP_HEIGHT,
    offset = DEFAULT_OFFSET,
  } = options;

  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;

  // Default: position to the right and below cursor
  let x = event.clientX + offset;
  let y = event.clientY + offset;

  // If tooltip would overflow right edge, position to the left of cursor
  if (x + tooltipWidth > viewportWidth) {
    x = event.clientX - tooltipWidth - offset;
  }

  // If tooltip would overflow bottom edge, position above cursor
  if (y + tooltipHeight > viewportHeight) {
    y = event.clientY - tooltipHeight - offset;
  }

  // Ensure minimum padding from edges
  x = Math.max(MIN_EDGE_PADDING, x);
  y = Math.max(MIN_EDGE_PADDING, y);

  return { x, y };
}

/**
 * Create a tooltip state manager for Vue components.
 *
 * @returns {Object} Tooltip state and methods
 *
 * @example
 * // In Vue component setup:
 * const tooltip = createTooltipState();
 *
 * // In template:
 * // :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
 * // v-if="tooltip.visible"
 *
 * // In methods:
 * // @mouseenter="tooltip.show($event, { type: 'variant', data: variant })"
 * // @mousemove="tooltip.updatePosition($event)"
 * // @mouseleave="tooltip.hide()"
 */
export function createTooltipState() {
  return {
    visible: false,
    x: 0,
    y: 0,
    content: null,

    /**
     * Show tooltip with content at mouse position.
     * @param {MouseEvent} event - Mouse event
     * @param {Object} content - Tooltip content object
     * @param {Object} options - Optional positioning options
     */
    show(event, content, options = {}) {
      const pos = calculateTooltipPosition(event, options);
      this.x = pos.x;
      this.y = pos.y;
      this.content = content;
      this.visible = true;
    },

    /**
     * Update tooltip position on mouse move.
     * @param {MouseEvent} event - Mouse event
     * @param {Object} options - Optional positioning options
     */
    updatePosition(event, options = {}) {
      const pos = calculateTooltipPosition(event, options);
      this.x = pos.x;
      this.y = pos.y;
    },

    /**
     * Hide tooltip and clear content.
     */
    hide() {
      this.visible = false;
      this.content = null;
    },
  };
}
