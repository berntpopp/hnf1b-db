# Ontology Data Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the importer rewriting curator labels, correct four wrong ontology terms and 408 dropped laterality annotations in both stored copies, and add the source-integrity check that would have caught the whole defect class at import time.

**Architecture:** Four layers, in strict dependency order. First delete the laundering mechanism (A2) — until that is gone, every other fix can be silently reverted by the next import. Then build the conformance module (A1 + A3) as production code. Then correct the data with journalled, exactly-reversible migrations. Then fix the remaining consumers.

**Tech Stack:** Python 3.11, pytest, Alembic, SQLAlchemy 2 async, PostgreSQL 15; Vue 3 + Vitest.

**Spec:** [`../specs/2026-07-30-ontology-data-quality-design.md`](../specs/2026-07-30-ontology-data-quality-design.md)
**Findings:** [`../../ontology-defect-report-2026-07-30.md`](../../ontology-defect-report-2026-07-30.md)

## Global Constraints

- **Never rewrite a curator's label to match an identifier.** That is the mechanism that
  caused this. A name/ID disagreement is a hard failure for a human to resolve.
- **Every data change writes the working copy and the head-published revision** —
  `phenopackets.phenopacket`, and the `phenopacket_revisions.content_jsonb` row at
  `head_published_revision_id`. `visibility.py:80` serves that revision publicly, so a
  working-copy-only fix leaves the wrong term in every public response. Older revision
  rows are immutable history and are deliberately not rewritten; A3's scope is qualified
  to match (Task 3 Step 2).
- **CI has no corpus.** `conftest.py::_isolate_database_between_tests` is `autouse=True`
  and truncates `phenopackets` and `phenopacket_revisions` after every test. Any test
  asserting production counts passes vacuously or fails with 0. Migration tests seed
  their own fixture; whole-corpus arithmetic lives in a preflight script (Task 5), never
  in pytest.
- **Do not touch the four benign deviations** — `HP:0000708`, `HP:0012443`, `HP:0012622`,
  `HP:0002910`. Their identifiers are correct. They are allowlisted, not migrated.
- **Do not touch the GA4GH conformance debt** (ADR 0003).
- Backend: `uv run ruff format` before every commit — CI runs `ruff format --check`
  separately from `make check`.
- Migrations: set `down_revision` to the output of `uv run alembic heads` at the time
  you write the file. Do not guess.

## Verified ontology facts — do not re-derive

```
HP:0033132  Renal cortical hyperechogenicity  "Increased echogenecity of the kidney cortex."
HP:0033133  Renal cortical hypoechogeneity
HP:0003577  Congenital onset      sheet lists "Prenatal onset" among its synonyms
HP:0034199  Late first trimester onset
HP:0003674  Onset (abstract parent; HPO has no generic postnatal term)
HP:0002149  Hyperuricemia         HP:0003149  Hyperuricosuria
HP:0010935  Abnormality of the upper urinary tract
HP:0004729  Acute tubulointerstitial nephritis
HP:0004719  Hyperechogenic kidneys
HP:0012832 Bilateral · HP:0012833 Unilateral · HP:0012835 Left · HP:0012834 Right
MONDO:0007669  renal cysts and diabetes syndrome
MONDO:0011593  seizures, benign familial infantile, 2
MONDO:0010953  Fanconi anemia complementation group E
ORPHA:2260  Oligomeganephronia      ECO:0000033  author statement supported by traceable reference
```

Corpus baseline measured 2026-07-30 (after `d4e8b1f60a27`): 1125 disease entries over
864 records, 7810 features, 771 modifiers all `Bilateral`, 134 `HP:0034199` disease
onsets + 46 in `timeAtLastEncounter`, 65 + 17 `HP:0003674`.

---

## Task 1: Delete the label-laundering path (A2)

**This must land first.** While `_get_canonical_label` exists, every other correction in
this plan can be silently reverted by the next import — including the already-applied
`d4e8b1f60a27`.

**Files:**
- Modify: `backend/migration/phenopackets/hpo_mapper.py` (`build_from_dataframe`, `_get_canonical_label`)
- Test: `backend/tests/migration/test_no_label_laundering.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `HPOMapper.build_from_dataframe` writes `phenotype_name` verbatim and raises `OntologySourceError` on an uncorroborated row. Task 2's A1 check supplies the corroboration logic.

- [x] **Step 1: Create the test package**

`backend/tests/migration/` does not exist. Create it with an empty `__init__.py`.

- [x] **Step 2: Write the failing test**

```python
"""The importer must never rewrite a curator's term name (spec §3.3 A2).

hpo_mapper._get_canonical_label trusted the identifier and overwrote
phenotype_name with the canonical name of whatever id the sheet supplied. For
HP:0033133 that inverted a clinical finding across 460 features and logged it
at debug level.
"""

import pandas as pd
import pytest

from migration.phenopackets.hpo_mapper import HPOMapper


def sheet(rows):
    return pd.DataFrame(
        rows, columns=["phenotype_category", "phenotype_id", "phenotype_name"]
    )


def test_curator_label_is_written_verbatim():
    mapper = HPOMapper()
    mapper.build_from_dataframe(
        sheet([["RenalCysts", "HP:0000107", "Renal cyst"]])
    )
    assert mapper.get_hpo_term("renalcysts")["label"] == "Renal cyst"


def test_a_local_qualifier_survives_unchanged():
    """HP:0012622's curated label is deliberately not the canonical name."""
    mapper = HPOMapper()
    mapper.build_from_dataframe(
        sheet([["RenalInsufficancy", "HP:0012622",
                "chronic kidney disease, not specified"]])
    )
    label = mapper.get_hpo_term("renalinsufficancy")["label"]
    assert label == "chronic kidney disease, not specified"
    assert label != "Chronic kidney disease", "canonical name must not be substituted"


def test_the_laundering_method_no_longer_exists():
    """A regression fence: the fix is deletion, not a behaviour flag."""
    assert not hasattr(HPOMapper, "_get_canonical_label")


def test_no_normalization_is_logged(caplog):
    mapper = HPOMapper()
    with caplog.at_level("DEBUG"):
        mapper.build_from_dataframe(
            sheet([["RenalCysts", "HP:0000107", "Renal cyst"]])
        )
    assert not any("Normalized label" in r.message for r in caplog.records)
```

- [x] **Step 3: Run to verify it fails**

Run: `cd backend && uv run pytest tests/migration/test_no_label_laundering.py -q`
Expected: FAIL on `test_the_laundering_method_no_longer_exists`, and on
`test_a_local_qualifier_survives_unchanged` (the canonical name is substituted).

- [x] **Step 4: Delete the method and its call**

In `hpo_mapper.py`, remove `_get_canonical_label` entirely, and in
`build_from_dataframe` replace:

```python
                fallback = source_label if pd.notna(source_label) else category
                canonical_label = self._get_canonical_label(hpo_id, fallback)

                if pd.notna(source_label) and canonical_label != source_label:
                    logger.debug(...)
                    normalized_count += 1
```

with:

```python
                # The curator's name is written verbatim. Rewriting it to agree
                # with the identifier is what inverted HP:0033133 across 460
                # features; see docs/ontology-defect-report-2026-07-30.md §4.1.
                # A name that disagrees with its identifier is a defect for a
                # human to resolve, and Task 2's source-integrity check catches
                # it at import time.
                label = source_label if pd.notna(source_label) else category
```

Then use `label` where `canonical_label` was used, and delete the
`normalized_count` bookkeeping and its summary log line.

- [x] **Step 5: Verify nothing else called it**

Run: `grep -rn "_get_canonical_label\|normalized_count" --include=*.py backend/`
Expected: no output.

- [x] **Step 6: Find and update tests that encoded the old behaviour**

Run first, before assuming anything passes:

```bash
grep -rn "canonical\|normaliz" --include=*.py backend/tests/ | grep -i label
uv run pytest -q -k "hpo or mapper or migration or ontology"
```

Any test asserting that a curated label is replaced by the canonical name **encoded the
bug**. Update it to assert the opposite and say so in the commit message. Do not weaken
the new tests to accommodate it.

Note this task is deliberately standalone: the comment added in Step 4 refers forward to
Task 2's check, but no code here imports it, so Task 1 lands and passes on its own. It
must land first regardless — while `_get_canonical_label` exists, Task 2's A1 can be
satisfied by the very rewriting it is meant to prevent.

- [x] **Step 7: Commit**

```bash
cd backend && uv run ruff format && cd ..
git add backend/migration/phenopackets/hpo_mapper.py backend/tests/migration/
git commit -m "fix(migration): stop rewriting curator term names

_get_canonical_label took the sheet's phenotype_id, fetched that id's canonical
name, and overwrote the curator's phenotype_name with it — logging the change
at debug level. For HP:0033133 this replaced 'Renal cortical hyperechogenicity'
with 'Renal cortical hypoechogeneity', inverting the finding across 460
features and making the contradiction undetectable ever after.

Deleted rather than flagged. A name that disagrees with its identifier is a
defect for a human to resolve; Task 2 catches it at import.

Refs: docs/ontology-defect-report-2026-07-30.md §4.1"
```

---

## Task 2: Build the conformance module (A1 + A3)

Production code, not a test helper — the curation program's `DomainValidator` imports it.

**Files:**
- Create: `backend/app/ontology/conformance.py`
- Create: `backend/app/ontology/data/ontology_snapshot.json`
- Create: `backend/scripts/refresh_ontology_snapshot.py`
- Test: `backend/tests/test_ontology_conformance.py` (create)
- Modify: `backend/Makefile`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `check_label(term_id: str, label: str) -> str | None` — A3; violation message or `None`.
  - `check_source_row(term_id, name, description) -> str | None` — A1; violation message or `None`.
  - `ONTOLOGY_PATHS: list[str]` — the JSONB paths A3 enumerates.
  Task 1's importer and the curation `DomainValidator` both call these.

- [x] **Step 1: Write the snapshot refresher**

Create `backend/scripts/refresh_ontology_snapshot.py`. Requirements:

- Cover **four** ontologies. HPO via `https://ontology.jax.org/api/hp/terms/{id}`.
  MONDO, Orphanet (ORDO) and ECO via OLS4 **term lookup by IRI**:
  `https://www.ebi.ac.uk/ols4/api/ontologies/{ont}/terms?iri={iri}`, with IRIs
  `http://purl.obolibrary.org/obo/MONDO_0007669`,
  `http://www.orpha.net/ORDO/Orphanet_2260`,
  `http://purl.obolibrary.org/obo/ECO_0000033`.
  **Do not use OLS4 `/search`** — it does text matching and returns plausible wrong
  terms for an identifier query (it reported `MONDO:0011593` as
  "seizures, benign familial infantile, 2" only because that *is* correct; for other
  ids it silently returns unrelated matches).
- Store `{name, synonyms, definition}` per term. The definition is what A1 needs.
- Term list must not depend on Task 4 (which runs later). **This task commits the sheet
  vocabulary itself**, as `backend/app/ontology/data/curation_vocabulary.csv`
  (`phenotype_category, phenotype_id, phenotype_name, phenotype_description`), exported
  from the workbook's `Phenotype` and `Phenotype_modifier` sheets. It carries no
  individual-level data, so ADR 0003's PII constraint does not apply. Term ids are then
  read from that file, plus `laterality.py`'s four constants, plus an explicit list of
  the onset/disease/evidence/SO/GENO terms the importer emits.
- `--check` mode exits 1 on drift without writing.
- Record `"_generated_against"` with each ontology's version string.

- [x] **Step 2: Generate and eyeball the snapshot**

Run: `cd backend && uv run python scripts/refresh_ontology_snapshot.py`

Verify three entries by hand:

```bash
python3 - <<'PY'
import json
t = json.load(open('backend/app/ontology/data/ontology_snapshot.json'))['terms']
for k in ('HP:0033132', 'MONDO:0007669', 'ORPHA:2260'):
    print(k, '->', t[k]['name'])
PY
```

Expected: `Renal cortical hyperechogenicity`, `renal cysts and diabetes syndrome`,
`Oligomeganephronia`. If any is wrong the resolver is wrong — stop and fix it before
anything depends on this file.

- [x] **Step 3: Write the failing test**

```python
"""Ontology conformance (spec §3.3).

A1 catches wrong identifiers. A3 catches drift. A3 alone cannot catch a wrong
identifier, because it is satisfiable by editing the label — which is exactly
how HP:0033133 survived.
"""

import pytest

from app.ontology.conformance import ALLOWED_DEVIATIONS, check_label, check_source_row


class TestA3StoredConformance:
    def test_accepts_the_canonical_name(self):
        assert check_label("HP:0000107", "Renal cyst") is None

    def test_accepts_a_listed_synonym(self):
        assert check_label("HP:0000708", "Behavioral abnormality") is None

    def test_rejects_an_unrelated_label(self):
        assert check_label("HP:0000107", "Seizure")

    def test_rejects_an_unknown_identifier(self):
        assert check_label("HP:9999999", "Nonexistent")

    def test_covers_mondo_not_only_hpo(self):
        """Two of the five stored defects were MONDO."""
        assert check_label("MONDO:0007669", "renal cysts and diabetes syndrome") is None
        assert check_label("MONDO:0011593", "Renal cysts and diabetes syndrome")

    def test_cannot_catch_a_normalized_wrong_id(self):
        """Documents the limitation, so nobody mistakes A3 for the guard.

        HP:0033133 paired with ITS OWN canonical name passes A3 and is still
        the wrong term for this database. Only A1 catches that.
        """
        assert check_label("HP:0033133", "Renal cortical hypoechogeneity") is None


class TestA1SourceIntegrity:
    def test_accepts_a_row_whose_definition_corroborates_its_id(self):
        assert check_source_row(
            "HP:0000107", "Renal cyst", "A fluid filled sac in the kidney."
        ) is None

    def test_accepts_a_local_qualifier_backed_by_a_matching_definition(self):
        """HP:0012622's name is curated, but its definition matches canonical."""
        assert check_source_row(
            "HP:0012622",
            "chronic kidney disease, not specified",
            "Functional anomaly of the kidney persisting for at least three months.",
        ) is None

    def test_rejects_the_real_defect(self):
        """The row that produced T1: right name, right definition, wrong id."""
        violation = check_source_row(
            "HP:0033133",
            "Renal cortical hyperechogenicity",
            "Increased echogenecity of the kidney cortex.",
        )
        assert violation
        assert "HP:0033132" in violation, "must name the term the description describes"

    def test_accepts_a_name_only_match_when_no_definition_is_given(self):
        assert check_source_row("HP:0000107", "Renal cyst", "") is None

    def test_rejects_when_neither_field_corroborates(self):
        assert check_source_row("HP:0000107", "Seizure", "An epileptic event.")


def test_every_allowlisted_deviation_carries_a_reason():
    for key, reason in ALLOWED_DEVIATIONS.items():
        assert len(reason) > 40, f"{key} needs a justification, not a placeholder"
```

- [x] **Step 4: Implement `conformance.py`**

`check_label(term_id, label)` — allowlist, then snapshot lookup, then
`label == name or label in synonyms`.

`check_source_row(term_id, name, description)`:

1. If `description` is non-empty and matches the canonical definition of `term_id`
   (case-insensitive, trailing-period-insensitive) → `None`.
2. Else if `name` matches the canonical name or a synonym of `term_id` → `None`.
3. Else → violation. **Search the snapshot for a term whose canonical definition
   matches `description`**; if found, name it in the message. That is what turns
   "this is wrong" into "you meant `HP:0033132`".

`ALLOWED_DEVIATIONS` holds **six** documented pairs — `HP:0012622`, `HP:0002910`,
`HP:0000708`, `HP:0012443`, `HP:0003674`, and `("ECO:0000033", "author statement")`,
whose label is an imprecise shortening of "author statement supported by traceable
reference" and which the spec defers rather than corrects. Omitting it would make A3
red on the existing corpus. Each entry carries a written reason.

- [x] **Step 5: Wire A1 into the importer**

In `hpo_mapper.build_from_dataframe`, for each row call `check_source_row` and raise on
violation, collecting all violations first so one import reports every bad row rather
than the first:

```python
violations = [v for row in rows if (v := check_source_row(...))]
if violations:
    raise OntologySourceError(
        "Curation sheet rows name a term their identifier does not denote:\n"
        + "\n".join(violations)
    )
```

Add a test asserting a sheet containing the T1 row raises, and that the message names
`HP:0033132`.

- [x] **Step 6: Run everything**

Run: `cd backend && uv run pytest tests/test_ontology_conformance.py tests/migration/ -q`
Expected: PASS.

- [x] **Step 7: Add the Makefile target and commit**

```makefile
refresh-ontology-snapshot: check-env  ## Refresh the pinned ontology snapshot (review the diff)
	uv run python scripts/refresh_ontology_snapshot.py
```

Do **not** add `--check` to the PR pipeline; an upstream rename must not redden
unrelated PRs. Wire it to the existing `-m network` job or a scheduled run so drift
surfaces as a reviewable diff.

```bash
cd backend && uv run ruff format && cd ..
git add backend/app/ontology/ backend/scripts/refresh_ontology_snapshot.py backend/tests/test_ontology_conformance.py backend/Makefile
git commit -m "feat(ontology): source-integrity and conformance checks

A1 corroborates each sheet identifier against a field normalisation cannot
touch — the curator's description — and names the term the description
actually describes. It would have failed the import that created HP:0033133
and pointed at HP:0033132.

A3 is the naive label-vs-id check, retained and explicitly documented as
insufficient: it is satisfiable by editing the label, which is how the defect
survived. Covers HPO, MONDO, Orphanet and ECO across every ontology-bearing
JSONB path, not just hpo_terms_lookup.

Production module so the curation DomainValidator can import it.

Refs: docs/superpowers/specs/2026-07-30-ontology-data-quality-design.md §3.3"
```

---

## Task 3: Correct the stored terms

**Files:**
- Create: `backend/alembic/versions/<rev>_correct_ontology_terms.py`
- Modify: `backend/alembic/env.py`, `backend/tests/test_alembic_env_autogenerate.py`
- Test: `backend/tests/test_ontology_term_migration.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: a corpus with `MONDO:0007669` only, `HP:0034199` eliminated, `HP:0003674` relabelled. Task 4's backfill runs after.

- [x] **Step 1: Create the journal table and register it**

The collapse (two terms → one, then deduplicate) destroys which record held which term,
so downgrade cannot be an inverse remap. The revision creates:

```sql
CREATE TABLE ontology_migration_journal (
    id             bigserial PRIMARY KEY,
    revision       text NOT NULL,
    table_name     text NOT NULL,
    row_id         text NOT NULL,      -- rendered PK; phenopackets.id is uuid,
                                       -- phenopacket_revisions.id is bigint, so a
                                       -- single typed column cannot hold both
    json_path      text NOT NULL,      -- 'diseases' | 'subject'
    preimage       jsonb NOT NULL,
    postimage_sha  text NOT NULL
);
CREATE INDEX ix_omj_lookup ON ontology_migration_journal (revision, table_name, row_id);
```

Keyed on the **row primary key rendered as text**, not `phenopacket_id`:
`phenopacket_revisions` has many rows per record, and the two tables' primary keys have
different types (`phenopackets.id uuid`, `phenopacket_revisions.id bigint`). Casts are
explicit at both ends: `row_id = t.id::text` on write, `t.id::text = j.row_id` on
restore. The journal is **retained after upgrade**; downgrade depends on
it. Register `ontology_migration_journal` in **both** `alembic/env.py::include_object`
and `tests/test_alembic_env_autogenerate.py::_RAW_SQL_TABLES`, or the drift test
proposes dropping it.

- [x] **Step 2: Decide and document revision scope**

`phenopacket_revisions` rows are immutable historical snapshots and there can be several
per record. Rewriting all of them edits history; rewriting none leaves the public
snapshot wrong.

**Decision: rewrite only each record's `head_published_revision_id` row**, plus every
working copy. Older revisions keep their original content and are correct as history.

Two consequences, both mandatory:

- Task 4's assertions count **head revisions**, not all revisions.
- **A3's scope must match.** `check_label` is applied to working copies and head
  revisions only. If A3 traversed all revision rows it would go permanently red the
  moment any term is corrected, since history legitimately holds the old value. Encode
  this in the query, not in an allowlist.

State both in the revision docstring.

- [x] **Step 3: Prove the SQL in a rolled-back transaction**

Deterministic deduplication — `jsonb_agg(DISTINCT e ORDER BY ord)` is **invalid**
PostgreSQL, because the ORDER BY expression is not the DISTINCT argument. Keep the
first occurrence by ordinality instead:

```sql
UPDATE phenopackets AS t
SET phenopacket = jsonb_set(t.phenopacket, '{diseases}', (
    SELECT jsonb_agg(e ORDER BY ord)
    FROM (
        SELECT DISTINCT ON (e) e, ord
        FROM (
            SELECT CASE
                     WHEN d->'term'->>'id' IN ('MONDO:0011593','MONDO:0010953')
                     THEN jsonb_set(d, '{term}', jsonb_build_object(
                              'id',    cast(:to_id    as text),
                              'label', cast(:to_label as text)))
                     ELSE d
                   END AS e,
                   ord
            FROM jsonb_array_elements(t.phenopacket->'diseases')
                 WITH ORDINALITY AS a(d, ord)
        ) mapped
        ORDER BY e, ord
    ) deduped
))
WHERE EXISTS (
    SELECT 1 FROM jsonb_array_elements(t.phenopacket->'diseases') d
    WHERE d->'term'->>'id' IN ('MONDO:0011593','MONDO:0010953')
);
```

Two traps already paid for in `d4e8b1f60a27` and documented in its comments: parenthesise
`((elem->'x') - 'k') || jsonb_build_object(...)` or the `-` binds wrong and deletes the
keys you are setting; and wrap every bind in `cast(:p as text)` because
`jsonb_build_object` takes `"any"` and asyncpg cannot infer it. Never write `::jsonb`
directly after a bind parameter.

Then assert, still inside the transaction:

```
diseases entries                 864
distinct array lengths           {1}
distinct term ids                {MONDO:0007669}
onsets  HP:0003577 594 · HP:0003674 54 · null 216
```

`ROLLBACK` and only then write the revision file.

- [x] **Step 4: Write the remaining remaps**

`HP:0034199` → `HP:0003577` / `"Congenital onset"` in `diseases[].onset.ontologyClass`
**and** `subject.timeAtLastEncounter.ontologyClass`. `HP:0003674` label → `"Onset"`, id
unchanged, in the same two locations. Journal the `subject` preimage too — Step 1's
`json_path` column exists for this.

> **AMENDED 2026-07-30 — four hazards, all verified against the live database. The plan as
> originally written aborts the migration.**
>
> 1. **Every array-rewrite UPDATE needs its own `WHERE EXISTS` guard.** Step 3's collapse SQL
>    has one; this step originally supplied neither SQL nor a warning. Reproduced: an unguarded
>    onset remap touches all 923 records, and the **59 with no `diseases` key** make
>    `jsonb_agg` over an empty set return NULL, so `jsonb_set(...)` returns NULL and the
>    statement dies with
>    `null value in column "phenopacket" of relation "phenopackets" violates not-null constraint`.
>    Guard shape: `WHERE EXISTS (SELECT 1 FROM jsonb_array_elements(t.phenopacket->'diseases') d
>    WHERE d->'onset'->'ontologyClass'->>'id' = 'HP:0034199')`.
>    Measured: `diseases` is missing in 59 working copies and 43 head revisions; there are
>    **zero** empty arrays and **zero** non-array values in either copy, so `WHERE EXISTS` is
>    sufficient and no type-normalisation is needed.
>
> 2. **`subject.timeAtLastEncounter` is NOT an aggregation problem — do not copy the array
>    shape here.** It is a single object at a fixed path. Use a scalar predicate:
>    `WHERE t.phenopacket #>> '{subject,timeAtLastEncounter,ontologyClass,id}' IN ('HP:0034199','HP:0003674')`
>    and a plain `jsonb_set` on that path. Wrapping it in `jsonb_agg` would be needless and
>    dangerous.
>
> 3. **Guard the working copy and the head revision independently**, and join the revision side
>    explicitly: `... FROM phenopacket_revisions r JOIN phenopackets p ON p.head_published_revision_id = r.id`.
>    Do not assume the two copies have the same row set.
>
> 4. **The head-revision copy has 907 documents, not 923** — 16 records have no
>    `head_published_revision_id`. Any assertion of the form "expect 923 rows updated" on the
>    revision side is wrong. Step 3's post-conditions (864 entries, all length 1, all
>    `MONDO:0007669`, onsets `HP:0003577` 594 / `HP:0003674` 54 / null 216) were verified by the
>    controller in a rolled-back transaction against the **working copy** and are correct there.

- [x] **Step 5: Write the migration test against a seeded fixture**

CI truncates the corpus, so this test **seeds its own records** covering every defect
shape, then invokes the migration functions directly:

```python
"""Term-correction migration, against a seeded fixture.

CI has no corpus: conftest truncates phenopackets after every test. Whole-corpus
arithmetic lives in scripts/ontology_preflight.py, not here.
"""

FIXTURE = [
    # id, diseases, timeAtLastEncounter
    ("pp-both",   [RCAD_OLD, MODY5_OLD], None),          # collapse + dedupe
    ("pp-single", [RCAD_OLD],            None),          # collapse only
    ("pp-onset",  [dict(RCAD_OLD, onset=PRENATAL)], None),
    ("pp-tale",   [RCAD_OLD],            PRENATAL_TALE), # subject path
    ("pp-post",   [dict(RCAD_OLD, onset=POSTNATAL)], None),
    ("pp-clean",  [RCAD_NEW],            None),          # already correct: no-op
]
```

Assert per record: `pp-both` ends with one disease; `pp-clean` is byte-identical
before and after; `pp-post` keeps `HP:0003674` and gains the label `"Onset"`;
`pp-tale`'s subject path is remapped. Then `downgrade()` and assert every fixture
record is byte-identical to its preimage.

- [x] **Step 6: Apply and round-trip against the real database**

```bash
cd backend
uv run alembic upgrade head
uv run pytest tests/test_ontology_term_migration.py tests/test_ontology_conformance.py -q
uv run alembic downgrade -1 && uv run alembic upgrade head
```

- [x] **Step 7: Refresh derived state**

```bash
psql -h localhost -p 5433 -U hnf1b_user -d hnf1b_phenopackets -c "\dm"   # enumerate first
psql ... -c "REFRESH MATERIALIZED VIEW global_search_index;"
```

Refresh every materialized view listed. Confirm `/api/v2/search/global?q=renal` still
returns results.

- [x] **Step 8: Commit**

Message: as in the defect report §1; note the head-revision-only scope decision.

---

## Task 4: Restore the 408 laterality annotations

The information is **not in the database**; it must be re-derived from the source.

**Files:**
- Create: `backend/scripts/build_laterality_fixture.py`
- Create: `backend/migration/data/laterality_2026-07-30.csv`
- Create: `backend/alembic/versions/<rev>_restore_laterality.py`
- Test: `backend/tests/test_laterality_backfill.py` (create)

**Interfaces:**
- Consumes: Task 1's `parse_laterality`, Task 3's corrected corpus.
- Produces: `Bilateral 797 / Unilateral 408 / Left 119 / Right 112` **subject to Step 1's resolution** — see the warning there.

- [x] **Step 1: Resolve source rows to records before trusting any total**

The importer groups 939 sheet rows into 864 individuals and deduplicates features by
HPO id. **797 "bilateral" source rows therefore do not imply 797 stored Bilateral
modifiers**, and the curation spec records that duplicate-row merge rules are undefined.

`build_laterality_fixture.py` must emit **one resolved row per
`(phenopacket_id, hpo_id)`**:

- group source rows by `individual_id`;
- for each laterality-bearing column, collect the distinct non-empty values;
- if they agree, emit the resolved value;
- if they disagree, emit **nothing** and write the conflict to
  `laterality_conflicts_2026-07-30.csv` for curator resolution.

Print the resolution summary — source rows, unique keys, agreements, conflicts — and
**derive the plan's expected totals from the emitted fixture**, not from raw row counts.
If conflicts exist, the expected totals in Step 3 change accordingly; update them and
say so in the commit rather than forcing the numbers.

Per ADR 0003 the fixture is de-identified: `individual_id, phenotype_column, hpo_id,
laterality_value` only. No `ReviewBy`, no comments, no other clinical columns. Record
the workbook's sha256 in a header comment.

- [x] **Step 2: Journal every touched feature**

Reuse `ontology_migration_journal` with `json_path = 'phenotypicFeatures'`. Downgrade
restores journalled rows only, after verifying `postimage_sha`, and asserts the exact
**771** baseline. Globally deleting the three unilateral ids would also delete
post-migration curator edits, so it is not an acceptable downgrade.

- [x] **Step 3: Write the test against a seeded fixture**

Same constraint as Task 3 — seed records, run the migration, assert. Cover:

- a feature that gains `[Unilateral, Left]`;
- a feature that already has `Bilateral` and is untouched;
- a feature whose stored modifier **disagrees** with the source → skipped, reported,
  not overwritten;
- a source row with no matching record → counted, reported, not an error;
- `downgrade()` restores the seeded preimages byte-identically;
- no feature ends with `Bilateral` alongside any sided modifier;
- `Left`/`Right` never appear without `Unilateral`;
- total feature count unchanged.

- [x] **Step 4: Apply, round-trip, refresh MVs, commit**

Assert `matched + skipped + unmatched == fixture rows`; abort the migration if not,
since that means the join is lossy.

---

## Task 5: Whole-corpus preflight

The arithmetic that cannot live in pytest.

**Files:**
- Create: `backend/scripts/ontology_preflight.py`

- [x] **Step 1: Write it**

Connects to a target database and reports, without modifying anything:

- every `(id, label)` pair at each path in `ONTOLOGY_PATHS`, run through `check_label`;
- disease entry count, distinct disease terms, array-length distribution;
- onset distribution across both paths;
- modifier totals by label;
- working copy vs head-published-revision divergence per record.

Exit non-zero on any A3 violation. Intended to be run **before and after** a deployment
of Tasks 3–4 and its output archived, replacing the "assert 864 in CI" idea that cannot
work against a truncated test database.

- [x] **Step 2: Run it against the local database and archive both outputs**

```bash
cd backend && uv run python scripts/ontology_preflight.py > /tmp/preflight-before.txt
# ... apply Tasks 3-4 ...
uv run python scripts/ontology_preflight.py > /tmp/preflight-after.txt
diff /tmp/preflight-before.txt /tmp/preflight-after.txt
```

The diff is the deployment record.

---

## Task 6: Fix the remaining consumers

Three wrong terms and one wrong numeric mapping outside the migration package.

**Files:**
- Modify: `backend/app/services/ontology_service.py`
- Modify: `backend/migration/phenopackets/hpo_mapper.py`
- Modify: `frontend/src/utils/ageParser.js`
- Test: extend `backend/tests/test_ontology_conformance.py`; `frontend/tests/unit/utils/ageParser.spec.js`

- [x] **Step 1: Correct `ontology_service.py`**

`HP:0003149` is Hyperuricosuria → `HP:0002149` Hyperuricemia. `MONDO:0011593` and
`MONDO:0010953` → `MONDO:0007669`. Check `HP:0000078`'s label against the snapshot while
you are there.

- [x] **Step 1b: Remediate `backend/scripts/normalize_hpo_labels.py` — ADDED 2026-07-30**

Found during Task 1, in neither plan. This standalone maintenance script is a **sixth instance
of the label-laundering defect family** (§4.1), and the one that most directly defeats Task 1.
Lines 79-85:

```python
term = ontology_service.get_term(hpo_id)
if term and not term.label.startswith("Unknown term:"):
    old_label = feature["type"].get("label", "")
    if old_label != term.label:
        feature["type"]["label"] = term.label       # <-- rewrites the curator's label
```

It cites "Fixes #165" — the same issue that produced `_get_canonical_label`. It is worse than
the importer path in two ways: it rewrites labels on **already-stored** records, so Task 1's
deletion does not contain it; and it writes only `pp.phenopacket`, never the head-published
revision, so running it would also violate this plan's Global Constraint on writing both
copies. One invocation re-inverts `HP:0033132` across 460 records.

Confirmed by review: no Makefile target, CI workflow, or migration path invokes it — it is
manually run. That lowers urgency, not severity.

**Delete it.** Task 1's precedent governs: the fix is deletion, not a behaviour flag. A
report-only variant is not worth keeping, because Task 2's `check_label` already provides that
capability over every ontology-bearing path, and Task 5's preflight script is the supported way
to run it against a live database. State in the commit message that `ontology_preflight.py`
supersedes it.

Add a regression fence next to the Task 1 tests:

```python
def test_no_script_rewrites_stored_curator_labels():
    """scripts/normalize_hpo_labels.py rewrote stored labels to match ids (§4.1).

    Deleted rather than flagged; check_label + ontology_preflight.py replace it.
    """
    assert not (Path(__file__).parents[2] / "scripts" / "normalize_hpo_labels.py").exists()
```

- [x] **Step 2: Correct the `hpo_mapper` fallback dictionary**

`HP:0004729` (Acute tubulointerstitial nephritis, labelled "Solitary functioning
kidney") and `HP:0004719` (Hyperechogenic kidneys, labelled "Oligomeganephronia"). Use
`HP:0000122` and `ORPHA:2260`, matching what the sheet and corpus actually use.

> **EXTENDED 2026-07-30 — the fallback map holds FOUR wrong ids, not two.**
> Found by running Task 2's `check_label` over every entry, then resolving each against the
> live HPO API. Step 3's `test_hpo_mapper_fallback_is_conformant` asserts EVERY entry is
> conformant, so it stays red until all four are corrected — fixing only the two above is not
> enough.
>
> | Entry | Label claims | Identifier actually denotes | Correct id | Evidence |
> |---|---|---|---|---|
> | `HP:0004729` | Solitary functioning kidney | Acute tubulointerstitial nephritis | `HP:0000122` | sheet maps SolitaryKidney → HP:0000122; corpus stores it 583× |
> | `HP:0004719` | Oligomeganephronia | Hyperechogenic kidneys | `ORPHA:2260` | sheet + corpus |
> | `HP:0010945` | Fetal renal anomaly | **Fetal pyelectasis** | `HP:0012210` | sheet maps AntenatalRenalAbnormalities → HP:0012210; corpus stores "Abnormal renal morphology" **261×** |
> | `HP:0100575` | Pancreatic hypoplasia | **Neoplasm of the gallbladder** | `HP:0002594` | HPO search resolves "Pancreatic hypoplasia" → HP:0002594; corpus stores it **206×** |
>
> All four wrong ids appear in **zero** stored records — the sheet replaces this dict at
> runtime, exactly as §2 of the defect report describes. They are live only on the
> Sheets-outage fallback path (`hpo_mapper.py:238`).
>
> **`HP:0012759` "Neurodevelopmental abnormality" is CORRECT** and must not be "fixed". It
> fails `check_label` only because it is absent from the pinned snapshot. Add it to the
> snapshot's term list instead — a coverage gap, not a defect.
>
> This raises the programme's total from 9 wrong identifiers to **11**. Update
> `docs/ontology-defect-report-2026-07-30.md` §2 and §8 accordingly as part of this task
> (T10 = `HP:0010945`, T11 = `HP:0100575`).

- [x] **Step 3: Add a test that every hardcoded map is conformant**

```python
def test_ontology_service_hardcoded_terms_are_conformant():
    """Three independent hardcoded maps is how these defects multiplied.

    Extract the literal dict in ontology_service into a module-level constant
    (e.g. ``ADDITIONAL_TERMS``) first so it can be imported; asserting against a
    dict built inside a method body is not possible.
    """
    from app.services.ontology_service import ADDITIONAL_TERMS

    for term_id, label in ADDITIONAL_TERMS.items():
        assert check_label(term_id, label) is None, f"{term_id}: {label}"


def test_hpo_mapper_fallback_is_conformant():
    for entry in HPOMapper().hpo_mappings.values():
        assert check_label(entry["id"], entry["label"]) is None
```

This is the assertion that would have caught T6–T9 without anyone auditing anything.

- [x] **Step 4: Correct `ageParser.js`**

`'HP:0034199': 0.08, // Neonatal onset` is wrong three ways: the term is Late first
trimester onset, the comment says Neonatal, and Task 3 eliminates the id from the
corpus. Remove the entry and add `'HP:0003577': 0` if not already present. Add a test
asserting no onset id maps to a value contradicting its ontology meaning.

- [x] **Step 5: Full gate and commit**

```bash
cd backend && uv run ruff format && uv run ruff check . && uv run pytest -q
cd ../frontend && npx vitest run && npm run lint:check && npm run build
cd ../mcp && uv run pytest -q
```

---

## Task 7: Hand off to the curation program

- [x] **Step 1: Wire the conformance check into the curation validator**

Curation plan Task 9's `DomainValidator` validates that a modifier is *permitted for a
term*. It would happily accept `HP:0033133` labelled "hyperechogenicity". Add a
`check_label` call so a wrong identifier cannot enter through the form.

- [x] **Step 2: Record the narrow dependency edges**

Not "this whole plan first". The real edges are:

1. `d4e8b1f60a27` (already applied) must precede the curation plan's `HP:0033132`
   laterality policy.
2. Task 2's `app/ontology/conformance.py` must precede curation Task 9.
3. Whichever plan's migration is written second must set `down_revision` to the other's
   head — update the placeholder in the curation plan's Task 5 accordingly.

Tasks 3–6 here are **not** prerequisites for the curation vocabularies and can proceed
in parallel.

- [x] **Step 3: Point the curation plan at the shared modifier constants**

Its Task 9 validator and Phase 3 UI must import the four ids from
`migration/phenopackets/laterality.py` rather than redeclaring them. Its test fixtures
use a fake label `"x"`, which a conformance call now rejects — update them to real
labels.

> **CORRECTED 2026-07-30.** This step originally included the Task 7 **migration** in that
> list. That is wrong, and the curation plan's inline redeclaration is right. An Alembic
> revision must be a frozen snapshot of its own intent: if it imported `BILATERAL` and friends
> from a mutable application module, editing that module later would silently change what an
> already-applied revision does when replayed on a fresh database. **Migrations redeclare ID
> literals inline; application code imports them.** Parity between the two encodings is
> enforced by a test, never by an import.

---

## Done criteria

- `_get_canonical_label` does not exist; no import path rewrites a curator's label.
- A sheet row naming a term its identifier does not denote fails the import, and the
  error names the term the description describes.
- `HP:0034199`, `MONDO:0011593`, `MONDO:0010953` appear in zero working copies and zero
  head-published revisions.
- `HP:0003674` carries the label `"Onset"`.
- Disease entries 864, every array length 1, every term `MONDO:0007669`.
- Modifier totals match the **resolved fixture** from Task 4 Step 1, with any conflicts
  written to the conflicts CSV rather than silently resolved.
- `check_label` passes for every hardcoded map and every seeded fixture path.
- Both migrations round-trip byte-identically against their seeded fixtures.
- `ontology_preflight.py` exits zero, and its before/after diff is archived.
- The curation plan's dependency edges and shared constants are recorded.

**The test that matters:** re-run the audit that produced the defect report — resolve
every stored `(id, label)` against its ontology, and check every sheet row's identifier
against its description. Both must come back clean, and A1 must be capable of failing,
which `test_rejects_the_real_defect` proves.

---

## Status: COMPLETE — landed in PR #422, CI green (2026-07-31)

All 6 tasks implemented, reviewed, and verified against the live corpus.

### Where reality differed from the plan

- **14 wrong identifiers, not 9**, across **8 hardcoded ontology maps, not 4**. The extra maps
  were found by sweeping every module that hardcodes an HPO/MONDO/ORPHA id rather than working
  from the defect report's list.
- **Two consumers were returning wrong results in production**, which the plan did not know
  about: `/kidney-morphology` filtered on `HP:0004719`, which appears **zero** times in the
  corpus, missing all 75 `ORPHA:2260` cases; and the `/timeline` renal bucket used substring
  matching, catching 657 of ~3300 features and mis-bucketing `HP:0000079` as genital.
- **`scripts/normalize_hpo_labels.py` was a second laundering mechanism** the report never
  listed. Deleted rather than fixed — it existed only to do the thing this plan forbids.
- **The onset remap aborted the migration** on first run: 59 records have no `diseases`, and
  `jsonb_agg` over an empty set returns `NULL`, violating the NOT NULL constraint. Every
  jsonb rebuild in both data migrations now carries a `WHERE EXISTS` guard.
- **A test fixture was destroying real reference rows** via `LIKE 'HP:000000%'`, and 5 tests
  could not fail. Both fixed.
- **`ORPHA:2260` still bucketed as "other"** in the timeline after the first pass — 75 renal
  findings reported as uncategorised. Caught in the 2026-07-31 review and fixed; timeline
  coverage is now 30 of the corpus's 36 distinct feature ids, and the 6 that remain are
  extrarenal syndromic findings for which "other" is correct.
- **`mypy` is a CI gate that the plan's verification sequence omitted.** `make check` runs it;
  `ruff format && ruff check && pytest` does not. It failed CI on `app/ontology/routers.py:239`.

### Verified, not assumed

- Migration reversibility on a clone of the real corpus: `e5bc71d2…` → downgrade past both data
  migrations → `8feba383…` → upgrade → `e5bc71d2…`. Byte-exact.
- Laterality: exactly 6 terms carry a policy; `HP:0000122` holds Unilateral/Left/Right
  (47/19/9) and **zero** Bilateral, per ADR 0003 Amendment 1.
- `hpo_mapper.py` writes `source_label` verbatim; no canonical-label lookup remains anywhere.
