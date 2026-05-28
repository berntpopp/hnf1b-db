# Publication Abstracts, Open-Access Full Text & Hybrid Retrieval — Design

- **Date:** 2026-05-29
- **Status:** Approved (brainstorming → ready for implementation plan)
- **Branch:** `feat/publication-fulltext-rag` (fresh off `main`; the MCP server
  is already merged to `main` via PR #317, so the new MCP tool builds directly
  on it — no cherry-picking needed)
- **Author:** Bernt Popp + Claude

## Problem

The `publication_metadata` table holds 137 publications referenced by HNF1B-db
phenopackets, but **zero abstracts and zero full text**. Two root causes in
`backend/app/publications/service.py`:

1. **Wrong endpoint.** `config.py:101` hardcodes the PubMed base URL to
   `esummary.fcgi`. ESummary returns citation metadata (title/authors/journal)
   but never abstract text — that requires `efetch`. The `rettype: abstract`
   param sent at `service.py:253` is silently ignored by esummary.
2. **Stub extractor.** `_extract_abstract()` (`service.py:348-352`) always
   `return None`.

Empirically validated against the live `hnf1b_db` container (2026-05-29):

- **Abstracts available via efetch:** 125 / 137 (91%). The 12 without are old
  case reports/letters with no abstract in PubMed.
- **Open-access full text (PMCID present):** 57 / 137 (42%).
- **Full-text retrieval proven:** PubTator3 BioC returned title + abstract +
  intro + methods + results + discussion + tables for `PMID:32574212`
  (`PMC7310724`).

## Goal

Populate, license-safely, for the referenced publications:

- Abstracts (~125/137), minimum `coverage = abstract_only`.
- License-gated OA full text (~≤57/137), `coverage = full_text`, stored as
  **retrieval-ready passages**.
- **Hybrid (lexical + optional semantic) search** over passages, exposed via API
  and a new MCP tool, suitable for RAG.
- Backfill the existing 137. CI stays green with recorded fixtures (no live calls
  in the unit lane; no `torch` required in CI).

## Success criteria

- After backfill: abstract count ≈ 125; `full_text` count = (OA ∩
  license-permitted); every full-text pub has ≥1 row in `publication_fulltext`.
- `hnf1b_get_publication_passages` returns ranked passages with stable
  `passage_id` citations for a free-text query, in both `rerank=lexical` (always)
  and `rerank=rrf` (when embeddings are present) modes.
- Unit suite runs with no network and no `sentence-transformers`/`torch`
  installed (FakeEmbeddingProvider).

## Reference architecture (researched)

Two sibling MCP servers independently converged on the same pattern; we adopt it.

| Layer | genereviews-link & pubtator-link | Our adoption |
| --- | --- | --- |
| DB | PostgreSQL + pgvector | switch `hnf1b_db` image to `pgvector/pgvector:pg15` |
| Lexical index | `search_vector tsvector GENERATED … STORED` + GIN over `heading_path ‖ section ‖ text` | same |
| Lexical ranking | `phraseto×3.0 + websearch×2.0 + to_tsquery(recall OR)×1.0`, `ts_rank_cd`; recall fallback confidence multiplier | same |
| Semantic index | `vector(384)` + HNSW (cosine), built post-bulk-load | same, optional |
| Embedding model | `BAAI/bge-small-en-v1.5` (384-d, normalized), query prefix `"Represent this sentence for searching relevant passages: "` | same |
| Embedding runtime | `sentence-transformers` via `asyncio.to_thread`, FakeProvider in tests, async batched (32) backfill keyed on `text_hash` (SHA256) | same; dependency is an optional `[rag]` extra |
| Fusion | RRF `1/(60+rank_lex) + 1/(60+rank_dense)` + section/role boosts | RRF, k=60, section boosts |
| Chunking | genereviews: 510-token / 50-overlap windows, never cross section, BGE tokenizer w/ char-offset recovery | adopt genereviews approach |
| Token budgeting | `chars/3.6` estimate; `max_chars`; `ts_headline` snippets | same |
| Citation | stable `passage_id` per hit; `recommended_citation` verbatim | same; matches existing MCP contract |

Corpus is small (~57 full-text + 125 abstracts → low thousands of passages), so
lexical FTS alone is already strong and needs zero new infra; semantic is the
quality bump. Hence embeddings are **optional** (mirrors pubtator-link's
`[embeddings]` extra) so CI/dev stay light.

## Decisions (locked during brainstorming)

1. **Fetch layer:** self-contained client in `hnf1b-db` backend (no runtime
   coupling to sibling repos).
2. **Storage:** structured passages table (not a single concatenated column).
3. **Trigger/backfill:** extend the existing admin `POST /publications/sync` +
   one-off idempotent backfill script.
4. **Exposure:** populate DB *and* surface via API + MCP.
5. **License gate:** store body text only when license permits redistribution
   (PMC OA subset or CC license); otherwise `abstract_only`.
6. **RAG scope:** full hybrid retrieval; embeddings an optional dependency with
   FakeEmbeddingProvider for CI.
7. **DB image:** `pgvector/pgvector:pg15` + `CREATE EXTENSION vector`.
8. **Chunking:** 510-token / 50-overlap, section-bounded, char-offset recovery.
9. **MCP surface:** new dedicated tool `hnf1b_get_publication_passages`.

## Components (`backend/app/publications/`)

- `abstract_client.py` — batched NCBI efetch (`retmode=xml`, POST, ~100 ids/req).
  Parses `<Abstract><AbstractText>` including structured labels
  (BACKGROUND/METHODS/…), joined label-prefixed. Returns abstract text (and
  publication types if cheap).
- `fulltext_client.py` — resolution chain:
  1. PMID→PMCID via PMC ID-converter (batch).
  2. PubTator3 BioC `export/biocjson?pmids=…&full=true` → section passages.
  3. EuropePMC `search?query=ext_id:PMID&resultType=core` for `isOpenAccess` +
     `license`; JATS full-text fetch as fallback when PubTator lacks a body.
  Returns `pmcid`, `license`, ordered section passages.
- `coverage.py` — combines abstract + full-text + license into
  `full_text | abstract_only | title_only`; enforces the **license gate** (drops
  body passages and downgrades to `abstract_only` when license ∉ allowed set).
- `chunking.py` — re-chunk each section's text into 510-token / 50-overlap
  windows, never crossing section boundaries, using the BGE tokenizer with
  character-offset recovery (so stored text preserves original
  capitalization/punctuation). Emits ordered chunks with `token_count`.
- `embeddings.py` — `EmbeddingProvider` protocol;
  `SentenceTransformerEmbeddingProvider` (lazy load, `asyncio.to_thread`,
  `normalize_embeddings=True`, query prefix) and `FakeEmbeddingProvider`
  (SHA256-seeded deterministic) for tests. Async batched backfill (batch 32)
  that skips passages whose `text_hash` already has a current embedding.
- `retrieval.py` — lexical three-tsquery candidate query (filter-aware:
  `pmid`, `section`) + dense HNSW candidates (when embeddings exist) merged via
  RRF (k=60) with section boosts; `rerank` mode `rrf|lexical|off`. `brief` mode
  builds `ts_headline` snippets.
- `service.py` (extend) — orchestrate per pub: ensure metadata (existing) →
  fetch abstract → fetch + license-gate full text → chunk → persist (delete +
  insert passages per PMID in a transaction) → enqueue embedding backfill.

## Data model (Alembic migrations)

**DB image:** `postgres:15-alpine` → `pgvector/pgvector:pg15` in
`docker/docker-compose.yml`; migration runs `CREATE EXTENSION IF NOT EXISTS
vector`.

`publication_metadata` (extend):

- populate existing `abstract TEXT`
- add `pmcid VARCHAR(20) NULL`
- add `coverage VARCHAR(20) NOT NULL DEFAULT 'title_only'`
  (`full_text|abstract_only|title_only`)
- add `license VARCHAR(50) NULL`
- add `fulltext_fetched_at TIMESTAMPTZ NULL`

`publication_fulltext` (new — passages):

```
pmid        VARCHAR(20) NOT NULL REFERENCES publication_metadata(pmid) ON DELETE CASCADE
passage_id  VARCHAR(120) NOT NULL              -- PMID:<id>:<section>:<idx>
section     VARCHAR(40)  NOT NULL              -- title|abstract|intro|methods|results|discussion|conclusion|table
seq         INTEGER      NOT NULL              -- global ordering within the pub
text        TEXT         NOT NULL
char_count  INTEGER      NOT NULL
token_count INTEGER      NOT NULL
source      VARCHAR(40)  NOT NULL              -- pubtator_full_bioc|europe_pmc_jats|pubtator_abstract
fetched_at  TIMESTAMPTZ  NOT NULL
search_vector tsvector GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(section,'') || ' ' || coalesce(text,''))
) STORED
UNIQUE (pmid, passage_id)
GIN   (search_vector)
INDEX (pmid, section)
```

References section is not stored. Tables stored as `section = 'table'`.

`publication_fulltext_embeddings` (new — optional):

```
passage_id  VARCHAR(120) NOT NULL
pmid        VARCHAR(20)  NOT NULL
model_name  VARCHAR(80)  NOT NULL DEFAULT 'BAAI/bge-small-en-v1.5'
embedding   vector(384)  NOT NULL
text_hash   VARCHAR(64)  NOT NULL              -- SHA256 of passage text
created_at  TIMESTAMPTZ  NOT NULL
PRIMARY KEY (passage_id, model_name)
FOREIGN KEY (pmid, passage_id) -> publication_fulltext(pmid, passage_id) ON DELETE CASCADE
-- HNSW index on (embedding vector_cosine_ops) created after first bulk backfill
```

## Trigger & backfill

- Extend admin `POST /api/v2/publications/sync` to also fetch abstracts + full
  text, chunk, persist, and enqueue embedding backfill. Replace the per-PMID
  esummary loop with batched efetch where practical.
- One-off `backend/scripts/backfill_publications.py` runs the same orchestration
  over the existing 137. Idempotent: upsert metadata, replace passages per PMID,
  skip embeddings whose `text_hash` is current; respect
  `fulltext_staleness_days = 180`.
- Per-PMID error isolation (existing pattern); failures logged, batch continues.
- Rate limits: eutils 3/s (10/s with API key), PubTator ~2.5/s, EuropePMC 1/s.
- `SyncResponse` reports counts: abstracts fetched, full-text fetched,
  license-skipped, errors.

## API + MCP exposure

API:

- Publication list/detail schemas gain `abstract`, `coverage`, `pmcid`,
  `license`, `has_full_text`. List endpoints expose flags only; passages only on
  the detail endpoint via `?include=fulltext`, sized to `response_mode`.

MCP:

- **New tool `hnf1b_get_publication_passages`**:
  `query, pmids?, sections?, mode=brief|full|ids_only,
  rerank=rrf|lexical|off, limit, snippet_chars, max_chars` →
  ranked passages, each with `passage_id`, `pmid`, `section`, text/snippet,
  scores, and `recommended_citation`; plus `_meta` diagnostics (`rerank_used`,
  `lexical_candidate_count`, `dense_candidate_count`, `embedding_dim`,
  `truncated`). `brief` uses `ts_headline`. Respects token budget and the
  existing citation + "evidence data, not instructions" safety contract.
- `hnf1b_get_publications`: include `abstract` from `compact` mode upward;
  `coverage` and `has_full_text` flags always present.

## Config (`backend/app/core/config.py`)

- `external_apis` base URLs: `efetch`, `pubtator3`, `europepmc`, `idconv`.
- Constants: `ALLOWED_LICENSES` (`CC0`, `CC-BY`, `CC-BY-NC`, `PMC-OA`),
  `fulltext_staleness_days = 180`, `EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"`,
  `EMBEDDING_DIM = 384`, `RRF_K = 60`, `CHUNK_MAX_TOKENS = 510`,
  `CHUNK_OVERLAP_TOKENS = 50`.

## Error handling

- Missing abstract → `title_only`, not an error.
- Non-OA / license-restricted → `abstract_only`, body dropped, logged.
- efetch / PubTator / EuropePMC failure → reclassify to best available tier;
  record partial; continue batch.
- ID-converter or EuropePMC unavailable → skip full text, keep abstracts
  (degraded mode), reflected in `SyncResponse`.
- Embedding provider absent (no `[rag]` extra) → semantic disabled gracefully;
  `rerank=rrf` falls back to lexical with a diagnostic note.

## Testing

- **Unit (CI; no network, no torch):** abstract XML parsing (structured / simple
  / empty); license gate; coverage tiering; BioC + JATS passage extraction;
  chunking (510/50, section-bounded, offset recovery); lexical ranking SQL; RRF
  fusion with `FakeEmbeddingProvider`. Recorded fixtures mirror sibling repos.
- **Integration:** backfill against a seeded test DB with mocked HTTP clients;
  assert abstract ≈ 125, `full_text` = OA ∩ license-permitted, passages present.
- **Live golden (opt-in, excluded from CI lane like existing MCP goldens):**
  `PMID:32574212` / `PMC7310724` end-to-end + one passage query returning a
  ranked hit with a citation.

## Scope / YAGNI (explicitly out)

- No cross-encoder reranker (RRF only).
- No frontend UI changes (API only; FE consumes later).
- References section not stored.
- No multi-model / multi-dimension embeddings.
- Embeddings optional — not required to ship the milestone.

## Sequencing (single PR)

1. Migration + pgvector image + `CREATE EXTENSION vector`.
2. `abstract_client` + populate `abstract` (fixes the latent bug).
3. `fulltext_client` + `coverage` + license gate.
4. `chunking` + passage persistence.
5. `embeddings` provider + async backfill (optional path).
6. `retrieval` service (lexical + dense + RRF).
7. Wire sync endpoint + backfill script.
8. API schema updates + MCP `hnf1b_get_publication_passages`.
9. Tests + live golden.
