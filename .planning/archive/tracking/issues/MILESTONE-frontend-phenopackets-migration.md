# Milestone: Frontend Phenopackets v2 Migration

## Overview

Complete migration of the frontend from v1 normalized schema to GA4GH Phenopackets v2 JSONB-based backend, with enhanced visualizations and analytics capabilities.

**Goal:** Fully functional frontend that leverages phenopackets structure for improved data presentation and clinical insights.

**Target Completion:** TBD

## Milestone Metadata

**Milestone Name:** `frontend-phenopackets-v2-migration`

**Labels:** `frontend`, `migration`, `phenopackets`, `milestone`

**Priority:** P0 (Critical) - Blocking production release

## Current Status

### ✅ Completed Issues
- **Issue #30:** `feat(api): migrate API client to phenopackets v2 endpoints` ✅
- **Issue #31:** `feat(frontend): migrate individuals list view to phenopackets` ✅
- **Issue #32:** `feat(frontend): migrate individual detail page to phenopackets v2` ✅
- **Issue #33:** `fix(frontend): update aggregation endpoints for phenopacket format` ✅
- **Issue #36:** `feat(frontend): migrate publications view to external references` ✅
- **Issue #37:** `feat(frontend): migrate publication detail page` ✅ Phase 1 (MVP)
- **Issue #38:** `feat(frontend): migrate home page statistics to v2 API` ✅

### 🔄 Partially Complete
- **Issue #37:** `feat(frontend): migrate publication detail page` - Phase 2 blocked by backend issues #51-#53

### 📋 Pending Issues
See breakdown below

## Issue Breakdown

### Phase 1: Core Views Migration (P1 - High Priority)

#### Issue #33: `fix(frontend): update aggregation endpoints for phenopacket format`
**Status:** 📋 Pending
**Blocks:** Statistical analysis features
**Effort:** 10 hours (1.5 days)
**Description:** Migrate aggregations dashboard from v1 to v2 endpoints with new data structures.

#### Issue #34: `feat(frontend): migrate variants view to phenopacket interpretations`
**Status:** 📋 Pending
**Depends on:** #30
**Effort:** 12 hours (2 days)
**Description:** Display variants from `phenopacket.interpretations[]` instead of separate variants table.
**Key Changes:**
- Extract variants from `interpretations[].diagnosis.genomicInterpretations[]`
- Show ACMG pathogenicity classifications
- Display VRS 2.0 variant identifiers
- Link variants to affected individuals (phenopackets)

#### Issue #35: `feat(frontend): migrate variant detail page to interpretation view`
**Status:** 📋 Pending
**Depends on:** #34
**Effort:** 10 hours (1.5 days)
**Description:** Show detailed variant information from phenopacket interpretations.
**Key Changes:**
- Display VRS variation descriptor
- Show all phenopackets with this variant
- Display gene context (HGNC ID, symbol)
- Show VCF record details

#### Issue #36: `feat(frontend): migrate publications view to external references`
**Status:** 📋 Pending
**Depends on:** #30
**Effort:** 8 hours (1 day)
**Description:** Display publications from `phenopacket.metaData.externalReferences[]`.
**Key Changes:**
- Extract PMIDs from all phenopackets
- Group phenopackets by publication
- Show publication statistics (phenopackets per paper)

#### Issue #37: `feat(frontend): migrate publication detail page`
**Status:** ✅ Phase 1 Complete | 📋 Phase 2 Blocked
**Depends on:** #36 ✅ | Backend issues #51, #52, #53
**Effort:** 6 hours (1 day) - Phase 1 ✅ | 28 hours (3.5 days) - Phase 2 backend + 4 hours frontend
**Description:** Show all phenopackets linked to a specific publication.

**Phase 1 Complete (MVP):**
- ✅ Basic publication detail page at `/publications/{pmid}`
- ✅ Table showing individuals citing this publication
- ✅ Client-side filtering (works for current 864 phenopackets)
- ✅ Links to PubMed, DOI
- ✅ Breadcrumb navigation
- ✅ Bidirectional navigation working

**Phase 2 Blocked (Enhancements):**
- ⏸️ PubMed metadata (title, authors, journal) - Requires Issue #51
- ⏸️ Server-side filtering for performance - Requires Issue #52
- ⏸️ Summary statistics (sex, phenotypes, variants) - Requires Issue #53

See: `docs/issues/issue-37-41-batch.md` for detailed implementation notes

#### Issue #38: `feat(frontend): migrate home page statistics to v2 API`
**Status:** 📋 Pending
**Depends on:** #30
**Effort:** 4 hours (0.5 days)
**Description:** Update home page stats using `/aggregate/summary` endpoint.

### Phase 2: Search & Navigation (P1 - High Priority)

#### Issue #39: `feat(frontend): implement global phenopacket search`
**Status:** 📋 Pending
**Depends on:** #30
**Effort:** 12 hours (2 days)
**Description:** Universal search across individuals, variants, publications, phenotypes.
**Features:**
- Search by subject ID, phenopacket ID
- Search by HPO terms (phenotypic features)
- Search by gene, variant identifier
- Search by PMID, publication
- Unified search results page

#### Issue #41: `feat(frontend): implement search results with faceted filtering`
**Status:** 📋 Pending
**Depends on:** #39
**Effort:** 10 hours (1.5 days)
**Description:** Enhanced search results with filters.
**Features:**
- Filter by sex, disease, HPO terms
- Filter by variant type, pathogenicity
- Sort by relevance, date
- Export search results

### Phase 3: Enhanced Visualizations (P2 - Medium Priority)

#### Issue #42: `feat(frontend): add phenotype distribution stacked bar chart`
**Status:** 📋 Pending
**Depends on:** #33
**Effort:** 8 hours (1 day)
**Description:** Visualize HPO term frequencies across phenopackets.
**Visualization:**
- Stacked bar chart: phenotype presence/absence
- Group by clinical categories (renal, diabetes, genital)
- Show percentage distribution

#### Issue #43: `feat(frontend): add publication timeline visualization`
**Status:** 📋 Pending
**Depends on:** #36
**Effort:** 6 hours (1 day)
**Description:** Timeline of phenopackets by publication date.
**Visualization:**
- D3.js timeline plot
- Show phenopackets added over time
- Group by publication

#### Issue #44: `feat(frontend): add phenotype count histogram`
**Status:** 📋 Pending
**Depends on:** #33
**Effort:** 6 hours (1 day)
**Description:** Distribution of phenotype counts per individual.
**Visualization:**
- Histogram: X=number of phenotypes, Y=count of individuals
- Separate histograms for CAKUT vs MODY

### Phase 4: Cohort Comparisons (P2 - Medium Priority)

#### Issue #45: `feat(frontend): add variant type comparison view`
**Status:** 📋 Pending
**Depends on:** #33, #34
**Effort:** 12 hours (2 days)
**Description:** Compare phenotype distributions between variant types.
**Features:**
- Compare truncating vs non-truncating variants
- Compare 17q deletion vs point mutations
- Side-by-side donut/bar charts
- Statistical significance indicators

#### Issue #46: `feat(frontend): add clinical subgroup comparisons`
**Status:** 📋 Pending
**Depends on:** #33
**Effort:** 10 hours (1.5 days)
**Description:** Compare phenotypes across clinical subgroups.
**Comparisons:**
- CAKUT-only vs CAKUT+MODY
- Kidney disease stages (CKD3 vs CKD4 vs CKD5)
- With vs without diabetes
- With vs without genital abnormalities

### Phase 5: Survival Analysis (P3 - Low Priority)

#### Issue #47: `feat(frontend): implement Kaplan-Meier survival curves`
**Status:** 📋 Pending
**Depends on:** #33
**Effort:** 16 hours (2 days)
**Description:** Renal survival analysis with Kaplan-Meier curves.
**Features:**
- D3.js Kaplan-Meier plot
- Survival by variant type (truncating vs non-truncating)
- Survival by 17q deletion status
- Censoring indicators
- Log-rank test p-values
- Risk tables below curves

**Note:** Requires temporal data (age at CKD stages, age at dialysis/transplant)

### Phase 6: Polish & Testing (P1 - High Priority)

#### Issue #48: `test(frontend): add E2E tests for critical user flows`
**Status:** 📋 Pending
**Depends on:** All Phase 1 issues
**Effort:** 16 hours (2 days)
**Description:** Comprehensive E2E testing with Playwright.
**Test Coverage:**
- Search → Individual detail → Variant navigation
- Aggregations dashboard all charts
- Publication → Individual links
- Filter and sort operations

#### Issue #49: `fix(frontend): remove all v1 legacy code`
**Status:** 📋 Pending
**Depends on:** All Phase 1-2 issues
**Effort:** 8 hours (1 day)
**Description:** Clean up deprecated v1 code.
**Tasks:**
- Remove old API functions
- Remove unused components
- Remove legacy routes
- Update documentation

#### Issue #50: `docs(frontend): update user documentation`
**Status:** 📋 Pending
**Depends on:** #49
**Effort:** 6 hours (1 day)
**Description:** Complete user-facing documentation.

## Feature Requirements Mapping

Based on your notes, here's how each feature maps to issues:

| Your Note | Issue(s) | Status |
|-----------|----------|--------|
| Suchfeld für individuen, varianten, publication | #39, #41 | 📋 Pending |
| Tabellen für individuals + navigation | #31, #32 | ✅ Done |
| Individual detail page with all info | #32 | ✅ Done |
| Variants view + detail | #34, #35 | 📋 Pending |
| Publications view + detail | #36, #37 | ✅ MVP / 📋 Enhanced (needs #51-#53) |
| Aggregations mit donut plots | #33 | 📋 Pending |
| Zeitplan/timeline for publications | #43 | 📋 Pending |
| Phenotypes as stacked bar charts | #42 | 📋 Pending |
| Gruppen vergleiche (T vs nT, 17q, etc.) | #45, #46 | 📋 Pending |
| Renal survival curve (Kaplan-Meier) | #47 | 📋 Pending |
| Anzahl phenotypes histogram | #44 | 📋 Pending |
| CAKUT vs CAKUT/MODY comparison | #46 | 📋 Pending |

## Timeline Estimate

| Phase | Issues | Effort | Duration |
|-------|--------|--------|----------|
| Phase 1: Core Views | #33-#38 | 50 hours | 6.5 days |
| Phase 2: Search | #39-#41 | 22 hours | 3 days |
| Phase 3: Visualizations | #42-#44 | 20 hours | 2.5 days |
| Phase 4: Comparisons | #45-#46 | 22 hours | 3 days |
| Phase 5: Survival | #47 | 16 hours | 2 days |
| Phase 6: Polish | #48-#50 | 30 hours | 4 days |
| **Total** | **17 issues** | **160 hours** | **21 days (4 weeks)** |

**Note:** This is development time only, does not include code review, testing, or rework.

## Dependencies Graph

```
Phase 1 (Core Views):
  #30 (API client) ✅
    ├── #33 (Aggregations) ✅
    ├── #34 (Variants view)
    │     └── #35 (Variant detail)
    ├── #36 (Publications view) ✅
    │     └── #37 (Publication detail) ✅ Phase 1 | 📋 Phase 2 (needs #51, #52, #53)
    └── #38 (Home stats) ✅

Phase 2 (Search):
  #30 ✅
    └── #39 (Global search)
          └── #41 (Search results)

Phase 3 (Visualizations):
  #33
    ├── #42 (Phenotype bars)
    ├── #44 (Histogram)
    └── #47 (Survival curves)
  #36
    └── #43 (Timeline)

Phase 4 (Comparisons):
  #33, #34
    ├── #45 (Variant comparisons)
    └── #46 (Clinical comparisons)

Phase 6 (Polish):
  All Phase 1-2
    ├── #48 (E2E tests)
    ├── #49 (Cleanup)
    └── #50 (Docs)
```

## Success Criteria

### Functional
- [ ] All views migrated from v1 to v2 API
- [ ] No 404 errors from old endpoints
- [ ] Search works across all data types
- [ ] All aggregations display correctly
- [ ] Comparisons show statistical differences

### Performance
- [ ] Initial page load < 2 seconds
- [ ] Search results < 500ms
- [ ] Aggregations render < 1 second
- [ ] No N+1 query problems

### Code Quality
- [ ] ESLint passes with no warnings
- [ ] No console errors
- [ ] E2E tests pass
- [ ] Documentation updated

### User Experience
- [ ] Responsive on mobile/tablet
- [ ] Intuitive navigation
- [ ] Clear data presentation
- [ ] Helpful error messages

## Risk Mitigation

### Data Availability Risks
| Risk | Mitigation |
|------|------------|
| Missing temporal data for survival curves | Document requirements, implement with mock data, mark as "coming soon" |
| Incomplete phenotype data | Conditional rendering, clear "no data" messages |
| Missing publication dates | Fallback to created_at timestamp |

### Technical Risks
| Risk | Mitigation |
|------|------------|
| D3.js performance with large datasets | Implement pagination, data aggregation |
| Complex statistical calculations in browser | Consider backend computation for survival analysis |
| Browser compatibility | Test on Chrome, Firefox, Safari |

## Labels to Use

**Category Labels:**
- `frontend` - All issues
- `migration` - Issues #33-40, #49
- `visualization` - Issues #42-43, #47
- `feature` - Issues #39-46
- `testing` - Issue #48
- `documentation` - Issue #50

**Priority Labels:**
- `p0-critical` - Milestone itself
- `p1-high` - Phase 1, 2, 6 issues
- `p2-medium` - Phase 3, 4 issues
- `p3-low` - Phase 5 issues

**Type Labels:**
- `feat` - Issues #34-46
- `fix` - Issues #33, #49
- `test` - Issue #48
- `docs` - Issue #50

**Component Labels:**
- `views` - Issues #34-38
- `components` - Issues #42-46
- `api-client` - Issues #39-40
- `charts` - Issues #42-46

## Backend Issues for Publication Enhancements

Three new backend issues were created to unblock Issue #37 Phase 2:

### Issue #51: `feat(backend): add PubMed API integration with database caching`
**Effort:** 12 hours (1.5 days)
**Description:** Fetch and cache publication metadata from PubMed API
- Creates `publication_metadata` table with 90-day TTL
- Implements `/publications/{pmid}/metadata` endpoint
- Cache warming script for known PMIDs
- Handles rate limiting and errors gracefully

See: `docs/issues/issue-51-backend-pubmed-api.md`

### Issue #52: `feat(backend): add /by-publication/{pmid} phenopackets endpoint`
**Effort:** 8 hours (1 day)
**Description:** Server-side filtering for phenopackets by publication
- Creates `/phenopackets/by-publication/{pmid}` endpoint
- GIN index on `externalReferences` for performance
- Replaces client-side filtering (7x performance improvement)
- Supports pagination and filters

See: `docs/issues/issue-52-backend-publication-endpoint.md`

### Issue #53: `feat(backend): add publication summary statistics endpoint`
**Effort:** 8 hours (1 day)
**Description:** Aggregated statistics per publication
- Creates `/aggregate/publication-summary/{pmid}` endpoint
- Sex distribution, common phenotypes, variant statistics
- Query completes in < 200ms
- Percentages for top 10 phenotypes

See: `docs/issues/issue-53-backend-publication-aggregation.md`

**Templates:** GitHub issue templates available in `docs/issues/github-templates-34-52.md`

## Next Steps

1. **Create milestone in GitHub:**
   ```
   Name: Frontend Phenopackets v2 Migration
   Description: Complete migration of frontend to GA4GH Phenopackets v2 backend
   Due date: [Set based on team capacity]
   ```

2. **Create issues #34-49** using templates in `docs/issues/`

3. **Create backend issues #51-52** using templates in `docs/issues/github-templates-34-52.md`

4. **Prioritize Phase 1** - Core views must work first

5. **Implement incrementally** - Each issue is independently testable

6. **Track progress** - Update this document as issues close
