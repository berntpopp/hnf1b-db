# Phase 5: Chart Polish - Research

**Researched:** 2026-01-20
**Domain:** D3.js chart animations, SVG accessibility, export utilities
**Confidence:** HIGH

## Summary

This phase enhances five existing D3.js chart components (DonutChart, StackedBarChart, KaplanMeierChart, VariantComparisonChart, and DNADistanceAnalysis/BoxPlotChart) with accessibility features, entry animations, and export functionality.

The current chart components follow a consistent pattern:
- Vue Options API with D3.js integration
- Direct DOM manipulation via D3 selections
- Manual tooltip handling per component
- Some charts already have SVG export (KaplanMeierChart, VariantComparisonChart, BoxPlotChart)
- No accessibility features (no ARIA, no screen reader text)
- No animations beyond hover effects

**Primary recommendation:** Create shared utilities for export (`utils/export.js`) and accessibility (`utils/chartAccessibility.js`), then apply consistently across all chart components. Use D3's transition system with `prefers-reduced-motion` detection for animations.

## Standard Stack

The project already has all required dependencies in place.

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| d3 | ^7.9.0 | Chart rendering and animations | Industry standard for data visualization |
| file-saver | ^2.0.5 | File download utility | Already installed, handles blob downloads |
| chart.js | ^4.5.1 | PublicationsTimelineChart (Canvas-based) | Already used for line charts |

### Supporting (No New Dependencies Needed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Native Canvas API | Built-in | PNG export via toDataURL | For 2x resolution PNG export |
| Native Blob API | Built-in | File creation | For CSV text export |
| matchMedia | Built-in | Reduced motion detection | For accessibility preferences |

### Why No New Dependencies
The project already has `file-saver` for download handling. PNG export uses native Canvas + XMLSerializer (already demonstrated in existing SVG export code). CSV export is simple string manipulation. No additional libraries needed.

## Architecture Patterns

### Recommended Utility Structure
```
frontend/src/utils/
├── export.js              # NEW: PNG/CSV export utilities
├── chartAccessibility.js  # NEW: ARIA helpers, screen reader text
├── chartAnimation.js      # NEW: Animation helpers with reduced-motion
├── designTokens.js        # EXISTING: Colors for tooltips
├── tooltip.js             # EXISTING: Tooltip positioning
└── ...
```

### Pattern 1: Shared Export Utility
**What:** Centralized export functions for PNG and CSV
**When to use:** All chart components that need export functionality
**Example:**
```javascript
// Source: Derived from existing SVG export patterns in KaplanMeierChart.vue
// frontend/src/utils/export.js

import { saveAs } from 'file-saver';

/**
 * Export SVG element to PNG at specified resolution scale
 * @param {SVGElement} svgElement - The SVG to export
 * @param {string} filename - Base filename (without extension)
 * @param {number} scale - Resolution multiplier (default: 2 for 2x)
 */
export function exportToPNG(svgElement, filename, scale = 2) {
  const svgData = new XMLSerializer().serializeToString(svgElement);
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  const img = new Image();

  // Set canvas dimensions at higher resolution
  const svgWidth = svgElement.width.baseVal.value || svgElement.clientWidth;
  const svgHeight = svgElement.height.baseVal.value || svgElement.clientHeight;
  canvas.width = svgWidth * scale;
  canvas.height = svgHeight * scale;

  // White background
  ctx.fillStyle = 'white';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.scale(scale, scale);

  img.onload = () => {
    ctx.drawImage(img, 0, 0);
    canvas.toBlob((blob) => {
      saveAs(blob, `${filename}.png`);
    }, 'image/png');
  };

  img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));
}

/**
 * Export data array to CSV with snake_case headers
 * @param {Array<Object>} data - Array of data objects
 * @param {Array<string>} headers - Column headers (snake_case)
 * @param {string} filename - Filename (without extension)
 */
export function exportToCSV(data, headers, filename) {
  const headerRow = headers.join(',');
  const rows = data.map(item =>
    headers.map(h => {
      const val = item[h];
      // Escape quotes and wrap in quotes if contains comma
      if (typeof val === 'string' && (val.includes(',') || val.includes('"'))) {
        return `"${val.replace(/"/g, '""')}"`;
      }
      return val ?? '';
    }).join(',')
  );

  const csv = [headerRow, ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  saveAs(blob, `${filename}.csv`);
}

/**
 * Generate timestamp for filenames
 * @returns {string} ISO date string (YYYY-MM-DD)
 */
export function getTimestamp() {
  return new Date().toISOString().slice(0, 10);
}
```

### Pattern 2: Screen Reader Accessibility
**What:** ARIA attributes and screen reader text for charts
**When to use:** All chart components for WCAG 2.1 Level A compliance
**Example:**
```javascript
// Source: Based on https://www.smashingmagazine.com/2021/05/accessible-svg-patterns-comparison/
// frontend/src/utils/chartAccessibility.js

/**
 * Add accessibility attributes to SVG element
 * @param {D3Selection} svg - D3 selection of SVG element
 * @param {string} titleId - Unique ID for title element
 * @param {string} descId - Unique ID for description element
 * @param {string} title - Short title for the chart
 * @param {string} description - Full data description for screen readers
 */
export function addChartAccessibility(svg, titleId, descId, title, description) {
  // Add role="img" for screen reader recognition
  svg.attr('role', 'img')
     .attr('aria-labelledby', `${titleId} ${descId}`);

  // Add title element (short label)
  svg.insert('title', ':first-child')
     .attr('id', titleId)
     .text(title);

  // Add desc element (full data for screen readers)
  svg.insert('desc', 'title + *')
     .attr('id', descId)
     .text(description);
}

/**
 * Generate screen reader description for donut/pie chart data
 * @param {Array<{label: string, count: number}>} data - Chart data
 * @param {number} total - Total count
 * @returns {string} Human-readable description
 */
export function generateDonutDescription(data, total) {
  const items = data.map(d => {
    const pct = ((d.count / total) * 100).toFixed(1);
    return `${d.label}: ${d.count} (${pct}%)`;
  });
  return `Chart showing ${total} total items. ${items.join('. ')}.`;
}

/**
 * Generate screen reader description for bar chart data
 * @param {Array<{label: string, present: number, absent: number}>} data
 * @returns {string} Human-readable description
 */
export function generateBarChartDescription(data) {
  const items = data.slice(0, 10).map(d => {
    const total = d.present + d.absent;
    const pct = total > 0 ? ((d.present / total) * 100).toFixed(0) : 0;
    return `${d.label}: ${pct}% present (${d.present} of ${total})`;
  });
  const more = data.length > 10 ? ` and ${data.length - 10} more features` : '';
  return `Bar chart showing ${data.length} features. Top features: ${items.join('. ')}${more}.`;
}
```

### Pattern 3: Animation with Reduced Motion Support
**What:** Entry animations that respect user preferences
**When to use:** All animated chart elements
**Example:**
```javascript
// Source: Based on https://web.dev/articles/prefers-reduced-motion
// frontend/src/utils/chartAnimation.js

/**
 * Check if user prefers reduced motion
 * @returns {boolean} True if reduced motion is preferred
 */
export function prefersReducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Get animation duration based on user preference
 * @param {number} defaultDuration - Duration in ms when motion is allowed
 * @returns {number} 0 if reduced motion, otherwise default
 */
export function getAnimationDuration(defaultDuration = 400) {
  return prefersReducedMotion() ? 0 : defaultDuration;
}

/**
 * Get stagger delay for sequential animations
 * @param {number} index - Element index
 * @param {number} delayPerItem - Delay between items in ms
 * @returns {number} Calculated delay or 0 if reduced motion
 */
export function getStaggerDelay(index, delayPerItem = 50) {
  return prefersReducedMotion() ? 0 : index * delayPerItem;
}
```

### Pattern 4: Arc Tween Animation for Donut Charts
**What:** Smooth arc entrance animation using D3's attrTween
**When to use:** DonutChart component
**Example:**
```javascript
// Source: https://jonsadka.com/blog/how-to-create-adaptive-pie-charts-with-transitions-in-d3/
// Arc tween for smooth donut chart animations

function arcTween(arc) {
  return function(d) {
    // Store current angles in _current
    const interpolate = d3.interpolate(this._current || { startAngle: 0, endAngle: 0 }, d);
    this._current = interpolate(1);
    return function(t) {
      return arc(interpolate(t));
    };
  };
}

// Usage in renderChart:
const duration = getAnimationDuration(400);
const stagger = prefersReducedMotion() ? 0 : 50;

svg.selectAll('path.slice')
  .data(dataReady)
  .enter()
  .append('path')
  .attr('class', 'slice')
  .attr('fill', d => color(d.data[0]))
  .each(function(d) { this._current = { startAngle: 0, endAngle: 0 }; })
  .transition()
  .duration(duration)
  .delay((d, i) => getStaggerDelay(i, stagger))
  .attrTween('d', arcTween(arc));
```

### Pattern 5: Bar Chart Height Animation
**What:** Bars grow from baseline with staggered timing
**When to use:** StackedBarChart component
**Example:**
```javascript
// Source: https://d3-graph-gallery.com/graph/barplot_animation_start.html
// Staggered bar height animation

const duration = getAnimationDuration(400);
const stagger = prefersReducedMotion() ? 0 : 30;

svg.selectAll('rect')
  .data(data)
  .enter()
  .append('rect')
  .attr('x', d => x(d[0]))
  .attr('y', svgHeight)  // Start at baseline
  .attr('width', d => x(d[1]) - x(d[0]))
  .attr('height', 0)     // Start with zero height
  .attr('fill', d => color(d.key))
  .transition()
  .duration(duration)
  .delay((d, i) => getStaggerDelay(i, stagger))
  .attr('y', d => y(d.data.group))
  .attr('height', y.bandwidth());
```

### Pattern 6: Line Path Drawing Animation
**What:** Lines draw progressively using stroke-dasharray
**When to use:** KaplanMeierChart survival curves
**Example:**
```javascript
// Source: https://medium.com/@louisemoxy/create-a-d3-line-chart-animation-336f1cb7dd61
// Path drawing animation using dasharray/dashoffset

const duration = getAnimationDuration(2000);

const path = svg.append('path')
  .datum(data)
  .attr('fill', 'none')
  .attr('stroke', color)
  .attr('stroke-width', 2)
  .attr('d', line);

if (!prefersReducedMotion()) {
  const totalLength = path.node().getTotalLength();

  path
    .attr('stroke-dasharray', `${totalLength} ${totalLength}`)
    .attr('stroke-dashoffset', totalLength)
    .transition()
    .duration(duration)
    .ease(d3.easeLinear)
    .attr('stroke-dashoffset', 0);
}
```

### ChartExportMenu Component Pattern
**What:** Reusable dropdown menu for chart export options
**When to use:** All chart components with export functionality
**Example:**
```vue
<!-- frontend/src/components/common/ChartExportMenu.vue -->
<template>
  <v-menu>
    <template #activator="{ props }">
      <v-btn
        v-bind="props"
        variant="outlined"
        size="small"
        color="primary"
      >
        <v-icon start>mdi-download</v-icon>
        Export
      </v-btn>
    </template>
    <v-list>
      <v-list-item @click="$emit('export-png')">
        <v-list-item-title>
          <v-icon start size="small">mdi-image</v-icon>
          Download PNG
        </v-list-item-title>
      </v-list-item>
      <v-list-item v-if="showCsv" @click="$emit('export-csv')">
        <v-list-item-title>
          <v-icon start size="small">mdi-file-delimited</v-icon>
          Download CSV
        </v-list-item-title>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script>
export default {
  name: 'ChartExportMenu',
  props: {
    showCsv: {
      type: Boolean,
      default: true
    }
  },
  emits: ['export-png', 'export-csv']
};
</script>
```

### Anti-Patterns to Avoid
- **Direct DOM queries in export:** Use refs, not `document.querySelector` for SVG elements
- **Inline tooltip styles:** Use existing `tooltip.js` utility for positioning
- **Hardcoded colors:** Import from `designTokens.js` for consistency
- **Skipping reduced-motion check:** Always check `prefersReducedMotion()` before animating
- **Animation on data updates:** Only animate on initial load; use smooth transitions for updates

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File downloads | Manual anchor click | `file-saver` library | Already installed, handles edge cases |
| SVG serialization | String manipulation | `XMLSerializer` | Native API, handles encoding correctly |
| Motion preference | Polling or checking once | `matchMedia` with listener | Reacts to preference changes |
| CSV escaping | Simple string replace | Proper quoting logic | Commas, quotes, newlines need handling |
| Unique IDs for ARIA | Random strings | Component-scoped IDs | Predictable, testable, no collisions |

**Key insight:** The project already has file-saver installed and working export code in three components. Extract and generalize rather than rewriting.

## Common Pitfalls

### Pitfall 1: Canvas Tainting with External Resources
**What goes wrong:** PNG export fails silently or throws security error
**Why it happens:** SVG references external fonts or images not loaded via same origin
**How to avoid:** Inline all styles before serialization; use embedded fonts only
**Warning signs:** Export works in dev but fails in production

### Pitfall 2: Animation Blocking Data Updates
**What goes wrong:** Chart freezes or shows stale data during animation
**Why it happens:** Transition prevents immediate DOM updates
**How to avoid:** Cancel in-progress transitions before re-rendering; use `.interrupt()` in D3
**Warning signs:** Rapid data changes cause visual glitches

### Pitfall 3: Screen Reader Reads Every SVG Element
**What goes wrong:** Screen reader announces hundreds of path elements
**Why it happens:** Missing `aria-hidden` on decorative elements
**How to avoid:** Add `aria-hidden="true"` to all non-semantic SVG elements (paths, rects)
**Warning signs:** VoiceOver/NVDA takes forever to read chart

### Pitfall 4: ARIA Description Too Long
**What goes wrong:** Screen reader reads 500+ words for a chart
**Why it happens:** Including all data points in description
**How to avoid:** Summarize (top 5-10 items, totals, percentages); link to data table for full details
**Warning signs:** Description exceeds 2-3 sentences

### Pitfall 5: Reduced Motion Not Detected on First Render
**What goes wrong:** Initial animation plays despite user preference
**Why it happens:** `matchMedia` check happens after animation started
**How to avoid:** Check `prefersReducedMotion()` synchronously before any transition
**Warning signs:** Animation plays once then stops on re-renders

### Pitfall 6: Pattern Fills Not Working in PNG Export
**What goes wrong:** Patterns appear solid in exported PNG
**Why it happens:** Pattern definitions not included in serialized SVG
**How to avoid:** Define patterns inline within the SVG, not in external CSS
**Warning signs:** SVG export works, PNG export loses patterns

## Code Examples

### Existing SVG Export Pattern (from KaplanMeierChart.vue)
```javascript
// Source: /frontend/src/components/analyses/KaplanMeierChart.vue lines 51-96
exportSVG() {
  const svgElement = this.$refs.chart.querySelector('svg');
  if (!svgElement) return;

  const clonedSvg = svgElement.cloneNode(true);
  clonedSvg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  clonedSvg.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');

  // Add white background
  const background = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  background.setAttribute('width', '100%');
  background.setAttribute('height', '100%');
  background.setAttribute('fill', 'white');
  clonedSvg.insertBefore(background, clonedSvg.firstChild);

  const serializer = new XMLSerializer();
  let svgString = serializer.serializeToString(clonedSvg);
  svgString = '<?xml version="1.0" encoding="UTF-8"?>\n' + svgString;

  const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);

  const timestamp = new Date().toISOString().slice(0, 10);
  const filename = `chart-${timestamp}.svg`;

  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
```

### Tooltip Styling Using Design Tokens
```javascript
// Source: /frontend/src/utils/designTokens.js
// Use these colors for tooltip consistency

import { COLORS } from '@/utils/designTokens';

// In D3 tooltip creation:
const tooltip = d3.select(this.$refs.chart)
  .append('div')
  .attr('class', 'chart-tooltip')
  .style('background-color', COLORS.SURFACE)  // #FFFFFF
  .style('border', `1px solid ${COLORS.SECONDARY}`)  // #37474F
  .style('border-radius', '4px')
  .style('padding', '8px')
  .style('box-shadow', '0 2px 8px rgba(0,0,0,0.15)');
```

### SVG Accessibility Pattern
```html
<!-- Source: https://www.tpgi.com/using-aria-enhance-svg-accessibility/ -->
<svg role="img" aria-labelledby="donut-title donut-desc">
  <title id="donut-title">Sex Distribution Chart</title>
  <desc id="donut-desc">
    Donut chart showing 864 total subjects.
    Male: 432 (50.0%). Female: 389 (45.0%). Unknown: 43 (5.0%).
  </desc>
  <!-- Chart content with aria-hidden="true" on decorative paths -->
  <g aria-hidden="true">
    <path class="slice" ... />
  </g>
</svg>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `aria-describedby` for charts | `aria-labelledby` with title+desc | 2021 | Better screen reader support |
| Manual file download with anchor | `file-saver` library | 2019 | Cross-browser compatibility |
| Check reduced-motion once | Listen for changes with `matchMedia` | 2020 | Respects runtime preference changes |
| CSS transitions for SVG | D3 transition with `.attrTween()` | D3 v4 (2016) | Proper arc interpolation |
| Separate SVG + PNG export code | Unified export utility | Best practice | DRY, easier maintenance |

**Deprecated/outdated:**
- `aria-describedby` alone for complex images: Less reliable than `aria-labelledby` with both title and desc IDs
- canvg library for PNG export: Modern browsers support direct Canvas rendering of SVG data URIs

## Open Questions

Things that couldn't be fully resolved:

1. **Pattern Fill Implementation Details**
   - What we know: SVG pattern fills work, need inline definitions
   - What's unclear: Best pattern shapes for donut vs bar (stripes, dots, crosshatch?)
   - Recommendation: Research colorblind-safe patterns; user testing recommended

2. **Screen Reader Testing Scope**
   - What we know: NVDA on Windows, VoiceOver on macOS are primary targets
   - What's unclear: Mobile screen reader behavior (TalkBack, iOS VoiceOver)
   - Recommendation: Test with desktop readers first, document mobile behavior

3. **PublicationsTimelineChart Handling**
   - What we know: Uses Chart.js (Canvas), not D3 (SVG)
   - What's unclear: Whether to migrate to D3 or add Canvas-specific export
   - Recommendation: Keep Chart.js, use native Canvas export (`toDataURL`)

## Sources

### Primary (HIGH confidence)
- Codebase analysis: DonutChart.vue, StackedBarChart.vue, KaplanMeierChart.vue, VariantComparisonChart.vue, BoxPlotChart.vue
- Codebase analysis: designTokens.js, tooltip.js, colors.js
- Codebase analysis: package.json (confirmed file-saver, d3 versions)

### Secondary (MEDIUM confidence)
- [Smashing Magazine - Accessible SVG Patterns](https://www.smashingmagazine.com/2021/05/accessible-svg-patterns-comparison/) - SVG accessibility patterns
- [TPGi - Using ARIA to Enhance SVG Accessibility](https://www.tpgi.com/using-aria-enhance-svg-accessibility/) - ARIA role/labelledby patterns
- [web.dev - prefers-reduced-motion](https://web.dev/articles/prefers-reduced-motion) - Animation accessibility
- [MDN - prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion) - CSS media query reference
- [D3 Graph Gallery - Bar Animation](https://d3-graph-gallery.com/graph/barplot_animation_start.html) - Bar chart animation patterns
- [Jon Sadka - Adaptive Pie Charts](https://jonsadka.com/blog/how-to-create-adaptive-pie-charts-with-transitions-in-d3/) - Arc tween animation
- [Louise Moxy - D3 Line Animation](https://medium.com/@louisemoxy/create-a-d3-line-chart-animation-336f1cb7dd61) - Path drawing animation
- [W3C - WCAG 1.4.1 Use of Color](https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html) - Colorblind accessibility

### Tertiary (LOW confidence)
- [d3-svg-to-png npm](https://www.npmjs.com/package/d3-svg-to-png) - Not needed; project has file-saver already

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All dependencies already installed, patterns verified in codebase
- Architecture: HIGH - Based on existing code patterns in the repository
- Pitfalls: MEDIUM - Based on web research and common D3/SVG issues
- Accessibility: MEDIUM - Based on W3C/WCAG documentation, needs user testing

**Research date:** 2026-01-20
**Valid until:** 2026-02-20 (30 days - patterns are stable)
