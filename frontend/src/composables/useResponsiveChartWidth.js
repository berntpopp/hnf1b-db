/**
 * Track a container element's content width and derive a responsive chart size.
 *
 * D3 charts in this app take fixed `width`/`height` props. On mobile that forces
 * a chart far wider than its card, clipping it. This composable observes the
 * container with a ResizeObserver and returns a reactive `width` clamped to the
 * container (capped at `maxWidth`) plus a derived `height`, so the chart fills
 * the available width on phones and stays bounded on desktop.
 *
 * Mirrors the ResizeObserver approach already proven in PhenotypeHeatmap.vue.
 *
 * @param {import('vue').Ref<HTMLElement|null>} containerRef - ref to the measured container
 * @param {Object} [options]
 * @param {number} [options.maxWidth=900]  - upper bound for the chart width (desktop cap)
 * @param {number} [options.minWidth=0]    - lower bound for the chart COORDINATE width.
 *   Charts with large fixed inner margins (e.g. a horizontal stacked bar with a
 *   300px left label gutter) produce negative bar widths if the coordinate width
 *   drops below the sum of their margins. Floor the coordinate width here; the
 *   SVG still scales DOWN to its container via `width:100%` + `viewBox`, so the
 *   chart stays proportional and never renders negative dimensions on mobile.
 * @param {number} [options.aspect=0.75]   - height / width ratio used to derive height
 * @param {number} [options.maxHeight=500] - upper bound for the derived height
 * @param {number} [options.minHeight=240] - lower bound for the derived height
 * @returns {{ width: import('vue').Ref<number>, height: import('vue').ComputedRef<number>, measure: () => void }}
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';

export function useResponsiveChartWidth(containerRef, options = {}) {
  const { maxWidth = 900, minWidth = 0, aspect = 0.75, maxHeight = 500, minHeight = 240 } = options;

  // Start at maxWidth so SSR / tests (no real layout) default to the desktop
  // size; the ResizeObserver corrects this to the real container width on mount.
  const width = ref(Math.max(maxWidth, minWidth));

  const height = computed(() =>
    Math.round(Math.max(minHeight, Math.min(maxHeight, width.value * aspect)))
  );

  let observer = null;
  let rafId = null;

  function applyWidth() {
    const el = containerRef.value;
    if (!el) return;
    const available = el.clientWidth;
    // Ignore 0 (display:none / inactive v-window-item / pre-layout / happy-dom)
    // so an inactive tab or test env keeps the last good / default width.
    if (!available) return;
    // Clamp to [minWidth, maxWidth]. minWidth keeps the coordinate system large
    // enough for the chart's inner margins; the SVG scales down to the container.
    const next = Math.max(minWidth, Math.min(maxWidth, available));
    if (Math.abs(next - width.value) > 1) {
      width.value = next;
    }
  }

  // Debounce measurements through requestAnimationFrame to avoid layout thrash
  // when the ResizeObserver fires repeatedly during a resize.
  function measure() {
    if (typeof requestAnimationFrame === 'undefined') {
      applyWidth();
      return;
    }
    if (rafId !== null) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(() => {
      rafId = null;
      applyWidth();
    });
  }

  onMounted(() => {
    measure();
    if (typeof ResizeObserver !== 'undefined' && containerRef.value) {
      observer = new ResizeObserver(() => measure());
      observer.observe(containerRef.value);
    }
  });

  onBeforeUnmount(() => {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
    if (rafId !== null && typeof cancelAnimationFrame !== 'undefined') {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  });

  return { width, height, measure };
}
