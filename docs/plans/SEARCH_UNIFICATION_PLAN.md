# Unified Search System - Implementation Plan

**Status:** 🔄 In Progress (Revised)
**Created:** 2025-12-07
**Last Updated:** 2025-12-07

---

## Executive Summary

This plan unifies the fragmented search system into a single, modular, high-performance architecture using PostgreSQL materialized views and full-text search.

### Current State Issues

1. **Two Overlapping Search Systems**
   - `app/phenopackets/routers/search.py` (407 lines) - phenopacket-specific search
   - `app/search/` module - new global search (partially implemented)

2. **Anti-Patterns Identified**
   - Dynamic SQL string building (SQL injection risk in old search)
   - No repository pattern (direct SQL in router)
   - Missing variants from global search index
   - No automated MV refresh strategy
   - Duplicated filter logic across systems

3. **Missing Features in New Global Search**
   - No cursor-based pagination (only offset)
   - No search facets
   - No filter capabilities (HPO, sex, gene, PMID)
   - No phenopacket-specific detailed search

---

## Architecture Decision

### Option Chosen: Unified Service Layer

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (Routers)                    │
├──────────────────────┬──────────────────────────────────────┤
│ /api/v2/search/      │  /api/v2/phenopackets/search         │
│  - autocomplete      │   - KEPT for backwards compatibility │
│  - global            │   - Delegates to service layer       │
└──────────┬───────────┴──────────────────┬───────────────────┘
           │                              │
           └──────────────┬───────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                            │
│  app/search/services.py                                     │
│  - GlobalSearchService (existing)                           │
│  - PhenopacketSearchService (new, extracted)                │
│  - SearchFacetService (new, extracted)                      │
└──────────┬────────────────────────────┬─────────────────────┘
           │                            │
           ▼                            ▼
┌─────────────────────┐    ┌─────────────────────────────────┐
│   Materialized View │    │   Direct Table Queries          │
│   global_search_idx │    │   (phenopackets table)          │
│   - Fast autocomplete    │   - Detailed search              │
│   - Global FTS           │   - Cursor pagination            │
└─────────────────────┘    └─────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Enhance Materialized View (Migration)

**Goal:** Add variants to global search index for comprehensive coverage.

**File:** `backend/alembic/versions/xxx_add_variants_to_global_search.py`

```sql
-- Add variants to global_search_index
DROP MATERIALIZED VIEW IF EXISTS global_search_index;
CREATE MATERIALIZED VIEW global_search_index AS
-- Existing entities (genes, domains, transcripts, publications, phenopackets)
...
UNION ALL
-- NEW: Unique variants extracted from phenopackets
SELECT DISTINCT
    gi.value->'variantInterpretation'->'variationDescriptor'->>'id' AS id,
    COALESCE(
        gi.value->'variantInterpretation'->'variationDescriptor'->>'label',
        gi.value->'variantInterpretation'->'variationDescriptor'
            ->'geneContext'->>'symbol' || ':' ||
        (gi.value->'variantInterpretation'->'variationDescriptor'
            ->'expressions'->0->>'value')
    ) AS label,
    'Variant' AS type,
    gi.value->'variantInterpretation'->'variationDescriptor'
        ->>'moleculeContext' AS subtype,
    to_tsvector('english',
        COALESCE(gi.value->'variantInterpretation'->'variationDescriptor'->>'label', '') || ' ' ||
        COALESCE(gi.value->'variantInterpretation'->'variationDescriptor'
            ->'geneContext'->>'symbol', '')
    ) AS search_vector,
    gi.value->'variantInterpretation'->>'acmgPathogenicityClassification' AS extra_info
FROM phenopackets p,
    jsonb_array_elements(p.phenopacket->'interpretations') AS interp,
    jsonb_array_elements(interp.value->'diagnosis'->'genomicInterpretations') AS gi
WHERE p.deleted_at IS NULL
  AND gi.value->'variantInterpretation'->'variationDescriptor'->>'id' IS NOT NULL;
```

### Phase 2: Refactor Service Layer

**Goal:** Extract search logic into proper service classes following SOLID principles.

#### 2.1 Create Base Search Repository

**File:** `backend/app/search/repositories.py`

```python
"""Search repositories - Data access layer for search operations."""

from abc import ABC, abstractmethod
from typing import Any, Protocol
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SearchResult(Protocol):
    """Protocol for search results."""
    id: str
    label: str
    type: str
    subtype: str | None
    score: float | None


class BaseSearchRepository(ABC):
    """Abstract base for search repositories."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @abstractmethod
    async def search(self, query: str, **kwargs) -> list[SearchResult]:
        """Execute search query."""
        pass

    @abstractmethod
    async def count(self, query: str, **kwargs) -> int:
        """Count matching results."""
        pass


class GlobalSearchRepository(BaseSearchRepository):
    """Repository for global materialized view search."""

    async def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        type_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Search global index with optional type filter."""
        params = {"query": query, "limit": limit, "offset": offset}
        filter_clause = ""

        if type_filter:
            filter_clause = "AND type = :type_filter"
            params["type_filter"] = type_filter

        sql = text(f"""
            SELECT id, label, type, subtype, extra_info,
                   ts_rank(search_vector, websearch_to_tsquery('english', :query)) as score
            FROM global_search_index
            WHERE search_vector @@ websearch_to_tsquery('english', :query)
            {filter_clause}
            ORDER BY score DESC
            LIMIT :limit OFFSET :offset
        """)

        result = await self.db.execute(sql, params)
        return [dict(row._mapping) for row in result.fetchall()]

    async def count(self, query: str, type_filter: str | None = None) -> dict[str, int]:
        """Get counts grouped by type."""
        sql = text("""
            SELECT type, COUNT(*) as count
            FROM global_search_index
            WHERE search_vector @@ websearch_to_tsquery('english', :query)
            GROUP BY type
        """)
        result = await self.db.execute(sql, {"query": query})
        return {row.type: row.count for row in result.fetchall()}

    async def autocomplete(
        self,
        query: str,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """Fast autocomplete using trigram + prefix matching."""
        sql = text("""
            SELECT id, label, type, subtype, extra_info,
                   similarity(label, :query) as score
            FROM global_search_index
            WHERE label ILIKE :prefix
               OR label % :query
            ORDER BY
                CASE WHEN label ILIKE :prefix THEN 1 ELSE 2 END,
                score DESC,
                label ASC
            LIMIT :limit
        """)

        result = await self.db.execute(sql, {
            "query": query,
            "prefix": f"{query}%",
            "limit": limit
        })
        return [dict(row._mapping) for row in result.fetchall()]
```

#### 2.2 Enhanced Search Service

**File:** `backend/app/search/services.py` (rewrite)

```python
"""Search services - Business logic layer."""

from dataclasses import dataclass
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.search.repositories import GlobalSearchRepository
from app.search.schemas import SearchResultItem, SearchResponse


@dataclass
class PaginationParams:
    """Pagination parameters."""
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class GlobalSearchService:
    """Service for global unified search."""

    def __init__(self, db: AsyncSession):
        self.repo = GlobalSearchRepository(db)

    async def search(
        self,
        query: str,
        pagination: PaginationParams,
        type_filter: str | None = None
    ) -> SearchResponse:
        """Execute global search with pagination."""
        if not query or len(query) < 2:
            return SearchResponse(results=[], total=0, summary={})

        results = await self.repo.search(
            query=query,
            limit=pagination.page_size,
            offset=pagination.offset,
            type_filter=type_filter
        )

        summary = await self.repo.count(query)
        total = sum(summary.values())

        return SearchResponse(
            results=[SearchResultItem(**r) for r in results],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            summary=summary
        )

    async def autocomplete(self, query: str, limit: int = 10) -> list[SearchResultItem]:
        """Get autocomplete suggestions."""
        if not query or len(query) < 2:
            return []

        results = await self.repo.autocomplete(query, limit)
        return [SearchResultItem(**r) for r in results]
```

### Phase 3: Phenopacket Search Consolidation

**Goal:** Refactor phenopacket-specific search to use service layer.

#### 3.1 Create Phenopacket Search Service

**File:** `backend/app/search/phenopacket_search.py`

```python
"""Phenopacket-specific search with advanced filtering."""

import json
from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.pagination import encode_cursor, decode_cursor


class PhenopacketSearchService:
    """Service for phenopacket-specific advanced search."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self,
        query: str | None = None,
        hpo_id: str | None = None,
        sex: str | None = None,
        gene: str | None = None,
        pmid: str | None = None,
        page_size: int = 20,
        cursor_after: str | None = None,
        cursor_before: str | None = None,
    ) -> dict[str, Any]:
        """
        Advanced phenopacket search with cursor pagination.

        Supports:
        - Full-text search (q parameter)
        - HPO term filtering
        - Sex filtering
        - Gene symbol filtering
        - Publication PMID filtering
        - Cursor-based pagination for stable results
        """
        params: dict[str, Any] = {}
        where_conditions = ["deleted_at IS NULL"]
        select_extra = ""

        # Build dynamic filters
        if query:
            select_extra = ", ts_rank(search_vector, plainto_tsquery('english', :query)) AS rank"
            where_conditions.append(
                "search_vector @@ plainto_tsquery('english', :query)"
            )
            params["query"] = query

        if hpo_id:
            where_conditions.append(
                "phenopacket->'phenotypicFeatures' @> :hpo_filter"
            )
            params["hpo_filter"] = json.dumps([{"type": {"id": hpo_id}}])

        if sex:
            where_conditions.append("subject_sex = :sex")
            params["sex"] = sex

        if gene:
            where_conditions.append(
                "phenopacket->'interpretations' @> :gene_filter"
            )
            params["gene_filter"] = json.dumps([{
                "diagnosis": {
                    "genomicInterpretations": [{
                        "variantInterpretation": {
                            "variationDescriptor": {
                                "geneContext": {"symbol": gene}
                            }
                        }
                    }]
                }
            }])

        if pmid:
            where_conditions.append(
                "phenopacket->'metaData'->'externalReferences' @> :pmid_filter"
            )
            params["pmid_filter"] = json.dumps([{"id": f"PMID:{pmid}"}])

        # Handle cursor pagination
        is_backward = cursor_before is not None
        cursor_data = None

        if cursor_after:
            cursor_data = decode_cursor(cursor_after)
        elif cursor_before:
            cursor_data = decode_cursor(cursor_before)

        if cursor_data:
            cursor_created_at = cursor_data.get("created_at")
            cursor_id = cursor_data.get("id")
            if cursor_created_at and cursor_id:
                if is_backward:
                    where_conditions.append("""
                        (created_at > :cursor_created_at OR
                         (created_at = :cursor_created_at AND id > :cursor_id))
                    """)
                else:
                    where_conditions.append("""
                        (created_at < :cursor_created_at OR
                         (created_at = :cursor_created_at AND id < :cursor_id))
                    """)
                params["cursor_created_at"] = cursor_created_at
                params["cursor_id"] = str(cursor_id)

        # Build query
        where_clause = " AND ".join(where_conditions)
        order_by = "ORDER BY rank DESC, created_at DESC, id DESC" if query else "ORDER BY created_at DESC, id DESC"
        if is_backward:
            order_by = order_by.replace("DESC", "ASC")

        params["limit"] = page_size + 1

        sql = text(f"""
            SELECT id, phenopacket_id, phenopacket, created_at{select_extra}
            FROM phenopackets
            WHERE {where_clause}
            {order_by}
            LIMIT :limit
        """)

        result = await self.db.execute(sql, params)
        rows = list(result.fetchall())

        has_more = len(rows) > page_size
        if has_more:
            rows = rows[:page_size]

        if is_backward:
            rows = list(reversed(rows))

        # Build cursors
        start_cursor = end_cursor = None
        if rows:
            start_cursor = encode_cursor({
                "created_at": rows[0].created_at,
                "id": rows[0].id
            })
            end_cursor = encode_cursor({
                "created_at": rows[-1].created_at,
                "id": rows[-1].id
            })

        return {
            "data": [
                {
                    "id": r.phenopacket_id,
                    "type": "phenopacket",
                    "attributes": r.phenopacket,
                    "meta": {"rank": r.rank if query else None}
                }
                for r in rows
            ],
            "meta": {
                "page": {
                    "pageSize": page_size,
                    "hasNextPage": has_more if not is_backward else bool(cursor_after),
                    "hasPreviousPage": bool(cursor_after) if not is_backward else has_more,
                    "startCursor": start_cursor,
                    "endCursor": end_cursor,
                }
            }
        }

    async def get_facets(
        self,
        query: str | None = None,
        hpo_id: str | None = None,
        sex: str | None = None,
        gene: str | None = None,
        pmid: str | None = None,
    ) -> dict[str, list[dict]]:
        """Get facet counts for search filters."""
        # Implementation delegated to FacetService for cleaner separation
        facet_service = FacetService(self.db)
        return await facet_service.get_facets(
            query=query, hpo_id=hpo_id, sex=sex, gene=gene, pmid=pmid
        )


class FacetService:
    """Service for computing search facets."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_facets(self, **filters) -> dict[str, list[dict]]:
        """Compute facet counts based on current filters."""
        # Build base filter conditions
        base_conditions, params = self._build_filter_conditions(filters)

        return {
            "sex": await self._get_sex_facets(base_conditions, params, filters.get("sex")),
            "hasVariants": await self._get_variant_facets(base_conditions, params),
            "pathogenicity": await self._get_pathogenicity_facets(base_conditions, params),
            "genes": await self._get_gene_facets(base_conditions, params),
            "phenotypes": await self._get_phenotype_facets(base_conditions, params),
        }

    def _build_filter_conditions(self, filters: dict) -> tuple[str, dict]:
        """Build SQL WHERE conditions from filters."""
        conditions = ["deleted_at IS NULL"]
        params = {}

        if filters.get("query"):
            conditions.append("search_vector @@ plainto_tsquery('english', :query)")
            params["query"] = filters["query"]

        if filters.get("hpo_id"):
            conditions.append("phenopacket->'phenotypicFeatures' @> :hpo_filter")
            params["hpo_filter"] = json.dumps([{"type": {"id": filters["hpo_id"]}}])

        if filters.get("gene"):
            conditions.append("phenopacket->'interpretations' @> :gene_filter")
            params["gene_filter"] = json.dumps([{
                "diagnosis": {"genomicInterpretations": [{
                    "variantInterpretation": {"variationDescriptor": {
                        "geneContext": {"symbol": filters["gene"]}
                    }}
                }]}
            }])

        if filters.get("pmid"):
            conditions.append("phenopacket->'metaData'->'externalReferences' @> :pmid_filter")
            params["pmid_filter"] = json.dumps([{"id": f"PMID:{filters['pmid']}"}])

        return " AND ".join(conditions), params

    async def _get_sex_facets(self, base_conditions: str, params: dict, exclude_sex: str | None) -> list[dict]:
        """Get sex distribution (excluding current sex filter)."""
        conditions = base_conditions
        if exclude_sex:
            conditions = " AND ".join([c for c in base_conditions.split(" AND ") if "subject_sex" not in c])

        sql = text(f"""
            SELECT subject_sex AS value, COUNT(*) AS count
            FROM phenopackets
            WHERE {conditions}
            GROUP BY subject_sex
            ORDER BY count DESC
        """)
        result = await self.db.execute(sql, params)
        return [{"value": r.value, "label": r.value, "count": r.count} for r in result.fetchall()]

    # Similar methods for other facets...
```

### Phase 4: Update Routers (Thin Controllers)

**Goal:** Make routers thin controllers that delegate to services.

#### 4.1 Global Search Router

**File:** `backend/app/search/routers.py` (update)

```python
"""Global search API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.search.services import GlobalSearchService, PaginationParams
from app.search.schemas import AutocompleteResponse, GlobalSearchResponse

router = APIRouter(tags=["search"])


@router.get("/search/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get autocomplete suggestions across all entity types."""
    service = GlobalSearchService(db)
    results = await service.autocomplete(q, limit)
    return AutocompleteResponse(results=results)


@router.get("/search/global", response_model=GlobalSearchResponse)
async def global_search(
    q: str = Query(..., min_length=1, description="Search query"),
    type: str | None = Query(None, description="Filter by result type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=100, alias="page_size"),
    db: AsyncSession = Depends(get_db)
):
    """Perform global full-text search across all entity types."""
    service = GlobalSearchService(db)
    pagination = PaginationParams(page=page, page_size=page_size)
    return await service.search(q, pagination, type)
```

#### 4.2 Phenopacket Search Router

**File:** `backend/app/phenopackets/routers/search.py` (simplify)

```python
"""Phenopacket search endpoints - delegates to service layer."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.json_api import JsonApiCursorResponse
from app.search.phenopacket_search import PhenopacketSearchService

router = APIRouter()


@router.get("/search", response_model=JsonApiCursorResponse)
async def search_phenopackets(
    request: Request,
    q: Optional[str] = Query(None, description="Full-text search query"),
    hpo_id: Optional[str] = Query(None, description="Filter by HPO term ID"),
    sex: Optional[str] = Query(None, description="Filter by subject sex"),
    gene: Optional[str] = Query(None, description="Filter by gene symbol"),
    pmid: Optional[str] = Query(None, description="Filter by publication PMID"),
    page_size: int = Query(20, alias="page[size]", ge=1, le=100),
    page_after: Optional[str] = Query(None, alias="page[after]"),
    page_before: Optional[str] = Query(None, alias="page[before]"),
    db: AsyncSession = Depends(get_db),
):
    """Advanced phenopacket search with cursor pagination."""
    service = PhenopacketSearchService(db)
    return await service.search(
        query=q,
        hpo_id=hpo_id,
        sex=sex,
        gene=gene,
        pmid=pmid,
        page_size=page_size,
        cursor_after=page_after,
        cursor_before=page_before,
    )


@router.get("/search/facets")
async def get_search_facets(
    q: Optional[str] = Query(None),
    hpo_id: Optional[str] = Query(None),
    sex: Optional[str] = Query(None),
    gene: Optional[str] = Query(None),
    pmid: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get facet counts for search filters."""
    service = PhenopacketSearchService(db)
    return {"facets": await service.get_facets(
        query=q, hpo_id=hpo_id, sex=sex, gene=gene, pmid=pmid
    )}
```

### Phase 5: MV Refresh Strategy

**Goal:** Automate materialized view refresh on data changes.

#### 5.1 Add Refresh Trigger

**File:** `backend/app/search/mv_refresh.py`

```python
"""Materialized view refresh utilities."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def refresh_global_search_index(db: AsyncSession, concurrently: bool = True) -> None:
    """
    Refresh the global search materialized view.

    Args:
        db: Database session
        concurrently: If True, uses CONCURRENTLY (doesn't block reads but requires unique index)
    """
    keyword = "CONCURRENTLY" if concurrently else ""
    await db.execute(text(f"REFRESH MATERIALIZED VIEW {keyword} global_search_index"))
    await db.commit()


async def schedule_refresh_if_stale(db: AsyncSession, max_age_seconds: int = 300) -> bool:
    """
    Refresh MV if older than max_age_seconds.

    Returns True if refresh was performed.
    """
    # Check last refresh time (PostgreSQL doesn't track this natively)
    # Use a metadata table or pg_stat_user_tables
    result = await db.execute(text("""
        SELECT EXTRACT(EPOCH FROM (NOW() - last_analyze)) as age_seconds
        FROM pg_stat_user_tables
        WHERE relname = 'global_search_index'
    """))
    row = result.fetchone()

    if row and row.age_seconds and row.age_seconds > max_age_seconds:
        await refresh_global_search_index(db)
        return True
    return False
```

#### 5.2 Integration with CRUD Operations

Add refresh trigger to phenopacket create/update/delete:

```python
# In crud.py after successful create/update/delete:
from app.search.mv_refresh import schedule_refresh_if_stale

# After commit:
await schedule_refresh_if_stale(db, max_age_seconds=60)
```

### Phase 6: Testing

**Goal:** Comprehensive test coverage for search functionality.

#### 6.1 Test Structure

```
backend/tests/
├── unit/
│   └── search/
│       ├── test_global_search_service.py
│       ├── test_phenopacket_search_service.py
│       └── test_facet_service.py
└── integration/
    └── search/
        ├── test_global_search_api.py
        └── test_phenopacket_search_api.py
```

#### 6.2 Key Test Cases

```python
# test_global_search_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.search.services import GlobalSearchService, PaginationParams


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def service(mock_db):
    return GlobalSearchService(mock_db)


class TestGlobalSearchService:
    async def test_search_returns_empty_for_short_query(self, service):
        """Should return empty results for queries < 2 chars."""
        result = await service.search("a", PaginationParams())
        assert result.results == []
        assert result.total == 0

    async def test_search_with_type_filter(self, service, mock_db):
        """Should filter results by type."""
        mock_db.execute.return_value.fetchall.return_value = []

        await service.search("HNF1B", PaginationParams(), type_filter="Gene")

        call_args = mock_db.execute.call_args
        assert "type = :type_filter" in str(call_args)

    async def test_autocomplete_uses_trigram_matching(self, service, mock_db):
        """Should use trigram similarity for autocomplete."""
        mock_db.execute.return_value.fetchall.return_value = []

        await service.autocomplete("HNF")

        call_args = mock_db.execute.call_args
        assert "similarity" in str(call_args)
        assert "ILIKE" in str(call_args)
```

---

## File Changes Summary

### New Files
| File | Purpose |
|------|---------|
| `app/search/repositories.py` | Data access layer for search |
| `app/search/phenopacket_search.py` | Phenopacket-specific search service |
| `app/search/mv_refresh.py` | MV refresh utilities |
| `alembic/versions/xxx_add_variants_to_search.py` | Migration for variants |
| `tests/unit/search/*.py` | Unit tests |
| `tests/integration/search/*.py` | Integration tests |

### Modified Files
| File | Changes |
|------|---------|
| `app/search/services.py` | Rewrite with repository pattern |
| `app/search/routers.py` | Simplify to thin controller |
| `app/search/schemas.py` | Add missing fields |
| `app/phenopackets/routers/search.py` | Delegate to service layer |
| `app/phenopackets/routers/crud.py` | Add MV refresh trigger |

### Files to Delete (After Migration)
| File | Reason |
|------|--------|
| None | Keep backwards compatibility |

---

## Implementation Order

1. **Phase 1**: Migration - Add variants to MV (non-breaking)
2. **Phase 2**: Create new service layer files (non-breaking)
3. **Phase 3**: Refactor phenopacket search to use services (non-breaking)
4. **Phase 4**: Update routers to use services (non-breaking)
5. **Phase 5**: Add MV refresh strategy (non-breaking)
6. **Phase 6**: Add tests (non-breaking)

Each phase is independently deployable and backwards compatible.

---

## Best Practices Applied

### SOLID Principles
- **S**ingle Responsibility: Each service handles one domain
- **O**pen/Closed: Services extensible via new repositories
- **L**iskov Substitution: Repository interfaces allow swapping implementations
- **I**nterface Segregation: Separate interfaces for global vs phenopacket search
- **D**ependency Inversion: Services depend on abstractions (repositories)

### DRY
- Filter building logic extracted to reusable methods
- Pagination logic centralized in PaginationParams dataclass
- Cursor encoding/decoding reused from utils

### KISS
- Simple service methods with clear responsibilities
- Minimal abstraction layers (Router → Service → Repository → DB)
- No complex inheritance hierarchies

### Modularization
- Clear separation: routes, services, repositories, schemas
- Each module can be tested independently
- Easy to add new entity types to search

---

## Acceptance Criteria

- [ ] Global search returns results from all entity types including variants
- [ ] Autocomplete works with 2+ character queries
- [ ] Phenopacket search supports all existing filters
- [ ] Cursor pagination works correctly for phenopacket search
- [ ] Facets return accurate counts
- [ ] MV refreshes automatically within 60s of data changes
- [ ] All tests pass
- [ ] No breaking changes to existing API contracts
