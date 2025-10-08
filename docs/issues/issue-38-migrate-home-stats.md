# Issue #38: feat: migrate home page statistics to v2 API (backend + frontend)

## Overview

Create summary statistics endpoint for frontend home page to replace old `/aggregations/summary`. This combines backend endpoint creation with frontend migration.

**Current State:** No summary endpoint exists in v2 API, Home.vue shows 404 errors
**Required State:** `/api/v2/phenopackets/aggregate/summary` returns statistics, Home.vue displays them

## Why This Matters

### Current Frontend Need

```javascript
// Frontend home page needs summary stats
const stats = await getSummaryStats();
// GET /api/v2/phenopackets/aggregate/summary

// Expected response:
{
  "total_phenopackets": 864,
  "with_variants": 423,
  "with_phenotypes": 830,
  "with_diseases": 864,
  "distinct_hpo_terms": 150,
  "distinct_diseases": 50
}
```

**Problem:** This endpoint doesn't exist yet. Must be created in backend.

---

## Part 1: Backend Endpoint Implementation

### Endpoint Specification

**Route Definition**

File: `backend/app/phenopackets/endpoints.py`

```python
@router.get("/aggregate/summary", response_model=Dict[str, int])
async def get_summary_statistics(db: AsyncSession = Depends(get_db)):
    """Get summary statistics for phenopackets.

    Returns counts for:
    - Total phenopackets
    - Phenopackets with variants (interpretations)
    - Phenopackets with phenotypes (phenotypicFeatures)
    - Phenopackets with diseases
    - Distinct HPO terms
    - Distinct disease terms
    """
```

### SQL Queries Needed

**1. Total Phenopackets:**
```sql
SELECT COUNT(*) FROM phenopackets;
-- Expected: 864
```

**2. Phenopackets with Variants:**
```sql
SELECT COUNT(*)
FROM phenopackets
WHERE jsonb_array_length(jsonb->'interpretations') > 0;
-- Expected: ~423 (49% have variants)
```

**3. Phenopackets with Phenotypic Features:**
```sql
SELECT COUNT(*)
FROM phenopackets
WHERE jsonb_array_length(jsonb->'phenotypicFeatures') > 0;
-- Expected: ~830 (96% have features)
```

**4. Phenopackets with Diseases:**
```sql
SELECT COUNT(*)
FROM phenopackets
WHERE jsonb_array_length(jsonb->'diseases') > 0;
-- Expected: 864 (100% have diseases)
```

**5. Distinct HPO Terms:**
```sql
SELECT COUNT(DISTINCT feature->'type'->>'id')
FROM phenopackets,
     jsonb_array_elements(jsonb->'phenotypicFeatures') as feature;
-- Expected: ~150 distinct HPO terms
```

**6. Distinct Diseases:**
```sql
SELECT COUNT(DISTINCT disease->'term'->>'id')
FROM phenopackets,
     jsonb_array_elements(jsonb->'diseases') as disease;
-- Expected: ~50 distinct disease terms
```

### Complete Backend Implementation

File: `backend/app/phenopackets/endpoints.py`

```python
from typing import Dict
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

@router.get("/aggregate/summary", response_model=Dict[str, int])
async def get_summary_statistics(db: AsyncSession = Depends(get_db)):
    """Get summary statistics for all phenopackets.

    Returns:
        Dictionary with counts:
        - total_phenopackets: Total number of phenopackets
        - with_variants: Phenopackets containing interpretations
        - with_phenotypes: Phenopackets with phenotypic features
        - with_diseases: Phenopackets with disease diagnoses
        - distinct_hpo_terms: Number of unique HPO terms used
        - distinct_diseases: Number of unique disease terms used
    """

    # 1. Total phenopackets
    total_result = await db.execute(select(func.count()).select_from(Phenopacket))
    total_phenopackets = total_result.scalar()

    # 2. With variants (interpretations exist)
    with_variants_result = await db.execute(
        text("""
            SELECT COUNT(*)
            FROM phenopackets
            WHERE jsonb_array_length(jsonb->'interpretations') > 0
        """)
    )
    with_variants = with_variants_result.scalar()

    # 3. With phenotypic features
    with_phenotypes_result = await db.execute(
        text("""
            SELECT COUNT(*)
            FROM phenopackets
            WHERE jsonb_array_length(jsonb->'phenotypicFeatures') > 0
        """)
    )
    with_phenotypes = with_phenotypes_result.scalar()

    # 4. With diseases
    with_diseases_result = await db.execute(
        text("""
            SELECT COUNT(*)
            FROM phenopackets
            WHERE jsonb_array_length(jsonb->'diseases') > 0
        """)
    )
    with_diseases = with_diseases_result.scalar()

    # 5. Distinct HPO terms
    distinct_hpo_result = await db.execute(
        text("""
            SELECT COUNT(DISTINCT feature->'type'->>'id')
            FROM phenopackets,
                 jsonb_array_elements(jsonb->'phenotypicFeatures') as feature
            WHERE feature->'type'->>'id' IS NOT NULL
        """)
    )
    distinct_hpo_terms = distinct_hpo_result.scalar() or 0

    # 6. Distinct diseases
    distinct_diseases_result = await db.execute(
        text("""
            SELECT COUNT(DISTINCT disease->'term'->>'id')
            FROM phenopackets,
                 jsonb_array_elements(jsonb->'diseases') as disease
            WHERE disease->'term'->>'id' IS NOT NULL
        """)
    )
    distinct_diseases = distinct_diseases_result.scalar() or 0

    return {
        "total_phenopackets": total_phenopackets,
        "with_variants": with_variants,
        "with_phenotypes": with_phenotypes,
        "with_diseases": with_diseases,
        "distinct_hpo_terms": distinct_hpo_terms,
        "distinct_diseases": distinct_diseases,
    }
```

### Backend Testing

**Unit Test**

File: `backend/tests/test_aggregations.py` (create if doesn't exist)

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

async def test_summary_statistics(db_session: AsyncSession):
    """Test summary statistics endpoint."""
    from app.phenopackets.endpoints import get_summary_statistics

    # Call endpoint
    stats = await get_summary_statistics(db=db_session)

    # Verify structure
    assert "total_phenopackets" in stats
    assert "with_variants" in stats
    assert "with_phenotypes" in stats
    assert "with_diseases" in stats
    assert "distinct_hpo_terms" in stats
    assert "distinct_diseases" in stats

    # Verify types
    assert isinstance(stats["total_phenopackets"], int)
    assert isinstance(stats["with_variants"], int)

    # Verify logical constraints
    assert stats["with_variants"] <= stats["total_phenopackets"]
    assert stats["with_phenotypes"] <= stats["total_phenopackets"]
    assert stats["with_diseases"] <= stats["total_phenopackets"]
    assert stats["distinct_hpo_terms"] >= 0
    assert stats["distinct_diseases"] >= 0

    # Verify expected values (with 864 phenopackets)
    assert stats["total_phenopackets"] == 864
    assert stats["with_variants"] > 0  # Should have some variants
    assert stats["with_phenotypes"] > 0  # Should have features
    assert stats["with_diseases"] == 864  # All should have diseases
```

**Manual API Testing**

```bash
# 1. Start backend
cd backend && make backend

# 2. Test summary endpoint
curl http://localhost:8000/api/v2/phenopackets/aggregate/summary

# Expected response:
# {
#   "total_phenopackets": 864,
#   "with_variants": 423,
#   "with_phenotypes": 830,
#   "with_diseases": 864,
#   "distinct_hpo_terms": 150,
#   "distinct_diseases": 50
# }

# 3. Verify response time
time curl http://localhost:8000/api/v2/phenopackets/aggregate/summary
# Expected: < 200ms

# 4. Check API docs
# Open: http://localhost:8000/api/v2/docs
# Verify /phenopackets/aggregate/summary appears
```

---

## Part 2: Frontend Integration

### Update API Client

File: `frontend/src/api/index.js`

```javascript
/**
 * Get summary statistics for home page
 */
export async function getSummaryStats() {
  return apiClient.get('/phenopackets/aggregate/summary');
}
```

### Update Home Page

File: `frontend/src/views/Home.vue`

**Before:**
```javascript
async fetchStats() {
  // Old v1 endpoints (404 errors)
  const individuals = await getIndividualsCount();  // 404
  const variants = await getVariantsCount();        // 404
  const publications = await getPublicationsCount(); // 404
}
```

**After:**
```javascript
async fetchStats() {
  try {
    const response = await getSummaryStats();
    this.stats = {
      individuals: response.data.total_phenopackets,
      variants: response.data.with_variants,
      publications: response.data.distinct_diseases,  // Or fetch separately
    };
    this.animateStats();
  } catch (error) {
    console.error('Error fetching stats:', error);
    // Show fallback or error state
  }
}
```

### Current Home Page Stats

The home page displays three animated counters:
- **Individuals:** Shows `total_phenopackets` (864)
- **Variants:** Shows `with_variants` (423)
- **Publications:** Needs separate publications aggregation endpoint

**Note:** If publications count is needed, may require additional endpoint:
```http
GET /api/v2/phenopackets/aggregate/publications
```

---

## Implementation Checklist

### Phase 1: Backend Endpoint
- [ ] Add route decorator `@router.get("/aggregate/summary")`
- [ ] Add response model `response_model=Dict[str, int]`
- [ ] Implement 6 SQL queries for statistics
- [ ] Add error handling for empty database
- [ ] Add docstring explaining return values
- [ ] Write unit test in `test_aggregations.py`
- [ ] Run tests: `uv run pytest tests/test_aggregations.py -v`

### Phase 2: Frontend Integration
- [ ] Add `getSummaryStats()` to API client
- [ ] Update `Home.vue` to call new endpoint
- [ ] Map response fields to stats display
- [ ] Test stats animate correctly
- [ ] Verify no console 404 errors

### Phase 3: Performance
- [ ] Verify GIN indexes exist (from Issue #28)
- [ ] Test query performance (< 200ms)
- [ ] Test with 864 phenopackets
- [ ] Consider caching for frequently accessed stats

### Phase 4: Testing
- [ ] Backend unit tests pass
- [ ] Manual API test successful
- [ ] Frontend displays stats correctly
- [ ] No errors in browser console
- [ ] Stats animation smooth

---

## Acceptance Criteria

### Backend
- [ ] Endpoint responds at `/api/v2/phenopackets/aggregate/summary`
- [ ] Returns JSON object with 6 integer fields
- [ ] All counts are accurate
- [ ] Handles empty database gracefully (returns zeros)
- [ ] Query completes in < 200ms
- [ ] Appears in `/api/v2/docs` (Swagger UI)

### Frontend
- [ ] Home page loads without errors
- [ ] Stats show correct counts
- [ ] Numbers animate smoothly
- [ ] No console 404 errors
- [ ] Graceful error handling if endpoint fails

### Data Accuracy
- [ ] `total_phenopackets` = 864
- [ ] `with_variants` ≈ 423 (49%)
- [ ] `with_phenotypes` ≈ 830 (96%)
- [ ] `with_diseases` = 864 (100%)
- [ ] `distinct_hpo_terms` > 100
- [ ] `distinct_diseases` > 10

---

## Files to Modify

```
backend/app/phenopackets/
└── endpoints.py              # Add get_summary_statistics()

backend/tests/
└── test_aggregations.py      # Add test_summary_statistics()

frontend/src/api/
└── index.js                  # Add getSummaryStats()

frontend/src/views/
└── Home.vue                  # Update fetchStats() method
```

---

## Dependencies

**Depends On:**
- Issue #28 (JSONB GIN indexes) - For performance
- Issue #30 (API client migration) - Frontend API client setup

**Blocks:**
- None (improves home page UX but doesn't block other features)

---

## Performance Requirements

**Target Performance:**
- Response time: **< 200ms** for all 6 queries combined
- Uses existing GIN indexes (no sequential scans)
- Scalable to 10,000+ phenopackets

**Optimization:**
- All queries use GIN indexes on JSONB fields
- No N+1 query problems (single database round-trip)
- Consider adding Redis caching with 5-minute TTL for home page

---

## Timeline

- **Backend:** 4 hours (endpoint + tests)
- **Frontend:** 2 hours (integration + testing)
- **Total:** 6 hours (1 day)

---

## Priority

**P1 (High)** - User-facing, easy win, improves home page UX

---

## Labels

`backend`, `frontend`, `api`, `aggregation`, `p1`, `fullstack`

---

## Related Issues

- Issue #28 (JSONB indexes) - Provides query performance
- Issue #30 (Frontend API client) - Will call this endpoint
- Issue #33 (Aggregations dashboard) - Similar aggregation patterns
