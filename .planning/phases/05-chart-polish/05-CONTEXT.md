# Phase 5: Chart Polish - Context

**Gathered:** 2026-01-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Enhance existing D3.js charts with accessibility, animations, and export functionality. Covers: DonutChart, StackedBarChart, KaplanMeierChart, VariantComparisonChart, and DNADistanceAnalysis components. New chart types or data visualizations are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Animation behavior
- Staggered animations on load — elements animate one after another (donut arcs, bar columns)
- Snappy duration (300-400ms) — quick, responsive feel
- Data updates use smooth transitions (morph between states), not full replay
- `prefers-reduced-motion`: instant render with zero animation

### Accessibility approach
- Screen reader text includes full data values (all categories with percentages/counts)
- No keyboard navigation required — SR text is sufficient for chart comprehension
- Keep existing design token colors (already color-blind reviewed in Phase 4)

### Export options
- PNG export: white background, 2x resolution
- Filenames: `{chart-type}-{timestamp}.png` (e.g., `variant-types-2026-01-20.png`)
- CSV headers: machine-friendly snake_case (`variant_type`, `count`, `percentage`)

### Visual polish
- Loading state: skeleton shapes matching chart dimensions
- Empty state: illustration + "No data available" message
- Error state: "Failed to load" message with retry button
- Tooltips: styled using existing design tokens (colors, shadows)

### Claude's Discretion
- Screen reader text placement (research best practices)
- Export menu placement (research best practices)
- Exact skeleton shape designs
- Illustration style for empty states
- Specific easing functions for animations

</decisions>

<specifics>
## Specific Ideas

- Staggered animation feels more "alive" — each bar or arc entering in sequence
- Error retry should be prominent enough to find but not disruptive
- Machine-friendly CSV headers enable easier data processing downstream

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-chart-polish*
*Context gathered: 2026-01-20*
