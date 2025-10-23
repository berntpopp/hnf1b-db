# Issue #52: feat(backend): add /by-publication/{pmid} phenopackets endpoint

## Overview
Create backend endpoint to efficiently query phenopackets by publication PMID with server-side filtering, replacing client-side filtering of all 864 phenopackets.

**Current:** Frontend fetches all phenopackets, filters client-side
**Target:** Server-side filtering with optimized database query

## Privacy and Compliance

### HIPAA/GDPR Assessment
- **Data Classification:** Phenopackets may contain de-identified clinical data (HPO terms, sex, age ranges)
- **HIPAA:** De-identified data under Safe Harbor method (no direct identifiers)
- **GDPR Compliance:**
  - Processing based on legitimate scientific research interest (GDPR Article 9(2)(j))
  - De-identified phenotypic data: no personal identifiers exposed
  - PMID filtering does not create re-identification risk
  - Access control: Endpoint should require authentication if PHI risk exists

### Data Minimization
- **Query Design:** Returns only phenopackets matching publication filter
- **Pagination:** Limits data exposure per request (max 500 records recommended)
- **Field Selection:** Returns full phenopacket (consider adding field projection in future)

## Why This Matters

Issue #37 (publication detail page) currently loads ALL 864 phenopackets to find the ~40 that cite a specific publication. This is inefficient and will not scale.

**Current Implementation (frontend/src/views/PagePublication.vue:331-336):**
```javascript
// Fetches ALL phenopackets (inefficient)
const phenopacketsResponse = await getPhenopackets({
  skip: 0,
  limit: 1000, // Fetch ALL to filter client-side
});

this.allPhenopackets = phenopacketsResponse.data;
```

**Target Implementation:**
```javascript
// Fetches only phenopackets for this publication
const response = await getPhenopacketsByPublication(pmid);
this.phenopackets = response.data;  // Only ~40 records
```

## Required Changes

### 1. API Endpoint

**File:** `backend/app/phenopackets/router.py` (add new endpoint)

```http
GET /api/v2/phenopackets/by-publication/{pmid}

Query Parameters:
- skip: int = 0 (pagination offset)
- limit: int = 100 (max records to return)
- sex: str | None (filter by sex)
- has_variants: bool | None (filter by variant presence)

Response: 200 OK
{
  "data": [
    {
      "phenopacket_id": "phenopacket-001",
      "phenopacket": { /* full GA4GH phenopacket */ }
    }
  ],
  "total": 42,
  "skip": 0,
  "limit": 100
}
```

### 2. Database Query

**File:** `backend/app/phenopackets/service.py` (add new function)

**⚠️ SECURITY NOTE:** This implementation includes input validation and parameterized queries to prevent SQL injection.

```python
import re
from typing import Dict, List, Any

def validate_pmid(pmid: str) -> str:
    """
    Validate and normalize PMID format.

    Args:
        pmid: PubMed ID (with or without PMID: prefix)

    Returns:
        Normalized PMID (format: PMID:12345678)

    Raises:
        ValueError: If PMID format is invalid
    """
    if not pmid.startswith("PMID:"):
        pmid = f"PMID:{pmid}"

    # Validate format: PMID followed by 1-8 digits only
    if not re.match(r'^PMID:\d{1,8}$', pmid):
        raise ValueError(f"Invalid PMID format: {pmid}. Expected PMID:12345678")

    return pmid

async def get_phenopackets_by_publication(
    pmid: str,
    skip: int = 0,
    limit: int = 100,
    sex: str | None = None,
    has_variants: bool | None = None,
    db: AsyncSession = None
) -> dict:
    """
    Get phenopackets that cite a specific publication.

    Queries JSONB metaData.externalReferences array for PMID match.

    Args:
        pmid: Validated PubMed ID (format: PMID:12345678)
        skip: Pagination offset (default: 0)
        limit: Max records to return (default: 100, max: 500)
        sex: Optional sex filter (MALE|FEMALE|OTHER_SEX|UNKNOWN_SEX)
        has_variants: Optional variant presence filter
        db: Database session

    Returns:
        Dict with data, total, skip, limit

    Raises:
        ValueError: If PMID format is invalid
        HTTPException: If database query fails
    """
    # SECURITY: Validate PMID format to prevent SQL injection
    pmid = validate_pmid(pmid)

    # SECURITY: Cap limit to prevent excessive data exposure
    limit = min(limit, 500)

    # Build query with JSONB filtering
    query = """
        SELECT
            id AS phenopacket_id,
            jsonb AS phenopacket
        FROM phenopackets
        WHERE jsonb->'metaData'->'externalReferences' @> :pmid_filter
    """

    # Build JSONB filter for PMID (parameterized - safe from injection)
    pmid_filter = json.dumps([{"id": pmid}])

    params = {"pmid_filter": pmid_filter, "skip": skip, "limit": limit}

    # Add optional filters with parameterized queries
    if sex:
        # SECURITY: Validate sex enum value
        valid_sex_values = {"MALE", "FEMALE", "OTHER_SEX", "UNKNOWN_SEX"}
        if sex not in valid_sex_values:
            raise ValueError(f"Invalid sex value: {sex}. Must be one of {valid_sex_values}")
        query += " AND subject_sex = :sex"
        params["sex"] = sex

    if has_variants is not None:
        if has_variants:
            query += " AND jsonb_array_length(jsonb->'interpretations') > 0"
        else:
            query += " AND (jsonb->'interpretations' IS NULL OR jsonb_array_length(jsonb->'interpretations') = 0)"

    # FIXED: SQL injection risk - use parameterized count query
    count_query = """
        SELECT COUNT(*)
        FROM phenopackets
        WHERE jsonb->'metaData'->'externalReferences' @> :pmid_filter
    """

    # Add same filters to count query
    if sex:
        count_query += " AND subject_sex = :sex"
    if has_variants is not None:
        if has_variants:
            count_query += " AND jsonb_array_length(jsonb->'interpretations') > 0"
        else:
            count_query += " AND (jsonb->'interpretations' IS NULL OR jsonb_array_length(jsonb->'interpretations') = 0)"

    total_result = await db.execute(text(count_query), params)
    total = total_result.scalar()

    # Add pagination (parameters prevent injection)
    query += " ORDER BY phenopacket_id LIMIT :limit OFFSET :skip"

    # Execute query
    result = await db.execute(text(query), params)
    rows = result.fetchall()

    return {
        "data": [
            {
                "phenopacket_id": row.phenopacket_id,
                "phenopacket": row.phenopacket
            }
            for row in rows
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }
```

### 3. Router Endpoint

**File:** `backend/app/phenopackets/router.py` (add new route)

```python
from pydantic import BaseModel
from typing import List, Dict, Any

class PhenopacketsByPublicationResponse(BaseModel):
    """Response schema for phenopackets by publication endpoint."""
    data: List[Dict[str, Any]]
    total: int
    skip: int
    limit: int

@router.get("/by-publication/{pmid}", response_model=PhenopacketsByPublicationResponse)
async def get_by_publication(
    pmid: str,
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Max records (max: 500)"),
    sex: str | None = Query(None, regex="^(MALE|FEMALE|OTHER_SEX|UNKNOWN_SEX)$", description="Filter by sex"),
    has_variants: bool | None = Query(None, description="Filter by variant presence"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get phenopackets citing a specific publication.

    **Security:** PMID is validated to prevent SQL injection.

    **Parameters:**
    - **pmid**: PubMed ID (format: PMID:12345678 or just 12345678)
    - **skip**: Pagination offset (default: 0)
    - **limit**: Max records to return (default: 100, max: 500)
    - **sex**: Filter by sex (MALE|FEMALE|OTHER_SEX|UNKNOWN_SEX)
    - **has_variants**: Filter by variant presence (true/false)

    **Returns:**
    - Phenopackets where metaData.externalReferences contains this PMID
    - Total count of matching phenopackets
    - Pagination metadata

    **Error Codes:**
    - 400: Invalid PMID format or parameters
    - 404: No phenopackets found for this publication
    - 500: Database error
    """
    try:
        result = await get_phenopackets_by_publication(
            pmid=pmid,  # Will be validated inside service function
            skip=skip,
            limit=limit,
            sex=sex,
            has_variants=has_variants,
            db=db
        )

        # Return 404 if no results found
        if result["total"] == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No phenopackets found citing publication {pmid}"
            )

        return result

    except ValueError as e:
        # Invalid PMID format or parameter
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching phenopackets for PMID {pmid}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

### 4. JSONB Index Optimization

**File:** `backend/alembic/versions/xxxx_add_publication_index.py`

```sql
-- Add GIN index for externalReferences queries
CREATE INDEX idx_phenopackets_external_refs
ON phenopackets
USING GIN ((jsonb->'metaData'->'externalReferences'));

-- This enables fast containment queries (@> operator)
```

## Implementation Checklist

### Phase 1: Database Query (2 hours)
- [ ] Write SQL query using JSONB `@>` containment operator
- [ ] Test query in PostgreSQL with EXPLAIN ANALYZE
- [ ] Verify index is used (should show "Bitmap Index Scan")
- [ ] Add optional filters (sex, has_variants)
- [ ] Implement pagination

### Phase 2: Service Layer (2 hours)
- [ ] Create `get_phenopackets_by_publication()` in service.py
- [ ] Implement PMID format normalization
- [ ] Add total count query
- [ ] Test with various PMIDs
- [ ] Handle edge cases (no results, invalid PMID)

### Phase 3: API Endpoint (1 hour)
- [ ] Add route to `phenopackets/router.py`
- [ ] Add query parameter validation
- [ ] Add error handling
- [ ] Test with curl/Postman
- [ ] Verify OpenAPI docs

### Phase 4: Performance Optimization (1 hour)
- [ ] Create GIN index on externalReferences
- [ ] Run EXPLAIN ANALYZE before/after index
- [ ] Verify query time < 50ms
- [ ] Test with multiple PMIDs

### Phase 5: Testing (2 hours)
- [ ] Unit tests for service function
- [ ] Integration test for endpoint
- [ ] Test pagination
- [ ] Test filters (sex, has_variants)
- [ ] Test PMID format normalization
- [ ] Add to CI/CD

## Acceptance Criteria

### Backend Service
- [x] `get_phenopackets_by_publication()` function implemented
- [x] PMID format normalized (handles with/without PMID: prefix)
- [x] Optional filters work (sex, has_variants)
- [x] Pagination works correctly
- [x] Total count accurate

### API Endpoint
- [x] `/by-publication/{pmid}` endpoint responds
- [x] Returns only phenopackets citing this PMID
- [x] Query parameters work (skip, limit, sex, has_variants)
- [x] Error handling (404 if no results, 400 for invalid params)
- [x] OpenAPI docs generated

### Performance
- [x] GIN index created on externalReferences
- [x] Query time < 50ms (with index)
- [x] Index used in query plan (verify with EXPLAIN ANALYZE)

### Testing
- [x] Unit tests pass
- [x] Integration tests pass
- [x] Pagination tested
- [x] Filters tested
- [x] CI/CD includes tests

## Files to Create/Modify

### Modified Files (3 files, ~120 lines added)
- `backend/app/phenopackets/service.py` (+60 lines for new function)
- `backend/app/phenopackets/router.py` (+30 lines for new endpoint)
- `backend/alembic/versions/xxxx_add_publication_index.py` (+30 lines for migration)
- `backend/tests/test_phenopackets.py` (+50 lines for new tests)

## Dependencies

**Blocked by:** None

**Blocks:**
- Issue #37 Phase 2 (frontend publication detail enhancements)

**Related:**
- Issue #51 (PubMed API integration) - can be done in parallel

## Performance Impact

**Before (client-side filtering):**
- Fetches all 864 phenopackets: ~300ms
- Client-side filtering: ~50ms
- Total: ~350ms
- Network payload: ~2MB

**After (server-side filtering):**
- Query with index: ~20ms
- Returns only matching records (~40): ~30ms
- Total: ~50ms ✅
- Network payload: ~100KB ✅

**Performance gain:** 7x faster, 95% less data transferred

## Testing Verification

### Manual Testing

```bash
# 1. Create index
cd backend
uv run alembic upgrade head

# 2. Start backend
make backend

# 3. Test endpoint
curl "http://localhost:8000/api/v2/phenopackets/by-publication/30791938"

# Expected: Returns phenopackets citing PMID:30791938

# 4. Test with pagination
curl "http://localhost:8000/api/v2/phenopackets/by-publication/30791938?skip=0&limit=10"

# Expected: First 10 results

# 5. Test with filters
curl "http://localhost:8000/api/v2/phenopackets/by-publication/30791938?sex=FEMALE&has_variants=true"

# Expected: Only female individuals with variants

# 6. Test PMID normalization
curl "http://localhost:8000/api/v2/phenopackets/by-publication/PMID:30791938"

# Expected: Same results as test #3

# 7. Verify query performance
psql $DATABASE_URL -c "EXPLAIN ANALYZE
  SELECT id FROM phenopackets
  WHERE jsonb->'metaData'->'externalReferences' @> '[{\"id\":\"PMID:30791938\"}]';"

# Expected: "Bitmap Index Scan on idx_phenopackets_external_refs"
```

### Frontend Integration Test

```javascript
// Update frontend/src/api/index.js
export const getPhenopacketsByPublication = (pmid, params = {}) =>
  apiClient.get(`/phenopackets/by-publication/${pmid}`, { params });

// Update frontend/src/views/PagePublication.vue
async loadPublicationData() {
  // OLD: Fetch all phenopackets
  // const phenopacketsResponse = await getPhenopackets({skip: 0, limit: 1000});

  // NEW: Fetch only phenopackets for this publication
  const phenopacketsResponse = await getPhenopacketsByPublication(this.pmid, {
    skip: 0,
    limit: 100
  });

  this.phenopackets = phenopacketsResponse.data.data;  // Access nested data
}
```

## Timeline

**Estimated:** 8 hours (1 day)

## Priority

**P2 (Medium)** - Performance optimization for issue #37

## Labels

`backend`, `api`, `performance`, `jsonb`, `p2`

## Monitoring and Observability

### Metrics to Track

```python
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
publication_query_requests_total = Counter(
    'publication_query_requests_total',
    'Total publication query requests',
    ['pmid', 'status']
)

publication_query_latency = Histogram(
    'publication_query_latency_seconds',
    'Publication query latency',
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

publication_query_results = Histogram(
    'publication_query_results_count',
    'Number of phenopackets per publication query',
    buckets=[0, 1, 5, 10, 25, 50, 100, 200, 500]
)

# Index performance
publication_query_index_usage = Counter(
    'publication_query_index_usage_total',
    'Whether GIN index was used in query',
    ['index_used']
)
```

### Structured Logging

```python
import structlog

logger = structlog.get_logger()

# Log query execution
logger.info(
    "publication_query_executed",
    pmid=pmid,
    total_results=total,
    query_time_ms=query_time * 1000,
    filters={"sex": sex, "has_variants": has_variants},
    pagination={"skip": skip, "limit": limit}
)
```

### Alerting Thresholds

- **Error Rate:** Alert if publication query error rate >5% over 5 minutes
- **Latency:** Alert if p95 latency >100ms (indicates index not being used)
- **No Results:** Log warning if publication has 0 phenopackets (may indicate data issue)
- **Large Result Sets:** Log warning if query returns >200 phenopackets (uncommon for single publication)

### Dashboard Metrics

- Query latency histogram (p50, p95, p99)
- Requests per publication (top 10 PMIDs)
- Error rate by error type (400, 404, 500)
- Index usage percentage (should be 100%)
- Average phenopackets per publication

## Testing Requirements

### Unit Tests (≥80% coverage)

**File:** `backend/tests/test_phenopackets_service.py`

```python
import pytest
from app.phenopackets.service import validate_pmid, get_phenopackets_by_publication

class TestPMIDValidation:
    """Test PMID validation and normalization."""

    def test_validate_pmid_with_prefix(self):
        """Test PMID with PMID: prefix."""
        assert validate_pmid("PMID:12345678") == "PMID:12345678"

    def test_validate_pmid_without_prefix(self):
        """Test PMID without prefix - should add it."""
        assert validate_pmid("12345678") == "PMID:12345678"

    def test_validate_pmid_invalid_format_letters(self):
        """Test PMID with invalid characters."""
        with pytest.raises(ValueError, match="Invalid PMID format"):
            validate_pmid("PMID:abc123")

    def test_validate_pmid_invalid_format_special_chars(self):
        """Test PMID with SQL injection attempt."""
        with pytest.raises(ValueError, match="Invalid PMID format"):
            validate_pmid("PMID:123'; DROP TABLE phenopackets;--")

    def test_validate_pmid_too_long(self):
        """Test PMID with too many digits."""
        with pytest.raises(ValueError, match="Invalid PMID format"):
            validate_pmid("PMID:123456789")  # 9 digits, max is 8

    def test_validate_pmid_empty(self):
        """Test empty PMID."""
        with pytest.raises(ValueError, match="Invalid PMID format"):
            validate_pmid("")

class TestGetPhenopacketsByPublication:
    """Test get_phenopackets_by_publication service function."""

    @pytest.mark.asyncio
    async def test_get_phenopackets_basic(self, db_session, sample_phenopackets):
        """Test basic query for phenopackets by publication."""
        result = await get_phenopackets_by_publication(
            pmid="PMID:30791938",
            db=db_session
        )

        assert result["total"] > 0
        assert len(result["data"]) <= 100  # Default limit
        assert all("phenopacket_id" in item for item in result["data"])
        assert all("phenopacket" in item for item in result["data"])

    @pytest.mark.asyncio
    async def test_get_phenopackets_with_pagination(self, db_session):
        """Test pagination parameters."""
        result = await get_phenopackets_by_publication(
            pmid="PMID:30791938",
            skip=10,
            limit=5,
            db=db_session
        )

        assert result["skip"] == 10
        assert result["limit"] == 5
        assert len(result["data"]) <= 5

    @pytest.mark.asyncio
    async def test_get_phenopackets_with_sex_filter(self, db_session):
        """Test filtering by sex."""
        result = await get_phenopackets_by_publication(
            pmid="PMID:30791938",
            sex="FEMALE",
            db=db_session
        )

        # Verify all returned phenopackets have sex=FEMALE
        for item in result["data"]:
            assert item["phenopacket"]["subject"]["sex"] == "FEMALE"

    @pytest.mark.asyncio
    async def test_get_phenopackets_invalid_sex(self, db_session):
        """Test invalid sex value raises ValueError."""
        with pytest.raises(ValueError, match="Invalid sex value"):
            await get_phenopackets_by_publication(
                pmid="PMID:30791938",
                sex="INVALID",
                db=db_session
            )

    @pytest.mark.asyncio
    async def test_get_phenopackets_limit_cap(self, db_session):
        """Test that limit is capped at 500."""
        result = await get_phenopackets_by_publication(
            pmid="PMID:30791938",
            limit=1000,  # Request 1000
            db=db_session
        )

        # Should be capped at 500
        assert result["limit"] == 500

    @pytest.mark.asyncio
    async def test_get_phenopackets_no_results(self, db_session):
        """Test query with no matching phenopackets."""
        result = await get_phenopackets_by_publication(
            pmid="PMID:99999999",  # Non-existent PMID
            db=db_session
        )

        assert result["total"] == 0
        assert len(result["data"]) == 0
```

### Integration Tests

**File:** `backend/tests/test_phenopackets_router.py`

```python
import pytest
from fastapi.testclient import TestClient

class TestPublicationEndpoint:
    """Integration tests for /by-publication/{pmid} endpoint."""

    def test_get_by_publication_success(self, client: TestClient):
        """Test successful query."""
        response = client.get("/api/v2/phenopackets/by-publication/30791938")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data

    def test_get_by_publication_with_prefix(self, client: TestClient):
        """Test with PMID: prefix."""
        response = client.get("/api/v2/phenopackets/by-publication/PMID:30791938")

        assert response.status_code == 200

    def test_get_by_publication_not_found(self, client: TestClient):
        """Test 404 when no phenopackets found."""
        response = client.get("/api/v2/phenopackets/by-publication/99999999")

        assert response.status_code == 404
        assert "No phenopackets found" in response.json()["detail"]

    def test_get_by_publication_invalid_pmid(self, client: TestClient):
        """Test 400 with invalid PMID format."""
        response = client.get("/api/v2/phenopackets/by-publication/invalid-pmid")

        assert response.status_code == 400
        assert "Invalid PMID format" in response.json()["detail"]

    def test_get_by_publication_sql_injection_attempt(self, client: TestClient):
        """Test SQL injection is prevented."""
        response = client.get("/api/v2/phenopackets/by-publication/123'; DROP TABLE phenopackets;--")

        assert response.status_code == 400  # Should reject, not execute SQL

    def test_get_by_publication_with_filters(self, client: TestClient):
        """Test with sex and variant filters."""
        response = client.get(
            "/api/v2/phenopackets/by-publication/30791938",
            params={"sex": "FEMALE", "has_variants": True}
        )

        assert response.status_code == 200
        data = response.json()
        # Verify filtering worked (check first result)
        if len(data["data"]) > 0:
            assert data["data"][0]["phenopacket"]["subject"]["sex"] == "FEMALE"

    def test_get_by_publication_pagination(self, client: TestClient):
        """Test pagination parameters."""
        response = client.get(
            "/api/v2/phenopackets/by-publication/30791938",
            params={"skip": 5, "limit": 10}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 5
        assert data["limit"] == 10
        assert len(data["data"]) <= 10

    def test_get_by_publication_limit_exceeds_max(self, client: TestClient):
        """Test that limit >500 is rejected."""
        response = client.get(
            "/api/v2/phenopackets/by-publication/30791938",
            params={"limit": 1000}
        )

        # FastAPI validation should reject limit >500
        assert response.status_code == 422  # Validation error
```

### Performance Tests

**File:** `backend/tests/test_phenopackets_performance.py`

```python
import pytest
import time
from sqlalchemy import text

class TestPublicationQueryPerformance:
    """Performance tests for publication queries."""

    @pytest.mark.asyncio
    async def test_query_uses_index(self, db_session):
        """Verify GIN index is used in query plan."""
        query = """
            EXPLAIN (ANALYZE, FORMAT JSON)
            SELECT id FROM phenopackets
            WHERE jsonb->'metaData'->'externalReferences' @> '[{"id":"PMID:30791938"}]'
        """

        result = await db_session.execute(text(query))
        explain_plan = result.scalar()

        # Check that GIN index is used
        plan_str = str(explain_plan)
        assert "idx_phenopackets_external_refs" in plan_str or "Bitmap Index Scan" in plan_str

    @pytest.mark.asyncio
    async def test_query_performance(self, db_session):
        """Test query completes in <100ms."""
        start_time = time.time()

        result = await get_phenopackets_by_publication(
            pmid="PMID:30791938",
            db=db_session
        )

        elapsed_time = time.time() - start_time

        assert elapsed_time < 0.1  # Should complete in <100ms with index
        assert result["total"] > 0
```

### Test Coverage Requirements

- **Minimum Coverage:** ≥80% for all new code
- **Critical Paths:** 100% coverage for `validate_pmid()` and SQL injection prevention
- **Run Tests:** `uv run pytest tests/test_phenopackets*.py -v --cov=app/phenopackets --cov-report=html`

## Deployment and Rollback Strategy

### Deployment Procedure

1. **Create Database Index:**
   ```bash
   cd backend
   uv run alembic upgrade head
   # Creates idx_phenopackets_external_refs GIN index
   ```

2. **Verify Index Creation:**
   ```bash
   psql $DATABASE_URL -c "\d phenopackets"
   # Should show idx_phenopackets_external_refs in indexes list
   ```

3. **Deploy Backend Code:**
   ```bash
   git pull
   uv sync
   systemctl restart hnf1b-backend
   ```

4. **Smoke Test:**
   ```bash
   curl "http://localhost:8000/api/v2/phenopackets/by-publication/30791938"
   # Should return 200 with phenopackets data
   ```

5. **Monitor Metrics:**
   - Check `publication_query_latency` p95 <100ms
   - Check `publication_query_index_usage` = 100%
   - Check error rate <1%

### Rollback Criteria

Rollback if any of these occur:
1. **Error Rate:** Query error rate >10% for 5 minutes
2. **Performance Degradation:** p95 latency >500ms (indicates index not being used)
3. **Database Connection Pool:** Exhaustion due to slow queries
4. **Data Integrity:** Incorrect phenopackets returned

### Rollback Procedure

```bash
# 1. Revert code deployment
git revert <commit-hash>
systemctl restart hnf1b-backend

# 2. Drop index if causing issues (optional)
psql $DATABASE_URL -c "DROP INDEX IF EXISTS idx_phenopackets_external_refs;"

# 3. Verify frontend falls back to client-side filtering
# (Frontend Issue #37 should handle missing endpoint gracefully)

# 4. Monitor error rate returns to baseline
```

## Notes

- **JSONB `@>` Operator:** Checks if left JSONB contains right JSONB
- **GIN Index:** Required for fast containment queries (without it: ~500ms, with it: ~20ms)
- **Index Size:** ~5MB for 864 phenopackets (negligible)
- **Alternative:** Could also use `jsonb_array_elements()` but `@>` is faster with GIN index
- **PMID Format:** Handle both "PMID:12345" and "12345" formats
- **Security:** All inputs validated, parameterized queries prevent SQL injection
- **Pagination Limit:** Capped at 500 to prevent excessive data exposure
- **Future Enhancement:** Could add caching layer for frequently accessed publications
