# Table Search, Filter, and URL Sync Improvement Plan

## Executive Summary

This document outlines a comprehensive plan to fix and enhance the search, filter, sort, and URL synchronization functionality across the Phenopackets, Publications, and Variants tables. The current implementation has several gaps that limit usability and shareability of queries.

---

## Current State Analysis

### Issues Identified

#### 1. Search Functionality Doesn't Work Correctly

| Table | Issue | Root Cause |
|-------|-------|------------|
| **Phenopackets** | Search for "Male" returns 0 results | Backend full-text search uses `plainto_tsquery` on `search_vector` which doesn't include the `sex` enum field |
| **Phenopackets** | Search for variants like "c.165" returns 0 results | Variant data is computed client-side from nested JSONB, not indexed in `search_vector` |
| **Variants** | Search returns 400 Bad Request errors | `variant_search_validation.py` strictly validates HGVS format - partial queries like "c.826" fail because they don't match full HGVS patterns |
| **Publications** | Search works correctly | Server-side search implemented properly |

**Code References:**
- `backend/app/phenopackets/routers/search.py:52-60` - Full-text search implementation
- `backend/app/phenopackets/variant_search_validation.py:140-156` - Strict HGVS validation causing 400 errors

#### 2. Only Some Columns Are Sortable/Filterable

| Table | Column | Sortable | Filterable | Reason |
|-------|--------|----------|------------|--------|
| **Phenopackets** | Subject ID | ✅ | ❌ | Server-side sort |
| **Phenopackets** | Sex | ✅ | ✅ | Server-side sort + filter |
| **Phenopackets** | Phenotypes | ❌ | ❌ | **Computed client-side** (line 256-260) |
| **Phenopackets** | Variant | ❌ | ❌ | **Computed client-side** (line 261) |
| **Variants** | All columns | ✅ | Partial | Type, Classification have filters; others don't |
| **Publications** | All except Links | ✅ | ❌ | No column filters implemented |

**Code References:**
- `frontend/src/views/Phenopackets.vue:250-262` - Headers with `sortable: false`
- `frontend/src/views/Variants.vue:308-322` - All headers sortable

#### 3. Filter Icon Positioning Issues

The filter icons (funnel) in table headers appear visually disconnected from column titles:
- In Phenopackets: Sex column filter icon floats to the right
- In Variants: Type and Classification filter icons positioned inconsistently

**Code References:**
- `frontend/src/views/Phenopackets.vue:102-149` - Custom header template for Sex
- `frontend/src/views/Variants.vue:72-117` - Custom header template for Type

#### 4. URL Doesn't Contain Query Parameters

**Current Behavior:** URL remains static (e.g., `/phenopackets`) regardless of:
- Search queries
- Applied filters
- Sort order
- Current page

**Impact:**
- Cannot bookmark specific searches
- Cannot share filtered views via URL
- Browser back/forward navigation doesn't work with filters
- Page refresh loses all filter state

---

## Proposed Solutions

### Architecture Principles

Following **DRY**, **KISS**, **SOLID**, and **modularization**:

1. **Create reusable composables** for URL-state synchronization
2. **Centralize filter/search logic** in shared utilities
3. **Use consistent patterns** across all three table views
4. **Backend improvements** should be minimal and focused

---

### Solution 1: Fix Search Functionality

#### 1.1 Phenopackets Search Enhancement

**Problem:** Full-text search doesn't cover sex, phenotype counts, or variant data.

**Solution:** Implement hybrid search approach:

```
┌─────────────────────────────────────────────────────────────┐
│                    Hybrid Search Strategy                    │
├─────────────────────────────────────────────────────────────┤
│  User Query                                                  │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1. Check if query matches controlled vocabulary:     │    │
│  │    - Sex: Male, Female, Unknown → filter[sex]=MALE   │    │
│  │    - Has variants: yes/no → filter[has_variants]     │    │
│  └─────────────────────────────────────────────────────┘    │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 2. If HGVS-like (c., p., starts with chr):          │    │
│  │    → Route to variant-specific search                │    │
│  └─────────────────────────────────────────────────────┘    │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 3. Otherwise: Full-text search on search_vector      │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

**Frontend Implementation:**

```javascript
// frontend/src/composables/useSmartSearch.js
export function useSmartSearch() {
  const parseSearchQuery = (query) => {
    const normalized = query.trim().toLowerCase();

    // Check for sex values
    const sexMap = {
      'male': 'MALE',
      'female': 'FEMALE',
      'unknown': 'UNKNOWN_SEX',
      'other': 'OTHER_SEX'
    };
    if (sexMap[normalized]) {
      return { type: 'filter', field: 'sex', value: sexMap[normalized] };
    }

    // Check for HGVS-like patterns (allow partial matching)
    if (/^c\.\d+/.test(query) || /^p\.[A-Z]/.test(query)) {
      return { type: 'variant_search', value: query };
    }

    // Check for variant keywords
    if (['cnv', 'snv', 'deletion', 'pathogenic'].includes(normalized)) {
      return { type: 'variant_filter', value: query };
    }

    // Default to full-text search
    return { type: 'fulltext', value: query };
  };

  return { parseSearchQuery };
}
```

#### 1.2 Variants Search Fix

**Problem:** Strict HGVS validation in `variant_search_validation.py` rejects partial queries.

**Root Cause:** Lines 150-156 validate HGVS format strictly for search queries:
```python
# Current code rejects partial HGVS like "c.826"
if query_stripped.startswith(("c.", "p.", "g.")):
    if not validate_hgvs_notation(query_stripped):
        raise HTTPException(status_code=400, detail=f"Invalid HGVS notation format")
```

**Solution: REUSE the Global Search Pattern**

The homepage global search already handles partial HGVS correctly using a hybrid strategy:

**Existing Pattern from `backend/app/search/repositories.py:74-153`:**
```python
# GlobalSearchRepository.search() - REUSE THIS PATTERN
# Combines: Full-text search + prefix matching + ILIKE fallback

params = {
    "query": query,
    "query_like": f"%{query}%",  # Enables partial matching!
}

# Hybrid search with ILIKE fallback
sql = """
    WITH exact_matches AS (...FTS...),
    prefix_matches AS (...prefix FTS...),
    ilike_matches AS (
        SELECT ... WHERE label ILIKE :query_like  -- THIS is the key!
    )
    SELECT * FROM combined...
"""
```

**Apply to Variants Search:**

**Step 1: Relax validation (DRY - same pattern as global search)**
```python
# backend/app/phenopackets/variant_search_validation.py

def validate_search_query(query: Optional[str]) -> Optional[str]:
    if not query:
        return None

    if len(query) > 200:
        raise HTTPException(status_code=400, detail="Query too long")

    if not is_safe_search_query(query):
        raise HTTPException(status_code=400, detail="Invalid characters")

    # REMOVED: Strict HGVS validation
    # Search should allow partial matches - validation is for DATA ENTRY, not SEARCH
    # The SQL query handles partial matching via ILIKE (same as GlobalSearchRepository)

    return query.strip()
```

**Step 2: Reuse ILIKE pattern in variant_query_builder.py**
```python
# backend/app/phenopackets/routers/aggregations/variant_query_builder.py

def with_text_search(self, query: str) -> 'VariantQueryBuilder':
    """Hybrid search supporting partial matches (reuses global search pattern)."""
    search_pattern = f"%{query}%"

    # Same ILIKE fallback strategy as GlobalSearchRepository
    self.conditions.append("""(
        transcript ILIKE :search_pattern
        OR protein ILIKE :search_pattern
        OR label ILIKE :search_pattern
        OR hg38 ILIKE :search_pattern
        OR variant_id ILIKE :search_pattern
        OR structural_type ILIKE :search_pattern
        OR pathogenicity ILIKE :search_pattern
    )""")
    self.params["search_pattern"] = search_pattern
    return self
```

**Why This Works:**
- `"c.826"` → matches `transcript ILIKE '%c.826%'` → finds "c.826C>G"
- `"pathogenic"` → matches `pathogenicity ILIKE '%pathogenic%'` → finds "PATHOGENIC", "LIKELY_PATHOGENIC"
- `"CNV"` → matches `structural_type ILIKE '%CNV%'` → finds all CNVs
- No validation errors because we removed the strict HGVS check

---

### Solution 2: Enable Sorting/Filtering for All Columns

#### 2.1 Phenopackets: Server-Side Computed Columns

**Problem:** `features_count` and `variant_display` are computed client-side.

**Solution:** Add generated/computed columns to PostgreSQL or use materialized view.

**Option A: PostgreSQL Generated Columns (Recommended)**

```sql
-- Migration: Add generated columns for sortable phenopacket fields

ALTER TABLE phenopackets ADD COLUMN IF NOT EXISTS
  features_count INTEGER GENERATED ALWAYS AS (
    jsonb_array_length(
      COALESCE(phenopacket->'phenotypicFeatures', '[]'::jsonb)
    )
  ) STORED;

ALTER TABLE phenopackets ADD COLUMN IF NOT EXISTS
  has_variant BOOLEAN GENERATED ALWAYS AS (
    jsonb_array_length(
      COALESCE(phenopacket->'interpretations', '[]'::jsonb)
    ) > 0
  ) STORED;

-- Add indexes for sorting
CREATE INDEX IF NOT EXISTS idx_phenopackets_features_count
  ON phenopackets(features_count DESC);
```

**Frontend Update:**

```javascript
// frontend/src/views/Phenopackets.vue
headers: [
  { title: 'Subject ID', value: 'subject_id', sortable: true },
  { title: 'Sex', value: 'sex', sortable: true },
  { title: 'Phenotypes', value: 'features_count', sortable: true }, // Now server-side
  { title: 'Variant', value: 'has_variant', sortable: true },       // Boolean sortable
],
```

#### 2.2 Add Column Filters to All Tables

**Create Reusable Filter Component:**

```vue
<!-- frontend/src/components/common/ColumnFilter.vue -->
<template>
  <v-menu :close-on-content-click="false" location="bottom">
    <template #activator="{ props }">
      <v-btn
        icon
        size="x-small"
        variant="text"
        v-bind="props"
        :color="hasValue ? 'primary' : 'default'"
        class="ml-1"
      >
        <v-icon size="small">
          {{ hasValue ? 'mdi-filter' : 'mdi-filter-outline' }}
        </v-icon>
      </v-btn>
    </template>
    <v-card min-width="200" max-width="280">
      <v-card-title class="text-subtitle-2 py-2">
        <v-icon size="small" class="mr-2">{{ icon }}</v-icon>
        Filter: {{ title }}
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-3">
        <slot />
      </v-card-text>
      <v-divider />
      <v-card-actions class="pa-2">
        <v-spacer />
        <v-btn size="small" variant="text" @click="$emit('clear')">Clear</v-btn>
      </v-card-actions>
    </v-card>
  </v-menu>
</template>
```

**Consistent Header Template:**

```vue
<!-- Unified header slot pattern -->
<template #header.columnName="{ column, getSortIcon, toggleSort, isSorted }">
  <div class="d-flex align-center header-cell">
    <div class="flex-grow-1 sortable-area" @click="toggleSort(column)">
      <span class="header-title">{{ column.title }}</span>
      <v-icon v-if="isSorted(column)" size="small" class="ml-1">
        {{ getSortIcon(column) }}
      </v-icon>
    </div>
    <ColumnFilter
      :title="column.title"
      :has-value="!!filterValues[column.key]"
      icon="mdi-filter"
      @clear="clearFilter(column.key)"
    >
      <v-select
        v-model="filterValues[column.key]"
        :items="filterOptions[column.key]"
        density="compact"
        variant="outlined"
        clearable
        hide-details
      />
    </ColumnFilter>
  </div>
</template>
```

---

### Solution 3: Fix Filter Icon Positioning

**Problem:** Filter icons appear detached from column headers.

**CSS Solution:**

```css
/* frontend/src/components/common/AppDataTable.vue */

.header-cell {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
}

.sortable-area {
  display: flex;
  align-items: center;
  flex-grow: 1;
  cursor: pointer;
  user-select: none;
  min-width: 0;
}

.sortable-area:hover {
  opacity: 0.7;
}

.header-title {
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Ensure filter button stays adjacent to title */
:deep(.v-data-table-header__content) {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 4px;
}
```

---

### Solution 4: URL Query Parameter Synchronization

**Create Reusable Composable:**

```javascript
// frontend/src/composables/useTableUrlSync.js
import { watch, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { isEqual, omitBy, isNil } from 'lodash-es';

export function useTableUrlSync(options = {}) {
  const route = useRoute();
  const router = useRouter();

  const {
    defaultPage = 1,
    defaultPageSize = 10,
    defaultSort = null,
    filterKeys = [],
    onStateChange = () => {},
  } = options;

  // Read state from URL
  const getStateFromUrl = () => ({
    page: parseInt(route.query.page) || defaultPage,
    pageSize: parseInt(route.query.pageSize) || defaultPageSize,
    sort: route.query.sort || defaultSort,
    search: route.query.q || '',
    filters: filterKeys.reduce((acc, key) => {
      if (route.query[key]) acc[key] = route.query[key];
      return acc;
    }, {}),
  });

  // Write state to URL
  const updateUrl = (state) => {
    const query = omitBy({
      page: state.page !== defaultPage ? state.page : undefined,
      pageSize: state.pageSize !== defaultPageSize ? state.pageSize : undefined,
      sort: state.sort !== defaultSort ? state.sort : undefined,
      q: state.search || undefined,
      ...state.filters,
    }, isNil);

    // Avoid redundant navigation
    if (!isEqual(route.query, query)) {
      router.replace({ query });
    }
  };

  // Watch URL changes (back/forward navigation)
  watch(
    () => route.query,
    () => {
      onStateChange(getStateFromUrl());
    },
    { deep: true }
  );

  // Initialize from URL on mount
  onMounted(() => {
    const initialState = getStateFromUrl();
    onStateChange(initialState);
  });

  return {
    getStateFromUrl,
    updateUrl,
  };
}
```

**Usage in View Component:**

```javascript
// frontend/src/views/Phenopackets.vue
import { useTableUrlSync } from '@/composables/useTableUrlSync';

export default {
  setup() {
    const { getStateFromUrl, updateUrl } = useTableUrlSync({
      defaultSort: '-created_at',
      filterKeys: ['sex', 'has_variants'],
      onStateChange: (state) => {
        // Apply state to component
        this.pagination.currentPage = state.page;
        this.pagination.pageSize = state.pageSize;
        this.searchQuery = state.search;
        this.filterValues = state.filters;
        this.fetchPhenopackets();
      },
    });

    return { getStateFromUrl, updateUrl };
  },

  methods: {
    applySearch() {
      this.updateUrl({
        page: 1,
        pageSize: this.pagination.pageSize,
        search: this.searchQuery,
        filters: this.filterValues,
        sort: this.currentSort,
      });
    },
  },
};
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1)

1. **Create shared composables:**
   - `useTableUrlSync.js` - URL state synchronization
   - `useSmartSearch.js` - Intelligent search parsing
   - `useTableFilters.js` - Filter state management

2. **Create shared components:**
   - `ColumnFilter.vue` - Reusable filter dropdown
   - Refactor `AppDataTable.vue` for consistent header slots

3. **Fix CSS issues:**
   - Standardize header cell layout
   - Fix filter icon positioning

### Phase 2: Backend Enhancements (Week 2)

1. **Phenopackets search:**
   - Add `features_count` generated column (migration)
   - Update search endpoint to support hybrid search
   - Add sex filter quick-detection

2. **Variants search:**
   - Relax HGVS validation for search queries
   - Add ILIKE-based partial matching
   - Support searching by classification keywords

3. **Publications:**
   - Add column-level filters to API

### Phase 3: Frontend Integration (Week 3)

1. **Phenopackets view:**
   - Enable sorting on all columns
   - Add filters to Subject ID, Phenotypes, Variant columns
   - Integrate URL sync

2. **Variants view:**
   - Add filters to all columns
   - Fix search to use relaxed validation
   - Integrate URL sync

3. **Publications view:**
   - Add column filters
   - Integrate URL sync

### Phase 4: Testing & Polish (Week 4)

1. **Unit tests:**
   - Composable tests
   - API search tests with edge cases

2. **E2E tests:**
   - URL navigation (back/forward)
   - Filter persistence across refreshes
   - Deep linking

3. **Documentation:**
   - Update API docs
   - Add examples to README

---

## File Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `frontend/src/composables/useTableUrlSync.js` | URL-state synchronization |
| `frontend/src/composables/useSmartSearch.js` | Intelligent search parsing |
| `frontend/src/composables/useTableFilters.js` | Filter state management |
| `frontend/src/components/common/ColumnFilter.vue` | Reusable filter component |
| `backend/migrations/versions/xxx_add_features_count.py` | Add generated column |

### Modified Files

| File | Changes |
|------|---------|
| `frontend/src/views/Phenopackets.vue` | URL sync, enable all sorting, add filters |
| `frontend/src/views/Variants.vue` | URL sync, fix search, add all filters |
| `frontend/src/views/Publications.vue` | URL sync, add column filters |
| `frontend/src/components/common/AppDataTable.vue` | Header slot improvements, CSS fixes |
| `backend/app/phenopackets/variant_search_validation.py` | Relax search validation |
| `backend/app/phenopackets/routers/aggregations/variant_query_builder.py` | ILIKE search |
| `backend/app/phenopackets/routers/search.py` | Hybrid search support |

---

## Success Criteria

- [ ] Searching "Male" in Phenopackets returns all male individuals
- [ ] Searching "c.826" in Variants returns matching variants
- [ ] Searching "pathogenic" in Variants returns all pathogenic variants
- [ ] All columns in all tables are sortable
- [ ] All columns have filter dropdowns where applicable
- [ ] Filter icons are positioned consistently next to column headers
- [ ] URL updates when search/filter/sort/page changes
- [ ] Pasting URL with query params loads correct filtered view
- [ ] Browser back/forward navigation preserves filter state
- [ ] Page refresh preserves current filters

---

## References

- [Vue Router - Data Fetching](https://router.vuejs.org/guide/advanced/data-fetching.html)
- [vue-datatable-url-sync](https://github.com/socotecio/vue-datatable-url-sync)
- [Vuetify Data Tables - Server Side](https://vuetifyjs.com/en/components/data-tables/server-side-tables/)
- [Feature Request: v-data-table-server filtering](https://github.com/vuetifyjs/vuetify/issues/17140)
- [URL Query Parameters with Vue](https://serversideup.net/blog/url-query-parameters-with-javascript-vue-2-and-vue-3/)
