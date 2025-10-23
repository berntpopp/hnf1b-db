# Issue #62: feat(api): implement JSON:API query conventions and cursor pagination

## Overview

Add JSON:API v1.1 pagination, filtering, and sorting conventions to `/api/v2/phenopackets` endpoint while maintaining GA4GH Phenopackets response structure.

**Current:** `GET /phenopackets?skip=0&limit=100&sex=MALE` → `List[...]` (no metadata)
**Target:** `GET /phenopackets?page[number]=1&page[size]=100&filter[sex]=MALE&sort=-created_at` → `{data, meta, links}`

**Related Standards:**
- [JSON:API v1.1 Specification](https://jsonapi.org/format/)
- [GA4GH Phenopackets v2](https://phenopacket-schema.readthedocs.io/)

## Why This Matters

### Current Pain Points

**Problem 1: No Pagination Metadata**
```python
# Current response (lacking context)
GET /phenopackets?skip=0&limit=20
→ [phenopacket1, phenopacket2, ..., phenopacket20]

# Questions frontend cannot answer:
- How many total phenopackets exist? (cannot show "20 of 864")
- Are there more pages? (cannot disable "Next" button)
- What page am I on? (cannot show "Page 1 of 44")
```

**Problem 2: Non-Standard Query Parameters**
```python
# Current (custom conventions)
GET /phenopackets?skip=0&limit=20&sex=MALE&has_variants=true

# Industry standard (JSON:API)
GET /phenopackets?page[number]=1&page[size]=20&filter[sex]=MALE&filter[has_variants]=true
```

**Problem 3: No Cursor Pagination**
```python
# Current offset pagination breaks when data changes
1. User loads page 2 (skip=20, limit=20)
2. Admin deletes 10 phenopackets from page 1
3. User navigates to page 3 (skip=40, limit=20)
4. Result: User misses 10 records that shifted from page 3 to page 2
```

**Problem 4: No Sorting Control**
```python
# Current: No sorting parameter (database order)
GET /phenopackets?skip=0&limit=20

# Desired: User-controlled sorting
GET /phenopackets?sort=-created_at,subject_id
→ Order by created_at DESC, then subject_id ASC
```

### Target State (JSON:API Compliant)

```python
# Request with JSON:API conventions
GET /phenopackets?page[number]=1&page[size]=20&filter[sex]=MALE&sort=-created_at

# Response with metadata and links
{
  "data": [
    {...phenopacket1...},
    {...phenopacket2...},
    ...
  ],
  "meta": {
    "page": {
      "currentPage": 1,
      "pageSize": 20,
      "totalPages": 44,
      "totalRecords": 864
    }
  },
  "links": {
    "self": "/phenopackets?page[number]=1&page[size]=20&filter[sex]=MALE&sort=-created_at",
    "first": "/phenopackets?page[number]=1&page[size]=20&filter[sex]=MALE&sort=-created_at",
    "prev": null,
    "next": "/phenopackets?page[number]=2&page[size]=20&filter[sex]=MALE&sort=-created_at",
    "last": "/phenopackets?page[number]=44&page[size]=20&filter[sex]=MALE&sort=-created_at"
  }
}
```

### Benefits

1. **Better UX**: Frontend can show "Page 1 of 44" and disable navigation buttons intelligently
2. **Standard Conventions**: Developers familiar with JSON:API understand parameters immediately
3. **Stable Pagination**: Cursor-based pagination prevents missed/duplicate records
4. **Flexible Sorting**: Users can sort by created date, subject ID, etc.
5. **Consistent Filtering**: All endpoints use `filter[field]=value` pattern

## Required Changes

### Phase 1: Response Envelope (Offset Pagination)

#### 1.1 Create Response Models

**File:** `backend/app/models/json_api.py` (new file)

```python
"""JSON:API response envelope models."""

from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PageMeta(BaseModel):
    """Pagination metadata."""

    current_page: int = Field(..., alias="currentPage", ge=1)
    page_size: int = Field(..., alias="pageSize", ge=1, le=1000)
    total_pages: int = Field(..., alias="totalPages", ge=0)
    total_records: int = Field(..., alias="totalRecords", ge=0)

    class Config:
        populate_by_name = True


class MetaObject(BaseModel):
    """JSON:API meta object."""

    page: PageMeta


class LinksObject(BaseModel):
    """JSON:API links object for pagination."""

    self: str
    first: str
    prev: Optional[str] = None
    next: Optional[str] = None
    last: str


class JsonApiResponse(BaseModel, Generic[T]):
    """JSON:API compliant response envelope.

    Wraps GA4GH Phenopackets data with pagination metadata and links.
    """

    data: List[T]
    meta: MetaObject
    links: LinksObject
```

#### 1.2 Update Phenopackets Endpoint

**File:** `backend/app/routers/phenopackets.py`

**Current Implementation:**
```python
@router.get("/", response_model=List[PhenopacketDocument])
async def list_phenopackets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sex: Optional[str] = Query(None),
    has_variants: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List phenopackets with optional filters."""
    query = select(Phenopacket)

    # Apply filters
    if sex:
        query = query.where(Phenopacket.subject_sex == sex)
    if has_variants is not None:
        query = query.where(Phenopacket.has_variants == has_variants)

    # Pagination
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    phenopackets = result.scalars().all()

    return [p.jsonb for p in phenopackets]  # Returns List[dict]
```

**New Implementation:**
```python
from app.models.json_api import JsonApiResponse, MetaObject, PageMeta, LinksObject
from urllib.parse import urlencode


@router.get("/", response_model=JsonApiResponse[PhenopacketDocument])
async def list_phenopackets(
    # JSON:API pagination parameters
    page_number: int = Query(1, alias="page[number]", ge=1),
    page_size: int = Query(100, alias="page[size]", ge=1, le=1000),

    # JSON:API filter parameters
    filter_sex: Optional[str] = Query(None, alias="filter[sex]"),
    filter_has_variants: Optional[bool] = Query(None, alias="filter[has_variants]"),

    # JSON:API sort parameter
    sort: Optional[str] = Query(None, description="Comma-separated fields, prefix with '-' for descending"),

    # Legacy parameters (backwards compatibility)
    skip: Optional[int] = Query(None, ge=0, deprecated=True),
    limit: Optional[int] = Query(None, ge=1, le=1000, deprecated=True),
    sex: Optional[str] = Query(None, deprecated=True),
    has_variants: Optional[bool] = Query(None, deprecated=True),

    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """List phenopackets with JSON:API pagination, filtering, and sorting.

    **Pagination:**
    - `page[number]`: Page number (1-indexed)
    - `page[size]`: Items per page (default: 100, max: 1000)
    - Legacy `skip`/`limit` still supported (deprecated)

    **Filtering:**
    - `filter[sex]`: Filter by subject sex (MALE, FEMALE, OTHER_SEX, UNKNOWN_SEX)
    - `filter[has_variants]`: Filter by variant presence (true/false)

    **Sorting:**
    - `sort`: Comma-separated fields (e.g., `-created_at,subject_id`)
    - Prefix with `-` for descending order
    - Supported fields: `created_at`, `subject_id`, `subject_sex`

    **Examples:**
    ```
    GET /phenopackets?page[number]=1&page[size]=20
    GET /phenopackets?page[number]=2&page[size]=50&filter[sex]=MALE
    GET /phenopackets?page[number]=1&page[size]=100&sort=-created_at
    GET /phenopackets?page[number]=3&page[size]=20&filter[has_variants]=true&sort=subject_id
    ```
    """
    # Handle backwards compatibility
    if skip is not None or limit is not None:
        # Convert legacy pagination to page-based
        actual_skip = skip if skip is not None else (page_number - 1) * page_size
        actual_limit = limit if limit is not None else page_size
        page_number = (actual_skip // actual_limit) + 1
        page_size = actual_limit

    # Handle legacy filter parameters
    filter_sex = filter_sex or sex
    filter_has_variants = filter_has_variants if filter_has_variants is not None else has_variants

    # Build query
    query = select(Phenopacket)

    # Apply filters
    if filter_sex:
        query = query.where(Phenopacket.subject_sex == filter_sex)
    if filter_has_variants is not None:
        query = query.where(Phenopacket.has_variants == filter_has_variants)

    # Count total records (with filters applied)
    count_query = select(func.count()).select_from(query.subquery())
    total_records = await db.scalar(count_query)

    # Apply sorting
    if sort:
        order_clauses = parse_sort_parameter(sort)
        for order_clause in order_clauses:
            query = query.order_by(order_clause)
    else:
        # Default sort by created_at DESC
        query = query.order_by(Phenopacket.created_at.desc())

    # Apply pagination
    offset = (page_number - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    phenopackets = result.scalars().all()

    # Calculate pagination metadata
    total_pages = (total_records + page_size - 1) // page_size  # Ceiling division

    # Build response
    meta = MetaObject(
        page=PageMeta(
            current_page=page_number,
            page_size=page_size,
            total_pages=total_pages,
            total_records=total_records,
        )
    )

    links = build_pagination_links(
        base_url=str(request.url.remove_query_params(["page[number]"])),
        current_page=page_number,
        page_size=page_size,
        total_pages=total_pages,
        filters={"filter[sex]": filter_sex, "filter[has_variants]": filter_has_variants},
        sort=sort,
    )

    return JsonApiResponse(
        data=[p.jsonb for p in phenopackets],
        meta=meta,
        links=links,
    )


def parse_sort_parameter(sort: str) -> list:
    """Parse JSON:API sort parameter into SQLAlchemy order clauses.

    Args:
        sort: Comma-separated fields, prefix with '-' for descending
              Example: "-created_at,subject_id"

    Returns:
        List of SQLAlchemy order clauses

    Raises:
        HTTPException: If sort field is not allowed
    """
    allowed_fields = {
        "created_at": Phenopacket.created_at,
        "subject_id": Phenopacket.subject_id,
        "subject_sex": Phenopacket.subject_sex,
    }

    order_clauses = []
    for field in sort.split(","):
        field = field.strip()
        if field.startswith("-"):
            # Descending
            field_name = field[1:]
            if field_name not in allowed_fields:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid sort field: {field_name}. Allowed: {', '.join(allowed_fields.keys())}",
                )
            order_clauses.append(allowed_fields[field_name].desc())
        else:
            # Ascending
            if field not in allowed_fields:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid sort field: {field}. Allowed: {', '.join(allowed_fields.keys())}",
                )
            order_clauses.append(allowed_fields[field].asc())

    return order_clauses


def build_pagination_links(
    base_url: str,
    current_page: int,
    page_size: int,
    total_pages: int,
    filters: dict,
    sort: Optional[str] = None,
) -> LinksObject:
    """Build JSON:API pagination links.

    Args:
        base_url: Base URL without query parameters
        current_page: Current page number (1-indexed)
        page_size: Items per page
        total_pages: Total number of pages
        filters: Dictionary of filter parameters
        sort: Sort parameter string

    Returns:
        LinksObject with self, first, prev, next, last links
    """
    def build_url(page: int) -> str:
        params = {
            "page[number]": page,
            "page[size]": page_size,
        }
        # Add filters (exclude None values)
        for key, value in filters.items():
            if value is not None:
                params[key] = value
        # Add sort
        if sort:
            params["sort"] = sort

        return f"{base_url}?{urlencode(params)}"

    return LinksObject(
        self=build_url(current_page),
        first=build_url(1),
        prev=build_url(current_page - 1) if current_page > 1 else None,
        next=build_url(current_page + 1) if current_page < total_pages else None,
        last=build_url(total_pages),
    )
```

### Phase 2: Cursor Pagination

#### 2.1 Cursor Model

**File:** `backend/app/models/json_api.py` (update)

```python
class CursorPageMeta(BaseModel):
    """Cursor pagination metadata."""

    page_size: int = Field(..., alias="pageSize", ge=1, le=1000)
    has_next_page: bool = Field(..., alias="hasNextPage")
    has_previous_page: bool = Field(..., alias="hasPreviousPage")
    start_cursor: Optional[str] = Field(None, alias="startCursor")
    end_cursor: Optional[str] = Field(None, alias="endCursor")

    class Config:
        populate_by_name = True


class CursorMetaObject(BaseModel):
    """JSON:API meta object for cursor pagination."""

    page: CursorPageMeta


class CursorLinksObject(BaseModel):
    """JSON:API links object for cursor pagination."""

    self: str
    first: str
    prev: Optional[str] = None
    next: Optional[str] = None


class JsonApiCursorResponse(BaseModel, Generic[T]):
    """JSON:API response with cursor pagination.

    Used for stable pagination when data changes frequently.
    """

    data: List[T]
    meta: CursorMetaObject
    links: CursorLinksObject
```

#### 2.2 Cursor Pagination Implementation

**File:** `backend/app/routers/phenopackets.py` (add new endpoint or parameter)

```python
import base64
import json
from datetime import datetime


@router.get("/", response_model=JsonApiResponse[PhenopacketDocument])
async def list_phenopackets(
    # ... existing parameters ...

    # Cursor pagination parameters
    page_after: Optional[str] = Query(None, alias="page[after]", description="Cursor for next page"),
    page_before: Optional[str] = Query(None, alias="page[before]", description="Cursor for previous page"),

    # ... rest of implementation ...
):
    """List phenopackets with cursor pagination support.

    **Cursor Pagination:**
    - `page[after]`: Get records after this cursor
    - `page[before]`: Get records before this cursor
    - Cursors are opaque tokens returned in response `meta.page.endCursor`

    **Example:**
    ```
    # First page
    GET /phenopackets?page[size]=20
    → Returns: meta.page.endCursor = "eyJpZCI6MjAsImNyZWF0ZWRfYXQiOiIyMDI1LTAxLTAxVDEyOjAwOjAwWiJ9"

    # Next page
    GET /phenopackets?page[size]=20&page[after]=eyJpZCI6MjAsImNyZWF0ZWRfYXQiOiIyMDI1LTAxLTAxVDEyOjAwOjAwWiJ9
    ```
    """
    # Detect pagination mode
    use_cursor = page_after is not None or page_before is not None

    if use_cursor:
        return await _list_with_cursor_pagination(
            page_after=page_after,
            page_before=page_before,
            page_size=page_size,
            filter_sex=filter_sex,
            filter_has_variants=filter_has_variants,
            sort=sort,
            db=db,
            request=request,
        )
    else:
        # Use offset pagination (existing implementation)
        # ... existing code ...
        pass


async def _list_with_cursor_pagination(
    page_after: Optional[str],
    page_before: Optional[str],
    page_size: int,
    filter_sex: Optional[str],
    filter_has_variants: Optional[bool],
    sort: Optional[str],
    db: AsyncSession,
    request: Request,
) -> JsonApiCursorResponse:
    """Implement cursor-based pagination.

    Cursor format: Base64-encoded JSON with fields used in ORDER BY clause.
    Example cursor: {"id": 20, "created_at": "2025-01-01T12:00:00Z"}
    """
    # Decode cursor if provided
    cursor_data = None
    if page_after:
        cursor_data = decode_cursor(page_after)
        is_forward = True
    elif page_before:
        cursor_data = decode_cursor(page_before)
        is_forward = False
    else:
        is_forward = True

    # Build query
    query = select(Phenopacket)

    # Apply filters
    if filter_sex:
        query = query.where(Phenopacket.subject_sex == filter_sex)
    if filter_has_variants is not None:
        query = query.where(Phenopacket.has_variants == filter_has_variants)

    # Apply cursor condition
    if cursor_data:
        if is_forward:
            # page[after]: created_at > cursor.created_at OR (created_at = cursor.created_at AND id > cursor.id)
            query = query.where(
                or_(
                    Phenopacket.created_at > cursor_data["created_at"],
                    and_(
                        Phenopacket.created_at == cursor_data["created_at"],
                        Phenopacket.id > cursor_data["id"],
                    ),
                )
            )
        else:
            # page[before]: created_at < cursor.created_at OR (created_at = cursor.created_at AND id < cursor.id)
            query = query.where(
                or_(
                    Phenopacket.created_at < cursor_data["created_at"],
                    and_(
                        Phenopacket.created_at == cursor_data["created_at"],
                        Phenopacket.id < cursor_data["id"],
                    ),
                )
            )

    # Apply sorting (cursor pagination requires stable sort)
    if is_forward:
        query = query.order_by(Phenopacket.created_at.asc(), Phenopacket.id.asc())
    else:
        query = query.order_by(Phenopacket.created_at.desc(), Phenopacket.id.desc())

    # Fetch one extra record to check if there's a next page
    query = query.limit(page_size + 1)

    result = await db.execute(query)
    phenopackets = result.scalars().all()

    # Check for next/prev page
    has_more = len(phenopackets) > page_size
    if has_more:
        phenopackets = phenopackets[:page_size]  # Remove extra record

    # Reverse results if page[before] was used
    if not is_forward:
        phenopackets = list(reversed(phenopackets))

    # Generate cursors
    start_cursor = None
    end_cursor = None
    if phenopackets:
        start_cursor = encode_cursor(
            {"id": phenopackets[0].id, "created_at": phenopackets[0].created_at.isoformat()}
        )
        end_cursor = encode_cursor(
            {"id": phenopackets[-1].id, "created_at": phenopackets[-1].created_at.isoformat()}
        )

    # Build metadata
    meta = CursorMetaObject(
        page=CursorPageMeta(
            page_size=page_size,
            has_next_page=has_more if is_forward else (cursor_data is not None),
            has_previous_page=(cursor_data is not None) if is_forward else has_more,
            start_cursor=start_cursor,
            end_cursor=end_cursor,
        )
    )

    # Build links
    links = build_cursor_pagination_links(
        base_url=str(request.url.remove_query_params(["page[after]", "page[before]"])),
        page_size=page_size,
        start_cursor=start_cursor,
        end_cursor=end_cursor,
        has_next=meta.page.has_next_page,
        has_prev=meta.page.has_previous_page,
        filters={"filter[sex]": filter_sex, "filter[has_variants]": filter_has_variants},
        sort=sort,
    )

    return JsonApiCursorResponse(
        data=[p.jsonb for p in phenopackets],
        meta=meta,
        links=links,
    )


def encode_cursor(data: dict) -> str:
    """Encode cursor data to opaque token."""
    json_str = json.dumps(data, separators=(',', ':'))
    return base64.urlsafe_b64encode(json_str.encode()).decode()


def decode_cursor(cursor: str) -> dict:
    """Decode cursor token to data dictionary."""
    try:
        json_str = base64.urlsafe_b64decode(cursor.encode()).decode()
        return json.loads(json_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor format")


def build_cursor_pagination_links(
    base_url: str,
    page_size: int,
    start_cursor: Optional[str],
    end_cursor: Optional[str],
    has_next: bool,
    has_prev: bool,
    filters: dict,
    sort: Optional[str] = None,
) -> CursorLinksObject:
    """Build cursor pagination links."""
    def build_url(cursor_param: Optional[str] = None, cursor_value: Optional[str] = None) -> str:
        params = {"page[size]": page_size}
        if cursor_param and cursor_value:
            params[cursor_param] = cursor_value
        for key, value in filters.items():
            if value is not None:
                params[key] = value
        if sort:
            params["sort"] = sort
        return f"{base_url}?{urlencode(params)}"

    return CursorLinksObject(
        self=build_url(),
        first=build_url(),
        prev=build_url("page[before]", start_cursor) if has_prev else None,
        next=build_url("page[after]", end_cursor) if has_next else None,
    )
```

### Phase 3: Frontend Integration

#### 3.1 Update API Client

**File:** `frontend/src/api/index.js`

```javascript
/**
 * Fetch phenopackets with JSON:API pagination.
 *
 * @param {Object} options - Query options
 * @param {number} [options.pageNumber=1] - Page number (1-indexed)
 * @param {number} [options.pageSize=100] - Items per page
 * @param {string} [options.sex] - Filter by sex
 * @param {boolean} [options.hasVariants] - Filter by variant presence
 * @param {string} [options.sort] - Sort string (e.g., "-created_at,subject_id")
 * @param {string} [options.after] - Cursor for next page
 * @param {string} [options.before] - Cursor for previous page
 * @returns {Promise<JsonApiResponse>} Response with data, meta, links
 */
export const getPhenopackets = async (options = {}) => {
  const {
    pageNumber = 1,
    pageSize = 100,
    sex,
    hasVariants,
    sort,
    after,
    before,
  } = options;

  const params = new URLSearchParams();

  // Pagination (cursor takes precedence over offset)
  if (after) {
    params.append('page[after]', after);
    params.append('page[size]', pageSize);
  } else if (before) {
    params.append('page[before]', before);
    params.append('page[size]', pageSize);
  } else {
    params.append('page[number]', pageNumber);
    params.append('page[size]', pageSize);
  }

  // Filters
  if (sex) params.append('filter[sex]', sex);
  if (hasVariants !== undefined) params.append('filter[has_variants]', hasVariants);

  // Sort
  if (sort) params.append('sort', sort);

  const response = await apiClient.get(`/phenopackets/?${params}`);
  return response.data; // { data, meta, links }
};

/**
 * Legacy function for backwards compatibility.
 * @deprecated Use getPhenopackets() instead
 */
export const getPhenopacketsLegacy = async (skip = 0, limit = 100, filters = {}) => {
  const params = new URLSearchParams({
    skip,
    limit,
    ...filters,
  });

  const response = await apiClient.get(`/phenopackets/?${params}`);
  return response.data; // Still returns List[Phenopacket]
};
```

#### 3.2 Update Phenopackets View

**File:** `frontend/src/views/Phenopackets.vue`

```vue
<template>
  <v-container fluid>
    <v-card>
      <v-card-title>
        <span class="text-h5">Phenopackets</span>
        <v-spacer />
        <!-- Display pagination info -->
        <v-chip v-if="meta" color="primary" variant="outlined">
          {{ meta.page.totalRecords }} total records
        </v-chip>
      </v-card-title>

      <!-- Filters -->
      <v-card-text>
        <v-row>
          <v-col cols="12" md="4">
            <v-select
              v-model="filterSex"
              :items="sexOptions"
              label="Filter by Sex"
              clearable
              @update:modelValue="onFilterChange"
            />
          </v-col>
          <v-col cols="12" md="4">
            <v-select
              v-model="filterHasVariants"
              :items="variantOptions"
              label="Has Variants"
              clearable
              @update:modelValue="onFilterChange"
            />
          </v-col>
          <v-col cols="12" md="4">
            <v-select
              v-model="sortOption"
              :items="sortOptions"
              label="Sort By"
              @update:modelValue="onSortChange"
            />
          </v-col>
        </v-row>
      </v-card-text>

      <!-- Table -->
      <v-data-table-server
        :headers="headers"
        :items="phenopackets"
        :items-length="meta?.page.totalRecords || 0"
        :loading="loading"
        :items-per-page="pageSize"
        :page="currentPage"
        @update:page="onPageChange"
        @update:items-per-page="onPageSizeChange"
      >
        <!-- ... table columns ... -->
      </v-data-table-server>

      <!-- Pagination info -->
      <v-card-actions v-if="meta">
        <v-spacer />
        <span class="text-caption">
          Page {{ meta.page.currentPage }} of {{ meta.page.totalPages }}
          ({{ meta.page.pageSize }} per page)
        </span>
        <v-spacer />
      </v-card-actions>
    </v-card>
  </v-container>
</template>

<script>
export default {
  name: 'Phenopackets',
  data() {
    return {
      phenopackets: [],
      meta: null,
      links: null,
      loading: false,
      currentPage: 1,
      pageSize: 20,
      filterSex: null,
      filterHasVariants: null,
      sortOption: '-created_at',
      sexOptions: [
        { title: 'Male', value: 'MALE' },
        { title: 'Female', value: 'FEMALE' },
        { title: 'Other', value: 'OTHER_SEX' },
        { title: 'Unknown', value: 'UNKNOWN_SEX' },
      ],
      variantOptions: [
        { title: 'Yes', value: true },
        { title: 'No', value: false },
      ],
      sortOptions: [
        { title: 'Newest First', value: '-created_at' },
        { title: 'Oldest First', value: 'created_at' },
        { title: 'Subject ID (A-Z)', value: 'subject_id' },
        { title: 'Subject ID (Z-A)', value: '-subject_id' },
      ],
      headers: [
        { title: 'Subject ID', value: 'subject.id', sortable: false },
        { title: 'Sex', value: 'subject.sex', sortable: false },
        { title: 'Diseases', value: 'diseases', sortable: false },
        { title: 'Phenotypes', value: 'phenotypicFeatures', sortable: false },
        { title: 'Variants', value: 'interpretations', sortable: false },
        { title: 'Actions', value: 'actions', sortable: false },
      ],
    };
  },
  async mounted() {
    await this.loadPhenopackets();
  },
  methods: {
    async loadPhenopackets() {
      this.loading = true;
      try {
        const response = await this.$api.getPhenopackets({
          pageNumber: this.currentPage,
          pageSize: this.pageSize,
          sex: this.filterSex,
          hasVariants: this.filterHasVariants,
          sort: this.sortOption,
        });

        this.phenopackets = response.data;
        this.meta = response.meta;
        this.links = response.links;
      } catch (error) {
        console.error('Failed to load phenopackets:', error);
        this.$toast.error('Failed to load phenopackets');
      } finally {
        this.loading = false;
      }
    },
    async onPageChange(newPage) {
      this.currentPage = newPage;
      await this.loadPhenopackets();
    },
    async onPageSizeChange(newSize) {
      this.pageSize = newSize;
      this.currentPage = 1; // Reset to first page
      await this.loadPhenopackets();
    },
    async onFilterChange() {
      this.currentPage = 1; // Reset to first page when filters change
      await this.loadPhenopackets();
    },
    async onSortChange() {
      this.currentPage = 1; // Reset to first page when sort changes
      await this.loadPhenopackets();
    },
  },
};
</script>
```

### Phase 4: Backwards Compatibility & Migration

#### 4.1 Deprecation Strategy

**Timeline:**
1. **v2.1.0** (Current Release) - Add JSON:API support, keep legacy parameters
2. **v2.2.0** (3 months) - Deprecation warnings in API documentation
3. **v2.3.0** (6 months) - Deprecation warnings in API responses (X-Deprecation header)
4. **v3.0.0** (12 months) - Remove legacy `skip`/`limit` parameters

**Deprecation Header:**
```python
@router.get("/")
async def list_phenopackets(...):
    response = JsonApiResponse(...)

    # Add deprecation warning if legacy parameters used
    if skip is not None or limit is not None:
        response.headers["X-Deprecation"] = (
            "skip and limit parameters are deprecated. "
            "Use page[number] and page[size] instead. "
            "Legacy parameters will be removed in v3.0.0."
        )

    return response
```

#### 4.2 Migration Guide for Frontend

**File:** `frontend/MIGRATION-JSON-API.md` (new file)

```markdown
# Migration Guide: JSON:API Pagination

## Before (v2.0 - Legacy)

```javascript
// Old API client
const response = await this.$api.getPhenopacketsLegacy(0, 20, { sex: 'MALE' });
const phenopackets = response; // List[Phenopacket]

// Problems:
// - No total count (cannot show "Page X of Y")
// - No pagination links
// - Custom filter parameters
```

## After (v2.1+ - JSON:API)

```javascript
// New API client
const response = await this.$api.getPhenopackets({
  pageNumber: 1,
  pageSize: 20,
  sex: 'MALE',
});

const phenopackets = response.data; // List[Phenopacket]
const totalPages = response.meta.page.totalPages; // 44
const totalRecords = response.meta.page.totalRecords; // 864

// Benefits:
// - Pagination metadata available
// - Standard JSON:API conventions
// - Links to next/prev/first/last pages
```

## Migration Checklist

- [ ] Update `getPhenopackets()` calls to use `pageNumber` instead of `skip`
- [ ] Update `getPhenopackets()` calls to use `pageSize` instead of `limit`
- [ ] Update filter parameters to use `filter[field]` format (handled by API client)
- [ ] Update views to display `meta.page` information
- [ ] Update pagination controls to use `links.next`/`links.prev`
- [ ] Add sort controls using `sort` parameter
- [ ] Test backwards compatibility (legacy calls should still work)
```

### Phase 5: Testing & Validation

#### 5.1 Unit Tests

**File:** `backend/tests/test_json_api_pagination.py` (new file)

```python
"""Tests for JSON:API pagination implementation."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_offset_pagination_first_page(client: AsyncClient):
    """Test first page with offset pagination."""
    response = await client.get("/api/v2/phenopackets/?page[number]=1&page[size]=20")

    assert response.status_code == 200
    data = response.json()

    # Check response structure
    assert "data" in data
    assert "meta" in data
    assert "links" in data

    # Check metadata
    assert data["meta"]["page"]["currentPage"] == 1
    assert data["meta"]["page"]["pageSize"] == 20
    assert data["meta"]["page"]["totalPages"] > 0
    assert data["meta"]["page"]["totalRecords"] == 864

    # Check links
    assert data["links"]["self"] is not None
    assert data["links"]["first"] is not None
    assert data["links"]["prev"] is None  # First page has no prev
    assert data["links"]["next"] is not None
    assert data["links"]["last"] is not None

    # Check data
    assert len(data["data"]) == 20


@pytest.mark.asyncio
async def test_offset_pagination_last_page(client: AsyncClient):
    """Test last page with offset pagination."""
    response = await client.get("/api/v2/phenopackets/?page[number]=1&page[size]=20")
    total_pages = response.json()["meta"]["page"]["totalPages"]

    response = await client.get(f"/api/v2/phenopackets/?page[number]={total_pages}&page[size]=20")

    assert response.status_code == 200
    data = response.json()

    # Last page should have no next link
    assert data["links"]["next"] is None
    assert data["links"]["prev"] is not None


@pytest.mark.asyncio
async def test_filtering(client: AsyncClient):
    """Test filtering with pagination."""
    response = await client.get(
        "/api/v2/phenopackets/?page[number]=1&page[size]=20&filter[sex]=MALE"
    )

    assert response.status_code == 200
    data = response.json()

    # All returned phenopackets should have sex=MALE
    for phenopacket in data["data"]:
        assert phenopacket["subject"]["sex"] == "MALE"

    # Total records should be less than 864
    assert data["meta"]["page"]["totalRecords"] < 864


@pytest.mark.asyncio
async def test_sorting(client: AsyncClient):
    """Test sorting with pagination."""
    response = await client.get(
        "/api/v2/phenopackets/?page[number]=1&page[size]=20&sort=subject_id"
    )

    assert response.status_code == 200
    data = response.json()

    # Check subject IDs are in ascending order
    subject_ids = [p["subject"]["id"] for p in data["data"]]
    assert subject_ids == sorted(subject_ids)


@pytest.mark.asyncio
async def test_invalid_sort_field(client: AsyncClient):
    """Test error handling for invalid sort field."""
    response = await client.get("/api/v2/phenopackets/?sort=invalid_field")

    assert response.status_code == 400
    assert "Invalid sort field" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cursor_pagination(client: AsyncClient):
    """Test cursor-based pagination."""
    # Get first page
    response1 = await client.get("/api/v2/phenopackets/?page[size]=20")
    data1 = response1.json()

    assert data1["meta"]["page"]["hasNextPage"] is True
    end_cursor = data1["meta"]["page"]["endCursor"]

    # Get next page using cursor
    response2 = await client.get(f"/api/v2/phenopackets/?page[size]=20&page[after]={end_cursor}")
    data2 = response2.json()

    # Records should not overlap
    ids1 = {p["id"] for p in data1["data"]}
    ids2 = {p["id"] for p in data2["data"]}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_backwards_compatibility(client: AsyncClient):
    """Test legacy skip/limit parameters still work."""
    response = await client.get("/api/v2/phenopackets/?skip=0&limit=20&sex=MALE")

    assert response.status_code == 200
    data = response.json()

    # Should return JSON:API format even with legacy params
    assert "data" in data
    assert "meta" in data
    assert len(data["data"]) == 20

    # Should have deprecation warning
    assert "X-Deprecation" in response.headers
```

#### 5.2 Integration Tests

**File:** `backend/tests/test_json_api_integration.py` (new file)

```python
"""Integration tests for JSON:API pagination."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_paginate_through_all_records(client: AsyncClient):
    """Test paginating through all phenopackets."""
    page = 1
    page_size = 50
    all_ids = set()

    while True:
        response = await client.get(
            f"/api/v2/phenopackets/?page[number]={page}&page[size]={page_size}"
        )
        data = response.json()

        # Collect IDs
        for phenopacket in data["data"]:
            phenopacket_id = phenopacket["id"]
            assert phenopacket_id not in all_ids, "Duplicate phenopacket ID found"
            all_ids.add(phenopacket_id)

        # Check if we're done
        if not data["links"]["next"]:
            break

        page += 1

    # Should have collected all 864 records
    assert len(all_ids) == 864


@pytest.mark.asyncio
async def test_follow_pagination_links(client: AsyncClient):
    """Test following pagination links."""
    # Get first page
    response = await client.get("/api/v2/phenopackets/?page[number]=1&page[size]=20")
    data = response.json()

    # Follow next link
    next_url = data["links"]["next"]
    response = await client.get(next_url)

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["page"]["currentPage"] == 2


@pytest.mark.asyncio
async def test_data_consistency_with_filters(client: AsyncClient):
    """Test that filtering doesn't break pagination."""
    # Count total MALE phenopackets
    response = await client.get(
        "/api/v2/phenopackets/?page[number]=1&page[size]=1000&filter[sex]=MALE"
    )
    total_records = response.json()["meta"]["page"]["totalRecords"]

    # Paginate with smaller page size
    collected = 0
    page = 1
    while True:
        response = await client.get(
            f"/api/v2/phenopackets/?page[number]={page}&page[size]=20&filter[sex]=MALE"
        )
        data = response.json()
        collected += len(data["data"])

        if not data["links"]["next"]:
            break
        page += 1

    # Should collect same number of records
    assert collected == total_records
```

## Implementation Checklist

### Phase 1: Response Envelope (Offset Pagination)
- [ ] Create `backend/app/models/json_api.py` with response models
- [ ] Update `backend/app/routers/phenopackets.py` with JSON:API parameters
- [ ] Implement `parse_sort_parameter()` function
- [ ] Implement `build_pagination_links()` function
- [ ] Add backwards compatibility for `skip`/`limit` (deprecated)
- [ ] Test offset pagination manually (Swagger UI)

### Phase 2: Cursor Pagination
- [ ] Add cursor models to `json_api.py`
- [ ] Implement `encode_cursor()` and `decode_cursor()` functions
- [ ] Implement `_list_with_cursor_pagination()` function
- [ ] Implement `build_cursor_pagination_links()` function
- [ ] Test cursor pagination manually (Swagger UI)
- [ ] Verify no duplicate/missing records when data changes

### Phase 3: Frontend Integration
- [ ] Update `frontend/src/api/index.js` with `getPhenopackets()` function
- [ ] Update `frontend/src/views/Phenopackets.vue` to use JSON:API response
- [ ] Display pagination metadata (Page X of Y, total records)
- [ ] Implement sort dropdown
- [ ] Test frontend pagination controls
- [ ] Verify filter + sort + pagination work together

### Phase 4: Backwards Compatibility
- [ ] Add deprecation warnings for legacy parameters
- [ ] Add `X-Deprecation` header when legacy params used
- [ ] Create `frontend/MIGRATION-JSON-API.md` migration guide
- [ ] Update API documentation (OpenAPI/Swagger)
- [ ] Announce deprecation timeline in changelog

### Phase 5: Testing & Validation
- [ ] Write unit tests for offset pagination
- [ ] Write unit tests for cursor pagination
- [ ] Write unit tests for filtering and sorting
- [ ] Write integration tests for full pagination workflows
- [ ] Test backwards compatibility with legacy parameters
- [ ] Manual testing in browser (network tab, UI behavior)
- [ ] Load testing with 10,000+ records (performance validation)

### Phase 6: Documentation & Deployment
- [ ] Update OpenAPI schema with JSON:API examples
- [ ] Update `backend/CLAUDE.md` with JSON:API conventions
- [ ] Update `frontend/CLAUDE.md` with pagination examples
- [ ] Create ADR (Architecture Decision Record) for JSON:API adoption
- [ ] Deploy to staging environment
- [ ] Smoke test on staging (verify pagination works)
- [ ] Deploy to production

## Testing Verification

### Manual Testing Checklist

**Offset Pagination:**
- [ ] Visit `/phenopackets?page[number]=1&page[size]=20` in browser
- [ ] Verify response has `data`, `meta`, `links` structure
- [ ] Check `meta.page.totalRecords` equals 864
- [ ] Check `meta.page.totalPages` equals 44
- [ ] Click "Next" button and verify URL updates to `page[number]=2`
- [ ] Navigate to last page and verify "Next" button disabled
- [ ] Navigate to first page and verify "Prev" button disabled

**Filtering:**
- [ ] Filter by sex=MALE and verify total records changes
- [ ] Verify all returned phenopackets have sex=MALE
- [ ] Combine sex=MALE and has_variants=true filters
- [ ] Verify pagination works with filters applied

**Sorting:**
- [ ] Sort by newest first (`sort=-created_at`)
- [ ] Verify records are in descending created_at order
- [ ] Sort by subject ID A-Z (`sort=subject_id`)
- [ ] Verify records are alphabetically sorted
- [ ] Combine sorting with filters and pagination

**Cursor Pagination:**
- [ ] Get first page and copy `meta.page.endCursor`
- [ ] Use cursor in `page[after]=<cursor>` parameter
- [ ] Verify second page has different records (no overlap)
- [ ] Use `page[before]=<cursor>` to go backwards
- [ ] Verify cursor pagination is stable (delete record and re-paginate)

**Backwards Compatibility:**
- [ ] Use legacy `skip=0&limit=20` parameters
- [ ] Verify JSON:API response returned
- [ ] Check for `X-Deprecation` header in response
- [ ] Verify frontend still works with legacy API client

**Performance:**
- [ ] Measure query time with `page[number]=1&page[size]=100`
- [ ] Verify query time < 200ms
- [ ] Test with 1000 records per page (max limit)
- [ ] Verify no N+1 query issues (check SQL logs)

## Acceptance Criteria

- [ ] **Offset pagination works**: `page[number]` and `page[size]` parameters function correctly
- [ ] **Cursor pagination works**: `page[after]` and `page[before]` parameters function correctly
- [ ] **Response format correct**: JSON:API structure with `data`, `meta`, `links`
- [ ] **Metadata accurate**: `totalRecords`, `totalPages`, `currentPage` match database
- [ ] **Links functional**: `first`, `prev`, `next`, `last` links navigate correctly
- [ ] **Filtering works**: `filter[sex]`, `filter[has_variants]` apply correctly
- [ ] **Sorting works**: `sort` parameter orders results correctly
- [ ] **Backwards compatible**: Legacy `skip`/`limit` parameters still work (deprecated)
- [ ] **Frontend updated**: Phenopackets view displays pagination metadata
- [ ] **Tests pass**: All unit and integration tests pass
- [ ] **Performance acceptable**: Queries complete in <200ms
- [ ] **Documentation complete**: API docs, migration guide, ADR created

## Files Modified/Created

### Backend Files

**New Files:**
- `backend/app/models/json_api.py` (~200 lines) - JSON:API response models
- `backend/tests/test_json_api_pagination.py` (~300 lines) - Unit tests
- `backend/tests/test_json_api_integration.py` (~150 lines) - Integration tests

**Modified Files:**
- `backend/app/routers/phenopackets.py` (~500 lines added) - Pagination implementation
- `backend/app/main.py` (1 line) - Import json_api models

### Frontend Files

**Modified Files:**
- `frontend/src/api/index.js` (~50 lines added) - New `getPhenopackets()` function
- `frontend/src/views/Phenopackets.vue` (~100 lines modified) - JSON:API integration

**New Files:**
- `frontend/MIGRATION-JSON-API.md` (~100 lines) - Migration guide

### Documentation Files

**New Files:**
- `docs/adr/001-json-api-pagination.md` (~200 lines) - Architecture Decision Record

**Modified Files:**
- `backend/CLAUDE.md` (~50 lines added) - JSON:API conventions
- `frontend/CLAUDE.md` (~50 lines added) - Pagination examples
- `CHANGELOG.md` (~20 lines added) - v2.1.0 release notes

**Total:** ~1,720 lines of code/documentation

## Dependencies

**Blocking Issues:**
- None (independent feature)

**Related Issues:**
- Issue #64 (variant search) - Will also need JSON:API pagination
- Issue #66 (frontend search UI) - Will use JSON:API conventions
- Issue #34 (variants view) - Will benefit from pagination metadata

**Future Issues:**
- JSON:API pagination for `/aggregate/*` endpoints
- JSON:API pagination for `/clinical/*` endpoints
- JSON:API pagination for publications, variants, etc.

## Performance Impact

**Before (No Metadata):**
- Query time: ~100ms (SELECT + OFFSET/LIMIT)
- Response size: ~50KB (20 phenopackets)
- Frontend: Cannot show "Page X of Y" (UX degraded)

**After (With Metadata):**
- Query time: ~150ms (SELECT + OFFSET/LIMIT + COUNT)
- Response size: ~51KB (20 phenopackets + metadata)
- Frontend: Can show "Page 1 of 44" (better UX)

**Cursor Pagination:**
- Query time: ~120ms (SELECT + WHERE cursor condition + LIMIT)
- No COUNT query needed (faster than offset)
- Stable pagination (no duplicate/missing records)

**Optimization:** Add database index on `(created_at, id)` for cursor pagination:
```sql
CREATE INDEX CONCURRENTLY idx_phenopackets_cursor
ON phenopackets (created_at ASC, id ASC);
```

## Timeline Estimate

- **Phase 1** (Response Envelope): 6 hours
- **Phase 2** (Cursor Pagination): 8 hours
- **Phase 3** (Frontend Integration): 4 hours
- **Phase 4** (Backwards Compatibility): 2 hours
- **Phase 5** (Testing): 6 hours
- **Phase 6** (Documentation): 4 hours

**Total:** ~30 hours (~4 days)

## Priority & Labels

**Priority:** P1 (High)

**Reason:** Without pagination metadata, frontend cannot display "Page X of Y" or intelligently disable navigation buttons. This is a critical UX issue affecting usability.

**Labels:** `backend`, `api`, `pagination`, `json-api`, `p1`, `enhancement`

## Security & Compliance

**Security Considerations:**
- Cursor tokens are base64-encoded (not encrypted) - Do not include sensitive data
- Sorting must validate field names to prevent SQL injection
- Limit page size to 1000 to prevent DoS attacks
- Rate limiting recommended (10 req/min per IP)

**GDPR Compliance:**
- Pagination does not expose additional data
- Cursor tokens contain only `id` and `created_at` (non-sensitive)
- Audit logging not required (read-only operation)

**Performance:**
- Add `(created_at, id)` index for cursor pagination
- COUNT queries cached for 60 seconds (optional optimization)
- Consider materialized view for aggregated counts

## References

- [JSON:API v1.1 Specification](https://jsonapi.org/format/1.1/)
- [Pagination Design Patterns](https://www.moesif.com/blog/technical/api-design/REST-API-Design-Filtering-Sorting-and-Pagination/)
- [Cursor vs Offset Pagination](https://slack.engineering/evolving-api-pagination-at-slack/)
- [GA4GH Phenopackets v2](https://phenopacket-schema.readthedocs.io/en/latest/)
