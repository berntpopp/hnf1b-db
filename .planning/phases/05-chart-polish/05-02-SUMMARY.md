---
phase: 05-chart-polish
plan: 02
subsystem: frontend-charts
tags: [donut-chart, accessibility, animation, export, d3, wcag]
dependency-graph:
  requires: [05-01]
  provides: [donut-chart-accessibility, donut-chart-animation, donut-chart-export]
  affects: []
tech-stack:
  added: []
  patterns: [arc-tween-animation, staggered-entry, prefers-reduced-motion, csv-export]
file-tracking:
  key-files:
    created:
      - frontend/tests/components/analyses/DonutChart.spec.js
    modified:
      - frontend/src/components/analyses/DonutChart.vue
decisions:
  - id: chart-id-random
    choice: Use Math.random() for unique chart IDs
    reason: Simple and sufficient for non-cryptographic uniqueness
  - id: mouse-events-after-animation
    choice: Attach mouse event handlers after animation completes
    reason: Prevents interaction during animation for better UX
  - id: dual-animation-path
    choice: Support both animated and instant rendering paths
    reason: Clean code for prefers-reduced-motion when duration is 0
metrics:
  duration: 5m
  completed: 2026-01-20
---

# Phase 5 Plan 2: DonutChart Accessibility, Animation, and Export Summary

Accessible, animated donut chart with staggered arc entry and PNG/CSV export.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 33d4b58 | feat | Add accessibility to DonutChart (role, aria-labelledby, title, desc) |
| ae3a165 | feat | Add entry animation to DonutChart (arc tween, stagger delay) |
| 3c911bd | feat | Add export functionality and tests (PNG, CSV, 36 tests) |

## What Was Built

### Accessibility (`frontend/src/components/analyses/DonutChart.vue`)
- role="img" added to root SVG element
- aria-labelledby pointing to title and desc elements
- title element with "Distribution Chart"
- desc element with generated description (total, categories, percentages)
- aria-hidden="true" on decorative slice paths
- aria-hidden="true" on central text element

### Animation
- arcTween method for smooth arc interpolation
- 400ms initial load animation, 200ms for data updates
- 50ms stagger delay between slices
- Respects prefers-reduced-motion (returns 0 duration)
- Mouse event handlers attached after animation completes

### Export
- ChartExportMenu component with PNG and CSV options
- handleExportPNG: 2x resolution PNG with timestamp filename
- handleExportCSV: category, count, percentage columns
- chart-header CSS for menu positioning

## Test Coverage

| File | Tests |
|------|-------|
| DonutChart.spec.js | 36 |
| **Total** | **36** |

### Test Categories
- Rendering: 6 tests
- SVG creation: 3 tests
- Accessibility: 6 tests
- Export functionality: 5 tests
- Props: 6 tests
- Data reactivity: 1 test
- Methods: 4 tests
- Edge cases: 4 tests

## Key Patterns Established

### Arc Tween Animation Pattern
```javascript
arcTween(arc) {
  return function (d) {
    const interpolate = d3.interpolate(
      this._current || { startAngle: 0, endAngle: 0 },
      d
    );
    this._current = interpolate(1);
    return function (t) {
      return arc(interpolate(t));
    };
  };
}
```

### Conditional Animation Pattern
```javascript
if (duration > 0) {
  slices
    .transition()
    .duration(duration)
    .delay((d, i) => getStaggerDelay(i, staggerDelayMs))
    .attrTween('d', arcTweenFn)
    .on('end', function(d) {
      // Attach events after animation
    });
} else {
  // Instant render path
  slices.attr('d', arc);
  slices.on('mouseover', ...);
}
```

## Deviations from Plan

None - plan executed exactly as written.

## Files Modified

```
frontend/src/components/analyses/
  DonutChart.vue               # 385 lines (+131)

frontend/tests/components/analyses/
  DonutChart.spec.js           # 355 lines (new)
```

## Requirements Fulfilled

| Requirement | Description | Status |
|-------------|-------------|--------|
| A11Y-01 | role="img" and aria-labelledby | Done |
| A11Y-02 | title and desc elements | Done |
| A11Y-05 | Screen reader description | Done |
| CHART-01 | Entry animation on load | Done |
| CHART-04 | Staggered timing | Done |
| CHART-05 | prefers-reduced-motion support | Done |
| CHART-06 | PNG export | Done |
| CHART-07 | CSV export | Done |
| CHART-08 | 2x resolution | Done |
| CHART-09 | snake_case headers | Done |

## Next Phase Readiness

DonutChart is now fully enhanced with accessibility, animation, and export. No blockers identified.

---
*Summary generated: 2026-01-20*
