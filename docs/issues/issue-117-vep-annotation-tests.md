# Issue #117: test(backend): add comprehensive tests for VEP annotation system

## Overview

Add comprehensive unit and integration tests for the VEP (Variant Effect Predictor) annotation system implemented in #100. This ensures reliability, proper rate limiting, error handling, and maintainability of the variant annotation functionality.

**Problem**: The VEP annotation system (`backend/app/api/variant_validator.py`) currently has no automated tests, making it difficult to verify correctness, catch regressions, or refactor safely.

**Solution**: Implement a complete test suite covering unit tests (individual function behavior) and integration tests (end-to-end API workflows).

## Why This Matters

**Current State**:
```python
# backend/app/api/variant_validator.py - No tests
class VariantValidator:
    async def annotate_with_vep(self, variant: str) -> dict:
        # Complex logic:
        # - Format detection (VCF vs HGVS)
        # - Rate limiting (15 req/sec)
        # - Caching (Redis)
        # - Error handling (retries, timeouts)
        # - Data extraction (CADD, gnomAD)
        # NO AUTOMATED VERIFICATION ❌
```

**Target State**:
```python
# tests/test_variant_validator_enhanced.py
class TestVariantValidator:
    async def test_annotate_vcf_format(self):
        """Test VCF format annotation with CADD and gnomAD"""
        result = await validator.annotate_with_vep("17:41234470:T:A")
        assert result["cadd_phred"] == 28.5
        assert result["gnomad_af"] == 0.0001
        # ✅ VERIFIED AUTOMATICALLY

    async def test_rate_limiting_enforced(self):
        """Test 15 req/sec rate limit"""
        start = time.time()
        await asyncio.gather(*[
            validator.annotate_with_vep(f"17:41234{i}:T:A")
            for i in range(20)
        ])
        duration = time.time() - start
        assert duration >= 1.0  # 20 requests > 15/sec limit
        # ✅ RATE LIMITING VERIFIED
```

**Benefits**:
1. **Catch bugs early**: Detect issues before production
2. **Safe refactoring**: Modify code without breaking functionality
3. **Documentation**: Tests serve as executable examples
4. **CI/CD integration**: Automated verification on every commit
5. **Code quality**: Forces modular, testable design

## Required Changes

### 1. Unit Tests for VariantValidator Class

**File**: `backend/tests/test_variant_validator_enhanced.py`

**Test Cases** (~12 tests):

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.api.variant_validator import VariantValidator

class TestVariantValidator:
    """Unit tests for VEP annotation system"""

    @pytest.fixture
    def validator(self):
        """Create VariantValidator instance with mocked dependencies"""
        with patch('app.api.variant_validator.aiohttp.ClientSession'):
            return VariantValidator()

    # Format Detection Tests (2 tests)
    async def test_detect_vcf_format(self, validator):
        """Test VCF format detection: chr:pos:ref:alt"""
        assert validator._is_vcf_format("17:41234470:T:A") is True
        assert validator._is_vcf_format("chr17:41234470:T:A") is True

    async def test_detect_hgvs_format(self, validator):
        """Test HGVS format detection: gene transcript"""
        assert validator._is_hgvs_format("ENST00000357654:c.123A>G") is True
        assert validator._is_hgvs_format("NM_000546.5:c.215C>G") is True

    # Annotation Tests (3 tests)
    @patch('app.api.variant_validator.aiohttp.ClientSession.post')
    async def test_annotate_vcf_with_cadd_gnomad(self, mock_post, validator):
        """Test successful VCF annotation with CADD and gnomAD scores"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[{
            "id": "17:41234470:T:A",
            "transcript_consequences": [{
                "cadd_phred": 28.5,
                "frequencies": {"gnomAD": {"gnomad_af": 0.0001}}
            }]
        }])
        mock_post.return_value.__aenter__.return_value = mock_response

        result = await validator.annotate_with_vep("17:41234470:T:A")

        assert result["cadd_phred"] == 28.5
        assert result["gnomad_af"] == 0.0001
        assert result["vep_version"] is not None

    @patch('app.api.variant_validator.aiohttp.ClientSession.post')
    async def test_annotate_hgvs_format(self, mock_post, validator):
        """Test HGVS format annotation"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[{
            "id": "ENST00000357654:c.123A>G",
            "most_severe_consequence": "missense_variant"
        }])
        mock_post.return_value.__aenter__.return_value = mock_response

        result = await validator.annotate_with_vep("ENST00000357654:c.123A>G")
        assert result["most_severe_consequence"] == "missense_variant"

    async def test_extract_cadd_score_missing(self, validator):
        """Test CADD score extraction when missing"""
        vep_data = [{"transcript_consequences": [{}]}]
        result = validator._extract_cadd_score(vep_data)
        assert result is None

    # Rate Limiting Tests (2 tests)
    @patch('app.api.variant_validator.aiohttp.ClientSession.post')
    async def test_rate_limiting_enforced(self, mock_post, validator):
        """Test rate limiter enforces 15 req/sec"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[{"id": "test"}])
        mock_post.return_value.__aenter__.return_value = mock_response

        start = time.time()
        await asyncio.gather(*[
            validator.annotate_with_vep(f"17:4123447{i}:T:A")
            for i in range(20)
        ])
        duration = time.time() - start

        # 20 requests at 15/sec should take ~1.33 seconds
        assert duration >= 1.0

    async def test_rate_limiter_allows_burst(self, validator):
        """Test rate limiter allows immediate burst up to limit"""
        # First 15 requests should complete immediately
        start = time.time()
        await asyncio.gather(*[
            validator.annotate_with_vep(f"17:4123447{i}:T:A")
            for i in range(15)
        ])
        duration = time.time() - start
        assert duration < 0.5  # Should be nearly instant

    # Cache Tests (2 tests)
    @patch('app.api.variant_validator.redis.Redis')
    async def test_cache_hit_skips_api_call(self, mock_redis, validator):
        """Test cache hit returns cached data without API call"""
        cached_data = {"cadd_phred": 25.0, "gnomad_af": 0.0002}
        mock_redis.get.return_value = json.dumps(cached_data)

        with patch('app.api.variant_validator.aiohttp.ClientSession.post') as mock_post:
            result = await validator.annotate_with_vep("17:41234470:T:A")

            # Should return cached data
            assert result == cached_data
            # Should NOT call API
            mock_post.assert_not_called()

    @patch('app.api.variant_validator.redis.Redis')
    async def test_cache_miss_calls_api_and_caches(self, mock_redis, validator):
        """Test cache miss triggers API call and stores result"""
        mock_redis.get.return_value = None  # Cache miss
        api_response = {"cadd_phred": 28.5}

        with patch('app.api.variant_validator.aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=[api_response])
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await validator.annotate_with_vep("17:41234470:T:A")

            # Should call API
            mock_post.assert_called_once()
            # Should cache result
            mock_redis.set.assert_called_once()
            assert result["cadd_phred"] == 28.5

    # Error Handling Tests (3 tests)
    @patch('app.api.variant_validator.aiohttp.ClientSession.post')
    async def test_invalid_variant_format_error(self, mock_post, validator):
        """Test error handling for invalid variant format"""
        with pytest.raises(ValueError, match="Invalid variant format"):
            await validator.annotate_with_vep("invalid-variant-format")

    @patch('app.api.variant_validator.aiohttp.ClientSession.post')
    async def test_vep_api_timeout_error(self, mock_post, validator):
        """Test error handling for VEP API timeout"""
        mock_post.side_effect = asyncio.TimeoutError()

        with pytest.raises(TimeoutError, match="VEP API request timed out"):
            await validator.annotate_with_vep("17:41234470:T:A")

    @patch('app.api.variant_validator.aiohttp.ClientSession.post')
    async def test_vep_api_429_rate_limit_error(self, mock_post, validator):
        """Test error handling for VEP API 429 (too many requests)"""
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.text = AsyncMock(return_value="Rate limit exceeded")
        mock_post.return_value.__aenter__.return_value = mock_response

        with pytest.raises(Exception, match="Rate limit exceeded"):
            await validator.annotate_with_vep("17:41234470:T:A")
```

### 2. Integration Tests for API Endpoints

**File**: `backend/tests/test_variant_api_integration.py`

**Test Cases** (~6 tests):

```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
class TestVariantAnnotationAPI:
    """Integration tests for /api/v2/variants/annotate endpoint"""

    @pytest.fixture
    async def client(self):
        """Create test client"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    async def test_annotate_endpoint_vcf_format(self, client):
        """Test /api/v2/variants/annotate with VCF format"""
        response = await client.post(
            "/api/v2/variants/annotate",
            json={"variant": "17:41234470:T:A"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "cadd_phred" in data
        assert "gnomad_af" in data

    async def test_annotate_endpoint_hgvs_format(self, client):
        """Test /api/v2/variants/annotate with HGVS format"""
        response = await client.post(
            "/api/v2/variants/annotate",
            json={"variant": "ENST00000357654:c.123A>G"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "most_severe_consequence" in data

    async def test_annotate_endpoint_invalid_variant(self, client):
        """Test error handling for invalid variant"""
        response = await client.post(
            "/api/v2/variants/annotate",
            json={"variant": "invalid"}
        )
        assert response.status_code == 400
        assert "Invalid variant format" in response.json()["detail"]

    async def test_annotate_endpoint_concurrent_requests(self, client):
        """Test handling of concurrent annotation requests"""
        variants = [f"17:4123447{i}:T:A" for i in range(10)]

        tasks = [
            client.post("/api/v2/variants/annotate", json={"variant": v})
            for v in variants
        ]
        responses = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

    async def test_annotate_endpoint_requires_auth(self, client):
        """Test endpoint requires authentication"""
        # Remove auth header
        response = await client.post(
            "/api/v2/variants/annotate",
            json={"variant": "17:41234470:T:A"},
            headers={}  # No auth token
        )
        assert response.status_code == 401

    async def test_annotate_batch_endpoint(self, client):
        """Test /api/v2/variants/annotate-batch for multiple variants"""
        response = await client.post(
            "/api/v2/variants/annotate-batch",
            json={
                "variants": [
                    "17:41234470:T:A",
                    "17:41234471:G:C",
                    "17:41234472:A:T"
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 3
        assert all("cadd_phred" in r for r in data["results"])
```

### 3. Migration Script Tests

**File**: `backend/tests/test_vep_migration.py`

**Test Cases** (~3 tests):

```python
import pytest
from unittest.mock import patch, AsyncMock
from migration.enrich_variants_vep import enrich_variants_with_vep

class TestVEPMigration:
    """Tests for VEP enrichment migration script"""

    @pytest.mark.asyncio
    @patch('migration.enrich_variants_vep.VariantValidator')
    async def test_enrich_variants_updates_phenopackets(self, mock_validator):
        """Test migration enriches existing variants"""
        mock_validator.annotate_with_vep = AsyncMock(return_value={
            "cadd_phred": 28.5,
            "gnomad_af": 0.0001
        })

        # Run migration (limited to 10 phenopackets)
        stats = await enrich_variants_with_vep(limit=10)

        assert stats["phenopackets_processed"] == 10
        assert stats["variants_enriched"] > 0
        assert stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_enrich_variants_skips_already_enriched(self):
        """Test migration skips variants with existing CADD scores"""
        # Create phenopacket with already-enriched variant
        # Run migration
        # Verify variant not re-annotated
        pass

    @pytest.mark.asyncio
    @patch('migration.enrich_variants_vep.VariantValidator')
    async def test_enrich_variants_handles_errors_gracefully(self, mock_validator):
        """Test migration continues after annotation errors"""
        mock_validator.annotate_with_vep = AsyncMock(
            side_effect=[
                {"cadd_phred": 25.0},  # Success
                Exception("VEP API error"),  # Failure
                {"cadd_phred": 30.0},  # Success after error
            ]
        )

        stats = await enrich_variants_with_vep(limit=3)

        assert stats["variants_enriched"] == 2  # 2 successes
        assert stats["errors"] == 1  # 1 failure
```

### 4. Test Configuration

**File**: `backend/pytest.ini`

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Coverage settings
addopts =
    --cov=app/api/variant_validator
    --cov=migration
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=90
    -v

# Test markers
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (slower, requires services)
    slow: Slow tests (>1 second)
```

**File**: `backend/.coveragerc`

```ini
[run]
source = app/api,migration
omit =
    */tests/*
    */venv/*
    */__pycache__/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
```

### 5. CI/CD Integration

**File**: `.github/workflows/ci.yml` (add VEP tests section)

```yaml
jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: |
          cd backend
          uv sync --group dev --group test

      - name: Start Redis (for cache tests)
        run: docker run -d -p 6379:6379 redis:7-alpine

      - name: Run VEP annotation tests
        run: |
          cd backend
          uv run pytest tests/test_variant_validator_enhanced.py \
                       tests/test_variant_api_integration.py \
                       tests/test_vep_migration.py \
                       --cov=app/api/variant_validator \
                       --cov-report=xml \
                       --cov-fail-under=90

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./backend/coverage.xml
          flags: backend-vep-tests
```

## Implementation Checklist

### Phase 1: Unit Test Foundation (1 hour)
- [ ] Create `backend/tests/test_variant_validator_enhanced.py`
- [ ] Implement format detection tests (2 tests)
- [ ] Implement basic annotation tests (2 tests)
- [ ] Add pytest fixtures for mocked dependencies
- [ ] Verify tests run: `pytest tests/test_variant_validator_enhanced.py -v`

### Phase 2: Rate Limiting & Cache Tests (45 minutes)
- [ ] Implement rate limiting tests (2 tests)
- [ ] Implement cache hit/miss tests (2 tests)
- [ ] Add Redis mock fixtures
- [ ] Test concurrent request handling

### Phase 3: Error Handling Tests (30 minutes)
- [ ] Implement invalid format error test
- [ ] Implement timeout error test
- [ ] Implement 429 rate limit error test
- [ ] Verify all error paths covered

### Phase 4: Integration Tests (45 minutes)
- [ ] Create `backend/tests/test_variant_api_integration.py`
- [ ] Implement API endpoint tests (4 tests)
- [ ] Test authentication requirements
- [ ] Test batch annotation endpoint

### Phase 5: Migration & CI/CD (30 minutes)
- [ ] Create `backend/tests/test_vep_migration.py`
- [ ] Implement migration script tests (3 tests)
- [ ] Update `pytest.ini` and `.coveragerc`
- [ ] Add VEP tests to GitHub Actions workflow
- [ ] Verify CI/CD pipeline passes

## Testing Verification

### Manual Test Steps

**1. Run Unit Tests:**
```bash
cd backend
uv run pytest tests/test_variant_validator_enhanced.py -v
```

**Expected Output:**
```
test_detect_vcf_format PASSED
test_detect_hgvs_format PASSED
test_annotate_vcf_with_cadd_gnomad PASSED
test_annotate_hgvs_format PASSED
test_extract_cadd_score_missing PASSED
test_rate_limiting_enforced PASSED
test_rate_limiter_allows_burst PASSED
test_cache_hit_skips_api_call PASSED
test_cache_miss_calls_api_and_caches PASSED
test_invalid_variant_format_error PASSED
test_vep_api_timeout_error PASSED
test_vep_api_429_rate_limit_error PASSED

======================== 12 passed in 2.45s ========================
```

**2. Run Integration Tests:**
```bash
uv run pytest tests/test_variant_api_integration.py -v
```

**Expected Output:**
```
test_annotate_endpoint_vcf_format PASSED
test_annotate_endpoint_hgvs_format PASSED
test_annotate_endpoint_invalid_variant PASSED
test_annotate_endpoint_concurrent_requests PASSED
test_annotate_endpoint_requires_auth PASSED
test_annotate_batch_endpoint PASSED

======================== 6 passed in 3.12s ========================
```

**3. Check Coverage:**
```bash
uv run pytest tests/test_variant_validator_enhanced.py \
             tests/test_variant_api_integration.py \
             --cov=app/api/variant_validator \
             --cov-report=term-missing
```

**Expected Output:**
```
Name                                    Stmts   Miss  Cover   Missing
---------------------------------------------------------------------
app/api/variant_validator.py             156      8    95%   45-47, 89
---------------------------------------------------------------------
TOTAL                                     156      8    95%

======================== Coverage: 95% ========================
```

**4. Run All Quality Checks:**
```bash
cd backend
make check  # Runs lint + typecheck + all tests
```

**Expected Output:**
```
✅ Linting passed (ruff)
✅ Type checking passed (mypy)
✅ All tests passed (pytest)
✅ Coverage ≥90%
```

## Acceptance Criteria

- [ ] **Test Coverage**: ≥90% line coverage for `variant_validator.py`
- [ ] **Unit Tests**: All 12 unit tests pass
- [ ] **Integration Tests**: All 6 integration tests pass
- [ ] **Migration Tests**: All 3 migration tests pass
- [ ] **CI/CD Integration**: Tests run automatically on GitHub Actions
- [ ] **Performance**: Test suite completes in <2 minutes
- [ ] **Mocking**: Tests use mocks (don't spam Ensembl VEP API)
- [ ] **Documentation**: Test docstrings explain what each test verifies
- [ ] **Error Handling**: All error paths tested
- [ ] **No Regressions**: Existing tests still pass

## Files Modified/Created

### New Files (3 files, ~600 lines total)
1. `backend/tests/test_variant_validator_enhanced.py` (~350 lines)
   - 12 unit tests for VariantValidator class
   - Fixtures for mocked dependencies
   - Test helpers for VEP response mocking

2. `backend/tests/test_variant_api_integration.py` (~150 lines)
   - 6 integration tests for API endpoints
   - Test client setup
   - Authentication helpers

3. `backend/tests/test_vep_migration.py` (~100 lines)
   - 3 migration script tests
   - Database fixtures
   - Migration statistics validation

### Modified Files (2 files)
4. `backend/pytest.ini` (~15 lines added)
   - Coverage configuration
   - Test markers for unit/integration separation

5. `.github/workflows/ci.yml` (~25 lines added)
   - VEP test job
   - Coverage reporting

## Dependencies

**Blocks**:
- None (tests can be written independently)

**Blocked By**:
- ✅ #100 - VEP annotation implementation (COMPLETED)

**Related**:
- #56 - Original VEP integration issue
- See `docs/variant-annotation-implementation-plan.md`

## Performance Impact

**Before** (No Tests):
- Manual testing: ~30 minutes per deployment
- Regression risk: HIGH (no automated verification)
- Refactoring confidence: LOW

**After** (Automated Tests):
- Automated testing: <2 minutes per commit
- Regression risk: LOW (90%+ coverage)
- Refactoring confidence: HIGH
- CI/CD cost: +2 minutes per pipeline run (acceptable)

## Timeline

**Estimated Effort**: 2-3 hours

**Breakdown**:
- Phase 1 (Unit tests foundation): 1 hour
- Phase 2 (Rate limiting & cache): 45 minutes
- Phase 3 (Error handling): 30 minutes
- Phase 4 (Integration tests): 45 minutes
- Phase 5 (Migration & CI/CD): 30 minutes

**Total**: ~3 hours for comprehensive test coverage

## Priority & Labels

**Priority**: **P1 (High)** - Testing is critical for production readiness

**Rationale**:
- VEP annotation is a core feature (#100)
- No tests = high risk of regressions
- Required for safe refactoring/maintenance
- Blocks production deployment

**Labels**:
- `test` - Adding test coverage
- `backend` - Backend Python tests
- `ci/cd` - CI/CD integration
- `quality` - Code quality improvement
- `p1-high` - High priority
