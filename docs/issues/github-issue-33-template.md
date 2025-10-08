# fix(frontend): update aggregation endpoints for phenopacket format

## Summary

The aggregations dashboard uses v1 endpoints that no longer exist (all return 404). Needs migration to v2 phenopacket-based aggregation endpoints with updated data formats.

**Current:** All aggregations return 404 errors
**Target:** Use `/api/v2/phenopackets/aggregate/*` endpoints

## Details

See detailed implementation plan: [docs/issues/issue-33-update-aggregation-endpoints.md](../docs/issues/issue-33-update-aggregation-endpoints.md)

## Key Changes

### New Aggregation Categories
- **Demographics:** Sex distribution
- **Clinical Features:** Top HPO terms, kidney disease stages
- **Diseases:** MONDO term distribution
- **Genomic:** Variant pathogenicity (ACMG)

### Response Format Change
```javascript
// Old v1 (with wrapper)
{ "data": [...], "meta": {...} }

// New v2 (direct array)
[{ "key": "...", "label": "...", "count": 123 }]
```

## Acceptance Criteria

- [ ] Dashboard categories updated (Demographics, Clinical, Diseases, Genomic)
- [ ] All deprecated aggregations removed (age-onset, cohort, publications)
- [ ] New aggregations implemented (HPO terms, diseases, kidney stages, pathogenicity)
- [ ] Data fetching updated to use v2 endpoints
- [ ] Chart data transformation handles new format (`key`/`label`/`count`)
- [ ] All dropdowns populate correctly
- [ ] No 404 errors in console
- [ ] Charts render without errors
- [ ] DonutChart/StackedBarChart/TimePlot work correctly

## Dependencies

- Issue #30 (API client migration) - ✅ Required

## Priority

**P2 (Medium)** - Important for visualization, not blocking core workflows

## Labels

`frontend`, `charts`, `api`, `data-visualization`, `p2`
