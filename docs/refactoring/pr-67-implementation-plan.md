# PR #67 Refactoring Implementation Plan

**Status:** In Progress
**Created:** 2025-11-06
**PR:** feat/variant-page → main
**Review:** docs/reviews/feat-variant-page/detailed-review.md

---

## Executive Summary

This document provides a detailed, session-resumable implementation plan for refactoring PR #67 to address Priority 1 blocking issues identified in code review.

**Total Estimated Time:** 25-33 hours
**Completed:** 2 hours (utility modules created)
**Remaining:** 23-31 hours

---

## ✅ Phase 1: DRY Violations - Utility Modules (COMPLETED)

**Time Spent:** 2 hours
**Status:** ✅ DONE

### Completed Tasks
- [x] Create `frontend/src/utils/hgvs.js` (extractCNotation, extractPNotation, extractTranscriptId, extractProteinId)
- [x] Create `frontend/src/utils/colors.js` (getPathogenicityColor, getVariantTypeColor, getClassificationColor)
- [x] Create `frontend/src/utils/variants.js` (getVariantType, isCNV, isIndel, isSpliceVariant, getVariantSize)
- [x] Commit utility modules

**Commit Message:**
```
refactor(frontend): create utility modules to eliminate DRY violations
```

---

## 🔄 Phase 2: DRY Violations - Component Refactoring (IN PROGRESS)

**Estimated Time:** 6-8 hours
**Status:** NEXT

Refactor 4 components to use the new utility modules instead of duplicated code.

### 2.1 Update PageVariant.vue (~1.5 hours)

**File:** `frontend/src/views/PageVariant.vue` (971 lines)

**Current Duplicated Methods (to remove):**
- Lines 618-627: `extractCNotation()`
- Lines 629-636: `extractPNotation()`
- Lines 638-656: `getPathogenicityColor()`
- Lines 658-674: `getVariantType()` (partial, CNV detection only)

**Steps:**
1. Add imports at top of script section:
   ```javascript
   import { extractCNotation, extractPNotation } from '@/utils/hgvs';
   import { getPathogenicityColor } from '@/utils/colors';
   import { getVariantType, isCNV, getVariantSize } from '@/utils/variants';
   ```

2. Remove methods: `extractCNotation`, `extractPNotation`, `getPathogenicityColor`, `getVariantType`

3. Update `methods` object to reference imported functions:
   ```javascript
   methods: {
     extractCNotation,
     extractPNotation,
     getPathogenicityColor,
     getVariantType,
     isCNV,
     getVariantSize,
     // ... other methods
   }
   ```

4. Verify no other methods call the removed functions with `this.` prefix
5. Test the variant detail page loads correctly
6. Run linting: `npm run lint`

**Expected Line Reduction:** ~60 lines

**Commit Message:**
```
refactor(frontend): update PageVariant to use utility functions

- Replace duplicated extractCNotation/extractPNotation with utils/hgvs
- Replace duplicated getPathogenicityColor with utils/colors
- Replace duplicated getVariantType with utils/variants
- Reduces file from 971 to ~910 lines
- Part of DRY violations fix for PR #67
```

---

### 2.2 Update Variants.vue (~1.5 hours)

**File:** `frontend/src/views/Variants.vue` (989 lines)

**Current Duplicated Methods (to remove):**
- Lines 937-949: `extractCNotation()`
- Lines 951-963: `extractPNotation()`
- Lines 738-756: `getClassificationColor()` (similar to getPathogenicityColor)
- Lines 917-935: `getPathogenicityColor()`
- Lines 758-802: `getVariantType()`
- Lines 904-915: `getVariantTypeColor()`

**Steps:**
1. Add imports at top of script section:
   ```javascript
   import { extractCNotation, extractPNotation } from '@/utils/hgvs';
   import { getPathogenicityColor, getVariantTypeColor, getClassificationColor } from '@/utils/colors';
   import { getVariantType } from '@/utils/variants';
   ```

2. Remove methods: `extractCNotation`, `extractPNotation`, `getClassificationColor`, `getPathogenicityColor`, `getVariantType`, `getVariantTypeColor`

3. Update `methods` object to reference imported functions:
   ```javascript
   methods: {
     extractCNotation,
     extractPNotation,
     getClassificationColor,
     getPathogenicityColor,
     getVariantType,
     getVariantTypeColor,
     // ... other methods
   }
   ```

4. Test the variants list page:
   - Loads correctly
   - Search works
   - Filters work
   - Colors display correctly
   - Sorting works

5. Run linting: `npm run lint`

**Expected Line Reduction:** ~100 lines

**Commit Message:**
```
refactor(frontend): update Variants view to use utility functions

- Replace duplicated HGVS extraction with utils/hgvs
- Replace duplicated color mapping with utils/colors
- Replace duplicated variant type detection with utils/variants
- Reduces file from 989 to ~890 lines
- Part of DRY violations fix for PR #67
```

---

### 2.3 Update HNF1BGeneVisualization.vue (~1.5 hours)

**File:** `frontend/src/components/gene/HNF1BGeneVisualization.vue` (1,510 lines)

**Current Duplicated Methods (to remove):**
- Lines 1289-1298: `extractCNotation()`
- Possibly other HGVS/color functions (needs verification)

**Steps:**
1. Search file for all duplicated functions:
   ```bash
   grep -n "extractCNotation\|extractPNotation\|getPathogenicityColor\|getVariantType" frontend/src/components/gene/HNF1BGeneVisualization.vue
   ```

2. Add imports:
   ```javascript
   import { extractCNotation, extractPNotation } from '@/utils/hgvs';
   import { getPathogenicityColor, getVariantTypeColor } from '@/utils/colors';
   import { getVariantType, isCNV } from '@/utils/variants';
   ```

3. Remove duplicated methods

4. Update `methods` object to reference imported functions

5. Test gene visualization:
   - Renders correctly on homepage
   - Renders correctly on variant detail page
   - Variants clickable
   - Tooltips work
   - Gene view vs CNV view toggle works

6. Run linting: `npm run lint`

**Expected Line Reduction:** ~20-30 lines

**Commit Message:**
```
refactor(frontend): update HNF1BGeneVisualization to use utility functions

- Replace duplicated extractCNotation with utils/hgvs
- Add imports for color and variant utilities
- Ensures consistent variant detection across components
- Part of DRY violations fix for PR #67
```

---

### 2.4 Update HNF1BProteinVisualization.vue (~1.5 hours)

**File:** `frontend/src/components/gene/HNF1BProteinVisualization.vue` (777 lines)

**Current Duplicated Methods (to remove):**
- Lines 624-633: `extractCNotation()`
- Lines 635-644: `extractPNotation()`
- Lines 646-664: `getPathogenicityColor()`

**Steps:**
1. Add imports:
   ```javascript
   import { extractCNotation, extractPNotation } from '@/utils/hgvs';
   import { getPathogenicityColor } from '@/utils/colors';
   import { getVariantType } from '@/utils/variants';
   ```

2. Remove methods: `extractCNotation`, `extractPNotation`, `getPathogenicityColor`

3. Update `methods` object to reference imported functions

4. Test protein visualization:
   - Renders correctly on homepage
   - Renders correctly on variant detail page
   - Variants positioned correctly on domains
   - Tooltips work
   - Colors correct

5. Run linting: `npm run lint`

**Expected Line Reduction:** ~40 lines

**Commit Message:**
```
refactor(frontend): update HNF1BProteinVisualization to use utility functions

- Replace duplicated HGVS extraction with utils/hgvs
- Replace duplicated color mapping with utils/colors
- Reduces file from 777 to ~737 lines
- Part of DRY violations fix for PR #67
```

---

### Phase 2 Summary

**Total Time:** 6-8 hours
**Total Lines Saved:** ~220 lines
**Files Updated:** 4 Vue components

**Testing Checklist After Phase 2:**
- [ ] Homepage loads and displays stats correctly
- [ ] Variants list page works (search, filter, sort, pagination)
- [ ] Variant detail page loads correctly
- [ ] Gene visualization renders correctly
- [ ] Protein visualization renders correctly
- [ ] All colors display consistently
- [ ] All tooltips work
- [ ] No console errors
- [ ] `npm run lint` passes

---

## 🔄 Phase 3: Backend DRY Violations (~4-6 hours)

### 3.1 Create query_builders.py (~2 hours)

**File:** `backend/app/phenopackets/query_builders.py` (NEW)

**Purpose:** Extract reusable query building logic from endpoints.py

**Functions to Create:**

```python
"""
Query builder utilities for phenopacket queries.
Eliminates duplicate SQL query patterns across endpoints.
"""

from typing import Dict, List, Optional
from sqlalchemy import func
from app.models.phenopacket import Phenopacket
from app.phenopackets.schemas import PhenopacketResponse


def add_classification_filter(
    where_clauses: List[str],
    params: Dict,
    classification: Optional[str]
) -> None:
    """
    Add variant classification filter to WHERE clauses.

    Used in: get_variants, search_phenopackets, aggregate_all_variants

    Args:
        where_clauses: List of SQL WHERE conditions
        params: Query parameters dict
        classification: ACMG classification (e.g., 'PATHOGENIC')
    """
    if classification:
        where_clauses.append("gi->>'interpretationStatus' = :classification")
        params["classification"] = classification


def add_has_variants_filter(query, has_variants: Optional[bool]):
    """
    Add filter for phenopackets with/without variants.

    Used in: list_phenopackets, search_phenopackets

    Args:
        query: SQLAlchemy query object
        has_variants: True (has variants), False (no variants), None (all)

    Returns:
        Modified query object
    """
    if has_variants is None:
        return query

    if has_variants:
        return query.where(
            func.jsonb_array_length(Phenopacket.phenopacket["interpretations"]) > 0
        )

    return query.where(
        func.coalesce(
            func.jsonb_array_length(Phenopacket.phenopacket["interpretations"]), 0
        ) == 0
    )


def add_sex_filter(query, sex: Optional[str]):
    """
    Add sex filter to query.

    Used in: list_phenopackets, search_phenopackets, aggregate_*

    Args:
        query: SQLAlchemy query object
        sex: 'MALE', 'FEMALE', 'OTHER_SEX', 'UNKNOWN_SEX'

    Returns:
        Modified query object
    """
    if sex:
        return query.where(Phenopacket.phenopacket["subject"]["sex"].astext == sex)
    return query


def build_phenopacket_response(pp: Phenopacket) -> PhenopacketResponse:
    """
    Transform database model to response model.

    Used in: All CRUD endpoints

    Args:
        pp: Phenopacket database model instance

    Returns:
        PhenopacketResponse Pydantic model
    """
    return PhenopacketResponse(
        id=str(pp.id),
        phenopacket_id=pp.phenopacket_id,
        version=pp.version,
        phenopacket=pp.phenopacket,
        created_at=pp.created_at,
        updated_at=pp.updated_at,
        schema_version=pp.schema_version,
    )


def build_variant_query_filters(
    variant_type: Optional[str] = None,
    classification: Optional[str] = None,
    consequence: Optional[str] = None,
    query: Optional[str] = None
) -> tuple[List[str], Dict]:
    """
    Build WHERE clauses and params for variant filtering.

    Used in: get_variants, aggregate_all_variants

    Args:
        variant_type: Variant type filter
        classification: ACMG classification filter
        consequence: Molecular consequence filter
        query: Text search query

    Returns:
        Tuple of (where_clauses, params)
    """
    where_clauses = []
    params = {}

    if variant_type:
        where_clauses.append("v->>'structuralType' = :variant_type")
        params["variant_type"] = variant_type

    if classification:
        where_clauses.append("gi->>'interpretationStatus' = :classification")
        params["classification"] = classification

    if consequence:
        where_clauses.append(
            "v->'molecularConsequence'->0->'term'->>'label' = :consequence"
        )
        params["consequence"] = consequence

    if query:
        # Add HGVS search conditions
        search_conditions = [
            "v->>'transcript' ILIKE :query",
            "v->>'protein' ILIKE :query",
            "v->>'hg38' ILIKE :query",
            "v->>'label' ILIKE :query"
        ]
        where_clauses.append(f"({' OR '.join(search_conditions)})")
        params["query"] = f"%{query}%"

    return where_clauses, params
```

**Steps:**
1. Create new file `backend/app/phenopackets/query_builders.py`
2. Copy function implementations from above
3. Add proper imports
4. Add comprehensive docstrings
5. Run type checking: `cd backend && make typecheck`
6. Run linting: `cd backend && make lint`

**Commit Message:**
```
refactor(backend): create query builder utilities to eliminate DRY violations

- Create app/phenopackets/query_builders.py with reusable query functions
- add_classification_filter() - shared across 5+ endpoints
- add_has_variants_filter() - shared across 3 endpoints
- add_sex_filter() - shared across 4 endpoints
- build_phenopacket_response() - shared across all CRUD endpoints
- build_variant_query_filters() - consolidates variant filtering logic
- Eliminates 100+ lines of duplicated SQL query code
- Part of DRY violations fix for PR #67
```

---

### 3.2 Refactor endpoints.py to use query_builders (~2-4 hours)

**File:** `backend/app/phenopackets/endpoints.py` (1,960 lines)

**Goal:** Replace duplicated query logic with calls to query_builders functions

**Endpoints to Update:**

1. **`list_phenopackets()`** - Use `add_has_variants_filter`, `add_sex_filter`, `build_phenopacket_response`
2. **`get_phenopacket()`** - Use `build_phenopacket_response`
3. **`search_phenopackets()`** - Use `add_classification_filter`, `add_has_variants_filter`, `add_sex_filter`
4. **`aggregate_all_variants()`** - Use `build_variant_query_filters`
5. **`get_phenopackets_by_variant()`** - Use `add_classification_filter`

**Steps:**
1. Add import at top:
   ```python
   from app.phenopackets.query_builders import (
       add_classification_filter,
       add_has_variants_filter,
       add_sex_filter,
       build_phenopacket_response,
       build_variant_query_filters,
   )
   ```

2. Update each endpoint one at a time:
   - Replace inline query logic with function calls
   - Test endpoint works correctly
   - Move to next endpoint

3. Run tests after each change:
   ```bash
   cd backend
   make test  # Run all tests
   pytest tests/test_variant_search.py -v  # Run specific test file
   ```

4. Run full test suite:
   ```bash
   cd backend
   make check  # Runs lint, typecheck, and tests
   ```

**Expected Line Reduction:** ~100-150 lines

**Commit Message:**
```
refactor(backend): update endpoints to use query builder utilities

- Replace duplicated query logic in 5+ endpoints
- Use add_classification_filter() in search and variant endpoints
- Use add_has_variants_filter() in list and search endpoints
- Use build_phenopacket_response() in all CRUD endpoints
- Use build_variant_query_filters() in variant aggregation
- Reduces endpoints.py from 1,960 to ~1,810 lines
- All tests pass
- Part of DRY violations fix for PR #67
```

---

### Phase 3 Summary

**Total Time:** 4-6 hours
**Total Lines Saved:** ~100-150 lines
**Files Created:** 1 (query_builders.py)
**Files Updated:** 1 (endpoints.py)

**Testing Checklist After Phase 3:**
- [ ] `cd backend && make test` passes all tests
- [ ] `cd backend && make lint` passes
- [ ] `cd backend && make typecheck` passes
- [ ] API endpoints respond correctly (test with curl or frontend)
- [ ] Variant search works
- [ ] Aggregation endpoints work
- [ ] No database errors in logs

---

## 🔄 Phase 4: File Size Violations - Backend Split (8-10 hours)

**Current State:** `endpoints.py` is 1,960 lines with 27 functions
**Goal:** Split into 5 focused routers (~300-400 lines each)

### 4.1 Create Router Structure (~1 hour)

**Steps:**
1. Create directory:
   ```bash
   mkdir -p backend/app/phenopackets/routers
   ```

2. Create `__init__.py`:
   ```python
   # backend/app/phenopackets/routers/__init__.py
   """
   Phenopackets API routers.
   Split from monolithic endpoints.py for maintainability.
   """

   from fastapi import APIRouter
   from .crud import router as crud_router
   from .aggregations import router as aggregations_router
   from .search import router as search_router
   from .variants import router as variants_router

   # Combine all routers
   router = APIRouter()
   router.include_router(crud_router)
   router.include_router(aggregations_router)
   router.include_router(search_router)
   router.include_router(variants_router)

   __all__ = ["router"]
   ```

---

### 4.2 Create crud.py Router (~2 hours)

**File:** `backend/app/phenopackets/routers/crud.py` (NEW, ~200 lines)

**Purpose:** Basic CRUD operations

**Endpoints to Move:**
- `GET /api/v2/phenopackets/` - list_phenopackets
- `GET /api/v2/phenopackets/{id}` - get_phenopacket
- `POST /api/v2/phenopackets/` - create_phenopacket (if exists)
- `PUT /api/v2/phenopackets/{id}` - update_phenopacket (if exists)
- `DELETE /api/v2/phenopackets/{id}` - delete_phenopacket (if exists)
- `GET /api/v2/phenopackets/batch` - get_phenopackets_batch

**Template:**
```python
"""
CRUD operations for phenopackets.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.phenopacket import Phenopacket
from app.phenopackets.schemas import PhenopacketResponse
from app.phenopackets.query_builders import (
    add_has_variants_filter,
    add_sex_filter,
    build_phenopacket_response,
)

router = APIRouter(prefix="/api/v2/phenopackets", tags=["phenopackets-crud"])


@router.get("/", response_model=List[PhenopacketResponse])
async def list_phenopackets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sex: Optional[str] = None,
    has_variants: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    """List phenopackets with optional filters."""
    # ... copy implementation from endpoints.py
    pass


@router.get("/{id}", response_model=PhenopacketResponse)
async def get_phenopacket(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single phenopacket by ID."""
    # ... copy implementation from endpoints.py
    pass

# ... other CRUD endpoints
```

**Steps:**
1. Create file with router definition
2. Copy endpoint implementations from endpoints.py
3. Update imports to use query_builders
4. Test endpoints:
   ```bash
   curl http://localhost:8000/api/v2/phenopackets/?skip=0&limit=10
   curl http://localhost:8000/api/v2/phenopackets/{some-id}
   ```
5. Run tests: `pytest tests/ -k phenopacket -v`

**Commit Message:**
```
refactor(backend): extract CRUD operations to dedicated router

- Create app/phenopackets/routers/crud.py
- Move list, get, create, update, delete endpoints
- Reduces endpoints.py from ~1,810 to ~1,610 lines
- Each router now ~200 lines (within 500-line guideline)
- All tests pass
- Part of file size violations fix for PR #67
```

---

### 4.3 Create aggregations.py Router (~2 hours)

**File:** `backend/app/phenopackets/routers/aggregations.py` (NEW, ~400 lines)

**Purpose:** All statistical aggregation endpoints

**Endpoints to Move:**
- `GET /api/v2/phenopackets/aggregate/summary`
- `GET /api/v2/phenopackets/aggregate/sex-distribution`
- `GET /api/v2/phenopackets/aggregate/by-feature`
- `GET /api/v2/phenopackets/aggregate/by-disease`
- `GET /api/v2/phenopackets/aggregate/variant-pathogenicity`
- `GET /api/v2/phenopackets/aggregate/kidney-stages`
- `GET /api/v2/phenopackets/aggregate/all-variants`
- `GET /api/v2/phenopackets/aggregate/variant-types`
- Any other aggregate/* endpoints

**Template:**
```python
"""
Aggregation and statistics endpoints for phenopackets.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, text

from app.database import get_db
from app.phenopackets.query_builders import add_sex_filter, build_variant_query_filters

router = APIRouter(
    prefix="/api/v2/phenopackets/aggregate",
    tags=["phenopackets-aggregations"]
)


@router.get("/summary")
async def aggregate_summary(db: AsyncSession = Depends(get_db)):
    """Get overall summary statistics."""
    # ... copy implementation
    pass


@router.get("/all-variants")
async def aggregate_all_variants(
    variant_type: Optional[str] = None,
    classification: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get all unique variants with counts."""
    # ... copy implementation
    pass

# ... other aggregation endpoints
```

**Steps:**
1. Create file with router definition
2. Copy all aggregate/* endpoints
3. Test each endpoint works
4. Run tests

**Commit Message:**
```
refactor(backend): extract aggregation endpoints to dedicated router

- Create app/phenopackets/routers/aggregations.py
- Move all aggregate/* endpoints (8+ endpoints)
- Reduces endpoints.py from ~1,610 to ~1,210 lines
- Aggregation router ~400 lines (within guideline)
- All aggregation tests pass
- Part of file size violations fix for PR #67
```

---

### 4.4 Create search.py Router (~1.5 hours)

**File:** `backend/app/phenopackets/routers/search.py` (NEW, ~250 lines)

**Purpose:** Search and advanced filtering

**Endpoints to Move:**
- `POST /api/v2/phenopackets/search`
- `GET /api/v2/phenopackets/by-variant/{variant_id}`
- `GET /api/v2/phenopackets/by-feature/{feature_id}`
- Any other search-related endpoints

**Template:**
```python
"""
Search and filtering endpoints for phenopackets.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.phenopackets.schemas import SearchRequest, PhenopacketResponse
from app.phenopackets.query_builders import (
    add_classification_filter,
    add_has_variants_filter,
    add_sex_filter,
)

router = APIRouter(prefix="/api/v2/phenopackets", tags=["phenopackets-search"])


@router.post("/search", response_model=List[PhenopacketResponse])
async def search_phenopackets(
    request: SearchRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Advanced phenopacket search with multiple filters."""
    # ... copy implementation
    pass


@router.get("/by-variant/{variant_id}", response_model=List[PhenopacketResponse])
async def get_phenopackets_by_variant(
    variant_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all phenopackets containing a specific variant."""
    # ... copy implementation
    pass

# ... other search endpoints
```

**Commit Message:**
```
refactor(backend): extract search endpoints to dedicated router

- Create app/phenopackets/routers/search.py
- Move search, by-variant, by-feature endpoints
- Reduces endpoints.py from ~1,210 to ~960 lines
- Search router ~250 lines (within guideline)
- All search tests pass
- Part of file size violations fix for PR #67
```

---

### 4.5 Create variants.py Router (~1.5 hours)

**File:** `backend/app/phenopackets/routers/variants.py` (NEW, ~200 lines)

**Purpose:** Variant-specific operations (if exists)

**Endpoints to Move:**
- Any variant-specific CRUD operations
- Variant validation endpoints
- Variant batch operations

**Note:** If there are no variant-specific endpoints beyond what's in aggregations/search, this router may not be needed.

---

### 4.6 Update Main App to Use New Routers (~1 hour)

**File:** `backend/app/main.py`

**Steps:**
1. Update import:
   ```python
   # OLD
   from app.phenopackets import endpoints as phenopackets_endpoints

   # NEW
   from app.phenopackets.routers import router as phenopackets_router
   ```

2. Update router registration:
   ```python
   # OLD
   app.include_router(phenopackets_endpoints.router)

   # NEW
   app.include_router(phenopackets_router)
   ```

3. Delete or move old `endpoints.py`:
   ```bash
   # Option 1: Delete (recommended after verifying all endpoints moved)
   git rm backend/app/phenopackets/endpoints.py

   # Option 2: Rename as backup
   mv backend/app/phenopackets/endpoints.py backend/app/phenopackets/endpoints_old.py
   ```

4. Test the entire API works:
   ```bash
   cd backend
   make dev  # Start server
   # In another terminal:
   curl http://localhost:8000/api/v2/phenopackets/
   curl http://localhost:8000/api/v2/phenopackets/aggregate/summary
   # Test other endpoints
   ```

5. Run full test suite:
   ```bash
   cd backend
   make test
   make check
   ```

**Commit Message:**
```
refactor(backend): complete router split from monolithic endpoints

- Update main.py to use new router structure
- Remove old endpoints.py (1,960 lines)
- New structure: 5 focused routers (~200-400 lines each)
  - routers/crud.py (~200 lines)
  - routers/aggregations.py (~400 lines)
  - routers/search.py (~250 lines)
  - routers/variants.py (~200 lines)
- All endpoints functional
- All tests pass (make check)
- Completes file size violations fix for PR #67
```

---

### Phase 4 Summary

**Total Time:** 8-10 hours
**Result:** 1,960-line file split into 5 manageable routers
**Files Created:** 5 (routers/__init__.py, crud.py, aggregations.py, search.py, variants.py)
**Files Deleted:** 1 (endpoints.py)

**Testing Checklist After Phase 4:**
- [ ] All API endpoints respond correctly
- [ ] `/docs` (Swagger UI) shows all endpoints
- [ ] CRUD operations work (list, get, create, update, delete)
- [ ] Aggregation endpoints work
- [ ] Search endpoints work
- [ ] `make test` passes all tests
- [ ] `make check` passes (lint + typecheck + test)
- [ ] No import errors
- [ ] No database errors

---

## 🔄 Phase 5: File Size Violations - Frontend Component Extraction (6-8 hours)

### 5.1 Extract Variants.vue Components (~2 hours)

**Current:** 989 lines
**Goal:** ~400-500 lines with 3 extracted components

**Components to Extract:**

#### VariantSearchBar.vue (NEW, ~100 lines)
**Location:** `frontend/src/components/variants/VariantSearchBar.vue`

**Content:** Search text field with help menu
- Search input with debouncing
- Help menu with search examples
- Clear functionality

**Template from Variants.vue (lines ~14-65):**
```vue
<template>
  <v-text-field
    v-model="searchQuery"
    label="Search"
    placeholder="Enter HGVS notation, gene symbol, or variant ID"
    prepend-inner-icon="mdi-magnify"
    clearable
    :loading="loading"
    hide-details
    @input="handleInput"
    @click:clear="handleClear"
  >
    <template #append-inner>
      <v-menu>
        <!-- Help menu content -->
      </v-menu>
    </template>
  </v-text-field>
</template>

<script>
export default {
  name: 'VariantSearchBar',
  props: {
    loading: {
      type: Boolean,
      default: false
    },
    modelValue: {
      type: String,
      default: ''
    }
  },
  emits: ['update:modelValue', 'search', 'clear'],
  data() {
    return {
      searchQuery: this.modelValue
    };
  },
  watch: {
    modelValue(newVal) {
      this.searchQuery = newVal;
    }
  },
  methods: {
    handleInput() {
      this.$emit('update:modelValue', this.searchQuery);
      this.$emit('search', this.searchQuery);
    },
    handleClear() {
      this.searchQuery = '';
      this.$emit('update:modelValue', '');
      this.$emit('clear');
    }
  }
};
</script>
```

#### VariantFilters.vue (NEW, ~150 lines)
**Location:** `frontend/src/components/variants/VariantFilters.vue`

**Content:** Filter dropdowns and active filter chips
- Type filter dropdown
- Classification filter dropdown
- Consequence filter dropdown
- Active filters chip group
- Clear all button

**Props:**
- `filterType`, `filterClassification`, `filterConsequence`
- `variantTypes`, `classifications`, `consequences` (arrays)
- `loading`

**Emits:**
- `update:filterType`, `update:filterClassification`, `update:filterConsequence`
- `clearType`, `clearClassification`, `clearConsequence`, `clearAll`

#### VariantTable.vue (NEW, ~250 lines)
**Location:** `frontend/src/components/variants/VariantTable.vue`

**Content:** Data table with custom templates
- Table headers configuration
- Custom column templates (simple_id, transcript, protein, etc.)
- Pagination controls
- Row click handling
- Custom sorting headers

**Props:**
- `variants` (Array)
- `loading` (Boolean)
- `totalItems`, `totalPages` (Number)
- `options` (pagination/sort object)

**Emits:**
- `update:options`
- `row-click`

**Methods to Include:**
- `extractCNotation`, `extractPNotation` (from utils/hgvs)
- `getPathogenicityColor`, `getVariantTypeColor` (from utils/colors)
- `getVariantType` (from utils/variants)

---

#### Updated Variants.vue (~400-500 lines)

**After extraction:**
```vue
<template>
  <v-container fluid>
    <v-card class="mb-4">
      <v-card-title>Search Variants</v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" md="4">
            <VariantSearchBar
              v-model="searchQuery"
              :loading="loading"
              @search="debouncedSearch"
              @clear="clearSearch"
            />
          </v-col>
          <v-col cols="12" md="8">
            <VariantFilters
              v-model:filterType="filterType"
              v-model:filterClassification="filterClassification"
              v-model:filterConsequence="filterConsequence"
              :variant-types="variantTypes"
              :classifications="classifications"
              :consequences="consequences"
              :loading="loading"
              @clearType="clearTypeFilter"
              @clearClassification="clearClassificationFilter"
              @clearConsequence="clearConsequenceFilter"
              @clearAll="clearAllFilters"
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <VariantTable
      :variants="variants"
      :loading="loading"
      :total-items="totalItems"
      :total-pages="totalPages"
      :options="options"
      @update:options="options = $event"
      @row-click="handleRowClick"
    />
  </v-container>
</template>

<script>
import { debounce } from 'just-debounce-it';
import VariantSearchBar from '@/components/variants/VariantSearchBar.vue';
import VariantFilters from '@/components/variants/VariantFilters.vue';
import VariantTable from '@/components/variants/VariantTable.vue';
import { getVariants } from '@/api';

export default {
  name: 'Variants',
  components: {
    VariantSearchBar,
    VariantFilters,
    VariantTable
  },
  data() {
    return {
      searchQuery: '',
      filterType: null,
      filterClassification: null,
      filterConsequence: null,
      variants: [],
      loading: false,
      totalItems: 0,
      totalPages: 0,
      variantTypes: ['SNV', 'insertion', 'indel', 'deletion', 'duplication'],
      classifications: ['PATHOGENIC', 'LIKELY_PATHOGENIC', 'UNCERTAIN_SIGNIFICANCE', 'LIKELY_BENIGN', 'BENIGN'],
      consequences: ['Frameshift', 'Nonsense', 'Missense', 'Splice Donor', 'Splice Acceptor'],
      options: {
        page: 1,
        itemsPerPage: 10,
        sortBy: [{ key: 'simple_id', order: 'desc' }]
      }
    };
  },
  created() {
    this.debouncedSearch = debounce(this.searchVariants, 300);
  },
  methods: {
    async fetchVariants() {
      // ... API call logic
    },
    searchVariants() {
      this.options.page = 1;
      this.fetchVariants();
    },
    clearSearch() {
      this.searchQuery = '';
      this.searchVariants();
    },
    // ... other methods
  }
};
</script>
```

**Steps:**
1. Create `frontend/src/components/variants/` directory
2. Create VariantSearchBar.vue
3. Create VariantFilters.vue
4. Create VariantTable.vue
5. Update Variants.vue to use new components
6. Test variants page works:
   - Search functionality
   - Filters work
   - Table displays correctly
   - Pagination works
   - Row clicks work
7. Run linting: `npm run lint`

**Commit Message:**
```
refactor(frontend): extract sub-components from Variants view

- Create components/variants/VariantSearchBar.vue (~100 lines)
- Create components/variants/VariantFilters.vue (~150 lines)
- Create components/variants/VariantTable.vue (~250 lines)
- Update Variants.vue to use extracted components
- Reduces Variants.vue from 989 to ~450 lines
- Improves reusability and maintainability
- All functionality preserved
- Part of file size violations fix for PR #67
```

---

### 5.2 Extract PageVariant.vue Components (~2 hours)

**Current:** 971 lines
**Goal:** ~500-600 lines with 2-3 extracted components

**Components to Extract:**

#### VariantDetailCard.vue (NEW, ~200 lines)
**Location:** `frontend/src/components/variants/VariantDetailCard.vue`

**Content:** Variant information card
- Variant header with ID chip
- Type, size, transcript, protein display
- Classification badge
- Copy to clipboard functionality

**Props:**
- `variant` (Object)

**Methods:**
- `extractCNotation`, `extractPNotation` (from utils)
- `getVariantType`, `getVariantSize` (from utils)
- `getPathogenicityColor` (from utils)

#### VariantMetadata.vue (NEW, ~150 lines)
**Location:** `frontend/src/components/variants/VariantMetadata.vue`

**Content:** Metadata section
- Individual count
- Publications list
- Date information
- External links

**Props:**
- `individualCount` (Number)
- `publications` (Array)
- `createdAt`, `updatedAt` (String)

#### Updated PageVariant.vue (~600 lines)

**After extraction:**
```vue
<template>
  <v-container fluid>
    <v-row justify="center">
      <v-col cols="12">
        <VariantDetailCard :variant="variant" />

        <v-card class="mt-4">
          <v-tabs v-model="visualizationTab">
            <v-tab value="gene">Gene View</v-tab>
            <v-tab value="protein">Protein View</v-tab>
          </v-tabs>
          <!-- Visualizations -->
        </v-card>

        <VariantMetadata
          :individual-count="phenopacketsWithVariant.length"
          :publications="publications"
          :created-at="variant.created_at"
        />
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
import VariantDetailCard from '@/components/variants/VariantDetailCard.vue';
import VariantMetadata from '@/components/variants/VariantMetadata.vue';
// ... other imports

export default {
  name: 'PageVariant',
  components: {
    VariantDetailCard,
    VariantMetadata,
    // ... visualization components
  },
  // ... rest of component
};
</script>
```

**Commit Message:**
```
refactor(frontend): extract sub-components from PageVariant view

- Create components/variants/VariantDetailCard.vue (~200 lines)
- Create components/variants/VariantMetadata.vue (~150 lines)
- Update PageVariant.vue to use extracted components
- Reduces PageVariant.vue from 971 to ~600 lines
- Improves component organization
- All functionality preserved
- Part of file size violations fix for PR #67
```

---

### 5.3 Split HNF1BGeneVisualization.vue (~2-3 hours)

**Current:** 1,510 lines
**Goal:** ~500-600 lines with 3-4 extracted components

**This is complex - consider deferring to separate PR**

**Components to Extract:**

#### GeneTrack.vue (~200 lines)
- Gene structure rendering (exons, introns)
- Gene coordinates
- Gene labels

#### VariantTrack.vue (~300 lines)
- Variant markers on gene
- Variant tooltips
- Click handling

#### GeneVizControls.vue (~150 lines)
- Zoom controls
- View mode toggle
- Filter controls

#### GeneVizLegend.vue (~100 lines)
- Color legend
- Type legend
- Help text

**Note:** This split requires careful coordination of D3.js state and SVG rendering. May be better as a follow-up PR.

**Commit Message:**
```
refactor(frontend): split HNF1BGeneVisualization into sub-components

- Create components/gene/GeneTrack.vue (~200 lines)
- Create components/gene/VariantTrack.vue (~300 lines)
- Create components/gene/GeneVizControls.vue (~150 lines)
- Create components/gene/GeneVizLegend.vue (~100 lines)
- Reduces HNF1BGeneVisualization from 1,510 to ~600 lines
- Maintains D3.js rendering logic
- All visualization features preserved
- Part of file size violations fix for PR #67
```

---

### Phase 5 Summary

**Total Time:** 6-8 hours
**Components Created:** 7-10 new sub-components
**Files Updated:** 3 main views

**Note:** HNF1BGeneVisualization split is complex and can be deferred to follow-up PR if needed.

**Testing Checklist After Phase 5:**
- [ ] Variants page loads and works correctly
- [ ] Variant detail page loads and works correctly
- [ ] All extracted components render properly
- [ ] No prop/emit errors in console
- [ ] Search, filter, sort work in Variants view
- [ ] Visualizations work in PageVariant view
- [ ] `npm run lint` passes
- [ ] No broken layouts

---

## 🔄 Phase 6: Testing & Documentation (3-5 hours)

### 6.1 Integration Testing (~2 hours)

**Frontend Tests:**
1. Test all pages load:
   - Home page
   - Variants list
   - Variant detail
   - Publications
   - Aggregations dashboard

2. Test all interactions:
   - Search variants
   - Apply filters
   - Sort columns
   - Click variants
   - Navigate between pages
   - View visualizations

3. Test edge cases:
   - Empty search results
   - No filters applied
   - Large datasets
   - Mobile responsive layout

**Backend Tests:**
```bash
cd backend

# Run full test suite
make test

# Run specific test categories
pytest tests/test_variant_search.py -v
pytest tests/test_rate_limiting.py -v
pytest tests/test_audit_logging.py -v

# Check coverage
pytest --cov=app --cov-report=html
```

---

### 6.2 Documentation Updates (~2 hours)

**Files to Update:**

#### frontend/CLAUDE.md
- Document new utility modules (utils/hgvs, utils/colors, utils/variants)
- Document component extraction pattern
- Update file structure
- Add examples of using utilities

#### backend/README.md (if exists)
- Document new router structure
- Document query_builders module
- Update API endpoint organization

#### docs/refactoring/pr-67-completion-report.md (NEW)
Create summary document:
```markdown
# PR #67 Refactoring Completion Report

## Summary
- **Duration:** X days
- **Total Commits:** X
- **Lines Removed:** ~500+
- **Files Refactored:** 12+
- **Components Created:** 10+

## Changes Made

### DRY Violations Fixed
- Created 3 utility modules (hgvs, colors, variants)
- Updated 4 frontend components
- Created backend query_builders module
- **Lines saved:** ~200-300

### File Size Violations Fixed
- Split endpoints.py (1,960 lines) → 5 routers (~300-400 lines each)
- Extracted Variants.vue components (989 → ~450 lines)
- Extracted PageVariant.vue components (971 → ~600 lines)
- **Files now compliant:** All under 500-line guideline

### Testing
- All backend tests pass (make test)
- Frontend manually tested
- No regressions found
- Performance improved (smaller bundle chunks)

## Before/After Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| endpoints.py size | 1,960 lines | N/A (split into 5 routers) | 5 focused files |
| Variants.vue size | 989 lines | ~450 lines | 54% reduction |
| PageVariant.vue size | 971 lines | ~600 lines | 38% reduction |
| Code duplication | ~300 lines | ~0 lines | Eliminated |
| Largest file | 1,960 lines | ~600 lines | 69% reduction |

## Lessons Learned
- [Document any insights or challenges]

## Next Steps
- Monitor for any issues in production
- Consider further splitting HNF1BGeneVisualization
- Add unit tests for utility modules
```

---

### 6.3 Final Verification (~1 hour)

**Checklist:**
- [ ] All commits follow conventional commit format
- [ ] All files pass linting (frontend and backend)
- [ ] All tests pass
- [ ] No console errors
- [ ] No broken imports
- [ ] Documentation updated
- [ ] CLAUDE.md files accurate
- [ ] PR description updated with changes

**Run Final Checks:**
```bash
# Frontend
cd frontend
npm run lint
npm run build  # Verify production build works

# Backend
cd backend
make check  # Runs lint + typecheck + test
make dev    # Verify server starts

# Test API with frontend
# Start both servers and test all functionality
```

---

## Phase 6 Summary

**Total Time:** 3-5 hours
**Documentation:** 3-4 files updated
**Testing:** Comprehensive manual and automated testing

---

## 📊 Overall Summary

### Time Breakdown

| Phase | Estimated Time | Status |
|-------|---------------|--------|
| 1. Create Utility Modules | 2 hours | ✅ DONE |
| 2. Update Components (DRY) | 6-8 hours | PENDING |
| 3. Backend Query Builders | 4-6 hours | PENDING |
| 4. Split Backend Routers | 8-10 hours | PENDING |
| 5. Extract Frontend Components | 6-8 hours | PENDING |
| 6. Testing & Documentation | 3-5 hours | PENDING |
| **TOTAL** | **29-39 hours** | **~7% DONE** |

### Success Criteria

**Before Merge, Verify:**
- [ ] No files exceed 500 lines
- [ ] No code duplication (DRY violations eliminated)
- [ ] All tests pass (backend and frontend)
- [ ] All linting passes
- [ ] Documentation updated
- [ ] No console errors
- [ ] All features work correctly
- [ ] PR review checklist complete

---

## 🔄 Session Resumption Guide

**If resuming in a new session:**

1. **Check current state:**
   ```bash
   git status
   git log --oneline -10
   ```

2. **Find your place:**
   - Look at todo list above
   - Check which phase was last completed
   - Review last commit message

3. **Continue from next task:**
   - Each phase has detailed step-by-step instructions
   - Copy code templates as needed
   - Follow testing checklist after each change

4. **Commit frequently:**
   - Commit after each component/router completed
   - Use suggested commit messages
   - Push to branch regularly

---

## 📝 Quick Reference

**Key Files:**
- Frontend utils: `frontend/src/utils/{hgvs,colors,variants}.js`
- Backend routers: `backend/app/phenopackets/routers/*.py`
- Query builders: `backend/app/phenopackets/query_builders.py`
- Components: `frontend/src/components/variants/*.vue`

**Testing Commands:**
```bash
# Frontend
npm run lint
npm run dev

# Backend
make check
make test
make dev
```

**Review Documents:**
- PR Review: `docs/reviews/feat-variant-page/detailed-review.md`
- This Plan: `docs/refactoring/pr-67-implementation-plan.md`

---

**Last Updated:** 2025-11-06
**Progress:** Phase 1 complete (utility modules created)
**Next Task:** Phase 2.1 - Update PageVariant.vue
