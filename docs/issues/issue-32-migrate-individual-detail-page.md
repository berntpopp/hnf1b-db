# Issue #32: feat(frontend): migrate individual detail page to phenopackets v2

## Overview

The individual detail page (`frontend/src/views/PageIndividual.vue`) displays flat normalized data from separate individuals and variants tables that no longer exist. It needs complete redesign to display nested GA4GH Phenopackets v2 structure.

**Current State:** Shows individual + variant from two separate database tables
**Required State:** Display complete phenopacket document with all GA4GH sections (subject, features, diseases, interpretations, measurements, metadata)

## Why This Matters

### Current Implementation (Broken)

```javascript
// Route: /individuals/P001
// Expects flat individual object with nested variant
const individual = {
  individual_id: "P001",
  Sex: "MALE",
  IndividualIdentifier: "patient-001",
  DupCheck: "unique",
  Problematic: null,
  variant: {
    variant_ref: "NM_000458.3:c.123A>G",
    detection_method: "NGS",
    segregation: "De novo"
  }
};
```

**Problem:** This data structure no longer exists. Backend v2 uses nested JSONB phenopackets.

### New Implementation (Phenopackets v2)

```javascript
// Route: /phenopackets/phenopacket-001
// GET /api/v2/phenopackets/phenopacket-001
const phenopacket = {
  id: "uuid",
  phenopacket_id: "phenopacket-001",
  phenopacket: {
    id: "phenopacket-001",
    subject: { /* demographics */ },
    phenotypicFeatures: [ /* HPO terms */ ],
    diseases: [ /* MONDO terms */ ],
    interpretations: [ /* variants with VRS */ ],
    measurements: [ /* lab values */ ],
    metaData: { /* provenance, external references */ }
  }
};
```

## Required Changes

### 1. File Renaming and Routes

**Rename View:**
```bash
mv frontend/src/views/PageIndividual.vue frontend/src/views/PagePhenopacket.vue
```

**Update Router** (`frontend/src/router/index.js`):
```javascript
// Before:
{
  path: '/individuals/:individual_id',
  name: 'PageIndividual',
  component: () => import('../views/PageIndividual.vue'),
}

// After:
{
  path: '/phenopackets/:phenopacket_id',
  name: 'PagePhenopacket',
  component: () => import('../views/PagePhenopacket.vue'),
}
```

### 2. Component Architecture

Create modular card components in `frontend/src/components/phenopacket/`:

#### Core Components (Required - Always Have Data)
- `SubjectCard.vue` - Demographics (ID, sex, age, karyotype)
- `DiseasesCard.vue` - MONDO disease terms with onset
- `MetadataCard.vue` - External references (PMIDs), updates, resources

#### Optional Components (Conditional Rendering)
- `PhenotypicFeaturesCard.vue` - HPO terms with severity/onset
- `InterpretationsCard.vue` - Genomic variants with ACMG pathogenicity
- `MeasurementsCard.vue` - Lab values (if present)

**Note:** `MedicalActionsCard` is NOT needed (no data in current phenopackets)

### 3. Main Page Layout

```vue
<!-- PagePhenopacket.vue structure -->
<template>
  <v-container fluid>
    <!-- Header with phenopacket_id and download button -->

    <!-- 2-Column Responsive Grid -->
    <v-row>
      <v-col cols="12" md="6">
        <SubjectCard :subject="phenopacket.subject" />
      </v-col>
      <v-col cols="12" md="6">
        <DiseasesCard :diseases="phenopacket.diseases" />
      </v-col>

      <!-- Conditional sections -->
      <v-col v-if="hasPhenotypicFeatures" cols="12" md="6">
        <PhenotypicFeaturesCard :features="phenopacket.phenotypicFeatures" />
      </v-col>
      <v-col v-if="hasInterpretations" cols="12">
        <InterpretationsCard :interpretations="phenopacket.interpretations" />
      </v-col>

      <!-- Full-width metadata -->
      <v-col cols="12">
        <MetadataCard :meta-data="phenopacket.metaData" />
      </v-col>
    </v-row>
  </v-container>
</template>
```

### 4. Data Fetching

```javascript
async fetchPhenopacket() {
  this.loading = true;
  try {
    const phenopacketId = this.$route.params.phenopacket_id;
    const response = await getPhenopacket(phenopacketId);
    this.phenopacket = response.data;
  } catch (error) {
    this.error = error.response?.status === 404
      ? `Phenopacket '${phenopacketId}' not found.`
      : 'Failed to load phenopacket.';
  } finally {
    this.loading = false;
  }
}
```

### 5. Helper Functions

**ISO8601 Duration Parser:**
```javascript
formatISO8601Duration(duration) {
  // Parse "P45Y3M" → "45 years, 3 months"
  const regex = /P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?/;
  const matches = duration.match(regex);
  if (!matches) return duration;

  const parts = [];
  if (matches[1]) parts.push(`${matches[1]} year${matches[1] > 1 ? 's' : ''}`);
  if (matches[2]) parts.push(`${matches[2]} month${matches[2] > 1 ? 's' : ''}`);
  if (matches[3]) parts.push(`${matches[3]} day${matches[3] > 1 ? 's' : ''}`);

  return parts.join(', ') || duration;
}
```

**Sex Icons/Colors:**
```javascript
getSexIcon(sex) {
  const icons = {
    MALE: 'mdi-gender-male',
    FEMALE: 'mdi-gender-female',
    OTHER_SEX: 'mdi-gender-non-binary',
    UNKNOWN_SEX: 'mdi-help-circle',
  };
  return icons[sex] || 'mdi-help-circle';
}

getSexColor(sex) {
  const colors = {
    MALE: 'blue',
    FEMALE: 'pink',
    OTHER_SEX: 'purple',
    UNKNOWN_SEX: 'grey',
  };
  return colors[sex] || 'grey';
}
```

## Implementation Checklist

### Phase 1: File Setup
- [x] Rename `PageIndividual.vue` → `PagePhenopacket.vue`
- [x] Update route in `router/index.js`
- [x] Create `frontend/src/components/phenopacket/` directory

### Phase 2: Component Implementation
- [x] Create `SubjectCard.vue` (demographics)
- [x] Create `PhenotypicFeaturesCard.vue` (HPO terms)
- [x] Create `DiseasesCard.vue` (MONDO/OMIM)
- [x] Create `InterpretationsCard.vue` (variants)
- [x] Create `MeasurementsCard.vue` (lab values)
- [x] Create `MetadataCard.vue` (provenance)

### Phase 3: Main Page
- [x] Implement data fetching with `getPhenopacket()`
- [x] Add loading state
- [x] Add error handling (404, etc.)
- [x] Conditional rendering for optional sections
- [x] Add download JSON button

### Phase 4: Data Formatting
- [x] ISO8601 duration parser
- [x] Date formatter
- [x] Sex icon/color helpers
- [x] ACMG pathogenicity labels

### Phase 5: UI Polish
- [x] Section color coding (blue=subject, green=features, red=diseases, purple=variants)
- [x] Responsive layout (col-12 md-6 for cards)
- [x] Tooltips for long terms
- [x] Empty state messages

## Testing Verification

### Manual Testing Steps

```bash
# 1. Start backend and frontend
cd backend && make backend  # Terminal 1
cd frontend && npm run dev   # Terminal 2

# 2. Navigate to phenopackets list
# http://localhost:5173/phenopackets

# 3. Click a phenopacket ID chip
# Should navigate to: /phenopackets/phenopacket-001

# 4. Verify all sections display correctly
```

### Expected Sections

| Section | Always Shown? | Content |
|---------|--------------|---------|
| Subject | ✅ Yes | ID, sex with icon, age, karyotype |
| Diseases | ✅ Yes | MONDO terms with onset |
| Phenotypic Features | ⚠️ Conditional | HPO terms (96% have data) |
| Interpretations | ⚠️ Conditional | Variants (49% have data) |
| Measurements | ⚠️ Conditional | Lab values (rare) |
| Metadata | ✅ Yes | External refs, created date, resources |

### Test Cases

1. **Download JSON Button**
   - Click "Download JSON"
   - Should download `phenopacket-001.json`
   - File should contain complete phenopacket structure

2. **Back Navigation**
   - Click "Back to List"
   - Should return to `/phenopackets`

3. **404 Handling**
   - Navigate to `/phenopackets/invalid-id`
   - Should show error message
   - Back button should still work

## Acceptance Criteria

### Functionality
- [ ] Page loads phenopacket by ID from v2 API
- [ ] All GA4GH sections display correctly
- [ ] Loading spinner during fetch
- [ ] Error message on 404/failure
- [ ] Download JSON button works
- [ ] Back button navigates to list

### Data Display
- [ ] Subject: ID, sex (with icon), age, karyotype
- [ ] Phenotypic features: HPO terms with severity/onset
- [ ] Diseases: MONDO/OMIM terms with onset
- [ ] Interpretations: Variants with pathogenicity
- [ ] Measurements: Lab values with units (if present)
- [ ] Metadata: Created date, external references

### UI/UX
- [ ] Section cards color-coded
- [ ] Responsive layout (2-column on desktop)
- [ ] Empty states for missing sections
- [ ] ISO8601 durations formatted human-readable
- [ ] Sex icons color-coded
- [ ] HPO/MONDO IDs displayed as chips

### Code Quality
- [ ] Reusable section components
- [ ] Props validation in components
- [ ] No references to old Individual naming
- [ ] ESLint passes
- [ ] No console errors

## Files Modified/Created

### Created
```
frontend/src/components/phenopacket/
├── SubjectCard.vue                   (new - 120 lines)
├── PhenotypicFeaturesCard.vue        (new - 130 lines)
├── DiseasesCard.vue                  (new - 100 lines)
├── InterpretationsCard.vue           (new - 200 lines)
├── MeasurementsCard.vue              (new - 110 lines)
└── MetadataCard.vue                  (new - 140 lines)
```

### Modified
```
frontend/src/views/
└── PagePhenopacket.vue               (rewritten - 190 lines)

frontend/src/router/
└── index.js                          (route updated)
```

## Dependencies

**Depends On:**
- Issue #30 (API client migration) - ✅ **BLOCKER**
- Issue #31 (List view) - For navigation from list

**Blocks:**
- None

## Performance Impact

**Before (v1):**
```javascript
// Broken - returns 404
GET /api/individuals/P001 → 404 Not Found
```

**After (v2):**
```javascript
// Working - returns phenopacket
GET /api/v2/phenopackets/phenopacket-001 → 200 OK (~150ms)
```

**Improvement:** Goes from broken (404) to working (200) ✅

## Timeline

- **Phase 1:** File setup - 0.5 hours (✅ DONE)
- **Phase 2:** Component implementation - 4 hours (✅ DONE)
- **Phase 3:** Main page - 2 hours (✅ DONE)
- **Phase 4:** Data formatting - 1 hour (✅ DONE)
- **Phase 5:** UI polish - 1 hour (✅ DONE)

**Total:** 8.5 hours (1 day) - ✅ **COMPLETED**

## Priority

**P1 (High)** - Blocking user workflow (detail view broken)

## Labels

`frontend`, `vue`, `phenopackets`, `migration`, `p1`

## Related Issues

- Issue #30: API client migration (dependency)
- Issue #31: Phenopackets list view (navigation)
