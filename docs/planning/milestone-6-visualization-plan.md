# Milestone 6: Data Visualization and Analysis - Implementation Plan

## Overview

**Goal:** Provide comprehensive statistical analysis and interactive visualizations for phenotype-genotype correlations. Deliver publication-ready charts, survival analysis, and comparative tools for research insights.

**Branch:** `feature/milestone-6-data-visualization`

**Issues Covered:** #42-47, #90, #92, #95-96, #99, #116

---

## Implementation Order (Dependency-Based)

### Phase 1: Foundation & Bug Fixes (Critical Path)
**Duration:** 3-4 days | **Priority:** P1 (High)

#### 1.1 Fix Variant Search (#90)
**Effort:** 2-3 hours | **Blocks:** #99, #116

**Why First:** Core functionality needed for all variant-related features

**Tasks:**
- [ ] Identify root cause (API endpoint vs frontend logic)
- [ ] Fix search query parameter passing to backend
- [ ] Implement debounced search (300ms delay)
- [ ] Add loading state and error handling
- [ ] Verify search works for HGVS, coordinates, variant IDs
- [ ] Add search result count display

**Files:**
- `frontend/src/views/Variants.vue` (modify search logic)
- `frontend/src/api/variants.js` (verify API calls)

---

#### 1.2 Fix Zoom Functionality (#92)
**Effort:** 2-3 hours | **Blocks:** #95, #97

**Why Second:** Required for proper visualization interaction

**Tasks:**
- [ ] Debug D3 zoom behavior in `HNF1BGeneVisualization.vue`
- [ ] Fix zoom in `HNF1BProteinVisualization.vue`
- [ ] Implement zoom extent limits (min: 1x, max: 10x)
- [ ] Add pan constraints to prevent off-canvas scrolling
- [ ] Add zoom reset button
- [ ] Ensure zoom persists during data updates
- [ ] Test on mobile/touch devices
- [ ] Add keyboard shortcuts (+ / -, 0 for reset)

**Files:**
- `frontend/src/components/gene/HNF1BGeneVisualization.vue`
- `frontend/src/components/gene/HNF1BProteinVisualization.vue`

---

#### 1.3 Correct HNF1B Domain Coordinates (#95)
**Effort:** 3-4 hours | **Blocks:** #96, #97

**Why Third:** Data accuracy is critical before building infrastructure

**Tasks:**
- [ ] Cross-reference current domain data with UniProt P35680
- [ ] Verify Pfam/InterPro annotations:
  - POU-specific domain (IPR000327)
  - POU homeodomain (IPR001356)
  - Dimerization domain
  - Transactivation domain
- [ ] Update domain boundaries in visualization config
- [ ] Add unit tests for domain coordinate mapping
- [ ] Add source attribution comments (UniProt ID, date)
- [ ] Verify variant positions map correctly to domains
- [ ] Update protein length if incorrect (should be 557 aa)
- [ ] Add automated domain validation tests

**Research:**
- UniProt: https://www.uniprot.org/uniprotkb/P35680/entry
- Pfam: http://pfam.xfam.org/protein/P35680
- InterPro: https://www.ebi.ac.uk/interpro/protein/UniProt/P35680/

**Files:**
- `frontend/src/components/gene/HNF1BProteinVisualization.vue` (lines 300-330)
- `frontend/src/tests/unit/proteinDomains.spec.js` (NEW)

---

### Phase 2: Reference Data Architecture (Foundation for Future Features)
**Duration:** 4-5 days | **Priority:** P1 (High)

#### 2.1 Migrate Genomic Annotations to Database (#96)
**Effort:** 16-20 hours | **Enables:** #97, #99, scalability

**Why Fourth:** Provides single source of truth for all reference data

**Backend Tasks:**
- [ ] Create database schema:
  - `reference_genomes` table (GRCh37, GRCh38, T2T-CHM13)
  - `genes` table (symbol, name, chromosome, start, end, strand, genome_id)
  - `transcripts` table (RefSeq ID, gene_id, exon boundaries, CDS)
  - `protein_domains` table (UniProt/Pfam/InterPro, start, end, name, source, evidence)
  - `exons` table (exon number, genomic coordinates, transcript_id)
- [ ] Create Alembic migration
- [ ] Implement API endpoints:
  - `GET /api/v2/reference/genomes`
  - `GET /api/v2/reference/genes?symbol=HNF1B`
  - `GET /api/v2/reference/genes/{symbol}`
  - `GET /api/v2/reference/genes/{symbol}/transcripts`
  - `GET /api/v2/reference/genes/{symbol}/domains`
  - `GET /api/v2/reference/regions/{chr}:{start}-{end}`
- [ ] Add caching headers (Cache-Control: max-age=86400)
- [ ] Create data migration script:
  - Load HNF1B gene data from NCBI/Ensembl
  - Import protein domains from UniProt P35680
  - Load chr17q12 region genes (12 genes)
  - Add data provenance (source URLs, dates, versions)
- [ ] Write backend tests for reference endpoints

**Frontend Tasks:**
- [ ] Create `frontend/src/api/reference.js` service layer
- [ ] Update `HNF1BProteinVisualization.vue` to fetch domains from API
- [ ] Update `HNF1BGeneVisualization.vue` to fetch gene structure from API
- [ ] Remove hardcoded coordinates from `config/app.js` and `utils/variants.js`
- [ ] Add loading states during reference data fetch
- [ ] Cache reference data in Pinia store
- [ ] Handle API errors gracefully (fallback to last known data)
- [ ] Remove `frontend/src/data/chr17q12_genes.json` after verification

**Files (Backend):**
- `backend/alembic/versions/XXX_add_reference_data.py` (NEW)
- `backend/app/reference/` (NEW module)
  - `models.py` - SQLAlchemy models
  - `schemas.py` - Pydantic schemas
  - `routers.py` - API endpoints
- `backend/scripts/load_reference_data.py` (NEW)
- `backend/tests/test_reference_api.py` (NEW)

**Files (Frontend):**
- `frontend/src/api/reference.js` (NEW)
- `frontend/src/stores/referenceStore.js` (NEW, optional Pinia store)
- `frontend/src/components/gene/HNF1BProteinVisualization.vue` (modify)
- `frontend/src/components/gene/HNF1BGeneVisualization.vue` (modify)

---

### Phase 3: Enhanced Filtering & Search (User Experience)
**Duration:** 2-3 days | **Priority:** P1 (High)

#### 3.1 Advanced Filtering UI (#99)
**Effort:** 8-10 hours | **Requires:** #90 fixed

**Why Fifth:** Builds on working search to provide comprehensive filtering

**Tasks:**
- [ ] Create `VariantFilterSidebar.vue` component with:
  - Variant type filters (SNV, CNV deletion, CNV duplication)
  - Pathogenicity chips (Pathogenic, Likely pathogenic, VUS, Benign)
  - Consequence select (Frameshift, Nonsense, Missense, Splice site, Synonymous)
  - Domain select (Dimerization, POU-specific, POU-homeodomain, Transactivation)
- [ ] Integrate sidebar into `Variants.vue` view
- [ ] Implement filter state management (Vue reactive state)
- [ ] Add "Apply Filters" and "Reset" buttons
- [ ] Add active filter chip display above variant table
- [ ] Combine filters with search functionality
- [ ] Update URL query parameters to persist filter state
- [ ] Add filter result count ("Showing 15 of 200 variants")

**Files:**
- `frontend/src/components/variant/VariantFilterSidebar.vue` (NEW)
- `frontend/src/views/Variants.vue` (modify)

---

#### 3.2 Variant Annotation UI (#116)
**Effort:** 2-3 hours | **Requires:** VEP API endpoint (#100, assumed done)

**Why Sixth:** Enhances variant input with real-time validation

**Tasks:**
- [ ] Create `VariantAnnotator.vue` component with:
  - Text input with format detection (VCF/HGVS)
  - Real-time validation on blur
  - Annotation button with loading state
  - Results card showing:
    - Consequence (e.g., "missense_variant")
    - Impact badge (HIGH/MODERATE/LOW/MODIFIER with colors)
    - CADD score
    - gnomAD allele frequency
    - Format conversions (VCF ↔ HGVS)
- [ ] Integrate into phenopacket edit form
- [ ] Add error handling with user-friendly messages
- [ ] Test with various input formats

**Files:**
- `frontend/src/components/variant/VariantAnnotator.vue` (NEW)
- `frontend/src/views/PhenopacketCreateEdit.vue` (integrate component)

---

### Phase 4: Statistical Visualizations (Charts)
**Duration:** 5-6 days | **Priority:** P2 (Medium)

#### 4.1 Phenotype Distribution Stacked Bar Chart (#42)
**Effort:** 8 hours | **Backend dependency:** Aggregate endpoint

**Tasks:**
- [ ] Implement backend endpoint:
  - `GET /api/v2/phenopackets/aggregate/by-feature?limit=20`
  - Return HPO terms with counts/percentages
- [ ] Create D3.js stacked bar chart component
- [ ] X-axis: HPO term labels
- [ ] Y-axis: Percentage/count
- [ ] Color: Present (green), Absent (grey)
- [ ] Add tooltip with detailed stats
- [ ] Integrate into `AggregationsDashboard.vue`

**Files:**
- `backend/app/phenopackets/routers/aggregations.py` (add endpoint)
- `frontend/src/components/charts/PhenotypeDistributionChart.vue` (NEW)
- `frontend/src/views/AggregationsDashboard.vue` (modify)

---

#### 4.2 Publication Timeline (#43)
**Effort:** 6 hours | **Backend dependency:** Timeline endpoint

**Tasks:**
- [ ] Implement backend endpoint:
  - `GET /api/v2/phenopackets/aggregate/publications-timeline`
  - Return cumulative counts by year
- [ ] Create D3.js timeline chart
- [ ] X-axis: Year, Y-axis: Cumulative count
- [ ] Hover: Show publication details
- [ ] Click: Navigate to publication detail page
- [ ] Integrate into dashboard

**Files:**
- `backend/app/phenopackets/routers/aggregations.py` (add endpoint)
- `frontend/src/components/charts/PublicationTimeline.vue` (NEW)
- `frontend/src/views/AggregationsDashboard.vue` (modify)

---

#### 4.3 Phenotype Count Histogram (#44)
**Effort:** 6 hours | **Backend dependency:** Histogram endpoint

**Tasks:**
- [ ] Implement backend endpoint:
  - `GET /api/v2/phenopackets/aggregate/phenotype-counts`
  - Return distribution of phenotype counts
- [ ] Create histogram with D3.js
- [ ] Separate histograms for CAKUT-only vs CAKUT+MODY
- [ ] Overlay for comparison
- [ ] Add summary stats (mean, median)
- [ ] Integrate into dashboard

**Files:**
- `backend/app/phenopackets/routers/aggregations.py` (add endpoint)
- `frontend/src/components/charts/PhenotypeCountHistogram.vue` (NEW)
- `frontend/src/views/AggregationsDashboard.vue` (modify)

---

### Phase 5: Comparative Analysis (Advanced Charts)
**Duration:** 3-4 days | **Priority:** P2 (Medium)

#### 5.1 Variant Type Comparison (#45)
**Effort:** 12 hours | **Backend dependency:** Comparison endpoint

**Tasks:**
- [ ] Implement backend endpoint:
  - `POST /api/v2/phenopackets/aggregate/compare-groups`
  - Accept variant type groups
  - Perform chi-square test
  - Return phenotype distributions with p-values
- [ ] Create comparison component with:
  - Side-by-side bar charts
  - P-value display with significance indicators
  - Export comparison table button
- [ ] Support comparisons:
  - Truncating vs Non-truncating
  - 17q deletion vs Point mutations
  - Deletion vs Duplication

**Files:**
- `backend/app/phenopackets/routers/aggregations.py` (add endpoint)
- `backend/app/utils/statistics.py` (NEW, chi-square tests)
- `frontend/src/components/charts/VariantTypeComparison.vue` (NEW)
- `frontend/src/views/AggregationsDashboard.vue` (modify)

---

#### 5.2 Clinical Subgroup Comparisons (#46)
**Effort:** 10 hours | **Requires:** #45 component

**Tasks:**
- [ ] Implement backend endpoint:
  - `POST /api/v2/phenopackets/aggregate/compare-clinical`
  - Support subgroup comparisons:
    - CAKUT-only vs CAKUT+MODY
    - CKD Stage 3 vs 4 vs 5
    - With diabetes vs Without
    - With genital abnormalities vs Without
  - Perform ANOVA/chi-square tests
- [ ] Reuse comparison component from #45
- [ ] Add subgroup selector dropdown
- [ ] Multiple comparison view
- [ ] Display statistical test results

**Files:**
- `backend/app/phenopackets/routers/aggregations.py` (add endpoint)
- `frontend/src/components/charts/ClinicalSubgroupComparison.vue` (reuse #45)
- `frontend/src/views/AggregationsDashboard.vue` (modify)

---

### Phase 6: Advanced Visualizations (Optional/Data-Dependent)
**Duration:** 3-5 days | **Priority:** P3 (Low/Data-Dependent)

#### 6.1 3D Protein Structure (#97)
**Effort:** 12-16 hours | **Requires:** #95, #96

**Tasks:**
- [ ] Install NGL.js: `npm install ngl`
- [ ] Create `ProteinStructure3D.vue` component
- [ ] Load PDB structure: 2H8R (residues 170-280)
- [ ] Map missense variants onto structure
- [ ] Color-code by pathogenicity
- [ ] Add representation controls (cartoon/surface/ball-stick)
- [ ] Add variant tooltips on hover
- [ ] Integrate into variant detail page

**Files:**
- `frontend/package.json` (add ngl dependency)
- `frontend/src/components/variant/ProteinStructure3D.vue` (NEW)
- `frontend/src/views/VariantDetail.vue` (integrate component)

**Notes:**
- Reference implementation: https://github.com/halbritter-lab/hnf1b-protein-page
- Only shows missense variants in PDB-covered region (residues 170-280)

---

#### 6.2 Kaplan-Meier Survival Curves (#47) - **DATA AUDIT REQUIRED FIRST**
**Effort:** 16 hours IF data available | **Priority:** P3 (Data-Dependent)

**⚠️ CRITICAL: Run data audit BEFORE starting implementation**

**Pre-Implementation Data Audit:**
```sql
-- Check temporal data availability
SELECT
    COUNT(*) AS total_phenopackets,
    COUNT(CASE WHEN jsonb->'measurements' IS NOT NULL THEN 1 END) AS with_measurements,
    COUNT(CASE WHEN jsonb->'subject'->'timeAtLastEncounter' IS NOT NULL THEN 1 END) AS with_encounter_time
FROM phenopackets;

-- Check for age-at-onset data
SELECT
    COUNT(*) AS phenotypes_with_onset,
    COUNT(DISTINCT phenopacket_id) AS phenopackets_with_onset
FROM (
    SELECT
        p.id AS phenopacket_id,
        pf.value->'onset' AS onset
    FROM phenopackets p,
         jsonb_array_elements(p.jsonb->'phenotypicFeatures') AS pf
    WHERE pf.value->'onset' IS NOT NULL
) AS subq;
```

**Decision Tree:**
- **< 10% have temporal data:** ❌ **DESCOPE** - Add to docs as "Future Work"
- **10-50% have temporal data:** ⚠️ **Partial implementation** - Show with disclaimer
- **> 50% have temporal data:** ✅ **Full implementation** - Proceed

**If Data Available (>50%):**
- [ ] Run data audit to confirm temporal data availability
- [ ] Implement backend endpoint:
  - `GET /api/v2/phenopackets/aggregate/survival-data?outcome=esrd&group_by=variant_type`
  - Extract age at ESRD from medicalActions
  - Calculate survival probabilities
  - Perform log-rank test
- [ ] Create D3.js Kaplan-Meier component with:
  - Survival curves
  - Censoring indicators (vertical ticks)
  - Risk table below plot
  - Log-rank test p-value
  - Group by variant type, 17q status

**If Data Unavailable (<10%):**
- [ ] Add placeholder card with:
  - "Coming Soon" chip
  - Explanation of required temporal data
  - Instructions for data providers

**Files (if implemented):**
- `backend/app/phenopackets/routers/aggregations.py` (add endpoint)
- `backend/app/utils/survival_analysis.py` (NEW, Kaplan-Meier calculations)
- `frontend/src/components/charts/KaplanMeierCurve.vue` (NEW or placeholder)
- `frontend/src/views/AggregationsDashboard.vue` (modify)

---

## Summary Timeline

### Critical Path (Must Complete First)
1. **Phase 1:** Fix Variant Search (#90) → Fix Zoom (#92) → Correct Domains (#95)
   - **Duration:** 3-4 days
   - **Why:** Foundation for all variant visualizations

2. **Phase 2:** Migrate Genomic Annotations (#96)
   - **Duration:** 4-5 days
   - **Why:** Single source of truth for reference data

### Parallel Development (Can Start After Phase 1)
3. **Phase 3:** Advanced Filtering (#99) + Variant Annotation UI (#116)
   - **Duration:** 2-3 days
   - **Why:** User experience improvements

4. **Phase 4:** Statistical Visualizations (#42, #43, #44)
   - **Duration:** 5-6 days
   - **Why:** Publication-ready charts

5. **Phase 5:** Comparative Analysis (#45, #46)
   - **Duration:** 3-4 days
   - **Why:** Research insights

### Optional (Based on Data/Resources)
6. **Phase 6:** 3D Protein (#97) + Kaplan-Meier (#47)
   - **Duration:** 3-5 days
   - **Why:** Advanced visualizations (data-dependent)

---

## Total Estimated Duration

**Minimum Viable (Phases 1-5):** 17-22 days (3.5-4.5 weeks)
**Full Implementation (Phases 1-6):** 20-27 days (4-5.5 weeks)

---

## Testing Requirements

### Backend Tests
- [ ] Reference data API endpoints (CRUD operations)
- [ ] Aggregation endpoint correctness (phenotype counts, timelines)
- [ ] Statistical test implementations (chi-square, ANOVA)
- [ ] Data migration scripts (verify against known reference data)

### Frontend Tests
- [ ] Chart rendering (snapshot tests for D3.js components)
- [ ] Filter state management (verify URL params, reactive updates)
- [ ] Variant annotation input validation
- [ ] Reference data caching (Pinia store tests)
- [ ] Responsive design (viewport tests for mobile/tablet)

### Integration Tests
- [ ] End-to-end filter + search workflow
- [ ] Variant annotation → phenopacket creation flow
- [ ] Chart interactions (zoom, tooltip, export)

---

## Success Metrics

- [ ] All variant searches return results in < 500ms
- [ ] Zoom functionality works on all visualizations
- [ ] HNF1B domain coordinates match UniProt P35680 100%
- [ ] All charts render in < 2s with 864 phenopackets
- [ ] Filter combinations work correctly (no empty result bugs)
- [ ] 3D protein structure loads in < 3s
- [ ] Statistical tests show correct p-values (validate against R/Python)
- [ ] All frontend tests pass (vitest, ESLint, Prettier)
- [ ] All backend tests pass (pytest, ruff, mypy)

---

## Risk Mitigation

### High Risk
1. **Kaplan-Meier data unavailable (#47)** → Run audit FIRST, descope if <10%
2. **D3.js zoom complexity (#92)** → Allocate extra time, consider library alternatives
3. **Reference data migration complexity (#96)** → Start early, test incrementally

### Medium Risk
1. **3D protein structure performance (#97)** → Test with low-poly model first
2. **Statistical test correctness (#45, #46)** → Validate against known datasets

### Low Risk
1. **Chart rendering performance (#42-44)** → D3.js proven for this data size
2. **Filter UI state management (#99)** → Standard Vue.js patterns

---

## Dependencies

### External APIs
- UniProt API (protein domain data)
- NCBI Gene API (gene coordinates)
- Ensembl REST API (exon boundaries)

### Libraries
- NGL.js (3D protein visualization)
- D3.js v7 (already installed)
- Vuetify 3 (already installed)

### Backend Packages
- scipy/statsmodels (statistical tests) - **May need to add**
- lifelines (Kaplan-Meier) - **May need to add if #47 implemented**

---

## Notes

- **YAGNI Principle:** Focus on P1 issues first (#90, #92, #95, #96)
- **Data-Driven Decisions:** Run audit before implementing #47
- **Incremental Development:** Test each visualization independently
- **Code Reuse:** Share comparison component between #45 and #46
- **Performance First:** Optimize backend aggregations for 864 phenopackets

---

## Commit Message Convention

Use conventional commits for all changes:

**Examples:**
```
fix(frontend): repair variant search functionality (#90)
fix(frontend): restore zoom behavior in D3 visualizations (#92)
fix(data): correct HNF1B protein domain coordinates (#95)
refactor(api): migrate genomic annotations to database (#96)
feat(frontend): add advanced variant filtering sidebar (#99)
feat(frontend): add variant annotation UI component (#116)
feat(charts): add phenotype distribution stacked bar chart (#42)
feat(charts): add publication timeline visualization (#43)
feat(charts): add phenotype count histogram (#44)
feat(charts): add variant type comparison view (#45)
feat(charts): add clinical subgroup comparisons (#46)
feat(frontend): add 3D protein structure viewer (#97)
feat(charts): implement Kaplan-Meier survival curves (#47)
```
