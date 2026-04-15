# Issues #42-46 - Visualizations & Analysis

**Note:** Three placeholder tabs were removed from AggregationsDashboard.vue in issue #33:
- **Stacked Bar Chart** - Called non-existent `API.getPhenotypeDescribedCount()` (removed as YAGNI per issue #33)
- **Time Plot** - Called non-existent `API.getPublicationsCumulativeCount()` (removed as YAGNI per issue #33)
- **Protein Plot** - Called non-existent `API.getProteins()` and `API.getVariantsSmallVariants()` (backend endpoints not implemented)

These visualizations should be reimplemented with proper v2 API endpoints in issues #42, #43, and the protein plot functionality below.

---

## Issue #42: feat(frontend): add phenotype distribution stacked bar chart

### Overview
Stacked bar chart showing presence/absence of HPO terms across phenopackets.

### Visualization
```
Chronic Kidney Disease  ████████████████████ 96%
Genital Abnormalities   ████████████░░░░░░░░ 72%
Diabetes Mellitus       ██████████░░░░░░░░░░ 59%
Hypomagnesemia         ████████░░░░░░░░░░░░ 45%
```

### Implementation
- D3.js stacked bar chart
- X-axis: HPO term labels
- Y-axis: Percentage/count
- Color: Present (green), Absent (grey)
- Tooltip: Detailed stats

### Endpoint
```http
GET /api/v2/phenopackets/aggregate/by-feature?limit=20
```

### Timeline: 8 hours (1 day)
### Labels: `frontend`, `charts`, `visualization`, `p2`

---

## Issue #43: feat(frontend): add timeline visualizations

### Overview
Two complementary D3.js timeline visualizations using shared display logic:
1. **Publication Timeline** (aggregate view): Phenopackets added over time by publication
2. **Phenotype Timeline** (individual view): When phenotypic features emerged for each patient

Both timelines share similar visual design patterns and D3.js implementation logic.

---

### 43a. Publication Timeline (Aggregate View)

**Goal:** Show cumulative phenopackets added over time across all publications.

#### Visualization
```
Cumulative Count
 500 │                                 ●
 400 │                           ●────╯
 300 │                     ●────╯
 200 │               ●────╯
 100 │         ●────╯
   0 └────────────────────────────────
     2018   2019   2020   2021   2022
          Publication Year
```

#### Features
- X-axis: Year
- Y-axis: Cumulative count
- Hover: Show publication details (count added that year)
- Click: Navigate to publication detail page
- Interactive: Zoom into date ranges

#### Endpoint
```http
GET /api/v2/phenopackets/aggregate/publications-timeline

Response:
{
  "timeline": [
    { "year": 2018, "count": 4, "cumulative": 4 },
    { "year": 2019, "count": 8, "cumulative": 12 },
    { "year": 2020, "count": 12, "cumulative": 24 }
  ]
}
```

#### Integration Point
Add to **Aggregations Dashboard** as a new tab.

---

### 43b. Phenotype Timeline (Individual View)

**Goal:** Display temporal progression of phenotypic features for an individual, showing when each phenotype was first observed (onset) and documented (publication date).

#### User Story
As a clinician/researcher, I want to see a **temporal timeline** of when phenotypic features emerged for an individual, so that I can:
- Identify patterns in disease progression
- Understand the sequence of symptom onset
- See which features were documented in which publications
- Track how the clinical picture evolved over time

#### Data Structure
Each `phenotypicFeature` contains temporal data:

```json
{
  "type": { "id": "HP:0000107", "label": "Renal cyst" },
  "excluded": false,
  "onset": {
    "age": { "iso8601duration": "P5Y" },  // 5 years old
    "ontologyClass": { "id": "HP:0003577", "label": "Congenital onset" }
  },
  "evidence": [
    {
      "evidenceCode": { "id": "ECO:0000033", "label": "author statement" },
      "reference": {
        "id": "PMID:12345678",
        "description": "Smith et al., 2020...",
        "recordedAt": "2024-01-15T10:30:00Z"
      }
    }
  ]
}
```

#### Visualization
```
┌────────────────────────────────────────────────────────────────┐
│  Phenotypic Features Timeline - Subject ID: 123                │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Birth  1y   5y   10y  15y  20y  25y  30y  35y  40y  45y  50y │
│  ├──────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤   │
│  │      │    ●────┐    │    │    │    │    │    │    │    │   │
│  │      │    │Renal cyst (PMID:12345678)                    │   │
│  │      │    │    │    │    ●────┐    │    │    │    │    │   │
│  │      │    │    │    │    │MODY (PMID:23456789)          │   │
│  │      ●────┐    │    │    │    │    │    │    │    │    │   │
│  │   Bilateral │  │    │    │    │    │    │    │    │    │   │
│  │   absence   │  │    │    │    │    │    │    │    │    │   │
│  └──────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘   │
│                                                                 │
│  Legend:                                                        │
│  ● Onset age    PMID - Publication                            │
└────────────────────────────────────────────────────────────────┘
```

#### Features
1. **X-axis**: Age timeline (birth to current age)
2. **Y-axis**: Phenotypic features (grouped by organ system)
3. **Data Points**: 
   - Circle/marker at onset age
   - Connecting line to current age (if ongoing)
   - Label with HPO term and PMID
4. **Color Coding**: By organ system (renal=blue, diabetes=orange, genital=purple)
5. **Interactive**:
   - Hover: Full details (HPO ID, severity, modifiers, evidence)
   - Click: Link to publication or HPO term
   - Filter: Show/hide by organ system
   - Zoom: Focus on specific age ranges

#### Backend Endpoint
```python
# backend/app/phenopackets/routers/timeline.py

@router.get("/{phenopacket_id}/timeline")
async def get_phenotype_timeline(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns:
        {
            "subject_id": "123",
            "current_age": "P45Y6M",
            "features": [
                {
                    "hpo_id": "HP:0000107",
                    "label": "Renal cyst",
                    "onset_age": "P5Y",  # ISO8601 duration
                    "onset_label": "Congenital onset",
                    "category": "Renal",
                    "severity": "Moderate",
                    "excluded": false,
                    "evidence": [
                        {
                            "pmid": "12345678",
                            "recorded_at": "2024-01-15",
                            "description": "Smith et al., 2020"
                        }
                    ]
                }
            ]
        }
    """
```

#### Frontend Component
```vue
<!-- frontend/src/components/phenopacket/PhenotypeTimeline.vue -->
<template>
  <v-card variant="outlined" class="mb-4">
    <v-card-title class="bg-blue-lighten-5">
      <v-icon left>mdi-timeline-clock</v-icon>
      Phenotypic Features Timeline
    </v-card-title>
    
    <v-card-text>
      <!-- Filters -->
      <v-row class="mb-4">
        <v-col cols="12" md="6">
          <v-select
            v-model="selectedCategories"
            :items="categories"
            label="Filter by organ system"
            multiple
            chips
            dense
          />
        </v-col>
        <v-col cols="12" md="6">
          <v-checkbox
            v-model="showExcluded"
            label="Show excluded features"
            dense
          />
        </v-col>
      </v-row>
      
      <!-- D3.js Timeline -->
      <div ref="timeline" class="timeline-container"></div>
      
      <!-- Legend -->
      <div class="legend mt-4">
        <v-chip
          v-for="category in categories"
          :key="category.value"
          :color="category.color"
          size="small"
          class="mr-2"
        >
          {{ category.label }}
        </v-chip>
      </div>
    </v-card-text>
  </v-card>
</template>
```

#### Age Parsing Utility
```javascript
// Shared utility for both timelines
function parseAge(iso8601duration) {
  // Convert "P5Y6M" to 5.5 years
  const regex = /P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?/;
  const matches = iso8601duration.match(regex);
  if (!matches) return 0;
  
  const years = parseInt(matches[1] || 0);
  const months = parseInt(matches[2] || 0);
  const days = parseInt(matches[3] || 0);
  
  return years + (months / 12) + (days / 365);
}

// Handle ontology classes
const onsetMapping = {
  "HP:0003577": 0,         // Congenital onset → age 0
  "HP:0003623": 0,         // Neonatal onset → age 0
  "HP:0003581": 18,        // Adult onset → age 18+
};
```

#### Integration Point
Add **Timeline tab** to individual phenopacket detail page (`PagePhenopacket.vue`).

---

### Shared Implementation Components

Both timelines can reuse:
- **D3.js scales**: `d3.scaleTime()` for X-axis
- **Tooltip component**: Shared hover behavior
- **Zoom behavior**: `d3.zoom()` for both views
- **Color schemes**: Consistent color palette
- **Responsive sizing**: Same breakpoint logic
- **Loading states**: Shared skeleton loader

### Data Handling Considerations

#### Missing Data
- **No onset age**: Show as "Unknown onset" at bottom
- **No evidence**: Show feature with note "Undocumented"
- **Excluded features**: Dashed line, gray color
- **Prenatal/Congenital**: Show at birth (age 0)

---

### Implementation Plan

#### Phase 1: Shared Infrastructure (1 day)
- ✅ Create `TimelineBase.vue` component with D3.js setup
- ✅ Age parsing utility (`utils/ageParser.js`)
- ✅ Timeline color scheme constants
- ✅ Shared tooltip component

#### Phase 2: Publication Timeline (1 day)
- ✅ Backend: `/aggregate/publications-timeline` endpoint
- ✅ Frontend: `PublicationTimeline.vue` component
- ✅ Integration: Add to Aggregations Dashboard

#### Phase 3: Phenotype Timeline (2-3 days)
- ✅ Backend: `/{phenopacket_id}/timeline` endpoint
- ✅ Frontend: `PhenotypeTimeline.vue` component
- ✅ Filtering by organ system
- ✅ Click handlers (HPO/PMID links)
- ✅ Integration: Add tab to individual detail page

#### Phase 4: Polish (1 day)
- ✅ Responsive design
- ✅ Loading/error states
- ✅ Empty state handling
- ✅ Documentation

### Total Timeline: 5-6 days
### Labels: `frontend`, `charts`, `visualization`, `timeline`, `p2`

---

## Issue #44: feat(frontend): add phenotype count histogram

### Overview
Histogram showing distribution of phenotype counts per individual.

### Visualization
```
Count
 50 │     █
 40 │   █ █
 30 │   █ █ █
 20 │ █ █ █ █
 10 │ █ █ █ █ █
  0 └─────────────
     0 2 4 6 8+
     # Phenotypes
```

### Features
- Separate histograms for CAKUT-only vs CAKUT+MODY
- Overlay for comparison
- Summary stats (mean, median)

### Endpoint
```http
GET /api/v2/phenopackets/aggregate/phenotype-counts
```

### Timeline: 6 hours (1 day)
### Labels: `frontend`, `charts`, `visualization`, `p2`

---

## Issue #45: feat(frontend): add variant type comparison view

### Overview
Side-by-side comparison of phenotype distributions between variant types.

### Comparisons
- Truncating vs Non-truncating
- 17q deletion vs Point mutations
- Deletion vs Duplication

### Layout
```
┌─────────────────┬─────────────────┐
│  Truncating     │  Non-truncating │
│  (n=312)        │  (n=111)        │
├─────────────────┼─────────────────┤
│  CKD: 98%       │  CKD: 85%       │
│  Diabetes: 65%  │  Diabetes: 42%  │
│  Genital: 78%   │  Genital: 58%   │
└─────────────────┴─────────────────┘
  p-value: 0.001***
```

### Features
- Chi-square test for significance
- P-value display
- Paired bar charts
- Export comparison table

### Endpoint
```http
POST /api/v2/phenopackets/aggregate/compare-groups
Body: {
  "group_by": "variant_type",
  "groups": ["truncating", "non_truncating"],
  "features": ["HP:0012622", "HP:0000819"]
}
```

### Timeline: 12 hours (2 days)
### Labels: `frontend`, `charts`, `feature`, `p2`

---

## Issue #46: feat(frontend): add clinical subgroup comparisons

### Overview
Compare phenotypes across clinical subgroups.

### Subgroups
- CAKUT-only vs CAKUT+MODY
- CKD Stage 3 vs 4 vs 5
- With diabetes vs Without
- With genital abnormalities vs Without

### Implementation
- Reuse comparison component from #45
- Add subgroup selector dropdown
- Multiple comparison view
- Statistical tests (ANOVA, Chi-square)

### Endpoint
```http
POST /api/v2/phenopackets/aggregate/compare-clinical
Body: {
  "comparison": "cakut_mody",
  "features": ["HP:0012622", "HP:0000819"]
}
```

### Timeline: 10 hours (1.5 days)
### Labels: `frontend`, `charts`, `feature`, `p2`

---

## Issue #47: feat(frontend): implement Kaplan-Meier survival curves

### Overview
Renal survival analysis with Kaplan-Meier curves.

### Visualization
```
Survival
  1.0 ┤───────────╮
      │           ╰─────╮
  0.8 │                 ╰──╮
      │                    ╰─╮
  0.6 │                      ╰─
      │
  0.4 │   Legend:
      │   ── Truncating (n=312)
  0.2 │   ── Non-truncating (n=111)
      │
  0.0 └─────────────────────────
      0  10  20  30  40  50
          Years to ESRD
```

### Features
- Kaplan-Meier curves using D3.js
- Censoring indicators (vertical ticks)
- Log-rank test p-value
- Risk table below plot
- Group by variant type, 17q status

---

## Temporal Data Availability Audit

### Problem

**Kaplan-Meier survival analysis requires temporal data that may not exist in current phenopackets.**

Required fields:
- **Age at diagnosis** - When did HNF1B disease manifest?
- **Age at CKD stages** - When did patient reach Stage 3, 4, 5?
- **Age at ESRD** - When did patient reach end-stage renal disease (dialysis/transplant)?
- **Censoring status** - Is patient still being followed, or lost to follow-up?
- **Current age** - For calculating censored observations

### Data Audit Required

**Before implementing issue #47, audit phenopackets for temporal data:**

```sql
-- Check if phenopackets contain temporal measurements
SELECT
    COUNT(*) AS total_phenopackets,
    COUNT(CASE WHEN jsonb->'measurements' IS NOT NULL THEN 1 END) AS with_measurements,
    COUNT(CASE WHEN jsonb->'subject'->'timeAtLastEncounter' IS NOT NULL THEN 1 END) AS with_encounter_time
FROM phenopackets;

-- Check for age-at-onset data in phenotypic features
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

-- Check for temporal disease data
SELECT
    COUNT(*) AS diseases_with_onset,
    COUNT(DISTINCT phenopacket_id) AS phenopackets_with_disease_onset
FROM (
    SELECT
        p.id AS phenopacket_id,
        d.value->'onset' AS onset
    FROM phenopackets p,
         jsonb_array_elements(p.jsonb->'diseases') AS d
    WHERE d.value->'onset' IS NOT NULL
) AS subq;
```

**Expected Results:**

| Scenario | Action |
|----------|--------|
| **< 10% have temporal data** | ❌ **DESCOPE issue #47** - Not enough data for survival analysis |
| **10-50% have temporal data** | ⚠️ **Partial implementation** - Show survival curves with disclaimer about incomplete data |
| **> 50% have temporal data** | ✅ **Full implementation** - Proceed with Kaplan-Meier curves |

### Data Extraction Strategy (If Available)

**Phenopackets v2 Temporal Fields:**

```javascript
// Option 1: Age at last encounter (current age or age at last follow-up)
phenopacket.subject.timeAtLastEncounter.age.iso8601duration  // "P45Y6M" (45 years 6 months)

// Option 2: Onset age for specific phenotypes (e.g., CKD, ESRD)
phenopacket.phenotypicFeatures[].onset.age.iso8601duration  // "P25Y" (onset at 25 years)

// Option 3: Disease onset
phenopacket.diseases[].onset.age.iso8601duration

// Option 4: Medical actions (dialysis, transplant)
phenopacket.medicalActions[].treatment.agent  // { id: "NCIT:C15248", label: "Hemodialysis" }
phenopacket.medicalActions[].treatment.onset.age.iso8601duration  // Age at dialysis start
```

**Example Survival Data Extraction:**
```python
def extract_esrd_survival_data(phenopacket):
    """
    Extract age at ESRD (dialysis/transplant) from phenopacket.

    Returns: {
        "time_to_event": 45.5,  # years
        "event_occurred": True,  # True if ESRD reached, False if censored
        "variant_type": "truncating"
    }
    """
    # Get current age or age at last encounter
    current_age = parse_iso8601_age(
        phenopacket.get("subject", {}).get("timeAtLastEncounter", {}).get("age", {}).get("iso8601duration")
    )

    # Check medicalActions for dialysis/transplant
    esrd_age = None
    for action in phenopacket.get("medicalActions", []):
        agent = action.get("treatment", {}).get("agent", {})
        if agent.get("id") in ["NCIT:C15248", "NCIT:C15313"]:  # Dialysis or kidney transplant
            onset = action.get("treatment", {}).get("onset", {}).get("age", {}).get("iso8601duration")
            esrd_age = parse_iso8601_age(onset)
            break

    # Determine event status
    event_occurred = esrd_age is not None
    time_to_event = esrd_age if event_occurred else current_age

    return {
        "time_to_event": time_to_event,
        "event_occurred": event_occurred,
        "variant_type": get_variant_type(phenopacket)
    }
```

### Endpoint (If Data Available)
```http
GET /api/v2/phenopackets/aggregate/survival-data?outcome=esrd&group_by=variant_type

Response:
{
  "groups": [
    {
      "group_name": "Truncating",
      "n": 312,
      "events": 45,  # Number who reached ESRD
      "survival_data": [
        {"time": 0, "survival_probability": 1.0, "at_risk": 312},
        {"time": 10, "survival_probability": 0.92, "at_risk": 287},
        {"time": 20, "survival_probability": 0.85, "at_risk": 245},
        {"time": 30, "survival_probability": 0.78, "at_risk": 198},
        {"time": 40, "survival_probability": 0.65, "at_risk": 142}
      ]
    },
    {
      "group_name": "Non-truncating",
      "n": 111,
      "events": 8,
      "survival_data": [...]
    }
  ],
  "log_rank_test": {
    "statistic": 12.34,
    "p_value": 0.0004,
    "significant": true
  }
}
```

### Implementation Decision Tree

```
1. Run data audit
   ↓
2. Check temporal data availability
   ↓
   ├─ < 10% → DESCOPE (add to docs as "Future Work")
   ├─ 10-50% → Partial (with big disclaimer)
   └─ > 50% → Full implementation
       ↓
3. Implement survival analysis backend
   ↓
4. Create D3.js Kaplan-Meier component
   ↓
5. Add to aggregations dashboard
```

### Alternative: Mock Data Placeholder

**If temporal data unavailable:**

```vue
<!-- Survival curves placeholder -->
<v-card outlined>
  <v-card-title>
    <v-icon left color="grey">mdi-chart-line</v-icon>
    Kaplan-Meier Survival Analysis
    <v-chip color="orange" size="small" class="ml-2">Coming Soon</v-chip>
  </v-card-title>
  <v-card-text>
    <v-alert type="info" variant="tonal">
      <strong>Temporal data required:</strong> Survival analysis requires age at diagnosis,
      age at CKD stages, and age at ESRD (dialysis/transplant). This data is not currently
      available in the phenopackets.

      <p class="mt-2">
        <strong>To enable this feature:</strong> Phenopackets must include:
      </p>
      <ul>
        <li>subject.timeAtLastEncounter (current age)</li>
        <li>medicalActions with dialysis/transplant onset ages</li>
        <li>phenotypicFeatures with CKD stage onset ages</li>
      </ul>
    </v-alert>

    <!-- Optional: Show mock chart with placeholder data -->
    <div class="text-center mt-4">
      <v-img
        src="/images/kaplan-meier-placeholder.png"
        alt="Kaplan-Meier curve placeholder"
        max-width="600"
        class="mx-auto opacity-50"
      />
    </div>
  </v-card-text>
</v-card>
```

### Data Requirements
⚠️ **Requires temporal data:**
- Age at diagnosis
- Age at CKD stages
- Age at dialysis/transplant
- Censoring status

**ACTION REQUIRED:** Run data audit query BEFORE starting implementation

### Implementation
**Note:** Implementation depends on data audit results
- **If data available (> 50%):** Full Kaplan-Meier implementation
- **If partial data (10-50%):** Limited implementation with disclaimers
- **If no data (< 10%):** Descope and document as future work

### Timeline: 16 hours (2 days) *if data available*
### Labels: `frontend`, `charts`, `feature`, `p3`, `data-dependent`
