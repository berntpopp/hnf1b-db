# fix(frontend): zoom functionality broken in variant visualizations

## Summary
D3.js zoom not working in HNF1B gene and protein visualization components. Users cannot zoom or pan to inspect variant details.

**Current:** Zoom controls present but non-functional
**Target:** Smooth zoom/pan with proper constraint bounds

## Acceptance Criteria
- [ ] Debug D3 zoom behavior in `HNF1BGeneVisualization.vue`
- [ ] Fix zoom in `HNF1BProteinVisualization.vue`
- [ ] Implement zoom extent limits (min: 1x, max: 10x)
- [ ] Add pan constraints to prevent scrolling off-canvas
- [ ] Add zoom reset button
- [ ] Ensure zoom persists during data updates
- [ ] Test on mobile/touch devices
- [ ] Add keyboard shortcuts (+ / -, 0 for reset)

## Priority
**P1 (High)** - Core visualization feature

## Labels
`bug`, `frontend`, `visualization`, `p1-high`
