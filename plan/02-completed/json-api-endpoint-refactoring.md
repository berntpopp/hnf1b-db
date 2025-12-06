# JSON:API Endpoint Refactoring Plan (REVISED)

## Critical Review of Original Plan

### Problems Identified

| Issue | Violation | Original Plan | Simplified Approach |
|-------|-----------|---------------|---------------------|
| 10 new files proposed | KISS, YAGNI | Create publications/, variants/, utils/ modules | Extend existing modules, reuse `build_pagination_links` |
| Denormalized `phenopacket_count` column | Data Integrity | Add column + sync triggers | Compute via JOIN at query time |
| `fastapi-filter` library | KISS, DRY | Add new dependency | Reuse existing filter patterns from `crud.py` |
| Separate `variants/` module | Single Responsibility | Variants own their own router | Variants are a view over phenopackets, keep in aggregations |
| Deprecation period | Over-Engineering | Keep legacy + add warnings | **Alpha = just delete old endpoints** |
| 5 phases | Over-Engineering | Complex migration | 2 phases: Publications, then Variants/Search |
| Feature flags for migration | Over-Engineering | Dual API support | Single atomic migration per PR |

### Key Insight: Reuse What Exists

The phenopackets CRUD endpoint (`crud.py:350-393`) already has:
- ✅ `build_pagination_links()` - reusable for all endpoints
- ✅ JSON:API query parameter parsing (`page[number]`, `filter[sex]`, `sort`)
- ✅ `JsonApiResponse` envelope in `models/json_api.py`

**We don't need new utilities - we need to apply existing patterns consistently.**

---

## Revised Plan: Minimal Changes, Maximum Impact

### Guiding Principles

1. **KISS**: Modify existing files, don't create new modules
2. **DRY**: Extract `build_pagination_links` to shared location, reuse everywhere
3. **YAGNI**: No denormalized columns, no new libraries, no deprecation periods
4. **Alpha Rules**: Delete old endpoints immediately, update frontend in same PR

---

## Phase 1: Publications (Single PR)

### 1.1 What Changes

| File | Action | Description |
|------|--------|-------------|
| `aggregations.py` | MODIFY | Wrap `/aggregate/publications` in JSON:API envelope |
| `aggregations.py` | DELETE | Remove after new endpoint works |
| `publications/router.py` | CREATE | New `/api/v2/publications/` endpoint |
| `publications/service.py` | MODIFY | Add batch sync function |
| `crud.py` | REFACTOR | Extract `build_pagination_links` to shared location |
| `Publications.vue` | MODIFY | Remove PubMed API calls, use backend |

### 1.2 Publications List Endpoint

**Location**: `backend/app/publications/router.py` (extend existing file)

```python
from app.phenopackets.routers.crud import build_pagination_links  # Reuse!
from app.models.json_api import JsonApiResponse, MetaObject, PageMeta

@router.get("/", response_model=JsonApiResponse)
async def list_publications(
    request: Request,
    # Pagination
    page_number: int = Query(1, alias="page[number]", ge=1),
    page_size: int = Query(20, alias="page[size]", ge=1, le=100),
    # Filters
    filter_year: Optional[int] = Query(None, alias="filter[year]"),
    filter_has_doi: Optional[bool] = Query(None, alias="filter[has_doi]"),
    # Sorting
    sort: str = Query("-phenopacket_count"),
    # Search
    q: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List publications with JSON:API pagination."""

    # Query publications with enriched metadata (JOIN, not denormalized)
    base_query = """
    WITH pub_counts AS (
        SELECT
            ext_ref->>'id' as pmid,
            COUNT(DISTINCT phenopacket_id) as phenopacket_count,
            MIN(created_at) as first_added
        FROM phenopackets,
             jsonb_array_elements(phenopacket->'metaData'->'externalReferences') as ext_ref
        WHERE ext_ref->>'id' LIKE 'PMID:%'
        GROUP BY ext_ref->>'id'
    )
    SELECT
        REPLACE(pc.pmid, 'PMID:', '') as pmid,
        pm.title,
        pm.authors,
        pm.journal,
        pm.year,
        pm.doi,
        pc.phenopacket_count,
        pc.first_added
    FROM pub_counts pc
    LEFT JOIN publication_metadata pm ON pm.pmid = pc.pmid
    """
    # Add WHERE, ORDER BY, LIMIT/OFFSET based on params...
```

**Key Points**:
- No new `phenopacket_count` column - computed via JOIN
- Reuses existing `publication_metadata` table for enrichment
- LEFT JOIN ensures publications show even without metadata

### 1.3 Admin Sync Endpoint

```python
@router.post("/sync", dependencies=[Depends(require_admin)])
async def sync_publication_metadata(
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks,
):
    """Batch sync all publication metadata from PubMed.

    1. Get all unique PMIDs from phenopackets
    2. Filter out already-cached (< 90 days old)
    3. Batch fetch from PubMed (3 req/sec without API key)
    4. Store in publication_metadata table
    """
    background_tasks.add_task(sync_all_publications, db)
    return {"status": "sync_started", "message": "Background sync initiated"}
```

### 1.4 Frontend Changes

```javascript
// Publications.vue - DELETE this entire method:
async enrichWithPubMedData() { ... }  // DELETE

// REPLACE fetchPublications with:
async fetchPublications() {
    this.loading = true;
    try {
        const response = await getPublications({
            'page[number]': this.page,
            'page[size]': this.pageSize,
            'sort': '-phenopacket_count',
            'q': this.searchQuery,
        });
        this.publications = response.data;
        this.totalItems = response.meta.page.totalRecords;
    } finally {
        this.loading = false;
    }
}
```

### 1.5 Deletions

```bash
# DELETE these endpoints (alpha = no deprecation needed):
- /aggregate/publications  # Replaced by /publications/
```

---

## Phase 2: Variants + Search (Single PR)

### 2.1 Variants: Modify In Place

**Don't create new module** - variants are aggregated from phenopackets, not a first-class resource.

**Location**: `backend/app/phenopackets/routers/aggregations.py`

```python
# MODIFY existing aggregate_all_variants function
@router.get("/all-variants", response_model=JsonApiResponse)  # Add response_model
async def list_variants(  # Rename for clarity
    request: Request,
    # JSON:API pagination (REPLACE skip/limit)
    page_number: int = Query(1, alias="page[number]", ge=1),
    page_size: int = Query(20, alias="page[size]", ge=1, le=100),
    # JSON:API filters (RENAME existing params)
    filter_type: Optional[str] = Query(None, alias="filter[type]"),
    filter_classification: Optional[str] = Query(None, alias="filter[classification]"),
    filter_gene: Optional[str] = Query(None, alias="filter[gene]"),
    filter_consequence: Optional[str] = Query(None, alias="filter[consequence]"),
    # Sorting (keep existing)
    sort: Optional[str] = Query("-individual_count"),
    # Search (rename query -> q for consistency)
    q: Optional[str] = Query(None, alias="q"),
    db: AsyncSession = Depends(get_db),
):
    """List variants with JSON:API pagination."""

    # Existing query logic stays the same...
    # Just wrap result in JsonApiResponse envelope

    offset = (page_number - 1) * page_size

    # ... existing variant aggregation query ...

    return JsonApiResponse(
        data=variants,
        meta=MetaObject(page=PageMeta(
            current_page=page_number,
            page_size=page_size,
            total_pages=total_pages,
            total_records=total,
        )),
        links=build_pagination_links(base_url, page_number, page_size, total_pages, filters, sort),
    )
```

### 2.2 Search: Add Envelope

**Location**: `backend/app/phenopackets/routers/search.py`

```python
# MODIFY existing search_phenopackets function
@router.get("/search", response_model=JsonApiResponse)  # Add response_model
async def search_phenopackets(
    q: Optional[str] = Query(None),
    # JSON:API pagination (REPLACE skip/limit)
    page_number: int = Query(1, alias="page[number]", ge=1),
    page_size: int = Query(20, alias="page[size]", ge=1, le=100),
    # Filters (RENAME to JSON:API style)
    filter_hpo_id: Optional[str] = Query(None, alias="filter[hpo_id]"),
    filter_sex: Optional[str] = Query(None, alias="filter[sex]"),
    filter_gene: Optional[str] = Query(None, alias="filter[gene]"),
    filter_pmid: Optional[str] = Query(None, alias="filter[pmid]"),
    # Sorting
    sort: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # ... existing search logic ...
    # Wrap in JsonApiResponse at the end
```

### 2.3 Frontend Changes

```javascript
// Variants.vue - Update API call params
const params = {
    'page[number]': page,           // was: page
    'page[size]': itemsPerPage,     // was: page_size
    'q': searchQuery,               // was: query
    'filter[type]': filterType,     // was: variant_type
    'filter[classification]': cls,  // was: classification
    'sort': sortParam,              // unchanged
};
```

### 2.4 Deletions

```bash
# DELETE legacy parameters from aggregations.py:
- skip: int = Query(...)    # DELETE
- limit: int = Query(...)   # DELETE
- query: str = Query(...)   # RENAME to q
- variant_type: str         # RENAME to filter[type]
- classification: str       # RENAME to filter[classification]
```

---

## Shared Refactoring

### Extract `build_pagination_links` to Shared Location

```python
# MOVE from crud.py to app/utils/pagination.py
# (or keep in crud.py and import from there - simpler)

# Option A: Keep in crud.py, import elsewhere
from app.phenopackets.routers.crud import build_pagination_links

# Option B: Extract to utils/pagination.py (only if needed in 3+ places)
```

**Recommendation**: Option A (KISS) - don't create new file unless truly needed in many places.

---

## What We're NOT Doing (YAGNI)

| Rejected Approach | Why |
|-------------------|-----|
| Add `phenopacket_count` column | Denormalization risk, computed JOINs are fast enough |
| Create `backend/app/variants/` module | Variants aren't a first-class resource, they're aggregations |
| Add `fastapi-filter` library | We already have working filter patterns |
| Create `utils/filters.py`, `utils/sorting.py` | Over-abstraction for 2-3 use cases |
| Deprecation warnings and sunset dates | This is alpha, just delete |
| Feature flags for migration | Single atomic PR is simpler |
| New Pydantic schemas per resource | Reuse existing + extend as needed |

---

## File Changes Summary

### Phase 1: Publications

| File | Lines Changed | Action |
|------|---------------|--------|
| `publications/router.py` | +80 | Add list endpoint, sync endpoint |
| `publications/service.py` | +40 | Add batch sync function |
| `aggregations.py` | -50 | DELETE `/aggregate/publications` |
| `Publications.vue` | -60, +20 | Remove PubMed calls, use backend API |
| `frontend/src/api/index.js` | +5 | Add getPublications function |

### Phase 2: Variants + Search

| File | Lines Changed | Action |
|------|---------------|--------|
| `aggregations.py` | ~30 | Modify params, add JSON:API envelope |
| `search.py` | ~25 | Modify params, add JSON:API envelope |
| `Variants.vue` | ~15 | Update param names |

**Total: ~200 lines changed** (vs. ~500+ in original plan)

---

## Testing Strategy

### Unit Tests (Existing Pattern)

```python
# tests/test_publications.py
async def test_list_publications_pagination():
    response = await client.get("/api/v2/publications/?page[number]=1&page[size]=10")
    assert response.status_code == 200
    assert "data" in response.json()
    assert "meta" in response.json()
    assert "links" in response.json()
    assert response.json()["meta"]["page"]["currentPage"] == 1

async def test_list_publications_filter():
    response = await client.get("/api/v2/publications/?filter[year]=2020")
    assert all(p["year"] == 2020 for p in response.json()["data"])

async def test_list_publications_search():
    response = await client.get("/api/v2/publications/?q=HNF1B")
    assert response.status_code == 200
```

### Integration Tests

```python
async def test_publications_no_pubmed_call(mocker):
    """Ensure frontend doesn't call PubMed directly."""
    pubmed_spy = mocker.spy(httpx, "get")
    response = await client.get("/api/v2/publications/")
    # Verify no external calls to eutils.ncbi.nlm.nih.gov
    for call in pubmed_spy.call_args_list:
        assert "ncbi.nlm.nih.gov" not in str(call)
```

---

## Success Criteria

1. ✅ `GET /api/v2/publications/` returns JSON:API envelope
2. ✅ `GET /api/v2/phenopackets/aggregate/all-variants` returns JSON:API envelope
3. ✅ `GET /api/v2/phenopackets/search` returns JSON:API envelope
4. ✅ No frontend PubMed API calls (all via backend)
5. ✅ Consistent `page[number]`, `page[size]`, `filter[x]`, `sort`, `q` params
6. ✅ Old endpoints deleted (no deprecation baggage)
7. ✅ `make check` passes in both backend and frontend

---

## References

- [JSON:API v1.1 Specification](https://jsonapi.org/format/)
- Existing implementation: `backend/app/phenopackets/routers/crud.py:350-393`
- Existing models: `backend/app/models/json_api.py`
