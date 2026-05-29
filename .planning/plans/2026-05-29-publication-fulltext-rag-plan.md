# Publication Full-Text RAG — Implementation Plan

Derived from `docs/superpowers/specs/2026-05-29-publication-fulltext-rag-design.md`.
Branch: `feat/publication-fulltext-rag`. Single PR. Autonomous execution.

## Ground-truth facts (verified against the repo, 2026-05-29)

- Backend tests run against **real PostgreSQL** (CI spins a service container,
  runs `alembic upgrade head`, then pytest). So the migration runs in CI →
  `CREATE EXTENSION vector` + `vector(384)` require the image to be
  `pgvector/pgvector:pg15`. `tsvector GENERATED` is core PG and needs nothing.
- 4 image references to switch: `docker/docker-compose.yml:18`,
  `docker/docker-compose.dev.yml:21`, `.github/workflows/ci.yml:23` (test job),
  `.github/workflows/ci.yml:211` (e2e job). The npm overlay inherits the base.
- CI installs only `--group dev --group test` → `sentence-transformers`/`torch`
  absent. The `[rag]` extra is never installed in CI. FakeEmbeddingProvider only.
- Current Alembic head: `d4e9c1a2b3f5` → new migration's `down_revision`.
- Publications router: prefix `/api/v2/publications`, aggregates
  `list_route` (`GET /`), `metadata_route` (`GET /{pmid}/metadata`, live PubMed),
  `sync_route` (`POST /sync`, admin). List + new passages endpoint are **public**.
- Service layer is **raw SQL via `text()`**, not ORM. Mirror that style.
- pytest markers live in `backend/pytest.ini` (`slow`, `benchmark`, `network`).
  Main lane: `-m "not benchmark and not network"`. A separate lane runs
  `-m network`. Live golden tests gate via `skipif(env)` (always skipped in CI).
- HTTP mocking: separate **pure parse fns** (fixture-tested, no HTTP) from thin
  I/O wrappers (dependency-injected fakes / AsyncMock).
- The **PMC ID-converter URL in the spec is stale** — live endpoint is
  `https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/`.
- BioC `section_type` taxonomy (verified): TITLE/ABSTRACT/INTRO/METHODS/RESULTS/
  DISCUSS/CONCL/TABLE (+ skip REF/SUPPL/FIG). EuropePMC: `isOpenAccess:"Y"`,
  `license:"cc by"`.
- FE reads only `phenopacket_count` from list rows → additive fields are safe.
  Spec scope = no FE changes (verify no regression only).

## Module layout — `backend/app/publications/fulltext/`

Shared contract in `types.py` (foundation). Leaf modules import only from
`types`, stdlib, and already-installed third-party.

| Module | Pure (unit, fixtures) | I/O / DB (integration) |
| --- | --- | --- |
| `abstract_client.py` | `parse_efetch_xml` | `fetch_abstracts` (efetch batch) |
| `fulltext_client.py` | `parse_bioc`, `parse_europepmc_core`, `parse_jats`, `parse_idconv` | `resolve_pmcids`, `fetch_bioc`, `fetch_europepmc`, `fetch_jats` |
| `coverage.py` | `normalize_license`, `classify_coverage` (license gate) | — |
| `chunking.py` | `chunk_section` (510/50, section-bounded, offset recovery) + tokenizer fallback | — |
| `embeddings.py` | `FakeEmbeddingProvider`, provider protocol, `get_embedding_provider` | `backfill_embeddings` (test DB + Fake) |
| `rrf.py` | `rrf_fuse` (k=60 + section boosts) | — |
| `persistence.py` | — | `replace_passages`, metadata upsert helpers |
| `retrieval.py` | — | `search_passages` (lexical 3-tsquery + dense HNSW + RRF) |
| `orchestrator.py` | — | `process_publication` (glue for sync + backfill) |

## Stages

- **A (foundation, me):** branch, config, migration, pgvector image swap (4
  refs), `[rag]` extra + mypy overrides, `pytest.ini` `live` marker, conftest
  mutable-tables, `fulltext/__init__.py` + `types.py`, fixtures. One commit, CI-green.
- **B (workflow fan-out, TDD):** parallel agents implement the pure leaf modules
  + unit tests (abstract_client, fulltext_client, coverage, chunking, embeddings,
  rrf). Each owns disjoint new files; imports only `types`.
- **C (integration, me):** `persistence.py`, `retrieval.py` (DB SQL),
  `orchestrator.py`; extend `service.py` + `sync_route` (SyncResponse counts);
  new public `GET /api/v2/publications/passages` endpoint + schemas; extend list
  SELECT + schemas (`coverage`,`has_full_text`,`pmcid`,`license`,`abstract`);
  `scripts/backfill_publications.py` + Makefile target; integration tests.
- **D (MCP):** regen OpenAPI snapshot → `make contract`; allowlist
  `/publications/passages`; `services/publication_passages.py`,
  `tools/publication_passages.py`, register, capabilities `_TOOLS` +
  `_filterable_fields`; mocked + live tests. Reuse `build_pmid_citation_map`
  for `recommended_citation`.
- **E (verification):** swap local docker DB → pgvector, recreate, migrate;
  `make check` (backend) green on test DB; backfill subset + golden PMID 32574212;
  rebuild api+mcp; curl API; Playwright FE smoke (no regression); MCP pytest +
  contract drift; live golden.
- **F (review + PR):** adversarial multi-dimension review workflow; fix; push;
  open PR; CI green.

## Data model (migration `*_publication_fulltext_rag`, down_revision d4e9c1a2b3f5)

- `CREATE EXTENSION IF NOT EXISTS vector`.
- `publication_metadata` += `pmcid`, `coverage NOT NULL DEFAULT 'title_only'`
  (CHECK), `license`, `fulltext_fetched_at`.
- `publication_fulltext` (PK `(pmid,passage_id)`, generated `search_vector`
  tsvector, GIN, `(pmid,section)` index, FK→metadata ON DELETE CASCADE).
- `publication_fulltext_embeddings` (PK `(passage_id,model_name)`,
  `vector(384)`, `text_hash`, composite FK→fulltext ON DELETE CASCADE, HNSW
  `vector_cosine_ops`).

## passage_id format
`<PMID:bare>:<section>:<per-section-idx>` (≤120 chars), e.g. `PMID:32574212:methods:3`.
`seq` = global 0-based order within the pub.

## API: `GET /api/v2/publications/passages` (public)
Params: `q` (required), `pmids` (csv), `sections` (csv), `rerank=rrf|lexical|off`,
`mode=brief|full|ids_only`, `limit`, `snippet_chars`, `max_chars`.
Returns ranked passages (`passage_id,pmid,section,seq,text|snippet,scores`) +
`_meta` (`rerank_used,lexical_candidate_count,dense_candidate_count,embedding_dim,truncated`).

## License gate (fail-closed)
Keep body passages only when normalized license ∈ {CC0, CC-BY, CC-BY-NC, PMC-OA}
or PMC-OA-subset; else downgrade to `abstract_only`, drop body, log.
