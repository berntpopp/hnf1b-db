---
phase: 05-chart-polish
plan: 01
subsystem: frontend-utilities
tags: [d3, accessibility, animation, export, charts, wcag]
dependency-graph:
  requires: [04-01]
  provides: [chart-utilities, export-png, export-csv, accessibility-aria, animation-reduced-motion]
  affects: [05-02, 05-03, 05-04, 05-05]
tech-stack:
  added: []
  patterns: [utility-functions, d3-selection-support, prefers-reduced-motion]
file-tracking:
  key-files:
    created:
      - frontend/src/utils/export.js
      - frontend/src/utils/chartAccessibility.js
      - frontend/src/utils/chartAnimation.js
      - frontend/src/components/common/ChartExportMenu.vue
      - frontend/tests/unit/utils/export.spec.js
      - frontend/tests/unit/utils/chartAccessibility.spec.js
      - frontend/tests/unit/utils/chartAnimation.spec.js
      - frontend/tests/unit/components/common/ChartExportMenu.spec.js
    modified: []
decisions:
  - id: canvas-context-guard
    choice: Add null guard for canvas.getContext in test environments
    reason: happy-dom does not support Canvas 2D context
  - id: d3-and-raw-svg-support
    choice: Support both D3 selections and raw SVG elements in accessibility utility
    reason: Flexibility for different chart implementations
  - id: bom-for-csv
    choice: Add BOM (Byte Order Mark) to CSV exports
    reason: Excel compatibility for UTF-8 CSV files
  - id: spec-file-extension
    choice: Use .spec.js extension for tests
    reason: Consistent with existing codebase test file naming
metrics:
  duration: 5m
  completed: 2026-01-20
---

# Phase 5 Plan 1: Shared Chart Utilities Summary

Shared utilities for PNG/CSV export, ARIA accessibility, and reduced-motion animation supporting all chart components in Phase 5.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| ebe3428 | feat | Create export utilities (exportToPNG, exportToCSV, getTimestamp) |
| d326b22 | feat | Create accessibility and animation utilities |
| 2398de5 | feat | Create ChartExportMenu component |

## What Was Built

### Export Utilities (`frontend/src/utils/export.js`)
- `exportToPNG(svgElement, filename, scale)`: Export SVG to PNG at 2x resolution with white background
- `exportToCSV(data, headers, filename)`: Export data array to CSV with proper escaping and BOM for Excel
- `getTimestamp()`: Generate ISO date string (YYYY-MM-DD) for filenames

### Accessibility Utilities (`frontend/src/utils/chartAccessibility.js`)
- `addChartAccessibility(svg, titleId, descId, title, description)`: Add ARIA attributes to SVG
- `generateDonutDescription(data, total)`: Generate screen reader text for donut charts
- `generateBarChartDescription(data)`: Generate screen reader text for bar charts (top 10 truncation)
- `generateLineChartDescription(groups)`: Generate screen reader text for survival curves

### Animation Utilities (`frontend/src/utils/chartAnimation.js`)
- `prefersReducedMotion()`: Check user's prefers-reduced-motion setting
- `getAnimationDuration(defaultDuration)`: Return 0 if reduced motion, otherwise default
- `getStaggerDelay(index, delayPerItem)`: Return staggered delay or 0 if reduced motion
- `getEasingFunction()`: Return D3 easing function name or null
- `getAnimationConfig(options)`: Return complete animation config object

### ChartExportMenu Component (`frontend/src/components/common/ChartExportMenu.vue`)
- Reusable dropdown menu with PNG and CSV export options
- `showCsv` prop to conditionally hide CSV option
- Emits `export-png` and `export-csv` events

## Test Coverage

| File | Tests |
|------|-------|
| export.spec.js | 19 |
| chartAccessibility.spec.js | 25 |
| chartAnimation.spec.js | 25 |
| ChartExportMenu.spec.js | 16 |
| **Total** | **85** |

## Key Patterns Established

### PNG Export Pattern
```javascript
import { exportToPNG, getTimestamp } from '@/utils/export';

handlePngExport() {
  const svg = this.$refs.chart.querySelector('svg');
  exportToPNG(svg, `variant-types-${getTimestamp()}`);
}
```

### CSV Export Pattern
```javascript
import { exportToCSV, getTimestamp } from '@/utils/export';

handleCsvExport() {
  const data = this.chartData.map(d => ({
    variant_type: d.label,
    count: d.count,
    percentage: ((d.count / this.total) * 100).toFixed(1)
  }));
  exportToCSV(data, ['variant_type', 'count', 'percentage'], `variants-${getTimestamp()}`);
}
```

### Accessibility Pattern
```javascript
import { addChartAccessibility, generateDonutDescription } from '@/utils/chartAccessibility';

renderChart() {
  const svg = d3.select(this.$refs.chart).append('svg');
  const description = generateDonutDescription(this.data, this.total);
  addChartAccessibility(svg, 'chart-title', 'chart-desc', 'Sex Distribution', description);
}
```

### Animation Pattern
```javascript
import { getAnimationConfig } from '@/utils/chartAnimation';
import * as d3 from 'd3';

renderChart() {
  const config = getAnimationConfig({ duration: 400, staggerDelay: 50 });

  svg.selectAll('path')
    .transition()
    .duration(config.duration)
    .delay((d, i) => config.delay(i))
    .ease(config.easing ? d3[config.easing] : d3.easeLinear)
    .attrTween('d', arcTween);
}
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Canvas context null in test environment**
- **Found during:** Task 1
- **Issue:** `canvas.getContext('2d')` returns null in happy-dom test environment
- **Fix:** Added null guard with warning log message
- **Files modified:** `frontend/src/utils/export.js`
- **Commit:** ebe3428

**2. [Rule 1 - Bug] Test file naming convention**
- **Found during:** Task 1
- **Issue:** Plan specified `.test.js` but codebase uses `.spec.js`
- **Fix:** Used `.spec.js` extension for consistency with existing tests
- **Files modified:** All test files
- **Commit:** ebe3428, d326b22, 2398de5

## Files Created

```
frontend/src/utils/
  export.js                 # 170 lines
  chartAccessibility.js     # 142 lines
  chartAnimation.js         # 108 lines

frontend/src/components/common/
  ChartExportMenu.vue       # 67 lines

frontend/tests/unit/utils/
  export.spec.js            # 220 lines
  chartAccessibility.spec.js # 217 lines
  chartAnimation.spec.js    # 185 lines

frontend/tests/unit/components/common/
  ChartExportMenu.spec.js   # 161 lines
```

## Next Phase Readiness

All shared utilities are ready for use by individual chart components:
- **05-02**: DonutChart can use export, accessibility, and animation utilities
- **05-03**: StackedBarChart can use export, accessibility, and animation utilities
- **05-04**: KaplanMeierChart can use export, accessibility, and animation utilities
- **05-05**: VariantComparisonChart and BoxPlotChart can use export utilities

No blockers identified.

---
*Summary generated: 2026-01-20*
