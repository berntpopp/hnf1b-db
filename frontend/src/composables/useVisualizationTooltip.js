/**
 * Composable for managing visualization tooltips with reactive state.
 *
 * Provides reactive tooltip state and positioning logic that prevents
 * viewport overflow. Used across gene, protein, and analysis visualizations.
 *
 * @param {Object} options - Configuration options
 * @param {number} options.tooltipWidth - Approximate tooltip width (default: 300)
 * @param {number} options.tooltipHeight - Approximate tooltip height (default: 200)
 * @param {number} options.offset - Distance from cursor (default: 15)
 * @returns {{
 *   visible: Ref<boolean>,
 *   x: Ref<number>,
 *   y: Ref<number>,
 *   content: Ref<Object|null>,
 *   show: Function,
 *   hide: Function,
 *   updatePosition: Function
 * }}
 *
 * @example
 * // In component setup or script setup:
 * const tooltip = useVisualizationTooltip()
 *
 * // In template:
 * // :style="{ left: tooltip.x.value + 'px', top: tooltip.y.value + 'px' }"
 * // v-if="tooltip.visible.value"
 *
 * // In event handlers:
 * // @mouseenter="tooltip.show($event, { type: 'variant', data: variant })"
 * // @mousemove="tooltip.updatePosition($event)"
 * // @mouseleave="tooltip.hide()"
 */

import { ref } from 'vue';
import { calculateTooltipPosition } from '@/utils/tooltip';

export function useVisualizationTooltip(options = {}) {
  const { tooltipWidth = 300, tooltipHeight = 200, offset = 15 } = options;

  const visible = ref(false);
  const x = ref(0);
  const y = ref(0);
  const content = ref(null);

  const show = (event, tooltipContent) => {
    const pos = calculateTooltipPosition(event, { tooltipWidth, tooltipHeight, offset });
    x.value = pos.x;
    y.value = pos.y;
    content.value = tooltipContent;
    visible.value = true;
  };

  const updatePosition = (event) => {
    const pos = calculateTooltipPosition(event, { tooltipWidth, tooltipHeight, offset });
    x.value = pos.x;
    y.value = pos.y;
  };

  const hide = () => {
    visible.value = false;
    content.value = null;
  };

  return {
    visible,
    x,
    y,
    content,
    show,
    hide,
    updatePosition,
  };
}
