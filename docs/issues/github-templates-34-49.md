# GitHub Issue Templates #34-#49

Copy these templates to create GitHub issues.

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

## Summary
Show all phenopackets linked to a specific publication (PMID).

**Current:** `/publications/:pmid` → 404
**Target:** `/publications/:pmid` → Display publication + linked phenopackets

## Details
See: [docs/issues/issue-37-40-batch.md](../docs/issues/issue-37-40-batch.md)

## Acceptance Criteria
- [ ] Displays publication metadata (title, authors, journal)
- [ ] Shows all phenopackets citing this publication
- [ ] Summary stats (total individuals, sex distribution)
- [ ] Common phenotypes among individuals
- [ ] Links to PubMed, DOI

## Dependencies
- Issue #36 (Publications view)
- **Backend:** Create `/by-publication/{pmid}` endpoint

## Priority
**P1 (High)**

## Labels
`frontend`, `views`, `phenopackets`, `p1`
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
See: [docs/issues/issue-37-40-batch.md](../docs/issues/issue-37-40-batch.md)

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

## Issue #40

```markdown
# feat(frontend): implement search results with faceted filtering

## Summary
Enhanced search results page with sidebar filters and dynamic counts.

**Target:** Search results with sidebar faceted filters

## Details
See: [docs/issues/issue-37-40-batch.md](../docs/issues/issue-37-40-batch.md)

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

## Issue #41

```markdown
# feat(frontend): add phenotype distribution stacked bar chart

## Summary
Stacked bar chart showing HPO term presence/absence across phenopackets.

**Target:** Interactive D3.js visualization in aggregations dashboard

## Details
See: [docs/issues/issue-41-46-visualizations.md](../docs/issues/issue-41-46-visualizations.md)

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

## Issue #42

```markdown
# feat(frontend): add publication timeline visualization

## Summary
D3.js timeline showing phenopackets added over time by publication.

**Target:** Timeline chart in aggregations dashboard

## Details
See: [docs/issues/issue-41-46-visualizations.md](../docs/issues/issue-41-46-visualizations.md)

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

## Issue #43

```markdown
# feat(frontend): add phenotype count histogram

## Summary
Histogram showing distribution of phenotype counts per individual.

**Target:** D3.js histogram with comparison overlays

## Details
See: [docs/issues/issue-41-46-visualizations.md](../docs/issues/issue-41-46-visualizations.md)

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

## Issue #44

```markdown
# feat(frontend): add variant type comparison view

## Summary
Side-by-side comparison of phenotype distributions between variant types.

**Target:** Comparison dashboard (truncating vs non-truncating, 17q vs point mutations)

## Details
See: [docs/issues/issue-41-46-visualizations.md](../docs/issues/issue-41-46-visualizations.md)

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

## Issue #45

```markdown
# feat(frontend): add clinical subgroup comparisons

## Summary
Compare phenotypes across clinical subgroups (CAKUT vs MODY, CKD stages, etc.)

**Target:** Reusable comparison component for multiple subgroups

## Details
See: [docs/issues/issue-41-46-visualizations.md](../docs/issues/issue-41-46-visualizations.md)

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

## Issue #46

```markdown
# feat(frontend): implement Kaplan-Meier survival curves

## Summary
Renal survival analysis with Kaplan-Meier curves.

**Target:** D3.js survival curves grouped by variant type

## Details
See: [docs/issues/issue-41-46-visualizations.md](../docs/issues/issue-41-46-visualizations.md)

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

## Issue #47

```markdown
# test(frontend): add E2E tests for critical user flows

## Summary
Comprehensive Playwright E2E tests for all critical workflows.

**Target:** 90%+ coverage of user flows

## Details
See: [docs/issues/issue-47-49-polish.md](../docs/issues/issue-47-49-polish.md)

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

## Issue #48

```markdown
# fix(frontend): remove all v1 legacy code

## Summary
Clean up deprecated v1 code after migration complete.

**Target:** Zero v1 references, clean codebase

## Details
See: [docs/issues/issue-47-49-polish.md](../docs/issues/issue-47-49-polish.md)

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

## Issue #49

```markdown
# docs(frontend): update user documentation

## Summary
Complete user-facing documentation for phenopackets v2 frontend.

**Target:** User guide, developer guide, API reference, changelog

## Details
See: [docs/issues/issue-47-49-polish.md](../docs/issues/issue-47-49-polish.md)

## Acceptance Criteria
- [ ] User guide written (getting started, features, FAQ)
- [ ] Developer guide updated (setup, architecture, testing)
- [ ] API reference documented (all v2 endpoints)
- [ ] Changelog created (v2.0.0 release notes)
- [ ] README updated with new features
- [ ] Screenshots added
- [ ] All docs reviewed and proofread

## Dependencies
- Issue #48 (Cleanup done)

## Priority
**P1 (High)** - Production ready

## Labels
`documentation`, `p1`
```
