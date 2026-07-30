# Ontology Data Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct four wrong ontology terms, restore 408 dropped laterality annotations, and add a conformance test that makes the whole class of defect impossible to reintroduce.

**Architecture:** Three layers. The import source is already corrected and needs tests. One Alembic revision corrects the stored data in both authoritative copies with a preimage journal for reversibility. A pinned-snapshot conformance test then asserts the invariant every one of these defects violated — that a term's stored label matches what its ID actually denotes.

**Tech Stack:** Python 3.11, pytest, Alembic, SQLAlchemy 2 async, PostgreSQL 15; Vue 3 + Vitest for the one display fix.

**Spec:** [`docs/superpowers/specs/2026-07-30-ontology-data-quality-design.md`](../specs/2026-07-30-ontology-data-quality-design.md)
**Related:** [`2026-07-30-curation-data-model-design.md`](../specs/2026-07-30-curation-data-model-design.md) — see §5 of this plan for the coupling.

## Global Constraints

- **This plan lands before the curation program.** Curation Task 7's laterality policy references `HP:0033132`, which only exists after revision `d4e8b1f60a27` (already applied locally, uncommitted).
- **Every data change writes both copies.** `phenopackets.phenopacket` *and* `phenopacket_revisions.content_jsonb`. `visibility.py:80` serves the published revision to the public; a working-copy-only fix leaves the wrong term in every public response.
- **Do not "normalise" labels toward `hpo_terms_lookup` or toward stored IDs.** That is the mechanism that converted these contradictions into consistent falsehoods. Labels are corrected only toward the *authoritative ontology*, and only for the terms named in this plan.
- **Do not touch the four benign deviations** — `HP:0000708`, `HP:0012443`, `HP:0012622`, `HP:0002910`. Their IDs are correct; the labels are synonyms, HPO renames, or deliberate local qualifiers. They go in the allowlist, not the migration.
- **Do not touch the GA4GH conformance debt** (ADR 0003) — ACMG placement, extension value types, the `timeAtLastEncounter.age` wrapper.
- Backend: `cd backend && uv run ruff format` before every commit — CI runs `ruff format --check` as a step local `make check` does not cover.
- Frontend: `npm run lint:check`, never `npm run lint`.
- Any route change requires `uv run python scripts/dump_openapi.py` in the same commit (see the curation plan's constraints). This plan adds no routes.

## Ontology facts (verified 2026-07-30, do not re-derive)

```
HP:0033132  Renal cortical hyperechogenicity   "Increased echogenecity of the kidney cortex."
HP:0033133  Renal cortical hypoechogeneity     <- what was stored; opposite finding
HP:0003577  Congenital onset                   sheet lists "Prenatal onset" as its synonym
HP:0034199  Late first trimester onset         <- what was stored for "prenatal"
HP:0003674  Onset                              abstract parent; no generic postnatal term exists
HP:0012832  Bilateral    HP:0012833  Unilateral    HP:0012835  Left    HP:0012834  Right
MONDO:0007669  renal cysts and diabetes syndrome   <- correct RCAD/MODY5 term
MONDO:0011593  seizures, benign familial infantile, 2
MONDO:0010953  Fanconi anemia complementation group E
ORPHA:2260  Oligomeganephronia                 correct
```

---

## Task 1: Test the laterality parser

`migration/phenopackets/laterality.py` and the `extractors.py` call site are already written (uncommitted). They have no tests. This task adds them before anything depends on the parser.

**Files:**
- Test: `backend/tests/migration/test_laterality.py` (create)
- Verify: `backend/migration/phenopackets/laterality.py`, `backend/migration/phenopackets/extractors.py:157`

**Interfaces:**
- Consumes: nothing.
- Produces: confidence in `parse_laterality(value) -> list[dict]`. Task 4's backfill and the curation program's `allowed_modifiers` both depend on these exact four term IDs.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/migration/test_laterality.py`:

```python
"""Laterality parsing (spec §1.2, §3.1).

The original extractor exact-matched ["bilateral","unilateral","left","right"].
The source uses compound values, so only "bilateral" ever matched and 408
laterality assertions were silently dropped.
"""

import pytest

from migration.phenopackets.laterality import (
    BILATERAL,
    LEFT,
    RIGHT,
    UNILATERAL,
    parse_laterality,
)


def ids(mods):
    return [m["id"] for m in mods]


# Every value that actually occurs in the source, with its frequency.
@pytest.mark.parametrize(
    "value,expected",
    [
        ("bilateral", [BILATERAL["id"]]),                              # 797
        ("unilateral unspecified", [UNILATERAL["id"]]),                # 177
        ("unilateral left", [UNILATERAL["id"], LEFT["id"]]),           # 119
        ("unilateral right", [UNILATERAL["id"], RIGHT["id"]]),         # 112
        ("no", []),                                                    # 2114
        ("not reported", []),                                          # 2314
    ],
)
def test_every_real_source_value(value, expected):
    assert ids(parse_laterality(value)) == expected


@pytest.mark.parametrize("value", ["Bilateral", "BILATERAL", "  bilateral  "])
def test_case_and_whitespace_insensitive(value):
    assert ids(parse_laterality(value)) == [BILATERAL["id"]]


def test_bilateral_is_not_matched_by_the_unilateral_substring_check():
    """'bilateral' contains 'lateral' but must not be read as unilateral."""
    assert ids(parse_laterality("bilateral")) == [BILATERAL["id"]]


def test_contradictory_value_yields_nothing_rather_than_both():
    """Bilateral and unilateral are mutually exclusive.

    Emitting both would create a feature asserting a contradiction, which is
    worse than emitting neither.
    """
    assert parse_laterality("bilateral and unilateral") == []


@pytest.mark.parametrize("value", [None, "", "   ", "yes", "unknown"])
def test_values_carrying_no_laterality(value):
    assert parse_laterality(value) == []


def test_returned_dicts_are_copies():
    """Callers attach these to phenopackets; a shared dict would alias."""
    a = parse_laterality("bilateral")[0]
    a["label"] = "mutated"
    assert parse_laterality("bilateral")[0]["label"] == "Bilateral"


def test_modifier_ids_match_the_curation_vocabulary():
    """These four ids are referenced by the curation program's allowed_modifiers.

    Three independent copies of four HPO ids is how the HP:0033133 error
    happened; this asserts the single source of truth (spec §6.1).
    """
    assert BILATERAL["id"] == "HP:0012832"
    assert UNILATERAL["id"] == "HP:0012833"
    assert LEFT["id"] == "HP:0012835"
    assert RIGHT["id"] == "HP:0012834"
```

- [ ] **Step 2: Run it**

Run: `cd backend && uv run pytest tests/migration/test_laterality.py -q`
Expected: PASS. If `test_contradictory_value_yields_nothing_rather_than_both` fails, the guard in `laterality.py` is wrong — fix the module, not the test.

Create `backend/tests/migration/__init__.py` if the directory is new.

- [ ] **Step 3: Prove the extractor call site uses it**

Run: `grep -n "parse_laterality\|bilateral" backend/migration/phenopackets/extractors.py`
Expected: the import at the top, the call in `extract()`, and **no** remaining inline `["bilateral", "unilateral", "left", "right"]` list.

- [ ] **Step 4: Commit**

```bash
cd backend && uv run ruff format && cd ..
git add backend/migration/phenopackets/laterality.py backend/migration/phenopackets/extractors.py backend/tests/migration/
git commit -m "fix(migration): parse compound laterality values

extractors.py exact-matched ['bilateral','unilateral','left','right'] but the
source records compound text: 'unilateral left', 'unilateral right',
'unilateral unspecified'. Only 'bilateral' ever matched, so 408 of 1205
laterality assertions were dropped while the phenotype row was still written —
leaving features indistinguishable from ones whose laterality was never stated.

Refs: docs/superpowers/specs/2026-07-30-ontology-data-quality-design.md §1.2"
```

---

## Task 2: Test the corrected term IDs in the import source

`age_parser.py`, `builder_simple.py`, `cnv_parser.py` and `hpo_mapper.py` are corrected (uncommitted) and untested. These tests pin the corrections so a future edit cannot quietly revert them.

**Files:**
- Test: `backend/tests/migration/test_ontology_term_ids.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed downstream. This is a regression fence.

- [ ] **Step 1: Write the failing test**

```python
"""The import must emit terms whose id denotes what its label says (spec §1).

Each assertion here corresponds to a defect that reached production.
"""

import pandas as pd

from migration.phenopackets.age_parser import AgeParser
from migration.phenopackets.builder_simple import PhenopacketBuilder
from migration.phenopackets.hpo_mapper import HPOMapper


class TestOnsetTerms:
    def test_prenatal_maps_to_congenital_onset(self):
        """HP:0034199 is 'Late first trimester onset', not 'Prenatal onset'.

        The source Phenotype_modifier sheet lists 'Prenatal onset' as a synonym
        of HP:0003577 Congenital onset, so that is the curated intent.
        """
        result = AgeParser().parse_age("prenatal")
        assert result["ontologyClass"]["id"] == "HP:0003577"
        assert result["ontologyClass"]["label"] == "Congenital onset"

    def test_postnatal_keeps_the_parent_id_with_an_honest_label(self):
        """HPO has no generic postnatal-onset term.

        HP:0003674 'Onset' is a true ancestor of any onset, so it is
        uninformative rather than false. The label must not claim otherwise.
        """
        result = AgeParser().parse_age("postnatal")
        assert result["ontologyClass"]["id"] == "HP:0003674"
        assert result["ontologyClass"]["label"] == "Onset"

    def test_congenital_is_unchanged(self):
        result = AgeParser().parse_age("congenital")
        assert result["ontologyClass"]["id"] == "HP:0003577"

    def test_no_emitted_onset_uses_a_retired_id(self):
        for value in ["prenatal", "postnatal", "congenital", "infantile", "adult"]:
            result = AgeParser().parse_age(value)
            if result and "ontologyClass" in result:
                assert result["ontologyClass"]["id"] != "HP:0034199"


class TestDiseaseTerms:
    def test_both_disease_keys_use_the_correct_mondo_term(self):
        """MONDO:0011593 = 'seizures, benign familial infantile, 2';
        MONDO:0010953 = 'Fanconi anemia complementation group E'."""
        mappings = PhenopacketBuilder(HPOMapper())._init_mondo_mappings()
        for key in ("hnf1b_disorder", "mody5"):
            assert mappings[key]["id"] == "MONDO:0007669", key

    def test_the_two_wrong_ids_appear_nowhere(self):
        mappings = PhenopacketBuilder(HPOMapper())._init_mondo_mappings()
        emitted = {m["id"] for m in mappings.values()}
        assert "MONDO:0011593" not in emitted
        assert "MONDO:0010953" not in emitted

    def test_mapping_entries_are_independent_objects(self):
        """Both keys share one term; they must not share one dict."""
        mappings = PhenopacketBuilder(HPOMapper())._init_mondo_mappings()
        mappings["mody5"]["label"] = "mutated"
        assert mappings["hnf1b_disorder"]["label"] == "renal cysts and diabetes syndrome"


class TestEchogenicity:
    def test_hpo_mapper_uses_the_hyper_term(self):
        """HP:0033133 is hypoechogeneity — the opposite finding."""
        term = HPOMapper().get_hpo_term("hyperechogenicity")
        assert term["id"] == "HP:0033132"
        assert "hyper" in term["label"].lower()
```

- [ ] **Step 2: Run it**

Run: `cd backend && uv run pytest tests/migration/test_ontology_term_ids.py -q`
Expected: PASS. `PhenopacketBuilder(HPOMapper())` may need different construction — check its `__init__` signature and adapt; do not weaken the assertions.

- [ ] **Step 3: Grep for survivors**

Run:

```bash
grep -rn "MONDO:0011593\|MONDO:0010953\|HP:0034199\|HP:0010935\|HP:0033133" \
  --include=*.py backend/migration/ | grep -v "denotes\|was wrong\|NOT \|opposite"
```

Expected: no output. Any hit outside an explanatory comment is a missed call site.

- [ ] **Step 4: Commit**

```bash
cd backend && uv run ruff format && cd ..
git add backend/migration/ backend/tests/migration/test_ontology_term_ids.py
git commit -m "fix(migration): correct four ontology term ids

Each had the right label on the wrong id, verified against HPO 2026-06-23 and
MONDO releases/2026-07-06:

  HP:0034199  'Prenatal onset'  is Late first trimester onset -> HP:0003577
  HP:0003674  'Postnatal onset' is Onset (parent) -> label corrected, id kept
  MONDO:0011593 is seizures, benign familial infantile, 2 -> MONDO:0007669
  MONDO:0010953 is Fanconi anemia complementation group E -> MONDO:0007669
  HP:0010935 does not exist -> HP:0033132

Refs: docs/superpowers/specs/2026-07-30-ontology-data-quality-design.md §3.1"
```

---

## Task 3: Build the pinned ontology snapshot and conformance test

The deliverable that outlives the individual fixes. Every defect in this spec violated one invariant: a stored label must match what its ID denotes.

**Files:**
- Create: `backend/scripts/refresh_ontology_snapshot.py`
- Create: `backend/tests/fixtures/ontology_snapshot.json`
- Create: `backend/tests/test_ontology_conformance.py`
- Modify: `backend/Makefile` (add `refresh-ontology-snapshot`)

**Interfaces:**
- Consumes: nothing.
- Produces: `assert_term_conformant(term_id, label) -> str | None` returning a violation message or `None`. The curation program's domain validator calls this (spec §6.2).

- [ ] **Step 1: Write the snapshot refresher**

Create `backend/scripts/refresh_ontology_snapshot.py`:

```python
#!/usr/bin/env python3
"""Refresh the pinned ontology snapshot used by the conformance test.

The test must not call a live ontology API: that is nondeterministic, fails
offline, and turns any upstream rename into a red build. Instead this script
fetches the canonical name and synonyms for every term the database uses and
writes them to a committed fixture, so a rename surfaces as a reviewable diff.

Usage:
    uv run python scripts/refresh_ontology_snapshot.py            # rewrite
    uv run python scripts/refresh_ontology_snapshot.py --check    # diff only
"""

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

SNAPSHOT = Path(__file__).parent.parent / "tests" / "fixtures" / "ontology_snapshot.json"
HPO_TERM_URL = "https://ontology.jax.org/api/hp/terms/{}"


def fetch_hpo(term_id: str) -> dict:
    with urllib.request.urlopen(
        HPO_TERM_URL.format(term_id.replace(":", "%3A")), timeout=30
    ) as response:
        data = json.load(response)
    synonyms = [
        s if isinstance(s, str) else (s.get("name") or s.get("synonym") or "")
        for s in (data.get("synonyms") or [])
    ]
    return {
        "name": data["name"],
        "synonyms": sorted(filter(None, synonyms)),
        "definition": (data.get("definition") or "").strip(),
    }


def collect_term_ids() -> list[str]:
    """Term ids to snapshot.

    Sourced from the committed curation sheet vocabulary plus the modifiers and
    onset terms the importer emits, so the snapshot does not require a database.
    """
    from migration.phenopackets.laterality import BILATERAL, LEFT, RIGHT, UNILATERAL

    ids = {t["id"] for t in (BILATERAL, UNILATERAL, LEFT, RIGHT)}
    ids |= {
        "HP:0003577", "HP:0003674", "HP:0003593", "HP:0011463", "HP:0003581",
        "HP:0033132", "HP:0012622", "HP:0012623", "HP:0012624", "HP:0012625",
        "HP:0012626", "HP:0003774", "HP:0000107", "HP:0000003", "HP:0100611",
        "HP:0000089", "HP:0000122", "HP:0000079", "HP:0000078", "HP:0012210",
        "HP:0002917", "HP:0002900", "HP:0002149", "HP:0001997", "HP:0004904",
        "HP:0002594", "HP:0001738", "HP:0000843", "HP:0012758", "HP:0000708",
        "HP:0001250", "HP:0012443", "HP:0001622", "HP:0001627", "HP:0000478",
        "HP:0004322", "HP:0033127", "HP:0001999", "HP:0002910", "HP:0031865",
    }
    return sorted(ids)


def build() -> dict:
    terms = {}
    for term_id in collect_term_ids():
        terms[term_id] = fetch_hpo(term_id)
        time.sleep(0.1)
    return {
        "_source": "https://ontology.jax.org/api/hp/terms/{id}",
        "_note": "Regenerate with scripts/refresh_ontology_snapshot.py; review the diff.",
        "terms": terms,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="diff without writing")
    args = parser.parse_args()

    fresh = build()
    serialized = json.dumps(fresh, indent=2, sort_keys=True) + "\n"

    if args.check:
        current = SNAPSHOT.read_text() if SNAPSHOT.exists() else ""
        if current != serialized:
            print("Ontology snapshot is stale. Run without --check to update.")
            return 1
        print("Ontology snapshot is current.")
        return 0

    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(serialized)
    print(f"Wrote {len(fresh['terms'])} terms to {SNAPSHOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Generate the snapshot**

Run: `cd backend && uv run python scripts/refresh_ontology_snapshot.py`
Expected: `Wrote 44 terms to .../ontology_snapshot.json` (count may differ slightly; it is whatever `collect_term_ids` returns).

Inspect it: `python3 -c "import json;d=json.load(open('backend/tests/fixtures/ontology_snapshot.json'));print(d['terms']['HP:0033132'])"`
Expected: name `Renal cortical hyperechogenicity`.

- [ ] **Step 3: Write the conformance test**

Create `backend/tests/test_ontology_conformance.py`:

```python
"""Every stored (id, label) pair must be consistent with the ontology.

This is the invariant that all five wrong-term defects violated. Each of them
had the right label on the wrong id, and nothing ever checked. Worse, a label
normalisation step rewrote labels to AGREE with the wrong ids, converting a
detectable contradiction into a consistent falsehood.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import text

SNAPSHOT = Path(__file__).parent / "fixtures" / "ontology_snapshot.json"

# Pairs that legitimately deviate from the canonical name. Every entry needs a
# reason. An allowlist rather than a blanket tolerance means a NEW deviation
# fails loudly while a known one stays silent.
ALLOWED_DEVIATIONS = {
    ("HP:0012622", "chronic kidney disease, not specified"): (
        "Deliberate local qualifier. The curation sheet's definition matches "
        "the canonical definition verbatim, which is what proves the id is right."
    ),
    ("HP:0002910", "Elevated hepatic transaminase"): (
        "HPO renamed the term to 'Elevated circulating hepatic transaminase "
        "concentration'; the sheet definition still matches canonical verbatim."
    ),
    ("HP:0000708", "Behavioral abnormality"): (
        "Listed HPO synonym of the current name 'Atypical behavior'."
    ),
    ("HP:0012443", "Abnormality of brain morphology"): (
        "Listed HPO synonym of the current name 'Abnormal brain morphology'."
    ),
    ("HP:0003674", "Onset"): (
        "HPO has no generic postnatal-onset term. The parent 'Onset' is a true "
        "ancestor of any onset, so it is uninformative rather than false."
    ),
}


@pytest.fixture(scope="module")
def snapshot():
    assert SNAPSHOT.exists(), (
        "Missing ontology snapshot. Run "
        "`uv run python scripts/refresh_ontology_snapshot.py`."
    )
    return json.loads(SNAPSHOT.read_text())["terms"]


def check(term_id: str, label: str, snapshot: dict) -> str | None:
    """Return a violation message, or None when the pair is acceptable."""
    if (term_id, label) in ALLOWED_DEVIATIONS:
        return None
    entry = snapshot.get(term_id)
    if entry is None:
        return f"{term_id} is not in the ontology snapshot (label {label!r})"
    if label == entry["name"] or label in entry["synonyms"]:
        return None
    return (
        f"{term_id} is stored with label {label!r} but denotes "
        f"{entry['name']!r}. If the label is right, the id is wrong."
    )


async def _pairs(db_session, sql: str) -> list[tuple[str, str]]:
    result = await db_session.execute(text(sql))
    return [(row[0], row[1]) for row in result.fetchall() if row[0] and row[1]]


@pytest.mark.asyncio
async def test_stored_phenotypic_features_are_conformant(db_session, snapshot):
    pairs = await _pairs(
        db_session,
        """SELECT DISTINCT f->'type'->>'id', f->'type'->>'label'
           FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'phenotypicFeatures') f""",
    )
    violations = [v for tid, lab in pairs if (v := check(tid, lab, snapshot))]
    assert not violations, "\n".join(violations)


@pytest.mark.asyncio
async def test_stored_modifiers_are_conformant(db_session, snapshot):
    pairs = await _pairs(
        db_session,
        """SELECT DISTINCT m->>'id', m->>'label'
           FROM phenopackets p,
                jsonb_array_elements(p.phenopacket->'phenotypicFeatures') f,
                jsonb_array_elements(f->'modifiers') m""",
    )
    violations = [v for tid, lab in pairs if (v := check(tid, lab, snapshot))]
    assert not violations, "\n".join(violations)


@pytest.mark.asyncio
async def test_stored_onsets_are_conformant(db_session, snapshot):
    pairs = await _pairs(
        db_session,
        """SELECT DISTINCT d->'onset'->'ontologyClass'->>'id',
                           d->'onset'->'ontologyClass'->>'label'
           FROM phenopackets p, jsonb_array_elements(p.phenopacket->'diseases') d""",
    )
    violations = [v for tid, lab in pairs if (v := check(tid, lab, snapshot))]
    assert not violations, "\n".join(violations)


@pytest.mark.asyncio
async def test_published_revisions_are_conformant(db_session, snapshot):
    """The public snapshot is a second authoritative copy (visibility.py:80)."""
    pairs = await _pairs(
        db_session,
        """SELECT DISTINCT f->'type'->>'id', f->'type'->>'label'
           FROM phenopacket_revisions r,
                jsonb_array_elements(r.content_jsonb->'phenotypicFeatures') f""",
    )
    violations = [v for tid, lab in pairs if (v := check(tid, lab, snapshot))]
    assert not violations, "\n".join(violations)


@pytest.mark.asyncio
async def test_hpo_terms_lookup_is_conformant(db_session, snapshot):
    """This table paired the wrong id with the right label, which is exactly
    why the curation form rendered the defect as if it were correct."""
    pairs = await _pairs(
        db_session, "SELECT hpo_id, label FROM hpo_terms_lookup WHERE hpo_id LIKE 'HP:%'"
    )
    violations = [v for tid, lab in pairs if (v := check(tid, lab, snapshot))]
    assert not violations, "\n".join(violations)


def test_every_allowlisted_deviation_has_a_reason():
    for key, reason in ALLOWED_DEVIATIONS.items():
        assert len(reason) > 40, f"{key} needs a real justification, not a placeholder"


def test_the_known_defects_would_be_caught(snapshot):
    """Regression fence: the invariant must reject the exact pairs that shipped."""
    assert check("HP:0033133", "Renal cortical hyperechogenicity", snapshot)
    assert check("HP:0034199", "Prenatal onset", snapshot)
```

- [ ] **Step 4: Run it — expect failures that name the real defects**

Run: `cd backend && uv run pytest tests/test_ontology_conformance.py -q`

Expected on a database that has **not** had Task 4 applied: failures naming
`HP:0034199` stored as "Prenatal onset" and the MONDO terms. That is the test working.
`test_the_known_defects_would_be_caught` must pass immediately.

If `test_stored_phenotypic_features_are_conformant` fails on a term this plan does not
name, stop — the audit missed something and it needs the same investigation.

- [ ] **Step 5: Add the Makefile target**

In `backend/Makefile`:

```makefile
refresh-ontology-snapshot:
	uv run python scripts/refresh_ontology_snapshot.py
```

- [ ] **Step 6: Commit**

```bash
cd backend && uv run ruff format && cd ..
git add backend/scripts/refresh_ontology_snapshot.py backend/tests/fixtures/ontology_snapshot.json backend/tests/test_ontology_conformance.py backend/Makefile
git commit -m "test: assert every stored ontology label matches what its id denotes

The invariant all five wrong-term defects violated. Uses a pinned snapshot
rather than a live API so an upstream rename is a reviewable diff, not a red
build, and an allowlist so known deviations stay silent while new ones fail.

Refs: docs/superpowers/specs/2026-07-30-ontology-data-quality-design.md §3.3"
```

---

## Task 4: Correct the stored terms

One revision, both copies, one transaction, with a preimage journal because steps 1–2 are not reversible by inverse remap.

**Files:**
- Create: `backend/alembic/versions/e6a2d9c04b71_correct_ontology_terms.py`
- Test: `backend/tests/test_ontology_term_migration.py` (create)

**Interfaces:**
- Consumes: Task 3's conformance test (to prove the result).
- Produces: a conformant corpus. Everything downstream assumes it.

- [ ] **Step 1: Record the baseline**

```bash
export PGPASSWORD=hnf1b_pass
psql -h localhost -p 5433 -U hnf1b_user -d hnf1b_phenopackets -tAc "
SELECT 'diseases', count(*) FROM phenopackets p, jsonb_array_elements(p.phenopacket->'diseases') d
UNION ALL SELECT 'HP:0034199 onsets', count(*) FROM phenopackets p, jsonb_array_elements(p.phenopacket->'diseases') d WHERE d->'onset'->'ontologyClass'->>'id'='HP:0034199'
UNION ALL SELECT 'features', count(*) FROM phenopackets p, jsonb_array_elements(p.phenopacket->'phenotypicFeatures') f
UNION ALL SELECT 'modifiers', count(*) FROM phenopackets p, jsonb_array_elements(p.phenopacket->'phenotypicFeatures') f, jsonb_array_elements(f->'modifiers') m;" | tee /tmp/ontology-baseline.txt
```

Expected: `diseases 1125`, `HP:0034199 onsets 134`, `features 7810`, `modifiers 771`.
If these differ, the corpus has changed since 2026-07-30 — re-derive the spec's numbers before continuing.

- [ ] **Step 2: Write the migration**

Create `backend/alembic/versions/e6a2d9c04b71_correct_ontology_terms.py`. Key requirements, in order:

1. Create `ontology_migration_journal (phenopacket_id text, source text, content_sha256 text, preimage jsonb)` and populate it with the pre-change `diseases` array for every affected record, from **both** tables. Steps 3–4 collapse two terms into one and deduplicate, which is not reversible by inverse remap.
2. Remap `diseases[].term` — `MONDO:0011593` and `MONDO:0010953` → `MONDO:0007669` / `"renal cysts and diabetes syndrome"`.
3. Deduplicate `diseases[]` with `jsonb_agg(DISTINCT ...)`; entries become identical.
4. Remap `HP:0034199` → `HP:0003577` / `"Congenital onset"` in `diseases[].onset.ontologyClass` **and** `subject.timeAtLastEncounter.ontologyClass`.
5. Relabel `HP:0003674` → `"Onset"` in the same two locations; **id unchanged**.
6. Apply every step to `phenopackets.phenopacket` and `phenopacket_revisions.content_jsonb`.

Reuse the SQL shape proven in revision `d4e8b1f60a27` — `jsonb_agg(... ORDER BY ord)` over `jsonb_array_elements(...) WITH ORDINALITY`. Two traps that already cost a debugging cycle there and are documented in its comments:

- `((elem->'type') - 'id' - 'label') || jsonb_build_object(...)` — the parenthesisation matters. Written the other way round it parses as `(build || type) - 'id' - 'label'` and deletes the keys it was meant to set.
- `jsonb_build_object` takes `"any"`, so asyncpg cannot infer a bare bind parameter's type. Wrap every bound value in `cast(:param as text)`. And never write `::jsonb` directly after a bind parameter — that is a syntax error under asyncpg.

`downgrade()` restores from the journal, matching on `phenopacket_id` + `source`, and aborts if the current content hash does not match what the journal recorded as the post-migration state.

- [ ] **Step 3: Dry-run in a rolled-back transaction before writing the revision file**

Prove the arithmetic first:

```sql
BEGIN;
-- steps 2-4 here
SELECT count(*) FROM phenopackets p, jsonb_array_elements(p.phenopacket->'diseases') d;         -- expect 864
SELECT DISTINCT jsonb_array_length(phenopacket->'diseases') FROM phenopackets WHERE phenopacket ? 'diseases';  -- expect {1}
SELECT d->'onset'->'ontologyClass'->>'id', count(*) FROM phenopackets p,
       jsonb_array_elements(p.phenopacket->'diseases') d GROUP BY 1;  -- expect HP:0003577 594, null 216, HP:0003674 54
ROLLBACK;
```

Do not proceed until all three match.

- [ ] **Step 4: Write the migration test**

```python
"""Term-correction migration (spec §3.2)."""

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_no_record_lost_a_disease(db_session):
    result = await db_session.execute(
        text("SELECT count(*) FROM phenopackets WHERE phenopacket ? 'diseases'")
    )
    assert result.scalar() == 864


@pytest.mark.asyncio
async def test_every_disease_array_has_exactly_one_entry(db_session):
    result = await db_session.execute(
        text(
            """SELECT DISTINCT jsonb_array_length(phenopacket->'diseases')
               FROM phenopackets WHERE phenopacket ? 'diseases'"""
        )
    )
    assert [r[0] for r in result.fetchall()] == [1]


@pytest.mark.asyncio
async def test_only_the_correct_mondo_term_remains(db_session):
    result = await db_session.execute(
        text(
            """SELECT DISTINCT d->'term'->>'id'
               FROM phenopackets p, jsonb_array_elements(p.phenopacket->'diseases') d"""
        )
    )
    assert [r[0] for r in result.fetchall()] == ["MONDO:0007669"]


@pytest.mark.asyncio
async def test_onset_totals_reconcile(db_session):
    result = await db_session.execute(
        text(
            """SELECT d->'onset'->'ontologyClass'->>'id', count(*)
               FROM phenopackets p, jsonb_array_elements(p.phenopacket->'diseases') d
               GROUP BY 1"""
        )
    )
    counts = {row[0]: row[1] for row in result.fetchall()}
    assert counts.get("HP:0003577") == 594
    assert counts.get("HP:0003674") == 54
    assert counts.get(None) == 216


@pytest.mark.asyncio
async def test_no_retired_id_survives_in_either_copy(db_session):
    for table, column in (
        ("phenopackets", "phenopacket"),
        ("phenopacket_revisions", "content_jsonb"),
    ):
        result = await db_session.execute(
            text(f"SELECT count(*) FROM {table} WHERE {column}::text LIKE '%HP:0034199%'")  # noqa: S608
        )
        assert result.scalar() == 0, table


@pytest.mark.asyncio
async def test_both_copies_agree(db_session):
    """A working-copy-only fix leaves the wrong term in every public response."""
    result = await db_session.execute(
        text(
            """SELECT count(*) FROM phenopackets p
               JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id
               WHERE p.phenopacket->'diseases' IS DISTINCT FROM r.content_jsonb->'diseases'
                 AND p.state = 'published'"""
        )
    )
    assert result.scalar() == 0


@pytest.mark.asyncio
async def test_feature_and_modifier_counts_unchanged(db_session):
    """This migration touches diseases and onsets, never features."""
    for sql, expected in (
        ("""SELECT count(*) FROM phenopackets p,
            jsonb_array_elements(p.phenopacket->'phenotypicFeatures') f""", 7810),
        ("""SELECT count(*) FROM phenopackets p,
            jsonb_array_elements(p.phenopacket->'phenotypicFeatures') f,
            jsonb_array_elements(f->'modifiers') m""", 771),
    ):
        result = await db_session.execute(text(sql))
        assert result.scalar() == expected
```

- [ ] **Step 5: Apply, verify, round-trip**

```bash
cd backend
uv run alembic upgrade head
uv run pytest tests/test_ontology_term_migration.py tests/test_ontology_conformance.py -q
uv run alembic downgrade -1 && uv run alembic upgrade head
uv run pytest tests/test_ontology_term_migration.py -q
```

Expected: all pass both times. The conformance test should now be green for onsets and diseases.

- [ ] **Step 6: Refresh derived state**

The migration changed content the search index and aggregation MVs derive from:

```bash
psql -h localhost -p 5433 -U hnf1b_user -d hnf1b_phenopackets -c "REFRESH MATERIALIZED VIEW global_search_index;"
```

Enumerate the other MVs (`\dm`) and refresh each. Confirm `/api/v2/search/global?q=renal` still returns results.

- [ ] **Step 7: Commit**

```bash
cd backend && uv run ruff format && cd ..
git add backend/alembic/versions/e6a2d9c04b71_correct_ontology_terms.py backend/tests/test_ontology_term_migration.py
git commit -m "fix(data): correct disease and onset terms in both stored copies

MONDO:0011593 (seizures, benign familial infantile, 2) and MONDO:0010953
(Fanconi anemia complementation group E) were annotated on every record as
RCAD and MODY5. Both -> MONDO:0007669, then deduplicated: the 261 dual-disease
records carried byte-identical entries apart from the term.

HP:0034199 (Late first trimester onset) labelled 'Prenatal onset' -> HP:0003577
Congenital onset, per the source Phenotype_modifier sheet's own synonym list.
HP:0003674 relabelled to its real name 'Onset'; id kept, since HPO has no
generic postnatal-onset term and the parent is a true ancestor.

Preimage journal supports downgrade; the collapse is not reversible by remap.

Refs: docs/superpowers/specs/2026-07-30-ontology-data-quality-design.md §3.2"
```

---

## Task 5: Restore the 408 dropped laterality annotations

Unlike Task 4, this information **is not in the database**. It must be re-derived from the source sheet.

**Files:**
- Create: `backend/alembic/versions/f1b7e35c92a0_restore_laterality.py`
- Create: `backend/migration/data/laterality_2026-07-30.csv` (de-identified fixture)
- Create: `backend/scripts/build_laterality_fixture.py`
- Test: `backend/tests/test_laterality_backfill.py` (create)

**Interfaces:**
- Consumes: Task 1's `parse_laterality`, Task 4's corrected corpus.
- Produces: modifier totals Bilateral 797 / Unilateral 408 / Left 119 / Right 112.

- [ ] **Step 1: Build the de-identified fixture**

Per ADR 0003, the raw workbook must not be committed: `ReviewBy` holds institutional email addresses the repository does not currently contain, and the dataset licence is unspecified. Write `backend/scripts/build_laterality_fixture.py` emitting **only**:

```csv
individual_id,phenotype_column,hpo_id,laterality_value
317,RenalCysts,HP:0000107,bilateral
```

No reviewer, no comments, no clinical columns beyond the six laterality-bearing ones (`Hyperechogenicity`, `RenalCysts`, `MulticysticDysplasticKidney`, `RenalHypoplasia`, `SolitaryKidney`, `UrinaryTractMalformation`). Record the workbook's sha256 in a header comment so the derivation is auditable.

Run it and confirm the row count is 1205 (797 + 177 + 119 + 112).

- [ ] **Step 2: Write the backfill test first**

```python
"""Laterality backfill (spec §3.2 step 5)."""

import pytest
from sqlalchemy import text

EXPECTED = {"Bilateral": 797, "Unilateral": 408, "Left": 119, "Right": 112}


@pytest.mark.asyncio
async def test_modifier_totals_match_the_source(db_session):
    result = await db_session.execute(
        text(
            """SELECT m->>'label', count(*)
               FROM phenopackets p,
                    jsonb_array_elements(p.phenopacket->'phenotypicFeatures') f,
                    jsonb_array_elements(f->'modifiers') m
               GROUP BY 1"""
        )
    )
    assert {row[0]: row[1] for row in result.fetchall()} == EXPECTED


@pytest.mark.asyncio
async def test_no_feature_has_contradictory_modifiers(db_session):
    result = await db_session.execute(
        text(
            """SELECT count(*) FROM phenopackets p,
                    jsonb_array_elements(p.phenopacket->'phenotypicFeatures') f
               WHERE f->'modifiers' @> '[{"id":"HP:0012832"}]'
                 AND (f->'modifiers' @> '[{"id":"HP:0012833"}]'
                   OR f->'modifiers' @> '[{"id":"HP:0012835"}]'
                   OR f->'modifiers' @> '[{"id":"HP:0012834"}]')"""
        )
    )
    assert result.scalar() == 0


@pytest.mark.asyncio
async def test_left_and_right_always_accompany_unilateral(db_session):
    result = await db_session.execute(
        text(
            """SELECT count(*) FROM phenopackets p,
                    jsonb_array_elements(p.phenopacket->'phenotypicFeatures') f
               WHERE (f->'modifiers' @> '[{"id":"HP:0012835"}]'
                   OR f->'modifiers' @> '[{"id":"HP:0012834"}]')
                 AND NOT f->'modifiers' @> '[{"id":"HP:0012833"}]'"""
        )
    )
    assert result.scalar() == 0


@pytest.mark.asyncio
async def test_feature_count_unchanged(db_session):
    """The backfill adds modifiers to existing features; it creates none."""
    result = await db_session.execute(
        text(
            """SELECT count(*) FROM phenopackets p,
               jsonb_array_elements(p.phenopacket->'phenotypicFeatures') f"""
        )
    )
    assert result.scalar() == 7810


@pytest.mark.asyncio
async def test_both_copies_backfilled(db_session):
    result = await db_session.execute(
        text(
            """SELECT count(*) FROM phenopacket_revisions r,
                    jsonb_array_elements(r.content_jsonb->'phenotypicFeatures') f,
                    jsonb_array_elements(f->'modifiers') m
               WHERE m->>'id' = 'HP:0012833'"""
        )
    )
    assert result.scalar() == 408
```

- [ ] **Step 3: Write the migration**

Join on `phenopacket-{individual_id}`, match the feature by `type.id`, and set `modifiers` from `parse_laterality(laterality_value)`. Requirements:

- **Skip and report**, never overwrite, any record whose `phenotypicFeatures` already carries a modifier for that term other than the one the source implies. A record edited since migration must not be silently reverted.
- Apply to both `phenopackets.phenopacket` and `phenopacket_revisions.content_jsonb`.
- Log the counts: rows in fixture, features matched, features skipped, modifiers written. Abort if matched + skipped ≠ fixture rows, which would mean the join is lossy.
- `downgrade()` removes the three unilateral modifier ids and leaves `Bilateral` (which predates this migration), restoring the 771 baseline.

- [ ] **Step 4: Apply and verify**

```bash
cd backend
uv run alembic upgrade head
uv run pytest tests/test_laterality_backfill.py tests/test_ontology_conformance.py -q
uv run alembic downgrade -1
psql -h localhost -p 5433 -U hnf1b_user -d hnf1b_phenopackets -tAc "
SELECT m->>'label', count(*) FROM phenopackets p,
 jsonb_array_elements(p.phenopacket->'phenotypicFeatures') f,
 jsonb_array_elements(f->'modifiers') m GROUP BY 1;"
uv run alembic upgrade head
```

Expected after downgrade: `Bilateral 797` only. After re-upgrade: all four totals.

- [ ] **Step 5: Refresh derived state and commit**

```bash
psql -h localhost -p 5433 -U hnf1b_user -d hnf1b_phenopackets -c "REFRESH MATERIALIZED VIEW global_search_index;"
cd backend && uv run ruff format && cd ..
git add backend/alembic/versions/f1b7e35c92a0_restore_laterality.py backend/migration/data/ backend/scripts/build_laterality_fixture.py backend/tests/test_laterality_backfill.py
git commit -m "fix(data): restore 408 dropped laterality annotations

The importer exact-matched four bare tokens against compound source values, so
177 'unilateral unspecified', 119 'unilateral left' and 112 'unilateral right'
were discarded while the phenotype row was still written.

Re-derived from a de-identified fixture (join key, phenotype column, laterality
value only — no reviewer emails, per ADR 0003) joined on phenopacket-{id}.
Records edited since migration are skipped and reported, never overwritten.

Refs: docs/superpowers/specs/2026-07-30-ontology-data-quality-design.md §3.2"
```

---

## Task 6: Render excluded phenotypic features

`hnf1b.org/phenopackets/phenopacket-317` shows `5 HPO` in the header and `Phenotypic Features (3)` in the section. The two `excluded: true` features are counted and never rendered, erasing the difference between "assessed and absent" and "not assessed".

**Files:**
- Modify: `frontend/src/views/PagePhenopacket.vue`
- Test: `frontend/tests/unit/views/PagePhenopacket.spec.js` (create or extend)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed downstream.

- [ ] **Step 1: Locate the discrepancy**

Run: `grep -n "phenotypicFeatures\|excluded\|HPO" frontend/src/views/PagePhenopacket.vue | head -30`

Find the header badge computation and the list render. One counts all features; the other filters `excluded === false` — or the filter is implicit in a `v-for` guard. Note both line numbers before editing.

- [ ] **Step 2: Write the failing test**

```javascript
import { describe, it, expect } from 'vitest';

const FEATURES = [
  { type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: false,
    modifiers: [{ id: 'HP:0012832', label: 'Bilateral' }] },
  { type: { id: 'HP:0000078', label: 'Abnormality of the genital system' }, excluded: false },
  { type: { id: 'HP:0004904', label: 'Maturity-onset diabetes of the young' }, excluded: false },
  { type: { id: 'HP:0000122', label: 'Unilateral renal agenesis' }, excluded: true },
  { type: { id: 'HP:0000079', label: 'Abnormality of the urinary system' }, excluded: true },
];

describe('PagePhenopacket phenotype rendering', () => {
  it('renders excluded features, not only present ones', () => {
    // phenopacket-317 has 3 present + 2 excluded; the page showed "5 HPO"
    // in the header and "Phenotypic Features (3)" in the section.
    const rendered = renderedFeatures(FEATURES);
    expect(rendered).toHaveLength(5);
  });

  it('the header count equals the rendered count', () => {
    expect(headerCount(FEATURES)).toBe(renderedFeatures(FEATURES).length);
  });

  it('distinguishes excluded features rather than showing them as present', () => {
    const excluded = renderedFeatures(FEATURES).filter((f) => f.excluded);
    expect(excluded).toHaveLength(2);
    expect(excluded.map((f) => f.type.id)).toEqual(['HP:0000122', 'HP:0000079']);
  });

  it('keeps laterality attached to its own feature', () => {
    const cyst = renderedFeatures(FEATURES).find((f) => f.type.id === 'HP:0000107');
    expect(cyst.modifiers.map((m) => m.label)).toEqual(['Bilateral']);
  });
});
```

Replace `renderedFeatures` / `headerCount` with the component's actual computed properties found in Step 1, importing them the way the repo's other view tests do.

- [ ] **Step 3: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/views/PagePhenopacket.spec.js`
Expected: FAIL — 3 rendered, header says 5.

- [ ] **Step 4: Render excluded features**

Remove the filter so excluded features appear, styled distinctly (strikethrough or a muted "excluded" chip — follow whatever convention `PhenotypicFeaturesCard.vue` already uses for negation, and reuse it rather than inventing one). Make the header badge and the section heading read from the same array.

The fourth assertion — laterality attached to its feature — is the spec's deferred display item; if the current markup renders modifiers as a detached chip, fix it here since the test now pins it.

- [ ] **Step 5: Verify in the browser**

```bash
make hybrid-up && make backend   # and `make frontend` in another shell
```

Open `http://localhost:3000/phenopackets/phenopacket-317`. Confirm: five features listed, two visibly marked excluded, header and section counts agree, and `Bilateral` sits on Renal cyst rather than floating.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/PagePhenopacket.vue frontend/tests/unit/views/PagePhenopacket.spec.js
git commit -m "fix(ui): render excluded phenotypic features

phenopacket-317 showed '5 HPO' in the header and 'Phenotypic Features (3)' in
the section: the two excluded features were counted and never rendered. That
erases the difference between 'assessed and absent' and 'not assessed', which
is the distinction the excluded flag exists to carry.

Refs: docs/superpowers/specs/2026-07-30-ontology-data-quality-design.md §3.4"
```

---

## Task 7: Wire the conformance test into CI and hand off to the curation program

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/superpowers/plans/2026-07-30-curation-data-model.md`
- Modify: `docs/superpowers/specs/2026-07-30-curation-data-model-design.md`

- [ ] **Step 1: Add the conformance test to the backend CI job**

It runs with the rest of `pytest`, so confirm it is not excluded by any marker filter. Add a separate step running `uv run python scripts/refresh_ontology_snapshot.py --check` **only** as a scheduled/manual job, never on PRs — an upstream HPO rename must not break unrelated PRs. Its purpose is to surface renames as a reviewable diff.

- [ ] **Step 2: Record the coupling in the curation plan**

Per spec §6, add to `docs/superpowers/plans/2026-07-30-curation-data-model.md`:

- In Global Constraints: a line stating this plan must land first, and that `HP:0033132` in Task 7's policy depends on it.
- In Task 7: a note that the four modifier IDs are defined in `migration/phenopackets/laterality.py` and must be referenced, not re-declared.
- In Task 9: a step making the domain validator call the conformance checker, so a wrong ID cannot enter through the form either — Task 9 alone would accept `HP:0033133` labelled "hyperechogenicity".

- [ ] **Step 3: Cross-reference the specs**

Add a line to the curation spec's §7 pointing at this spec's §6 boundary table.

- [ ] **Step 4: Full gate**

```bash
cd backend && uv run ruff format && uv run ruff check . && uv run pytest -q
cd ../frontend && npx vitest run && npm run lint:check && npx prettier --check src tests && npm run build
cd ../mcp && uv run pytest -q
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml docs/superpowers/
git commit -m "ci: enforce ontology conformance; record curation coupling

Refs: docs/superpowers/specs/2026-07-30-ontology-data-quality-design.md §6"
```

---

## Done criteria

- `HP:0033133`, `HP:0034199`, `MONDO:0011593`, `MONDO:0010953` appear in **zero** rows of `phenopackets.phenopacket` and `phenopacket_revisions.content_jsonb`.
- Disease entries: 864, every array length 1, every term `MONDO:0007669`.
- Onsets reconcile: `HP:0003577` 594, `HP:0003674` 54, null 216.
- Modifier totals: Bilateral 797, Unilateral 408, Left 119, Right 112. No feature carries Bilateral together with any sided modifier.
- Feature count unchanged at 7810.
- The conformance test passes against both copies and `hpo_terms_lookup`, with five allowlisted deviations each carrying a written justification.
- `phenopacket-317` renders five phenotypic features, two marked excluded, header count matching, `Bilateral` attached to Renal cyst.
- Search index and aggregation MVs refreshed; `/api/v2/search/global` still returns results.
- The curation plan records the dependency and the shared modifier constants.

**The test that matters:** re-running the original audit — resolve every stored `(id, label)` pair against the ontology — reports zero unexplained violations. Everything else in this plan is a consequence of that invariant having been unenforced.
