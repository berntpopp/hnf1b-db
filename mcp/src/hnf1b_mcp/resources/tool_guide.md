# HNF1B-db Tool Guide

## Tool Inventory

| Tool | Purpose |
|---|---|
| `hnf1b_get_capabilities` | Retrieve server capabilities, limits, error codes, and this guide. Call first in any new session. |
| `hnf1b_search` | Search individuals by phenotype keywords, free text, or HPO term IDs. Returns a paginated list of matching phenopacket IDs and summary fields. |
| `hnf1b_get_individual` | Retrieve the full phenopacket record for a single individual by `phenopacket_id`. |
| `hnf1b_get_individuals` | Retrieve multiple phenopacket records in one call given a list of `phenopacket_id` values (batch fetch). |
| `hnf1b_find_individuals_by_phenotype` | Find individuals with a specific set of HPO term IDs. Caller supplies exact HPO IDs; v1 does not resolve free-text HPO labels. |
| `hnf1b_search_variants` | Search variant records by gene, HGVS notation, variant type, or ACMG class. Returns a paginated list of matching variant IDs and summaries. |
| `hnf1b_get_variant` | Retrieve the full record for a single variant by `variant_id`, including all associated interpretation details. |
| `hnf1b_get_gene_context` | Return a structured overview of the HNF1B gene: genomic coordinates, transcript IDs, disease associations, and published variant statistics. |
| `hnf1b_get_publications` | List publications curated in the database, optionally filtered by PMID list or keyword. Returns citation metadata with `recommended_citation` strings. |
| `hnf1b_get_statistics` | Return aggregate cohort statistics (variant counts by ACMG class, phenotype frequency histograms, etc.). Supports `dry_run=True` to preview payload cost. |
| `hnf1b_resolve_terms` | Resolve a list of HPO term IDs to their labels and hierarchy paths using the embedded ontology snapshot. |

## Canonical Workflows

### Workflow 1: Find Individuals by Clinical Phenotype

**Goal**: Identify individuals in the cohort with a specific clinical
presentation (e.g., renal cysts + diabetes).

1. **`hnf1b_search`** — supply `query` with keywords (e.g., `"renal cysts
   diabetes"`) or known HPO IDs. Review the returned phenopacket IDs and
   summary fields.
2. **`hnf1b_get_individual`** — for each ID of interest, retrieve the full
   phenopacket to inspect all phenotypic features, variant interpretations, and
   metadata.

```
hnf1b_search(query="renal cysts diabetes", response_mode="compact")
  → [phenopacket_id, ...]
    ↓
hnf1b_get_individual(phenopacket_id=<id>, response_mode="standard")
```

### Workflow 2: Explore a Specific Variant and Its Carriers

**Goal**: Find a known HNF1B variant and retrieve all individuals who carry it.

1. **`hnf1b_search_variants`** — supply `query` (e.g., `"c.494G>A"`) or
   other filters such as `variant_type`, `classification`, `gene`,
   `consequence`, or `domain`. Returns variant IDs and ACMG class summaries.
2. **`hnf1b_get_variant`** — retrieve full variant details including all
   published evidence and associated phenopacket IDs.
3. **`hnf1b_get_individuals`** — batch-fetch all individuals linked to that
   variant in one call.

```
hnf1b_search_variants(query="c.494G>A")
  → [variant_id, ...]
    ↓
hnf1b_get_variant(variant_id=<id>)
  → {variant detail, carriers: [...]}
    ↓
hnf1b_get_individuals(ids=[...], response_mode="compact")
```

### Workflow 3: Preview and Retrieve Cohort Statistics

**Goal**: Obtain aggregate cohort statistics without unexpectedly large
payloads.

1. **`hnf1b_get_statistics(dry_run=True)`** — inspect the expected payload size
   and available statistic categories before committing to a full request.
2. **`hnf1b_get_statistics`** — if the preview is acceptable, retrieve the full
   statistics payload with the desired `response_mode`.

```
hnf1b_get_statistics(dry_run=True)
  → {estimated_chars, available_categories: [...]}
    ↓
hnf1b_get_statistics(categories=["acmg_distribution", "phenotype_frequency"])
```

### Workflow 4: HPO Term Phenotype Search

**Goal**: Find individuals with a precise HPO-defined phenotype.

1. **`hnf1b_resolve_terms`** (optional) — confirm HPO term IDs map to the
   expected labels before searching.
2. **`hnf1b_find_individuals_by_phenotype`** — supply the resolved HPO term IDs
   to find matching individuals.
3. **`hnf1b_get_individual`** — retrieve full records for individuals of interest.

```
hnf1b_resolve_terms(text="proteinuria")
  → {HP:0000093: "Proteinuria", ...}
    ↓
hnf1b_find_individuals_by_phenotype(hpo_ids=["HP:0000093"])
  → [phenopacket_id, ...]
    ↓
hnf1b_get_individual(phenopacket_id=<id>)
```

## Payload Modes

All data-returning tools accept a `response_mode` parameter:

| Mode | Char budget | Use case |
|---|---|---|
| `minimal` | 4 000 | Counting / ID-only scans |
| `compact` | 12 000 | Exploratory browsing, default for search results |
| `standard` | 24 000 | Detailed individual or variant review |
| `full` | 48 000 | Complete record export for further analysis |

Use `dry_run=True` with `hnf1b_get_statistics` to preview payload cost before
requesting large aggregates.

## Error Codes

| Code | Meaning |
|---|---|
| `invalid_input` | A required parameter is missing, malformed, or out of range. |
| `not_found` | The requested resource (individual, variant, publication) does not exist. |
| `ambiguous_query` | The query matched multiple conflicting records; refine the search. |
| `temporarily_unavailable` | The upstream API or database is unreachable; retry later. |

## V1 Exclusions

The following capabilities are **not available** in v1:

- Write operations (create, update, delete records).
- Draft or unpublished record access.
- Live PubMed metadata fetch via `/publications/{pmid}/metadata`.
- HPO Ontology Lookup Service (OLS) proxy — callers must supply HPO IDs directly.
- Admin, authentication, or developer-management endpoints.
- Raw SQL or direct database access.
