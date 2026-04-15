# GitHub Issue Templates #34-#67

Copy these templates to create GitHub issues.

**Issues #34-#50:** Frontend migration and visualization tasks
**Issues #51-#53:** Backend enhancements for publication features
**Issue #62:** API infrastructure (JSON:API pagination)
**Issues #64-#66:** Variant search and visualization enhancements

---

## Issue #34

```markdown
# feat(frontend): migrate variants view to phenopacket interpretations

## Summary
Variants view displays data from non-existent variants table. Needs migration to extract variants from phenopacket interpretations structure.

**Current:** `/variants` → 404 (variants table doesn't exist)
**Target:** `/variants` → Display variants aggregated from phenopackets

## Details
See: [docs/issues/issue-34-migrate-variants-view.md](./issue-34-migrate-variants-view.md)

## Acceptance Criteria
- [ ] Table displays all unique variants across phenopackets
- [ ] Shows VRS variant ID, label, gene, type, pathogenicity
- [ ] Displays phenopacket count (how many individuals have variant)
- [ ] Clicking variant navigates to detail page
- [ ] Clicking phenopacket count filters to individuals with variant
- [ ] HGNC gene links work
- [ ] Pathogenicity color-coded
- [ ] No 404 errors

## Dependencies
- Issue #30 (API client) - ✅ Required
- **Backend:** Create `/aggregate/variants` endpoint - ⚠️ **BLOCKER**

## Priority
**P1 (High)** - Core functionality

## Labels
`frontend`, `views`, `phenopackets`, `migration`, `p1`
```

---

## Issue #35

```markdown
# feat(frontend): migrate variant detail page to interpretation view

## Summary
Variant detail page needs migration to show variant information from phenopacket interpretations, including all individuals with this variant.

**Current:** `/variants/:id` → 404
**Target:** `/variants/:id` → Display variant + affected individuals

## Details
See: [docs/issues/issue-35-migrate-variant-detail-page.md](./issue-35-migrate-variant-detail-page.md)

## Acceptance Criteria
- [ ] Page displays complete variant information (VRS ID, label, gene, VCF)
- [ ] Shows ACMG pathogenicity classification
- [ ] Displays all individuals with this variant in table
- [ ] HGNC, NCBI, OMIM gene links work
- [ ] VCF string copy-to-clipboard works
- [ ] Clicking individual navigates to phenopacket detail
- [ ] Responsive 2-column layout
- [ ] 404 handling for invalid variant IDs

## Dependencies
- Issue #34 (Variants view)
- **Backend:** Create `/by-variant/{id}` endpoint - ⚠️ **BLOCKER**

## Priority
**P1 (High)**

## Labels
`frontend`, `views`, `components`, `phenopackets`, `p1`
```

---

## Issue #36

```markdown
# feat(frontend): migrate publications view to external references

## Summary
Publications view needs migration to extract PMIDs from phenopacket external references.

**Current:** `/publications` → 404
**Target:** `/publications` → Display publications aggregated from phenopackets

## Details
See: [docs/issues/issue-36-migrate-publications-view.md](./issue-36-migrate-publications-view.md)

## Acceptance Criteria
- [ ] Table displays all publications from phenopackets
- [ ] Shows PMID, DOI, phenopacket count, date added
- [ ] PMID links to PubMed
- [ ] DOI links work
- [ ] Clicking phenopacket count filters individuals
- [ ] Sortable by all columns

## Dependencies
- Issue #30 (API client)
- **Backend:** Create `/aggregate/publications` endpoint

## Priority
**P1 (High)**

## Labels
`frontend`, `views`, `phenopackets`, `p1`
```

---

## Issue #37

```markdown
# feat(frontend): migrate publication detail page

## Status: Phase 1 Complete ✅ | Phase 2 Blocked 📋

### Summary
Show all phenopackets linked to a specific publication (PMID) with performance optimization and monitoring.

**Current (Phase 1 ✅):** `/publications/:pmid` → Basic publication page with client-side filtering
**Target (Phase 2 📋):** Enhanced page with PubMed metadata, server-side filtering, and production monitoring

## Details
See: [docs/issues/issue-37-41-batch.md](../docs/issues/issue-37-41-batch.md)

## Phase 1: MVP (Complete ✅)

**Implemented:**
- ✅ Publication detail page at `/publications/{pmid}`
- ✅ Basic metadata (PMID, DOI, individual count, date added)
- ✅ Table showing individuals citing this publication
- ✅ Client-side filtering (fetches all phenopackets, filters by PMID)
- ✅ Links to PubMed and DOI (external)
- ✅ Breadcrumb navigation
- ✅ Bidirectional navigation (Publications ↔ Individual ↔ Publication)

**Bug Fixes:**
- ✅ Fixed 404 errors (used `phenopacket_id` instead of UUID)
- ✅ Fixed MetadataCard publication links (array index mapping)
- ✅ Fixed CORS errors (Vite proxy)

**Files Modified:**
- `frontend/src/views/PagePublication.vue` (created)
- `frontend/src/views/Publications.vue` (links to detail)
- `frontend/src/components/phenopacket/MetadataCard.vue` (publication links)

**Performance Metrics (Phase 1):**
- **Current Load Time:** ~350ms (300ms API + 50ms client-side filtering)
- **Network Payload:** ~2MB (all 864 phenopackets)
- **Scalability Threshold:** Works for current 864 phenopackets, degrades beyond ~2000

## Phase 2: Backend Enhancements (Blocked 📋)

**Requires Backend Issues (with Security & Compliance):**
- [ ] Issue #51: PubMed API integration with caching (HIPAA/GDPR compliant)
- [ ] Issue #52: `/by-publication/{pmid}` endpoint (SQL injection prevention, input validation)
- [ ] Issue #53: `/aggregate/publication-summary/{pmid}` endpoint (privacy controls, ontology tracking)

**Enhanced Features (Not Yet Implemented):**
- [ ] Display publication title, authors, journal from PubMed API (with provenance tracking)
- [ ] Server-side filtering via `/by-publication/{pmid}` (7x performance improvement)
- [ ] Summary statistics (sex distribution, common phenotypes with validation)
- [ ] Variant statistics (pathogenicity, common genes with HGNC IDs)
- [ ] Small sample warning for privacy (n < 10)
- [ ] Abstract display

**Expected Performance (Phase 2):**
- **Target Load Time:** ~80ms (50ms API + 30ms render) - **4.4x faster**
- **Network Payload:** ~100KB (filtered results only) - **95% reduction**
- **Scalability:** Server-side filtering scales to 10,000+ phenopackets

## Acceptance Criteria

### Phase 1 (Complete ✅)
- [x] Page displays basic publication metadata (PMID, DOI, count, date)
- [x] Shows all phenopackets citing this publication
- [x] Links to PubMed, DOI work
- [x] Navigation to/from individual details works
- [x] No 404 errors, all links functional
- [x] Performance acceptable for 864 phenopackets

### Phase 2 (Blocked by Backend 📋)
- [ ] Displays publication metadata (title, authors, journal) - **Blocked: Issue #51**
- [ ] **Contextual display based on sample size** - **Blocked: Issue #53**
  - n = 1: Redirect to individual detail (no aggregation needed)
  - n = 2-9: Show table only (no misleading charts)
  - n = 10-29: Show table + simple bar chart
  - n ≥ 30: Show full statistics dashboard
- [ ] Server-side filtering for performance - **Blocked: Issue #52**
- [ ] Sample size warning for small publications - **Blocked: Issue #53**

### Performance & Monitoring
- [ ] Time-to-interactive < 200ms
- [ ] Network payload monitored (target <150KB)
- [ ] Error handling for backend failures (graceful degradation)
- [ ] Loading states for async operations
- [ ] **Conditional rendering:** No fancy charts for n < 10 (misleading)

## Dependencies

**Phase 1:**
- Issue #36 (Publications view) - ✅ Complete

**Phase 2:**
- **Backend:** Issue #51 (PubMed API integration with security) - ⚠️ **BLOCKER**
- **Backend:** Issue #52 (`/by-publication/{pmid}` endpoint with validation) - ⚠️ **BLOCKER**
- **Backend:** Issue #53 (Publication aggregation with privacy controls) - ⚠️ **BLOCKER**

## Rollback Strategy

### Phase 2 Rollback Criteria
Rollback to Phase 1 if:
1. **Backend Error Rate:** >10% for any backend endpoint (#51, #52, #53)
2. **Performance Degradation:** Time-to-interactive >500ms (worse than Phase 1)
3. **Data Integrity:** Invalid HPO terms or gene symbols displayed
4. **Privacy Breach:** Individual-level data exposed when n < 10

### Rollback Procedure
```bash
# 1. Revert frontend code to Phase 1
git revert <phase-2-commit-hash>
npm run build
# Deploy frontend

# 2. Verify Phase 1 functionality restored
# - Client-side filtering works
# - Basic metadata displays
# - Navigation functional

# 3. Monitor metrics return to Phase 1 baseline
# - Load time ~350ms (acceptable)
# - No backend dependency errors
```

### Graceful Degradation (Phase 2)
Frontend should handle backend failures gracefully:
- If Issue #51 fails: Show PMID only, hide metadata
- If Issue #52 fails: Fall back to client-side filtering (Phase 1 behavior)
- If Issue #53 fails: Hide statistics section, show table only

## Timeline

**Phase 1 (Complete):** 6 hours (1 day) ✅
**Phase 2 (Backend):** 28 hours (3.5 days) - Issues #51-#53
**Phase 3 (Frontend):** 4 hours (0.5 days) - Integrate backend APIs + error handling
**Total:** 38 hours (5 days)

## Priority
**Phase 1:** P1 (High) - ✅ Complete
**Phase 2:** P2 (Medium) - Enhancement with security/performance

## Labels
`frontend`, `views`, `phenopackets`, `p1`, `phase-1-complete`, `performance`, `security`
```

---

## Issue #38

```markdown
# feat: migrate home page statistics to v2 API (backend + frontend)

## Summary
Create `/aggregate/summary` endpoint and integrate with frontend home page. This is a full-stack task combining backend endpoint creation with frontend migration.

**Current:** No summary endpoint exists, Home.vue shows 404 errors
**Target:** Backend provides statistics, frontend displays them

## Details
See: [docs/issues/issue-38-migrate-home-stats.md](./issue-38-migrate-home-stats.md)

## Acceptance Criteria

### Backend
- [ ] Endpoint responds at `/api/v2/phenopackets/aggregate/summary`
- [ ] Returns 6 statistics (total, with_variants, with_phenotypes, with_diseases, distinct_hpo, distinct_diseases)
- [ ] Query completes in < 200ms
- [ ] Unit tests pass

### Frontend
- [ ] Home page loads without errors
- [ ] Stats show correct counts
- [ ] Numbers animate smoothly
- [ ] No console 404 errors

## Implementation Phases
1. **Backend:** Create aggregation endpoint with 6 SQL queries
2. **Frontend:** Update Home.vue to call new endpoint
3. **Testing:** Backend unit tests + frontend integration test

## Dependencies
- Issue #28 (JSONB indexes) - For performance
- Issue #30 (API client) - Frontend API setup

## Priority
**P1 (High)** - User-facing, easy win

## Labels
`backend`, `frontend`, `api`, `aggregation`, `p1`, `fullstack`
```

---

## Issue #39

```markdown
# feat(frontend): implement global phenopacket search

## Summary
Universal search across individuals, variants, publications, and phenotypes.

**Target:** Global search bar in AppBar with autocomplete

## Details
See: [docs/issues/issue-37-41-batch.md](../docs/issues/issue-37-41-batch.md)

## Acceptance Criteria
- [ ] Search bar in navigation (global access)
- [ ] Autocomplete with suggestions
- [ ] Search by subject ID, HPO terms, genes, variants, PMIDs
- [ ] Type-ahead results preview
- [ ] Recent searches saved
- [ ] Navigates to search results page

## Dependencies
- Issue #30 (API client)
- **Backend:** Enhance `/search` endpoint with full-text

## Priority
**P1 (High)** - Core functionality

## Labels
`frontend`, `components`, `feature`, `p1`
```

---

## Issue #41

```markdown
# feat(frontend): implement search results with faceted filtering

## Summary
Enhanced search results page with sidebar filters and dynamic counts.

**Target:** Search results with sidebar faceted filters

## Details
See: [docs/issues/issue-37-41-batch.md](../docs/issues/issue-37-41-batch.md)

## Acceptance Criteria
- [ ] Results page with 2-column layout (filters + results)
- [ ] Faceted filters: sex, has_variants, pathogenicity, diseases
- [ ] Filter counts update dynamically
- [ ] Sort by relevance, date, ID
- [ ] Export results (CSV, JSON)
- [ ] Shareable URL with query params
- [ ] Pagination

## Dependencies
- Issue #39 (Global search)

## Priority
**P1 (High)**

## Labels
`frontend`, `views`, `feature`, `p1`
```

---

## Issue #42

```markdown
# feat(frontend): add phenotype distribution stacked bar chart

## Summary
Stacked bar chart showing HPO term presence/absence across phenopackets.

**Target:** Interactive D3.js visualization in aggregations dashboard

## Details
See: [docs/issues/issue-42-47-visualizations.md](../docs/issues/issue-42-47-visualizations.md)

## Acceptance Criteria
- [ ] Stacked bar chart with D3.js
- [ ] X-axis: HPO term labels (top 20)
- [ ] Y-axis: Percentage/count
- [ ] Color-coded: Present (green), Absent (grey)
- [ ] Tooltip with detailed stats
- [ ] Responsive

## Dependencies
- Issue #33 (Aggregations)

## Priority
**P2 (Medium)**

## Labels
`frontend`, `charts`, `visualization`, `p2`
```

---

## Issue #43

```markdown
# feat(frontend): add publication timeline visualization

## Summary
D3.js timeline showing phenopackets added over time by publication.

**Target:** Timeline chart in aggregations dashboard

## Details
See: [docs/issues/issue-42-47-visualizations.md](../docs/issues/issue-42-47-visualizations.md)

## Acceptance Criteria
- [ ] D3.js timeline (X=year, Y=cumulative count)
- [ ] Hover shows publication details
- [ ] Click navigates to publication detail
- [ ] Smooth transitions

## Dependencies
- Issue #36 (Publications)

## Priority
**P2 (Medium)**

## Labels
`frontend`, `charts`, `visualization`, `p2`
```

---

## Issue #44

```markdown
# feat(frontend): add phenotype count histogram

## Summary
Histogram showing distribution of phenotype counts per individual.

**Target:** D3.js histogram with comparison overlays

## Details
See: [docs/issues/issue-42-47-visualizations.md](../docs/issues/issue-42-47-visualizations.md)

## Acceptance Criteria
- [ ] Histogram (X=# phenotypes, Y=count of individuals)
- [ ] Separate histograms: CAKUT-only vs CAKUT+MODY
- [ ] Overlay for comparison
- [ ] Summary stats (mean, median, std dev)

## Dependencies
- Issue #33 (Aggregations)

## Priority
**P2 (Medium)**

## Labels
`frontend`, `charts`, `visualization`, `p2`
```

---

## Issue #45

```markdown
# feat(frontend): add variant type comparison view

## Summary
Side-by-side comparison of phenotype distributions between variant types.

**Target:** Comparison dashboard (truncating vs non-truncating, 17q vs point mutations)

## Details
See: [docs/issues/issue-42-47-visualizations.md](../docs/issues/issue-42-47-visualizations.md)

## Acceptance Criteria
- [ ] Side-by-side paired bar charts
- [ ] Compare truncating vs non-truncating
- [ ] Compare 17q deletion vs point mutations
- [ ] Statistical significance tests (Chi-square, p-values)
- [ ] Export comparison table

## Dependencies
- Issue #33, #34

## Priority
**P2 (Medium)**

## Labels
`frontend`, `charts`, `feature`, `p2`
```

---

## Issue #46

```markdown
# feat(frontend): add clinical subgroup comparisons

## Summary
Compare phenotypes across clinical subgroups (CAKUT vs MODY, CKD stages, etc.)

**Target:** Reusable comparison component for multiple subgroups

## Details
See: [docs/issues/issue-42-47-visualizations.md](../docs/issues/issue-42-47-visualizations.md)

## Acceptance Criteria
- [ ] Subgroup selector dropdown
- [ ] CAKUT-only vs CAKUT+MODY comparison
- [ ] CKD Stage 3 vs 4 vs 5 comparison
- [ ] With/without diabetes comparison
- [ ] Statistical tests (ANOVA, Chi-square)
- [ ] Export results

## Dependencies
- Issue #33

## Priority
**P2 (Medium)**

## Labels
`frontend`, `charts`, `feature`, `p2`
```

---

## Issue #47

```markdown
# feat(frontend): implement Kaplan-Meier survival curves

## Summary
Renal survival analysis with Kaplan-Meier curves.

**Target:** D3.js survival curves grouped by variant type

## Details
See: [docs/issues/issue-42-47-visualizations.md](../docs/issues/issue-42-47-visualizations.md)

## Acceptance Criteria
- [ ] Kaplan-Meier curves using D3.js
- [ ] Censoring indicators (vertical ticks)
- [ ] Log-rank test p-values
- [ ] Risk table below plot
- [ ] Group by variant type, 17q deletion status
- [ ] Export survival data

⚠️ **Note:** Requires temporal data (age at ESRD). If unavailable, implement with mock data and mark "Coming Soon".

## Dependencies
- Issue #33

## Priority
**P3 (Low)** - Data availability uncertain

## Labels
`frontend`, `charts`, `feature`, `p3`
```

---

## Issue #48

```markdown
# test(frontend): add E2E tests for critical user flows

## Summary
Comprehensive Playwright E2E tests for all critical workflows.

**Target:** 90%+ coverage of user flows

## Details
See: [docs/issues/issue-48-50-polish.md](../docs/issues/issue-48-50-polish.md)

## Acceptance Criteria
- [ ] Playwright installed and configured
- [ ] Navigation tests (home → phenopackets → detail)
- [ ] Search tests (query, filters, results)
- [ ] Aggregations tests (all charts load)
- [ ] Variant flow tests (list → detail → individuals)
- [ ] Tests pass in CI/CD
- [ ] Test coverage report generated

## Dependencies
- All Phase 1-2 issues completed

## Priority
**P1 (High)** - Production quality

## Labels
`frontend`, `testing`, `p1`
```

---

## Issue #49

```markdown
# fix(frontend): remove all v1 legacy code

## Summary
Clean up deprecated v1 code after migration complete.

**Target:** Zero v1 references, clean codebase

## Details
See: [docs/issues/issue-48-50-polish.md](../docs/issues/issue-48-50-polish.md)

## Acceptance Criteria
- [ ] All deprecated API functions removed
- [ ] Unused v1 components deleted
- [ ] Legacy route redirects simplified
- [ ] No `individual_id` or `variant_ref` v1 naming
- [ ] ESLint passes with no warnings
- [ ] All views still work after cleanup

## Dependencies
- All Phase 1-2 issues completed

## Priority
**P1 (High)** - Code quality

## Labels
`frontend`, `refactor`, `p1`
```

---

## Issue #50

```markdown
# docs(frontend): update user documentation

## Summary
Complete user-facing documentation for phenopackets v2 frontend.

**Target:** User guide, developer guide, API reference, changelog

## Details
See: [docs/issues/issue-48-50-polish.md](../docs/issues/issue-48-50-polish.md)

## Acceptance Criteria
- [ ] User guide written (getting started, features, FAQ)
- [ ] Developer guide updated (setup, architecture, testing)
- [ ] API reference documented (all v2 endpoints)
- [ ] Changelog created (v2.0.0 release notes)
- [ ] README updated with new features
- [ ] Screenshots added
- [ ] All docs reviewed and proofread

## Dependencies
- Issue #49 (Cleanup done)

## Priority
**P1 (High)** - Production ready

## Labels
`documentation`, `p1`
```

---

## Issue #51

```markdown
# feat(backend): add PubMed API integration with database caching

## Summary
Create backend infrastructure for fetching and caching publication metadata from PubMed API with comprehensive security, compliance, and monitoring.

**Current:** No backend support for publication metadata
**Target:** Database-backed caching layer for PubMed data with 90-day TTL, HIPAA/GDPR compliance, and production-ready monitoring

## Details
See: [docs/issues/issue-51-backend-pubmed-api.md](./issue-51-backend-pubmed-api.md)

## Acceptance Criteria

### Security & Compliance
- [ ] PMID validation with regex (prevents SQL injection)
- [ ] HIPAA/GDPR compliance assessment documented
- [ ] API key management implemented (3 vs 10 req/sec rate limiting)
- [ ] Input validation for all parameters
- [ ] Pydantic response models for type safety

### Database
- [ ] `publication_metadata` table created with JSONB authors (preserves order)
- [ ] Provenance tracking fields (data_source, fetched_by, api_version)
- [ ] Partial indexes for expired/active records
- [ ] Alembic migration written with rollback script

### Backend
- [ ] `/publications/{pmid}/metadata` endpoint implemented
- [ ] PubMed API integration working with NCBI E-utilities
- [ ] Database caching functional (90-day TTL)
- [ ] Error handling (rate limits, timeouts, not found, 429 with Retry-After header)
- [ ] Cache warming script functional

### Monitoring & Observability
- [ ] Prometheus metrics (cache hits, API latency, error rates)
- [ ] Structured logging with context
- [ ] Alerting thresholds defined (error rate >5%, latency p95 >2s, cache hit <80%)
- [ ] Dashboard metrics specified

### Testing
- [ ] Unit tests for PMID validation (≥80% coverage)
- [ ] Integration tests for endpoint
- [ ] Mock PubMed API responses in tests
- [ ] Test error handling and SQL injection attempts
- [ ] Test invalid PMID formats

### Performance
- [ ] Cache hit response time < 50ms
- [ ] Cache miss (first request) < 1000ms
- [ ] Handles rate limiting gracefully with exponential backoff

### Deployment
- [ ] Deployment procedure documented
- [ ] Rollback criteria defined
- [ ] Rollback procedure tested

## Dependencies
**Blocked by:** None - standalone feature

**Blocks:**
- Issue #37 Phase 2 (frontend publication detail enhancements)

## Timeline
**Estimated:** 12 hours (1.5 days) development + monitoring/testing

## Priority
**P2 (Medium)** - Enhancement for issue #37

## Labels
`backend`, `api`, `feature`, `pubmed`, `caching`, `security`, `compliance`, `p2`
```

---

## Issue #52

```markdown
# feat(backend): add /by-publication/{pmid} phenopackets endpoint

## Summary
Create backend endpoint to efficiently query phenopackets by publication PMID with server-side filtering, comprehensive security validation, and production monitoring.

**Current:** Frontend fetches all phenopackets, filters client-side (inefficient, insecure)
**Target:** Server-side filtering with optimized database query, input validation, and monitoring

## Details
See: [docs/issues/issue-52-backend-publication-endpoint.md](./issue-52-backend-publication-endpoint.md)

## Acceptance Criteria

### Security & Compliance
- [ ] PMID validation function (prevents SQL injection)
- [ ] **CRITICAL FIX:** SQL injection prevention in count query (parameterized, not f-string)
- [ ] Sex enum validation (only valid GA4GH values)
- [ ] Pagination limit capped at 500 (data minimization)
- [ ] Pydantic response models for type safety
- [ ] HIPAA/GDPR compliance assessment (de-identified data)

### Backend Service
- [ ] `get_phenopackets_by_publication()` function implemented
- [ ] `validate_pmid()` function with regex validation
- [ ] PMID format normalized (handles with/without PMID: prefix)
- [ ] Optional filters work (sex, has_variants)
- [ ] Pagination works correctly
- [ ] Total count accurate

### API Endpoint
- [ ] `/by-publication/{pmid}` endpoint responds
- [ ] Returns only phenopackets citing this PMID
- [ ] Query parameters work (skip, limit, sex, has_variants)
- [ ] Error handling (404 if no results, 400 for invalid params, 500 with logging)
- [ ] OpenAPI docs generated

### Performance
- [ ] GIN index created on externalReferences
- [ ] Query time < 100ms (with index)
- [ ] Index used in query plan (verify with EXPLAIN ANALYZE)

### Monitoring & Observability
- [ ] Prometheus metrics (query latency, results count, index usage)
- [ ] Structured logging with query context
- [ ] Alerting thresholds defined (error rate >5%, latency p95 >100ms)
- [ ] Dashboard metrics specified

### Testing
- [ ] Unit tests pass (≥80% coverage)
- [ ] **CRITICAL:** SQL injection attempt test (validates rejection)
- [ ] Integration tests pass
- [ ] Pagination tested
- [ ] Filters tested
- [ ] Performance test (query <100ms)

### Deployment
- [ ] Deployment procedure documented
- [ ] Rollback criteria defined
- [ ] Rollback procedure tested

## Performance Impact
**Before:** Fetches all 864 phenopackets (~300ms), client-side filtering (~50ms) = 350ms
**After:** Server-side query with index (~20ms), returns only matches (~30ms) = 50ms ✅
**Gain:** 7x faster, 95% less data transferred

## Dependencies
**Blocked by:** None

**Blocks:**
- Issue #37 Phase 2 (frontend publication detail enhancements)

## Timeline
**Estimated:** 8 hours (1 day) development + security/monitoring

## Priority
**P2 (Medium)** - Performance optimization for issue #37

## Labels
`backend`, `api`, `performance`, `jsonb`, `security`, `p2`
```

---

## Issue #53

```markdown
# feat(backend): add publication summary statistics endpoint

## Summary
Create backend endpoint to provide **contextually appropriate** summary data for phenopackets citing a publication, with sample-size-based recommendations.

**Current:** No aggregation statistics available
**Target:** `/aggregate/publication-summary/{pmid}` endpoint with realistic statistics based on sample size

**⚠️ IMPORTANT CONTEXT:**
- **80-90% of publications:** 1-2 phenopackets (single case reports) → Statistics not meaningful
- **5-10% of publications:** 3-9 phenopackets (small case series) → Basic counts only
- **1-5% of publications:** 10-50 phenopackets (cohort studies) → Full statistics appropriate
- **<1% of publications:** 50+ phenopackets (large studies) → Comprehensive analytics

## Details
See: [docs/issues/issue-53-backend-publication-aggregation.md](./issue-53-backend-publication-aggregation.md)

## Implementation Options

### Recommended: Option B (Simplified Endpoint)
**Return minimal, always-useful data + frontend guidance**

**Benefits:**
- ✅ Simple, fast query (~3 hours vs 8 hours)
- ✅ No misleading statistics for small samples
- ✅ Frontend controls appropriate visualization
- ✅ Useful for ALL publications (not just large ones)

**Response Structure:**
```json
{
  "pmid": "PMID:30791938",
  "total_phenopackets": 5,
  "sample_size_category": "small",  // "single", "small", "medium", "large"
  "sex_counts": {"MALE": 3, "FEMALE": 2},
  "has_genetic_data_count": 5,
  "publication_type": "case_series",
  "display_recommendation": "show_table"  // frontend guidance
}
```

### Alternative: Option A (Full Implementation)
**Comprehensive statistics for all publications**
- Top 10 phenotypes, pathogenicity distribution, gene lists
- **Cons:** Overkill for 90% of publications, misleading for small samples
- **Estimated:** 8 hours

### Better Focus: Prioritize Issue #43 (Publication Timeline)
**Database-level visualization more valuable than per-publication stats**
- Shows which publications contributed most data
- Timeline of database growth
- More interesting insights

## Acceptance Criteria (Option B - Recommended)

### Security & Compliance
- [ ] PMID validation (prevents SQL injection)
- [ ] HIPAA/GDPR compliance assessment (aggregate data only)
- [ ] Sample size categorization (single/small/medium/large)

### Backend Service
- [ ] `get_publication_summary_simple()` function implemented
- [ ] Returns: total count, sex counts, genetic data count
- [ ] `sample_size_category` field (guides frontend display)
- [ ] `display_recommendation` field (redirect/table/stats)
- [ ] **No misleading percentages for n < 10**

### API Endpoint
- [ ] `/aggregate/publication-summary/{pmid}` responds
- [ ] Returns simplified summary object
- [ ] 404 error if no phenopackets cite this PMID
- [ ] 400 error for invalid PMID format
- [ ] Pydantic response model for type safety

### Performance
- [ ] Query completes in < 200ms (simpler than Option A)
- [ ] Single SQL query (not 5+ complex aggregations)

### Monitoring & Observability
- [ ] Prometheus metrics (latency, sample size distribution)
- [ ] Structured logging
- [ ] Alerting thresholds defined

### Testing
- [ ] Unit tests pass (≥80% coverage)
- [ ] Sample size categorization tested
- [ ] Edge cases tested (n=0, n=1, n=100)

### Deployment
- [ ] Deployment procedure documented
- [ ] Rollback criteria defined
- [ ] Rollback procedure tested

## Frontend Display Logic (Issue #37)
- **n = 1:** Redirect to individual phenopacket detail
- **n = 2-9:** Show table only (no charts)
- **n = 10-29:** Show table + simple bar chart
- **n ≥ 30:** Show full statistics dashboard

## Dependencies
**Blocked by:** None

**Recommended but not blocking:**
- Issue #52 (creates externalReferences GIN index for performance)

**Blocks:**
- Issue #37 Phase 2 (frontend publication detail enhancements)

**Consider prioritizing instead:**
- Issue #43 (Publication Timeline) - More valuable visualization

## Timeline
**Option B (Recommended):** 3 hours (0.5 days)
**Option A (Full):** 8 hours (1 day)

## Priority
**P2 (Medium)** - Enhancement for issue #37

**Recommendation:** Implement Option B (simplified) + prioritize Issue #43 (timeline)

## Labels
`backend`, `api`, `aggregation`, `statistics`, `privacy`, `p2`
```

---

## Issue #64

```markdown
# feat(backend): add variant search API endpoint with security

⚠️ **SECURITY WARNING**: This issue implements database search functionality. All input validation, SQL injection prevention, and rate limiting MUST be implemented before production deployment.

## Summary
Create secure backend API endpoint for variant search across all phenopackets with multiple filter criteria, input validation, rate limiting, and audit logging.

**Current:** No search endpoint exists - variants must be manually filtered client-side
**Target:** RESTful search endpoint with parameterized queries, HGVS validation, rate limiting, and GDPR-compliant audit logging

## Details
See: [docs/issues/issue-64-variant-search.md](./issue-64-variant-search.md)

## Acceptance Criteria

**Security:**
- [ ] All user inputs validated and sanitized
- [ ] SQL injection prevented (parameterized queries only)
- [ ] HGVS notation format validated
- [ ] Rate limiting enforced (10 req/min per IP)
- [ ] Audit logging captures all searches

**Functionality:**
- [ ] `/aggregate/variants/search` endpoint responds
- [ ] Text search works for HGVS notations (c., p., g.)
- [ ] Type filter works (SNV, deletion, etc.)
- [ ] Classification filter works (P, LP, VUS, etc.)
- [ ] Gene filter works (HNF1B)
- [ ] Multiple filters can be combined (AND logic)
- [ ] Returns total and filtered counts

**Performance:**
- [ ] Backend query performance < 200ms (with GIN indexes)
- [ ] GIN indexes created for variant IDs, expressions, types, classifications
- [ ] Max limit enforced (1000 variants per request)

**Testing:**
- [ ] SQL injection attempts fail (400 Bad Request)
- [ ] Rate limit exceeded returns 429 Too Many Requests
- [ ] Invalid HGVS notation returns 400 with helpful error

## Dependencies
- Issue #57 (Variant deduplication) - ⚠️ **BLOCKER** - Must resolve duplicate variants before search returns accurate results
- Issue #34 (Variants list page) - ✅ Required for context
- Issue #66 (Frontend search UI) - ⚠️ **DEPENDS ON THIS** - Cannot implement frontend without backend endpoint

## Priority
**P1 (High)** - Blocker for Issue #66 (frontend search UI)

**Rationale:**
- Security-critical endpoint (SQL injection risk)
- Required for variant search functionality
- Blocks frontend development until complete

## Labels
`backend`, `security`, `search`, `variants`, `database`, `p1`, `blocker`
```

---

## Issue #65

```markdown
# feat(frontend): add HNF1B gene visualization with variant mapping

## Summary
Add interactive SVG visualization of HNF1B gene structure to variant detail page, showing exon/intron architecture with variants mapped to genomic positions.

**Current:** Variant detail page shows metadata only (text/table)
**Target:** Visual gene diagram with variants positioned on gene structure

## Details
See: [docs/issues/issue-65-gene-visualization.md](./issue-65-gene-visualization.md)

## Acceptance Criteria
- [ ] Gene structure displays all 9 exons correctly positioned
- [ ] Exons rendered with genomic coordinates
- [ ] Introns shown as connecting lines
- [ ] Variants displayed as colored circles
- [ ] Current variant highlighted distinctly
- [ ] Variant colors match pathogenicity (P=red, LP=orange, VUS=yellow)
- [ ] Exon hover shows number, position, size, domain
- [ ] Variant hover shows HGVS, classification
- [ ] Clicking variant navigates to detail page
- [ ] Zoom controls work (in/out/reset)
- [ ] Legend explains colors and symbols
- [ ] Renders < 100ms for 100 variants

## Dependencies
- Issue #35 (Variant detail page) - ✅ Required
- Issue #34 (Variants list) - ✅ Required (for fetching variants)

## Priority
**P3 (Low)** - Enhancement, not critical for MVP

## Labels
`frontend`, `visualization`, `variants`, `enhancement`, `p3`, `svg`, `d3`
```

---

## Issue #66

```markdown
# feat(frontend): add variant search UI with filters

## Summary
Add frontend search interface to the variants list page, enabling users to quickly find specific variants by HGVS notation, gene, type, and pathogenicity classification.

**Current:** Variants list shows all variants without search/filter capabilities
**Target:** Interactive search bar with filters, active filter chips, and real-time result counts

## Details
See: [docs/issues/issue-66-frontend-variant-search-ui.md](./issue-66-frontend-variant-search-ui.md)

## Acceptance Criteria

**Search Functionality:**
- [ ] Search bar accepts text input
- [ ] Search is debounced (300ms delay)
- [ ] Text search works for HGVS notations (c., p., g.)
- [ ] Text search works for variant IDs
- [ ] Text search works for gene symbols
- [ ] Empty search shows all variants

**Filter Functionality:**
- [ ] Type filter works (SNV, deletion, duplication, insertion, inversion, CNV)
- [ ] Classification filter works (P, LP, VUS, LB, B)
- [ ] Gene filter works (HNF1B)
- [ ] Multiple filters can be combined
- [ ] Filters applied immediately (no debounce)

**UI/UX:**
- [ ] Active filters displayed as colored chips
- [ ] Each chip has close button
- [ ] Clear All button removes all filters
- [ ] Results count shows "X of Y variants"
- [ ] Search help tooltip shows examples
- [ ] Loading states shown during API calls
- [ ] No results message displayed appropriately
- [ ] Responsive on mobile devices

**Performance:**
- [ ] Debouncing prevents excessive API calls (max 3/sec)
- [ ] UI remains responsive during search
- [ ] No flickering during debounced typing

**Error Handling:**
- [ ] API errors display user-friendly messages
- [ ] Rate limit errors (429) handled gracefully
- [ ] Network errors show connection failed message

## Dependencies
- Issue #64 (Backend search endpoint) - ⚠️ **BLOCKER** - Must be completed first
- Issue #34 (Variants list page) - ✅ Required for context
- `lodash-es` npm package - For debouncing

## Priority
**P1 (High)** - Core feature for variant discovery

**Rationale:**
- Directly impacts user ability to find variants
- Complements backend search endpoint (Issue #64)
- Required for efficient variant lookup
- Relatively quick win (9 hours)

## Labels
`frontend`, `search`, `variants`, `ui`, `p1`
```

---

## Issue #62

```markdown
# feat(api): implement JSON:API query conventions and cursor pagination

## Summary
Add JSON:API v1.1 pagination, filtering, and sorting conventions to `/api/v2/phenopackets` endpoint. Maintain GA4GH Phenopackets response structure while adding standardized metadata and navigation links.

**Current:** `GET /phenopackets?skip=0&limit=100&sex=MALE` → `List[...]` (no metadata)
**Target:** `GET /phenopackets?page[number]=1&page[size]=100&filter[sex]=MALE&sort=-created_at` → `{data, meta, links}`

## Details
See: [docs/issues/issue-62-json-api-pagination.md](./issue-62-json-api-pagination.md)

## Acceptance Criteria

**Offset Pagination:**
- [ ] `page[number]` parameter works (1-indexed pages)
- [ ] `page[size]` parameter works (default: 100, max: 1000)
- [ ] Response includes `meta.page.totalRecords`
- [ ] Response includes `meta.page.totalPages`
- [ ] Response includes `meta.page.currentPage`
- [ ] Response includes `meta.page.pageSize`

**Navigation Links:**
- [ ] `links.self` points to current page
- [ ] `links.first` points to first page
- [ ] `links.last` points to last page
- [ ] `links.prev` exists when not on first page (null on page 1)
- [ ] `links.next` exists when not on last page (null on last page)

**Filtering:**
- [ ] `filter[sex]` parameter works (MALE, FEMALE, OTHER_SEX, UNKNOWN_SEX)
- [ ] `filter[has_variants]` parameter works (true/false)
- [ ] Filters reflected in pagination links
- [ ] Total counts respect active filters

**Sorting:**
- [ ] `sort` parameter works (comma-separated fields)
- [ ] Descending order with `-` prefix (e.g., `-created_at`)
- [ ] Ascending order without prefix (e.g., `subject_id`)
- [ ] Supported fields: `created_at`, `subject_id`, `subject_sex`
- [ ] Invalid sort fields return 400 error with message

**Cursor Pagination (Bonus):**
- [ ] `page[after]` parameter works for forward pagination
- [ ] `page[before]` parameter works for backward pagination
- [ ] Response includes `meta.page.endCursor`
- [ ] Response includes `meta.page.startCursor`
- [ ] Response includes `meta.page.hasNextPage`
- [ ] Response includes `meta.page.hasPreviousPage`
- [ ] Cursor pagination prevents duplicate/missing records

**Backwards Compatibility:**
- [ ] Legacy `skip` parameter still works (deprecated)
- [ ] Legacy `limit` parameter still works (deprecated)
- [ ] Legacy `sex` parameter still works (deprecated)
- [ ] Legacy `has_variants` parameter still works (deprecated)
- [ ] `X-Deprecation` header returned when legacy params used
- [ ] Legacy params return JSON:API response format

**Performance:**
- [ ] Query time < 200ms for page[size]=100
- [ ] Add `(created_at, id)` database index for cursor pagination
- [ ] COUNT query optimized (avoid full table scan)

**Tests:**
- [ ] Unit tests for offset pagination pass
- [ ] Unit tests for cursor pagination pass
- [ ] Unit tests for filtering pass
- [ ] Unit tests for sorting pass
- [ ] Integration tests for full pagination workflows pass
- [ ] Backwards compatibility tests pass

**Documentation:**
- [ ] OpenAPI schema updated with JSON:API examples
- [ ] `backend/CLAUDE.md` updated with conventions
- [ ] `frontend/CLAUDE.md` updated with pagination examples
- [ ] Migration guide created (`frontend/MIGRATION-JSON-API.md`)
- [ ] ADR created for JSON:API adoption decision

**Frontend Integration:**
- [ ] `frontend/src/api/index.js` updated with new `getPhenopackets()` function
- [ ] `frontend/src/views/Phenopackets.vue` displays pagination metadata
- [ ] Frontend shows "Page X of Y" text
- [ ] Frontend shows total record count
- [ ] Sort dropdown implemented
- [ ] Pagination controls use `links.next`/`links.prev`

## Dependencies
None (independent feature)

## Priority
**P1 (High)** - No pagination metadata breaks UX (can't show "Page X of Y")

**Rationale:**
- Without metadata, frontend cannot display current page or total pages
- Users have no visibility into dataset size
- Navigation buttons cannot be intelligently disabled
- Standard JSON:API conventions improve developer experience
- Cursor pagination prevents data inconsistencies during browsing

## Labels
`backend`, `api`, `pagination`, `json-api`, `p1`, `enhancement`, `frontend`
```

