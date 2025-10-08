# Issue #33: fix(frontend): update aggregation endpoints for phenopacket format

## Overview

The aggregations dashboard (`frontend/src/views/AggregationsDashboard.vue`) uses v1 aggregation endpoints that no longer exist. Charts expect normalized data from separate tables but backend v2 provides phenopacket-based aggregations.

**Current State:** Dashboard calls `/aggregations/individuals/sex-count`, `/aggregations/variants/type-count`, etc. → 404 errors
**Required State:** Dashboard uses `/api/v2/phenopackets/aggregate/*` endpoints with new data structures

## Why This Matters

### Current Implementation (Broken)

```javascript
// These endpoints DO NOT EXIST
const sexData = await getIndividualsSexCount();
// GET /aggregations/individuals/sex-count → 404

const variantTypes = await getVariantsTypeCount();
// GET /aggregations/variants/type-count → 404

const ageOnset = await getIndividualsAgeOnsetCount();
// GET /aggregations/individuals/age-onset-count → 404
```

**Problem:** All aggregation endpoints return 404. Dashboard displays no data.

### New Implementation (v2 API)

```javascript
// Use phenopacket aggregation endpoints
const sexData = await getSexDistribution();
// GET /api/v2/phenopackets/aggregate/sex-distribution → 200

const hpoTerms = await getPhenotypicFeaturesAggregation({ limit: 20 });
// GET /api/v2/phenopackets/aggregate/by-feature?limit=20 → 200

const diseases = await getDiseaseAggregation({ limit: 20 });
// GET /api/v2/phenopackets/aggregate/by-disease?limit=20 → 200

const pathogenicity = await getVariantPathogenicity();
// GET /api/v2/phenopackets/aggregate/variant-pathogenicity → 200

const kidneyStages = await getKidneyStages();
// GET /api/v2/phenopackets/aggregate/kidney-stages → 200
```

## Endpoint Migration

### Old v1 Endpoints → New v2 Endpoints

| Old Endpoint (404) | New Endpoint (200) | Data Source |
|-------------------|-------------------|-------------|
| `/aggregations/individuals/sex-count` | `/api/v2/phenopackets/aggregate/sex-distribution` | `phenopacket.subject.sex` |
| `/aggregations/individuals/age-onset-count` | ❌ Removed (YAGNI) | Not in phenopackets |
| `/aggregations/individuals/cohort-count` | ❌ Removed (YAGNI) | Not in phenopackets |
| `/aggregations/individuals/family-history-count` | ❌ Removed (YAGNI) | Not in phenopackets |
| `/aggregations/individuals/detection-method-count` | ❌ Removed (YAGNI) | Not in phenopackets |
| `/aggregations/variants/type-count` | `/api/v2/phenopackets/aggregate/variant-pathogenicity` | `interpretations[].variantInterpretation.acmgPathogenicityClassification` |
| `/aggregations/variants/newest-classification-verdict-count` | `/api/v2/phenopackets/aggregate/variant-pathogenicity` | Same as above |
| `/aggregations/publications/type-count` | ❌ Removed (in metadata) | `metaData.externalReferences[]` |
| `/aggregations/publications/cumulative-count` | ❌ Removed (YAGNI) | Not tracked |
| N/A | ✅ **NEW** `/api/v2/phenopackets/aggregate/by-feature` | `phenotypicFeatures[].type.id` (HPO) |
| N/A | ✅ **NEW** `/api/v2/phenopackets/aggregate/by-disease` | `diseases[].term.id` (MONDO) |
| N/A | ✅ **NEW** `/api/v2/phenopackets/aggregate/kidney-stages` | Clinical HPO terms for CKD |

### Response Format Changes

**Old v1 Format:**
```json
{
  "data": [
    { "sex": "MALE", "count": 432 },
    { "sex": "FEMALE", "count": 432 }
  ],
  "meta": { "total": 864 }
}
```

**New v2 Format:**
```json
[
  { "key": "MALE", "label": "Male", "count": 432 },
  { "key": "FEMALE", "label": "Female", "count": 432 }
]
```

**Key Changes:**
- Direct array response (no `data` wrapper)
- Added `label` field for display
- `key` replaces field-specific names (`sex` → `key`)

## New Aggregations Available

### 1. Sex Distribution
```javascript
GET /api/v2/phenopackets/aggregate/sex-distribution

// Response:
[
  { "key": "FEMALE", "label": "Female", "count": 432 },
  { "key": "MALE", "label": "Male", "count": 432 }
]
```

### 2. Phenotypic Features (Top HPO Terms)
```javascript
GET /api/v2/phenopackets/aggregate/by-feature?limit=20

// Response:
[
  { "key": "HP:0012622", "label": "Chronic kidney disease", "count": 427 },
  { "key": "HP:0000078", "label": "Genital abnormalities", "count": 312 },
  { "key": "HP:0000819", "label": "Diabetes mellitus", "count": 256 }
]
```

### 3. Disease Distribution
```javascript
GET /api/v2/phenopackets/aggregate/by-disease?limit=20

// Response:
[
  { "key": "MONDO:0011593", "label": "HNF1B-related disorder", "count": 864 },
  { "key": "MONDO:0005300", "label": "Chronic kidney disease", "count": 427 }
]
```

### 4. Variant Pathogenicity
```javascript
GET /api/v2/phenopackets/aggregate/variant-pathogenicity

// Response:
[
  { "key": "PATHOGENIC", "label": "Pathogenic", "count": 312 },
  { "key": "LIKELY_PATHOGENIC", "label": "Likely Pathogenic", "count": 89 },
  { "key": "UNCERTAIN_SIGNIFICANCE", "label": "VUS", "count": 22 }
]
```

### 5. Kidney Disease Stages
```javascript
GET /api/v2/phenopackets/aggregate/kidney-stages

// Response:
[
  { "key": "NCIT:C156778", "label": "Stage 3 CKD", "count": 156 },
  { "key": "NCIT:C156779", "label": "Stage 4 CKD", "count": 98 },
  { "key": "NCIT:C156780", "label": "Stage 5 CKD", "count": 45 }
]
```

## Required Changes

### 1. Update Dashboard Categories

**File:** `frontend/src/views/AggregationsDashboard.vue`

**Before:**
```javascript
categories: [
  {
    label: 'Individuals',
    aggregations: [
      { label: 'Sex Distribution', value: 'sex-count' },
      { label: 'Age at Onset', value: 'age-onset-count' },
      { label: 'Cohort Distribution', value: 'cohort-count' },
    ]
  },
  {
    label: 'Variants',
    aggregations: [
      { label: 'Type Distribution', value: 'type-count' },
      { label: 'Classification', value: 'classification-count' },
    ]
  },
  {
    label: 'Publications',
    aggregations: [
      { label: 'Type Distribution', value: 'type-count' },
      { label: 'Cumulative Count', value: 'cumulative-count' },
    ]
  }
]
```

**After:**
```javascript
categories: [
  {
    label: 'Demographics',
    aggregations: [
      { label: 'Sex Distribution', value: 'sex-distribution' },
    ]
  },
  {
    label: 'Clinical Features',
    aggregations: [
      { label: 'Top Phenotypic Features (HPO)', value: 'phenotypic-features' },
      { label: 'Kidney Disease Stages', value: 'kidney-stages' },
    ]
  },
  {
    label: 'Diseases',
    aggregations: [
      { label: 'Disease Distribution (MONDO)', value: 'diseases' },
    ]
  },
  {
    label: 'Genomic',
    aggregations: [
      { label: 'Variant Pathogenicity (ACMG)', value: 'variant-pathogenicity' },
    ]
  }
]
```

### 2. Update Data Fetching

```javascript
async fetchAggregationData() {
  this.loading = true;
  try {
    let response;
    switch (this.selectedAggregation) {
      case 'sex-distribution':
        response = await getSexDistribution();
        break;
      case 'phenotypic-features':
        response = await getPhenotypicFeaturesAggregation({ limit: 20 });
        break;
      case 'diseases':
        response = await getDiseaseAggregation({ limit: 20 });
        break;
      case 'variant-pathogenicity':
        response = await getVariantPathogenicity();
        break;
      case 'kidney-stages':
        response = await getKidneyStages();
        break;
      default:
        console.warn('Unknown aggregation:', this.selectedAggregation);
        return;
    }

    // v2 API returns array directly (no data wrapper)
    this.aggregationData = response.data;

    // Transform for chart
    this.updateChartData();
  } catch (error) {
    console.error('Error fetching aggregation:', error);
  } finally {
    this.loading = false;
  }
}
```

### 3. Update Chart Data Transformation

```javascript
updateChartData() {
  // Transform v2 response format for DonutChart
  this.donutChartData = this.aggregationData.map(item => ({
    name: item.label || item.key,  // v2 API provides 'label'
    value: item.count               // v2 API provides 'count'
  }));
}
```

## Implementation Checklist

### Phase 1: API Client
- [ ] Remove old aggregation functions (Done in Issue #30)
- [ ] Add new phenopacket aggregation functions (Done in Issue #30)
- [ ] Verify all return correct data format

### Phase 2: Dashboard Categories
- [ ] Update `categories` array with new aggregations
- [ ] Remove deprecated categories (age-onset, cohort, publications)
- [ ] Add new categories (HPO terms, diseases, kidney stages)
- [ ] Update category labels (Individuals → Demographics, etc.)

### Phase 3: Data Fetching
- [ ] Update `fetchAggregationData()` with new switch cases
- [ ] Remove old aggregation calls
- [ ] Handle v2 response format (no `data` wrapper)
- [ ] Add error handling for missing aggregations

### Phase 4: Chart Data Transformation
- [ ] Update `updateChartData()` to use `key`/`label`/`count`
- [ ] Verify `DonutChart` receives correct format
- [ ] Verify `StackedBarChart` receives correct format (if used)
- [ ] Test `TimePlot` with new data (if applicable)

### Phase 5: UI Updates
- [ ] Update tab labels if needed
- [ ] Add descriptions for new aggregations
- [ ] Update color schemes for new categories
- [ ] Test all dropdown selections

## Testing Verification

### Manual Testing

```bash
# 1. Start backend and frontend
cd backend && make backend
cd frontend && npm run dev

# 2. Navigate to aggregations dashboard
# http://localhost:5173/aggregations

# 3. Test each category/aggregation:

# Demographics → Sex Distribution
# - Select category: Demographics
# - Select aggregation: Sex Distribution
# - Expected: Donut chart with Male/Female distribution

# Clinical Features → Top Phenotypic Features
# - Select category: Clinical Features
# - Select aggregation: Top Phenotypic Features (HPO)
# - Expected: Donut/bar chart with top 20 HPO terms

# Clinical Features → Kidney Disease Stages
# - Select aggregation: Kidney Disease Stages
# - Expected: Bar chart with CKD stage distribution

# Diseases → Disease Distribution
# - Select category: Diseases
# - Select aggregation: Disease Distribution (MONDO)
# - Expected: Chart with disease term frequencies

# Genomic → Variant Pathogenicity
# - Select category: Genomic
# - Select aggregation: Variant Pathogenicity (ACMG)
# - Expected: Chart with Pathogenic/Likely Pathogenic/VUS counts

# 4. Verify console has no errors
# - No 404 errors
# - No data transformation errors
# - Charts render correctly
```

### Expected API Responses

**Sex Distribution:**
```http
GET /api/v2/phenopackets/aggregate/sex-distribution
Response:
[
  { "key": "FEMALE", "label": "Female", "count": 432 },
  { "key": "MALE", "label": "Male", "count": 432 }
]
```

**Phenotypic Features:**
```http
GET /api/v2/phenopackets/aggregate/by-feature?limit=20
Response:
[
  { "key": "HP:0012622", "label": "Chronic kidney disease", "count": 427 },
  { "key": "HP:0000078", "label": "Genital abnormalities", "count": 312 },
  { "key": "HP:0000819", "label": "Diabetes mellitus", "count": 256 }
]
```

## Acceptance Criteria

### Functionality
- [ ] All aggregation dropdowns populate correctly
- [ ] Selecting aggregation fetches correct data
- [ ] Charts display data without errors
- [ ] No 404 errors in console
- [ ] All categories work (Demographics, Clinical, Diseases, Genomic)

### Data Display
- [ ] Sex distribution shows male/female counts
- [ ] Top phenotypic features show HPO terms with counts
- [ ] Disease distribution shows MONDO terms
- [ ] Variant pathogenicity shows ACMG classifications
- [ ] Kidney stages show CKD stage distribution

### Chart Rendering
- [ ] DonutChart renders correctly
- [ ] StackedBarChart renders correctly (if used)
- [ ] TimePlot renders correctly (if used)
- [ ] ProteinPlot still works (separate data source)
- [ ] Colors are appropriate for each category

### Code Quality
- [ ] No references to old aggregation endpoints
- [ ] Category/aggregation config is maintainable
- [ ] Data transformation is clear and commented
- [ ] ESLint passes
- [ ] No console warnings

### Performance
- [ ] Aggregation fetches complete in < 500ms
- [ ] Chart rendering is smooth
- [ ] No memory leaks on category switching

## Files to Modify

```
frontend/src/views/
└── AggregationsDashboard.vue  # ⚠️ MAJOR UPDATES (100+ lines changed)

frontend/src/api/
└── index.js                   # Updated in Issue #30

frontend/src/components/analyses/
├── DonutChart.vue             # Verify data format compatibility
├── StackedBarChart.vue        # Verify data format compatibility
└── TimePlot.vue               # May need updates
```

## Dependencies

**Depends On:**
- Issue #30 (API client migration) - ✅ **BLOCKER**

**Blocks:**
- None

---

## Performance Requirements

### Query Performance Targets

**Response Time Goals:**
- **Sex distribution**: < 100ms (simple GROUP BY on generated column)
- **Phenotypic features**: < 300ms (JSONB array aggregation with LIMIT 20)
- **Disease distribution**: < 200ms (JSONB array aggregation with LIMIT 20)
- **Variant pathogenicity**: < 400ms (nested JSONB extraction + GROUP BY)
- **Kidney stages**: < 250ms (filtered phenotype aggregation)

**Pagination Strategy:**
- Top N aggregations: Default LIMIT 20, max 100
- No pagination needed (aggregation results inherently limited)
- Client-side sorting for small result sets

### Required Database Indexes

```sql
-- Index for sex distribution (already exists via generated column)
-- CREATE INDEX idx_phenopackets_sex ON phenopackets (subject_sex);

-- Index for phenotypic features aggregation
CREATE INDEX idx_phenopackets_phenotypic_features_gin ON phenopackets
USING GIN ((jsonb -> 'phenotypicFeatures'));

-- Index for diseases aggregation
CREATE INDEX idx_phenopackets_diseases_gin ON phenopackets
USING GIN ((jsonb -> 'diseases'));

-- Index for variant pathogenicity (already covered by variant interpretation index)
-- CREATE INDEX idx_phenopackets_interpretations_gin ON phenopackets
-- USING GIN ((jsonb -> 'interpretations'));

-- Composite index for filtered aggregations (e.g., kidney stages)
CREATE INDEX idx_phenopackets_features_type_id ON phenopackets
USING GIN ((jsonb -> 'phenotypicFeatures' -> 'type' -> 'id'));
```

### Performance Considerations

**JSONB Aggregation Costs:**
- 864 phenopackets × ~8 phenotypes each = **~7,000 phenotype records**
- Top 20 HPO terms requires: GROUP BY + ORDER BY + LIMIT
- Without indexes: **1-2 seconds** ❌
- With GIN indexes: **< 300ms** ✅

**Optimization Strategies:**

1. **Use JSONB indexes** (critical for performance)
2. **LIMIT aggregations** to Top 20/50 (don't fetch all)
3. **Cache results** client-side (5-minute TTL)
4. **Lazy load** charts (don't fetch all aggregations on page load)

### Frontend Performance

**Chart Rendering:**
- DonutChart: < 50ms for 2-10 categories
- StackedBarChart: < 100ms for 20 bars
- Transitions: Smooth 300ms animations

**Data Caching:**
```javascript
// Cache aggregation results to avoid repeated API calls
const aggregationCache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

async function fetchAggregation(type) {
  const cached = aggregationCache.get(type);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data;
  }

  const data = await fetchFromAPI(type);
  aggregationCache.set(type, { data, timestamp: Date.now() });
  return data;
}
```

### Load Testing Targets

**Concurrent Users:**
- 10 concurrent users: All aggregations < 500ms
- 50 concurrent users: All aggregations < 1000ms
- Database connection pool: 20 connections

**Stress Test Scenarios:**
```bash
# Benchmark aggregation endpoints
for i in {1..100}; do
  curl -s -w "%{time_total}\n" -o /dev/null \
    "http://localhost:8000/api/v2/phenopackets/aggregate/by-feature?limit=20"
done | awk '{sum+=$1; count++} END {print "Average:", sum/count, "seconds"}'
```

**Expected Results:**
- Average: < 0.3 seconds
- 95th percentile: < 0.5 seconds
- 99th percentile: < 1.0 second

---

## Performance Impact

**Before (v1):**
```javascript
// Multiple failed requests
await getIndividualsSexCount();        // 404 error
await getVariantsTypeCount();          // 404 error
await getIndividualsAgeOnsetCount();   // 404 error
// Total time: N/A (all fail)
```

**After (v2):**
```javascript
// Successful requests with performance targets
await getSexDistribution();            // 200 OK (< 100ms target)
await getPhenotypicFeaturesAggregation(); // 200 OK (< 300ms target)
await getVariantPathogenicity();       // 200 OK (< 400ms target)
// Total time: ~800ms max for 3 aggregations
```

**Improvement:** Goes from completely broken (404s) to fully functional with sub-second performance ✅

## Timeline

- **Phase 1:** API client updates - 0 hours (done in Issue #30)
- **Phase 2:** Dashboard categories - 2 hours
- **Phase 3:** Data fetching - 3 hours
- **Phase 4:** Chart data transformation - 2 hours
- **Phase 5:** UI updates & testing - 3 hours

**Total:** 10 hours (1.5 days)

## Priority

**P2 (Medium)** - Important for data visualization but not blocking core workflows

## Labels

`frontend`, `charts`, `api`, `data-visualization`, `p2`

## Related Issues

- Issue #30: API client migration (dependency)
- Issue #38: Backend summary endpoint (related aggregation work)
