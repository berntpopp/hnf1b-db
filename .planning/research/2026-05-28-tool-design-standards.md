# Tool / Agent-Design Standards (Anthropic + Google) → Fixes for the hnf1b-db MCP Server

**Date:** 2026-05-28
**Author:** research agent
**Scope:** Authoritative tool-design guidance from Anthropic and Google, mapped to the six concrete findings that earned the `hnf1b-db` MCP server a 5.6/10 from a consuming LLM. Opinionated, with exact target JSON shapes and a prioritized punch list to reach >9.

This document is **research + prescription only**. No code was changed.

---

## 0. Sources (every claim below cites one of these)

**Anthropic**
- [A1] Writing effective tools for AI agents — https://www.anthropic.com/engineering/writing-tools-for-agents
- [A2] Effective context engineering for AI agents — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

**Model Context Protocol (spec)**
- [M1] MCP — Server Tools spec (2025-06-18) — https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- [M2] MCP — Tools concept guide — https://modelcontextprotocol.info/docs/concepts/tools/

**Google**
- [G1] Function calling with the Gemini API (best practices) — https://ai.google.dev/gemini-api/docs/function-calling
- [G2] Vertex AI — Function calling with Gemini — https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/function-calling
- [G3] Gemini Enterprise Agent Platform — Introduction to function calling — https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/tools/function-calling
- [G4] Google Agent Development Kit (ADK) — Function tools — https://adk.dev/tools-custom/function-tools/

---

## 1. Cross-cutting principles where Anthropic and Google agree

These are the load-bearing agreements that the six fixes all derive from.

1. **The schema and descriptions ARE the contract the model reasons over.** Anthropic: "think of how you would describe your tool to a new hire... Avoid ambiguity by clearly describing (and enforcing with strict data models) expected inputs and outputs" [A1]. Google: "Be extremely clear and specific in your descriptions. The model relies on these to choose the correct function and provide appropriate arguments" [G1]. ADK: "a well-written and comprehensive docstring is crucial for the LLM to understand how to use the tool effectively" [G4]. **Implication:** capabilities prose that disagrees with real param names is worse than no prose — it actively mis-trains the model.

2. **Constrained values belong in enums, not prose.** Google is explicit: "If a parameter has a limited set of valid values, use an enum" — and this "is better than listing valid values in the description" [G1]; Vertex shows `"enum": ["celsius","fahrenheit"]` and says enums "constrain the model output and reduce errors" [G2]. Anthropic uses enums for `response_format` ("concise"/"detailed") [A1]. **Implication:** every filter with a fixed value set must be a JSON-Schema enum AND be re-stated in discovery.

3. **Errors must be actionable so the model self-corrects.** Anthropic: "prompt-engineer your error responses to clearly communicate specific and actionable improvements, rather than opaque error codes or tracebacks... give examples of correctly formatted tool inputs" [A1]. Google: "return informative error messages that the model can use to generate helpful responses" [G1]; ADK: "instead of returning a numeric error code, return a dictionary with an 'error_message' key containing a human-readable explanation" and "include a 'status' key" [G4]. **Implication:** `{"code":"invalid_input","message":"upstream rejected parameters"}` is a textbook anti-pattern.

4. **Return the smallest set of high-signal tokens.** Anthropic: identify "the smallest possible set of high-signal tokens that maximize the likelihood of some desired outcome" [A2] and offer a `response_format` enum so the agent controls "concise" vs "detailed" [A1]; restrict responses (Claude Code defaults to 25,000 tokens) via "pagination, range selection, filtering, and/or truncation with sensible default parameter values" [A1]. **Implication:** repeating `gene_symbol:"HNF1B"` ×25 and shipping a `uri` that is a pure function of `variant_id` is exactly the bloat this warns against.

5. **Structured output + output schema make results parseable and trustworthy.** MCP: structured results go in `structuredContent`, and an `outputSchema` enables "strict schema validation," "type information," and "guiding clients and LLMs to properly parse and utilize the returned data" [M1]. **Implication:** `total` must be authoritative and consistent with the rows; the detail tool must return the full record the schema promises.

6. **Tools should be focused/atomic but the *detail* tool must be authoritative.** MCP: keep operations "focused and atomic" [M2]; Anthropic: consolidate where it helps the agent (e.g., `get_customer_context`) [A1]. A detail/get tool's single job is to be the authoritative record — returning only carrier IDs from `get_variant` violates the "self-contained, robust... extremely clear with respect to their intended use" bar [A2].

---

## 2. Finding-by-finding mapping and prescription

Real param/field names below are taken from the current code:
`mcp/src/hnf1b_mcp/tools/variants.py`, `mcp/src/hnf1b_mcp/services/variants.py`,
`mcp/src/hnf1b_mcp/services/errors.py`, `mcp/src/hnf1b_mcp/services/capabilities.py`,
`mcp/src/hnf1b_mcp/services/shaping.py`.

### Finding 1 — Schema/doc mismatch; no enumerated valid values exposed

**Reality in repo.** `capabilities.py` advertises `hnf1b_search_variants` as *"Search variant records by gene, HGVS notation, **variant type**, or **ACMG class**"* and a workflow `hnf1b_search_variants(hgvs_c=...)`. But the real tool params are `query, variant_type, classification, gene, consequence, domain, page, page_size, sort, response_mode` — there is no `hgvs_c`, no `acmg_class`, and "ACMG class" is actually `classification` with values `PATHOGENIC | LIKELY_PATHOGENIC | UNCERTAIN_SIGNIFICANCE | LIKELY_BENIGN | BENIGN`. The reviewer who tried `variant_type='missense'` was misled — "missense" is a `consequence` value (`Missense`), not a `variant_type`.

**Standard.** Descriptions are what the model reasons over [A1][G1][G4]; enums beat prose for fixed value sets [G1][G2]. The capabilities/discovery tool is itself a tool whose output the model trusts — if it lies, the model mis-calls.

**Prescription.**
1. **Single source of truth.** The enums already exist (`VARIANT_CLASSIFICATION_VALUES`, `MOLECULAR_CONSEQUENCE_VALUES`, `VARIANT_TYPE_VALUES`, `PROTEIN_DOMAIN_VALUES` in the generated contract). Drive BOTH the JSON-Schema (via `Literal[...]`/enum types on the tool params) AND the discovery `filterable_fields` block from those same constants. Never hand-write the value lists in prose.
2. **Add a `filterable_fields` block** to `hnf1b_get_capabilities` keyed by tool, listing each filter's exact param name, type, enum values (or `free_text`), and a one-line hint. See appendix B.
3. **Delete the false advertising:** remove "ACMG class" and "HGVS notation"/`hgvs_c` wording; rename the summary to use the real param names. Fix the canonical workflow `hnf1b_search_variants(hgvs_c=...)` → `hnf1b_search_variants(query=..., classification=...)`.
4. **Express enums in the tool schema**, not just the docstring: type the params as enums so the JSON-Schema `inputSchema` carries `"enum": [...]` for `classification`, `consequence`, `domain`, and `response_mode`. (Today `classification`/`consequence`/`domain` are typed via `VariantClassification`/`MolecularConsequence`/`ProteinDomain` — good; ensure `variant_type` is likewise an enum sourced from `VARIANT_TYPE_VALUES` instead of free-form `str`, since a value set exists.)

### Finding 2 — Unhelpful errors

**Reality in repo.** `errors.py` `McpToolError` already supports `**details`, and `_validate_enum` in `variants.py` *does* attach `argument` + `choices`. So the *local* enum path is decent. The failing case was a server returning `{"code":"invalid_input","message":"upstream rejected parameters"}` — i.e., when the upstream REST API returns a 422 the MCP layer collapses it to an opaque message with **no field, no allowed values, no hint**. The model cannot self-correct from that.

**Standard.** Anthropic: errors must "clearly communicate specific and actionable improvements, rather than opaque error codes or tracebacks" and "give examples of correctly formatted tool inputs" [A1]. Google: "return informative error messages that the model can use" [G1]. ADK: human-readable `error_message`, never a bare code [G4]. MCP: tool execution errors go in the result with `isError: true` and descriptive content [M1][M2].

**Prescription.** Standardize ONE error envelope (extend the existing `to_envelope`) carrying: `code`, `field`, `message`, `allowed` (when a value set exists), `hint` (a concrete fix), and optionally `example`. Two upgrades:
1. **Local enum errors** already have `argument`+`choices`; rename to the agreed keys `field`+`allowed`, and add a `hint` that points at the *likely intended* field. Example: caller passes `variant_type='missense'` → hint `"'missense' is a consequence value; call again with consequence='Missense'"`. This is the single highest-leverage retry-saver.
2. **Upstream 422 passthrough.** When `ApiClient.get` receives a 422 from the REST API, parse the upstream FastAPI/JSON:API error body (`loc`, `msg`, `ctx.enum_values` / `detail[].loc`) and map it into the same envelope: set `field` from `loc[-1]`, `message` from upstream `msg`, `allowed` from the contract enum for that field if known, and a `hint`. Never emit "upstream rejected parameters" without a `field`. If the upstream body is unparseable, still echo `field: "unknown"` and include the raw upstream `detail` under `upstream_detail` so the model has *something* to reason over.

See appendix A for the exact shape.

### Finding 3 — Token efficiency (compact mode still bloated)

**Reality in repo.** `_shape_variant` emits 11 fields per row including `gene_symbol` (invariant — always "HNF1B") and `uri` = `f"hnf1b://variant/{variant_id}"` (a pure, deterministic function of `variant_id`). `compact` returned 25 fully-hydrated rows. `shaping.apply_budget` only trims whole rows when over the *char budget*; it never hoists invariants or drops derivable fields, so every row pays for `"gene_symbol":"HNF1B"` and a redundant `uri`.

**Standard.** "Smallest possible set of high-signal tokens" [A2]; offer a `response_format`/mode enum and use "filtering" + "truncation with sensible defaults" [A1]; avoid bloated outputs [A2]. A field that is constant across all rows, or computable from another field, is zero-signal repetition.

**Prescription — make shaping `response_mode`-aware with field policies:**
1. **Hoist invariant fields** to a single response-level `header`. `gene_symbol` (always HNF1B) and `data_class` move to `header`/`meta`; rows no longer repeat them. State the invariant once: `"header":{"gene_symbol":"HNF1B"}`.
2. **Drop deterministic-duplicate fields** from rows. `uri` is `hnf1b://variant/{variant_id}`; document the URI template once in `meta.uri_template` and omit per-row `uri`. The model (or client) can reconstruct it; it is pure duplication of `variant_id`.
3. **Per-mode field sets** (trim, don't just truncate):
   - `minimal`: `variant_id`, `label`, `classification` only.
   - `compact` (default): `variant_id`, `label`, `classification`, `consequence`, `carrier_count`. Drop `simple_id`, `hg38`, `transcript`, `protein`, `structural_type`, `uri`, hoisted `gene_symbol`.
   - `standard`: compact + `hg38`, `transcript`, `protein`, `structural_type`, `simple_id`.
   - `full`: everything including `recommended_citation` per row and the reconstructed `uri`.
4. Keep `apply_budget` row-trimming as the *final* safety net after field-trimming, and keep its `dropped_summary` so the model knows truncation happened (Anthropic: truncation should come "with guidance" [A1]).

Net effect for a 25-row compact page: from ~11 fields × 25 (incl. 25× `"HNF1B"` + 25× `uri`) down to 5 high-signal fields × 25 + one hoisted header. See appendix C.

### Finding 4 — Response consistency (`total:0` with 25 rows; undocumented sort)

**Reality in repo.** `search_variants` computes `total = meta.get("total") or meta.get("pagination",{}).get("total") or 0`. When the upstream aggregate endpoint puts the count somewhere else (or omits it), this silently falls to `0` while `data` still has 25 rows — exactly the inconsistency observed. `sort` is forwarded "as-is to the API" with no documented grammar or default.

**Standard.** MCP output schema exists to guarantee results "conform" and are correctly parsed [M1]; clear, unambiguous outputs [A1]. A `total` that contradicts the returned rows breaks the model's pagination reasoning.

**Prescription.**
1. **Authoritative total.** Resolve `total` from the real upstream location (inspect the JSON:API `meta`/`links` the aggregate endpoint actually returns) and assert the invariant: if `total == 0` but `len(variants) > 0`, that is a bug — fall back to a definitely-correct lower bound (`max(total, (page-1)*page_size + len(variants))`) and set `meta.total_estimated: true` rather than emit a contradictory `0`. Always include `has_more` (`page * page_size < total`) so the model paginates without guessing.
2. **Document and expose sort.** Add `sort` to the `filterable_fields`/discovery block with the allowed sort keys and the **default** sort order (e.g., `default_sort: "genomic_position:asc"`). Echo the effective sort back in `meta.sort` so the model can rely on ordering. Validate `sort` against the allowed keys and emit the standard `invalid_input` error (with `allowed`) on a bad key, instead of forwarding garbage upstream.

### Finding 5 — Detail tool not authoritative (`hnf1b_get_variant`)

**Reality in repo.** `get_variant` calls `PHENOPACKETS_BY_VARIANT_BY_VARIANT_ID` and returns ONLY `variant_id`, `carriers` (IDs), `carrier_count`, `uri`, `note`. It omits `classification`, `consequence`, `label`, HGVS (`hg38`/`transcript`/`protein`), domain — yet `capabilities.py` advertises it as *"Retrieve the **full record** for a single variant... including **all interpretation details** and associated individuals."* The discovery promise and the payload disagree (this also compounds Finding 1).

**Standard.** Tools must be "self-contained... extremely clear with respect to their intended use" [A2]; a `get_X` tool's contract is authority. MCP focused/atomic [M2] does not mean "thin" — it means "one clear job," and the job of a detail tool is the full record. Anthropic's consolidation guidance (`get_customer_context`) supports returning the full context in one call [A1].

**Prescription.** Make `hnf1b_get_variant` authoritative: return the full variant record (same canonical fields as the search row at `full` fidelity: `simple_id`, `variant_id`, `label`, `classification`, `consequence`, `structural_type`, `hg38`, `transcript`, `protein`, `domain`, `carrier_count`) PLUS the `carriers` ID list PLUS `recommended_citation` and `uri`. This needs a second upstream call to the variant-detail/all-variants record for the interpretation fields, merged with the carriers call — exactly the kind of multi-call consolidation Anthropic endorses [A1]. Keep the `note` pointing to `hnf1b_get_individuals` for deep carrier phenotype detail, but the variant's own classification/consequence/HGVS must live here. Define an `outputSchema` for this tool so the full shape is contractually validated [M1]. See appendix D.

### Finding 6 — Missing `recommended_citation`

**Reality in repo.** `capabilities.py` `_CITATION_CONTRACT` states *"Every response includes a recommended_citation field that should be pasted verbatim."* But `_shape_variant` and `get_variant` emit no `recommended_citation`. A `citation.py` service exists but is not wired into variant payloads. Contract violation.

**Standard.** Output must match the advertised schema [M1]; descriptions/contracts the model relies on must be true [A1][G1]. (Peer MCP servers in this same workspace — sysndd, genereviews-link — enforce "paste recommended_citation verbatim"; consistency matters.)

**Prescription.**
1. Wire `citation.py` into variant payloads. In `compact`/`standard`, put a single `recommended_citation` at the response/header level (it is invariant per dataset/version → hoist it, consistent with Finding 3). In `full` mode, additionally attach per-record `recommended_citation` for variants that have a distinct primary source.
2. Update the contract wording to match what is actually delivered per mode (e.g., "response-level in compact/standard; per-record in full"), so prose and payload agree.

---

## 3. Appendix — target shapes

### A. Improved `invalid_input` error envelope

Local enum mismatch (the model fixes it in ONE retry):

```json
{
  "schema_version": "1.0",
  "error": {
    "code": "invalid_input",
    "field": "variant_type",
    "message": "unknown value 'missense' for variant_type",
    "allowed": ["SNV", "DEL", "DUP", "INS", "INDEL", "CNV"],
    "hint": "'missense' is a molecular consequence, not a variant_type; call again with consequence='Missense'",
    "example": {"consequence": "Missense"}
  }
}
```

Upstream 422 mapped into the same envelope:

```json
{
  "schema_version": "1.0",
  "error": {
    "code": "invalid_input",
    "field": "classification",
    "message": "value not permitted by the data API",
    "allowed": ["PATHOGENIC", "LIKELY_PATHOGENIC", "UNCERTAIN_SIGNIFICANCE", "LIKELY_BENIGN", "BENIGN"],
    "hint": "use one of the allowed enum values (uppercase, underscore-separated)",
    "upstream_detail": [{"loc": ["query", "classification"], "msg": "value is not a valid enumeration member"}]
  }
}
```

### B. Capabilities `filterable_fields` block

```json
"filterable_fields": {
  "hnf1b_search_variants": {
    "classification": {
      "param": "classification",
      "type": "enum",
      "allowed": ["PATHOGENIC", "LIKELY_PATHOGENIC", "UNCERTAIN_SIGNIFICANCE", "LIKELY_BENIGN", "BENIGN"],
      "hint": "ACMG pathogenicity class (uppercase). This is the field the literature calls 'ACMG class'."
    },
    "consequence": {
      "param": "consequence",
      "type": "enum",
      "allowed": ["Missense", "Nonsense", "Frameshift", "Splice Donor", "Splice Acceptor", "Inframe Deletion", "Synonymous"],
      "hint": "Molecular consequence (title-case). 'missense' goes here, NOT in variant_type."
    },
    "variant_type": {
      "param": "variant_type",
      "type": "enum",
      "allowed": ["SNV", "DEL", "DUP", "INS", "INDEL", "CNV"],
      "hint": "Structural/sequence variant type. Not the same as consequence."
    },
    "domain": {
      "param": "domain",
      "type": "enum",
      "allowed": ["Dimerization Domain", "POU-Specific Domain", "POU Homeodomain", "Transactivation Domain"]
    },
    "gene": {"param": "gene", "type": "free_text", "hint": "Defaults to HNF1B; rarely needed."},
    "query": {"param": "query", "type": "free_text", "hint": "Free-text search across label/HGVS."}
  },
  "sort": {
    "param": "sort",
    "type": "enum",
    "allowed": ["genomic_position:asc", "genomic_position:desc", "carrier_count:desc", "classification:asc"],
    "default": "genomic_position:asc"
  }
}
```
(Note: `allowed` lists above are illustrative placeholders for the structure — populate them programmatically from `VARIANT_CLASSIFICATION_VALUES`, `MOLECULAR_CONSEQUENCE_VALUES`, `VARIANT_TYPE_VALUES`, `PROTEIN_DOMAIN_VALUES` so they cannot drift.)

### C. Compact-mode variant list (hoisted header + trimmed rows)

```json
{
  "header": {
    "gene_symbol": "HNF1B",
    "data_class": "curated",
    "uri_template": "hnf1b://variant/{variant_id}",
    "recommended_citation": "HNF1B-db (https://hnf1b-db...), accessed 2026-05-28. doi:..."
  },
  "variants": [
    {"variant_id": "HNF1B:c.494G>A", "label": "p.Arg165His", "classification": "PATHOGENIC", "consequence": "Missense", "carrier_count": 12},
    {"variant_id": "HNF1B:c.544+1G>T", "label": "splice donor", "classification": "PATHOGENIC", "consequence": "Splice Donor", "carrier_count": 7}
  ],
  "total": 318,
  "page": 1,
  "page_size": 25,
  "has_more": true,
  "meta": {
    "response_mode": "compact",
    "sort": "genomic_position:asc",
    "effective_chars": 412,
    "fields_trimmed": ["simple_id", "hg38", "transcript", "protein", "structural_type", "uri", "gene_symbol"]
  }
}
```

### D. Authoritative `hnf1b_get_variant` payload (full)

```json
{
  "variant_id": "HNF1B:c.494G>A",
  "simple_id": "v_0494ga",
  "label": "p.Arg165His",
  "gene_symbol": "HNF1B",
  "classification": "PATHOGENIC",
  "consequence": "Missense",
  "structural_type": "SNV",
  "domain": "POU-Specific Domain",
  "hg38": "chr17:g.37741123C>T",
  "transcript": "NM_000458.4:c.494G>A",
  "protein": "NP_000449.1:p.Arg165His",
  "carrier_count": 12,
  "carriers": ["PPKT:0001", "PPKT:0042", "PPKT:0117"],
  "uri": "hnf1b://variant/HNF1B:c.494G>A",
  "recommended_citation": "HNF1B-db (https://hnf1b-db...), variant HNF1B:c.494G>A, accessed 2026-05-28.",
  "note": "Call hnf1b_get_individuals with `carriers` ids for authoritative per-carrier phenotype detail.",
  "data_class": "curated",
  "meta": {"response_mode": "full", "effective_chars": 0}
}
```

---

## 4. Prioritized punch list (highest LLM-experience impact first) — 5.6 → >9

1. **[P0] Fix the discovery/schema lies (Finding 1 + 5 + 6 prose).** Rewrite `hnf1b_search_variants`/`hnf1b_get_variant` capability summaries and the canonical workflow to use real param names; remove "ACMG class"/`hgvs_c`. Single biggest trust repair — the model currently calls non-existent params. *(Touches `capabilities.py`.)*
2. **[P0] Add the `filterable_fields` block** to `hnf1b_get_capabilities`, generated from the contract enum constants (Finding 1). Gives the model the exact param-name + enum map up front → near-zero wasted calls.
3. **[P0] Actionable errors + upstream-422 passthrough** (Finding 2). Adopt the `field/message/allowed/hint/example` envelope; map upstream 422 `loc/msg` into it; add the `variant_type`→`consequence` hint. Converts multi-retry flailing into one self-corrected retry.
4. **[P1] Make `hnf1b_get_variant` authoritative** (Finding 5). Merge the variant-detail call with the carriers call; return classification/consequence/label/HGVS/domain + carriers + citation; define `outputSchema`.
5. **[P1] Fix `total` + expose sort** (Finding 4). Authoritative `total`, `has_more`, `meta.sort`, documented `default_sort`; never return `total:0` alongside rows.
6. **[P2] response_mode-aware field trimming + hoisting** (Finding 3). Per-mode field sets; hoist `gene_symbol`/`data_class`/`recommended_citation`/`uri_template` to `header`; drop per-row `uri`; keep `dropped_summary`. Big token win, lower correctness risk than 1–5.
7. **[P2] Wire `recommended_citation` into variant payloads** (Finding 6) and align the contract wording to per-mode delivery.
8. **[P3] Eval harness** (cross-cutting, [A1]): build a dozen+ prompt/response pairs (e.g., "find pathogenic missense variants", "get full record for HNF1B:c.494G>A") with verifiable outcomes; track tool-call count, retries, token consumption, and tool errors to lock in and regression-guard 1–7.
