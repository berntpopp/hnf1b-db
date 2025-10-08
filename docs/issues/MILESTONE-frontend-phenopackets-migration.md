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

### 🔄 In Progress
- None

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
**Status:** 📋 Pending
**Depends on:** #36
**Effort:** 6 hours (1 day)
**Description:** Show all phenopackets linked to a specific publication.

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

#### Issue #40: `feat(frontend): implement search results with faceted filtering`
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

#### Issue #41: `feat(frontend): add phenotype distribution stacked bar chart`
**Status:** 📋 Pending
**Depends on:** #33
**Effort:** 8 hours (1 day)
**Description:** Visualize HPO term frequencies across phenopackets.
**Visualization:**
- Stacked bar chart: phenotype presence/absence
- Group by clinical categories (renal, diabetes, genital)
- Show percentage distribution

#### Issue #42: `feat(frontend): add publication timeline visualization`
**Status:** 📋 Pending
**Depends on:** #36
**Effort:** 6 hours (1 day)
**Description:** Timeline of phenopackets by publication date.
**Visualization:**
- D3.js timeline plot
- Show phenopackets added over time
- Group by publication

#### Issue #43: `feat(frontend): add phenotype count histogram`
**Status:** 📋 Pending
**Depends on:** #33
**Effort:** 6 hours (1 day)
**Description:** Distribution of phenotype counts per individual.
**Visualization:**
- Histogram: X=number of phenotypes, Y=count of individuals
- Separate histograms for CAKUT vs MODY

### Phase 4: Cohort Comparisons (P2 - Medium Priority)

#### Issue #44: `feat(frontend): add variant type comparison view`
**Status:** 📋 Pending
**Depends on:** #33, #34
**Effort:** 12 hours (2 days)
**Description:** Compare phenotype distributions between variant types.
**Features:**
- Compare truncating vs non-truncating variants
- Compare 17q deletion vs point mutations
- Side-by-side donut/bar charts
- Statistical significance indicators

#### Issue #45: `feat(frontend): add clinical subgroup comparisons`
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

#### Issue #46: `feat(frontend): implement Kaplan-Meier survival curves`
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

#### Issue #47: `test(frontend): add E2E tests for critical user flows`
**Status:** 📋 Pending
**Depends on:** All Phase 1 issues
**Effort:** 16 hours (2 days)
**Description:** Comprehensive E2E testing with Playwright.
**Test Coverage:**
- Search → Individual detail → Variant navigation
- Aggregations dashboard all charts
- Publication → Individual links
- Filter and sort operations

#### Issue #48: `fix(frontend): remove all v1 legacy code`
**Status:** 📋 Pending
**Depends on:** All Phase 1-2 issues
**Effort:** 8 hours (1 day)
**Description:** Clean up deprecated v1 code.
**Tasks:**
- Remove old API functions
- Remove unused components
- Remove legacy routes
- Update documentation

#### Issue #49: `docs(frontend): update user documentation`
**Status:** 📋 Pending
**Depends on:** #48
**Effort:** 6 hours (1 day)
**Description:** Complete user-facing documentation.

## Feature Requirements Mapping

Based on your notes, here's how each feature maps to issues:

| Your Note | Issue(s) | Status |
|-----------|----------|--------|
| Suchfeld für individuen, varianten, publication | #39, #40 | 📋 Pending |
| Tabellen für individuals + navigation | #31, #32 | ✅ Done |
| Individual detail page with all info | #32 | ✅ Done |
| Variants view + detail | #34, #35 | 📋 Pending |
| Publications view + detail | #36, #37 | 📋 Pending |
| Aggregations mit donut plots | #33 | 📋 Pending |
| Zeitplan/timeline for publications | #42 | 📋 Pending |
| Phenotypes as stacked bar charts | #41 | 📋 Pending |
| Gruppen vergleiche (T vs nT, 17q, etc.) | #44, #45 | 📋 Pending |
| Renal survival curve (Kaplan-Meier) | #46 | 📋 Pending |
| Anzahl phenotypes histogram | #43 | 📋 Pending |
| CAKUT vs CAKUT/MODY comparison | #45 | 📋 Pending |

## Timeline Estimate

| Phase | Issues | Effort | Duration |
|-------|--------|--------|----------|
| Phase 1: Core Views | #33-#38 | 50 hours | 6.5 days |
| Phase 2: Search | #39-#40 | 22 hours | 3 days |
| Phase 3: Visualizations | #41-#43 | 20 hours | 2.5 days |
| Phase 4: Comparisons | #44-#45 | 22 hours | 3 days |
| Phase 5: Survival | #46 | 16 hours | 2 days |
| Phase 6: Polish | #47-#49 | 30 hours | 4 days |
| **Total** | **17 issues** | **160 hours** | **21 days (4 weeks)** |

**Note:** This is development time only, does not include code review, testing, or rework.

## Dependencies Graph

```
Phase 1 (Core Views):
  #30 (API client) ✅
    ├── #33 (Aggregations)
    ├── #34 (Variants view)
    │     └── #35 (Variant detail)
    ├── #36 (Publications view)
    │     └── #37 (Publication detail)
    └── #38 (Home stats)

Phase 2 (Search):
  #30 ✅
    └── #39 (Global search)
          └── #40 (Search results)

Phase 3 (Visualizations):
  #33
    ├── #41 (Phenotype bars)
    ├── #43 (Histogram)
    └── #46 (Survival curves)
  #36
    └── #42 (Timeline)

Phase 4 (Comparisons):
  #33, #34
    ├── #44 (Variant comparisons)
    └── #45 (Clinical comparisons)

Phase 6 (Polish):
  All Phase 1-2
    ├── #47 (E2E tests)
    ├── #48 (Cleanup)
    └── #49 (Docs)
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
- `migration` - Issues #33-40, #48
- `visualization` - Issues #41-43, #46
- `feature` - Issues #39-46
- `testing` - Issue #47
- `documentation` - Issue #49

**Priority Labels:**
- `p0-critical` - Milestone itself
- `p1-high` - Phase 1, 2, 6 issues
- `p2-medium` - Phase 3, 4 issues
- `p3-low` - Phase 5 issues

**Type Labels:**
- `feat` - Issues #34-46
- `fix` - Issues #33, #48
- `test` - Issue #47
- `docs` - Issue #49

**Component Labels:**
- `views` - Issues #34-38
- `components` - Issues #41-46
- `api-client` - Issues #39-40
- `charts` - Issues #41-46

## Next Steps

1. **Create milestone in GitHub:**
   ```
   Name: Frontend Phenopackets v2 Migration
   Description: Complete migration of frontend to GA4GH Phenopackets v2 backend
   Due date: [Set based on team capacity]
   ```

2. **Create issues #33-49** using templates in `docs/issues/`

3. **Prioritize Phase 1** - Core views must work first

4. **Implement incrementally** - Each issue is independently testable

5. **Track progress** - Update this document as issues close
