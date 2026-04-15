# Branching Strategy - Frontend Phenopackets v2 Migration

## Overview

This document outlines the branching strategy for migrating the frontend to work with the GA4GH Phenopackets v2 backend. The strategy prioritizes getting a **Minimum Viable Product (MVP)** on the `main` branch first, then using feature branches for additional functionality.

## Current Status

### ✅ Completed on `main`
- **#30** - API client migration to v2 format
- **#31** - Phenopackets list view
- **#32** - Phenopacket detail page

### 📋 Issues Created (Up to #39)
Issues #33-#39 are created in GitHub and ready for implementation.

---

## Phase 1: MVP on `main` Branch

**Goal:** Get basic frontend functionality working with v2 backend before branching.

**Timeline:** 3-4 days

**Why on `main`?**
- Core functionality needed for any testing
- Small, incremental changes
- Quick wins to verify full-stack integration
- Establishes stable base for feature branches

### Issue #38: Home Page Statistics (Day 1)
**Branch:** `main`
**Time:** 6 hours (1 day)
**Type:** Full-stack (backend + frontend)

**Why first?**
- Simplest full-stack integration test
- Highly visible (home page)
- No dependencies on other issues
- Tests `/aggregate/summary` endpoint

**Implementation:**
1. Backend: Create `/api/v2/phenopackets/aggregate/summary` endpoint
2. Frontend: Update `Home.vue` to call new endpoint
3. Test: Verify stats display correctly

**Acceptance Criteria:**
- Home page loads without errors
- Shows correct counts (phenopackets, variants, diseases)
- Numbers animate smoothly
- No 404 errors in console

**Commit:**
```bash
git commit -m "feat: implement home page statistics (#38)"
```

---

### Issue #36: Publications View (Day 2)
**Branch:** `main`
**Time:** 8 hours (1 day)
**Type:** Frontend only

**Why second?**
- Independent from variants (no backend blockers)
- Uses existing data in phenopackets (`metaData.externalReferences[]`)
- No new backend endpoints needed
- Tests JSONB extraction

**Implementation:**
1. Frontend: Create `Publications.vue` view
2. Extract PMIDs from phenopackets
3. Display publication table with phenopacket counts
4. Add sorting and filtering

**Acceptance Criteria:**
- Publications list displays correctly
- Shows PMID, DOI, phenopacket count
- Links to PubMed work
- Clicking phenopacket count filters to individuals

**Commit:**
```bash
git commit -m "feat(frontend): migrate publications view (#36)"
```

---

### Issue #33: Aggregations Dashboard (Days 3-4)
**Branch:** `main`
**Time:** 10 hours (1.5 days)
**Type:** Frontend (uses existing backend endpoints)

**Why third?**
- Core analytics feature
- Enables all future visualizations
- Tests JSONB aggregation performance
- No backend blockers (endpoints exist)

**Implementation:**
1. Update `AggregationsDashboard.vue` to use v2 endpoints
2. Update data fetching for new response format
3. Migrate chart components (DonutChart, StackedBarChart)
4. Test all aggregation categories

**Acceptance Criteria:**
- Dashboard loads without errors
- All aggregations display correctly
- Charts render properly
- Performance < 500ms per aggregation

**Commit:**
```bash
git commit -m "fix(frontend): update aggregation endpoints (#33)"
```

---

## 📍 MVP Checkpoint

**After completing #38, #36, #33, you have:**

✅ **Functional Basic Frontend:**
- Home page working (statistics display)
- Phenopackets list + detail (browse individuals)
- Publications view (browse papers)
- Aggregations dashboard (basic analytics)
- API client fully functional
- Zero 404 errors on core pages

✅ **Production-Ready Core Features:**
- Users can browse phenopackets
- Users can view individual details
- Users can see publications
- Users can view basic statistics
- All pages load without errors

**This is your MVP - safe to branch!**

---

## Phase 2: Feature Branches

After MVP is complete and merged to `main`, create feature branches for remaining work.

### Feature Branch 1: `feature/variants-migration`

**Issues:** #34, #35
**Timeline:** 2 days (after backend endpoints ready)
**Type:** Frontend + backend dependency

#### Required Backend Work (BLOCKERS)

**Create these backend issues FIRST:**

```markdown
# Backend Issue 1
Title: feat(backend): add /aggregate/variants endpoint for variants view

Description:
Create aggregation endpoint to extract unique variants from phenopacket interpretations.

Endpoint: GET /api/v2/phenopackets/aggregate/variants
Query params: limit, pathogenicity, gene

See detailed specification:
docs/issues/issue-34-migrate-variants-view.md (Backend Endpoint Specification section)

Acceptance Criteria:
- Returns unique variants across all phenopackets
- Deduplicates by VRS ID
- Shows phenopacket count per variant
- Response time < 500ms
- Unit tests pass

Priority: P1 (High) - Blocking frontend issue #34
Labels: backend, api, aggregation, p1
```

```markdown
# Backend Issue 2
Title: feat(backend): add /by-variant/{id} endpoint for variant details

Description:
Create endpoint to show all phenopackets containing a specific variant.

Endpoint: GET /api/v2/phenopackets/by-variant/{variant_id}
Path params: variant_id (VRS ID or genomic coordinate)

See detailed specification:
docs/issues/issue-35-migrate-variant-detail-page.md (Backend Endpoint Specification section)

Acceptance Criteria:
- Matches variants by VRS ID, coordinates, or label
- Returns variant metadata + phenopackets list
- Response time < 200ms for summaries
- Handles missing VRS IDs gracefully
- Unit tests pass

Priority: P1 (High) - Blocking frontend issue #35
Labels: backend, api, p1
```

#### Frontend Work

**After backend endpoints are ready:**

```bash
# Create feature branch from main
git checkout main
git pull origin main
git checkout -b feature/variants-migration

# Work on #34
# Implement Variants.vue to call /aggregate/variants
git commit -m "feat(frontend): migrate variants view (#34)"

# Work on #35
# Implement PageVariant.vue to call /by-variant/{id}
git commit -m "feat(frontend): migrate variant detail page (#35)"

# Push feature branch
git push origin feature/variants-migration

# Create Pull Request
# Title: feat(frontend): migrate variants views to v2 API (#34, #35)
```

**Time:** 16 hours (2 days)

**Acceptance Criteria:**
- Variants list displays correctly
- Variant detail page shows all affected individuals
- HGNC gene links work
- Pathogenicity color-coded
- No 404 errors

---

### Feature Branch 2: `feature/search-implementation`

**Issues:** #39, #40
**Timeline:** 3 days
**Type:** Frontend + moderate backend enhancement

#### Backend Work Needed

**Enhance existing `/search` endpoint:**

```markdown
# Backend Issue
Title: feat(backend): enhance /search endpoint with full-text search

Description:
Add PostgreSQL full-text search (tsvector) to phenopackets search endpoint.

Enhancements:
- Add tsvector generated column for full-text search
- Support search by subject ID, HPO terms, genes, variants, PMIDs
- Add autocomplete endpoint: /ontology/hpo/autocomplete
- Return search relevance ranking

See detailed specification:
docs/issues/issue-37-40-batch.md (Search Architecture section)

Acceptance Criteria:
- Full-text search works (< 200ms)
- Autocomplete returns suggestions (< 100ms)
- Supports filtering by sex, has_variants, pathogenicity
- GIN indexes created
- Unit tests pass

Priority: P1 (High) - Required for search feature
Labels: backend, api, search, p1
```

#### Frontend Work

```bash
# Create feature branch from main
git checkout main
git pull origin main
git checkout -b feature/search-implementation

# Work on #39
# Implement GlobalSearch.vue component with autocomplete
git commit -m "feat(frontend): implement global phenopacket search (#39)"

# Work on #40
# Implement SearchResults.vue with faceted filters
git commit -m "feat(frontend): implement search results with faceted filtering (#40)"

# Push feature branch
git push origin feature/search-implementation

# Create Pull Request
```

**Time:** 22 hours (3 days)

**Acceptance Criteria:**
- Search bar in navigation works
- Autocomplete suggests HPO terms, genes
- Results page shows filtered phenopackets
- Faceted filters update counts dynamically
- Shareable URLs with query params

---

### Feature Branch 3: `feature/visualizations`

**Issues:** #41, #42, #43
**Timeline:** 2.5 days
**Type:** Frontend only (pure D3.js)

**No backend dependencies!** Can work in parallel with other branches.

```bash
# Create feature branch from main
git checkout main
git pull origin main
git checkout -b feature/visualizations

# Work on #41 - Phenotype distribution stacked bar chart
git commit -m "feat(frontend): add phenotype distribution stacked bar chart (#41)"

# Work on #42 - Publication timeline
git commit -m "feat(frontend): add publication timeline visualization (#42)"

# Work on #43 - Phenotype count histogram
git commit -m "feat(frontend): add phenotype count histogram (#43)"

# Push feature branch
git push origin feature/visualizations

# Create Pull Request
```

**Time:** 20 hours (2.5 days)

**Acceptance Criteria:**
- All charts render correctly with D3.js
- Interactive tooltips work
- Charts responsive to window size
- Smooth transitions/animations
- No performance issues with large datasets

---

### Feature Branch 4: `feature/comparisons`

**Issues:** #44, #45
**Timeline:** 3 days
**Type:** Frontend + backend aggregation

**Backend work needed:** `/aggregate/compare-groups` endpoint

```bash
# Create feature branch from main
git checkout main
git pull origin main
git checkout -b feature/comparisons

# Work on #44 - Variant type comparisons
git commit -m "feat(frontend): add variant type comparison view (#44)"

# Work on #45 - Clinical subgroup comparisons
git commit -m "feat(frontend): add clinical subgroup comparisons (#45)"

# Push feature branch
git push origin feature/comparisons

# Create Pull Request
```

**Time:** 22 hours (3 days)

---

### Feature Branch 5: `feature/polish`

**Issues:** #47, #48, #49
**Timeline:** 4 days
**Type:** Testing, cleanup, documentation

**When:** After all Phase 1-2 features complete

```bash
# Create feature branch from main
git checkout main
git pull origin main
git checkout -b feature/polish

# Work on #47 - E2E tests
git commit -m "test(frontend): add E2E tests for critical user flows (#47)"

# Work on #48 - Remove v1 code
git commit -m "fix(frontend): remove all v1 legacy code (#48)"

# Work on #49 - Documentation
git commit -m "docs(frontend): update user documentation (#49)"

# Push feature branch
git push origin feature/polish

# Create Pull Request
```

**Time:** 28 hours (4 days)

---

## Branching Workflow Summary

```
main (protected)
├── ✅ #30, #31, #32 (completed)
├── 🔥 #38 (home stats) ← Do on main
├── 🔥 #36 (publications) ← Do on main
├── 🔥 #33 (aggregations) ← Do on main
│
│   📍 MVP COMPLETE - Branch here!
│
├── feature/variants-migration (PR #1)
│   ├── #34 (variants view)
│   └── #35 (variant detail)
│
├── feature/search-implementation (PR #2)
│   ├── #39 (global search)
│   └── #40 (search results)
│
├── feature/visualizations (PR #3)
│   ├── #41 (phenotype distribution)
│   ├── #42 (publication timeline)
│   └── #43 (phenotype histogram)
│
├── feature/comparisons (PR #4)
│   ├── #44 (variant type comparison)
│   └── #45 (clinical subgroups)
│
└── feature/polish (PR #5)
    ├── #47 (E2E tests)
    ├── #48 (cleanup v1 code)
    └── #49 (documentation)
```

---

## Pull Request Guidelines

### PR Title Format
```
feat(frontend): [brief description] (#issue-numbers)
```

**Examples:**
- `feat(frontend): migrate variants views to v2 API (#34, #35)`
- `feat(frontend): implement global search feature (#39, #40)`
- `feat(frontend): add D3.js visualizations (#41, #42, #43)`

### PR Description Template

```markdown
## Summary
Brief description of changes (1-2 sentences)

## Issues
Closes #XX, Closes #YY

## Changes
- Bullet list of key changes
- Component additions/modifications
- API endpoint changes

## Testing
- [ ] Manual testing completed
- [ ] No console errors
- [ ] Works in dev environment
- [ ] ESLint passes

## Screenshots
(If applicable - especially for UI changes)

## Dependencies
- Requires backend PR #XX (if applicable)
- Depends on branch YYY (if applicable)
```

---

## Merge Strategy

### For Feature Branches

1. **Create PR** from feature branch to `main`
2. **Request review** from team
3. **Run tests** (ESLint, E2E if available)
4. **Address feedback**
5. **Squash and merge** to keep clean history
6. **Delete branch** after merge

### Merge Order (If possible)

**Ideal order:**
1. `feature/variants-migration` (after backend ready)
2. `feature/search-implementation` (after search backend ready)
3. `feature/visualizations` (independent, can go anytime)
4. `feature/comparisons` (after comparison backend ready)
5. `feature/polish` (last - cleanup and tests)

**Note:** Visualizations can be merged at any time since they have no dependencies.

---

## Conflict Resolution

### If Conflicts Arise

```bash
# Update your feature branch with latest main
git checkout feature/your-branch
git fetch origin
git rebase origin/main

# Resolve conflicts
# ... fix conflicts in files ...
git add .
git rebase --continue

# Force push (since you rebased)
git push origin feature/your-branch --force-with-lease
```

### Avoiding Conflicts

- Keep feature branches short-lived (< 1 week)
- Regularly rebase on `main`
- Coordinate file changes with team
- MVP on `main` first reduces risk

---

## Testing Before Merging

### Feature Branch Testing Checklist

- [ ] ESLint passes: `npm run lint:check`
- [ ] No console errors in browser
- [ ] All new views load correctly
- [ ] API calls work (no 404s)
- [ ] Responsive design works
- [ ] Works with current main branch

### Integration Testing (After Merge)

- [ ] Full smoke test on `main`
- [ ] All pages accessible
- [ ] No regressions in existing features
- [ ] Performance acceptable

---

## Communication

### Before Starting Feature Branch

1. **Announce in team chat:** "Starting work on feature/variants-migration (#34, #35)"
2. **Check for conflicts:** Ensure no one else working on same files
3. **Verify backend status:** If depends on backend, confirm endpoints ready

### During Development

1. **Daily updates:** Brief status in team chat
2. **Blockers:** Immediately communicate if blocked
3. **Changes to plan:** Discuss scope changes before implementing

### Before Merging

1. **PR review request:** Tag reviewers
2. **Demo (if significant UI):** Show changes in team meeting
3. **Deployment plan:** Coordinate with DevOps if needed

---

## Emergency Hotfixes

**If critical bug found on `main`:**

```bash
# Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-bug-description

# Fix bug
git commit -m "fix: critical bug description"

# Create PR immediately
git push origin hotfix/critical-bug-description

# Fast-track review and merge
# No squash - preserve commit
```

---

## Timeline Estimate

| Phase | Duration | Includes |
|-------|----------|----------|
| **MVP on `main`** | 3-4 days | #38, #36, #33 |
| **Feature Branch 1** | 2 days | #34, #35 (after backend) |
| **Feature Branch 2** | 3 days | #39, #40 (parallel with FB1) |
| **Feature Branch 3** | 2.5 days | #41, #42, #43 (parallel) |
| **Feature Branch 4** | 3 days | #44, #45 (after FB3) |
| **Feature Branch 5** | 4 days | #47, #48, #49 (last) |
| **Total** | ~17-18 days | All issues #30-#49 |

**With parallelization:** ~12-14 days calendar time

---

## Success Metrics

### MVP Success (After Phase 1)
- [ ] Zero 404 errors on core pages
- [ ] Home page shows statistics
- [ ] Phenopackets browsable
- [ ] Publications browsable
- [ ] Aggregations work
- [ ] < 2 second page load times

### Full Migration Success (After All Features)
- [ ] All 20 issues closed (#30-#49)
- [ ] Zero v1 code remaining
- [ ] E2E tests passing
- [ ] Documentation complete
- [ ] Production deployment successful

---

## Related Documentation

- **Issue Milestone:** `docs/issues/MILESTONE-frontend-phenopackets-migration.md`
- **Quick Reference:** `docs/issues/MIGRATION-SUMMARY.md`
- **Individual Issues:** `docs/issues/issue-##-*.md`
- **GitHub Templates:** `docs/issues/github-templates-34-49.md`
- **Project Guidelines:** `CLAUDE.md` (Issue Management section)

---

## Questions?

For questions about:
- **Branching strategy:** See this document
- **Issue details:** See `docs/issues/issue-##-*.md`
- **Backend endpoints:** See "Backend Endpoint Specification" sections in issue docs
- **Testing:** See `docs/issues/issue-47-49-polish.md`

**Contact:** Team lead or create GitHub discussion
