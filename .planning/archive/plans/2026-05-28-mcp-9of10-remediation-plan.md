# MCP "9/10 on every tool" remediation plan

Branch: `feat/mcp-server` (continues PR #317). One PR, CI green, golden-verified
against the local docker stack (hnf1b_db:5433, hnf1b_api:8000, hnf1b_mcp:8788).

Target: every factor and every tool ≥ 9/10 in the LLM-consumer usage reports.

## Classification (vs current HEAD)

ALREADY FIXED (stale-deploy artefacts, no code change): C1 empty-phenotype full
cohort (commit 4c7916e); `effective_chars: 0` (safe_tool computes real length).

DATA/DEPLOYMENT (gene_context empty): backend the live MCP pointed at was only
partially seeded. Code is correct → add MCP hardening + document seeding.

REAL CODE DEFECTS — fix:

### Backend (full scope, approved)
- B1. New migration: rebuild `global_search_index` MV so the variant branch
  emits the **resolvable VRS descriptor id** (`vd->>'id'`) not `md5(label)`, and
  the phenopacket branch indexes **`phenopacket_id`** (so `phenopacket-596` is
  searchable). Dedup variants on descriptor id. Exclude synthetic `e2e-%`
  phenopackets from both branches.
- B2. Defense-in-depth synthetic-record exclusion in MCP-facing **public**
  aggregation + search paths only (NOT single-record public GET): shared
  `SYNTHETIC_PHENOPACKET_EXCLUSION` constant applied in the public branch of
  `PhenopacketSearchRepository.search/count`, the aggregation public-filter
  fragment, and summary. Single-record `GET /phenopackets/{id}` stays unchanged
  so the e2e lifecycle self-check still works.
- B3. `summary.distinct_publications` → align to PMID-only (matches
  `get_publications.total`) and add explicit unit; keep `distinct_sources` too.
- B4. (handled MCP-side) percentage float rounding.

### MCP layer
- M1. `search` single-type casing: `_TYPE_TOKEN` emits Phenopacket/Variant/
  Publication/Gene. Add per-hit `resolve_with` {tool, id/arg} so the
  search→get chain is explicit and never severed.
- M2. `get_individual` response_mode: map mode→include_* so minimal/compact
  actually trim. Per-mode field projection.
- M3. `get_individuals`: add `requested` + `not_found` array (batch path).
- M4. `find_individuals_by_phenotype`: real `total` = full match count +
  `has_more`; honest cap disclosure; multi-HPO OR documented + `match` echo.
- M5. `search_variants`: translate `carrier_count`→`individualCount` sort key;
  echo `applied_sort` / `ignored_params` in meta (extend build_meta).
- M6. `resolve_terms`: `_map_vocab_item` id falls back to `value` (fixes sex).
- M7. publications: expose `sort` (default `-phenopacket_count`, documented);
  mode-aware `_shape_publication` drops redundant journal/year in
  minimal/compact (citation string already contains them).
- M8. statistics: label variant-metric unit (instances vs distinct) + optional
  `count_mode`; round percentages; survival budget degrades resolution before
  dropping a whole arm (+ disclose dropped arms by name).
- M9. error envelope: ErrorEnvelopeMiddleware maps pydantic/FastMCP validation
  errors → clean `{schema_version,error,is_error}` with field+allowed+hint.
- M10. api_client: not_found message no longer leaks the internal route path
  (path moved to non-surfaced detail).
- M11. meta: `effective_chars` counts the full envelope; add
  `total_available_chars` + `truncated` when a budget trims.
- M12. reference: apply_budget to transcripts/domains; capabilities/gene note
  that domain enum is the catalog and live availability depends on seeded data.
- M13. capabilities + tool_guide: fix doc drift (publications params q/citing_pmid,
  not "PMID list"; gene_context wording; search scope; multi-HPO OR; sort docs;
  canonical workflows use real chains).

## Verification
- `make -C mcp check` (ruff + mypy + pytest) green.
- New unit tests for every MCP behavior change.
- Backend: migration applies + downgrades; new search tests; pytest for changed
  modules.
- Live golden: apply migration to docker DB, REFRESH MV, exercise all 11 tools.
