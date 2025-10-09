# Issues #41-46 - Visualizations & Analysis

**Note:** Three placeholder tabs were removed from AggregationsDashboard.vue in issue #33:
- **Stacked Bar Chart** - Called non-existent `API.getPhenotypeDescribedCount()` (removed as YAGNI per issue #33)
- **Time Plot** - Called non-existent `API.getPublicationsCumulativeCount()` (removed as YAGNI per issue #33)
- **Protein Plot** - Called non-existent `API.getProteins()` and `API.getVariantsSmallVariants()` (backend endpoints not implemented)

These visualizations should be reimplemented with proper v2 API endpoints in issues #41, #42, and the protein plot functionality below.

---

## Issue #41: feat(frontend): add phenotype distribution stacked bar chart

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

## Issue #42: feat(frontend): add publication timeline visualization

### Overview
D3.js timeline showing phenopackets added over time by publication.

### Visualization
```
2018 ●●●●
2019 ●●●●●●●●
2020 ●●●●●●●●●●●●
2021 ●●●●●●●●●●●●●●●●
2022 ●●●●●●●●●●
2023 ●●●●●●
2024 ●●●●
```

### Implementation
- X-axis: Year
- Y-axis: Cumulative count
- Hover: Show publication details
- Click: Navigate to publication detail

### Endpoint
```http
GET /api/v2/phenopackets/aggregate/publications-timeline
```

### Timeline: 6 hours (1 day)
### Labels: `frontend`, `charts`, `visualization`, `p2`

---

## Issue #43: feat(frontend): add phenotype count histogram

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

## Issue #44: feat(frontend): add variant type comparison view

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

## Issue #45: feat(frontend): add clinical subgroup comparisons

### Overview
Compare phenotypes across clinical subgroups.

### Subgroups
- CAKUT-only vs CAKUT+MODY
- CKD Stage 3 vs 4 vs 5
- With diabetes vs Without
- With genital abnormalities vs Without

### Implementation
- Reuse comparison component from #44
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

## Issue #46: feat(frontend): implement Kaplan-Meier survival curves

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

**Before implementing issue #46, audit phenopackets for temporal data:**

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
| **< 10% have temporal data** | ❌ **DESCOPE issue #46** - Not enough data for survival analysis |
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
