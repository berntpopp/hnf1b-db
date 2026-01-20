---
phase: 05-chart-polish
plan: 04
subsystem: frontend-charts
tags: [kaplan-meier, survival-analysis, accessibility, animation, export, d3, wcag]
dependency-graph:
  requires: [05-01]
  provides: [kaplan-meier-accessibility, kaplan-meier-animation, kaplan-meier-export]
  affects: []
tech-stack:
  added: []
  patterns: [path-drawing-animation, staggered-fade-in, aria-hidden-decorative]
file-tracking:
  key-files:
    created: []
    modified:
      - frontend/src/components/analyses/KaplanMeierChart.vue
      - frontend/tests/unit/components/KaplanMeierChart.spec.js
decisions:
  - id: path-drawing-animation
    choice: Use stroke-dasharray/dashoffset for curve animation
    reason: Creates smooth line drawing effect for survival curves
  - id: staggered-group-animation
    choice: Stagger groups by 300ms delay
    reason: Visual separation between multiple survival curves
  - id: confidence-band-fade
    choice: Animate confidence bands with opacity fade-in
    reason: Subtle appearance that doesn't compete with main curve animation
  - id: 2000ms-line-duration
    choice: Use 2000ms animation duration for line charts
    reason: Per CONTEXT.md, longer duration for line chart types
  - id: event-marker-after-curve
    choice: Fade in event markers after curve animation completes
    reason: Sequential visual flow - curve draws, then markers appear
metrics:
  duration: 3m
  completed: 2026-01-20
---

# Phase 5 Plan 4: KaplanMeierChart Polish Summary

Accessible Kaplan-Meier survival chart with path drawing animation and multi-format export (PNG/CSV/SVG).

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 3ea8854 | feat | Add accessibility, animation, and export to KaplanMeierChart |

## What Was Built

### Accessibility (Task 1)

Added WCAG-compliant accessibility to KaplanMeierChart:

- **ARIA attributes**: `role="img"`, `aria-labelledby` pointing to `<title>` and `<desc>` elements
- **Screen reader description**: Uses `generateLineChartDescription(groups)` to announce group names, sample sizes, and event counts
- **Decorative elements hidden**: Grid lines, curves, confidence bands, median lines, censoring markers all have `aria-hidden="true"`
- **Interactive elements accessible**: Event markers (circles) are kept accessible for tooltip interaction

### Path Drawing Animation (Task 2)

Added stroke-dasharray-based path drawing animation:

- **Survival curves**: Draw progressively using `stroke-dasharray` and `stroke-dashoffset` transition
- **Duration**: 2000ms for line charts (per CONTEXT.md)
- **Stagger**: Each group starts 300ms after the previous (groupIndex * 300)
- **Confidence bands**: Fade in with opacity transition (0 to 0.15)
- **Event markers**: Fade in after curve completes (delay = stagger + duration)
- **Reduced motion**: All animations disabled when `prefers-reduced-motion: reduce`

Animation flow:
1. Confidence band fades in (duration/2)
2. Survival curve draws (full duration)
3. Event markers fade in (300ms after curve)
4. Next group starts 300ms later

### Export Functionality (Task 3)

Upgraded export with ChartExportMenu component:

- **PNG export**: Uses `exportToPNG()` at 2x resolution with white background
- **CSV export**: Flattens all survival data from all groups with columns:
  - `group_name`, `time_years`, `survival_probability`
  - `ci_lower`, `ci_upper`, `at_risk`, `events`, `censored`
- **SVG export**: Preserved existing SVG download button
- **Filename**: `kaplan-meier-{comparison_type}-{endpoint}-{timestamp}.{ext}`

## Test Coverage

| Description | Tests |
|-------------|-------|
| Existing tests | 39 |
| New export tests | 5 |
| New accessibility tests | 2 |
| New animation tests | 2 |
| ChartExportMenu render test | 1 |
| Props with stubs | 1 |
| **Total** | **50** |

New test categories:
- `Export Functionality`: Tests handleExportPNG, handleExportCSV, exportSVG methods
- `Accessibility`: Tests addChartAccessibility and generateLineChartDescription calls
- `Animation`: Tests getAnimationDuration(2000) and prefersReducedMotion calls

## Animation Pattern Established

```javascript
// Path drawing animation pattern for line charts
const curvePath = svg.append('path')
  .datum(data)
  .attr('d', line)
  .attr('aria-hidden', 'true');

if (!reducedMotion && duration > 0) {
  const totalLength = curvePath.node().getTotalLength();
  curvePath
    .attr('stroke-dasharray', `${totalLength} ${totalLength}`)
    .attr('stroke-dashoffset', totalLength)
    .transition()
    .delay(staggerDelay)
    .duration(duration)
    .ease(d3.easeLinear)
    .attr('stroke-dashoffset', 0);
}

// Fade-in pattern for area fills
confidenceBand
  .attr('fill-opacity', 0)
  .transition()
  .delay(staggerDelay)
  .duration(duration / 2)
  .attr('fill-opacity', 0.15);
```

## CSV Export Structure

```csv
group_name,time_years,survival_probability,ci_lower,ci_upper,at_risk,events,censored
Missense,0,1.0000,1.0000,1.0000,50,0,0
Missense,5,0.9000,0.8200,0.9800,45,5,0
...
Truncating,0,1.0000,1.0000,1.0000,30,0,0
```

## Deviations from Plan

None - plan executed exactly as written.

## Files Modified

```
frontend/src/components/analyses/
  KaplanMeierChart.vue        # +145 lines, -20 lines

frontend/tests/unit/components/
  KaplanMeierChart.spec.js    # +292 lines (50 tests total)
```

## Success Criteria Verification

- [x] KaplanMeierChart has role="img" and aria-labelledby on SVG (via addChartAccessibility)
- [x] KaplanMeierChart has title and desc elements with group summaries
- [x] Survival curves animate with path drawing effect
- [x] Animation respects prefers-reduced-motion
- [x] Export menu has PNG, CSV options (plus existing SVG button)
- [x] PNG export downloads at 2x resolution
- [x] CSV export downloads with all survival data points
- [x] All tests pass (50/50)

## Next Phase Readiness

Plan 05-04 complete. KaplanMeierChart is now fully polished with:
- Screen reader accessibility for survival curve data
- Engaging path drawing animation with staggered groups
- Three export formats (PNG, CSV, SVG) for research use

No blockers identified.

---
*Summary generated: 2026-01-20*
