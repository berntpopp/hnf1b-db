# Unified Global Search & Discovery Plan (HNF1B Focused)

## 1. Executive Summary

The current search functionality is fragmented. While the database is HNF1B-centric, users still need to find specific **variants** (e.g., "c.123A>G"), **phenotypic features** (e.g., "Renal cysts"), **publications**, and **gene features** (e.g., "Exon 4", "Homeobox domain").

This plan outlines a solution to implement:
1.  **Global Autocomplete:** Instant suggestions across Variants, Phenotypes, Publications, and Gene Features (Domains/Exons).
2.  **Unified Search Results:** A ranked, categorized view of all matching data.
3.  **High-Performance Backend:** Leveraging PostgreSQL's native Full-Text Search (`tsvector`) and Trigram (`pg_trgm`) indexes.

*Note: Since the database is primarily for the HNF1B gene, "Gene Search" is replaced by "Gene Feature Search" (finding specific transcripts, exons, or domains).*

---

## 2. Current State Analysis

| Entity | Storage | Current Search Capabilities | Gaps |
| :--- | :--- | :--- | :--- |
| **Phenopackets** | `phenopackets` table (JSONB) | ✅ Robust. Uses `tsvector` column + GIN index. | |
| **Variants** | Inside `phenopackets` JSONB | ✅ Good. Specialized GIN indexes for HGVS strings. | No dedicated `variants` table makes independent ranking harder. |
| **Publications** | `publication_metadata` table | ⚠️ Basic SQL `WHERE` clauses. | No full-text search index on titles/abstracts. |
| **Gene Features** | `transcripts`, `exons`, `protein_domains` | ⚠️ Basic ID lookups. | Cannot search for "Homeobox" or "Exon 4" easily. |
| **HPO Terms** | External / `hpo_proxy` | ✅ Good (via OLS or cached). | Separate endpoint; not integrated into global search. |

---

## 3. Proposed Architecture

### 3.1 Database Optimizations

To enable fast, unified search without an external engine (like Elasticsearch), we will maximize PostgreSQL capabilities.

1.  **Publications:** Add a `search_vector` generated column to `publication_metadata` (indexing title, authors, journal).
2.  **Gene Features:** Add indexes to `protein_domains` (name) and `transcripts` (refseq IDs) to allow searching for structural elements.
3.  **Materialized View (Recommended):** Create a `global_search_index` materialized view to aggregate "searchable items" for autocomplete.
    ```sql
    -- Concept
    CREATE MATERIALIZED VIEW global_search_index AS
      SELECT id, name as label, 'Domain' as type, to_tsvector(name) as vector FROM protein_domains
      UNION ALL
      SELECT id, transcript_id as label, 'Transcript' as type, to_tsvector(transcript_id) as vector FROM transcripts
      UNION ALL
      SELECT pmid, title as label, 'Publication' as type, to_tsvector(title) as vector FROM publication_metadata
      UNION ALL
      -- ... (Phenopackets and Variants from views)
    ```

### 3.2 Backend API (`/api/v2/search`)

We will introduce a dedicated `search` module with two core endpoints:

#### `GET /api/v2/search/autocomplete`
*   **Purpose:** Live suggestions for the search bar.
*   **Params:** `q` (query), `limit` (default 10).
*   **Logic:**
    *   **Variants:** Regex match on HGVS patterns (c., p., g.) and dbSNP IDs (rs...).
    *   **Gene Features:** Match "Exon X", Domain names ("Homeobox"), Transcript IDs ("NM_...").
    *   **Phenopackets:** Match Subject ID or specific phenotypic features.
    *   **HPO:** Proxy to HPO service.
*   **Response:**
    ```json
    {
      "results": [
        { "type": "Variant", "label": "c.123A>G (p.Arg41Gly)", "id": "..." },
        { "type": "Domain", "label": "POU-specific domain", "id": "..." },
        { "type": "HPO", "label": "Renal cysts", "id": "HP:..." }
      ]
    }
    ```

#### `GET /api/v2/search/global`
*   **Purpose:** Main results page.
*   **Params:** `q` (query), `limit`, `offset`.
*   **Logic:** Parallel async queries to all data sources.
*   **Ranking:** Exact Variant/ID matches > Phenotype Matches > Partial Text Matches.
*   **Response:**
    ```json
    {
      "summary": { "phenopackets": 12, "variants": 3, "publications": 4, "features": 1 },
      "hits": [ ... mixed list or grouped ... ]
    }
    ```

### 3.3 Frontend UX (Vue.js)

1.  **Global Search Bar (`GlobalSearch.vue`):**
    *   **Location:** Replaces the current search bar in the Hero/Navbar.
    *   **Placeholder:** "Search variants (c.123...), phenotypes, or publications..."
    *   **Behavior:**
        *   Input > 2 chars triggers `autocomplete`.
        *   Dropdown groups results by type (Variants, Features, Phenotypes).
    *   **Component:** Use Vuetify's `v-autocomplete` with custom `item` slots.

2.  **Search Results Page (`SearchResults.vue`):**
    *   **Layout:** "Dashboard" style.
    *   **Tabs:** [ All ] [ Variants ] [ Phenopackets ] [ Publications ] [ Reference ].
    *   **"All" Tab:**
        *   **Best Match Card:** If query matches a specific Variant (e.g. "c.544C>T") or Domain, show a detailed summary card at the top.
        *   **Lists:** Summary lists for other categories below.

---

## 4. Implementation Plan

### Phase 1: Database & Backend (Estimated: 2 Days)
1.  **Migration:** Add `search_vector` to `publication_metadata` and indexes to `protein_domains`.
2.  **Service:** Create `GlobalSearchService` in Python.
    *   *Logic:* Prioritize HNF1B-specific context (Variants > Domains > General Text).
3.  **API:** Implement `/search/autocomplete` and `/search/global`.

### Phase 2: Frontend Components (Estimated: 2 Days)
1.  **Component:** Build `GlobalSearchBar.vue` optimized for Variant searching (handling special chars like `>`, `.`).
2.  **View:** Refactor `SearchResults.vue`.
3.  **Integration:** Wire up endpoints.

### Phase 3: Polish (Estimated: 1 Day)
1.  **Highlighting:** Add `<mark>` tags to matching terms.
2.  **Analytics:** Track search terms to understand user intent (e.g., are they searching for clinical terms or genetic coordinates?).

---

## 5. Technical Requirements

*   **Extensions:** `pg_trgm` (PostgreSQL Trigram Extension) must be enabled.
*   **Dependencies:** `aiohttp` (existing).

## 6. Example UI Mockup

**Search Bar Dropdown:**
```text
[ pou                  ]
------------------------
🧬 Gene Features
  POU-specific domain (Amino acids 1-100)
💊 Variants
  p.Leu123Pro (Located in POU domain)
🏥 Phenotypes (HPO)
  Polyuria (HP:0000103)
```

**Results Page (Query: "c.544")**
```text
Results for "c.544"
[ All ] [ Variants (5) ] [ Publications (2) ]

⭐ Best Match:
Variant: c.544C>T (p.Arg182Cys)
Type: Missense | Pathogenicity: Likely Pathogenic
[ View Variant Details ]

Related Phenopackets (12 patients with this variant):
1. Patient P001 - "Renal cysts..."
2. ...
```