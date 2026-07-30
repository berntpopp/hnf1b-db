# Ontology Defect Report

**Date:** 2026-07-30
**Status:** Findings — remediation shape not yet decided
**Verified against:** HPO 2026-06-23 (`ontology.jax.org`), MONDO releases/2026-07-06,
Orphanet (OLS4), the live database (923 records), and `HNF1B_DataCuration.xlsx`.

Nine ontology term identifiers in this codebase denote something other than what their
label claims, and one import defect discarded 408 curated laterality annotations.
Every instance shares one signature — **right label, wrong identifier** — and two
mechanisms actively concealed them.

## 0. Provenance: the curation source is not at fault

Eight of the nine wrong identifiers **appear nowhere in the workbook**. They are
hardcoded in application and migration code. Verified by scanning every cell of all ten
sheets:

| Identifier | In the workbook? | Origin |
|---|---|---|
| `HP:0033133` | **yes** | curation sheet |
| `MONDO:0011593`, `MONDO:0010953` | no | `builder_simple.py`, `cnv_parser.py` |
| `HP:0034199`, `HP:0003674` | no | `age_parser.py` |
| `HP:0003149` | no | `ontology_service.py` |
| `HP:0010935`, `HP:0004729`, `HP:0004719` | no | `hpo_mapper.py` defaults |

Where the sheet does specify a term, it specifies the **correct** one. `HP:0002149`
Hyperuricemia and `HP:0003577` Congenital onset are both present and correct in the
workbook, and both are contradicted by hardcoded values in code (T6, T4).

All 408 discarded laterality annotations were **correct in the sheet** (§3); the
importer failed to read them.

The single sheet-side error, `HP:0033133`, arrived with the **correct name and the
correct description**:

```
Hyperechogenicity | HP:0033133 | Renal cortical hyperechogenicity
                  | "Increased echogenecity of the kidney cortex."
```

Two of three fields were right, and the description matches `HP:0033132`'s canonical
definition verbatim — enough to detect and repair the identifier automatically. Instead
the importer discarded the curator's correct name in favour of the wrong identifier's
name (§4.1), converting a single recoverable field error into an inverted clinical
assertion across 460 features.

**The curation data was sound. The pipeline that consumed it was not.**

This document records findings and evidence only. It does not propose a remediation
plan; see §7 for what is already applied.

---

## 1. Wrong terms present in stored data

Counts are `entries × 2` because every record exists twice: `phenopackets.phenopacket`
(working copy) and `phenopacket_revisions.content_jsonb` at
`head_published_revision_id`, which `visibility.py:80` serves to the public.

| # | Stored ID | Label claims | Identifier actually denotes | Entries |
|---|---|---|---|---|
| **T1** | `HP:0033133` | Renal cortical hyperechogenicity | **Renal cortical hypoechogeneity** | 460 × 2 |
| **T2** | `MONDO:0011593` | Renal cysts and diabetes syndrome | **seizures, benign familial infantile, 2** | 864 × 2 |
| **T3** | `MONDO:0010953` | Maturity-onset diabetes of the young type 5 | **Fanconi anemia complementation group E** | 261 × 2 |
| **T4** | `HP:0034199` | Prenatal onset | **Late first trimester onset** | ~1,068 × 2 (see below) |
| **T5** | `HP:0003674` | Postnatal onset | **Onset** (abstract parent) | ~445 × 2 (see below) |

**T4/T5 entry counts corrected (2026-07-30).** The `180 × 2` and `82 × 2` figures originally
printed above were never the number of occurrences of `HP:0034199` / `HP:0003674` in the
corpus — they were the count in two of the *four* paths the importer writes each onset id to.
`diseases[].onset.ontologyClass` and `subject.timeAtLastEncounter.ontologyClass` are the two
paths a reader would expect onset to live in, and are the two the original audit queried;
`phenotypicFeatures[].onset.ontologyClass` and `phenotypicFeatures[].onset.age.ontologyClass`
are the two it did not. Per-path counts in the working copy, measured before correction
migration `efa98cccfa51` ran (each doubled again by the head-published revision copy, per the
note above the table):

| Path | `HP:0034199` (T4) | `HP:0003674` (T5) |
|---|---|---|
| `diseases[].onset.ontologyClass` | 134 | 65 |
| `subject.timeAtLastEncounter.ontologyClass` | 46 | 17 |
| `phenotypicFeatures[].onset.ontologyClass` | 678 | 298 |
| `phenotypicFeatures[].onset.age.ontologyClass` | 210 | 65 |
| **Total** | **1,068** | **445** |

`phenotypicFeatures[].onset.age.ontologyClass` is a second, independent copy of the same onset
id, nested under each feature's own `onset.age` key rather than derived from
`phenotypicFeatures[].onset.ontologyClass`. Of the 275 features carrying this path, **10**
disagreed with their sibling `onset.ontologyClass` value (outer `HP:0034199`, nested
`HP:0003674`); migration `efa98cccfa51` corrects each independently from its own stored value,
never copying from the other.

`interpretations[].diagnosis.disease` was surfaced by the same investigation that found the two
`phenotypicFeatures[]` paths above, and is corrected in the same migration commit — but its
journalled pre-correction values show it carries only the T2 `MONDO:0011593` defect (880
journalled rows across both copies, confirmed via `ontology_migration_journal`); zero of those
rows contain `HP:0034199` or `HP:0003674`. It is not a fifth onset path and is not counted in
the totals above.

**T1** inverts a clinical finding. Hyper- and hypo-echogenicity are opposite
ultrasound observations, and renal cortical hyperechogenicity is the characteristic
HNF1B feature. The correct term is `HP:0033132`. This is the one defect with a
sheet-side component — a wrong identifier alongside a correct name and description
(§0) — and the import turned it from a single wrong field into an inverted assertion.

**T2/T3** mean every record in the database has been annotated with a benign infantile
epilepsy syndrome or a Fanconi anaemia subtype as its disease. The correct term is
`MONDO:0007669` *"renal cysts and diabetes syndrome"*, whose definition reads: *"Renal
cysts and diabetes syndrome (RCAD) is a rare form of maturity-onset diabetes of the
young (MODY) characterized clinically by heterogeneous cystic renal disease and
early-onset familial non-autoimmune diabetes. Pancreatic atrophy, liver dysfunction
and genital tract anomalies are also features"* — the HNF1B spectrum exactly.

MONDO does not maintain RCAD and MODY5 as separate entities; resolving *"maturity-onset
diabetes of the young type 5"* returns `MONDO:0007669`.

**T4** is far more specific than intended, and is **not** a curation error: the
workbook contains no HPO identifier for onset at all. `AgeOnset` holds free text
(`prenatal`, `postnatal`, `12y`), and `age_parser.py` chose the identifiers. The
source's own `Phenotype_modifier` sheet lists *"Prenatal onset"* among the synonyms of
`HP:0003577 Congenital onset`, which is the curated intent the importer overrode.

**T5** is likewise hardcoded, not curated. It is not false, but vacuous. `HP:0003674 "Onset"` is defined as *"The age group in
which disease manifestations appear"* — a true ancestor of any onset. HPO has **no
generic postnatal-onset term**; its children are Congenital, Neonatal, Infantile,
Childhood, Pediatric, Young adult, Adult, Late, Middle age, Antenatal, Embryonal, Fetal,
Perimenopausal, Postmenopausal, Puerpural. The label asserts a specificity the
identifier does not carry.

---

## 2. Wrong terms present only in code

These never reached the database but are live in application and import paths.

| # | ID | Claimed label | Actually denotes | Location |
|---|---|---|---|---|
| **T6** | `HP:0003149` | Hyperuricemia | **Hyperuricosuria** | `app/services/ontology_service.py:230` |
| **T7** | `HP:0010935` | Increased echogenicity of kidneys | **Abnormality of the upper urinary tract** | `migration/phenopackets/hpo_mapper.py` |
| **T8** | `HP:0004729` | Solitary functioning kidney | **Acute tubulointerstitial nephritis** | `migration/phenopackets/hpo_mapper.py` |
| **T9** | `HP:0004719` | Oligomeganephronia | **Hyperechogenic kidneys** | `migration/phenopackets/hpo_mapper.py` |
| **T10** | `HP:0010945` | Fetal renal anomaly | **Fetal pyelectasis** | `migration/phenopackets/hpo_mapper.py` |
| **T11** | `HP:0100575` | Pancreatic hypoplasia | **Neoplasm of the gallbladder** | `migration/phenopackets/hpo_mapper.py` |
| **T12** | `HP:0000108` | Multiple glomerular cysts | **Renal corticomedullary cysts** | `app/core/config.py` (`HPOTermsConfig.any_kidney`) |
| **T13** | `HP:0001970` | Oligomeganephronia | **Tubulointerstitial nephritis** | `app/core/config.py` (`HPOTermsConfig.any_kidney`) |

**T6** confuses urine with blood. Hyperuricosuria is elevated urinary uric acid;
hyperuricemia is elevated serum uric acid. The correct term is `HP:0002149`, which the
curation sheet uses correctly.

**T7–T11** sit in `HPOMapper`'s default dictionary. That dictionary is normally replaced
at runtime by the sheet (§4), so these have not reached the corpus — but
`hpo_mapper.py:238` falls back to it when the Sheets fetch fails:

```python
if phenotypes_df is None or phenotypes_df.empty:
    logger.warning("No phenotype dataframe provided, using default mappings")
    return
```

A transient Sheets outage during an import would therefore write five wrong terms.
T9 is notable: `HP:0004719` *is* an echogenicity term, labelled here as
oligomeganephronia. **T10 and T11** were found running Task 2's `check_label` over
every entry in this dictionary and resolving each against the live HPO API, after T6–T9
were already fixed — the same audit method, applied completely rather than by hand.
`HP:0012759` "Neurodevelopmental abnormality", also in this dictionary, resolved as
**correct**; it only failed `check_label` because it was missing from the pinned
snapshot, a coverage gap rather than a tenth defect, closed by adding it to
`scripts/refresh_ontology_snapshot.py`'s explicit term list.

**T12 and T13** were found by applying the same `check_label` sweep method to a sixth
independent hardcoded ontology map, `app/core/config.py`'s `HPOTermsConfig.any_kidney`
(the fifth map, `app/phenopackets/clinical_queries.py`'s `MORPHOLOGY_TERM_LABELS`, was
found and corrected the same way — see `backend/tests/test_clinical_queries_morphology.py`
— and is not renumbered here). Both wrong ids appeared in zero stored records; the
corpus stores the intended concepts as `HP:0100611` (103 features) and `ORPHA:2260` (75
features), so any filter built on `any_kidney` with the wrong ids silently excluded all
178 of those stored feature rows. Every remaining id/label pair in `HPOTermsConfig`,
including its scalar CKD aliases, was independently verified conformant by the same
sweep (`backend/tests/test_hpo_terms_config_conformance.py`).

**Status (2026-07-30): T1–T11 are now all corrected.** T1–T5 (stored data) by
migrations `d4e8b1f60a27` (T1) and `efa98cccfa51` (T2–T5); T6, T8–T11 in
`app/services/ontology_service.py` and `migration/phenopackets/hpo_mapper.py`; T7 was
already fixed at source before this pass. See
`docs/superpowers/plans/2026-07-30-ontology-data-quality.md` Tasks 3 and 6.

**T12 and T13 are also now corrected**, in `app/core/config.py`'s
`HPOTermsConfig.any_kidney`.

---

## 3. Dropped data — 408 laterality annotations

`migration/phenopackets/extractors.py:157`, before correction:

```python
if value.lower() in ["bilateral", "unilateral", "left", "right"]:
```

An exact match against four bare tokens. The source records laterality as **compound**
text:

| Source value | Occurrences | Matched |
|---|---|---|
| `bilateral` | 797 | yes |
| `unilateral unspecified` | 177 | **no** |
| `unilateral left` | 119 | **no** |
| `unilateral right` | 112 | **no** |

Only `bilateral` ever occurs bare. The phenotype row was still written, so 408 features
carry no modifier and are indistinguishable from features whose laterality was never
stated. The database holds 771 `Bilateral` modifiers and **zero** `Unilateral`, `Left`
or `Right` — exactly as the code predicts.

Independently, `direct_sheets_to_phenopackets.py:39` declares
`GID_CONFIG["modifiers"] = "1350764936"` and never references it again. The
`Phenotype_modifier` sheet — which defines the four modifier terms, all four verified
correct against HPO — is configured but never fetched. The modifier vocabulary was
hardcoded instead.

---

## 4. Mechanism A — label laundering

The most important finding. Two independent components assume the **identifier is
correct and the label is the thing to fix**. Both are wrong in the same direction, and
the curator's label was the reliable signal of intent.

### 4.1 In the importer

`migration/phenopackets/hpo_mapper.py`, `build_from_dataframe`:

```python
self.hpo_mappings = {}                                        # line 241 — discards defaults
...
canonical_label = self._get_canonical_label(hpo_id, fallback) # line 253 — trusts the id
if pd.notna(source_label) and canonical_label != source_label:
    logger.debug(
        f"Normalized label for {hpo_id}: '{source_label}' -> '{canonical_label}'"
    )
```

For T1 this emitted, at **debug** level:

```
Normalized label for HP:0033133:
  'Renal cortical hyperechogenicity' -> 'Renal cortical hypoechogeneity'
```

The importer detected the disagreement, resolved it in favour of the wrong identifier,
logged the inversion below the default log level, and continued. This converted a
*detectable contradiction* into a *consistent falsehood* — which is why every later
audit of stored data found nothing: labels and identifiers agreed perfectly.

Line 241 also means corrections to the default dictionary have no effect in production.

### 4.2 In CI

`backend/tests/test_hpo_label_integrity.py`, run by `.github/workflows/ci.yml:149`:

```python
if official != our_label:
    mismatches.append(...)
```

Exact equality against the canonical HPO name, no synonym tolerance. The only way to
make it pass is to rewrite the label. `hpo_terms_lookup` now holds canonical names for
every term — including `HP:0033133 → "Renal cortical hypoechogeneity"` — which is
consistent with the table having been normalised to satisfy this test.

The guard did not merely fail to catch these defects. It created pressure toward the
mechanism that concealed them.

**Any replacement invariant must not have this property.** Checking "does the label
match the identifier" is satisfiable by editing the label. The discriminator that works
is the curator's `phenotype_description`, which normalisation never touches:

| Term | Sheet definition vs canonical definition | Conclusion |
|---|---|---|
| `HP:0012622` | matches verbatim | identifier correct, label is a local qualifier |
| `HP:0002910` | matches verbatim | identifier correct, HPO renamed the term |
| `HP:0033133` | matches **`HP:0033132`'s** definition | **identifier wrong** |

---

## 5. Mechanism B — four independent ontology maps

No single source of truth. Four places define term-to-label mappings, and three contain
errors:

| Map | Errors |
|---|---|
| `migration/phenopackets/hpo_mapper.py` defaults | T7, T8, T9 |
| `hpo_terms_lookup` table | normalised to canonical names (§4.2) |
| `app/services/ontology_service.py` | T2, T3, T6 |
| `frontend/src/utils/ageParser.js` | T4, with a third reading |

`ageParser.js:53` is its own finding:

```javascript
'HP:0034199': 0.08, // Neonatal onset (approx 1 month)
```

Three components hold three different beliefs about one identifier — the importer calls
it "Prenatal onset", the frontend calls it "Neonatal onset" and assigns it a numeric age
of 0.08 years, and HPO says it is "Late first trimester onset". That numeric value feeds
age-of-onset analysis.

---

## 6. Why no consumer noticed

| | |
|---|---|
| **Disease terms are never rendered.** | `hnf1b.org/phenopackets/phenopacket-317` shows subject, phenotypes and variant. `diseases[]` appears nowhere, so T2/T3 were invisible to every reader for the lifetime of the database. |
| **The lookup table paired the wrong id with the right label.** | Before normalisation, the curation form rendered `Renal cortical hyperechogenicity HP:0033133` — internally contradictory, outwardly correct. |
| **The CI guard checks one table, one ontology.** | Only `hpo_terms_lookup`, only `HP:*`. Never the stored phenopackets, never MONDO/ORPHA/ECO, and it `skip`s when the API is unreachable. |
| **CI runs against an empty corpus.** | `conftest.py::_isolate_database_between_tests` is `autouse=True` and truncates `phenopackets` and `phenopacket_revisions` after every test. Any assertion over stored data passes vacuously. |

---

## 7. Current status

**Applied locally, uncommitted:**

- `backend/alembic/versions/d4e8b1f60a27_fix_renal_echogenicity_hpo_term.py` — T1
  corrected in both copies and in `hpo_terms_lookup` (460 + 460 + 1). Round-trip tested;
  feature count 7810 and modifier count 771 unchanged.
- `migration/phenopackets/laterality.py` — new `parse_laterality()` handling compound
  values; verified against all six real source values, recovers 639 modifier entries
  across 408 features.
- `extractors.py`, `age_parser.py`, `builder_simple.py`, `cnv_parser.py`,
  `hpo_mapper.py` — T4, T5, T7 and both MONDO ids corrected at source. Lint-clean.

**Not addressed:**

- T2, T3, T4, T5 in stored data (1725 entries across both copies).
- T6 in `ontology_service.py`; T8, T9 in `hpo_mapper.py` defaults.
- The 408 dropped laterality annotations.
- `ageParser.js` — T4 plus the erroneous 0.08-year age.
- Both laundering mechanisms (§4). **Until `_get_canonical_label` stops rewriting
  curator labels, a corrected sheet row can be re-inverted on the next import.**
- The unused `Phenotype_modifier` sheet wiring.

**Known-good — do not "fix":**

`HP:0000708` (Behavioral abnormality) and `HP:0012443` (Abnormality of brain morphology)
are listed HPO synonyms. `HP:0012622` and `HP:0002910` are a deliberate local qualifier
and an HPO rename respectively, both with sheet definitions matching canonical verbatim.
`ORPHA:2260` Oligomeganephronia and the four laterality modifiers are correct.
`ECO:0000033` is *"author statement supported by traceable reference"*, stored as
"author statement" — label imprecise, identifier defensible.

---

## 8. Scale

```
ontology terms audited                        44   (+ hpo_mapper.py's full default
                                                       dictionary, audited a second
                                                       pass with check_label — T10, T11)
identifiers denoting something else           13
  originating in code                         12   (T7-T13)
  originating in the curation sheet            1   (with correct name + description)
of those, present in stored data               5   (T1-T5; T10/T11 never reached the
                                                       corpus, same as T7-T9)
stored entries affected            ~2,976 × 2 copies  (corrected 2026-07-30 -- see §1's
                                                       T4/T5 per-path breakdown; the original
                                                       figure summed T4/T5 occurrences from
                                                       only 2 of their 4 stored paths)
laterality annotations discarded             408   (all correct in the sheet)
independent ontology maps                      4
maps containing errors                         3
```

**Status (2026-07-30): resolved.** All 11 identifiers corrected — T1-T5 in stored data
(migrations `d4e8b1f60a27`, `efa98cccfa51`), T6-T11 in application/migration code
(`app/services/ontology_service.py`, `migration/phenopackets/hpo_mapper.py`); the 408
laterality annotations restored (migration `18cfc57307f6`); both label-laundering
mechanisms deleted (`hpo_mapper._get_canonical_label`, `scripts/normalize_hpo_labels.py`).
See `docs/superpowers/plans/2026-07-30-ontology-data-quality.md`.

**T12 and T13 also corrected the same day**, found by the same `check_label` sweep
applied to a sixth independent hardcoded map (`app/core/config.py`'s
`HPOTermsConfig.any_kidney`); the programme total is now **13** wrong identifiers.

For one representative record (`phenopacket-317`): the source sheet holds 33 curated
fields, the database stores 24, the public page renders 8, and the curation form can
edit 6.

## 9. Related

- `docs/adr/0003-ga4gh-conformance-debt.md` — deliberately deferred: GA4GH field placement
  and extension value types.
  **Correction (2026-07-30):** this entry originally read "Not overlapping with these
  findings." That is true of the ADR's D1–D4 and **false of its D5**, which is the same
  laterality loss recorded in §3 above. The ADR's D5 deferral has been superseded by its
  Amendment 1, which authorizes the journalled, reversible restoration of the 408 annotations
  as data recovery. D1–D4 remain deferred.
- `docs/superpowers/specs/2026-07-30-ontology-data-quality-design.md` and its plan —
  rev 2, rewritten after adversarial review. The invariant is now three assertions
  anchored on the curator's description (§4 explains why a label-vs-id check cannot
  work), migration tests run against seeded fixtures because CI truncates the corpus,
  and whole-corpus arithmetic moved to a preflight script.
