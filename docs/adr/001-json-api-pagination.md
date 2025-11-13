# ADR 001: Adopt JSON:API v1.1 Pagination with Cursor Support

**Date:** 2025-11-10
**Status:** Accepted
**Deciders:** Development Team
**Related Issue:** #62

## Context and Problem Statement

The HNF1B Database API serves phenopacket data through the `/api/v2/phenopackets/` endpoint. The original implementation used custom `skip`/`limit` parameters and returned a plain array of phenopackets without pagination metadata. This created several UX problems:

1. **No pagination metadata**: Frontend cannot display "Page X of Y" or total record counts
2. **Non-standard parameters**: Custom `skip`/`limit` instead of industry-standard conventions
3. **Unstable pagination**: Offset-based pagination breaks when data changes during browsing
4. **No sorting control**: Users cannot reorder results by date, subject ID, etc.

### Example of the Problem

When using offset pagination, if records are inserted or deleted while a user browses:

```
Page 1: Records 1-20
[Admin deletes 10 records from page 1]
Page 2: Records 31-50 (user expected 21-40)
Result: User misses records 21-30
```

## Decision Drivers

* **User Experience**: Need to display "Page 1 of 44" and "864 total records"
* **API Standards**: Industry adoption of JSON:API conventions
* **Data Stability**: Prevent duplicate/missing records during pagination
* **Developer Experience**: Familiar patterns for API consumers
* **Performance**: Efficient queries for large datasets
* **Backwards Compatibility**: Don't break existing API clients

## Considered Options

### Option 1: Keep Custom Pagination

**Pros:**
- No changes required
- Existing clients work

**Cons:**
- No metadata for frontend
- Non-standard approach
- Unstable results when data changes
- Poor developer experience

### Option 2: Add Simple Metadata Only

Add `total_count` to response but keep custom parameters:

```json
{
  "data": [...],
  "total_count": 864
}
```

**Pros:**
- Minimal changes
- Provides basic metadata

**Cons:**
- Still non-standard
- No navigation links
- No cursor pagination
- Incomplete solution

### Option 3: Adopt JSON:API v1.1 (Selected)

Implement full JSON:API v1.1 pagination with both offset and cursor modes:

```json
{
  "data": [...],
  "meta": {
    "page": {
      "currentPage": 1,
      "pageSize": 20,
      "totalPages": 44,
      "totalRecords": 864
    }
  },
  "links": {
    "self": "...",
    "first": "...",
    "prev": null,
    "next": "...",
    "last": "..."
  }
}
```

**Pros:**
- Industry standard (JSON:API v1.1)
- Complete pagination metadata
- Navigation links included
- Cursor pagination for stability
- Filtering and sorting support
- Better developer experience
- Maintains backwards compatibility

**Cons:**
- More implementation work
- Response size slightly larger (~1KB)
- COUNT query adds ~50ms latency (offset mode only)

## Decision Outcome

**Chosen option:** "Option 3: Adopt JSON:API v1.1"

### Rationale

JSON:API v1.1 is the de facto standard for RESTful API pagination and provides:

1. **Complete metadata**: `totalRecords`, `totalPages`, `currentPage`, `pageSize`
2. **Navigation links**: `first`, `prev`, `next`, `last` for easy traversal
3. **Two pagination modes**: Offset (with page numbers) and cursor (stable results)
4. **Standard conventions**: Developers familiar with JSON:API understand immediately
5. **Filtering and sorting**: `filter[field]=value` and `sort=-field` patterns
6. **Backwards compatibility**: Legacy `skip`/`limit` parameters still work (deprecated)

### Implementation Details

**Pagination Modes:**

1. **Offset Pagination** (`page[number]`, `page[size]`)
   - Use case: Displaying page numbers ("Page 2 of 44")
   - Algorithm: `SELECT ... OFFSET (page-1)*size LIMIT size`
   - Performance: O(n) with COUNT query (~150ms)
   - Provides: `totalRecords`, `totalPages`, `currentPage`

2. **Cursor Pagination** (`page[after]`, `page[before]`)
   - Use case: Infinite scroll, frequently changing data
   - Algorithm: `SELECT ... WHERE (created_at, id) > cursor LIMIT size`
   - Performance: O(log n) with B-tree index (~120ms)
   - Provides: `hasNextPage`, `hasPreviousPage`, cursors
   - Stability: Immune to insertions/deletions during browsing

**Database Optimization:**

Added composite B-tree index for cursor pagination:

```sql
CREATE INDEX idx_phenopackets_cursor_pagination
ON phenopackets (created_at DESC, id DESC);
```

This enables efficient cursor queries using range scans instead of full table scans.

**Query Parameters:**

```
# Offset pagination
page[number]=1          # Page number (1-indexed)
page[size]=20           # Items per page (max: 1000)

# Cursor pagination
page[after]=<token>     # Next page cursor
page[before]=<token>    # Previous page cursor
page[size]=20           # Items per page

# Filtering
filter[sex]=MALE        # Filter by subject sex
filter[has_variants]=true  # Filter by variant presence

# Sorting
sort=-created_at        # Sort by created date (descending)
sort=subject_id         # Sort by subject ID (ascending)
sort=-created_at,subject_id  # Multiple fields
```

**Response Structure:**

```json
{
  "data": [...],          // Array of phenopackets
  "meta": {               // Pagination metadata
    "page": {
      // Offset mode
      "currentPage": 1,
      "pageSize": 20,
      "totalPages": 44,
      "totalRecords": 864,
      // OR cursor mode
      "pageSize": 20,
      "hasNextPage": true,
      "hasPreviousPage": false,
      "startCursor": "eyJpZCI6...",
      "endCursor": "eyJpZCI6..."
    }
  },
  "links": {              // Navigation links
    "self": "/api/v2/phenopackets/?page[number]=1&page[size]=20",
    "first": "/api/v2/phenopackets/?page[number]=1&page[size]=20",
    "prev": null,
    "next": "/api/v2/phenopackets/?page[number]=2&page[size]=20",
    "last": "/api/v2/phenopackets/?page[number]=44&page[size]=20"
  }
}
```

### Backwards Compatibility

Legacy `skip`/`limit` parameters continue to work:

```bash
# Legacy call (deprecated but functional)
GET /api/v2/phenopackets/?skip=20&limit=10

# Automatically converted to:
GET /api/v2/phenopackets/?page[number]=3&page[size]=10

# Returns JSON:API response format
```

Legacy parameters are marked as deprecated in OpenAPI schema and will be removed in v3.0.0 (12+ months).

### Frontend Integration

Vue.js components updated to use JSON:API format:

```javascript
// API client
const response = await getPhenopackets({
  pageNumber: 1,
  pageSize: 20,
  sex: 'MALE',
  sort: '-created_at'
});

// Extract data and metadata
const phenopackets = response.data;
const totalPages = response.meta.page.totalPages;
const currentPage = response.meta.page.currentPage;

// Use navigation links
const nextPageUrl = response.links.next;
```

### Performance Impact

**Before (No Metadata):**
- Query time: ~100ms (SELECT + OFFSET/LIMIT)
- Response size: ~50KB (20 phenopackets)
- Frontend: Cannot show page numbers

**After (Offset Mode):**
- Query time: ~150ms (SELECT + OFFSET/LIMIT + COUNT)
- Response size: ~51KB (20 phenopackets + metadata)
- Frontend: Shows "Page 1 of 44"
- Trade-off: +50ms for COUNT query, but much better UX

**After (Cursor Mode):**
- Query time: ~120ms (SELECT + WHERE cursor + LIMIT)
- Response size: ~51KB (20 phenopackets + metadata)
- Frontend: Shows "Next/Prev" buttons
- Benefit: No COUNT query, faster than offset, stable results

## Positive Consequences

* ✅ **Better UX**: Frontend displays "Page X of Y" and total record counts
* ✅ **Standard API**: Developers recognize JSON:API conventions immediately
* ✅ **Stable Pagination**: Cursor mode prevents duplicate/missing records
* ✅ **Navigation Links**: Frontend can use `links.next` without building URLs
* ✅ **Flexible Sorting**: Users can reorder by date, subject ID, sex
* ✅ **Backwards Compatible**: Existing clients continue working
* ✅ **Performance Optimized**: Database index for cursor queries
* ✅ **Type Safe**: Pydantic models with Pydantic v2 ConfigDict

## Negative Consequences

* ⚠️ **Slightly Larger Responses**: +1KB overhead for metadata/links
* ⚠️ **COUNT Query Latency**: +50ms for offset pagination (acceptable trade-off)
* ⚠️ **Migration Effort**: Frontend components need updates
* ⚠️ **Learning Curve**: Developers must understand cursor vs offset pagination

## Compliance and Validation

* ✅ **39 tests passing**: Comprehensive test suite for both pagination modes
* ✅ **OpenAPI schema**: Auto-generated documentation with examples
* ✅ **Ruff linting**: All code quality checks passing
* ✅ **Mypy type checking**: Full type safety with Pydantic v2
* ✅ **Manual testing**: Verified with browser and MCP Playwright

## References

* [JSON:API v1.1 Specification](https://jsonapi.org/format/1.1/)
* [Pagination Design Patterns](https://www.moesif.com/blog/technical/api-design/REST-API-Design-Filtering-Sorting-and-Pagination/)
* [Cursor vs Offset Pagination (Slack Engineering)](https://slack.engineering/evolving-api-pagination-at-slack/)
* [GA4GH Phenopackets v2](https://phenopacket-schema.readthedocs.io/)
* [Issue #62: JSON:API Pagination Implementation](../issues/issue-62-json-api-pagination.md)

## Related Decisions

* Future ADR: Extend JSON:API pagination to aggregation endpoints
* Future ADR: Extend JSON:API pagination to clinical endpoints
* Future ADR: Implement JSON:API sparse fieldsets

## Changelog

* **2025-11-10**: Initial ADR created
* **2025-11-10**: Implementation completed (Phases 1-3)
* **2025-11-10**: Database index added for cursor pagination
* **2025-11-10**: Type safety improvements (Pydantic v2 migration)
* **2025-11-10**: Status changed to "Accepted" (all tests passing)
