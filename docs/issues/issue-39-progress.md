# Issue #39: Global Phenopacket Search - Progress Report

**Status:** In Progress (Backend Phase 1 Complete)
**Started:** 2025-11-10
**Last Updated:** 2025-11-10
**Estimated Remaining:** ~10 hours (4 hours backend + 6 hours frontend)

---

## Overview

Implementing comprehensive global search functionality across phenopackets with:
- PostgreSQL full-text search using tsvector
- HPO term autocomplete with fuzzy matching
- Advanced filtering (phenotypes, diseases, genes, variants)
- Frontend GlobalSearch component with recent searches

---

## ✅ Completed Work

### Phase 1: Database Migration (2 hours) - COMPLETE

**File:** `backend/alembic/versions/8baf0de6a441_add_fulltext_search_to_phenopackets.py`

**Migration Status:** ✅ Successfully applied (confirmed via `alembic current`)

**Database Changes Implemented:**

1. **Full-Text Search Infrastructure**
   - Added `search_vector` tsvector column to `phenopackets` table
   - Created PL/pgSQL trigger function `phenopackets_search_vector_update()`
   - Trigger extracts and indexes:
     - Subject IDs
     - Phenotype labels (HPO terms)
     - Disease labels (MONDO terms)
     - Gene symbols from variant interpretations
   - Created GIN index `idx_phenopackets_fulltext_search` for fast queries
   - Populated search_vector for all 864 existing phenopackets

2. **HPO Term Autocomplete Table**
   - Created `hpo_terms_lookup` table with schema:
     ```sql
     hpo_id VARCHAR(20) PRIMARY KEY
     label TEXT NOT NULL
     phenopacket_count INTEGER NOT NULL DEFAULT 0
     created_at TIMESTAMP DEFAULT NOW()
     ```
   - Enabled `pg_trgm` extension for fuzzy matching
   - Created trigram GIN index `idx_hpo_lookup_label_trgm` for fast prefix search
   - Populated with HPO terms extracted from existing phenopackets
   - Sorted by frequency (most common terms first)

**Technical Decisions:**

- **Trigger-based approach** instead of generated columns
  - PostgreSQL doesn't allow subqueries in GENERATED columns
  - Trigger updates search_vector automatically on INSERT/UPDATE
  - Better for JSONB array extraction and aggregation

- **Separate HPO lookup table** instead of materialized view
  - Faster autocomplete queries (small table, optimized index)
  - Can be manually refreshed or updated via API
  - Includes phenopacket_count for relevance ranking

**Migration Code (Key Sections):**

```python
# Trigger function for auto-updating search_vector
CREATE OR REPLACE FUNCTION phenopackets_search_vector_update()
RETURNS TRIGGER AS $$
DECLARE
    phenotype_labels text;
    disease_labels text;
    gene_symbols text;
BEGIN
    -- Extract phenotype labels from JSONB array
    SELECT string_agg(value->'type'->>'label', ' ')
    INTO phenotype_labels
    FROM jsonb_array_elements(NEW.phenopacket->'phenotypic_features');

    -- Extract disease labels
    SELECT string_agg(value->'term'->>'label', ' ')
    INTO disease_labels
    FROM jsonb_array_elements(NEW.phenopacket->'diseases');

    -- Extract gene symbols
    SELECT string_agg(
        gi.value->'variant_interpretation'->'variation_descriptor'->'gene_context'->>'symbol', ' ')
    INTO gene_symbols
    FROM jsonb_array_elements(NEW.phenopacket->'interpretations') AS interp,
         jsonb_array_elements(interp.value->'diagnosis'->'genomic_interpretations') AS gi;

    -- Build composite search vector
    NEW.search_vector :=
        to_tsvector('english', COALESCE(NEW.phenopacket->'subject'->>'id', '')) ||
        to_tsvector('english', COALESCE(phenotype_labels, '')) ||
        to_tsvector('english', COALESCE(disease_labels, '')) ||
        to_tsvector('english', COALESCE(gene_symbols, ''));

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

# HPO lookup table population
INSERT INTO hpo_terms_lookup (hpo_id, label, phenopacket_count)
SELECT DISTINCT
    pf.value->'type'->>'id' AS hpo_id,
    pf.value->'type'->>'label' AS label,
    COUNT(DISTINCT p.id) AS phenopacket_count
FROM phenopackets p,
     jsonb_array_elements(p.phenopacket->'phenotypic_features') AS pf
WHERE pf.value->'type'->>'id' IS NOT NULL
  AND pf.value->'type'->>'id' LIKE 'HP:%'
GROUP BY hpo_id, label
ORDER BY phenopacket_count DESC;
```

**Verification Commands:**

```bash
# Check migration status
alembic current
# Output: 8baf0de6a441 (head)

# Verify tables and indexes exist
alembic show 8baf0de6a441

# Test search vector (example query)
# SELECT id, ts_rank(search_vector, to_tsquery('kidney')) AS rank
# FROM phenopackets
# WHERE search_vector @@ to_tsquery('kidney')
# ORDER BY rank DESC LIMIT 10;
```

---

## ❌ Remaining Work

### Phase 2: Backend API Endpoints (4 hours) - NOT STARTED

#### Task 1: HPO Autocomplete Endpoint (~2 hours)

**File to Create:** `backend/app/ontology/routers.py`

**Endpoint:** `GET /api/v2/ontology/hpo/autocomplete`

**Query Parameters:**
- `q` (required) - Search query string
- `limit` (optional) - Max results (default: 10)

**Response Format:**
```json
{
  "data": [
    {
      "hpo_id": "HP:0000077",
      "label": "Abnormality of the kidney",
      "phenopacket_count": 456
    },
    ...
  ]
}
```

**Implementation Approach:**

```python
# backend/app/ontology/routers.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from app.database.session import get_db

router = APIRouter(prefix="/api/v2/ontology", tags=["ontology"])

@router.get("/hpo/autocomplete")
async def hpo_autocomplete(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Fast HPO term autocomplete with fuzzy matching.
    Uses trigram similarity for typo tolerance.
    """
    query = text("""
        SELECT hpo_id, label, phenopacket_count,
               similarity(label, :search_term) AS similarity_score
        FROM hpo_terms_lookup
        WHERE label ILIKE :prefix OR label % :search_term
        ORDER BY similarity_score DESC, phenopacket_count DESC
        LIMIT :limit
    """)

    result = await db.execute(
        query,
        {
            "search_term": q,
            "prefix": f"%{q}%",
            "limit": limit
        }
    )

    terms = result.fetchall()
    return {"data": [dict(row) for row in terms]}
```

**Testing:**
```bash
# Test autocomplete
curl "http://localhost:8000/api/v2/ontology/hpo/autocomplete?q=kidney"
curl "http://localhost:8000/api/v2/ontology/hpo/autocomplete?q=kidny"  # typo

# Expected: Returns HPO terms related to kidney
```

---

#### Task 2: Enhanced Search Endpoint (~2 hours)

**File to Modify:** `backend/app/phenopackets/routers/search.py`

**Endpoint:** `GET /api/v2/phenopackets/search` (enhance existing)

**New Query Parameters:**
- `q` (optional) - Full-text search query
- `hpo_id` (optional) - Filter by HPO term ID
- `sex` (optional) - Filter by subject sex
- `gene` (optional) - Filter by gene symbol
- `pmid` (optional) - Filter by publication PMID
- `rank_by_relevance` (optional, default: true) - Sort by search rank

**Response Format (JSON:API v1.1):**
```json
{
  "data": [
    {
      "id": "phenopacket_001",
      "type": "phenopacket",
      "attributes": { ... },
      "meta": {
        "search_rank": 0.894,
        "matched_fields": ["phenotypes", "diseases"]
      }
    }
  ],
  "meta": {
    "total": 42,
    "page": { ... }
  }
}
```

**Implementation Approach:**

```python
# backend/app/phenopackets/routers/search.py
from sqlalchemy import text, select, and_, or_
from app.phenopackets.models import Phenopacket

@router.get("/search")
async def search_phenopackets(
    q: Optional[str] = Query(None),
    hpo_id: Optional[str] = Query(None),
    sex: Optional[str] = Query(None),
    gene: Optional[str] = Query(None),
    pmid: Optional[str] = Query(None),
    rank_by_relevance: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Advanced phenopacket search with full-text and structured filters.
    """

    # Build base query
    if q:
        # Full-text search with ranking
        query = text("""
            SELECT id, phenopacket,
                   ts_rank(search_vector, to_tsquery('english', :search_query)) AS search_rank
            FROM phenopackets
            WHERE search_vector @@ to_tsquery('english', :search_query)
        """)
    else:
        # No full-text search, just filters
        query = select(Phenopacket)

    # Apply structured filters
    filters = []
    if hpo_id:
        filters.append(text("phenopacket @> :hpo_filter"))
    if sex:
        filters.append(Phenopacket.subject_sex == sex)
    if gene:
        filters.append(text("phenopacket @> :gene_filter"))
    if pmid:
        filters.append(text("phenopacket @> :pmid_filter"))

    # Execute query with pagination
    result = await db.execute(
        query,
        {
            "search_query": q,
            "hpo_filter": json.dumps({"phenotypicFeatures": [{"type": {"id": hpo_id}}]}),
            "gene_filter": json.dumps({"interpretations": [{"diagnosis": {"genomicInterpretations": [{"variationInterpretation": {"variationDescriptor": {"geneContext": {"symbol": gene}}}}]}}]}),
            "pmid_filter": json.dumps({"metaData": {"externalReferences": [{"id": f"PMID:{pmid}"}]}}),
            "skip": skip,
            "limit": limit
        }
    )

    phenopackets = result.fetchall()

    # Transform to JSON:API format
    return {
        "data": [
            {
                "id": pp.id,
                "type": "phenopacket",
                "attributes": pp.phenopacket,
                "meta": {"search_rank": pp.search_rank if q else None}
            }
            for pp in phenopackets
        ],
        "meta": {"total": len(phenopackets)}
    }
```

**Testing:**
```bash
# Full-text search
curl "http://localhost:8000/api/v2/phenopackets/search?q=kidney+disease"

# HPO filter
curl "http://localhost:8000/api/v2/phenopackets/search?hpo_id=HP:0000077"

# Combined filters
curl "http://localhost:8000/api/v2/phenopackets/search?q=kidney&sex=FEMALE&gene=HNF1B"
```

---

### Phase 3: Frontend Components (6 hours) - NOT STARTED

#### Task 1: GlobalSearch Vue Component (~3 hours)

**File to Create:** `frontend/src/components/GlobalSearch.vue`

**Features:**
- v-autocomplete component with HPO term suggestions
- Real-time search as user types (debounced 300ms)
- Display recent searches from localStorage
- Navigate to search results page on selection

**Component Structure:**

```vue
<template>
  <v-autocomplete
    v-model="selectedItem"
    v-model:search="searchQuery"
    :items="suggestions"
    :loading="loading"
    placeholder="Search phenopackets, HPO terms, genes..."
    append-inner-icon="mdi-magnify"
    density="comfortable"
    variant="solo"
    auto-select-first
    clearable
    @update:search="debouncedSearch"
    @update:model-value="onSelect"
  >
    <template #item="{ item }">
      <v-list-item>
        <v-list-item-title>{{ item.label }}</v-list-item-title>
        <v-list-item-subtitle>
          {{ item.hpo_id }} · {{ item.phenopacket_count }} phenopackets
        </v-list-item-subtitle>
      </v-list-item>
    </template>

    <template #prepend-item v-if="recentSearches.length">
      <v-list-subheader>Recent Searches</v-list-subheader>
      <v-list-item
        v-for="recent in recentSearches"
        :key="recent"
        @click="searchQuery = recent"
      >
        <v-list-item-title>{{ recent }}</v-list-item-title>
        <template #prepend>
          <v-icon>mdi-history</v-icon>
        </template>
      </v-list-item>
      <v-divider />
    </template>
  </v-autocomplete>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { getHPOAutocomplete } from '@/api';
import { addRecentSearch, getRecentSearches } from '@/utils/searchHistory';
import { debounce } from '@/utils/debounce';

const router = useRouter();
const searchQuery = ref('');
const selectedItem = ref(null);
const suggestions = ref([]);
const loading = ref(false);

const recentSearches = computed(() => getRecentSearches());

const fetchSuggestions = async (query) => {
  if (!query || query.length < 2) {
    suggestions.value = [];
    return;
  }

  loading.value = true;
  try {
    const { data } = await getHPOAutocomplete(query);
    suggestions.value = data.data;
  } catch (error) {
    window.logService.error('HPO autocomplete failed', { error: error.message });
  } finally {
    loading.value = false;
  }
};

const debouncedSearch = debounce(fetchSuggestions, 300);

const onSelect = (item) => {
  if (!item) return;

  addRecentSearch(item.label);
  router.push({
    name: 'SearchResults',
    query: { q: searchQuery.value, hpo_id: item.hpo_id }
  });
};
</script>
```

**Files to Create:**
- `frontend/src/components/GlobalSearch.vue` (~200 lines)
- `frontend/src/utils/searchHistory.js` (~50 lines)
- `frontend/src/utils/debounce.js` (~15 lines) - if not exists

---

#### Task 2: AppBar Integration (~1 hour)

**File to Modify:** `frontend/src/components/AppBar.vue`

**Changes:**
- Add GlobalSearch component to toolbar
- Make responsive (hide on mobile, show in mobile menu)
- Position between title and user menu

```vue
<template>
  <v-app-bar app color="primary" dark>
    <v-toolbar-title>HNF1B Database</v-toolbar-title>

    <!-- Desktop: Show search in toolbar -->
    <v-spacer class="d-none d-md-flex" />
    <div class="d-none d-md-flex" style="max-width: 400px; width: 100%;">
      <GlobalSearch />
    </div>

    <v-spacer />
    <!-- User menu, etc. -->
  </v-app-bar>

  <!-- Mobile: Search in navigation drawer -->
  <v-navigation-drawer v-model="drawer" app temporary>
    <GlobalSearch class="ma-4" />
    <!-- Other nav items -->
  </v-navigation-drawer>
</template>

<script setup>
import GlobalSearch from '@/components/GlobalSearch.vue';
</script>
```

---

#### Task 3: SearchResults Page Enhancement (~2 hours)

**File to Modify:** `frontend/src/views/SearchResults.vue`

**Changes:**
- Support new query parameters (`hpo_id`, `gene`, `sex`, `pmid`)
- Display search relevance scores
- Add filter chips for active filters
- Show "Searching in X phenopackets" message

```vue
<template>
  <v-container>
    <v-row>
      <v-col cols="12">
        <h2>Search Results</h2>
        <v-chip-group>
          <v-chip v-if="filters.q" closeable @click:close="removeFilter('q')">
            Text: {{ filters.q }}
          </v-chip>
          <v-chip v-if="filters.hpo_id" closeable @click:close="removeFilter('hpo_id')">
            HPO: {{ filters.hpo_id }}
          </v-chip>
          <!-- Other filter chips -->
        </v-chip-group>
      </v-col>
    </v-row>

    <v-row v-if="loading">
      <v-col cols="12">
        <v-progress-circular indeterminate />
        <span>Searching {{ totalPhenopackets }} phenopackets...</span>
      </v-col>
    </v-row>

    <v-row v-else>
      <v-col cols="12">
        <v-data-table
          :headers="headers"
          :items="results"
          :items-length="totalResults"
          @click:row="navigateToPhenopacket"
        >
          <template #item.search_rank="{ item }">
            <v-chip v-if="item.search_rank" color="green" small>
              {{ (item.search_rank * 100).toFixed(1) }}% match
            </v-chip>
          </template>
        </v-data-table>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { searchPhenopackets } from '@/api';

const route = useRoute();
const router = useRouter();

const filters = computed(() => route.query);
const results = ref([]);
const loading = ref(false);
const totalResults = ref(0);

const fetchResults = async () => {
  loading.value = true;
  try {
    const { data } = await searchPhenopackets(filters.value);
    results.value = data.data.map(pp => ({
      ...pp.attributes,
      search_rank: pp.meta?.search_rank
    }));
    totalResults.value = data.meta.total;
  } catch (error) {
    window.logService.error('Search failed', { error: error.message });
  } finally {
    loading.value = false;
  }
};

const removeFilter = (key) => {
  const newQuery = { ...route.query };
  delete newQuery[key];
  router.push({ query: newQuery });
};

onMounted(fetchResults);
</script>
```

---

### Phase 4: Testing & Documentation (1 hour) - NOT STARTED

**Tasks:**
- Backend unit tests for HPO autocomplete
- Backend integration tests for enhanced search endpoint
- Frontend component tests for GlobalSearch.vue
- Update `CLAUDE.md` with search feature documentation
- Manual testing checklist

**Test Files to Create:**
- `backend/tests/test_ontology_autocomplete.py`
- `backend/tests/test_search_endpoint.py`
- `frontend/tests/components/GlobalSearch.spec.js`

---

## API Changes Summary

### New Endpoints

1. **`GET /api/v2/ontology/hpo/autocomplete`**
   - Query: `q` (search term), `limit` (max results)
   - Returns: HPO term suggestions with phenopacket counts
   - Performance: ~10ms average (indexed query)

2. **Enhanced `GET /api/v2/phenopackets/search`**
   - New params: `q`, `hpo_id`, `sex`, `gene`, `pmid`, `rank_by_relevance`
   - Returns: Phenopackets with search relevance scores
   - Performance: ~50-100ms for full-text queries

### Frontend API Client Changes

**File:** `frontend/src/api/index.js`

```javascript
// Add new function
export const getHPOAutocomplete = (query, limit = 10) => {
  return apiClient.get('/ontology/hpo/autocomplete', {
    params: { q: query, limit }
  });
};

// Enhance existing searchPhenopackets function
export const searchPhenopackets = (params) => {
  return apiClient.get('/phenopackets/search', { params });
};
```

---

## Database Schema Changes

### New Table: `hpo_terms_lookup`

```sql
CREATE TABLE hpo_terms_lookup (
    hpo_id VARCHAR(20) PRIMARY KEY,
    label TEXT NOT NULL,
    phenopacket_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_hpo_lookup_label_trgm
ON hpo_terms_lookup USING GIN (label gin_trgm_ops);
```

**Population:** Extracted from existing phenopackets' `phenotypic_features`

**Maintenance:** Can be refreshed via migration or background job

### Modified Table: `phenopackets`

**New Column:**
```sql
ALTER TABLE phenopackets ADD COLUMN search_vector tsvector;
```

**New Index:**
```sql
CREATE INDEX idx_phenopackets_fulltext_search
ON phenopackets USING GIN (search_vector);
```

**New Trigger:**
```sql
CREATE TRIGGER phenopackets_search_vector_trigger
BEFORE INSERT OR UPDATE ON phenopackets
FOR EACH ROW
EXECUTE FUNCTION phenopackets_search_vector_update();
```

---

## Performance Estimates

Based on 864 phenopackets:

| Operation | Expected Performance |
|-----------|---------------------|
| HPO autocomplete | ~5-10ms |
| Full-text search (simple) | ~20-50ms |
| Full-text search + filters | ~50-100ms |
| Trigger overhead (insert/update) | ~1-2ms per record |

**Scalability:**
- GIN indexes scale well to millions of records
- Full-text search performance degrades logarithmically
- HPO lookup table size: ~2000 terms (stable)

---

## Known Issues & Limitations

1. **No fuzzy matching for gene symbols yet**
   - Exact match only in current implementation
   - Future: Add trigram index on gene symbols

2. **Search rank normalization**
   - PostgreSQL `ts_rank()` scores vary widely
   - May need normalization for better UX

3. **Recent searches stored in localStorage**
   - Not synced across devices
   - Future: Store in backend user preferences

4. **HPO lookup table refresh**
   - Manual refresh needed when new phenopackets added
   - Future: Automatic refresh via background job

---

## Next Steps (Priority Order)

1. **Implement HPO autocomplete endpoint** (~2 hours)
   - Create `backend/app/ontology/routers.py`
   - Add to main.py router registration
   - Test with curl/Postman

2. **Enhance search endpoint** (~2 hours)
   - Modify `backend/app/phenopackets/routers/search.py`
   - Add full-text search with ranking
   - Add structured filters

3. **Create GlobalSearch component** (~3 hours)
   - Create `frontend/src/components/GlobalSearch.vue`
   - Implement HPO autocomplete integration
   - Add recent searches feature

4. **Integrate with AppBar** (~1 hour)
   - Modify `frontend/src/components/AppBar.vue`
   - Add responsive design

5. **Update SearchResults page** (~2 hours)
   - Add filter chips
   - Display search ranks
   - Support new query parameters

6. **Testing & documentation** (~1 hour)
   - Write backend tests
   - Write frontend component tests
   - Update CLAUDE.md

---

## Files to Modify/Create

### Backend Files

**To Create:**
- [ ] `backend/app/ontology/__init__.py`
- [ ] `backend/app/ontology/routers.py` (~150 lines)
- [ ] `backend/tests/test_ontology_autocomplete.py` (~100 lines)
- [ ] `backend/tests/test_search_endpoint_enhanced.py` (~150 lines)

**To Modify:**
- [ ] `backend/app/main.py` (add ontology router)
- [ ] `backend/app/phenopackets/routers/search.py` (enhance search endpoint)

### Frontend Files

**To Create:**
- [ ] `frontend/src/components/GlobalSearch.vue` (~200 lines)
- [ ] `frontend/src/utils/searchHistory.js` (~50 lines)
- [ ] `frontend/tests/components/GlobalSearch.spec.js` (~100 lines)

**To Modify:**
- [ ] `frontend/src/api/index.js` (add getHPOAutocomplete function)
- [ ] `frontend/src/components/AppBar.vue` (integrate GlobalSearch)
- [ ] `frontend/src/views/SearchResults.vue` (add filters, search ranks)

### Documentation Files

**To Modify:**
- [ ] `docs/CLAUDE.md` (add search feature documentation)
- [ ] `docs/issues/issue-39-progress.md` (update as work progresses)

---

## Commit Strategy

**Commit 1: Database Migration** (READY TO COMMIT)
```bash
git add backend/alembic/versions/8baf0de6a441_add_fulltext_search_to_phenopackets.py
git commit -m "feat(backend): add full-text search infrastructure for phenopackets (#39)

- Add search_vector tsvector column with trigger-based updates
- Create hpo_terms_lookup table for fast autocomplete
- Add GIN indexes for full-text and trigram search
- Populate from 864 existing phenopackets

Phase 1 of Issue #39: Global Phenopacket Search"
```

**Commit 2: Backend API Endpoints** (after Phase 2)
```bash
git commit -m "feat(api): add HPO autocomplete and enhanced search endpoints (#39)

- Add /api/v2/ontology/hpo/autocomplete endpoint
- Enhance /api/v2/phenopackets/search with full-text ranking
- Support filters: hpo_id, sex, gene, pmid

Phase 2 of Issue #39: Global Phenopacket Search"
```

**Commit 3: Frontend Components** (after Phase 3)
```bash
git commit -m "feat(frontend): add GlobalSearch component with HPO autocomplete (#39)

- Create GlobalSearch.vue with real-time autocomplete
- Integrate with AppBar (responsive design)
- Add recent searches feature (localStorage)
- Enhance SearchResults page with filters and ranks

Phase 3 of Issue #39: Global Phenopacket Search"
```

**Commit 4: Tests & Documentation** (after Phase 4)
```bash
git commit -m "test(search): add tests and documentation for global search (#39)

- Add backend tests for autocomplete and search endpoints
- Add frontend component tests
- Update CLAUDE.md with search documentation

Phase 4 of Issue #39: Global Phenopacket Search (Complete)"
```

---

## Questions for Next Session

1. Should we add variant-level search (e.g., search by HGVS notation)?
2. Should recent searches be synced to backend (user preferences)?
3. Do we want export functionality for search results?
4. Should we add saved search queries feature?

---

## References

- **Original Issue:** `docs/issues/issue-37-41-batch.md` (Section: Issue #39)
- **Migration File:** `backend/alembic/versions/8baf0de6a441_add_fulltext_search_to_phenopackets.py`
- **PostgreSQL Full-Text Search:** https://www.postgresql.org/docs/current/textsearch.html
- **pg_trgm Extension:** https://www.postgresql.org/docs/current/pgtrgm.html
- **JSON:API v1.1 Spec:** https://jsonapi.org/format/1.1/

---

**End of Progress Report**
