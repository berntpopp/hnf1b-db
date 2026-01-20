/**
 * Chart Accessibility Utilities
 *
 * Provides ARIA attributes and screen reader text generation for D3.js charts.
 * Implements WCAG 2.1 Level A compliance for SVG visualizations.
 *
 * Pattern: Add role="img" with aria-labelledby pointing to title and desc elements.
 * Screen readers read the title first (short), then description (full data).
 *
 * @module utils/chartAccessibility
 */

/**
 * Add accessibility attributes to SVG element.
 *
 * Sets role="img" and aria-labelledby on the SVG, then inserts
 * title and desc elements for screen reader announcement.
 *
 * @param {D3Selection|SVGElement} svg - D3 selection of SVG element or raw SVG element
 * @param {string} titleId - Unique ID for title element
 * @param {string} descId - Unique ID for description element
 * @param {string} title - Short title for the chart
 * @param {string} description - Full data description for screen readers
 * @returns {void}
 *
 * @example
 * // With D3 selection
 * const svg = d3.select('#chart').append('svg');
 * addChartAccessibility(svg, 'chart-title', 'chart-desc', 'Sex Distribution', 'Pie chart showing...');
 *
 * @example
 * // With raw SVG element
 * const svgElement = document.querySelector('svg');
 * addChartAccessibility(svgElement, 'chart-title', 'chart-desc', 'Sex Distribution', 'Pie chart showing...');
 */
export function addChartAccessibility(svg, titleId, descId, title, description) {
  if (!svg) {
    window.logService?.warn('addChartAccessibility called with null SVG');
    return;
  }

  // Handle both D3 selection and raw SVG element
  const isD3Selection = typeof svg.attr === 'function';

  if (isD3Selection) {
    // D3 selection - use D3 methods
    svg.attr('role', 'img').attr('aria-labelledby', `${titleId} ${descId}`);

    // Insert title element as first child
    svg.insert('title', ':first-child').attr('id', titleId).text(title);

    // Insert desc element after title
    svg.insert('desc', 'title + *').attr('id', descId).text(description);
  } else {
    // Raw SVG element - use DOM methods
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-labelledby', `${titleId} ${descId}`);

    // Create and insert title element
    const titleElement = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    titleElement.setAttribute('id', titleId);
    titleElement.textContent = title;

    // Create desc element
    const descElement = document.createElementNS('http://www.w3.org/2000/svg', 'desc');
    descElement.setAttribute('id', descId);
    descElement.textContent = description;

    // Insert title as first child
    if (svg.firstChild) {
      svg.insertBefore(titleElement, svg.firstChild);
      svg.insertBefore(descElement, svg.children[1] || null);
    } else {
      svg.appendChild(titleElement);
      svg.appendChild(descElement);
    }
  }
}

/**
 * Generate screen reader description for donut/pie chart data.
 *
 * Creates a human-readable summary including total count and
 * breakdown by category with percentages.
 *
 * @param {Array<{label: string, count: number}>} data - Chart data
 * @param {number} total - Total count
 * @returns {string} Human-readable description
 *
 * @example
 * const data = [
 *   { label: 'Male', count: 432 },
 *   { label: 'Female', count: 389 }
 * ];
 * generateDonutDescription(data, 821);
 * // Returns: "Chart showing 821 total items. Male: 432 (52.6%). Female: 389 (47.4%)."
 */
export function generateDonutDescription(data, total) {
  if (!data || data.length === 0) {
    return 'Chart with no data.';
  }

  if (total === 0) {
    return 'Chart showing 0 total items.';
  }

  const items = data.map((d) => {
    const pct = ((d.count / total) * 100).toFixed(1);
    return `${d.label}: ${d.count} (${pct}%)`;
  });

  return `Chart showing ${total} total items. ${items.join('. ')}.`;
}

/**
 * Generate screen reader description for bar chart data.
 *
 * Creates a human-readable summary of the top 10 features
 * with penetrance percentages (present vs total).
 *
 * @param {Array<{label: string, present: number, absent: number}>} data - Chart data
 * @returns {string} Human-readable description
 *
 * @example
 * const data = [
 *   { label: 'Kidney abnormality', present: 450, absent: 200 },
 *   { label: 'Diabetes', present: 300, absent: 350 }
 * ];
 * generateBarChartDescription(data);
 * // Returns: "Bar chart showing 2 features. Top features: Kidney abnormality: 69% present (450 of 650). Diabetes: 46% present (300 of 650)."
 */
export function generateBarChartDescription(data) {
  if (!data || data.length === 0) {
    return 'Bar chart with no data.';
  }

  const items = data.slice(0, 10).map((d) => {
    const total = d.present + d.absent;
    const pct = total > 0 ? ((d.present / total) * 100).toFixed(0) : 0;
    return `${d.label}: ${pct}% present (${d.present} of ${total})`;
  });

  const more = data.length > 10 ? ` and ${data.length - 10} more features` : '';

  return `Bar chart showing ${data.length} features. Top features: ${items.join('. ')}${more}.`;
}

/**
 * Generate screen reader description for Kaplan-Meier survival chart.
 *
 * Creates a human-readable summary of survival curves including
 * group names, sample sizes, and event counts.
 *
 * @param {Array<{name: string, n: number, events: number}>} groups - Survival curve groups
 * @returns {string} Human-readable description
 *
 * @example
 * const groups = [
 *   { name: 'With HNF1B variant', n: 150, events: 45 },
 *   { name: 'Control group', n: 200, events: 30 }
 * ];
 * generateLineChartDescription(groups);
 * // Returns: "Survival chart showing 2 groups. With HNF1B variant: 150 subjects, 45 events. Control group: 200 subjects, 30 events."
 */
export function generateLineChartDescription(groups) {
  if (!groups || groups.length === 0) {
    return 'Survival chart with no data.';
  }

  const items = groups.map((g) => {
    return `${g.name}: ${g.n} subjects, ${g.events} events`;
  });

  return `Survival chart showing ${groups.length} groups. ${items.join('. ')}.`;
}
