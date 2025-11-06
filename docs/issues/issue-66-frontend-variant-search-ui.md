# Issue #66: feat(frontend): add variant search UI with filters

## Overview

Add frontend search interface to the variants list page, enabling users to quickly find specific variants by HGVS notation, gene, type, and pathogenicity classification.

**Current:** Variants list shows all variants without search/filter capabilities
**Target:** Interactive search bar with filters, active filter chips, and real-time result counts

## Why This Matters

With potentially hundreds of unique variants in the database, users need efficient ways to find specific variants:

- **Clinicians:** Quickly locate a patient's variant by HGVS notation
- **Researchers:** Filter to pathogenic variants for genotype-phenotype studies
- **Geneticists:** Find all variants in a specific gene or of a certain type

### Current User Experience (Without Search)

```
Researcher wants to find: c.1654-2A>T variant
Current workflow:
1. Load variants page (shows all ~200 variants in table)
2. Use browser Ctrl+F to search in rendered HTML
3. May miss variant if notation differs slightly
4. Manual scrolling through paginated results
⏱️ Time: 2-3 minutes per search
```

### Target User Experience (With Search)

```
Researcher wants to find: c.1654-2A>T variant
New workflow:
1. Load variants page
2. Type "1654-2" in search box
3. Results filtered instantly (debounced API call)
4. See "Showing 3 of 200 variants"
⏱️ Time: 5 seconds
```

## Required Changes

### 1. Search Bar Component

**File:** `frontend/src/views/Variants.vue`

Add search UI above the variants table:

```vue
<template>
  <v-container fluid>
    <!-- Search and Filter Section -->
    <v-card class="mb-4">
      <v-card-title>Search Variants</v-card-title>
      <v-card-text>
        <v-row>
          <!-- Text Search -->
          <v-col cols="12" md="6">
            <v-text-field
              v-model="searchQuery"
              label="Search"
              placeholder="Enter HGVS, gene symbol, or variant ID"
              prepend-inner-icon="mdi-magnify"
              clearable
              @input="debouncedSearch"
              :loading="loading"
            >
              <template #append-inner>
                <v-menu>
                  <template #activator="{ props }">
                    <v-btn
                      icon="mdi-help-circle-outline"
                      variant="text"
                      size="small"
                      v-bind="props"
                    />
                  </template>
                  <v-list dense>
                    <v-list-item>
                      <v-list-item-title class="font-weight-bold">
                        Search Examples:
                      </v-list-item-title>
                    </v-list-item>
                    <v-list-item>
                      <v-list-item-subtitle>c.1654-2A>T</v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <v-list-item-subtitle>p.Ser546Phe</v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <v-list-item-subtitle>HNF1B</v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <v-list-item-subtitle>chr17:36098063</v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-menu>
              </template>
            </v-text-field>
          </v-col>

          <!-- Variant Type Filter -->
          <v-col cols="12" md="2">
            <v-select
              v-model="filterType"
              :items="variantTypes"
              label="Type"
              clearable
              @update:model-value="applyFilters"
              :disabled="loading"
            />
          </v-col>

          <!-- Classification Filter -->
          <v-col cols="12" md="2">
            <v-select
              v-model="filterClassification"
              :items="classifications"
              label="Classification"
              clearable
              @update:model-value="applyFilters"
              :disabled="loading"
            />
          </v-col>

          <!-- Gene Filter -->
          <v-col cols="12" md="2">
            <v-select
              v-model="filterGene"
              :items="genes"
              label="Gene"
              clearable
              @update:model-value="applyFilters"
              :disabled="loading"
            />
          </v-col>
        </v-row>

        <!-- Active Filters Display -->
        <v-row v-if="hasActiveFilters">
          <v-col cols="12">
            <v-chip-group>
              <v-chip
                v-if="searchQuery"
                closable
                @click:close="clearSearch"
                color="primary"
                variant="flat"
              >
                <v-icon left size="small">mdi-magnify</v-icon>
                Search: {{ searchQuery }}
              </v-chip>
              <v-chip
                v-if="filterType"
                closable
                @click:close="clearTypeFilter"
                color="secondary"
                variant="flat"
              >
                <v-icon left size="small">mdi-dna</v-icon>
                Type: {{ filterType }}
              </v-chip>
              <v-chip
                v-if="filterClassification"
                closable
                @click:close="clearClassificationFilter"
                :color="getClassificationColor(filterClassification)"
                variant="flat"
              >
                <v-icon left size="small">mdi-alert-circle</v-icon>
                {{ filterClassification }}
              </v-chip>
              <v-chip
                v-if="filterGene"
                closable
                @click:close="clearGeneFilter"
                color="info"
                variant="flat"
              >
                <v-icon left size="small">mdi-gene</v-icon>
                Gene: {{ filterGene }}
              </v-chip>
              <v-chip
                color="error"
                variant="outlined"
                @click="clearAllFilters"
              >
                <v-icon left size="small">mdi-close</v-icon>
                Clear All
              </v-chip>
            </v-chip-group>
          </v-col>
        </v-row>

        <!-- Results Count -->
        <v-row>
          <v-col cols="12">
            <div class="d-flex align-center">
              <v-chip color="info" size="small" variant="flat">
                <v-icon left size="small">mdi-filter</v-icon>
                {{ filteredCount }} of {{ totalCount }} variants
              </v-chip>
              <v-spacer />
              <v-btn
                v-if="hasActiveFilters"
                variant="text"
                size="small"
                @click="clearAllFilters"
              >
                <v-icon left>mdi-refresh</v-icon>
                Reset Filters
              </v-btn>
            </div>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Variants Table -->
    <v-data-table
      :headers="headers"
      :items="variants"
      :loading="loading"
      class="elevation-1"
    >
      <!-- Existing table template -->
    </v-data-table>
  </v-container>
</template>

<script>
import { debounce } from 'lodash-es';

export default {
  name: 'Variants',
  data() {
    return {
      searchQuery: '',
      filterType: null,
      filterClassification: null,
      filterGene: null,
      variants: [],
      filteredCount: 0,
      totalCount: 0,
      loading: false,
      variantTypes: ['SNV', 'deletion', 'duplication', 'insertion', 'inversion', 'CNV'],
      classifications: [
        'PATHOGENIC',
        'LIKELY_PATHOGENIC',
        'UNCERTAIN_SIGNIFICANCE',
        'LIKELY_BENIGN',
        'BENIGN',
      ],
      genes: ['HNF1B'], // Can be expanded for multi-gene databases
      headers: [
        { title: 'Variant ID', value: 'variant_id', sortable: true },
        { title: 'Label', value: 'label', sortable: true },
        { title: 'Gene', value: 'gene', sortable: true },
        { title: 'Type', value: 'structural_type', sortable: true },
        { title: 'Classification', value: 'classification', sortable: true },
        { title: 'Individuals', value: 'phenopacket_count', sortable: true },
      ],
    };
  },
  computed: {
    hasActiveFilters() {
      return !!(
        this.searchQuery ||
        this.filterType ||
        this.filterClassification ||
        this.filterGene
      );
    },
  },
  created() {
    // Debounce search to prevent excessive API calls (300ms delay)
    this.debouncedSearch = debounce(this.searchVariants, 300);
    this.loadVariants();
  },
  methods: {
    async loadVariants() {
      this.loading = true;
      try {
        const params = {
          skip: 0,
          limit: 1000,
        };

        // Add search query if present
        if (this.searchQuery) {
          params.query = this.searchQuery;
        }

        // Add filters
        if (this.filterType) {
          params.type = this.filterType;
        }
        if (this.filterClassification) {
          params.classification = this.filterClassification;
        }
        if (this.filterGene) {
          params.gene = this.filterGene;
        }

        const response = await this.$api.getVariants(params);
        this.variants = response.data.data;
        this.filteredCount = response.data.total;
        this.totalCount = response.data.total_unfiltered || response.data.total;
      } catch (error) {
        console.error('Error loading variants:', error);
        this.$snackbar.error('Failed to load variants');
      } finally {
        this.loading = false;
      }
    },
    searchVariants() {
      this.loadVariants();
    },
    applyFilters() {
      this.loadVariants();
    },
    clearSearch() {
      this.searchQuery = '';
      this.debouncedSearch();
    },
    clearTypeFilter() {
      this.filterType = null;
      this.applyFilters();
    },
    clearClassificationFilter() {
      this.filterClassification = null;
      this.applyFilters();
    },
    clearGeneFilter() {
      this.filterGene = null;
      this.applyFilters();
    },
    clearAllFilters() {
      this.searchQuery = '';
      this.filterType = null;
      this.filterClassification = null;
      this.filterGene = null;
      this.loadVariants();
    },
    getClassificationColor(classification) {
      const colors = {
        PATHOGENIC: 'error',
        LIKELY_PATHOGENIC: 'warning',
        UNCERTAIN_SIGNIFICANCE: 'info',
        LIKELY_BENIGN: 'success',
        BENIGN: 'success',
      };
      return colors[classification] || 'grey';
    },
  },
};
</script>

<style scoped>
/* Add custom styles if needed */
</style>
```

### 2. API Client Integration

**File:** `frontend/src/api/index.js`

Add the `getVariants()` method to call the backend search endpoint:

```javascript
/**
 * Get variants with search and filters
 * Calls backend /aggregate/variants/search endpoint (Issue #64)
 *
 * @param {Object} params - Search parameters
 * @param {string} params.query - Text search (HGVS, gene, variant ID)
 * @param {string} params.type - Variant type filter (SNV, deletion, etc.)
 * @param {string} params.classification - ACMG classification filter
 * @param {string} params.gene - Gene symbol filter
 * @param {number} params.skip - Pagination offset (default: 0)
 * @param {number} params.limit - Results limit (default: 100, max: 1000)
 * @returns {Promise} Axios response with variant data
 */
export const getVariants = (params = {}) => {
  const { query, type, classification, gene, skip = 0, limit = 100 } = params;

  const queryParams = new URLSearchParams();
  if (query) queryParams.append('query', query);
  if (type) queryParams.append('type', type);
  if (classification) queryParams.append('classification', classification);
  if (gene) queryParams.append('gene', gene);
  queryParams.append('skip', skip);
  queryParams.append('limit', limit);

  return apiClient.get(`/phenopackets/aggregate/variants/search?${queryParams}`);
};
```

### 3. Install lodash-es (if not already installed)

**File:** `frontend/package.json`

Ensure `lodash-es` is in dependencies for debouncing:

```bash
cd frontend
npm install lodash-es
```

## Search Behavior Examples

### Example 1: Text Search by HGVS Notation

```
User types: "c.1654-2A>T"
Frontend:
1. Waits 300ms (debounce)
2. Calls API: GET /variants/search?query=c.1654-2A>T
3. Backend returns matching variants
4. Updates table and shows "3 of 200 variants"
```

### Example 2: Filter by Pathogenicity

```
User selects: Classification = "PATHOGENIC"
Frontend:
1. Immediately calls API (no debounce for dropdown)
2. GET /variants/search?classification=PATHOGENIC
3. Shows only pathogenic variants
4. Red chip displayed: "PATHOGENIC [x]"
```

### Example 3: Combined Search + Filters

```
User types: "deletion" + Type = "deletion" + Classification = "PATHOGENIC"
Frontend:
1. Calls API with all params
2. GET /variants/search?query=deletion&type=deletion&classification=PATHOGENIC
3. Shows pathogenic deletions matching "deletion"
4. Three chips displayed: "Search: deletion", "Type: deletion", "PATHOGENIC"
```

### Example 4: Clear All Filters

```
User clicks: "Clear All" button
Frontend:
1. Resets all filter state
2. Calls API with no params: GET /variants/search
3. Shows all variants
4. Chips removed, count shows "200 of 200 variants"
```

## Implementation Checklist

### Phase 1: Basic Search UI (3 hours)
- [ ] Add search text field to Variants.vue
- [ ] Implement debounced search function (300ms)
- [ ] Wire up API call to backend endpoint
- [ ] Test text search with HGVS notations
- [ ] Add loading states
- [ ] Handle empty results gracefully

### Phase 2: Filter Dropdowns (2 hours)
- [ ] Add variant type dropdown filter
- [ ] Add classification dropdown filter
- [ ] Add gene filter dropdown
- [ ] Wire filters to API params
- [ ] Test filters individually
- [ ] Test combined filters

### Phase 3: Active Filters UI (2 hours)
- [ ] Add active filters chip display
- [ ] Implement individual chip close handlers
- [ ] Add "Clear All" button
- [ ] Add results count display ("X of Y variants")
- [ ] Color-code classification chips
- [ ] Add filter icons to chips

### Phase 4: UX Enhancements (1 hour)
- [ ] Add search help tooltip with examples
- [ ] Add keyboard shortcuts (Enter to search, Esc to clear)
- [ ] Add empty state message ("No variants found")
- [ ] Add error handling for API failures
- [ ] Test responsive layout (mobile/tablet)

### Phase 5: Testing (1 hour)
- [ ] Test search with various HGVS formats (c., p., g.)
- [ ] Test special characters in search (>, -, +)
- [ ] Test filter combinations
- [ ] Test pagination with search results
- [ ] Test empty search (shows all variants)
- [ ] Test debouncing (type fast, only 1 API call)
- [ ] Verify no console errors

## Acceptance Criteria

**Search Functionality:**
- [ ] Search bar accepts text input
- [ ] Search is debounced (300ms delay)
- [ ] Text search works for HGVS notations (c., p., g.)
- [ ] Text search works for variant IDs
- [ ] Text search works for gene symbols
- [ ] Empty search shows all variants

**Filter Functionality:**
- [ ] Type filter works (SNV, deletion, duplication, insertion, inversion, CNV)
- [ ] Classification filter works (P, LP, VUS, LB, B)
- [ ] Gene filter works (HNF1B)
- [ ] Multiple filters can be combined
- [ ] Filters applied immediately (no debounce)

**UI/UX:**
- [ ] Active filters displayed as colored chips
- [ ] Each chip has close button
- [ ] Clear All button removes all filters
- [ ] Results count shows "X of Y variants"
- [ ] Search help tooltip shows examples
- [ ] Loading states shown during API calls
- [ ] No results message displayed when appropriate
- [ ] Frontend is responsive on mobile

**Performance:**
- [ ] Debouncing prevents excessive API calls
- [ ] Max 3 requests per second (300ms debounce)
- [ ] No flickering during debounced typing
- [ ] UI remains responsive during search

**Error Handling:**
- [ ] API errors display user-friendly message
- [ ] Rate limit errors (429) show "Too many requests"
- [ ] Network errors show "Connection failed"
- [ ] Invalid filter values handled gracefully

## Dependencies

- Issue #64 (Backend search endpoint) - ⚠️ **BLOCKER** - Must be completed first
- Issue #34 (Variants list page) - ✅ Required for context
- `lodash-es` npm package - For debouncing

## Performance Impact

**Frontend Performance:**
- Debouncing prevents excessive API calls (max 3/sec)
- Only one pending request at a time
- Results cached until filters change
- Table re-renders minimized with Vue reactivity

**Network Traffic:**
- Without search: Fetches all variants (~100KB)
- With search: Fetches only matching variants (~10-50KB)
- 50-90% reduction in data transferred

**User Experience:**
- Instant feedback on filter changes (<100ms)
- Debounced search feels responsive (300ms)
- Loading indicators show progress
- No page reloads required

## Testing Verification

### Manual Testing

```bash
# 1. Start frontend dev server
cd frontend
npm run dev

# 2. Navigate to http://localhost:5173/variants

# 3. Test Text Search
# - Type "c.1654" slowly
# - Observe only 1 API call after 300ms
# - Verify results filtered

# 4. Test Type Filter
# - Select "deletion" from Type dropdown
# - Verify immediate API call
# - Verify only deletions shown

# 5. Test Classification Filter
# - Select "PATHOGENIC" from Classification dropdown
# - Verify red chip appears
# - Verify only pathogenic variants shown

# 6. Test Combined Filters
# - Keep "deletion" and "PATHOGENIC" selected
# - Type "HNF1B" in search
# - Verify all filters applied (AND logic)
# - Verify 3 chips displayed

# 7. Test Clear All
# - Click "Clear All" button
# - Verify all filters removed
# - Verify all variants shown

# 8. Test Empty Results
# - Search for "xyz123" (non-existent)
# - Verify "No variants found" message
# - Verify results count shows "0 of 200"

# 9. Test Error Handling
# - Stop backend server
# - Try to search
# - Verify error message displayed
```

### Browser DevTools Verification

```javascript
// 1. Open DevTools → Network tab
// 2. Type "c.1654" slowly
// 3. Verify only 1 request sent (after 300ms)

// Expected request:
// GET /api/v2/phenopackets/aggregate/variants/search?query=c.1654&skip=0&limit=100

// 4. Apply filters
// Expected request:
// GET /api/v2/phenopackets/aggregate/variants/search?query=c.1654&type=SNV&classification=PATHOGENIC&skip=0&limit=100

// 5. Check response structure:
{
  "data": [
    {
      "variant_id": "ga4gh:VA.xxx",
      "label": "HNF1B:c.1654-2A>T",
      "gene": "HNF1B",
      "structural_type": "SNV",
      "classification": "PATHOGENIC",
      "expressions": [...]
    }
  ],
  "total": 3,
  "total_unfiltered": 200,
  "skip": 0,
  "limit": 100
}
```

## Files Modified/Created

### Modified Files (2 files, ~200 lines added)
- `frontend/src/views/Variants.vue` (+150 lines for search UI)
- `frontend/src/api/index.js` (+20 lines for getVariants method)

### Dependencies Added
- `lodash-es` (if not already in package.json)

## Timeline

**Estimated:** 9 hours (1.1 days)

**Breakdown:**
- Phase 1 (Basic Search): 3 hours
- Phase 2 (Filters): 2 hours
- Phase 3 (Active Filters UI): 2 hours
- Phase 4 (UX Enhancements): 1 hour
- Phase 5 (Testing): 1 hour

## Priority

**P1 (High)** - Core feature for variant discovery

**Rationale:**
- Directly impacts user ability to find variants
- Complements backend search endpoint (Issue #64)
- Required for efficient variant lookup
- Relatively quick win (9 hours)

## Labels

`frontend`, `search`, `variants`, `ui`, `p1`

## Notes

**Debouncing Strategy:**
- Text search: 300ms debounce (user typing)
- Dropdowns: No debounce (instant feedback)
- Clear buttons: Instant action

**Filter Combination Logic:**
- All filters use AND logic (all must match)
- Empty filters ignored (treated as "any")
- Backend enforces same logic

**Accessibility:**
- All inputs labeled correctly
- Keyboard navigation works
- Screen reader friendly
- ARIA labels on icons

**Future Enhancements (Not in Scope):**
- Save recent searches (localStorage)
- URL params for shareable filtered views
- Export filtered results to CSV
- Advanced search with OR logic
- Search history dropdown

**Related Work:**
- Issue #64 provides the backend endpoint
- Issue #34 provides the variants table structure
- Issue #65 (gene visualization) may use filtered variants
