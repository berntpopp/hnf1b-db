/**
 * Composable for semantic zoom/pan functionality in visualizations.
 *
 * Provides reactive zoom state and methods for zooming/panning across
 * a coordinate range (genomic positions, amino acid positions, etc.).
 * Used by gene and protein visualization components.
 *
 * @param {Object} options - Configuration options
 * @param {number} options.minPosition - Minimum position in the range (default: 1)
 * @param {number} options.maxPosition - Maximum position in the range
 * @param {number} options.minVisibleRange - Minimum visible range when zoomed in (default: 50)
 * @param {number} options.zoomFactor - Factor for zoom in/out (default: 1.5)
 * @param {number} options.panFactor - Factor for pan left/right as fraction of visible range (default: 0.2)
 * @returns {{
 *   visibleStart: Ref<number>,
 *   visibleEnd: Ref<number>,
 *   zoomLevel: Ref<number>,
 *   zoomIn: Function,
 *   zoomOut: Function,
 *   resetZoom: Function,
 *   panLeft: Function,
 *   panRight: Function,
 *   canPanLeft: ComputedRef<boolean>,
 *   canPanRight: ComputedRef<boolean>,
 *   setVisibleRange: Function
 * }}
 *
 * @example
 * // For protein visualization (1-557 aa):
 * const zoom = useSemanticZoom({ minPosition: 1, maxPosition: 557 })
 *
 * // For gene visualization:
 * const zoom = useSemanticZoom({ minPosition: 37680000, maxPosition: 37750000 })
 *
 * // In template:
 * // <button @click="zoom.zoomIn" :disabled="zoom.zoomLevel.value >= 10">+</button>
 * // <button @click="zoom.panLeft" :disabled="!zoom.canPanLeft.value">←</button>
 */

import { ref, computed } from 'vue';

export function useSemanticZoom(options = {}) {
  const {
    minPosition = 1,
    maxPosition,
    minVisibleRange = 50,
    zoomFactor = 1.5,
    panFactor = 0.2,
  } = options;

  if (!maxPosition) {
    throw new Error('useSemanticZoom requires maxPosition option');
  }

  const totalRange = maxPosition - minPosition;
  const visibleStart = ref(minPosition);
  const visibleEnd = ref(maxPosition);
  const zoomLevel = ref(1);

  const canPanLeft = computed(() => visibleStart.value > minPosition);
  const canPanRight = computed(() => visibleEnd.value < maxPosition);

  const zoomIn = () => {
    const currentRange = visibleEnd.value - visibleStart.value;
    const center = (visibleStart.value + visibleEnd.value) / 2;
    const newRange = Math.max(currentRange / zoomFactor, minVisibleRange);

    visibleStart.value = Math.max(minPosition, Math.round(center - newRange / 2));
    visibleEnd.value = Math.min(maxPosition, Math.round(center + newRange / 2));
    zoomLevel.value = totalRange / (visibleEnd.value - visibleStart.value);
  };

  const zoomOut = () => {
    const currentRange = visibleEnd.value - visibleStart.value;
    const center = (visibleStart.value + visibleEnd.value) / 2;
    const newRange = Math.min(currentRange * zoomFactor, totalRange);

    visibleStart.value = Math.max(minPosition, Math.round(center - newRange / 2));
    visibleEnd.value = Math.min(maxPosition, Math.round(center + newRange / 2));
    zoomLevel.value = totalRange / (visibleEnd.value - visibleStart.value);

    // Snap to full range if close
    if (visibleEnd.value - visibleStart.value > totalRange * 0.9) {
      resetZoom();
    }
  };

  const resetZoom = () => {
    visibleStart.value = minPosition;
    visibleEnd.value = maxPosition;
    zoomLevel.value = 1;
  };

  const panLeft = () => {
    const range = visibleEnd.value - visibleStart.value;
    const panAmount = Math.round(range * panFactor);

    if (visibleStart.value > minPosition) {
      visibleStart.value = Math.max(minPosition, visibleStart.value - panAmount);
      visibleEnd.value = visibleStart.value + range;
    }
  };

  const panRight = () => {
    const range = visibleEnd.value - visibleStart.value;
    const panAmount = Math.round(range * panFactor);

    if (visibleEnd.value < maxPosition) {
      visibleEnd.value = Math.min(maxPosition, visibleEnd.value + panAmount);
      visibleStart.value = visibleEnd.value - range;
    }
  };

  const setVisibleRange = (start, end) => {
    visibleStart.value = Math.max(minPosition, start);
    visibleEnd.value = Math.min(maxPosition, end);
    zoomLevel.value = totalRange / (visibleEnd.value - visibleStart.value);
  };

  return {
    visibleStart,
    visibleEnd,
    zoomLevel,
    zoomIn,
    zoomOut,
    resetZoom,
    panLeft,
    panRight,
    canPanLeft,
    canPanRight,
    setVisibleRange,
  };
}
