# Frontend Phenopackets v2 Migration - Quick Reference

## Milestone Information

**Name:** `frontend-phenopackets-v2-migration`

**Description:** Complete migration of frontend from v1 normalized schema to GA4GH Phenopackets v2 JSONB-based backend, with enhanced visualizations and analytics.

**Priority:** P0 (Critical) - Blocking production release

**Timeline:** ~4 weeks (160 hours development time)

## GitHub Labels to Create

### Category Labels
```
frontend          - Frontend code changes
migration         - Migration from v1 to v2
phenopackets      - GA4GH Phenopackets related
visualization     - Charts and graphs
feature           - New functionality
```

### Priority Labels
```
p0-critical      - Blocking production
p1-high          - Core functionality
p2-medium        - Important but not blocking
p3-low           - Nice to have
```

### Component Labels
```
views            - Vue view components
components       - Reusable components
api-client       - API service layer
charts           - D3.js visualizations
```

## Issue Status Overview

| Status | Count | Issues |
|--------|-------|--------|
| ✅ Completed | 3 | #30, #31, #32 |
| 📋 Pending | 17 | #33-#49 |
| **Total** | **20** | |

## Issues by Phase

### Phase 1: Core Views Migration (P1) - 6.5 days
**Goal:** All basic views working with v2 API

- [ ] **#33** `fix(frontend): update aggregation endpoints for phenopacket format` (1.5d)
- [ ] **#34** `feat(frontend): migrate variants view to phenopacket interpretations` (2d) ⚠️ Needs backend
- [ ] **#35** `feat(frontend): migrate variant detail page to interpretation view` (1.5d)
- [ ] **#36** `feat(frontend): migrate publications view to external references` (1d)
- [ ] **#37** `feat(frontend): migrate publication detail page` (1d)
- [ ] **#38** `feat(frontend): migrate home page statistics to v2 API` (0.5d)

### Phase 2: Search & Navigation (P1) - 3 days
**Goal:** Universal search working

- [ ] **#39** `feat(frontend): implement global phenopacket search` (2d)
- [ ] **#40** `feat(frontend): implement search results with faceted filtering` (1.5d)

### Phase 3: Enhanced Visualizations (P2) - 2.5 days
**Goal:** Rich data visualizations

- [ ] **#41** `feat(frontend): add phenotype distribution stacked bar chart` (1d)
- [ ] **#42** `feat(frontend): add publication timeline visualization` (1d)
- [ ] **#43** `feat(frontend): add phenotype count histogram` (1d)

### Phase 4: Cohort Comparisons (P2) - 3 days
**Goal:** Statistical comparisons between groups

- [ ] **#44** `feat(frontend): add variant type comparison view` (2d)
- [ ] **#45** `feat(frontend): add clinical subgroup comparisons` (1.5d)

### Phase 5: Survival Analysis (P3) - 2 days
**Goal:** Kaplan-Meier curves

- [ ] **#46** `feat(frontend): implement Kaplan-Meier survival curves` (2d) ⚠️ Needs temporal data

### Phase 6: Polish & Testing (P1) - 4 days
**Goal:** Production-ready quality

- [ ] **#47** `test(frontend): add E2E tests for critical user flows` (2d)
- [ ] **#48** `fix(frontend): remove all v1 legacy code` (1d)
- [ ] **#49** `docs(frontend): update user documentation` (1d)

## Critical Path

```
#30 ✅ (API client)
  ├─> #33 (Aggregations)
  │     ├─> #41, #43, #44, #45 (Visualizations & Comparisons)
  │     └─> #46 (Survival curves)
  │
  ├─> #34 (Variants view) ⚠️ BACKEND BLOCKER
  │     └─> #35 (Variant detail)
  │
  ├─> #36 (Publications view)
  │     ├─> #37 (Publication detail)
  │     └─> #42 (Timeline viz)
  │
  ├─> #38 (Home stats)
  │
  └─> #39 (Global search)
        └─> #40 (Search results)

All Phase 1-2 completed
  └─> #47, #48, #49 (Polish & testing)
```

## Backend Dependencies

These issues require NEW backend endpoints:

| Issue | Endpoint Needed | Priority |
|-------|----------------|----------|
| #34 | `GET /api/v2/phenopackets/aggregate/variants` | P1 - BLOCKER |
| #35 | `GET /api/v2/phenopackets/by-variant/{id}` | P1 - BLOCKER |
| #39 | `POST /api/v2/phenopackets/search` (enhanced) | P1 |
| #44 | `GET /api/v2/phenopackets/aggregate/compare-groups` | P2 |
| #46 | `GET /api/v2/phenopackets/aggregate/survival-data` | P3 |

**Action:** Create backend issues for these endpoints BEFORE starting frontend work.

## Feature-to-Issue Mapping

| Your Requirement | Issue(s) | Priority | Status |
|------------------|----------|----------|--------|
| Suchfeld für individuen, varianten, publication | #39, #40 | P1 | 📋 |
| Tabellen für individuals + navigation | #31, #32 | P1 | ✅ |
| Individual detail page | #32 | P1 | ✅ |
| Variants view + detail | #34, #35 | P1 | 📋 |
| Publications view + detail | #36, #37 | P1 | 📋 |
| Aggregations mit donut plots | #33 | P1 | 📋 |
| Zeitplan/timeline for publications | #42 | P2 | 📋 |
| Phenotypes stacked bar charts | #41 | P2 | 📋 |
| Gruppen vergleiche (T vs nT, 17q, etc.) | #44, #45 | P2 | 📋 |
| Renal survival curve | #46 | P3 | 📋 |
| Anzahl phenotypes histogram | #43 | P2 | 📋 |
| CAKUT vs CAKUT/MODY | #45 | P2 | 📋 |

## How to Use This Plan

### 1. Update Existing Issues

You can edit issues #33-40 to match these plans:

```bash
# For each issue, copy content from:
docs/issues/issue-##-<descriptive-name>.md

# To GitHub issue #33, #34, etc.
```

### 2. Create New Issues #41-49

Create issues with proper titles following convention:
```
feat(frontend): add phenotype distribution stacked bar chart
test(frontend): add E2E tests for critical user flows
```

### 3. Create GitHub Milestone

```
Name: Frontend Phenopackets v2 Migration
Description: Complete migration of frontend to GA4GH Phenopackets v2 backend
Due date: [4 weeks from start]
```

### 4. Apply Labels

For each issue:
- Add category labels: `frontend`, `migration` (if applicable), `phenopackets`
- Add priority label: `p1-high`, `p2-medium`, or `p3-low`
- Add component label: `views`, `components`, `charts`, etc.
- Add type from title: `feat`, `fix`, `test`, `docs`

### 5. Set Dependencies

In GitHub:
- Mark backend blockers
- Link dependent issues
- Track with project board

### 6. Start with Phase 1

**Recommended order:**
1. #38 (Home stats) - Simplest, tests API connection
2. #33 (Aggregations) - Core functionality
3. #36, #37 (Publications) - Independent from variants
4. #34, #35 (Variants) - Wait for backend endpoint
5. #39, #40 (Search) - After basic views work

## Success Metrics

Track these weekly:

- [ ] Issues closed vs. planned
- [ ] Zero 404 errors from old endpoints
- [ ] Zero console errors on any page
- [ ] ESLint passes with no warnings
- [ ] All views load < 2 seconds

## Risk Mitigation

### High Risk Areas

1. **Variant aggregation complexity**
   - Mitigation: Start backend work early, use mock data if needed

2. **Missing temporal data for survival curves**
   - Mitigation: Mark as "Coming Soon", implement with sample data

3. **D3.js performance with large datasets**
   - Mitigation: Implement pagination, server-side aggregation

## Quick Start Checklist

- [ ] Create GitHub milestone `frontend-phenopackets-v2-migration`
- [ ] Create/apply all labels listed above
- [ ] Update issue #33 with new plan
- [ ] Create backend issues for required endpoints
- [ ] Start with #38 (easiest win)
- [ ] Set up weekly progress tracking
- [ ] Update MIGRATION-SUMMARY.md as issues close

## Questions?

See detailed plans in:
- `docs/issues/MILESTONE-frontend-phenopackets-migration.md` - Full breakdown
- `docs/issues/issue-##-*.md` - Individual issue plans
- `CLAUDE.md` - Issue management guidelines
