/**
 * Composable for D3-Vue integration with drag and wheel zoom support.
 *
 * Provides D3 drag and wheel zoom behaviors that integrate with Vue's
 * reactivity system. Handles the complex interaction between D3's
 * imperative DOM manipulation and Vue's reactive state.
 *
 * @param {Object} options - Configuration options
 * @param {Ref<HTMLElement>} options.elementRef - Vue ref to the SVG element
 * @param {Object} options.zoom - Semantic zoom composable from useSemanticZoom
 * @param {Function} options.getSvgDimensions - Function returning { width, marginLeft, marginRight }
 * @returns {{
 *   initializeDragPan: Function,
 *   initializeWheelZoom: Function,
 *   cleanup: Function
 * }}
 *
 * @example
 * const svgRef = ref(null)
 * const zoom = useSemanticZoom({ maxPosition: 557 })
 * const d3bindings = useD3Bindable({
 *   elementRef: svgRef,
 *   zoom,
 *   getSvgDimensions: () => ({ width: 1000, marginLeft: 50, marginRight: 50 })
 * })
 *
 * onMounted(() => {
 *   d3bindings.initializeDragPan()
 *   d3bindings.initializeWheelZoom()
 * })
 *
 * onUnmounted(() => d3bindings.cleanup())
 */

import * as d3 from 'd3';

export function useD3Bindable(options = {}) {
  const { elementRef, zoom, getSvgDimensions } = options;

  let dragBehavior = null;

  const initializeDragPan = () => {
    if (!elementRef?.value) return;

    const svg = d3.select(elementRef.value);
    let dragStartX = null;
    let dragStartVisibleStart = null;
    let dragStartVisibleEnd = null;

    dragBehavior = d3
      .drag()
      .on('start', (event) => {
        dragStartX = event.x;
        dragStartVisibleStart = zoom.visibleStart.value;
        dragStartVisibleEnd = zoom.visibleEnd.value;
        svg.style('cursor', 'grabbing');
      })
      .on('drag', (event) => {
        if (dragStartX === null) return;

        const { width, marginLeft, marginRight } = getSvgDimensions();
        const svgLength = width - marginLeft - marginRight;
        const visibleRange = dragStartVisibleEnd - dragStartVisibleStart;
        const pixelsPerUnit = svgLength / visibleRange;
        const dragDelta = dragStartX - event.x;
        const unitDelta = Math.round(dragDelta / pixelsPerUnit);

        let newStart = dragStartVisibleStart + unitDelta;
        let newEnd = dragStartVisibleEnd + unitDelta;

        // Bounds will be enforced by setVisibleRange
        zoom.setVisibleRange(newStart, newEnd);
      })
      .on('end', () => {
        dragStartX = null;
        dragStartVisibleStart = null;
        dragStartVisibleEnd = null;
        svg.style('cursor', 'grab');
      });

    svg.call(dragBehavior);
    svg.style('cursor', 'grab');
  };

  const initializeWheelZoom = () => {
    if (!elementRef?.value) return;

    const svg = d3.select(elementRef.value);

    svg.on('wheel.zoom', (event) => {
      event.preventDefault();
      if (event.deltaY < 0) {
        zoom.zoomIn();
      } else {
        zoom.zoomOut();
      }
    });
  };

  const cleanup = () => {
    if (elementRef?.value) {
      const svg = d3.select(elementRef.value);
      svg.on('.drag', null);
      svg.on('wheel.zoom', null);
    }
  };

  return {
    initializeDragPan,
    initializeWheelZoom,
    cleanup,
  };
}
