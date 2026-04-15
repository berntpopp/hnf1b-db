# Issue #119: epic: Complete variant annotation system with VEP integration

## Overview

This epic tracks the complete implementation of a variant annotation system using Ensembl VEP (Variant Effect Predictor). The system provides comprehensive variant analysis including functional consequence predictions, pathogenicity scores, and population frequencies to support clinical variant interpretation.

**Problem**: Users cannot assess the functional impact of genetic variants within the HNF1B database. Without annotation, variants are just genomic coordinates with no context about their potential pathogenicity or clinical significance.

**Solution**: Integrate Ensembl VEP to provide real-time variant annotation with:
- Consequence predictions (missense, nonsense, splice site, etc.)
- Pathogenicity scores (CADD, PolyPhen-2, SIFT)
- Population frequencies (gnomAD)
- Support for multiple input formats (VCF, HGVS)
- User-friendly web interface

---

## **Update**: Scope adjustment for focused backend implementation

Issue #116 (frontend UI component) has been **moved to future CRUD system milestone**.

The current "Variant annotation" milestone now focuses on:

### Backend-Only Implementation (4-5 hours)

✅ **Phase 1: Core Backend** (3.5 hours)
- #56 - Fix ga4gh.vrs installation (5 min) ✅ COMPLETED
- #100 - Add VEP annotation pipeline (2-3 hours) ✅ COMPLETED
- #117 - Add comprehensive tests (2-3 hours) ⏳ PENDING

✅ **Phase 2: Documentation** (1-1.5 hours)
- #118 - Document API and user guide ⏳ PENDING

### Deferred to CRUD System
- #116 - Add variant annotation UI component (for later)

**Total Effort**: 4-5 hours (down from 6-8 hours)

**Rationale**: Focus on backend API foundation first. Frontend UI will be added when CRUD system is implemented, providing consistent data management across the application.

**API Availability**: The `/api/v2/variants/annotate` endpoint will be available for testing and integration once #100 is complete.

---

## Why This Matters

**Current State**:
```python
# backend/app/models.py - Variants stored without annotations
{
  "id": "var-123",
  "vcf_record": {
    "chr": "17",
    "pos": 36459258,
    "ref": "A",
    "alt": "G"
  }
  # ❌ No consequence prediction
  # ❌ No pathogenicity score
  # ❌ No population frequency
  # ❌ No clinical interpretation guidance
}
```

**Target State**:
```python
# Enriched variant with VEP annotations
{
  "id": "var-123",
  "vcf_record": {
    "chr": "17",
    "pos": 36459258,
    "ref": "A",
    "alt": "G"
  },
  "vep_annotation": {
    "consequence": "missense_variant",
    "impact": "MODERATE",
    "gene_symbol": "HNF1B",
    "cadd_phred": 25.4,        # ✅ Pathogenicity score
    "gnomad_af": 0.00001,      # ✅ Population frequency
    "polyphen": "probably_damaging",
    "sift": "deleterious"
  }
  # ✅ Users can assess clinical significance
  # ✅ Supports ACMG variant classification
}
```

**Benefits**:
1. **Clinical Decision Support**: Pathogenicity scores guide variant interpretation
2. **Research Efficiency**: Automated annotation vs. manual literature review
3. **Standardization**: Consistent VEP predictions across all variants
4. **Data Enrichment**: Enhances existing variant records in database
5. **User Experience**: Real-time annotation via web interface

## Goals

### Functional Goals
- ✅ **Variant Validation**: Real-time format validation with helpful error messages
- ✅ **Consequence Prediction**: Annotate variants with functional impact (missense, nonsense, splice site, etc.)
- ✅ **Pathogenicity Scoring**: Provide CADD scores to assess deleteriousness
- ✅ **Population Frequencies**: Include gnomAD allele frequencies for rarity assessment
- ✅ **Format Support**: Accept both VCF (genomic coordinates) and HGVS (transcript-based) formats
- ✅ **User Interface**: Intuitive web UI for variant input and results visualization

### Technical Goals
- ✅ **Performance**: <3 second response time for annotations
- ✅ **Reliability**: Rate limiting to prevent Ensembl API throttling
- ✅ **Caching**: 24-hour Redis cache to reduce API calls
- ✅ **Testing**: ≥90% code coverage for variant annotation components
- ✅ **Documentation**: Comprehensive API docs and user guide

### Quality Goals
- ✅ **Error Handling**: Graceful degradation when VEP API unavailable
- ✅ **Validation**: Input validation prevents invalid API requests
- ✅ **Monitoring**: Cache hit rate and API latency tracking
- ✅ **Maintainability**: Modular code with clear separation of concerns

## Implementation Issues

### Phase 1: Backend Infrastructure (3.5 hours)

#### Issue #56: Fix ga4gh.vrs installation
**Status**: ✅ **COMPLETED**
**Effort**: 5 minutes
**Priority**: P0 (Blocker)

**Description**: Install `ga4gh.vrs` library to enable VRS-compliant variant representation

**Deliverables**:
- [x] `ga4gh.vrs` added to `pyproject.toml`
- [x] VRS digest computation working
- [x] Tests verify VRS variant identifiers

**Blocks**: #100 (VEP annotation depends on VRS library)

---

#### Issue #100: Add VEP annotation pipeline
**Status**: ✅ **COMPLETED**
**Effort**: 2-3 hours
**Priority**: P1 (High)

**Description**: Implement backend API endpoint to annotate variants using Ensembl VEP REST API

**Deliverables**:
- [x] `POST /api/v2/variants/annotate` endpoint
- [x] Format detection (VCF vs HGVS)
- [x] VEP API integration with async HTTP client
- [x] CADD score and gnomAD frequency extraction
- [x] Rate limiting (15 req/sec token bucket)
- [x] Redis caching (24-hour TTL)
- [x] Error handling (invalid format, timeout, 429 rate limit)

**Technical Details**:
- File: `backend/app/api/variant_validator.py` (~300 lines)
- Dependencies: `aiohttp`, `redis`, `asyncio`
- External API: Ensembl VEP REST API v112

**Acceptance Criteria**:
- [x] VCF format annotated successfully
- [x] HGVS format annotated successfully
- [x] CADD score extracted from response
- [x] gnomAD frequency extracted from response
- [x] Rate limiter enforces 15 req/sec
- [x] Cache reduces API calls

**Related**:
- Implementation Plan: `docs/variant-annotation-implementation-plan.md`
- Blocked By: #56 (VRS installation)

---

#### Issue #117: Add comprehensive tests for VEP annotation
**Status**: ⏳ **PENDING**
**Effort**: 2-3 hours
**Priority**: P1 (High)

**Description**: Create unit and integration tests for VEP annotation system to ensure reliability and prevent regressions

**Deliverables**:
- [ ] Unit tests for `VariantValidator` class (12 tests)
  - Format detection (VCF, HGVS)
  - Annotation success cases
  - CADD/gnomAD extraction
  - Rate limiting enforcement
  - Cache hit/miss scenarios
  - Error handling (invalid format, timeout, 429)
- [ ] Integration tests for API endpoints (6 tests)
  - `/api/v2/variants/annotate` for VCF/HGVS
  - Concurrent request handling
  - Authentication requirements
  - Batch annotation endpoint
- [ ] Migration script tests (3 tests)
  - Variant enrichment workflow
  - Error handling during migration
  - Skip already-enriched variants
- [ ] CI/CD integration (GitHub Actions)
- [ ] ≥90% code coverage

**Technical Details**:
- Files:
  - `backend/tests/test_variant_validator_enhanced.py` (~350 lines)
  - `backend/tests/test_variant_api_integration.py` (~150 lines)
  - `backend/tests/test_vep_migration.py` (~100 lines)
- Tools: pytest, pytest-asyncio, pytest-cov, AsyncMock

**Acceptance Criteria**:
- [ ] All 21 tests pass
- [ ] Coverage ≥90% for `variant_validator.py`
- [ ] Tests complete in <2 minutes
- [ ] Proper mocking (no live Ensembl API calls)
- [ ] CI/CD pipeline runs tests on every commit

**Related**:
- Implementation: #100 (VEP annotation API)
- Documentation: `docs/issues/issue-117-vep-annotation-tests.md`
- Blocked By: #100 (needs implementation to test)

---

### Phase 2: Documentation (1-1.5 hours)

#### Issue #118: Document VEP annotation API and user guide
**Status**: ⏳ **PENDING**
**Effort**: 1-1.5 hours
**Priority**: P2 (Medium)

**Description**: Create comprehensive documentation for variant annotation system covering API reference, user guide, and developer documentation

**Deliverables**:
- [ ] **API Reference** (`docs/api/variant-annotation.md`, ~250 lines)
  - Endpoint specification: `POST /api/v2/variants/annotate`
  - Request/response formats with examples
  - Error codes and handling
  - Scoring interpretation (CADD, gnomAD, PolyPhen, SIFT)
  - Rate limiting guidance
  - Consequence glossary

- [ ] **User Guide** (`docs/user-guide/variant-annotation.md`, ~200 lines)
  - How to use the variant annotation API
  - Supported formats (VCF vs HGVS) with examples
  - Understanding annotation results
  - Example workflows (clinical assessment, literature validation, batch)
  - Troubleshooting common issues

- [ ] **Developer Guide** (update `docs/variant-annotation-implementation-plan.md`)
  - Architecture overview with data flow diagram
  - Testing approach
  - Deployment considerations

- [ ] **OpenAPI/Swagger** (update `backend/app/api/variants.py`)
  - Pydantic model docstrings
  - Auto-generated docs at `/docs`

- [ ] **README Updates**
  - Add variant annotation to features list
  - Link to documentation

**Acceptance Criteria**:
- [ ] API documentation complete with curl examples
- [ ] User guide with format examples
- [ ] Developer guide updated
- [ ] Swagger UI shows variant annotation endpoint
- [ ] All curl examples tested and working
- [ ] No broken links in documentation

**Related**:
- API: #100 (documents this implementation)
- Tests: #117 (references test coverage)
- Documentation: `docs/issues/issue-118-vep-documentation.md`
- Blocked By: #100 (API must exist to document)

---

## Dependency Graph

```
#56 (VRS installation) ✅ COMPLETED
  │
  ├─→ #100 (VEP annotation API) ✅ COMPLETED
  │     │
  │     ├─→ #117 (Tests) ⏳ PENDING
  │     │
  │     └─→ #118 (Documentation) ⏳ PENDING
  │
  └─→ #116 (Frontend UI) 📦 DEFERRED TO CRUD SYSTEM
```

**Critical Path**:
1. ✅ #56 → ✅ #100 → ⏳ #117 (Tests)
2. ✅ #56 → ✅ #100 → ⏳ #118 (Documentation)

**Parallel Work**:
- #117 (Tests) and #118 (Documentation) can be done in parallel after #100
- #116 (Frontend UI) deferred to future CRUD system milestone

## Total Effort Estimate

| Phase | Issue | Effort | Status |
|-------|-------|--------|--------|
| **Phase 1: Backend** | | | |
| | #56 - VRS installation | 5 min | ✅ Complete |
| | #100 - VEP annotation API | 2-3 hours | ✅ Complete |
| | #117 - Comprehensive tests | 2-3 hours | ⏳ Pending |
| **Phase 2: Documentation** | | | |
| | #118 - API & user guide | 1-1.5 hours | ⏳ Pending |
| **Deferred** | | | |
| | #116 - Variant annotator UI | 1.5-2 hours | 📦 Deferred |
| **Total (Current Milestone)** | | **4-5 hours** | **50% Complete** |

**Completed**: 2.5 hours (50%)
**Remaining**: 3.5-4.5 hours (50%)
**Deferred**: 1.5-2 hours (moved to CRUD system)

## Success Criteria

### Backend Functionality
- [x] ✅ VEP annotations working for VCF format
- [x] ✅ VEP annotations working for HGVS format
- [x] ✅ CADD scores extracted and returned
- [x] ✅ gnomAD frequencies extracted and returned
- [x] ✅ Rate limiting enforced (15 req/sec)
- [x] ✅ Caching reduces API calls (Redis 24h TTL)
- [ ] ⏳ Test coverage ≥90%
- [ ] ⏳ Error handling tested (invalid format, timeout, 429)

### Documentation Completeness
- [ ] ⏳ API endpoint documented with examples
- [ ] ⏳ User guide with format examples
- [ ] ⏳ Developer architecture guide
- [ ] ⏳ Swagger UI accessible at `/docs`
- [ ] ⏳ All code examples tested

### Integration & Quality
- [x] ✅ API endpoint returns valid JSON
- [ ] ⏳ CI/CD pipeline includes VEP tests
- [ ] ⏳ All documentation links work
- [ ] ⏳ API accessible via curl/Postman for testing

## Technical Details

### API Specification

**Endpoint**: `POST /api/v2/variants/annotate`

**Authentication**: Required (JWT bearer token)

**Request**:
```json
{
  "variant": "17:36459258:A:G"  // VCF format
}
```
or
```json
{
  "variant": "NM_000458.4:c.544+1G>A"  // HGVS format
}
```

**Response**:
```json
{
  "input": "17:36459258:A:G",
  "assembly_name": "GRCh38",
  "most_severe_consequence": "missense_variant",
  "transcript_consequences": [
    {
      "transcript_id": "ENST00000269305",
      "gene_symbol": "HNF1B",
      "consequence_terms": ["missense_variant"],
      "impact": "MODERATE",
      "cadd_phred": 25.4,
      "cadd_raw": 3.876,
      "polyphen_prediction": "probably_damaging",
      "polyphen_score": 0.95,
      "sift_prediction": "deleterious",
      "sift_score": 0.01
    }
  ],
  "colocated_variants": [
    {
      "id": "rs123456",
      "frequencies": {
        "gnomAD": {
          "gnomad_af": 0.00001,
          "gnomad_nfe_af": 0.00002
        }
      }
    }
  ],
  "vep_version": "112",
  "cache_timestamp": "2025-01-14T10:30:00Z"
}
```

### Supported Formats

**1. VCF Format** (Genomic Coordinates):
- Pattern: `chr:pos:ref:alt` or `chr-pos-ref-alt`
- Examples:
  - `17:36459258:A:G`
  - `chr17:36459258:A:G`
  - `X:123456:G:C`
  - `17-36459258-ATCG-A` (deletion)

**2. HGVS Format** (Transcript-based):
- Pattern: `transcript:c.change` or `transcript:p.change`
- Examples:
  - `ENST00000269305:c.544+1G>A` (splice site)
  - `NM_000458.4:c.123A>G` (coding)
  - `ENST00000269305:p.Arg248Trp` (protein)

### Response Fields

**Key Fields**:
- `most_severe_consequence` - Worst predicted effect (e.g., `missense_variant`)
- `impact` - Severity: `HIGH`, `MODERATE`, `LOW`, `MODIFIER`
- `cadd_phred` - Pathogenicity score (0-99, higher = more deleterious)
- `gnomad_af` - Population allele frequency (0-1)
- `polyphen_prediction` - `benign`, `possibly_damaging`, `probably_damaging`
- `sift_prediction` - `tolerated`, `deleterious`

**Score Interpretation**:

| Score | Threshold | Interpretation |
|-------|-----------|----------------|
| CADD | >20 | Top 1% most deleterious (likely pathogenic) |
| CADD | >30 | Top 0.1% most deleterious (very likely pathogenic) |
| gnomAD AF | <0.01% | Very rare (supports pathogenicity) |
| gnomAD AF | >5% | Common (likely benign) |
| PolyPhen | >0.909 | Probably damaging |
| SIFT | <0.05 | Deleterious (note: lower = worse) |

### Performance Characteristics

**Latency**:
- Cache hit: <50ms (Redis)
- Cache miss: 1-3 seconds (Ensembl VEP API)
- Timeout: 10 seconds (configurable)

**Rate Limiting**:
- Client-side: 15 requests/second (token bucket)
- Ensembl API: 15 requests/second per IP
- Ensembl API: 55,000 requests/hour per IP

**Caching**:
- Backend: Redis, 24-hour TTL
- Cache key: `vep:v2:{normalized_variant}`
- Cache hit rate: ~70% (after initial annotation)

**Scalability**:
- Stateless API (horizontal scaling)
- Rate limiter per-instance (needs server-side for multi-instance)
- Shared Redis cache across instances

## Architecture Overview

### System Components

```
┌─────────────┐
│   Browser   │
│  (Vue.js)   │
└──────┬──────┘
       │
       │ POST /api/v2/variants/annotate
       │ {"variant": "17:36459258:A:G"}
       ▼
┌─────────────────────────────────────────────────────────┐
│ FastAPI Backend                                         │
│                                                         │
│ ┌─────────────────────────────────────────────────┐    │
│ │ VariantValidator.annotate_with_vep()            │    │
│ │                                                 │    │
│ │ 1. Format Detection (VCF vs HGVS)              │    │
│ │ 2. Rate Limiting (15 req/sec)                  │    │
│ │ 3. Cache Check (Redis)                          │    │
│ │ 4. VEP API Call (if cache miss)                 │    │
│ │ 5. Extract CADD/gnomAD                          │    │
│ │ 6. Cache Store (24h TTL)                        │    │
│ │ 7. Return Normalized Response                   │    │
│ └─────────────────────────────────────────────────┘    │
│                                                         │
└─────────┬───────────────────────────────────┬───────────┘
          │                                   │
          │                                   │
          ▼                                   ▼
  ┌───────────────┐                   ┌──────────────┐
  │ Redis Cache   │                   │ Ensembl VEP  │
  │ (24h TTL)     │                   │  REST API    │
  └───────────────┘                   └──────────────┘
```

### Data Flow

**Annotation Request**:
1. User enters variant in frontend input field
2. Frontend validates format (VCF or HGVS)
3. POST request to `/api/v2/variants/annotate`
4. Backend rate limiter checks token bucket (15/sec)
5. Backend checks Redis cache for variant
6. **Cache hit**: Return cached result (fast path)
7. **Cache miss**: Call Ensembl VEP API
8. Extract CADD score and gnomAD frequency
9. Store result in Redis (24h TTL)
10. Return normalized response to frontend
11. Frontend displays results with color-coded badges

**Error Handling**:
- Invalid format → 400 Bad Request
- Variant not found → 404 Not Found
- Ensembl API timeout → 500 Internal Server Error
- Rate limit exceeded → 429 Too Many Requests
- Ensembl API down → 503 Service Unavailable

## Documentation

### Implementation Plan
Primary reference: [`docs/variant-annotation-implementation-plan.md`](../variant-annotation-implementation-plan.md)

**Contents**:
- Detailed architecture
- VEP API integration guide
- Rate limiting strategy
- Caching implementation
- Error handling patterns
- Testing approach
- Deployment notes

### Issue Documentation
- **Tests**: [`docs/issues/issue-117-vep-annotation-tests.md`](issue-117-vep-annotation-tests.md)
- **Documentation**: [`docs/issues/issue-118-vep-documentation.md`](issue-118-vep-documentation.md)

### External References
- **Ensembl VEP API**: https://rest.ensembl.org/documentation/info/vep_region_post
- **CADD Scores**: https://cadd.gs.washington.edu/
- **gnomAD Database**: https://gnomad.broadinstitute.org/
- **ACMG Guidelines**: Richards et al. (2015), *Genetics in Medicine*

## Target Completion

**Original Estimate**: End of January 2025

**Current Status** (as of Jan 14, 2025):
- ✅ **Phase 1: Backend**: 2/3 issues complete (66%)
  - ✅ #56 - VRS installation (complete)
  - ✅ #100 - VEP annotation API (complete)
  - ⏳ #117 - Tests (pending)

- ⏳ **Phase 2: Documentation**: 0/1 issues complete (0%)
  - ⏳ #118 - Documentation (pending)

- 📦 **Deferred to CRUD System**:
  - 📦 #116 - Frontend UI component

**Overall Progress**: 50% complete (2/4 issues in current scope)

**Revised Target**: End of January 2025 (on track)

**Remaining Work**: 3.5-4.5 hours
- Testing (2-3 hours)
- Documentation (1-1.5 hours)

**Risk Assessment**: **LOW**
- Core backend functionality complete and tested manually
- Remaining work is independent (tests, docs)
- No blocking dependencies or unknowns
- Can be completed in 1 work session
- Frontend UI moved to future CRUD milestone

## Acceptance Criteria (Epic-level)

### Functional Requirements
- [x] ✅ Users can annotate variants via API
- [x] ✅ Both VCF and HGVS formats supported
- [x] ✅ CADD scores returned for variants
- [x] ✅ gnomAD frequencies returned for variants
- [x] ✅ Rate limiting prevents API abuse
- [x] ✅ Caching improves performance
- [ ] 📦 Users can annotate variants via web UI (deferred to CRUD system)
- [ ] 📦 UI displays color-coded impact badges (deferred to CRUD system)
- [ ] 📦 UI shows CADD score interpretation (deferred to CRUD system)

### Quality Requirements
- [x] ✅ Backend code follows DRY/YAGNI principles
- [x] ✅ Error handling implemented
- [ ] ⏳ Test coverage ≥90%
- [ ] ⏳ All tests pass in CI/CD
- [ ] ⏳ Code reviewed and approved

### Documentation Requirements
- [x] ✅ Implementation plan complete
- [ ] ⏳ API reference documentation
- [ ] ⏳ User guide with examples
- [ ] ⏳ Developer guide updated
- [ ] ⏳ Swagger UI accessible

### Integration Requirements
- [x] ✅ API endpoint accessible via HTTP
- [ ] ⏳ Authentication required and enforced
- [ ] ⏳ CORS configured correctly
- [ ] ⏳ No 500 errors in production
- [ ] ⏳ API testable via curl/Postman

## Related Epics & Issues

**Related Features**:
- VRS variant representation (#56)
- Phenopacket variant storage (#100)

**Future Enhancements** (out of scope):
- #116 - Frontend UI component (moved to CRUD system)
- Batch variant annotation endpoint
- Variant annotation during data import
- ClinVar integration for known pathogenic variants
- Custom VEP cache for offline annotation
- Variant re-annotation (update old annotations)

## Metrics & Success Indicators

**Post-Launch Metrics** (to track after completion):

1. **Usage**:
   - Variants annotated per day (via API)
   - Unique users/applications using API
   - API call volume trends

2. **Performance**:
   - Average annotation latency (cache hit/miss)
   - Cache hit rate (target: >70%)
   - 95th percentile latency (target: <3s)

3. **Quality**:
   - Error rate (target: <1%)
   - API timeout rate (target: <0.1%)
   - User-reported issues (target: <2/month)

4. **Adoption**:
   - % of variants with VEP annotations
   - Time saved vs manual annotation
   - User satisfaction (survey)

## Priority & Labels

**Priority**: **P1 (High)** - Core feature for clinical variant interpretation

**Rationale**:
- Essential for clinical decision support
- Enables ACMG variant classification
- High user value (pathogenicity assessment)
- Reduced effort (4-5 hours, down from 6-8 hours)
- Low risk (backend complete, remaining work is straightforward)
- Frontend UI deferred to future CRUD system for consistency

**Labels**:
- `epic` - Epic issue tracking multiple sub-issues
- `feature` - New functionality
- `backend` - Backend API work
- `documentation` - Documentation tasks
- `testing` - Test coverage
- `p1-high` - High priority
- `vep` - VEP annotation specific
- `variant-annotation` - Variant annotation feature
- `api-only` - Backend API implementation (no UI)

**Milestones**:
- `v1.1.0` - Variant Annotation Backend (target: Jan 2025)
- `v1.2.0` - CRUD System with UI Components (includes #116)

---

## Deferred Component: Frontend UI (#116)

**Status**: 📦 **DEFERRED** to future CRUD system milestone

**Reason for Deferral**:
The frontend UI component (#116) has been intentionally moved to the future CRUD (Create, Read, Update, Delete) system milestone to ensure consistency across the application. Rather than building a standalone variant annotation UI now, we will integrate it into a comprehensive data management system that provides:

1. **Consistent UX**: Unified interface patterns across all data types (phenopackets, variants, diseases, etc.)
2. **Reusable Components**: Shared form validation, error handling, and data display components
3. **Better Architecture**: Centralized state management and API integration
4. **Reduced Duplication**: Avoid building one-off UI components that will be replaced later

**What This Means**:
- ✅ Backend API (`POST /api/v2/variants/annotate`) is **fully functional** and ready for use
- ✅ API can be tested via curl, Postman, or other HTTP clients
- ✅ Documentation will include API usage examples for programmatic access
- 📦 Web UI will be added later as part of comprehensive CRUD system
- 🔄 No functionality is lost - API provides all annotation capabilities

**Testing the API Without UI**:

```bash
# Example: Annotate a variant using curl
curl -X POST "http://localhost:8000/api/v2/variants/annotate" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "17:36459258:A:G"}'

# Response
{
  "most_severe_consequence": "missense_variant",
  "impact": "MODERATE",
  "transcript_consequences": [{
    "gene_symbol": "HNF1B",
    "cadd_phred": 25.4,
    "gnomad_af": 0.00001
  }]
}
```

**Benefits of This Approach**:
- Faster delivery of backend functionality (4-5 hours vs 6-8 hours)
- API available immediately for integration and testing
- Future UI benefits from mature CRUD patterns
- Avoids technical debt from hasty UI implementation
