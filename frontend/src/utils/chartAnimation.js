/**
 * Chart Animation Utilities
 *
 * Provides animation timing helpers with prefers-reduced-motion support.
 * All animation functions return 0 when reduced motion is preferred,
 * ensuring instant rendering for accessibility.
 *
 * @module utils/chartAnimation
 */

/**
 * Check if user prefers reduced motion.
 *
 * Uses CSS media query to detect user's system preference.
 * Returns true if the user has enabled "reduce motion" accessibility setting.
 *
 * @returns {boolean} True if reduced motion is preferred
 *
 * @example
 * if (prefersReducedMotion()) {
 *   // Skip animations, render instantly
 * }
 */
export function prefersReducedMotion() {
  // Guard for environments without window.matchMedia (e.g., SSR or tests)
  if (typeof window === 'undefined' || !window.matchMedia) {
    return false;
  }

  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Get animation duration based on user preference.
 *
 * Returns 0 if user prefers reduced motion, otherwise returns the default duration.
 * Use this to make D3 transitions respect accessibility preferences.
 *
 * @param {number} [defaultDuration=400] - Duration in ms when motion is allowed
 * @returns {number} 0 if reduced motion, otherwise defaultDuration
 *
 * @example
 * // D3 transition with accessibility support
 * svg.selectAll('rect')
 *   .transition()
 *   .duration(getAnimationDuration(300))
 *   .attr('height', d => y(d.value));
 */
export function getAnimationDuration(defaultDuration = 400) {
  return prefersReducedMotion() ? 0 : defaultDuration;
}

/**
 * Get stagger delay for sequential animations.
 *
 * Returns 0 if user prefers reduced motion, otherwise returns calculated delay.
 * Use this to create staggered entry animations (elements appear one after another).
 *
 * @param {number} index - Element index in the sequence
 * @param {number} [delayPerItem=50] - Delay between items in ms
 * @returns {number} Calculated delay or 0 if reduced motion
 *
 * @example
 * // Staggered bar chart animation
 * svg.selectAll('rect')
 *   .data(data)
 *   .enter()
 *   .append('rect')
 *   .attr('height', 0)
 *   .transition()
 *   .duration(getAnimationDuration(400))
 *   .delay((d, i) => getStaggerDelay(i, 30))
 *   .attr('height', d => y(d.value));
 */
export function getStaggerDelay(index, delayPerItem = 50) {
  return prefersReducedMotion() ? 0 : index * delayPerItem;
}

/**
 * Get easing function name for D3 transitions.
 *
 * Returns a snappy easing function name for D3.
 * When reduced motion is preferred, returns null (D3 will use linear).
 *
 * @returns {string|null} D3 easing function name or null
 *
 * @example
 * import * as d3 from 'd3';
 *
 * const easing = getEasingFunction();
 * const transition = svg.transition()
 *   .duration(getAnimationDuration(400));
 *
 * if (easing) {
 *   transition.ease(d3[easing]);
 * }
 */
export function getEasingFunction() {
  return prefersReducedMotion() ? null : 'easeCubicOut';
}

/**
 * Create a motion-aware animation configuration object.
 *
 * Returns a configuration object with duration, delay function, and easing
 * that respects user's reduced motion preference.
 *
 * @param {Object} [options] - Animation options
 * @param {number} [options.duration=400] - Base duration in ms
 * @param {number} [options.staggerDelay=50] - Delay per item in ms
 * @returns {{duration: number, delay: Function, easing: string|null}} Animation config
 *
 * @example
 * const config = getAnimationConfig({ duration: 300, staggerDelay: 30 });
 *
 * svg.selectAll('path')
 *   .transition()
 *   .duration(config.duration)
 *   .delay((d, i) => config.delay(i))
 *   .ease(config.easing ? d3[config.easing] : d3.easeLinear)
 *   .attrTween('d', arcTween);
 */
export function getAnimationConfig(options = {}) {
  const { duration = 400, staggerDelay = 50 } = options;

  return {
    duration: getAnimationDuration(duration),
    delay: (index) => getStaggerDelay(index, staggerDelay),
    easing: getEasingFunction(),
  };
}
