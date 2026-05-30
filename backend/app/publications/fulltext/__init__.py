"""Publication abstracts, open-access full text, and hybrid retrieval.

This subpackage adds, license-safely, for the publications referenced by HNF1B-db
phenopackets:

- abstracts (NCBI ``efetch``),
- license-gated open-access full-text *passages* (PubTator3 BioC / EuropePMC JATS),
- hybrid retrieval over those passages (PostgreSQL FTS + optional pgvector,
  fused with Reciprocal Rank Fusion), suitable for RAG.

Design notes live in
``docs/superpowers/specs/2026-05-29-publication-fulltext-rag-design.md`` and
``.planning/plans/2026-05-29-publication-fulltext-rag-plan.md``.

Module map:

- :mod:`.types`           — shared dataclasses and the canonical section taxonomy.
- :mod:`.abstract_client` — NCBI efetch abstract fetch + XML parsing.
- :mod:`.fulltext_client` — PMCID resolution, PubTator BioC / EuropePMC fetch + parse.
- :mod:`.coverage`        — license gate + coverage tiering.
- :mod:`.chunking`        — 510/50 section-bounded token windows + offset recovery.
- :mod:`.embeddings`      — embedding provider protocol + Fake/ST impls.
- :mod:`.rrf`             — Reciprocal Rank Fusion + section boosts (pure).
- :mod:`.persistence`     — passage + metadata persistence (raw SQL).
- :mod:`.retrieval`       — hybrid search query orchestration.
- :mod:`.orchestrator`    — per-publication fetch/gate/chunk/persist glue.
"""
