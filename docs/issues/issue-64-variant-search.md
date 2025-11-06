# Issue #64: feat(backend): add variant search API endpoint with security

⚠️ **SECURITY WARNING**: This issue implements database search functionality. All input validation, SQL injection prevention, and rate limiting MUST be implemented before production deployment.

## Overview

Add secure backend API endpoint for variant search across all phenopackets with multiple filter criteria.

**Current:** No search endpoint exists - variants must be manually filtered client-side
**Target:** RESTful search endpoint with parameterized queries, HGVS validation, rate limiting, and audit logging

**Related Issues:**
- Issue #66 (frontend search UI) - Depends on this issue
- Issue #57 (variant deduplication) - ⚠️ **BLOCKER** - Must resolve duplicate variants before search is accurate

## Why This Matters

With 864 phenopackets potentially containing hundreds of unique variants, users need efficient ways to find specific variants of interest:

- **Clinicians:** Search by HGVS notation to find a specific patient variant
- **Researchers:** Filter by pathogenicity class to study P/LP variants
- **Geneticists:** Search by chromosome/position for specific regions

### Security Context

**Why Security Matters:**
- Search endpoints are common SQL injection targets
- User-provided HGVS notation must be validated
- Unrestricted search can enable DoS attacks
- GDPR compliance requires audit logging of data access

### Current State (Without Search)

```
User wants to find: c.1654-2A>T variant
Current workflow:
1. Fetch ALL variants via /aggregate/variants endpoint
2. Client-side filtering with JavaScript
3. Performance degrades with >100 variants
4. No audit trail of searches
⏱️ Time: 5-10 seconds for full table load
```

### Target State (With Secure Search)

```
User wants to find: c.1654-2A>T variant
New workflow:
1. POST /aggregate/variants/search with validated query
2. Backend filters with parameterized SQL
3. Returns only matching variants
4. Search logged for audit compliance
⏱️ Time: <200ms backend query
```

## Required Changes

**Scope:** This issue covers BACKEND implementation only. Frontend UI will be tracked in Issue #66.

### 1. Input Validation & Security Layer

**File:** `backend/app/phenopackets/validation.py` (new file)

Create validation functions for search inputs:

```python
"""Input validation for variant search endpoint."""

import re
from typing import Optional
from fastapi import HTTPException

# HGVS validation patterns (simplified - consider using hgvs library for production)
HGVS_PATTERNS = {
    "c": re.compile(r"^c\.[0-9]+[ACGT]>[ACGT]$|^c\.[0-9]+[-+][0-9]+[ACGT]>[ACGT]$"),  # c.1654-2A>T
    "p": re.compile(r"^p\.\([A-Z][a-z]{2}[0-9]+[A-Z][a-z]{2}\)$"),  # p.(Ser546Phe)
    "g": re.compile(r"^g\.[0-9]+[ACGT]>[ACGT]$"),  # g.36098063A>T
}

ALLOWED_VARIANT_TYPES = {"SNV", "deletion", "duplication", "insertion", "inversion", "CNV"}
ALLOWED_CLASSIFICATIONS = {
    "PATHOGENIC",
    "LIKELY_PATHOGENIC",
    "UNCERTAIN_SIGNIFICANCE",
    "LIKELY_BENIGN",
    "BENIGN",
}
ALLOWED_GENES = {"HNF1B"}  # Expand as needed


def validate_hgvs_notation(query: str) -> bool:
    """Validate HGVS notation format.

    Args:
        query: User-provided HGVS string

    Returns:
        True if valid HGVS format, False otherwise

    Note: For production, use `hgvs` library for comprehensive validation:
        from hgvs.parser import Parser
        parser = Parser()
        try:
            parser.parse(query)
            return True
        except Exception:
            return False
    """
    for pattern in HGVS_PATTERNS.values():
        if pattern.match(query):
            return True
    return False


def validate_search_query(query: Optional[str]) -> Optional[str]:
    """Validate and sanitize search query input.

    Args:
        query: User-provided search string

    Returns:
        Sanitized query string or None

    Raises:
        HTTPException: If query contains invalid characters or is too long
    """
    if not query:
        return None

    # Length validation (prevent DoS)
    if len(query) > 100:
        raise HTTPException(status_code=400, detail="Search query too long (max 100 chars)")

    # Character whitelist (alphanumeric + HGVS symbols)
    if not re.match(r"^[A-Za-z0-9._:>()+-]+$", query):
        raise HTTPException(
            status_code=400,
            detail="Search query contains invalid characters. Allowed: A-Z a-z 0-9 . _ : > ( ) + -"
        )

    # Optional: Validate HGVS format if it looks like HGVS
    if query.startswith(("c.", "p.", "g.")) and not validate_hgvs_notation(query):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid HGVS notation format: {query}"
        )

    return query.strip()


def validate_variant_type(variant_type: Optional[str]) -> Optional[str]:
    """Validate variant type filter."""
    if not variant_type:
        return None

    if variant_type not in ALLOWED_VARIANT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid variant type: {variant_type}. Allowed: {', '.join(ALLOWED_VARIANT_TYPES)}"
        )

    return variant_type


def validate_classification(classification: Optional[str]) -> Optional[str]:
    """Validate ACMG classification filter."""
    if not classification:
        return None

    if classification not in ALLOWED_CLASSIFICATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid classification: {classification}. Allowed: {', '.join(ALLOWED_CLASSIFICATIONS)}"
        )

    return classification


def validate_gene(gene: Optional[str]) -> Optional[str]:
    """Validate gene symbol filter."""
    if not gene:
        return None

    if gene not in ALLOWED_GENES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid gene symbol: {gene}. Allowed: {', '.join(ALLOWED_GENES)}"
        )

    return gene
```

### 2. Rate Limiting Middleware

**File:** `backend/app/middleware/rate_limiter.py` (new file)

```python
"""Rate limiting middleware for search endpoints."""

from fastapi import HTTPException, Request
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple

# In-memory rate limiter (for production, use Redis)
REQUEST_COUNTS: Dict[str, list] = defaultdict(list)
RATE_LIMIT = 10  # requests
RATE_WINDOW = 60  # seconds


def check_rate_limit(request: Request) -> None:
    """Check if client has exceeded rate limit.

    Args:
        request: FastAPI request object

    Raises:
        HTTPException: If rate limit exceeded
    """
    client_ip = request.client.host
    now = datetime.now()
    window_start = now - timedelta(seconds=RATE_WINDOW)

    # Clean old requests
    REQUEST_COUNTS[client_ip] = [
        req_time for req_time in REQUEST_COUNTS[client_ip]
        if req_time > window_start
    ]

    # Check rate limit
    if len(REQUEST_COUNTS[client_ip]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT} requests per {RATE_WINDOW} seconds."
        )

    # Record this request
    REQUEST_COUNTS[client_ip].append(now)
```

### 3. Audit Logging

**File:** `backend/app/utils/audit_logger.py` (new file)

```python
"""Audit logging for search queries (GDPR compliance)."""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("audit")


def log_search_query(
    user_id: Optional[str],
    client_ip: str,
    query: Optional[str],
    variant_type: Optional[str],
    classification: Optional[str],
    gene: Optional[str],
    result_count: int,
) -> None:
    """Log search query for audit trail.

    Args:
        user_id: Authenticated user ID (if available)
        client_ip: Client IP address
        query: Search query text
        variant_type: Variant type filter
        classification: Classification filter
        gene: Gene filter
        result_count: Number of results returned
    """
    logger.info(
        "VARIANT_SEARCH",
        extra={
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id or "anonymous",
            "client_ip": client_ip,
            "query": query,
            "filters": {
                "type": variant_type,
                "classification": classification,
                "gene": gene,
            },
            "result_count": result_count,
        }
    )
```

### 4. Backend Search Endpoint (Secure)

**File:** `backend/app/phenopackets/endpoints.py` (add new endpoint)

```python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, Request
from typing import Dict, Optional

from app.phenopackets.validation import (
    validate_search_query,
    validate_variant_type,
    validate_classification,
    validate_gene,
)
from app.middleware.rate_limiter import check_rate_limit
from app.utils.audit_logger import log_search_query


@router.get("/aggregate/variants/search", response_model=Dict)
async def search_variants(
    request: Request,
    query: Optional[str] = None,
    type: Optional[str] = None,
    classification: Optional[str] = None,
    gene: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional),  # Optional auth
):
    """
    Search variants across all phenopackets with multiple filter criteria.

    Security Features:
    - Input validation and sanitization
    - Parameterized queries (SQL injection prevention)
    - Rate limiting (10 req/min per IP)
    - Audit logging for GDPR compliance

    Parameters:
    - query: Text search in HGVS notations, variant ID, or label
    - type: Filter by structural type (SNV, deletion, etc.)
    - classification: Filter by ACMG classification
    - gene: Filter by gene symbol
    - skip, limit: Pagination

    Returns:
    - data: List of matching variants
    - total: Filtered count
    - total_unfiltered: Total variants without filters
    """
    # Rate limiting
    check_rate_limit(request)

    # Input validation
    validated_query = validate_search_query(query)
    validated_type = validate_variant_type(type)
    validated_classification = validate_classification(classification)
    validated_gene = validate_gene(gene)

    # Build filter clauses using parameterized queries (SQL injection safe)
    filter_conditions = []
    params = {}

    if validated_query:
        # Search in variant ID, label, and HGVS expressions
        filter_conditions.append(
            """
            (
                gi.value->'variantInterpretation'->'variationDescriptor'->>'id' ILIKE :query
                OR gi.value->'variantInterpretation'->'variationDescriptor'->>'label' ILIKE :query
                OR EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(gi.value->'variantInterpretation'->'variationDescriptor'->'expressions') AS expr
                    WHERE expr->>'value' ILIKE :query
                )
            )
            """
        )
        params["query"] = f"%{validated_query}%"

    if validated_type:
        filter_conditions.append(
            "gi.value->'variantInterpretation'->'variationDescriptor'->'structuralType'->>'label' = :type"
        )
        params["type"] = validated_type

    if validated_classification:
        filter_conditions.append(
            "gi.value->'variantInterpretation'->>'acmgPathogenicityClassification' = :classification"
        )
        params["classification"] = validated_classification

    if validated_gene:
        filter_conditions.append(
            "gi.value->'variantInterpretation'->'variationDescriptor'->'geneContext'->>'symbol' = :gene"
        )
        params["gene"] = validated_gene

    # Combine filters with AND (safe - no f-string interpolation)
    where_clause = " AND ".join(filter_conditions) if filter_conditions else "TRUE"

    # Build final query with parameterized WHERE clause
    # NOTE: where_clause is safe here because it's constructed from pre-validated string literals
    # and does NOT include user input directly via f-string
    query_sql = f"""
    WITH variant_data AS (
        SELECT DISTINCT ON (gi.value->'variantInterpretation'->'variationDescriptor'->>'id')
            gi.value->'variantInterpretation'->'variationDescriptor'->>'id' AS variant_id,
            gi.value->'variantInterpretation'->'variationDescriptor' AS descriptor,
            gi.value->'variantInterpretation'->>'acmgPathogenicityClassification' AS classification,
            COUNT(*) OVER () AS total_filtered
        FROM phenopackets p,
             jsonb_array_elements(p.jsonb->'interpretations') AS interp,
             jsonb_array_elements(interp.value->'diagnosis'->'genomicInterpretations') AS gi
        WHERE {where_clause}
    )
    SELECT
        variant_id,
        descriptor,
        classification,
        (SELECT COUNT(DISTINCT gi.value->'variantInterpretation'->'variationDescriptor'->>'id')
         FROM phenopackets p2,
              jsonb_array_elements(p2.jsonb->'interpretations') AS interp2,
              jsonb_array_elements(interp2.value->'diagnosis'->'genomicInterpretations') AS gi) AS total_unfiltered,
        total_filtered
    FROM variant_data
    ORDER BY variant_id
    LIMIT :limit OFFSET :skip
    """

    # Add pagination params
    params["skip"] = skip
    params["limit"] = min(limit, 1000)  # Enforce max limit

    # Execute query with bound parameters (SQL injection safe)
    result = await db.execute(text(query_sql), params)
    rows = result.fetchall()

    if not rows:
        result_data = {
            "data": [],
            "total": 0,
            "total_unfiltered": 0,
            "skip": skip,
            "limit": limit,
        }
    else:
        variants = []
        for row in rows:
            variants.append({
                "variant_id": row.variant_id,
                "label": row.descriptor.get("label"),
                "gene": row.descriptor.get("geneContext", {}).get("symbol"),
                "structural_type": row.descriptor.get("structuralType", {}).get("label"),
                "classification": row.classification,
                "expressions": row.descriptor.get("expressions", []),
            })

        result_data = {
            "data": variants,
            "total": rows[0].total_filtered if rows else 0,
            "total_unfiltered": rows[0].total_unfiltered if rows else 0,
            "skip": skip,
            "limit": limit,
        }

    # Audit logging
    log_search_query(
        user_id=current_user,
        client_ip=request.client.host,
        query=validated_query,
        variant_type=validated_type,
        classification=validated_classification,
        gene=validated_gene,
        result_count=result_data["total"],
    )

    return result_data
```

**Key Security Improvements:**
1. ✅ **SQL Injection Prevention**: All user inputs passed via `:param` bind parameters
2. ✅ **Input Validation**: HGVS format checked, character whitelist enforced
3. ✅ **Rate Limiting**: 10 requests/minute per IP address
4. ✅ **Audit Logging**: All searches logged with timestamp, user, filters, result count
5. ✅ **Max Limit Enforcement**: Prevents fetching >1000 variants in one request

### 5. Database Indexing for Performance

**File:** `backend/alembic/versions/XXX_add_variant_search_indexes.py` (new migration)

Create GIN indexes for JSONB expression arrays to enable fast text search:

```python
"""Add GIN indexes for variant search

Revision ID: add_variant_search_indexes
Revises: <previous_revision>
Create Date: 2025-XX-XX
"""

from alembic import op


def upgrade():
    """Add GIN indexes for variant search performance."""
    # Index for variant ID and label (text search)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_variant_descriptor_id
        ON phenopackets USING GIN (
            (jsonb_path_query_array(
                jsonb,
                '$.interpretations[*].diagnosis.genomicInterpretations[*].variantInterpretation.variationDescriptor.id'
            ))
        );
    """)

    # Index for HGVS expressions array (enables fast HGVS search)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_variant_expressions
        ON phenopackets USING GIN (
            (jsonb_path_query_array(
                jsonb,
                '$.interpretations[*].diagnosis.genomicInterpretations[*].variantInterpretation.variationDescriptor.expressions[*].value'
            ))
        );
    """)

    # Index for variant type
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_variant_type
        ON phenopackets USING GIN (
            (jsonb_path_query_array(
                jsonb,
                '$.interpretations[*].diagnosis.genomicInterpretations[*].variantInterpretation.variationDescriptor.structuralType.label'
            ))
        );
    """)

    # Index for pathogenicity classification
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_variant_classification
        ON phenopackets USING GIN (
            (jsonb_path_query_array(
                jsonb,
                '$.interpretations[*].diagnosis.genomicInterpretations[*].variantInterpretation.acmgPathogenicityClassification'
            ))
        );
    """)


def downgrade():
    """Remove variant search indexes."""
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_variant_descriptor_id;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_variant_expressions;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_variant_type;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_variant_classification;")
```

**Why GIN Indexes:**
- `GIN` (Generalized Inverted Index) is ideal for JSONB full-text search
- Enables fast `@>` (contains) and `ILIKE` queries on JSONB arrays
- `CREATE INDEX CONCURRENTLY` allows indexing without locking the table
- Expected performance: <50ms for filtered queries (down from 500ms+)

### 6. Frontend Integration (Issue #66)

**Note:** Frontend UI implementation is tracked separately in Issue #66. That issue will cover:
- Vue search component with debounced input
- Filter dropdowns for type, classification, gene
- Active filter chips display
- Results count and pagination
- API client integration with `getVariants()` method

## Search Behavior Examples

### Example 1: Search by HGVS notation
```
User types: "c.1654-2A>T"
Backend searches:
- variant.id contains "c.1654-2A>T"
- variant.label contains "c.1654-2A>T"
- variant.expressions[] contains "c.1654-2A>T"
Results: All variants with this notation
```

### Example 2: Filter by pathogenicity
```
User selects: Classification = "PATHOGENIC"
Backend filters:
- acmgPathogenicityClassification = "PATHOGENIC"
Results: Only pathogenic variants
```

### Example 3: Combined search + filter
```
User types: "deletion" + Type = "deletion" + Classification = "PATHOGENIC"
Backend applies:
- Text search for "deletion" in label/id
- AND structural_type = "deletion"
- AND classification = "PATHOGENIC"
Results: Pathogenic deletions matching "deletion"
```

## Implementation Checklist

### Phase 1: Security & Validation (3 hours)
- [ ] Create `validation.py` with input validators
- [ ] Implement HGVS notation validation (consider `hgvs` library)
- [ ] Add character whitelist enforcement
- [ ] Add length limits (100 chars max)
- [ ] Test validation with malicious inputs (SQL injection attempts)

### Phase 2: Rate Limiting & Audit (2 hours)
- [ ] Create `rate_limiter.py` middleware
- [ ] Implement in-memory rate limiter (10 req/min)
- [ ] Add Redis-based rate limiter (production)
- [ ] Create `audit_logger.py` for GDPR compliance
- [ ] Test rate limiting with concurrent requests

### Phase 3: Search Endpoint (4 hours)
- [ ] Create `/aggregate/variants/search` endpoint
- [ ] Wire up validation, rate limiting, audit logging
- [ ] Implement parameterized SQL queries
- [ ] Add JSONB array searching with EXISTS clause
- [ ] Test search with various HGVS formats (c., p., g.)
- [ ] Test filters individually and combined
- [ ] Handle empty results gracefully

### Phase 4: Database Optimization (2 hours)
- [ ] Create Alembic migration for GIN indexes
- [ ] Add index on variant IDs
- [ ] Add index on HGVS expressions array
- [ ] Add index on variant types
- [ ] Add index on classifications
- [ ] Verify index usage with EXPLAIN ANALYZE

### Phase 5: Testing & Security Review (3 hours)
- [ ] Test SQL injection prevention (try malicious queries)
- [ ] Test rate limiting (exceed 10 req/min)
- [ ] Test pagination with search results
- [ ] Test special characters in HGVS notation
- [ ] Verify audit logs are written correctly
- [ ] Measure query performance (<200ms target)
- [ ] Load test with 864 phenopackets

## Acceptance Criteria

**Security:**
- [ ] All user inputs validated and sanitized
- [ ] SQL injection prevented (parameterized queries only)
- [ ] HGVS notation format validated
- [ ] Character whitelist enforced (no special characters except HGVS symbols)
- [ ] Query length limited to 100 characters
- [ ] Rate limiting enforced (10 req/min per IP)
- [ ] Audit logging captures all searches with user ID, filters, result count

**Functionality:**
- [ ] Text search works for HGVS notations (c., p., g.)
- [ ] Text search works for variant IDs
- [ ] Text search works for variant labels
- [ ] Type filter works (SNV, deletion, duplication, insertion, inversion)
- [ ] Classification filter works (P, LP, VUS, LB, B)
- [ ] Gene filter works (HNF1B)
- [ ] Multiple filters can be combined (AND logic)
- [ ] Empty search returns all variants
- [ ] No results returns empty array with total counts

**Performance:**
- [ ] Backend query performance < 200ms (with GIN indexes)
- [ ] GIN indexes created for variant IDs, expressions, types, classifications
- [ ] Query plan uses indexes (verified with EXPLAIN ANALYZE)
- [ ] Pagination works correctly (skip/limit)
- [ ] Max limit enforced (1000 variants per request)

**Testing:**
- [ ] SQL injection attempts fail (400 Bad Request)
- [ ] Rate limit exceeded returns 429 Too Many Requests
- [ ] Invalid HGVS notation returns 400 with helpful error
- [ ] Invalid filter values return 400 with allowed values
- [ ] Audit logs written to logger correctly

## Dependencies

- Issue #57 (Variant deduplication) - ⚠️ **BLOCKER** - Must resolve duplicate variants before search returns accurate results
- Issue #34 (Variants list page) - ✅ Required for context
- Issue #66 (Frontend search UI) - ⚠️ **DEPENDS ON THIS** - Cannot implement frontend without backend endpoint

## Performance Impact

**Without GIN Indexes (Before):**
- Full table scan on 864 phenopackets
- Search without filters: ~500ms
- Search with filters: ~800ms
- ILIKE on JSONB: ~1000ms

**With GIN Indexes (After):**
- Index scan on JSONB paths
- Search without filters: ~50ms (10x faster)
- Search with 1 filter: ~80ms
- Search with multiple filters: ~150ms (5x faster)
- HGVS expression search: ~60ms (using idx_variant_expressions)

**Security Overhead:**
- Input validation: ~1ms
- Rate limiting check: ~2ms
- Audit logging: ~5ms (async write)
- Total overhead: ~8ms (negligible)

**Database Impact:**
- GIN indexes add ~10-20MB storage per index
- Indexes updated on phenopacket INSERT/UPDATE (minimal overhead)
- `CREATE INDEX CONCURRENTLY` prevents table locking during migration

## Testing Verification

### Security Testing

```bash
# 1. SQL Injection Attempts (should all return 400)
curl "http://localhost:8000/api/v2/phenopackets/aggregate/variants/search?query='; DROP TABLE phenopackets;--"
# Expected: 400 Bad Request - "Search query contains invalid characters"

curl "http://localhost:8000/api/v2/phenopackets/aggregate/variants/search?query=1' OR '1'='1"
# Expected: 400 Bad Request - "Search query contains invalid characters"

# 2. Rate Limiting Test (should return 429 after 10 requests)
for i in {1..12}; do
  curl "http://localhost:8000/api/v2/phenopackets/aggregate/variants/search?query=test"
  echo "Request $i"
done
# Expected: First 10 succeed, requests 11-12 return 429 Too Many Requests

# 3. Invalid HGVS Notation
curl "http://localhost:8000/api/v2/phenopackets/aggregate/variants/search?query=c.invalid"
# Expected: 400 Bad Request - "Invalid HGVS notation format"

# 4. Query Too Long
curl "http://localhost:8000/api/v2/phenopackets/aggregate/variants/search?query=$(python3 -c 'print("A"*101)')"
# Expected: 400 Bad Request - "Search query too long (max 100 chars)"
```

### Functional Testing

```bash
# 1. Start backend
make backend

# 2. Test HGVS search
curl "http://localhost:8000/api/v2/phenopackets/aggregate/variants/search?query=c.1654"
# Expected: Returns variants with "c.1654" in ID, label, or expressions

# 3. Test type filter
curl "http://localhost:8000/api/v2/phenopackets/aggregate/variants/search?type=deletion"
# Expected: Returns only deletion variants

# 4. Test classification filter
curl "http://localhost:8000/api/v2/phenopackets/aggregate/variants/search?classification=PATHOGENIC"
# Expected: Returns only pathogenic variants

# 5. Test combined filters
curl "http://localhost:8000/api/v2/phenopackets/aggregate/variants/search?query=HNF1B&type=SNV&classification=PATHOGENIC"
# Expected: Returns pathogenic SNVs in HNF1B

# 6. Test empty search (returns all)
curl "http://localhost:8000/api/v2/phenopackets/aggregate/variants/search?skip=0&limit=10"
# Expected: Returns first 10 variants

# 7. Test pagination
curl "http://localhost:8000/api/v2/phenopackets/aggregate/variants/search?skip=10&limit=10"
# Expected: Returns variants 11-20
```

### Performance Testing

```bash
# 1. Verify GIN indexes exist
psql -d hnf1b_phenopackets -c "\d+ phenopackets" | grep idx_variant

# Expected output:
# idx_variant_descriptor_id
# idx_variant_expressions
# idx_variant_type
# idx_variant_classification

# 2. Check query plan (should use indexes)
psql -d hnf1b_phenopackets -c "EXPLAIN ANALYZE SELECT ...;"
# Expected: "Bitmap Index Scan using idx_variant_expressions"

# 3. Measure query time
time curl "http://localhost:8000/api/v2/phenopackets/aggregate/variants/search?query=c.1654"
# Expected: < 200ms total time
```

## Files Modified/Created

### New Files (5 files, ~450 lines)
- `backend/app/phenopackets/validation.py` (~150 lines for input validation)
- `backend/app/middleware/rate_limiter.py` (~40 lines for rate limiting)
- `backend/app/utils/audit_logger.py` (~30 lines for audit logging)
- `backend/alembic/versions/XXX_add_variant_search_indexes.py` (~60 lines for GIN indexes)
- `backend/tests/test_variant_search_security.py` (~100 lines for security tests)

### Modified Files (1 file, ~100 lines added)
- `backend/app/phenopackets/endpoints.py` (+100 lines for secure search endpoint)

## Timeline

**Estimated:** 14 hours (2 days)

**Breakdown:**
- Phase 1 (Security & Validation): 3 hours
- Phase 2 (Rate Limiting & Audit): 2 hours
- Phase 3 (Search Endpoint): 4 hours
- Phase 4 (Database Optimization): 2 hours
- Phase 5 (Testing & Security Review): 3 hours

## Priority

**P1 (High)** - Blocker for Issue #66 (frontend search UI)

**Rationale:**
- Security-critical endpoint (SQL injection risk)
- Required for variant search functionality
- Blocks frontend development until complete

## Labels

`backend`, `security`, `search`, `variants`, `database`, `p1`, `blocker`

## Notes

**Security:**
- All inputs validated before database query
- Parameterized queries prevent SQL injection
- Rate limiting prevents DoS attacks
- Audit logging for GDPR compliance
- Consider upgrading to `hgvs` library for production HGVS validation

**Search Behavior:**
- Case-insensitive (uses ILIKE in PostgreSQL)
- Partial matches (e.g., "1654" matches "c.1654-2A>T")
- Searches variant ID, label, AND HGVS expressions array
- Filters are AND combined (all must match)
- Empty search/filters returns all variants

**Performance:**
- GIN indexes on JSONB paths enable <200ms queries
- Max limit enforced (1000 variants per request)
- Pagination with skip/limit (offset-based)

**Production Considerations:**
- Replace in-memory rate limiter with Redis for distributed systems
- Configure audit logger to write to centralized logging system (e.g., ELK stack)
- Monitor rate limit violations and adjust thresholds
- Set up alerts for SQL injection attempts (400 errors with "invalid characters")

**Related Work:**
- Issue #57 must be completed first (variant deduplication)
- Issue #66 will implement frontend UI for this endpoint
- Issue #65 (gene visualization) may consume this endpoint for variant mapping
