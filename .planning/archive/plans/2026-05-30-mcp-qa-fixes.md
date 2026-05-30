# MCP QA Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the six defects found in the 2026-05-30 MCP QA test pass — the `publications_timeline` year-bucketing bug, the publication-passages RAG relevance gap, the `hnf1b_search` phenotype-blind individual search, and three MCP polish issues (inert `get_variant` response_mode, inconsistent `not_found` errors, silent unknown-HPO IDs).

**Architecture:** Monorepo with a FastAPI backend (`backend/`) and a read-only FastMCP sidecar (`mcp/`) that calls the backend over HTTP. Bugs split across both layers: SQL aggregations + a materialized view + RAG retrieval live in `backend/`; response shaping, error envelopes, and field projection live in `mcp/`. Each fix is test-first (TDD), atomically committed.

**Tech Stack:** Python 3.10+, async SQLAlchemy + asyncpg, PostgreSQL (JSONB, FTS, pgvector), Alembic, FastAPI, FastMCP, httpx, pytest + pytest-asyncio (auto mode), respx (MCP mocks), ruff + mypy, uv.

---

## Conventions (read before any task)

- **MCP tests** (no DB): run from `mcp/` → `uv run pytest tests/<file>.py -v`. Backend HTTP is mocked with **respx** (`@respx.mock` + `respx.get(...).mock(...)`). Full suite: `uv run pytest`. Lint/type: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` (mypy is **strict** in mcp). One-shot: `make check`.
- **Backend tests** (need live Postgres+pgvector): from `backend/` run `make db-test-init` once (creates `hnf1b_phenopackets_test` in the `hnf1b_db` docker container + migrates), or `make hybrid-up` to start DB+Redis. Then `uv run pytest tests/<file>.py -v`. Lint/type: `uv run ruff check . && uv run ruff format --check . && uv run mypy app/ migration/`. One-shot: `make check`.
- **Commits:** Conventional Commits (`fix(...)`, `feat(...)`, `test(...)`). End every commit message with the trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **Branch:** create `fix/mcp-qa-remediation` off `main` before Task 1. Keep `.planning/` commits separate; produce the review branch with the `gsd-pr-branch` skill at the end.
- **Contract gate:** none of these changes alter the OpenAPI surface (no new/removed routes, no changed response models — `PassageHit.score` already exists). Still run `cd mcp && make contract-verify` after Workstream B/E to confirm zero diff in `mcp/src/hnf1b_mcp/contract/_generated_*.py`.
- **CI path-filtering:** backend-only changes run the `backend`+`e2e` jobs; mcp-only changes run the `mcp` job. The required check is **"CI gate"**.

---

## File Structure

**Backend (modify):**
- `backend/app/phenopackets/routers/aggregations/publications.py` — fix `get_publications_timeline` SQL (Workstream A).
- `backend/app/core/config.py` — add `min_lex_score` to `PublicationsRagConfig` (Workstream B).
- `backend/app/publications/fulltext/retrieval.py` — apply lexical relevance floor (Workstream B).
- `backend/alembic/versions/f3a9c1d4e7b2_search_mv_phenotype_text.py` — **create**: new MV migration folding phenotype/disease labels into the phenopacket branch (Workstream C).

**Backend (test):**
- `backend/tests/test_aggregations_endpoints.py` — add timeline year-correctness regression (A).
- `backend/tests/test_fulltext_retrieval.py` — add relevance-floor test (B).
- `backend/tests/test_global_search.py` — add phenotype-text individual-search test (C).

**MCP (modify):**
- `mcp/src/hnf1b_mcp/services/publication_passages.py` — expose `score` in all modes (B).
- `mcp/src/hnf1b_mcp/tools/publication_passages.py` — docstring sync (B).
- `mcp/src/hnf1b_mcp/services/variants.py` — per-mode scalar field projection for `get_variant` (D).
- `mcp/src/hnf1b_mcp/services/individuals.py` — rich `not_found` for `get_individual` (E).
- `mcp/src/hnf1b_mcp/services/reference.py` — rich `not_found` for `get_gene_context` (E).
- `mcp/src/hnf1b_mcp/services/publications.py` — rich `not_found` for reverse PMID lookup (E).
- `mcp/src/hnf1b_mcp/tools/individuals.py` — surface `unmatched_hpo_ids` from `find_individuals_by_phenotype` (F).

**MCP (test):**
- `mcp/tests/test_tool_publication_passages.py` — update score-visibility test (B).
- `mcp/tests/test_variants.py` — add field-set projection test (D).
- `mcp/tests/test_tool_individuals.py`, `mcp/tests/test_tool_reference.py`, `mcp/tests/test_tool_publications.py` — rich `not_found` assertions (E) + unmatched-HPO assertion (F).

---

## Workstream A — `publications_timeline` buckets every publication into the current year (HIGH)

**Root cause:** `get_publications_timeline` derives the year by regex-parsing `externalReferences[].description`, which never contains a year, so `NULLIF` collapses it to `NULL` and `COALESCE` falls back to `EXTRACT(YEAR FROM p.created_at)` — the row-insert timestamp (2026). The correct year lives in `publication_metadata.year`, already used by the two sibling endpoints in the same file.

### Task A1: Fix the timeline year derivation to use `publication_metadata.year`

**Files:**
- Modify: `backend/app/phenopackets/routers/aggregations/publications.py:92-136`
- Test: `backend/tests/test_aggregations_endpoints.py`

- [ ] **Step 1: Write the failing regression test**

Add to `backend/tests/test_aggregations_endpoints.py` (mirror the existing `async_client`/`db_session` style; seed two PMIDs in `publication_metadata` with distinct known years, attach each to a published phenopacket, and assert the timeline returns those two years — not 2026):

```python
@pytest.mark.asyncio
class TestPublicationsTimelineYearCorrectness:
    """Regression: timeline must bucket by publication_metadata.year, not created_at."""

    async def test_timeline_buckets_by_real_publication_year(
        self, async_client: AsyncClient, db_session
    ) -> None:
        from sqlalchemy import text as _text

        # Two cached publications with distinct, non-current years.
        await db_session.execute(
            _text(
                "INSERT INTO publication_metadata (pmid, title, year) VALUES "
                "('PMID:11111111', 'Old paper', 2008), "
                "('PMID:22222222', 'Newer paper', 2017) "
                "ON CONFLICT (pmid) DO UPDATE SET year = EXCLUDED.year"
            )
        )
        await db_session.commit()

        resp = await async_client.get(
            "/api/v2/phenopackets/aggregate/publications-timeline"
        )
        assert resp.status_code == 200, resp.text
        years = {row["year"] for row in resp.json()}
        # The bug produced exactly {2026}; the fix must surface the real years
        # for any seeded/imported published phenopackets and never the import year.
        assert 2026 not in years or years != {2026}, resp.json()
        assert years & {2008, 2017} or years == set(), resp.json()
```

> Note for the executor: the published-phenopacket fixtures available in `conftest.py` may not reference these PMIDs. If the timeline returns `[]` because no *published* phenopacket cites them, extend the test to attach `PMID:11111111` to the `published_record` fixture's `metaData.externalReferences` (via a JSONB update) so the row is counted. The non-negotiable assertion is: **no year equals the current import year unless a real publication was actually published that year.**

- [ ] **Step 2: Run it to confirm it fails (red)**

From `backend/`: `uv run pytest tests/test_aggregations_endpoints.py -k timeline_buckets_by_real_publication_year -v`
Expected: FAIL — returned years are `{2026}` (the bug), so the `& {2008, 2017}` assertion fails.

- [ ] **Step 3: Replace the broken `publication_years` CTE**

In `backend/app/phenopackets/routers/aggregations/publications.py`, replace lines **92-136** (the `query = """ ... """` block in `get_publications_timeline`) with the `publication_metadata`-joined version, copying the JOIN pattern already proven in `get_publications_by_type` (line 187) and `get_publications_timeline_data` (line 249):

```python
    # Public endpoint — apply public visibility filter (I3 + I7)
    # Year comes from the publication_metadata cache (run `make publications-sync`).
    # Publications without cached metadata have NULL year and are excluded.
    query = """
    WITH publication_years AS (
        SELECT
            p.phenopacket_id,
            ext_ref->>'id' as pmid,
            pm.year as pub_year
        FROM phenopackets p,
            jsonb_array_elements(
                p.phenopacket->'metaData'->'externalReferences'
            ) as ext_ref
        LEFT JOIN publication_metadata pm ON pm.pmid = ext_ref->>'id'
        WHERE p.deleted_at IS NULL
          AND p.state = 'published'
          AND p.head_published_revision_id IS NOT NULL
          AND p.phenopacket_id NOT LIKE 'e2e-%'
          AND ext_ref->>'id' LIKE 'PMID:%'
    ),
    year_counts AS (
        SELECT
            pub_year as year,
            COUNT(DISTINCT phenopacket_id) as count,
            array_agg(DISTINCT pmid ORDER BY pmid) as publications
        FROM publication_years
        WHERE pub_year IS NOT NULL
        GROUP BY pub_year
        ORDER BY pub_year
    )
    SELECT
        year,
        count,
        SUM(count) OVER (ORDER BY year) as cumulative,
        publications
    FROM year_counts
    ORDER BY year
    """
```

The downstream row-mapping (lines 138-149) is unchanged — `row.year`, `row.count`, `row.cumulative`, `row.publications` all still resolve. The MCP layer (`mcp/src/hnf1b_mcp/services/statistics.py:324-334`) needs no change; `publication_count` self-corrects once years are bucketed correctly.

- [ ] **Step 4: Run the test to confirm it passes (green)**

From `backend/`: `uv run pytest tests/test_aggregations_endpoints.py -k "timeline" -v`
Expected: PASS (both the new regression and the existing `TestAggregationTimelineEndpoints` smoke test).

- [ ] **Step 5: Lint, type, commit**

```bash
cd backend
uv run ruff check app/phenopackets/routers/aggregations/publications.py
uv run mypy app/phenopackets/routers/aggregations/publications.py
git add app/phenopackets/routers/aggregations/publications.py tests/test_aggregations_endpoints.py
git commit -m "fix(backend): bucket publications_timeline by publication_metadata.year

The timeline derived the year from externalReferences.description (which
never holds a year), collapsing every publication into EXTRACT(YEAR FROM
created_at) = the import year. Join publication_metadata and group by
pm.year, matching the sibling publications-by-type/timeline-data endpoints.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Workstream B — Publication-passages RAG returns confident junk for non-matching queries (MED-HIGH)

**Root cause (two parts):** (1) The backend lexical leg has an OR-recall `to_tsquery` leg that matches any passage containing *any* English token in the query, with **no minimum-score floor** anywhere in `search_passages`; RRF then re-scores by rank so weak hits look as confident as strong ones. (2) The MCP layer hides the per-passage `score` in `compact`/`minimal` (the default), so a caller cannot see the scores are near-zero.

### Task B1: Expose `score` in every response mode (MCP) — the visibility fix

**Files:**
- Modify: `mcp/src/hnf1b_mcp/services/publication_passages.py:36-73` (`_shape_passage`)
- Modify: `mcp/src/hnf1b_mcp/tools/publication_passages.py:67-70` (docstring)
- Test: `mcp/tests/test_tool_publication_passages.py:123-136`

- [ ] **Step 1: Update the test that currently codifies the bug**

In `mcp/tests/test_tool_publication_passages.py`, replace `test_compact_mode_omits_score_but_full_includes_it` (lines ~123-136) with an assertion that `score` is present in compact while `seq`/`source` remain standard/full-only:

```python
@pytest.mark.asyncio
@respx.mock
async def test_score_present_in_compact_seq_source_only_in_full():
    _mock_passages_and_citations()  # existing helper used by sibling tests
    mcp = FastMCP("test")
    client = ApiClient(base_url=BASE)
    register(mcp, client)

    compact = await mcp.call_tool(
        "hnf1b_get_publication_passages", {"query": "renal cysts"}
    )
    p0 = compact.structured_content["passages"][0]
    assert "score" in p0  # caller can now judge relevance in the default mode
    assert "seq" not in p0 and "source" not in p0  # still trimmed in compact

    full = await mcp.call_tool(
        "hnf1b_get_publication_passages",
        {"query": "renal cysts", "response_mode": "full"},
    )
    pf = full.structured_content["passages"][0]
    assert "score" in pf and "seq" in pf and "source" in pf
    await client.aclose()
```

> If the existing test uses an inline mock rather than a `_mock_passages_and_citations()` helper, copy the two `respx.get(...).mock(...)` lines from the neighbouring `test_passage_has_citation_and_snippet` test verbatim instead.

- [ ] **Step 2: Run it to confirm it fails (red)**

From `mcp/`: `uv run pytest tests/test_tool_publication_passages.py -k score_present_in_compact -v`
Expected: FAIL — `"score" not in p0` (compact strips it today).

- [ ] **Step 3: Hoist `score` out of the standard/full gate**

In `mcp/src/hnf1b_mcp/services/publication_passages.py`, change `_shape_passage` (lines 36-73) so `score` is always emitted and only `seq`/`source` stay mode-gated:

```python
    if text is not None:
        shaped["text"] = text
    if snippet is not None:
        shaped["snippet"] = snippet
    shaped["score"] = passage.get("score")  # always visible: lets caller judge relevance
    if response_mode in ("standard", "full"):
        shaped["seq"] = passage.get("seq")
        shaped["source"] = passage.get("source")
    return shaped
```

- [ ] **Step 4: Sync the tool docstring**

In `mcp/src/hnf1b_mcp/tools/publication_passages.py`, update the line in the docstring (around lines 67-70) that says standard/full "also include per-passage `score`, `seq`, and `source`" to: `Every mode includes per-passage ``score``; ``standard``/``full`` add ``seq`` and ``source``.`

- [ ] **Step 5: Run tests (green)**

From `mcp/`: `uv run pytest tests/test_tool_publication_passages.py -v`
Expected: PASS (all, including the rewritten test).

- [ ] **Step 6: Commit**

```bash
cd mcp
uv run ruff check src/hnf1b_mcp/services/publication_passages.py src/hnf1b_mcp/tools/publication_passages.py
uv run mypy src/
git add src/hnf1b_mcp/services/publication_passages.py src/hnf1b_mcp/tools/publication_passages.py tests/test_tool_publication_passages.py
git commit -m "fix(mcp): expose passage score in all response modes

A caller in the default compact mode could not see relevance scores, so
low-relevance RAG hits looked as authoritative as strong ones. Always emit
score; keep seq/source as standard/full extras.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task B2: Add a configurable lexical relevance floor (backend) — the recall fix

**Files:**
- Modify: `backend/app/core/config.py` (`PublicationsRagConfig`, ~lines 289-328)
- Modify: `backend/app/publications/fulltext/retrieval.py` (`_lexical_candidates` lines 59-100; thread param from `search_passages` lines 218-284)
- Test: `backend/tests/test_fulltext_retrieval.py`

- [ ] **Step 1: Write the failing relevance-floor test**

In `backend/tests/test_fulltext_retrieval.py` (uses real Postgres + the existing passage-seeding helpers; copy seeding from `test_lexical_ranks_keyword_match_first`):

```python
@pytest.mark.asyncio
async def test_min_lex_score_floor_drops_weak_only_matches(db_session, monkeypatch):
    """A query that matches only via the weak OR-recall leg is filtered by the floor."""
    await _seed_passages(db_session)  # same helper the other retrieval tests use

    # A strong query still returns its target.
    strong = await search_passages(
        db_session, query="renal cysts diabetes", rerank="lexical", limit=8
    )
    assert any(p.pmid for p in strong)

    # A query whose only overlap with the corpus is incidental stopword-like tokens
    # must return nothing once the floor is applied.
    from app.core.config import get_settings

    monkeypatch.setattr(
        get_settings().publications_rag, "min_lex_score", 0.05, raising=False
    )
    junk = await search_passages(
        db_session,
        query="zqxjkv nonexistent term that matches nothing",
        rerank="lexical",
        limit=8,
    )
    assert junk == [] or all(p.score >= 0.05 for p in junk)
```

> The executor tunes the literal `0.05` during the red→green loop: pick the smallest floor that yields `junk == []` while keeping `strong` non-empty against the seeded corpus. Record the chosen value as the config default in Step 3.

- [ ] **Step 2: Run it to confirm it fails (red)**

From `backend/`: `uv run pytest tests/test_fulltext_retrieval.py -k min_lex_score_floor -v`
Expected: FAIL — `min_lex_score` does not exist on the config and the junk query returns rows.

- [ ] **Step 3: Add the config knob**

In `backend/app/core/config.py`, inside `PublicationsRagConfig` (the block at ~289-328 with `rrf_k`, `section_boosts`, `lexical_candidate_limit`), add:

```python
    min_lex_score: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Minimum ts_rank_cd lexical score a passage must reach to be a "
            "candidate. 0.0 disables the floor (legacy behavior). A small "
            "positive value (e.g. 0.05) drops OR-recall-only noise."
        ),
    )
```

> Set the `default` to the value tuned in Step 1 so the floor is on by default. Keep it conservative — the test must prove known-good queries survive.

- [ ] **Step 4: Apply the floor in the lexical candidate query**

In `backend/app/publications/fulltext/retrieval.py`, in `_lexical_candidates` (lines 59-100): after the `GREATEST(...) AS lex_score` select, wrap the candidate query so the floor is a `HAVING`-style filter on the computed score. Replace the `sql = (...)` assembly (lines 84-95) with a version that filters `lex_score`:

```python
    min_score = float(get_settings().publications_rag.min_lex_score)
    params["min_lex_score"] = min_score
    sql = (
        f"WITH q AS (SELECT {', '.join(q_ctes)}), "
        "cand AS (SELECT f.pmid, f.passage_id, f.section, f.seq, f.text, "
        "f.char_count, f.token_count, f.source, "
        f"GREATEST({', '.join(select_rank)}) AS lex_score "
        "FROM publication_fulltext f, q "
        f"WHERE {''.join(where)}{filter_sql}) "
        "SELECT * FROM cand WHERE lex_score >= :min_lex_score "
        "ORDER BY lex_score DESC, pmid, seq "
        "LIMIT :lex_limit"
    )
```

Add the import if absent (top of file): `from app.core.config import get_settings`. When `min_lex_score == 0.0` the predicate is a no-op, preserving legacy behavior.

- [ ] **Step 5: Run tests (green)**

From `backend/`: `uv run pytest tests/test_fulltext_retrieval.py tests/test_fulltext_rrf.py tests/test_publications_passages_route.py -v`
Expected: PASS — new floor test green; all pre-existing retrieval/route tests still pass (they use matching queries above the floor).

- [ ] **Step 6: Commit**

```bash
cd backend
uv run ruff check app/core/config.py app/publications/fulltext/retrieval.py
uv run mypy app/core/config.py app/publications/fulltext/retrieval.py
git add app/core/config.py app/publications/fulltext/retrieval.py tests/test_fulltext_retrieval.py
git commit -m "fix(backend): add configurable lexical relevance floor to passage RAG

The OR-recall tsquery leg matched any passage sharing one English token
with the query, with no score floor, so gibberish-plus-common-words queries
returned confident-looking passages. Add PublicationsRagConfig.min_lex_score
and filter lexical candidates below it.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Workstream C — `hnf1b_search` never returns individuals for free-text clinical queries (MED)

**Root cause:** the unified search hits the `/search/global` materialized view and classifies rows by id-prefix. The MV's phenopacket branch indexes only `phenopacket_id` + `subject.id` into its `search_vector` — no phenotype/disease text — so `"renal cysts"`/`"diabetes"` never match an individual. **Chosen fix: enrich the MV** (keeps the single-call architecture; makes individuals genuinely searchable). No MCP change needed.

### Task C1: New Alembic migration folding phenotype + disease labels into the phenopacket branch

**Files:**
- Create: `backend/alembic/versions/f3a9c1d4e7b2_search_mv_phenotype_text.py`
- Test: `backend/tests/test_global_search.py`

- [ ] **Step 1: Write the failing backend test**

Add to `backend/tests/test_global_search.py` (real Postgres; the MV is built by migrations during `make db-test-init`). Seed a published phenopacket whose `content_jsonb` has a disease/feature label, refresh the MV, and assert `/search/global?q=<label>` returns a `pp_` hit:

```python
@pytest.mark.asyncio
async def test_global_search_matches_individual_by_phenotype_text(
    async_client: AsyncClient, db_session, published_record
):
    from sqlalchemy import text as _text

    # Ensure the published revision content carries a recognizable disease label.
    await db_session.execute(
        _text(
            "UPDATE phenopacket_revisions SET content_jsonb = "
            "jsonb_set(content_jsonb, '{diseases}', "
            "'[{\"term\": {\"id\": \"MONDO:0011593\", "
            "\"label\": \"Renal cysts and diabetes syndrome\"}}]'::jsonb) "
            "WHERE id = (SELECT head_published_revision_id FROM phenopackets "
            "WHERE phenopacket_id = :pid)"
        ),
        {"pid": published_record.phenopacket_id},
    )
    await db_session.commit()
    await db_session.execute(_text("REFRESH MATERIALIZED VIEW global_search_index"))
    await db_session.commit()

    resp = await async_client.get(
        "/api/v2/search/global", params={"q": "renal cysts", "page_size": 20}
    )
    assert resp.status_code == 200, resp.text
    ids = [r["id"] for r in resp.json()["results"]]
    assert any(i.startswith("pp_") for i in ids), resp.json()
```

> Adjust the response key (`results` vs `data`) to match the existing assertions in `test_global_search.py`. If `published_record` has no head revision wired, reuse whatever published-phenopacket helper the other tests in this file use.

- [ ] **Step 2: Run it to confirm it fails (red)**

From `backend/`: `uv run pytest tests/test_global_search.py -k matches_individual_by_phenotype_text -v`
Expected: FAIL — no `pp_` hit (current MV is phenotype-blind).

- [ ] **Step 3: Create the migration file**

Create `backend/alembic/versions/f3a9c1d4e7b2_search_mv_phenotype_text.py`. It rebuilds `global_search_index` with the same gene/domain/transcript/publication/variant branches as `b7c1f0a9d2e4`, changing **only** the phenopacket branch's `search_vector` to fold in disease + (non-excluded) phenotypic-feature labels. `downgrade()` restores the phenotype-blind phenopacket branch. SQL is inlined (migrations must be self-contained; the pre-commit guard forbids importing from `migration.*`).

```python
"""global_search_index: phenopacket branch searchable by phenotype/disease text

Revision ID: f3a9c1d4e7b2
Revises: e7a1b9c3d2f4
Create Date: 2026-05-30 11:00:00.000000

Folds disease term labels and non-excluded phenotypicFeatures labels into the
phenopacket branch ``search_vector`` so ``/search/global`` (and the MCP
``hnf1b_search`` tool that consumes it) returns individuals for free-text
clinical queries like "renal cysts" or "diabetes". All other branches are
identical to b7c1f0a9d2e4.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f3a9c1d4e7b2"
down_revision: Union[str, Sequence[str], None] = "e7a1b9c3d2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PUBLIC_FILTER = (
    "p.deleted_at IS NULL"
    "\n          AND p.state = 'published'"
    "\n          AND p.head_published_revision_id IS NOT NULL"
)
_NO_E2E = "p.phenopacket_id NOT LIKE 'e2e-%'"

DROP_GLOBAL_SEARCH_MV = "DROP MATERIALIZED VIEW IF EXISTS global_search_index;"

MV_INDEXES = [
    "CREATE UNIQUE INDEX idx_global_search_id ON global_search_index (id);",
    "CREATE INDEX idx_global_search_vector "
    "ON global_search_index USING GIN (search_vector);",
    "CREATE INDEX idx_global_search_label_trgm "
    "ON global_search_index USING GIN (label gin_trgm_ops);",
    "CREATE INDEX idx_global_search_type ON global_search_index (type);",
]

_STATIC_BRANCHES = """
-- Genes
SELECT
    'gene_' || id::text AS id,
    symbol AS label,
    'Gene'::text AS type,
    'Symbol'::text AS subtype,
    setweight(to_tsvector('simple', symbol), 'A') ||
    setweight(to_tsvector('english', COALESCE(name, '')), 'B') AS search_vector,
    name AS extra_info
FROM genes

UNION ALL

-- Protein domains
SELECT
    'domain_' || id::text AS id,
    name AS label,
    'Gene Feature'::text AS type,
    'Domain'::text AS subtype,
    to_tsvector('english', name) AS search_vector,
    short_name AS extra_info
FROM protein_domains

UNION ALL

-- Transcripts
SELECT
    'transcript_' || id::text AS id,
    transcript_id AS label,
    'Gene Feature'::text AS type,
    'Transcript'::text AS subtype,
    to_tsvector('simple', transcript_id) AS search_vector,
    NULL::text AS extra_info
FROM transcripts

UNION ALL

-- Publications with authors
SELECT
    'pub_' || pmid AS id,
    title AS label,
    'Publication'::text AS type,
    'Article'::text AS subtype,
    setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
    setweight(to_tsvector('simple', COALESCE(
        (SELECT string_agg(a->>'name', ' ') FROM jsonb_array_elements(authors) AS a),
        ''
    )), 'B') ||
    setweight(to_tsvector('english', COALESCE(journal, '')), 'C') AS search_vector,
    journal AS extra_info
FROM publication_metadata
WHERE title IS NOT NULL
"""

# Variant branch — identical to b7c1f0a9d2e4 (resolvable descriptor ids).
_VARIANT_BRANCH = f"""
-- Variants (deduplicated by resolvable VRS/CNV descriptor id; published-only)
SELECT * FROM (
    SELECT DISTINCT ON (descriptor_id)
        'var_' || descriptor_id AS id,
        variant_label AS label,
        'Variant'::text AS type,
        molecule_context AS subtype,
        to_tsvector('simple', search_text) AS search_vector,
        pathogenicity AS extra_info
    FROM (
        SELECT
            gi.value->'variantInterpretation'->'variationDescriptor'->>'id'
                AS descriptor_id,
            COALESCE(
                gi.value->'variantInterpretation'->'variationDescriptor'->>'label',
                COALESCE(
                    gi.value->'variantInterpretation'->'variationDescriptor'
                        ->'geneContext'->>'symbol',
                    'Unknown'
                ) || ':' || COALESCE(
                    (gi.value->'variantInterpretation'->'variationDescriptor'
                        ->'expressions'->0)->>'value',
                    'unknown'
                )
            ) AS variant_label,
            COALESCE(
                gi.value->'variantInterpretation'->'variationDescriptor'
                    ->>'moleculeContext',
                'genomic'
            ) AS molecule_context,
            COALESCE(
                gi.value->'variantInterpretation'->'variationDescriptor'->>'label', ''
            ) || ' ' ||
            COALESCE(
                gi.value->'variantInterpretation'->'variationDescriptor'
                    ->'geneContext'->>'symbol', ''
            ) || ' ' ||
            COALESCE((
                SELECT string_agg(e->>'value', ' ')
                FROM jsonb_array_elements(
                    gi.value->'variantInterpretation'->'variationDescriptor'
                        ->'expressions'
                ) AS e
            ), '') AS search_text,
            gi.value->'variantInterpretation'
                ->>'acmgPathogenicityClassification' AS pathogenicity
        FROM phenopackets p
        JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id,
             LATERAL jsonb_array_elements(
                 r.content_jsonb->'interpretations') AS interp,
             LATERAL jsonb_array_elements(
                 interp.value->'diagnosis'->'genomicInterpretations') AS gi
        WHERE {_PUBLIC_FILTER}
          AND {_NO_E2E}
          AND gi.value->'variantInterpretation'->'variationDescriptor'->>'id'
              IS NOT NULL
    ) AS raw_variants
    ORDER BY descriptor_id, variant_label
) AS unique_variants;
"""

# Phenopacket branch — ENRICHED: id + subject.id (exact, simple) plus disease
# term labels and non-excluded phenotypicFeatures labels (stemmed, english).
_PHENO_BRANCH_NEW = f"""
-- Phenopackets (phenotype/disease text searchable; published-only)
SELECT
    'pp_' || p.phenopacket_id AS id,
    COALESCE(r.content_jsonb->'subject'->>'id', p.phenopacket_id) AS label,
    'Phenopacket'::text AS type,
    'Individual'::text AS subtype,
    setweight(to_tsvector(
        'simple',
        p.phenopacket_id || ' '
            || COALESCE(r.content_jsonb->'subject'->>'id', '')
    ), 'A') ||
    setweight(to_tsvector('english', COALESCE((
        SELECT string_agg(DISTINCT d->'term'->>'label', ' ')
        FROM jsonb_array_elements(r.content_jsonb->'diseases') AS d
    ), '')), 'B') ||
    setweight(to_tsvector('english', COALESCE((
        SELECT string_agg(DISTINCT pf->'type'->>'label', ' ')
        FROM jsonb_array_elements(r.content_jsonb->'phenotypicFeatures') AS pf
        WHERE COALESCE((pf->>'excluded')::boolean, false) = false
    ), '')), 'C') AS search_vector,
    NULL::text AS extra_info
FROM phenopackets p
JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id
WHERE {_PUBLIC_FILTER}
  AND {_NO_E2E}
"""

# Phenopacket branch — PREVIOUS (phenotype-blind), for downgrade().
_PHENO_BRANCH_PREV = f"""
-- Phenopackets (phenopacket_id searchable; published-only)
SELECT
    'pp_' || p.phenopacket_id AS id,
    COALESCE(r.content_jsonb->'subject'->>'id', p.phenopacket_id) AS label,
    'Phenopacket'::text AS type,
    'Individual'::text AS subtype,
    to_tsvector(
        'simple',
        p.phenopacket_id || ' '
            || COALESCE(r.content_jsonb->'subject'->>'id', '')
    ) AS search_vector,
    NULL::text AS extra_info
FROM phenopackets p
JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id
WHERE {_PUBLIC_FILTER}
  AND {_NO_E2E}
"""

CREATE_MV_NEW = (
    "CREATE MATERIALIZED VIEW global_search_index AS\n"
    f"{_STATIC_BRANCHES}\nUNION ALL\n{_PHENO_BRANCH_NEW}\nUNION ALL\n{_VARIANT_BRANCH}"
)
CREATE_MV_PREV = (
    "CREATE MATERIALIZED VIEW global_search_index AS\n"
    f"{_STATIC_BRANCHES}\nUNION ALL\n{_PHENO_BRANCH_PREV}\nUNION ALL\n{_VARIANT_BRANCH}"
)


def _recreate_indexes() -> None:
    for stmt in MV_INDEXES:
        op.execute(stmt)


def upgrade() -> None:
    """Rebuild global_search_index with a phenotype/disease-searchable phenopacket branch."""
    op.execute(DROP_GLOBAL_SEARCH_MV)
    op.execute(CREATE_MV_NEW)
    _recreate_indexes()


def downgrade() -> None:
    """Restore the b7c1f0a9d2e4 phenotype-blind phenopacket branch."""
    op.execute(DROP_GLOBAL_SEARCH_MV)
    op.execute(CREATE_MV_PREV)
    _recreate_indexes()
```

- [ ] **Step 4: Apply the migration to the test DB and run the test (green)**

```bash
cd backend
uv run alembic upgrade head        # applies f3a9c1d4e7b2 to the dev DB
make db-test-init                  # rebuilds/migrates the test DB(s)
uv run pytest tests/test_global_search.py -v
```
Expected: PASS — `pp_` hit returned for `"renal cysts"`; all pre-existing global-search tests still pass.

- [ ] **Step 5: Verify migration round-trips**

```bash
cd backend
uv run alembic downgrade -1 && uv run alembic upgrade head
```
Expected: both succeed (no SQL errors); confirms `downgrade()` recreates a valid MV.

- [ ] **Step 6: Commit**

```bash
cd backend
uv run ruff check alembic/versions/f3a9c1d4e7b2_search_mv_phenotype_text.py
git add alembic/versions/f3a9c1d4e7b2_search_mv_phenotype_text.py tests/test_global_search.py
git commit -m "feat(backend): make individuals searchable by phenotype/disease text

Enrich the global_search_index phenopacket branch search_vector with disease
term labels and non-excluded phenotypicFeatures labels so /search/global (and
the MCP hnf1b_search tool) returns individuals for free-text clinical queries.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Workstream D — `hnf1b_get_variant` ignores `response_mode` (LOW)

**Root cause:** `get_variant` builds one fixed 15-key dict and only applies `apply_budget` to the `carriers` **list**; it never projects the scalar field set by mode. For low-carrier variants the payload is under the smallest budget, so minimal == standard == full. The canonical pattern to copy is `get_individual`'s `_project_individual` / `_INDIVIDUAL_FIELDS_BY_MODE`.

### Task D1: Add per-mode scalar field projection to `get_variant`

**Files:**
- Modify: `mcp/src/hnf1b_mcp/services/variants.py` (add `_DETAIL_FIELDS_BY_MODE` + `_project_variant_detail`; call it in `get_variant` before `apply_budget` at line ~535)
- Test: `mcp/tests/test_variants.py`

- [ ] **Step 1: Write the failing field-set test**

In `mcp/tests/test_variants.py` (mirror `test_individuals.py::test_get_individual_response_mode_trims`):

```python
@pytest.mark.asyncio
@respx.mock
async def test_get_variant_minimal_has_fewer_fields_than_full():
    _mock_single_variant()  # reuse the helper used by test_get_variant_* tests
    c = ApiClient(base_url=BASE)
    minimal = await get_variant(c, "Var6", response_mode="minimal")
    full = await get_variant(c, "Var6", response_mode="full")
    await c.aclose()
    # minimal must be a strict subset of full's keys, and smaller
    assert set(minimal) < set(full)
    # identity + classification survive in minimal; provenance/note are full-only
    assert {"variant_id", "label", "classification", "carrier_count"} <= set(minimal)
    assert "data_provenance" not in minimal and "note" not in minimal
    assert "data_provenance" in full and "note" in full
```

> If `test_variants.py` lacks a `_mock_single_variant()` helper, copy the `respx.get(...).mock(...)` setup from `test_get_variant_full_mode_keeps_all_carriers` (line ~554).

- [ ] **Step 2: Run it to confirm it fails (red)**

From `mcp/`: `uv run pytest tests/test_variants.py -k minimal_has_fewer_fields -v`
Expected: FAIL — `set(minimal) < set(full)` is false (identical field sets today).

- [ ] **Step 3: Add the field policy + projector**

In `mcp/src/hnf1b_mcp/services/variants.py`, near the existing `_ROW_FIELDS_BY_MODE` (lines ~125-170), add a detail policy and a projector that always keeps identity keys:

```python
# Scalar field policy for the single-variant detail payload, by response mode.
_DETAIL_ALWAYS = ("variant_id", "simple_id", "label", "uri", "carrier_count")
_DETAIL_FIELDS_BY_MODE: dict[str, tuple[str, ...]] = {
    "minimal": _DETAIL_ALWAYS + ("classification", "consequence"),
    "compact": _DETAIL_ALWAYS
    + ("gene_symbol", "classification", "consequence", "structural_type"),
    "standard": _DETAIL_ALWAYS
    + (
        "gene_symbol", "classification", "consequence", "structural_type",
        "hg38", "transcript", "protein", "carriers",
    ),
    "full": (),  # () == keep every field
}


def _project_variant_detail(result: dict[str, Any], mode: str) -> dict[str, Any]:
    """Trim the detail dict to the field set allowed for ``mode`` (full keeps all)."""
    allowed = _DETAIL_FIELDS_BY_MODE.get(mode, ())
    if not allowed:
        return result
    keep = set(allowed) | set(_DETAIL_ALWAYS)
    return {k: v for k, v in result.items() if k in keep}
```

> `carriers` is included from `standard` upward; in `minimal`/`compact` the carriers list is dropped entirely (consistent with `carrier_count` being the summary). `data_provenance` and `note` appear only in `full`.

- [ ] **Step 4: Call the projector in `get_variant`**

In `get_variant` (service, ~lines 507-535), immediately after the `result = {...}` dict is built and **before** the `apply_budget(...)` call, insert:

```python
    result = _project_variant_detail(result, response_mode)
    budget = Settings().mode_char_budgets.get(response_mode, 12000)
    result, dropped = apply_budget(result, budget, ["carriers"])
```

(The `apply_budget` line already exists — only the `_project_variant_detail` line is new, placed directly above it.) `apply_budget` on a now-absent `carriers` key is a safe no-op.

- [ ] **Step 5: Run tests (green)**

From `mcp/`: `uv run pytest tests/test_variants.py tests/test_tool_variants.py -v`
Expected: PASS — new test green; existing carrier-trim tests still pass (they use `standard`/`full`, which retain `carriers`).

- [ ] **Step 6: Commit**

```bash
cd mcp
uv run ruff check src/hnf1b_mcp/services/variants.py
uv run mypy src/
git add src/hnf1b_mcp/services/variants.py tests/test_variants.py
git commit -m "fix(mcp): make get_variant honor response_mode field projection

get_variant returned an identical full field set for minimal/standard/full
because only the carriers list was budget-trimmed. Add a per-mode scalar
field policy mirroring get_individual.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Workstream E — Inconsistent `not_found` errors (LOW)

**Root cause:** only `get_variant` matches the id client-side, so only it raises a rich `not_found` (`field="variant_id"` + value). `get_individual`, `get_gene_context`, and the publications reverse lookup fetch by id and let the shared 404 handler in `client/api_client.py:149-156` bubble a generic, value-less message. Fix: each service catches the `not_found` `McpToolError` and re-raises with `field` + value.

### Task E1: Rich `not_found` for `get_individual`, `get_gene_context`, reverse-PMID lookup

**Files:**
- Modify: `mcp/src/hnf1b_mcp/services/individuals.py` (`get_individual`, fetch ~lines 281-283)
- Modify: `mcp/src/hnf1b_mcp/services/reference.py` (`get_gene_context`, fetch ~lines 52-54)
- Modify: `mcp/src/hnf1b_mcp/services/publications.py` (`get_publication_citing_individuals`, ~line 268)
- Test: `mcp/tests/test_tool_individuals.py`, `mcp/tests/test_tool_reference.py`, `mcp/tests/test_tool_publications.py`

- [ ] **Step 1: Strengthen the existing not_found tests**

In `mcp/tests/test_tool_individuals.py`, extend `test_get_individual_not_found_returns_error_envelope` (line ~263) to assert the rich envelope:

```python
    assert sc["error"]["code"] == "not_found"
    assert sc["error"]["field"] == "phenopacket_id"
    assert "phenopacket-doesnotexist-99999" in sc["error"]["message"]
```

Add the analogous assertions in `test_tool_reference.py` (a 404 gene → `field == "gene_symbol"`, symbol echoed) and `test_tool_publications.py` (a 404 reverse lookup → `field == "citing_pmid"`, pmid echoed). If a not_found test does not yet exist in those files, add one modeled on the individuals test, mocking the backend route to return `httpx.Response(404)`.

- [ ] **Step 2: Run them to confirm they fail (red)**

From `mcp/`: `uv run pytest tests/test_tool_individuals.py tests/test_tool_reference.py tests/test_tool_publications.py -k "not_found" -v`
Expected: FAIL — `field`/value absent (generic message today).

- [ ] **Step 3: Catch + re-raise in `get_individual`**

In `mcp/src/hnf1b_mcp/services/individuals.py`, wrap the single-record fetch in `get_individual` (~lines 281-283):

```python
    try:
        raw = await client.get(
            PHENOPACKETS_BY_PHENOPACKET_ID.format(phenopacket_id=phenopacket_id)
        )
    except McpToolError as exc:
        if exc.code == "not_found":
            raise McpToolError(
                "not_found",
                f"individual '{phenopacket_id}' not found",
                field="phenopacket_id",
            ) from exc
        raise
```

Ensure `from hnf1b_mcp.services.errors import McpToolError` is imported (it is used elsewhere in the module; add if missing).

- [ ] **Step 4: Catch + re-raise in `get_gene_context`**

In `mcp/src/hnf1b_mcp/services/reference.py`, wrap the gene fetch (~lines 52-54):

```python
    try:
        raw = await client.get(REFERENCE_GENES_BY_SYMBOL.format(symbol=gene_symbol))
    except McpToolError as exc:
        if exc.code == "not_found":
            raise McpToolError(
                "not_found",
                f"gene '{gene_symbol}' not found",
                field="gene_symbol",
            ) from exc
        raise
```

- [ ] **Step 5: Catch + re-raise in the reverse-PMID lookup**

In `mcp/src/hnf1b_mcp/services/publications.py`, wrap the fetch in `get_publication_citing_individuals` (~line 268) and re-raise with `field="citing_pmid"` and the pmid value, following the same pattern.

- [ ] **Step 6: Run tests (green)**

From `mcp/`: `uv run pytest tests/test_tool_individuals.py tests/test_tool_reference.py tests/test_tool_publications.py tests/test_api_client.py -v`
Expected: PASS — rich envelopes asserted; `test_api_client.py::test_404_maps_to_not_found` (which checks the generic client-level mapping in isolation) still passes because the generic handler is unchanged.

- [ ] **Step 7: Commit**

```bash
cd mcp
uv run ruff check src/hnf1b_mcp/services/individuals.py src/hnf1b_mcp/services/reference.py src/hnf1b_mcp/services/publications.py
uv run mypy src/
git add src/hnf1b_mcp/services/individuals.py src/hnf1b_mcp/services/reference.py src/hnf1b_mcp/services/publications.py tests/test_tool_individuals.py tests/test_tool_reference.py tests/test_tool_publications.py
git commit -m "fix(mcp): standardize rich not_found errors across record fetches

get_individual, get_gene_context, and the reverse-PMID lookup returned a
generic value-less not_found, unlike get_variant. Catch the upstream 404 and
re-raise with field + offending id.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Workstream F — `find_individuals_by_phenotype` silently ignores unknown HPO IDs (LOW)

**Root cause:** the tool validates HPO *shape* (`^HP:\d{7}$`) but a well-formed-yet-unmatched id (`HP:9999999`) falls through to an empty result with no `not_found` key. `_collect_matches` discards per-term match info, so an unknown term is indistinguishable from a matched-but-empty one. The `not_found:[]` seen on success is a side effect of the downstream batch call, not HPO validity.

### Task F1: Surface `unmatched_hpo_ids` on both the empty and matched paths

**Files:**
- Modify: `mcp/src/hnf1b_mcp/tools/individuals.py` (`find_individuals_by_phenotype` handler, ~lines 274-335)
- Test: `mcp/tests/test_tool_individuals.py`

- [ ] **Step 1: Update the test that codifies the silent behavior**

In `mcp/tests/test_tool_individuals.py`, extend `test_find_individuals_by_phenotype_empty_search_result` (line ~446, already uses `HP:9999999`) to assert the new signal, and add a mixed-terms case:

```python
    sc = result.structured_content
    assert sc["total"] == 0
    assert sc["unmatched_hpo_ids"] == ["HP:9999999"]


@pytest.mark.asyncio
@respx.mock
async def test_find_by_phenotype_reports_partial_unmatched():
    # HP:0000107 matches; HP:9999999 does not.
    _mock_phenopacket_search(  # reuse the file's existing search mock helper
        {"HP:0000107": ["phenopacket-1"], "HP:9999999": []}
    )
    _mock_batch(["phenopacket-1"])
    mcp = FastMCP("test")
    client = ApiClient(base_url=BASE)
    register(mcp, client)
    r = await mcp.call_tool(
        "hnf1b_find_individuals_by_phenotype",
        {"hpo_ids": ["HP:0000107", "HP:9999999"]},
    )
    sc = r.structured_content
    assert sc["total"] >= 1
    assert sc["unmatched_hpo_ids"] == ["HP:9999999"]
    await client.aclose()
```

> Use whatever per-term search mock the file already defines; if none, mock `respx.get(f"{BASE}/phenopackets/search")` with a `side_effect` keyed on the `filter`/`q` param so the two HPO ids return different bodies.

- [ ] **Step 2: Run to confirm failure (red)**

From `mcp/`: `uv run pytest tests/test_tool_individuals.py -k "unmatched or empty_search_result" -v`
Expected: FAIL — `unmatched_hpo_ids` key does not exist.

- [ ] **Step 3: Track per-term matches and emit the key**

In `mcp/src/hnf1b_mcp/tools/individuals.py` `handler` (~lines 290-326), capture per-term results and build the unmatched list:

```python
            seen: dict[str, None] = {}
            capped = False
            per_term_hit: dict[str, bool] = {}
            for hpo_id in hpo_ids:
                matched, term_capped = await _collect_matches(hpo_id)
                capped = capped or term_capped
                per_term_hit[hpo_id] = bool(matched)
                for item_id in matched:
                    if item_id not in seen:
                        seen[item_id] = None
            merged_ids = list(seen.keys())
            unmatched_hpo_ids = [h for h, hit in per_term_hit.items() if not hit]
            total = len(merged_ids)
            has_more = total > page_size

            if not merged_ids:
                return {
                    "individuals": [],
                    "total": 0,
                    "returned": 0,
                    "page_size": page_size,
                    "has_more": False,
                    "match_mode": "any",
                    "hpo_ids": list(hpo_ids),
                    "unmatched_hpo_ids": unmatched_hpo_ids,
                }
```

Then in the matched branch (after the downstream `get_individuals` result dict is assembled, ~line 326), set the key explicitly so it is always present and HPO-scoped (avoiding the batch-coverage `not_found` collision):

```python
            result["unmatched_hpo_ids"] = unmatched_hpo_ids
            return result
```

- [ ] **Step 4: Run tests (green)**

From `mcp/`: `uv run pytest tests/test_tool_individuals.py -v`
Expected: PASS (including the happy-path and dedupe tests, which now also carry `unmatched_hpo_ids: []`).

- [ ] **Step 5: Commit**

```bash
cd mcp
uv run ruff check src/hnf1b_mcp/tools/individuals.py
uv run mypy src/
git add src/hnf1b_mcp/tools/individuals.py tests/test_tool_individuals.py
git commit -m "fix(mcp): flag unknown/unmatched HPO ids in find_individuals_by_phenotype

A well-formed but unmatched HPO id (e.g. HP:9999999) returned an empty result
indistinguishable from a real no-match. Track per-term hits and always return
unmatched_hpo_ids.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Finalization

- [ ] **Run the full suites**
  - MCP: `cd mcp && make check` (ruff + mypy strict + `uv run pytest`) — expect all pass, coverage ≥ 80.
  - Backend: `cd backend && make check` — expect all pass, coverage ≥ 70. (Requires DB up: `make hybrid-up` + `make db-test-init` first.)
- [ ] **Contract gate:** `cd mcp && make contract-verify` — expect no diff.
- [ ] **Update capabilities docstring if needed:** confirm `hnf1b_get_capabilities` text about passages `score` visibility and search individual-coverage still matches behavior; adjust `mcp/src/hnf1b_mcp/services/capabilities.py` wording for the search/passages changes if it overstated prior limits.
- [ ] **Manual smoke (optional):** `make hybrid-up && make backend`, then re-run the four QA probes (timeline, passages junk query, `hnf1b_search "renal cysts"`, `get_variant` minimal vs full) to confirm the fixes end-to-end.
- [ ] **PR:** create the clean review branch with the `gsd-pr-branch` skill (filters `.planning/` commits), push `fix/mcp-qa-remediation`, open the PR, and watch the **CI gate** check to green per AGENTS.md.

---

## Self-Review (completed by plan author)

1. **Spec coverage:** All six QA findings map to a workstream — A (timeline HIGH), B (passages MED-HIGH, both score-visibility and floor), C (search individuals MED, MV enrichment per user's choice), D/E/F (three LOW polish items). ✅
2. **Placeholder scan:** Each code step contains real SQL/Python and exact `uv run pytest` commands with expected red/green. Two values are intentionally executor-tuned within the TDD loop (the `min_lex_score` default in B2 and the response-key/fixture wiring in DB-backed tests) — each is flagged with how to choose it, not left as "TBD". ✅
3. **Type/name consistency:** `_DETAIL_FIELDS_BY_MODE`/`_project_variant_detail` (D), `min_lex_score` (B2 config ↔ retrieval param), `unmatched_hpo_ids` (F), and migration `revision="f3a9c1d4e7b2"`/`down_revision="e7a1b9c3d2f4"` (confirmed current head via `alembic heads`) are used consistently across their tasks. ✅
4. **Ordering:** Backend workstreams (A, B2, C) and MCP workstreams (B1, D, E, F) are independent and can be parallelized or sequenced; each commit is atomic and self-contained. ✅
