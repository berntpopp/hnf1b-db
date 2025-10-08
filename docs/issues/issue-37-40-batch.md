# Issues #37, #39, #40 - Quick Reference

## Issue #37: feat(frontend): migrate publication detail page

### Overview
Show all phenopackets linked to a specific publication (PMID).

---

## Publication Metadata Strategy

### Problem

Issue #37 states "fetch publication metadata from PubMed API" but lacks implementation details:
- **Client-side** fetch: Hits NCBI API on every page load (slow, rate-limited)
- **Server-side** fetch: Better, but still slow without caching
- **Where to cache:** Database? Redis? In-memory?

### Recommended Solution: Server-Side Caching

**Architecture:**
```
User → Frontend → Backend → Cache → PubMed API
                         ↓
                    (Cache hit: ~10ms)
                         ↓
                    (Cache miss: fetch + cache: ~500ms)
```

**Implementation:**

#### Option 1: Database Cache (Recommended)

```sql
-- Create publications cache table
CREATE TABLE publication_metadata (
    pmid VARCHAR(20) PRIMARY KEY,
    title TEXT,
    authors TEXT[],
    journal VARCHAR(255),
    year INTEGER,
    doi VARCHAR(100),
    abstract TEXT,
    fetched_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT valid_pmid CHECK (pmid LIKE 'PMID:%')
);

-- Index for expiration queries
CREATE INDEX idx_publication_metadata_fetched ON publication_metadata (fetched_at);
```

**Backend Endpoint:**
```python
# backend/app/publications/service.py
import aiohttp
from datetime import datetime, timedelta

PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
CACHE_TTL_DAYS = 90  # Publications don't change, cache for 90 days

async def get_publication_metadata(pmid: str):
    """
    Fetch publication metadata with caching.

    1. Check database cache
    2. If missing or expired, fetch from PubMed
    3. Cache in database
    """
    # Check cache
    cached = await db.execute(
        "SELECT * FROM publication_metadata WHERE pmid = :pmid AND fetched_at > NOW() - INTERVAL '90 days'",
        {"pmid": pmid}
    )

    if cached:
        return cached[0]

    # Cache miss - fetch from PubMed
    async with aiohttp.ClientSession() as session:
        pmid_number = pmid.replace("PMID:", "")
        url = f"{PUBMED_API}?db=pubmed&id={pmid_number}&retmode=json"

        async with session.get(url) as response:
            if response.status != 200:
                raise PubMedAPIError(f"PubMed API returned {response.status}")

            data = await response.json()
            result = data['result'][pmid_number]

            metadata = {
                "pmid": pmid,
                "title": result.get("title", ""),
                "authors": result.get("authors", []),
                "journal": result.get("source", ""),
                "year": result.get("pubdate", "").split()[0],  # Extract year
                "doi": result.get("elocationid", "").replace("doi: ", ""),
                "abstract": ""  # Not in summary, requires efetch
            }

    # Store in cache
    await db.execute(
        """
        INSERT INTO publication_metadata (pmid, title, authors, journal, year, doi)
        VALUES (:pmid, :title, :authors, :journal, :year, :doi)
        ON CONFLICT (pmid) DO UPDATE SET fetched_at = NOW()
        """,
        metadata
    )

    return metadata
```

#### Option 2: Redis Cache (Alternative)

```python
# backend/app/publications/service.py
import redis.asyncio as redis
import json

REDIS_TTL = 60 * 60 * 24 * 90  # 90 days

async def get_publication_metadata_redis(pmid: str):
    """Use Redis for caching (faster but requires Redis)."""
    cache_key = f"publication:{pmid}"

    # Check Redis cache
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Fetch from PubMed (same as above)
    metadata = await fetch_from_pubmed(pmid)

    # Cache in Redis
    await redis_client.setex(
        cache_key,
        REDIS_TTL,
        json.dumps(metadata)
    )

    return metadata
```

**Comparison:**

| Strategy | Pros | Cons |
|----------|------|------|
| **Database cache** | No extra service, persistent | Slightly slower (10-20ms) |
| **Redis cache** | Very fast (< 5ms) | Requires Redis, volatile |
| **In-memory** | Fastest | Lost on restart, memory usage |

**Recommendation:** **Database cache** (simpler, no Redis dependency)

### Endpoint Implementation

```http
GET /api/v2/phenopackets/by-publication/PMID:30791938

Response:
{
  "publication": {
    "pmid": "PMID:30791938",
    "title": "Renal phenotypes related to hepatocyte nuclear factor-1beta...",
    "authors": ["Clissold RL", "Hamilton AJ", "Hattersley AT", "..."],
    "journal": "Nephrology Dialysis Transplantation",
    "year": 2019,
    "doi": "10.1093/ndt/gfz029",
    "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/30791938/",
    "doi_url": "https://doi.org/10.1093/ndt/gfz029"
  },
  "phenopackets": [
    {
      "phenopacket_id": "phenopacket-001",
      "subject_id": "PATIENT-001",
      "sex": "FEMALE",
      "primary_disease": "MONDO:0013894",
      "phenotype_count": 8,
      "has_variants": true
    }
  ],
  "stats": {
    "total_phenopackets": 42,
    "sex_distribution": {"MALE": 20, "FEMALE": 22},
    "common_phenotypes": [
      {"hpo_id": "HP:0012622", "label": "Chronic kidney disease", "count": 40},
      {"hpo_id": "HP:0000078", "label": "Genital abnormality", "count": 28}
    ]
  }
}
```

### Error Handling

```python
# Handle PubMed API failures gracefully

# 1. Rate limiting
if response.status == 429:
    # Use cached data even if expired, or return partial data
    return {
        "pmid": pmid,
        "title": f"Publication {pmid} (metadata unavailable)",
        "error": "PubMed API rate limit exceeded"
    }

# 2. PMID not found
if pmid_number not in data['result']:
    return {
        "pmid": pmid,
        "title": "Publication not found",
        "error": f"PMID {pmid} not found in PubMed"
    }

# 3. API timeout
try:
    async with asyncio.timeout(5):  # 5 second timeout
        response = await session.get(url)
except asyncio.TimeoutError:
    # Return minimal data
    return {"pmid": pmid, "title": "Metadata unavailable (timeout)"}
```

### Cache Warming Strategy

**Pre-populate cache with known PMIDs:**

```python
# backend/migration/warm_publication_cache.py

async def warm_publication_cache():
    """
    Extract all PMIDs from phenopackets and pre-fetch metadata.
    Run after data migration.
    """
    # Extract unique PMIDs
    pmids_query = """
        SELECT DISTINCT
            er.value->>'id' AS pmid
        FROM phenopackets p,
             jsonb_array_elements(p.jsonb->'metaData'->'externalReferences') AS er
        WHERE er.value->>'id' LIKE 'PMID:%'
    """

    pmids = await db.fetch_all(pmids_query)

    # Fetch metadata for each (with rate limiting)
    for pmid_row in pmids:
        pmid = pmid_row['pmid']
        try:
            await get_publication_metadata(pmid)
            await asyncio.sleep(0.5)  # NCBI rate limit: max 3 req/sec
        except Exception as e:
            logger.error(f"Failed to fetch {pmid}: {e}")
```

**Run after migration:**
```bash
# Warm cache
make backend-shell
>>> from backend.migration.warm_publication_cache import warm_publication_cache
>>> await warm_publication_cache()
```

### Performance Impact

**Without caching:**
- PubMed API: ~500-1000ms per request
- Rate limited to 3 req/sec
- Page load: **500ms+** for each publication

**With database caching:**
- Cache hit: ~10-20ms
- Cache miss: ~500ms (first request only)
- Subsequent loads: **< 20ms** ✅

### Implementation
- Display publication info (PMID, DOI, title from cached PubMed data)
- Table of all phenopackets citing this publication
- Stats: Total individuals, sex distribution, common phenotypes

### Checklist
- [ ] Backend: Create `publication_metadata` table
- [ ] Backend: `/by-publication/{pmid}` endpoint
- [ ] Backend: PubMed API integration with caching
- [ ] Backend: Cache warming script
- [ ] API: `getPhenopacketsByPublication(pmid)`
- [ ] View: Create PagePublication.vue
- [ ] Display publication metadata with fallback for errors
- [ ] Display phenopackets table with filters

### Timeline: 6 hours (1 day)
### Labels: `frontend`, `views`, `phenopackets`, `p1`

---

## Issue #39: feat(frontend): implement global phenopacket search

### Overview
Universal search across individuals, variants, publications, and phenotypes.

---

## Search Architecture

### Technology Decision

**Problem:** How to implement full-text search across phenopackets?

**Options:**
1. **PostgreSQL Full-Text Search (tsvector)** - Recommended
2. **Elasticsearch** - Overkill for 864 phenopackets
3. **Client-side filtering** - Too slow, no fuzzy matching

**Recommendation:** **PostgreSQL Full-Text Search**

**Rationale:**
- Dataset size: 864 phenopackets = **small** (< 10k documents)
- No need for external service (Elasticsearch complexity)
- PostgreSQL tsvector supports ranking, fuzzy matching, stemming
- Can index JSONB fields directly
- Performance: < 100ms for full-text queries with proper indexes

### Search Implementation

**Backend Index Setup:**
```sql
-- Create tsvector generated column for full-text search
ALTER TABLE phenopackets ADD COLUMN search_vector tsvector
GENERATED ALWAYS AS (
    -- Index subject ID
    to_tsvector('english', COALESCE(jsonb->>'subject'->>'id', '')) ||
    -- Index phenotype labels
    to_tsvector('english', COALESCE(
        (SELECT string_agg(value->>'type'->>'label', ' ')
         FROM jsonb_array_elements(jsonb->'phenotypicFeatures')), ''
    )) ||
    -- Index disease labels
    to_tsvector('english', COALESCE(
        (SELECT string_agg(value->>'term'->>'label', ' ')
         FROM jsonb_array_elements(jsonb->'diseases')), ''
    )) ||
    -- Index gene symbols
    to_tsvector('english', COALESCE(
        (SELECT string_agg(
            value->'variantInterpretation'->'variationDescriptor'->'geneContext'->>'symbol', ' ')
         FROM jsonb_array_elements(jsonb->'interpretations'),
              jsonb_array_elements(value->'diagnosis'->'genomicInterpretations')), ''
    ))
) STORED;

-- Create GIN index on tsvector
CREATE INDEX idx_phenopackets_search ON phenopackets USING GIN (search_vector);
```

**Query Example:**
```sql
-- Full-text search with ranking
SELECT
    id,
    jsonb->>'subject'->>'id' AS subject_id,
    ts_rank(search_vector, query) AS rank
FROM phenopackets,
     to_tsquery('english', 'chronic & kidney') AS query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 20;
```

### Search Endpoint Specification

```http
POST /api/v2/phenopackets/search

Body:
{
  "query": "chronic kidney",        // Full-text search (tsquery syntax)
  "hpo_terms": ["HP:0012622"],     // HPO filters (exact match)
  "sex": "FEMALE",                  // Sex filter
  "has_variants": true,             // Variant presence
  "genes": ["HNF1B"],              // Gene filter
  "pmids": ["PMID:30791938"],      // Publication filter
  "pathogenicity": ["PATHOGENIC"],  // Variant classification
  "skip": 0,                        // Pagination offset
  "limit": 20                       // Results per page
}

Response: 200 OK
{
  "results": [
    {
      "phenopacket_id": "phenopacket-001",
      "subject_id": "PATIENT-001",
      "sex": "FEMALE",
      "primary_disease": "MONDO:0013894",
      "disease_label": "HNF1B-related disorder",
      "phenotype_count": 8,
      "has_variants": true,
      "search_rank": 0.876  // Relevance score
    }
  ],
  "total_count": 42,
  "query_time_ms": 87
}
```

### Autocomplete Implementation

**Problem:** How to provide autocomplete suggestions for HPO terms, genes, variants?

**Solution:** Separate autocomplete endpoints querying ontology data

**HPO Term Autocomplete:**
```http
GET /api/v2/ontology/hpo/autocomplete?q=kidney

Response:
[
  { "id": "HP:0012622", "label": "Chronic kidney disease", "count": 427 },
  { "id": "HP:0000107", "label": "Renal cyst", "count": 156 },
  { "id": "HP:0000083", "label": "Kidney failure", "count": 89 }
]
```

**Data Source:**
- Option 1: Query `phenotypicFeatures` JSONB for existing terms in data
- Option 2: Maintain separate `hpo_terms` lookup table (faster)

**Recommended:** **Pre-populate lookup table** with all HPO terms present in phenopackets

```sql
-- Create lookup table
CREATE TABLE hpo_terms_lookup AS
SELECT DISTINCT
    pf.value->'type'->>'id' AS hpo_id,
    pf.value->'type'->>'label' AS label,
    COUNT(DISTINCT p.id) AS phenopacket_count
FROM phenopackets p,
     jsonb_array_elements(p.jsonb->'phenotypicFeatures') AS pf
GROUP BY hpo_id, label
ORDER BY phenopacket_count DESC;

-- Index for autocomplete
CREATE INDEX idx_hpo_lookup_label_trgm ON hpo_terms_lookup
USING GIN (label gin_trgm_ops);  -- Trigram index for fuzzy search
```

**Autocomplete Query:**
```sql
SELECT hpo_id, label, phenopacket_count
FROM hpo_terms_lookup
WHERE label ILIKE '%kidney%'  -- Case-insensitive substring match
   OR label % 'kidney'         -- Fuzzy trigram match
ORDER BY phenopacket_count DESC
LIMIT 10;
```

### Recent Searches

**Implementation:** Store in browser localStorage

```javascript
// frontend/src/utils/searchHistory.js
const MAX_RECENT_SEARCHES = 10;

export function saveRecentSearch(query) {
  const recent = getRecentSearches();
  const updated = [query, ...recent.filter(q => q !== query)].slice(0, MAX_RECENT_SEARCHES);
  localStorage.setItem('recentSearches', JSON.stringify(updated));
}

export function getRecentSearches() {
  const stored = localStorage.getItem('recentSearches');
  return stored ? JSON.parse(stored) : [];
}
```

### Performance Targets

**Full-Text Search:**
- Response time: < 200ms for simple queries
- Response time: < 500ms for complex queries (multiple filters)
- Autocomplete: < 100ms

**Expected Query Complexity:**
- 864 phenopackets × ~8 phenotypes = ~7k searchable records
- PostgreSQL tsvector easily handles this without external services

### Features
- Search bar in AppBar (global)
- Autocomplete for HPO terms
- Recent searches
- Search suggestions
- Type-ahead results

### Implementation
**File:** `frontend/src/components/GlobalSearch.vue`

```vue
<template>
  <v-autocomplete
    v-model="searchQuery"
    :items="suggestions"
    :loading="loading"
    label="Search individuals, variants, publications..."
    prepend-inner-icon="mdi-magnify"
    clearable
    @update:search="onSearch"
    @update:model-value="navigateToResults"
  >
    <template #item="{ item }">
      <v-list-item :to="`/search?q=${item.value}`">
        <v-list-item-title>{{ item.title }}</v-list-item-title>
        <v-list-item-subtitle>{{ item.type }}</v-list-item-subtitle>
      </v-list-item>
    </template>
  </v-autocomplete>
</template>
```

### Checklist
- [ ] Backend: Enhance `/search` with full-text
- [ ] API: Update `searchPhenopackets()` with all filters
- [ ] Component: Create GlobalSearch.vue
- [ ] Add to AppBar.vue
- [ ] Implement autocomplete
- [ ] Add recent searches (localStorage)

### Timeline: 12 hours (2 days)
### Labels: `frontend`, `components`, `feature`, `p1`

---

## Issue #40: feat(frontend): implement search results with faceted filtering

### Overview
Enhanced search results page with sidebar filters.

### Layout
```
┌─────────────────────┬───────────────────────────────┐
│  Filters            │  Results (20)                 │
│  ───────            │  ─────────────────────        │
│  ☐ Sex              │  [Phenopacket Card 1]         │
│    ☐ Male (432)     │  [Phenopacket Card 2]         │
│    ☐ Female (432)   │  [Phenopacket Card 3]         │
│                     │                               │
│  ☐ Has Variants     │  Pagination: < 1 2 3 4 5 >    │
│    ☐ Yes (423)      │                               │
│    ☐ No (441)       │                               │
│                     │                               │
│  ☐ Pathogenicity    │                               │
│    ☐ Pathogenic     │                               │
│    ☐ Likely Path.   │                               │
│    ☐ VUS            │                               │
│                     │                               │
│  [Clear All]        │  [Export Results]             │
└─────────────────────┴───────────────────────────────┘
```

### Features
- Faceted filters (counts update dynamically)
- Sort by relevance, date, ID
- Export results (CSV, JSON)
- Shareable URL with query params
- Pagination

### Checklist
- [ ] View: Create SearchResults.vue
- [ ] Component: FacetedFilters.vue
- [ ] Component: PhenopacketCard.vue (summary)
- [ ] Implement dynamic filter counts
- [ ] Add export functionality
- [ ] URL query string management

### Timeline: 10 hours (1.5 days)
### Labels: `frontend`, `views`, `feature`, `p1`
