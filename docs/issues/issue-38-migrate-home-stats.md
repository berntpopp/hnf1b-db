# Issue #38: feat(frontend): migrate home page statistics to v2 API

## Overview

Home page needs stats from new `/aggregate/summary` endpoint instead of broken v1 endpoints.

**Current:** Home.vue fetches stats from v1 (404 errors)
**Target:** Use `/api/v2/phenopackets/aggregate/summary`

## Required Endpoint

```http
GET /api/v2/phenopackets/aggregate/summary

Response:
{
  total_phenopackets: 864,
  total_variants: 312,
  total_publications: 45,
  with_phenotypic_features: 830,  // 96%
  with_variants: 423,              // 49%
  with_diseases: 864               // 100%
}
```

## Current Home Page Stats

- **Individuals:** Shows animated count
- **Variants:** Shows animated count
- **Publications:** Shows animated count

## Implementation

**Update:** `frontend/src/views/Home.vue`

```javascript
async fetchStats() {
  try {
    const response = await getSummaryStats();
    this.stats = {
      individuals: response.data.total_phenopackets,
      variants: response.data.total_variants,
      publications: response.data.total_publications,
    };
    this.animateStats();
  } catch (error) {
    console.error('Error fetching stats:', error);
  }
}
```

## Implementation Checklist

- [ ] Backend: Create `/aggregate/summary` endpoint
- [ ] API: Add `getSummaryStats()` function
- [ ] Home: Update fetchStats() method
- [ ] Test stats animate correctly
- [ ] Verify no 404 errors

## Acceptance Criteria

- [ ] Home page loads without errors
- [ ] Stats show correct counts
- [ ] Numbers animate smoothly
- [ ] No console errors

## Dependencies

**Depends On:** #30 (API client)

## Timeline

4 hours (0.5 days)

## Labels

`frontend`, `views`, `phenopackets`, `p1`
