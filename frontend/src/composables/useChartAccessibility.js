/**
 * Per-chart accessibility helpers: generates stable unique IDs for ARIA
 * title/description, returns a prop bundle the chart spreads onto its
 * wrapper, and exposes the summary ref for binding into a visually-hidden
 * description element.
 *
 * @param {{ chartName: string, summary: import('vue').Ref<string> }} options
 * @returns {{
 *   titleId: string,
 *   descId: string,
 *   description: import('vue').Ref<string>,
 *   ariaProps: { role: string, 'aria-labelledby': string, 'aria-describedby': string },
 * }}
 */
let counter = 0;

export function useChartAccessibility({ chartName: _chartName, summary }) {
  counter += 1;
  const titleId = `chart-title-${counter}`;
  const descId = `chart-desc-${counter}`;
  return {
    titleId,
    descId,
    description: summary,
    ariaProps: {
      role: 'img',
      'aria-labelledby': titleId,
      'aria-describedby': descId,
    },
  };
}
