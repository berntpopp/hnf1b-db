## Publication Abstracts, Open-Access Full Text & Hybrid Retrieval (RAG)

Implements `docs/superpowers/specs/2026-05-29-publication-fulltext-rag-design.md`.

Populates, license-safely, for the 137 referenced publications: **abstracts** (fixes the latent esummary-can't-return-abstracts bug via `efetch`), **license-gated open-access full-text passages**, and **hybrid (lexical + optional semantic) retrieval** over those passages — exposed via a new public API endpoint and a new MCP tool, suitable for RAG.

### What's new
- **Schema (Alembic `e7a1b9c3d2f4`)**: `CREATE EXTENSION vector`; extend `publication_metadata` (`pmcid`/`coverage`/`license`/`fulltext_fetched_at`); `publication_fulltext` (passages, generated `tsvector` + GIN); `publication_fulltext_embeddings` (`vector(384)` + HNSW cosine). DB image switched to `pgvector/pgvector:pg15` (compose ×2 + both CI postgres services).
- **Fetch + ingest** (`backend/app/publications/fulltext/`): `efetch` abstract client; PMCID resolution + PubTator3 BioC + EuropePMC (license/OA) + JATS fallback; fail-closed license gate; 510/50 section-bounded token chunking with char-offset recovery; embedding provider protocol (`FakeEmbeddingProvider` for CI, lazy SentenceTransformer for prod); RRF fusion; per-publication orchestrator with error isolation.
- **API**: new public `GET /api/v2/publications/passages` (hybrid retrieval; `brief|full|ids_only`, `rrf|lexical|off`, filters, budgeting, `_meta` diagnostics). List + detail schemas gain `abstract`/`coverage`/`pmcid`/`license`/`has_full_text`. Admin `POST /publications/sync` now runs full orchestration and reports counts. New idempotent `scripts/backfill_publications.py` + Makefile targets.
- **MCP**: new read-only `hnf1b_get_publication_passages` tool (reuses `build_pmid_citation_map` so every passage carries the verbatim `recommended_citation`); allowlist + capabilities updated; OpenAPI snapshot + contract regenerated.
- **Embeddings are optional** (`[rag]` extra; never installed in CI). The lexical leg always works; the dense leg degrades gracefully when embeddings/provider are absent.

### Verification
- Backend suite **1497 passed, 0 failed** in CI-parity conditions (fresh `pgvector/pgvector:pg15`, `alembic upgrade head`, no local `.env`). 129 new backend tests (unit + integration against real Postgres, RRF exercised with `FakeEmbeddingProvider`). ruff + mypy clean.
- MCP suite **312 + 9 new** green; strict mypy + ruff clean; contract-drift guard clean.
- **Live end-to-end** against real NCBI/PubTator/EuropePMC: backfilled golden PMID `32574212` (full_text, CC-BY, PMC7310724, title/abstract/intro/methods×29/results/discussion/table) and `30791938`; `10484768` correctly gated to `abstract_only` (not in PMC). Queried `/publications/passages` (lexical, section filter, brief/full/ids_only, rrf-fallback); MCP tool returned ranked passages with full citations (`Obeidova L et al. … PloS one. 2020. PMID:32574212. doi:…`).
- **Playwright**: the unchanged frontend renders the Publications list + detail pages against the new additive API with no regression (FE consumes only existing fields; new fields are additive).

### Scope / out
No frontend UI changes (API only). No cross-encoder reranker (RRF only). References section not stored. Embeddings optional — not required to ship.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
