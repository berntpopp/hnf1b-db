# Handoff — HNF1B MCP "to 10/10" fixes (continuation)

**Branch:** `fix/mcp-10of10-statistics-compare-enums` (off `main`)
**Goal:** Take the HNF1B-db MCP from ~8.7/10 to 10/10 by fixing the QA findings
B1–B7 + Rec1–5 + the workflow's NEW-1/NEW-2/NEW-3, then open one PR with CI green.

## Decisions already made (locked — do not re-ask)
1. **Scope = MCP + backend** (fix B1 kidney-stages SQL and B6 KM CI at source).
2. **Reshape compare; keep `percentage`** — compare_phenotypes reshaped (alias+tuple),
   but B3 is ADDITIVE (`prevalence_*` added, `percentage` untouched → no REST/frontend break).
3. **Both Rec4 + Rec5** in scope (Rec4 = gated Fisher; Rec5 = docstring→resource + version hash).

## DONE (committed on the branch, newest first)
- `4a15bdd` idempotentHint on all 13 tools; document hnf1b_search response_mode inert (NEW-3)
- `d14f599` backend: kidney-stages query rewrite (B1) + KM CI collapse-at-S=0 (B6) + tests
- `369bde3` get_individuals batch preserves requested id order (B4)
- `4e9a44e` statistics honesty: by_feature prevalence + unit_note (B3), publications_timeline
  unit_note (B5), kidney_stages empty-result guard (B1 MCP side), KM CI scrub (B6 MCP guard)
- `1026f90` compare_phenotypes: shared variant resolver + `unmatched_variant_ids` (B2/Rec3,
  also refactors get_variant), response_mode + apply_budget (NEW-1), alias+`[obs,exc,unk,rate]`
  tuple cells (Rec1), `observed_rate_among_recorded` + `annotation_completeness` (Rec2),
  gated pure-Python Fisher `include_stats` (Rec4)
- `f829053` schema-visible Literal enums: response_mode/mode/rerank/genome_build (B7)

All MCP unit tests green (432 passed at last run); backend survival + aggregations tests green
(50 passed). `cd mcp && uv run mypy src/` clean; `ruff check`/`ruff format` clean on both packages.

## REMAINING work (do these, in order)
1. **NEW-2 — capabilities size-as-data.** In `mcp/src/hnf1b_mcp/services/capabilities.py::get_capabilities`,
   emit `descriptor_chars = len(json.dumps(descriptor, sort_keys=True, default=str))` as a real
   field (approx; note it in the docstring) and DELETE the stale magic numbers:
   - the `(~9k char)` comment at capabilities.py ~line 508
   - `~11k` in `mcp/src/hnf1b_mcp/server.py` `SERVER_INSTRUCTIONS` (lines 42–43) — reference
     "see meta/descriptor_chars" instead of a hardcoded size
   - the capabilities **tool** docstring in `mcp/src/hnf1b_mcp/tools/capabilities.py` (any `~11k`/`~9k`)
   Add a grep-guard test asserting no source string hardcodes a `~9k`/`~11k` capabilities size.
2. **Rec5 — tool-guide cache-skip infra (SAFE part).** The resource already exists:
   `hnf1b://schema/tool-guide` → `mcp/src/hnf1b_mcp/resources/tool_guide.md` (loader:
   `services/resources.py`; server wiring: `server.py:300-307`). Add a `tool_guide_version`
   content-hash (sha256(body)[:16], mirroring `capabilities_version`) exposed in the
   capabilities descriptor so a warm client can skip re-reading the guide. Add tests:
   `tool_guide_version` is a content hash and is advertised in capabilities; the guide has a
   section per registered tool name.
   - **DEFER (do NOT do unless explicitly asked):** the aggressive trim of all 13 tool
     docstrings into tool_guide.md. Verified risk: removing chaining/truncation field names
     (`resolve_with`, `carriers_truncated`, `unmatched_variant_ids`, etc.) that agents parse at
     runtime, for a "low"-severity token saving. Note this deferral in the PR body.
3. **outputSchema (BP, optional stretch).** Synthesis flagged authored outputSchemas for the
   high-traffic chained tools (get_variant, get_individual(s), search, compare_phenotypes) as the
   biggest unrealized best practice. Large/separable — only attempt if time allows; otherwise
   defer to a follow-up and say so. FastMCP exposes `tool.output_schema`.
4. **Final verification + PR.**
   - `cd mcp && uv run ruff format . && uv run ruff check . && uv run mypy src/ && uv run pytest -n auto -q -m "not smoke and not live"`
   - `cd backend && uv run ruff format <changed files> && uv run ruff check <changed> && uv run pytest tests/test_survival_analysis.py tests/test_aggregations_endpoints.py -q`
   - Contract drift guard: `cd mcp && uv run python scripts/gen_contract.py && git diff --exit-code -- src/hnf1b_mcp/contract/_generated_paths.py src/hnf1b_mcp/contract/_generated_enums.py`
   - Push branch, open PR; in the PR body, map fixes → B1–B7/Rec1–5/NEW-1..3 and note the
     two deferrals (Rec5 docstring-trim; outputSchema if not done). Watch GitHub Actions until
     the **CI gate** check is green; main requires it.

## Gotchas (verified this session)
- MCP CI job runs `ruff check` + `mypy` + `pytest` + a contract drift guard on
  `_generated_paths.py`/`_generated_enums.py` only — it does NOT run `ruff format --check`
  (still run `ruff format` for cleanliness). `_generated_models.py` drift is intentionally NOT
  gated (datamodel-codegen flakiness).
- **Backend CI DOES run `ruff format --check`** — always `cd backend && uv run ruff format <files>`
  before pushing backend changes. Backend tests enforce docstrings on public test methods (D102).
- MCP sidecar has **no scipy/numpy** — keep Fisher (Rec4) pure-Python.
- compare_phenotypes resolves ids via `variants.build_variant_id_index` (one cached all-variants
  page); tests must mock `/phenopackets/aggregate/all-variants` before `/phenopackets/by-variant/{id}`.
- `run_tool` (services/safe_tool.py) hoists `_meta`/`_dropped`; top-level data fields like
  `unmatched_variant_ids` survive — keep signals top-level, not under `_meta`, when they're data.

## Full review context
Workflow synthesis (8 agents, B1–B7+Rec1–5 validated against code + Anthropic/Google research):
`/tmp/claude-1000/-home-bernt-popp-development-hnf1b-db/38673241-bb59-4184-ad8e-d078957fd4f2/tasks/wtlqc5lbd.output`
(may be GC'd; the `fixes[]` + `scorecard_to_10` + `decisions_for_user` blocks are the spec.)
