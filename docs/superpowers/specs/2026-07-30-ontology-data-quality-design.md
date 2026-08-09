# Ontology Data Quality — Design

**Date:** 2026-07-30
**Status:** Draft rev 2 (post adversarial review)
**Scope:** Correct five wrong ontology terms, restore 408 dropped laterality
annotations, and instrument the invariant that would have caught all six.

## 1. Problem

An audit of all 44 ontology terms used by this database against their authoritative
sources (HPO 2026-06-23, MONDO releases/2026-07-06, Orphanet, ECO) found **five terms
whose ID denotes something other than what its label claims**, and one import defect
that silently discarded a third of the laterality annotations.

These are not typos. Every instance has the same signature — **right label, wrong ID** —
and every one survived because no process ever compared an identifier against what it
denotes. The database has been serving them since migration.

| # | Stored | Label claims | ID actually denotes | Entries affected |
|---|---|---|---|---|
| T1 | `HP:0033133` | Renal cortical hyperechogenicity | Renal cortical **hypo**echogeneity | 460 × 2 |
| T2 | `MONDO:0011593` | Renal cysts and diabetes syndrome | **seizures, benign familial infantile, 2** | 864 × 2 |
| T3 | `MONDO:0010953` | Maturity-onset diabetes of the young type 5 | **Fanconi anemia complementation group E** | 261 × 2 |
| T4 | `HP:0034199` | Prenatal onset | **Late first trimester onset** | 180 × 2 |
| T5 | `HP:0003674` | Postnatal onset | **Onset** (abstract parent) | 82 × 2 |
| L1 | — | — | 408 features lost their laterality modifier | 408 × 2 |

"× 2" because every record exists twice: `phenopackets.phenopacket` (working copy) and
`phenopacket_revisions.content_jsonb` at `head_published_revision_id` (the public
snapshot that `visibility.py:80` serves).

T1 was corrected on 2026-07-30 by revision `d4e8b1f60a27`. T2–T5 and L1 are open.

### 1.1 Why it stayed invisible

Three independent mechanisms concealed it, and the third actively made it worse:

1. **No consumer renders the disease term.** `hnf1b.org/phenopackets/phenopacket-317`
   shows subject, phenotypes and variant; `diseases[]` appears nowhere. A benign
   infantile epilepsy syndrome has been the disease annotation on 864 records without a
   single reader ever seeing it.
2. **`hpo_terms_lookup` held the wrong ID paired with the right label**, so the
   curation form rendered `Renal cortical hyperechogenicity HP:0033133` — internally
   contradictory, outwardly correct.
3. **Label normalisation rewrote labels to agree with IDs.** Stored labels read
   "Renal cortical hypoechogeneity" — i.e. a process had already noticed the
   disagreement and resolved it *in favour of the wrong ID*. Normalising a label
   against an unvalidated identifier converts a detectable contradiction into a
   consistent falsehood. This is the single most important lesson in this document.

### 1.2 Root cause of L1

`backend/migration/phenopackets/extractors.py:157` (pre-fix):

```python
if value.lower() in ["bilateral", "unilateral", "left", "right"]:
```

An exact match against four bare tokens. The source records laterality as **compound**
text:

| Source value | Occurrences | Matched? |
|---|---|---|
| `bilateral` | 797 | yes |
| `unilateral unspecified` | 177 | **no** |
| `unilateral left` | 119 | **no** |
| `unilateral right` | 112 | **no** |

Only `bilateral` ever occurs bare, so 408 of 1205 laterality assertions were dropped
while the phenotype row was still written — producing a feature indistinguishable from
one whose laterality was never stated. The database contains 771 `Bilateral` modifiers
and zero of the other three, exactly as predicted by the code.

A second, independent defect: `direct_sheets_to_phenopackets.py:39` declares
`GID_CONFIG["modifiers"] = "1350764936"` and **never references it again**. The
`Phenotype_modifier` sheet is configured but never fetched; the modifier vocabulary in
`extractors.py` was hardcoded instead of being read from the sheet that defines it.

## 2. Evidence

Every figure below is measured, not estimated.

### 2.1 Full audit result — 44 terms

```
HP terms checked            40      unresolvable / obsolete    0
MONDO terms                  2      wrong                      2
ORPHA terms                  1      wrong                      0
ECO terms                    1      label imprecise            1
```

**Genuine wrong-term errors:** T1–T5 above.

**Benign label differences — ID correct, do not "fix":**

| Term | Stored label | Canonical name | Why benign |
|---|---|---|---|
| `HP:0000708` | Behavioral abnormality | Atypical behavior | listed HPO synonym |
| `HP:0012443` | Abnormality of brain morphology | Abnormal brain morphology | listed HPO synonym |
| `HP:0012622` | chronic kidney disease, not specified | Chronic kidney disease | deliberate local qualifier; **sheet definition matches canonical definition verbatim** |
| `HP:0002910` | Elevated hepatic transaminase | Elevated circulating hepatic transaminase concentration | HPO rename; **sheet definition matches canonical verbatim** |

The definition match is what proves the ID is right in the last two cases — and is the
discriminator this spec's validator uses.

`ECO:0000033` is *"author statement supported by traceable reference"*, stored as
"author statement" (which is `ECO:0000204`). The more specific ID is correct given
every feature carries a PMID; only the label is imprecise.

### 2.2 Collapse arithmetic for T2/T3

Verified by dry-run in a rolled-back transaction:

```
before:  1125 disease entries   603 records × 1 disease, 261 records × 2
after:    864 disease entries   864 records × 1 disease
```

All 261 dual-disease records carry **byte-identical** entries apart from the term —
same onset distribution for both (127 none / 112 `HP:0003577` / 11 `HP:0034199` /
11 `HP:0003674`). Deduplication is therefore lossless, not a merge.

Onset totals reconcile exactly: `594 = 471 surviving congenital + 123 remapped
prenatal`, `54 = 65 − 11 deduplicated`, `216 nulls = 343 − 127`.

### 2.3 Display gap — measured on production

`hnf1b.org/phenopackets/phenopacket-317`, against its source sheet row:

```
sheet fields populated   33
stored in the JSONB      24
rendered on the page      8
editable in curation      6
```

One rendering defect is a correctness bug rather than a coverage gap: the header
reads **"5 HPO"** while the section reads **"Phenotypic Features (3)"**. The two
`excluded: true` features — `HP:0000122` and `HP:0000079`, both explicitly assessed as
absent — are counted and never rendered. That erases the distinction between "assessed
and absent" and "not assessed", which is the distinction the excluded flag exists to
carry.

## 3. Design

Three parts, in dependency order: correct the source, correct the data, then make the
class of defect impossible to reintroduce. The third is the one that matters.

### 3.1 Import source corrections (complete, needs tests)

| File | Change |
|---|---|
| `migration/phenopackets/laterality.py` | **new** — `parse_laterality(value)` handling compound source text |
| `migration/phenopackets/extractors.py:157` | replaced inline exact-match map with `parse_laterality` |
| `migration/phenopackets/age_parser.py` | `HP:0034199`→`HP:0003577`; `HP:0003674` label → "Onset" |
| `migration/phenopackets/builder_simple.py` | both MONDO ids → `MONDO:0007669`; onset priority table de-duplicated |
| `migration/vrs/cnv_parser.py:378` | `MONDO:0011593` → `MONDO:0007669` |
| `migration/phenopackets/hpo_mapper.py:144` | `HP:0010935` (nonexistent) → `HP:0033132` |

`parse_laterality` verified against all six real source values; recovers 639 modifier
entries across 408 features. Bilateral and unilateral are mutually exclusive, so a
value naming both yields **no** modifiers rather than a contradiction.

**On `HP:0003577` for prenatal onset:** the source's own `Phenotype_modifier` sheet
lists "Prenatal onset" among the synonyms of `HP:0003577 Congenital onset`. That is the
curation vocabulary's stated intent, so it wins over `HP:0030674 Antenatal onset`,
which would also be defensible on pure ontology grounds. Recorded because a future
reader will otherwise "correct" it.

**On keeping `HP:0003674`:** HPO has no generic postnatal-onset term — its children are
Congenital, Neonatal, Infantile, Childhood, Adult, Antenatal, Embryonal, Fetal,
Pediatric and so on. `HP:0003674 "Onset"` is a true ancestor of any real onset, so it is
uninformative rather than false. The label is corrected; the ID stays. Representing
"postnatal" properly requires a term HPO does not have, and fabricating specificity
(e.g. mapping to Neonatal) would assert something the source never said.

### 3.2 Data corrections

One Alembic revision, wrapped in a single transaction, writing **every working copy
and each record's `head_published_revision_id` row**. Older revision rows are immutable
history and are deliberately left alone; §3.3's A3 scope is qualified to match.

| Step | Operation | Entries |
|---|---|---|
| 1 | `MONDO:0011593`, `MONDO:0010953` → `MONDO:0007669` "renal cysts and diabetes syndrome" | 1125 → 864 |
| 2 | deduplicate `diseases[]` (entries become identical) | 261 records |
| 3 | `HP:0034199` → `HP:0003577` in `diseases[].onset` and `subject.timeAtLastEncounter` | 180 |
| 4 | `HP:0003674` label → "Onset" (ID unchanged) | 82 |
| 5 | restore laterality modifiers from the source sheet | 408 features |
| 6 | `hpo_terms_lookup` rows realigned to canonical ids | 2 |

Steps 1–2 are **not** reversible by inverse remap: collapsing two terms into one and
deduplicating destroys which record held which. Steps 3–4 are reversible in principle
but are journalled alongside them so downgrade is one mechanism, not two. **Step 5 is
different again**: the
information does not exist in the database and must be re-derived from the spreadsheet,
joined on `phenopacket-{individual_id}` (verified: sheet `individual_id=317` ⇄
`phenopacket-317`, `subject.alternateIds = [report_id, IndividualIdentifier]`).

Step 5 therefore needs a committed fixture. Per ADR 0003's PII finding, that fixture is
**de-identified** — join key, phenotype column, laterality value only. No `ReviewBy`
emails, no comments, no clinical columns beyond the six laterality-bearing ones.

**Reversibility.** Steps 1–2 are not exactly reversible: collapsing two terms into one
and deduplicating loses which record had which. The revision therefore writes a
per-record preimage journal (`phenopacket_id`, `sha256(diseases)`, original JSON) into
a migration-owned table, and `downgrade()` restores from it, aborting on hash mismatch.
Every step restores from the journal; no step relies on an inverse remap.

### 3.3 The invariant — three assertions, not one

This is the deliverable that matters, and the obvious version of it is wrong.

**The naive invariant reproduces the defect.** "For every `(id, label)` pair, `label`
must equal the canonical name of `id`" is exactly what `test_hpo_label_integrity.py`
already asserts, and exactly what `_get_canonical_label` already enforces at import.
It is satisfiable by **editing the label**, so a wrong identifier becomes permanently
invisible the moment someone makes the check pass. That is not a hypothetical: it is
how T1 reached production and survived every subsequent audit.

Any label-versus-identifier check is **necessary but not sufficient**. Three assertions
are needed, and A1 is the one that catches the actual defect class.

#### A1 — Source integrity (the discriminator)

> For every row of the curation `Phenotype` sheet, the identifier must be corroborated
> by a field that normalisation does not touch.

Concretely, evaluated **in this order** — the description is authoritative whenever it
is present, and a name match is a fallback only when no description exists:

1. `phenotype_description` non-empty → it **must** match the canonical definition of
   `phenotype_id`. If it does not, the row fails. It does **not** fall through to a
   name check: falling through is what makes the invariant bypassable, because a
   normalised label always matches its (wrong) identifier's name.
2. `phenotype_description` empty → `phenotype_name` must match the canonical name or a
   listed synonym of `phenotype_id`.
3. Otherwise the row fails.

Rule 1 is the whole point. A wrong identifier whose label has already been normalised
passes any name-based check by construction; only a field the normaliser never touched
can refute it. A row with **neither** a matching description nor a matching name is
also a failure — silence is not corroboration.

The description is the discriminator because no process rewrites it. It already
separates the real defects from the benign deviations without any human judgement:

| Term | Sheet definition vs `phenotype_id`'s definition | Verdict |
|---|---|---|
| `HP:0012622` | matches verbatim | ID correct; label is a local qualifier |
| `HP:0002910` | matches verbatim | ID correct; HPO renamed the term |
| `HP:0033133` | matches **`HP:0033132`'s** definition | **ID wrong** |

A1 would have failed the import that created T1, and named `HP:0033132` as the term the
description actually describes.

#### A2 — No laundering

> The importer writes the curator's `phenotype_name` verbatim. It never rewrites a
> label to agree with an identifier.

`_get_canonical_label` is deleted, not fixed. A disagreement between name and identifier
is a defect for a human to resolve, not a value for code to overwrite — and A1 has
already caught it by the time this matters. The current debug-level log line
(`Normalized label for HP:0033133: 'hyperechogenicity' -> 'hypoechogeneity'`) becomes
impossible to emit because the code path ceases to exist.

#### A3 — Stored conformance (drift detection)

> Every `(id, label)` pair stored anywhere resolves against a pinned snapshot and
> matches the canonical name or a listed synonym, unless explicitly allowlisted.

This is the naive invariant, retained deliberately and labelled as insufficient. It
catches drift, typos, and terms retired upstream — not wrong-identifier defects. It is
worth having; it is not the guard.

**A3 must actually cover what it claims.** The existing guard checks one table and one
ontology. A3 enumerates every ontology-bearing path in both authoritative copies:

```
subject.timeAtLastEncounter.ontologyClass
phenotypicFeatures[].type
phenotypicFeatures[].modifiers[]
phenotypicFeatures[].onset.ontologyClass
phenotypicFeatures[].evidence[].evidenceCode
diseases[].term
diseases[].onset.ontologyClass
interpretations[].diagnosis.disease
interpretations[].diagnosis.genomicInterpretations[]
    .variantInterpretation.variationDescriptor.structuralType     (SO)
    .variantInterpretation.variationDescriptor.allelicState       (GENO)
hpo_terms_lookup.hpo_id
```

`structuralType` (SO terms, 864 records) and `allelicState` (GENO) are ontology-bearing
and were omitted from rev 1's list. The snapshot therefore covers **six** vocabularies:
HPO, MONDO, Orphanet, ECO, SO and GENO.

**A3's scope is working copies plus each record's head-published revision** — the same
scope §3.2's migration writes. Older revision rows are historical snapshots that may
legitimately contain superseded terms; asserting over them would make A3 permanently
red after any correction.

in `phenopackets.phenopacket`, `phenopacket_revisions.content_jsonb`, and the lookup
table. Two of the five stored defects are MONDO, so the snapshot covers **HPO, MONDO,
Orphanet and ECO** — HPO via `ontology.jax.org`, the rest via EBI OLS4 term lookup by
IRI. (OLS4's `search` endpoint does *not* do identifier lookup and returns plausible
wrong matches; use `/ontologies/{ont}/terms?iri=...`.)

#### Where the code lives

`backend/app/ontology/conformance.py` — a **production module**, not a test helper,
with the snapshot as package data. Tests import it, and so does the curation program's
`DomainValidator` (§6.2), so a wrong identifier cannot enter through the form either.
A test-only helper under `tests/` could not be imported by production code.

**Pinned, not live.** A test that calls `ontology.jax.org` is nondeterministic, fails
offline, and breaks CI whenever HPO renames a term. The snapshot is a committed JSON
file of `{id: {name, synonyms}}` covering only the ~44 terms this database uses,
refreshed by an explicit `make refresh-ontology-snapshot` target that shows a diff.
An HPO rename then surfaces as a reviewable diff rather than a red build.

**Known-deviation allowlist.** Four pairs legitimately deviate (§2.1). Each gets an
entry with a reason:

```python
ALLOWED_DEVIATIONS = {
    ("HP:0012622", "chronic kidney disease, not specified"):
        "Deliberate local qualifier; sheet definition matches canonical definition.",
    ("HP:0002910", "Elevated hepatic transaminase"):
        "HPO renamed the term; the sheet definition matches canonical verbatim.",
    ...
}
```

An allowlist rather than a blanket tolerance means a *new* deviation fails loudly while
a known one stays silent — and every exception carries a written justification.

**A second assertion catches the wrong-ID-right-name case directly.** For each term the
curation sheet defines, assert that the sheet's `phenotype_name` matches the canonical
name of its `phenotype_id`. That is precisely the check that would have caught T1, T2,
T3 and T5 at import time, and it is the check §1.1's label normalisation defeated.

### 3.4 Display corrections

Only one is in scope here — the rest belong to the curation console spec.

**Excluded phenotypes must render.** The `5 HPO` / `Features (3)` discrepancy is a
correctness bug on production: it hides curated negative findings. Excluded features
render in the list, visually distinguished, and the two counts agree.

Deferred to `2026-07-30-curation-data-model-design.md` and the Phase 3 console spec:
attaching laterality to its term, showing age, showing the disease, and showing
`expressions[syntax:"text"]` as *reported as*.

## 4. Non-goals

- The GA4GH conformance debt (ADR 0003) — ACMG field placement, extension value types,
  the `timeAtLastEncounter.age` wrapper. Untouched.
- Wiring `GID_CONFIG["modifiers"]` to actually read the `Phenotype_modifier` sheet.
  Worth doing, but the vocabulary is four stable terms and hardcoding them with a
  conformance test is not the risk that dropped 408 annotations. Recorded as follow-up.
- Correcting `ECO:0000033`'s label. One term, cosmetic, no reader.
- The 261 records' lost RCAD-vs-MODY5 distinction. If that distinction carries curation
  meaning it needs a dedicated field, which is curation-console scope.

## 5. Testing

| Area | Assertion |
|---|---|
| `parse_laterality` | all six real source values map correctly; `bilateral`+`unilateral` yields `[]`; `no` / `not reported` yield `[]` |
| Migration | round-trip upgrade/downgrade restores byte-identical JSON via the journal, **against a seeded fixture** — CI truncates the corpus, so production counts cannot be asserted in pytest |
| Collapse | 1125 → 864 disease entries; every array length 1; no record loses a disease |
| Onset | totals reconcile to 594/54/216 exactly |
| Laterality backfill | totals match the **resolved** fixture, not raw sheet-row counts — 939 rows collapse to 864 individuals and features deduplicate by HPO id, so 797 `bilateral` rows do not imply 797 stored modifiers. Conflicting duplicate rows go to a conflicts CSV, not into the fixture. |
| **A1 source integrity** | the T1 row fails and the message names `HP:0033132`; local qualifiers backed by a matching definition pass |
| **A2 no laundering** | `_get_canonical_label` does not exist; a curated label survives verbatim |
| **A3 conformance** | every stored `(id,label)` at every path in `ONTOLOGY_PATHS`, across HPO/MONDO/ORPHA/ECO, in both copies |
| **A3 limitation** | a normalised wrong id (`HP:0033133` + its own canonical name) passes A3 — asserted, so nobody mistakes A3 for the guard |
| **Hardcoded maps** | every entry of `ontology_service` and the `hpo_mapper` fallback passes `check_label` |
| Display | a record with excluded features renders them; header count equals rendered count |
| Both copies | working copy and published revision agree after migration |

## 6. Relationship to the curation program

This spec and `2026-07-30-curation-data-model-design.md` touch the same four files and
the same four modifier terms. The boundary is drawn by **who owns the fact**, and this
spec lands first because the curation program's Task 7 policy table already references
`HP:0033132`, which only exists after T1.

| Concern | Owner | Consumed by |
|---|---|---|
| Canonical `(id, label)` for every term | **this spec** — ontology snapshot §3.3 | curation validator, form vocabularies |
| The four laterality term IDs and labels | **this spec** — `laterality.py` constants | curation `allowed_modifiers`, UI control |
| `parse_laterality()` source-text parsing | **this spec** | import only |
| Laterality *data* for 408 legacy features | **this spec** — backfill §3.2 step 5 | — |
| `hpo_terms_lookup` row correctness | **this spec** | — |
| `hpo_terms_lookup.allowed_modifiers` column + per-term policy | curation spec Task 7 | domain validator, UI |
| Async domain validator | curation spec Task 9 | REST write path |
| Laterality UI control | Phase 3 console | — |
| Excluded features rendering | **this spec** §3.4 | — |
| Age / disease / *reported as* rendering | curation program | — |

Three concrete couplings the implementer must honour:

1. **One source of truth for the modifier terms.** `migration/phenopackets/laterality.py`
   defines `BILATERAL`/`UNILATERAL`/`LEFT`/`RIGHT`. The curation spec's `allowed_modifiers`
   migration and the Phase 3 UI must reference those IDs rather than re-declare them.
   Three copies of four HPO IDs is how T1 happened.
2. **The curation domain validator reuses this spec's conformance checker.** Curation
   Task 9 validates that a modifier is *permitted for a term*; this spec validates that
   a term *is what its label says*. Both are needed and they are different assertions —
   Task 9 would happily accept `HP:0033133` labelled "hyperechogenicity". The validator
   calls into the conformance helper so a wrong ID cannot enter through the form either.
3. **Curation Task 7's policy table is downstream of T1.** It lists `HP:0033132`. If
   this spec is not applied first, that row matches nothing and the policy silently
   admits no modifiers for renal cortical hyperechogenicity.

Revised program order:

```
  this spec  ──►  curation Phase 1-2  ──►  Phase 3 console
  (data + invariant)   (contract)          (UI, incl. laterality control)
```

The curation spec's plan needs two edits when this lands: Task 7 gains a dependency
note on this spec, and Task 9's validator gains the conformance call. Both are recorded
in §5 of the implementation plan.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Collapsing T2/T3 loses a curated distinction | confirmed byte-identical entries; preimage journal allows recovery |
| Laterality backfill writes to records edited since migration | join on `phenopacket_id`; skip and report any record whose `diseases`/`phenotypicFeatures` hash differs from the migration-era baseline |
| Snapshot drifts from live ontology | explicit refresh target with reviewable diff; snapshot version recorded in the file |
| Migration leaves the published revision stale | both copies written in one transaction; test asserts agreement |
| MV / search index serve pre-migration content | refresh aggregation MVs and `global_search_index` post-commit |
