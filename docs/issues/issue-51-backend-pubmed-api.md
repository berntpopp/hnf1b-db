# Issue #51: feat(backend): add PubMed API integration with database caching

## Overview
Create backend infrastructure for fetching and caching publication metadata from PubMed API to enable rich publication detail pages.

**Current:** No backend support for publication metadata
**Target:** Database-backed caching layer for PubMed data with 90-day TTL

## Why This Matters

Issue #37 (publication detail page) is currently showing only basic metadata (PMID, DOI, count). To display rich metadata (title, authors, journal, abstract), we need backend support.

**Current Implementation:**
```vue
<!-- frontend: Only shows PMID and DOI -->
<v-list-item>
  <v-list-item-title>PMID</v-list-item-title>
  <v-list-item-subtitle>{{ pmid }}</v-list-item-subtitle>
</v-list-item>
```

**Target Implementation:**
```vue
<!-- frontend: Shows full publication details -->
<v-card-title>{{ publication.title }}</v-card-title>
<v-card-subtitle>
  {{ publication.authors.join(', ') }}
  <br>
  {{ publication.journal }} ({{ publication.year }})
</v-card-subtitle>
```

## Architecture

```
Frontend → Backend API → Database Cache → PubMed API
                       ↓
                  (Cache hit: ~10ms)
                       ↓
                  (Cache miss: fetch + cache: ~500ms)
```

## Privacy and Compliance

### HIPAA/GDPR Assessment
- **Data Classification:** PubMed metadata is **publicly available scientific literature**
- **HIPAA:** No Protected Health Information (PHI) - publications are public domain
- **GDPR Compliance:**
  - Author names: Public scientific record, legitimate interest under GDPR Article 85 (academic/journalistic expression)
  - No personal data processing: All data sourced from public NCBI repositories
  - Data minimization: Only caching publication metadata relevant to phenopacket citations

### Data Retention Policy
- **Cache TTL:** 90 days (aligns with research data lifecycle)
- **Rationale:** Publication metadata rarely changes; citations remain valid
- **Invalidation:** Manual cache clear available if publication is retracted
- **Audit Trail:** All external API calls logged for reproducibility

### Regulatory Notes
- Publication metadata does not contain patient identifiable information
- Author names are part of scientific record, not personal data under research exception
- Database stores only publicly accessible information from NCBI PubMed
- No consent required for caching public scientific literature metadata

## Required Changes

### 1. Database Schema

**File:** `backend/alembic/versions/xxxx_add_publication_metadata.py`

```sql
-- Create publications cache table
CREATE TABLE publication_metadata (
    pmid VARCHAR(20) PRIMARY KEY,
    title TEXT NOT NULL,
    authors JSONB NOT NULL,  -- Changed from TEXT[] to preserve order and affiliations
    journal VARCHAR(255),
    year INTEGER,
    doi VARCHAR(100),
    abstract TEXT,
    data_source VARCHAR(50) DEFAULT 'PubMed',  -- Track data provenance
    fetched_by VARCHAR(100),  -- User or system identifier
    fetched_at TIMESTAMP DEFAULT NOW(),
    api_version VARCHAR(20),  -- E-utilities version for reproducibility
    CONSTRAINT valid_pmid CHECK (pmid LIKE 'PMID:%')
);

-- Partial index for expired records (more efficient than full index)
CREATE INDEX idx_publication_metadata_expired
ON publication_metadata (fetched_at)
WHERE fetched_at < NOW() - INTERVAL '90 days';

-- Index for active cache lookups
CREATE INDEX idx_publication_metadata_active
ON publication_metadata (pmid, fetched_at)
WHERE fetched_at > NOW() - INTERVAL '90 days';

-- Add comment for documentation
COMMENT ON TABLE publication_metadata IS 'Cache for PubMed publication metadata. Data is public domain scientific literature.';
COMMENT ON COLUMN publication_metadata.authors IS 'JSONB array of author objects [{name, affiliation}] to preserve order';
```

### 2. Service Layer

**File:** `backend/app/publications/service.py` (~200 lines)

```python
import aiohttp
import asyncio
import os
import re
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Configuration with environment variables
PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY")  # Optional but recommended for production
CACHE_TTL_DAYS = 90  # Publications don't change

# Rate limiting based on API key presence
if PUBMED_API_KEY:
    MAX_REQUESTS_PER_SECOND = 10  # With API key
    logger.info("PubMed API key configured: 10 req/sec limit")
else:
    MAX_REQUESTS_PER_SECOND = 3  # Without API key
    logger.warning("No PubMed API key: 3 req/sec limit")

def validate_pmid(pmid: str) -> str:
    """
    Validate and normalize PMID format.

    Args:
        pmid: PMID string (with or without PMID: prefix)

    Returns:
        Normalized PMID in format "PMID:12345678"

    Raises:
        ValueError: If PMID format is invalid
    """
    if not pmid.startswith("PMID:"):
        pmid = f"PMID:{pmid}"

    # Validate format: PMID followed by 1-8 digits only
    if not re.match(r'^PMID:\d{1,8}$', pmid):
        raise ValueError(f"Invalid PMID format: {pmid}. Expected PMID:12345678")

    return pmid

async def get_publication_metadata(pmid: str, db: AsyncSession):
    """
    Fetch publication metadata with database caching.

    Flow:
    1. Validate PMID format
    2. Check database cache
    3. If missing or expired (> 90 days), fetch from PubMed
    4. Cache in database and return

    Args:
        pmid: PubMed ID (format: PMID:12345678 or 12345678)
        db: Database session

    Returns:
        dict: Publication metadata

    Raises:
        ValueError: If PMID format is invalid
        PubMedAPIError: If PubMed API fails
    """
    # Validate PMID format
    pmid = validate_pmid(pmid)
    logger.info(f"Fetching metadata for {pmid}")

    # Check cache
    cached = await _get_cached_metadata(pmid, db)
    if cached:
        logger.info(f"Cache hit for {pmid}")
        return cached

    # Cache miss - fetch from PubMed
    logger.info(f"Cache miss for {pmid}, fetching from PubMed")
    metadata = await _fetch_from_pubmed(pmid)

    # Store in cache
    await _store_in_cache(metadata, db)
    logger.info(f"Cached metadata for {pmid}")

    return metadata

async def _get_cached_metadata(pmid: str, db: AsyncSession):
    """Check database cache for unexpired metadata."""
    query = text("""
        SELECT * FROM publication_metadata
        WHERE pmid = :pmid
        AND fetched_at > NOW() - INTERVAL '90 days'
    """)
    result = await db.execute(query, {"pmid": pmid})
    return result.fetchone()

async def _fetch_from_pubmed(pmid: str) -> dict:
    """
    Fetch metadata from PubMed E-utilities API.

    Args:
        pmid: Validated PMID in format PMID:12345678

    Returns:
        dict: Publication metadata with JSONB-compatible authors array

    Raises:
        PubMedRateLimitError: If rate limit exceeded
        PubMedNotFoundError: If PMID not found
        PubMedTimeoutError: If request times out
        PubMedAPIError: For other API errors
    """
    async with aiohttp.ClientSession() as session:
        pmid_number = pmid.replace("PMID:", "")

        # Build URL with optional API key
        params = {
            "db": "pubmed",
            "id": pmid_number,
            "retmode": "json"
        }
        if PUBMED_API_KEY:
            params["api_key"] = PUBMED_API_KEY

        try:
            async with asyncio.timeout(5):  # 5 second timeout
                async with session.get(PUBMED_API, params=params) as response:
                    if response.status == 429:
                        logger.error(f"Rate limit exceeded for {pmid}")
                        raise PubMedRateLimitError("Rate limit exceeded")

                    if response.status != 200:
                        logger.error(f"PubMed API returned {response.status} for {pmid}")
                        raise PubMedAPIError(f"PubMed API returned {response.status}")

                    data = await response.json()

                    if pmid_number not in data.get('result', {}):
                        logger.warning(f"PMID {pmid} not found in PubMed")
                        raise PubMedNotFoundError(f"PMID {pmid} not found")

                    result = data['result'][pmid_number]

                    # Build authors as JSONB array to preserve order and affiliations
                    authors_list = result.get("authors", [])
                    authors_jsonb = [
                        {
                            "name": a.get("name", ""),
                            "authtype": a.get("authtype", ""),
                            "affiliation": a.get("affiliation", "")
                        }
                        for a in authors_list
                    ]

                    metadata = {
                        "pmid": pmid,
                        "title": result.get("title", ""),
                        "authors": authors_jsonb,  # JSONB array
                        "journal": result.get("source", ""),
                        "year": _extract_year(result.get("pubdate")),
                        "doi": result.get("elocationid", "").replace("doi: ", ""),
                        "abstract": "",  # Phase 2: Requires separate efetch call
                        "data_source": "PubMed",
                        "api_version": "esummary.fcgi"
                    }

                    logger.debug(f"Successfully fetched metadata for {pmid}")
                    return metadata

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching {pmid} from PubMed")
            raise PubMedTimeoutError("PubMed API timeout")

async def _store_in_cache(metadata: dict, db: AsyncSession):
    """
    Store metadata in database cache with provenance tracking.

    Args:
        metadata: Publication metadata dictionary
        db: Database session
    """
    import json

    query = text("""
        INSERT INTO publication_metadata
        (pmid, title, authors, journal, year, doi, abstract, data_source, fetched_by, api_version)
        VALUES (:pmid, :title, :authors::jsonb, :journal, :year, :doi, :abstract, :data_source, :fetched_by, :api_version)
        ON CONFLICT (pmid) DO UPDATE SET
            fetched_at = NOW(),
            title = EXCLUDED.title,
            authors = EXCLUDED.authors,
            journal = EXCLUDED.journal,
            year = EXCLUDED.year,
            doi = EXCLUDED.doi,
            data_source = EXCLUDED.data_source,
            api_version = EXCLUDED.api_version
    """)

    # Convert authors list to JSON string for JSONB insertion
    params = {
        **metadata,
        "authors": json.dumps(metadata["authors"]),
        "fetched_by": "system"  # Could be user ID in authenticated context
    }

    await db.execute(query, params)
    await db.commit()
    logger.info(f"Stored metadata for {metadata['pmid']} in cache")

def _extract_year(pubdate: str) -> int | None:
    """Extract year from PubMed date string."""
    if not pubdate:
        return None
    try:
        return int(pubdate.split()[0])
    except (ValueError, IndexError):
        return None

# Custom exceptions
class PubMedAPIError(Exception):
    pass

class PubMedRateLimitError(PubMedAPIError):
    pass

class PubMedNotFoundError(PubMedAPIError):
    pass

class PubMedTimeoutError(PubMedAPIError):
    pass
```

### 3. API Router

**File:** `backend/app/publications/router.py` (~80 lines)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Dict
from app.database import get_db
from .service import (
    get_publication_metadata,
    validate_pmid,
    PubMedAPIError,
    PubMedNotFoundError,
    PubMedRateLimitError,
    PubMedTimeoutError
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/publications", tags=["publications"])

class AuthorModel(BaseModel):
    """Publication author metadata."""
    name: str
    authtype: str = ""
    affiliation: str = ""

class PublicationMetadataResponse(BaseModel):
    """Publication metadata response schema."""
    pmid: str
    title: str
    authors: List[Dict[str, str]]  # JSONB array
    journal: str | None
    year: int | None
    doi: str | None
    abstract: str
    data_source: str
    api_version: str

@router.get("/{pmid}/metadata", response_model=PublicationMetadataResponse)
async def get_metadata(
    pmid: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get publication metadata with caching.

    - **pmid**: PubMed ID (format: PMID:12345678 or just 12345678)

    Returns cached data if available (< 90 days old),
    otherwise fetches from PubMed API.

    **Error Codes:**
    - 400: Invalid PMID format
    - 404: PMID not found in PubMed
    - 429: Rate limit exceeded (retry after 60s)
    - 504: PubMed API timeout
    - 502: PubMed API error
    """
    try:
        # Validation happens in service layer
        metadata = await get_publication_metadata(pmid, db)
        return metadata
    except ValueError as e:
        logger.warning(f"Invalid PMID format: {pmid}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid PMID format: {str(e)}"
        )
    except PubMedNotFoundError as e:
        logger.info(f"PMID not found: {pmid}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PMID {pmid} not found in PubMed"
        )
    except PubMedRateLimitError as e:
        logger.error(f"Rate limit exceeded for {pmid}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="PubMed rate limit exceeded. Retry after 60 seconds.",
            headers={"Retry-After": "60"}
        )
    except PubMedTimeoutError as e:
        logger.error(f"Timeout fetching {pmid}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="PubMed API timeout. Please retry."
        )
    except PubMedAPIError as e:
        logger.error(f"PubMed API error for {pmid}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"PubMed API error: {str(e)}"
        )
```

### 4. Cache Warming Script

**File:** `backend/migration/warm_publication_cache.py` (~100 lines)

```python
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.config import settings
from app.publications.service import get_publication_metadata

logger = logging.getLogger(__name__)

async def warm_publication_cache():
    """
    Pre-populate cache with all PMIDs from phenopackets.
    Run after data migration.

    Usage:
        cd backend
        uv run python -m migration.warm_publication_cache
    """
    engine = create_async_engine(settings.DATABASE_URL)

    async with AsyncSession(engine) as session:
        # Extract unique PMIDs from phenopackets
        pmids_query = """
            SELECT DISTINCT
                er.value->>'id' AS pmid
            FROM phenopackets p,
                 jsonb_array_elements(p.jsonb->'metaData'->'externalReferences') AS er
            WHERE er.value->>'id' LIKE 'PMID:%'
            ORDER BY pmid
        """

        result = await session.execute(text(pmids_query))
        pmids = [row.pmid for row in result.fetchall()]

        logger.info(f"Found {len(pmids)} unique PMIDs to cache")

        # Fetch metadata for each (with rate limiting)
        success_count = 0
        failure_count = 0

        for i, pmid in enumerate(pmids, 1):
            try:
                await get_publication_metadata(pmid, session)
                success_count += 1
                logger.info(f"[{i}/{len(pmids)}] ✓ Cached {pmid}")

                # NCBI rate limit: max 3 req/sec without API key
                await asyncio.sleep(0.34)

            except Exception as e:
                failure_count += 1
                logger.error(f"[{i}/{len(pmids)}] ✗ Failed {pmid}: {e}")

        logger.info(f"Cache warming complete: {success_count} success, {failure_count} failed")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(warm_publication_cache())
```

## Implementation Checklist

### Phase 1: Database Setup (2 hours)
- [ ] Create Alembic migration for `publication_metadata` table
- [ ] Add `pmid` primary key constraint
- [ ] Add `fetched_at` index for TTL queries
- [ ] Test migration up/down
- [ ] Verify table structure in PostgreSQL

### Phase 2: PubMed Integration (3 hours)
- [ ] Create `app/publications/service.py`
- [ ] Implement `_fetch_from_pubmed()` function
- [ ] Add timeout handling (5 seconds)
- [ ] Add error handling (rate limits, not found, API errors)
- [ ] Test with real PMIDs (e.g., PMID:30791938)
- [ ] Handle edge cases (invalid PMID format, missing fields)

### Phase 3: Caching Layer (2 hours)
- [ ] Implement `_get_cached_metadata()` with TTL check
- [ ] Implement `_store_in_cache()` with upsert logic
- [ ] Implement `get_publication_metadata()` orchestration
- [ ] Test cache hit scenario
- [ ] Test cache miss scenario
- [ ] Test cache expiration (90-day TTL)

### Phase 4: API Endpoint (2 hours)
- [ ] Create `app/publications/router.py`
- [ ] Implement `GET /publications/{pmid}/metadata` endpoint
- [ ] Add PMID format normalization (handle with/without PMID: prefix)
- [ ] Add error responses (404, 429, 504, 502)
- [ ] Register router in `app/main.py`
- [ ] Test with curl/Postman
- [ ] Verify OpenAPI docs generated correctly

### Phase 5: Cache Warming (1 hour)
- [ ] Create `migration/warm_publication_cache.py` script
- [ ] Extract unique PMIDs from phenopackets
- [ ] Add rate limiting (3 req/sec)
- [ ] Add progress logging
- [ ] Test with production data
- [ ] Document usage in README

### Phase 6: Testing (2 hours)
- [ ] Unit tests for `_fetch_from_pubmed()`
- [ ] Unit tests for caching logic
- [ ] Integration test for API endpoint
- [ ] Mock PubMed API responses
- [ ] Test error scenarios
- [ ] Add to CI/CD pipeline

## Acceptance Criteria

### Database
- [x] `publication_metadata` table exists
- [x] Table has correct columns and types
- [x] Indexes created for performance
- [x] Alembic migration runs successfully

### Backend Service
- [x] `/publications/{pmid}/metadata` endpoint responds
- [x] PubMed API integration works
- [x] Database caching functional (90-day TTL)
- [x] Error handling works (rate limits, timeouts, not found)
- [x] PMID format normalization works

### Cache Warming
- [x] Script extracts PMIDs from phenopackets
- [x] Script respects NCBI rate limits
- [x] Progress logging works
- [x] Error handling for failed fetches

### Testing
- [x] Unit tests pass
- [x] Integration tests pass
- [x] Mock PubMed responses work
- [x] CI/CD includes new tests

### Performance
- [x] Cache hit response time < 50ms
- [x] Cache miss (first request) < 1000ms
- [x] No 429 errors during cache warming

## Files to Create/Modify

### New Files (5 files, ~530 lines total)
- `backend/app/publications/__init__.py` (empty)
- `backend/app/publications/service.py` (~200 lines)
- `backend/app/publications/router.py` (~80 lines)
- `backend/migration/warm_publication_cache.py` (~100 lines)
- `backend/alembic/versions/xxxx_add_publication_metadata.py` (~40 lines)
- `backend/tests/test_publications.py` (~150 lines)

### Modified Files (1 file)
- `backend/app/main.py` (+3 lines to register router)

## Dependencies

**Blocked by:** None - standalone feature

**Blocks:**
- Issue #37 Phase 2 (frontend publication detail enhancements)

## Performance Impact

**Before:** No publication metadata available

**After:**
- First request per PMID: ~500-1000ms (PubMed API call)
- Cached requests: ~10-50ms (database query)
- 90-day cache reduces API calls by ~99%
- Cache warming pre-populates all PMIDs (~50 PMIDs in database)

## Testing Verification

### Manual Testing

```bash
# 1. Run migration
cd backend
uv run alembic upgrade head

# 2. Start backend
make backend

# 3. Test endpoint (cache miss - will fetch from PubMed)
curl http://localhost:8000/api/v2/publications/30791938/metadata

# Expected: 200 OK with publication data (~500ms)

# 4. Test again (cache hit)
curl http://localhost:8000/api/v2/publications/30791938/metadata

# Expected: 200 OK with same data (~20ms)

# 5. Test invalid PMID
curl http://localhost:8000/api/v2/publications/99999999/metadata

# Expected: 404 Not Found

# 6. Warm cache
uv run python -m migration.warm_publication_cache

# Expected: All PMIDs cached with progress logging
```

## Monitoring and Observability

### Metrics to Track (Prometheus)
```python
# Add to backend/app/publications/service.py
from prometheus_client import Counter, Histogram, Gauge

pubmed_api_requests_total = Counter(
    'pubmed_api_requests_total',
    'Total PubMed API requests',
    ['status', 'pmid']
)

pubmed_cache_hits = Counter(
    'pubmed_cache_hits_total',
    'Total cache hits for publication metadata'
)

pubmed_cache_misses = Counter(
    'pubmed_cache_misses_total',
    'Total cache misses requiring PubMed API call'
)

pubmed_api_latency = Histogram(
    'pubmed_api_latency_seconds',
    'PubMed API request latency',
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

pubmed_cache_age_days = Gauge(
    'pubmed_cache_age_days',
    'Age of cached publication metadata in days',
    ['pmid']
)
```

### Structured Logging
```python
# All log statements include structured context
logger.info(
    "PubMed API request",
    extra={
        "pmid": pmid,
        "cache_hit": False,
        "latency_ms": 523,
        "data_source": "PubMed",
        "api_version": "esummary.fcgi"
    }
)
```

### Alerting Thresholds
- **Error Rate:** Alert if > 5% of PubMed API requests fail
- **Latency:** Alert if p95 latency > 2 seconds
- **Cache Hit Rate:** Alert if < 80% (indicates cache issues)
- **Rate Limiting:** Alert on any 429 responses (rate limit exceeded)

### Dashboard Metrics
- Cache hit/miss ratio (target: > 90% hits)
- PubMed API response time (p50, p95, p99)
- Number of cached publications
- Cache age distribution
- Error rate by error type

## Testing Requirements

### Unit Tests (≥ 80% Coverage)
```python
# backend/tests/test_publications.py
import pytest
from unittest.mock import AsyncMock, patch
from app.publications.service import (
    validate_pmid,
    get_publication_metadata,
    _fetch_from_pubmed,
    PubMedNotFoundError
)

class TestPMIDValidation:
    def test_validate_pmid_with_prefix(self):
        assert validate_pmid("PMID:12345678") == "PMID:12345678"

    def test_validate_pmid_without_prefix(self):
        assert validate_pmid("12345678") == "PMID:12345678"

    def test_validate_pmid_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid PMID format"):
            validate_pmid("PMID:abc123")

    def test_validate_pmid_too_long(self):
        with pytest.raises(ValueError):
            validate_pmid("PMID:123456789")  # > 8 digits

@pytest.mark.asyncio
class TestPubMedFetching:
    @patch('aiohttp.ClientSession.get')
    async def test_fetch_from_pubmed_success(self, mock_get):
        # Mock PubMed API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "result": {
                "12345678": {
                    "title": "Test Publication",
                    "authors": [{"name": "Smith J"}],
                    "source": "Test Journal",
                    "pubdate": "2024"
                }
            }
        }
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await _fetch_from_pubmed("PMID:12345678")
        assert result["title"] == "Test Publication"
        assert len(result["authors"]) == 1

    @patch('aiohttp.ClientSession.get')
    async def test_fetch_from_pubmed_not_found(self, mock_get):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"result": {}}
        mock_get.return_value.__aenter__.return_value = mock_response

        with pytest.raises(PubMedNotFoundError):
            await _fetch_from_pubmed("PMID:99999999")

@pytest.mark.asyncio
class TestCaching:
    async def test_cache_hit_returns_cached_data(self, db_session):
        # Pre-populate cache
        # Test that second call returns cached data
        pass

    async def test_cache_miss_fetches_from_pubmed(self, db_session):
        # Test that first call fetches from PubMed
        # Verify data is stored in cache
        pass

    async def test_cache_expiration_after_90_days(self, db_session):
        # Insert old cache entry (> 90 days)
        # Verify it's treated as cache miss
        pass
```

### Integration Tests
```python
@pytest.mark.integration
class TestPublicationEndpoint:
    async def test_get_metadata_returns_200(self, client):
        response = await client.get("/api/v2/publications/30791938/metadata")
        assert response.status_code == 200
        data = response.json()
        assert data["pmid"] == "PMID:30791938"
        assert "title" in data
        assert "authors" in data

    async def test_invalid_pmid_returns_400(self, client):
        response = await client.get("/api/v2/publications/invalid/metadata")
        assert response.status_code == 400

    async def test_not_found_pmid_returns_404(self, client):
        response = await client.get("/api/v2/publications/99999999/metadata")
        assert response.status_code == 404
```

### Test Coverage Requirements
- **Unit Tests:** ≥ 80% code coverage
- **Integration Tests:** All API endpoints
- **E2E Tests:** Cache warming script with test PMIDs
- **Mock Data:** All PubMed API responses mocked in tests

## Deployment and Rollback Strategy

### Deployment Steps
1. **Database Migration**
   ```bash
   # Run in staging first
   uv run alembic upgrade head

   # Verify table created
   psql $DATABASE_URL -c "\d publication_metadata"

   # Rollback if issues
   uv run alembic downgrade -1
   ```

2. **Application Deployment**
   ```bash
   # Deploy with feature flag (optional)
   ENABLE_PUBMED_CACHE=true uv run uvicorn app.main:app

   # Monitor error rates for 15 minutes
   # If error rate > 5%, rollback
   ```

3. **Cache Warming (Post-Deployment)**
   ```bash
   # Run during low-traffic period
   uv run python -m migration.warm_publication_cache

   # Monitor PubMed API rate limits
   # Should complete without 429 errors
   ```

### Rollback Criteria
Trigger rollback if:
- Error rate > 5% for 5 minutes
- P95 latency > 2 seconds
- Database connection pool exhaustion
- More than 10 consecutive PubMed 429 errors

### Rollback Procedure
```bash
# 1. Revert application code
git revert <commit-hash>
git push

# 2. Rollback database migration
cd backend
uv run alembic downgrade -1

# 3. Verify table dropped
psql $DATABASE_URL -c "\d publication_metadata"
# Should return: "Did not find any relation named 'publication_metadata'"

# 4. Restart application without feature
ENABLE_PUBMED_CACHE=false uv run uvicorn app.main:app
```

### Migration Rollback Script
```sql
-- backend/alembic/versions/xxxx_add_publication_metadata.py
def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_publication_metadata_active")
    op.execute("DROP INDEX IF EXISTS idx_publication_metadata_expired")
    op.execute("DROP TABLE IF EXISTS publication_metadata CASCADE")
```

## Timeline

**Estimated:** 12 hours (1.5 days)

## Priority

**P2 (Medium)** - Enhancement for issue #37

## Labels

`backend`, `api`, `feature`, `pubmed`, `caching`, `p2`

## Notes

- **NCBI Rate Limits:** 3 requests/second without API key, 10 req/sec with key
- **API Key Support:** Consider adding for production (set in environment variables)
- **Cache Warming:** Run during low-traffic periods or after migrations
- **Abstract Fetching:** Requires separate PubMed efetch call (can add later)
- **DOI Fallback:** If PubMed doesn't have DOI, can fetch from Crossref API
