# HNF1B-db Tool Guide

## Tool Inventory

| Tool | Purpose |
|---|---|
| `hnf1b_get_capabilities` | Retrieve server capabilities, limits, error codes, and this guide. Recommended (not required) for cold-session orientation; per-tool `filterable_fields` let clients build valid calls directly, and a warm client can compare `capabilities_version` and `tool_guide_version` before re-fetching. |
| `hnf1b_search` | Unified free-text discovery across individuals, variants, and publications (and genes). Returns typed ID hits; each hit carries a `resolve_with` object naming the exact tool + argument to fetch its content. |
| `hnf1b_get_individual` | Retrieve the full phenopacket record for a single individual by `phenopacket_id`. |
| `hnf1b_get_individuals` | Retrieve multiple phenopacket records in one call given a list of `phenopacket_id` values (batch fetch). |
| `hnf1b_find_individuals_by_phenotype` | Find individuals with a specific set of HPO term IDs. Caller supplies exact HPO IDs; v1 does not resolve free-text HPO labels. |
| `hnf1b_search_variants` | Search variant records by gene, HGVS notation, variant type, or ACMG class. Returns a paginated list of matching variant IDs and summaries. |
| `hnf1b_get_variant` | Retrieve the full record for a single variant by `variant_id`, including all associated interpretation details. |
| `hnf1b_get_gene_context` | Return the HNF1B gene reference record: genomic coordinates, cross-references (HGNC/NCBI/OMIM), transcript IDs, and annotated protein domains. |
| `hnf1b_get_publications` | List cached publications (keyword `q`, `year`, `has_doi`; `sort`), OR reverse-lookup the individuals citing one publication via `citing_pmid`. Returns `recommended_citation` strings. |
| `hnf1b_get_publication_passages` | Hybrid RAG retrieval over cached abstracts and license-gated open-access full-text passages. Returns passage IDs, section labels, snippets/text by mode, and citation metadata. |
| `hnf1b_get_statistics` | Return one aggregate cohort `metric` (variant counts by ACMG class, phenotype frequency, survival, etc.). Supports `dry_run=True` to preview payload cost. |
| `hnf1b_resolve_terms` | Resolve free text to HPO terms (autocomplete) or list a controlled vocabulary (sex, allelic-state, evidence-code, …). Returns `{id, label, description}` entries. |
| `hnf1b_compare_phenotypes` | Genotype-phenotype analytics: compare HPO phenotype frequencies (observed/excluded/unknown) across the carrier cohorts of up to 10 variants in a single call. |

## Tool Reference

### `hnf1b_get_capabilities`

Use for server-local discovery: available tools, enum-constrained filters,
payload-mode budgets, safety/citation contracts, resource versions, and
descriptor size metadata.

### `hnf1b_search`

Use for broad free-text discovery across individuals, variants, publications,
and genes. Hits include a `resolve_with` handoff that names the follow-up tool,
argument, and value.

### `hnf1b_get_individual`

Use when you already have one `phenopacket_id` and need the individual
phenopacket detail, including observed and excluded phenotype assertions.

### `hnf1b_get_individuals`

Use to batch-fetch multiple phenopacket records from an ordered `ids` list.

### `hnf1b_find_individuals_by_phenotype`

Use when you have exact HPO IDs and want the matching cohort by `match_mode`
(`any` union or `all` intersection).

### `hnf1b_search_variants`

Use to browse variants with server-side filtering and sorting by classification,
consequence, type, domain, gene, query text, or carrier count.

### `hnf1b_get_variant`

Use when you have a canonical `variant_id` or accepted `simple_id` and need the
variant record plus carrier counts and sampled carrier IDs.

### `hnf1b_get_gene_context`

Use for HNF1B reference context: coordinates, external references, transcripts,
protein domains, and optional exon details.

### `hnf1b_get_publications`

Use to list cached publications or reverse-lookup the individuals citing one
publication via `citing_pmid`.

### `hnf1b_get_publication_passages`

Use to retrieve ranked publication passages for a query, optionally filtered by
PMID or section and shaped by `mode` and `rerank`.

### `hnf1b_get_statistics`

Use for one aggregate cohort statistic at a time. Call with `dry_run=True` to
preview the metric and expected payload before fetching the data.

### `hnf1b_resolve_terms`

Use to resolve free text into controlled-vocabulary entries, especially HPO IDs
before phenotype searches.

### `hnf1b_compare_phenotypes`

Use for genotype-phenotype comparison across carrier cohorts for up to 10
variants, including observed, excluded, unknown, and recorded-rate fields.

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
hnf1b_get_statistics(metric="variant_types", dry_run=True)
  → {metric, available, estimated}
    ↓
hnf1b_get_statistics(metric="variant_types")
  → {metric, unit, result}   # unit states instances-per-carrier vs distinct
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
