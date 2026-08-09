# Curation Data Model — Design

**Date:** 2026-07-30
**Status:** Draft (rev 3)
**Scope:** Where curated case, variant and phenotype facts live, so the curation
console can be built. Phases 1–2 of a 3-phase program.

Revisions 1 and 2 were reviewed adversarially and both found unsafe to plan against.
Rev 1 proposed two nonconformant GA4GH placements and a derived cohort that fabricated
certainty. Rev 2 fixed those but introduced a relational side table that bypassed the
publication/revision architecture, and created a dual-location window for ACMG and
classification criteria with no dual reads.

Rev 3 follows a scope decision: **build the curation console on the conventions the
corpus already uses.** The GA4GH conformance debt uncovered during review is real,
pre-existing, and separable; it is recorded in
`docs/adr/0003-ga4gh-conformance-debt.md` and deliberately not paid here.
That decision removes four of the five blockers rather than patching them (§10).

## 1. Problem

`/phenopackets/create` can express six curation facts: phenopacket ID, subject ID,
sex, a bare PMID, a variant notation string, and a phenotype present/excluded/unknown
flag.

The source curation model — `HNF1B_DataCuration.xlsx`, 939 rows over 864 individuals —
carries 28 curation dimensions. Most already exist in the production JSONB and the form
cannot reach them. Four have no home at all. One was flattened during migration.

This spec closes those gaps **additively**: it introduces no change to any existing
JSONB path, so every one of the 923 legacy records remains valid and every existing
reader keeps working unchanged.

## 2. Evidence base

Verified against the live database (923 records), the pinned `phenopackets 2.0.2.post5`
protobuf, and the spreadsheet. Counts are measured.

### 2.1 Dimensions in the JSONB but unreachable from the form

| Spreadsheet column | JSONB path | Records |
|---|---|---|
| `AgeReported` | `subject.timeAtLastEncounter.iso8601duration` | 664 |
| `AgeOnset` | `diseases[].onset.ontologyClass` | 782 |
| `report_id`, `IndividualIdentifier` | `subject.alternateIds[]` | 864 |
| `VariantReported` | `…variationDescriptor.expressions[syntax="text"]` | 440 |
| `VariantType` | `…variationDescriptor.structuralType` | 864 |
| `hg19`/`hg38` + `_INFO` | `…extensions[name="coordinates"]`, `expressions[syntax="vcf"]` | 864 |
| `Varsome` | `expressions[syntax="hgvs.c"]` 424, `[syntax="hgvs.p"]` 363 | 424 |
| `verdict_classification` | `genomicInterpretations[].interpretationStatus` | 864 |
| `criteria_classification`, `system_classification` | `variantInterpretation.extensions[name="classification_criteria"]` | 864 |
| `ID` (dbVar) | `…extensions[name="external_reference"]` | 440 |
| `PublicationType` | `metaData.externalReferences[].reference` | 939 rows |
| `Comment` | `metaData.comment` | 864 |
| `ReviewBy`, `ReviewDate` | `metaData.reviewer`, `metaData.updates[]` | 864 |

The last two columns of §2.1 are counts of *records*, except `PublicationType`, which
is a count of spreadsheet *rows*. §2.5 explains why the two differ.

### 2.2 Dimensions with no home

| Column | Stated | `not reported` | Current storage |
|---|---|---|---|
| `Cohort` (`born`/`fetus`) | 872 / 67 | — (never absent) | none |
| `DetecionMethod` [sic] | 877 | 62 | leaked into `metaData.comment` in 90 records |
| `Segregation` | 448 | 491 | none |
| `FamilyHistory` | 549 | 390 | none |

All counts are spreadsheet rows (939 total).

### 2.3 Laterality was flattened

| Modifier | Uses in DB |
|---|---|
| HP:0012832 Bilateral | 771 |
| HP:0012833 Unilateral / HP:0012835 Left / HP:0012834 Right | 0 |

| Term | Stored | With `Bilateral` | Source bilateral | Source unilateral (lost) |
|---|---|---|---|---|
| HP:0000107 Renal cyst | 657 | 287 | 295 | 101 |
| HP:0000003 Multicystic kidney dysplasia | 596 | 158 | 167 | 79 |
| HP:0000089 Renal hypoplasia | 575 | 112 | 116 | 68 |
| HP:0000079 Abnormality of the urinary system | 329 | 41 | 42 | 80 |
| HP:0033132 Renal cortical hyperechogenicity | — | — | 177 | 32 |

### 2.4 The age display bug

| Path | Records | Read by |
|---|---|---|
| `timeAtLastEncounter.iso8601duration` (corpus convention) | 664 | `sql_fragments/paths.py:19` `CURRENT_AGE_PATH` — works |
| `timeAtLastEncounter.age.iso8601duration` (GA4GH-conformant) | **0** | `SubjectCard.vue:119`, `PagePhenopacket.vue:450` — return nothing |
| `timeAtLastEncounter.ontologyClass` | 63 (46 HP:0034199, 17 HP:0003674) | — |

Last-encounter age therefore never renders. The fix is to correct the two frontend
readers to the corpus path, **not** to migrate 664 records. `PagePhenopacket.vue:454`
has a separate `vitalStatus.timeOfDeath.age` fallback, so the bug is scoped to
last-encounter age.

`backend/app/phenopackets/age_utils.py` is dead code — nothing imports it — and its SQL
is independently invalid (`phenopacket->>'subject'->>'timeAtLastEncounter'` raises
`operator does not exist: text ->> unknown`, because the first `->>` yields text). It
is deleted, not repaired.

### 2.5 Source cardinality

| Quantity | Value |
|---|---|
| Spreadsheet rows | 939 |
| Distinct `individual_id` | **864** |
| Rows flagged duplicate in `DupCheck` | 148 |
| DB phenopackets | 923 (10 soft-deleted) |
| DB records with `interpretations` | 864 |
| DB records with no source row | 59 |

`direct_sheets_to_phenopackets.py:222` groups rows by `individual_id`. Every value
count in this document is a row count unless stated otherwise. Because rev 3 performs
**no backfill**, duplicate-row merge rules are not needed here; they are recorded as an
open question for the conformance program.

### 2.6 Bugs the current form introduces

| # | Defect | Location | Phase |
|---|---|---|---|
| B1 | `moleculeContext` receives a VEP consequence (`"missense_variant"`) | `VariantAnnotationForm.vue:253` | 1 |
| B2 | `variation` receives `{notation: …}` instead of a VRS object | `VariantAnnotationForm.vue:257` | 1 |
| B3 | Undocumented top-level `publications` key persisted | `PhenopacketCreateEdit.vue:209`, spread at `:326` | 1 |
| B4 | Form-added phenotypes carry no `evidence`, while all 7810 stored features do | `PhenotypicFeaturesSection.vue:230` | 3 |
| B5 | Interpretation IDs are `interpretation-${Date.now()}-${rand}`; corpus uses `interpretation-001` | `VariantAnnotationForm.vue:243` | 3 |
| B6 | `cycleState` mutates the shared prop element | `PhenotypicFeaturesSection.vue:223-240` | 1 |
| B7 | Non-standard `impact` / `caddScore` written onto `VariantInterpretation` | `VariantAnnotationForm.vue:265-270` | 1 |

B1–B3, B6 and B7 are fixed in Phase 1 **before** any validation is tightened;
tightening first would reject the form's own payloads.

### 2.7 Two authoritative copies

`phenopackets.phenopacket` is the mutable working copy;
`phenopacket_revisions.content_jsonb` at `head_published_revision_id` is the public
snapshot (`visibility.py:80`). 1003 revision rows, 933 audit rows. **Everything this
spec stores lives inside the phenopacket JSONB**, so it inherits revisioning,
audit, draft/publish isolation, rollback and optimistic locking automatically. That is
the central reason rev 2's side table was abandoned.

## 3. Program shape

| Phase | Deliverable | Touches existing data? |
|---|---|---|
| **1 — Stop the corruption** | Fix B1, B2, B3, B6, B7. Correct the two age readers. Delete dead `age_utils`. | no |
| **2 — Storage contract** (this document) | `hnf1bCuration` block, `segregation` extension, laterality reference data + validation, four vocabulary endpoints, export modes, MCP contract. | no |
| **3 — Curation console** | The form: publication-anchored, autosave, dense keyboard phenotype grid with laterality, variant normalize-then-confirm with *reported as*, ID suggestion, age/cohort controls. | no |

No phase rewrites an existing record. The conformance program is separate and
sequenced after all three.

## 4. Design

### 4.1 Case-level facts → a documented `hnf1bCuration` block

Cohort, family history and detection method are properties of the case, not of an
allele: 59 records have no interpretation at all, and a negative family history is not
evidence about a particular variant.

```json
{
  "id": "phenopacket-940",
  "subject": { … },
  "interpretations": [ … ],
  "hnf1bCuration": {
    "cohort": "fetus",
    "familyHistory": "positive",
    "detectionMethod": "mlpa",
    "curatedBy": "Bernt Popp",
    "curatedAt": "2026-07-30T14:02:11Z"
  }
}
```

A namespaced top-level object, not `metaData`. `metaData` is provenance; these are
clinical facts. The corpus already carries non-standard keys there (`comment`,
`reviewer`, `updates` — 864 records each), so the precedent for extending the document
exists, but this block is explicitly labelled as HNF1B-DB curation data rather than
disguised as GA4GH content.

This is the same *class* of thing as bug B3, and the distinction is deliberate: B3 is
an **undeclared** key written by accident and stripped by nothing. `hnf1bCuration` is
declared in the schema, documented, versioned with the record, and removed by
conformant export (§4.6). The registry in §4.7 is what makes the difference
enforceable.

**Absence means "not yet curated"; `not_reported` means "curator read the source and it
is silent."** The two are distinct and both are needed. `cohort` has no `not_reported`
member because the spreadsheet always states it (939/939); an uncurated record simply
omits the key.

Per-field curation status is **not** modelled. `curatedBy`/`curatedAt` are block-level.
A QC surface that needs to know which individual fields were reviewed is a conformance-
program concern, and forcing it here would over-build Phase 3.

### 4.2 Variant-level facts → `variationDescriptor.extensions`

`segregation` asserts how *this allele* was transmitted, so it joins the four names
already present (`coordinates` 440, `external_reference` 440, `copy_number` 13,
`zygosity` 13):

```json
"variationDescriptor": {
  "extensions": [
    { "name": "coordinates", "value": { … } },
    { "name": "segregation", "value": { "origin": "de_novo" } }
  ]
}
```

**This uses an object-valued `Extension.value`, which GA4GH v2 does not permit.**
Verified: `org.ga4gh.vrsatile.v1.Extension.value` is protobuf type 9 (string), and
`ParseDict` rejects a dict. Every existing extension in the corpus has the same defect.

Adding a sixth object-valued extension is a deliberate choice: a lone string-valued
extension among five object-valued ones would make the eventual migration harder, not
easier, and would give the console a second serialization rule to implement for no
present benefit. The debt is recorded in the ADR and migrated in one pass later.

`classification_criteria` stays where it is, on the nonexistent
`variantInterpretation.extensions` slot. Moving it would create a dual-location window
for 864 records with no compensating benefit in this program.

### 4.3 Age and cohort are independent

| Situation | `subject.timeAtLastEncounter` |
|---|---|
| age known | `{ "iso8601duration": "P2Y" }` — corpus convention |
| gestational age known (15 source rows, `22wks`–`35wks`) | `{ "gestationalAge": { "weeks": 24 } }` |
| age not reported | key omitted |

Born/fetus lives in `hnf1bCuration.cohort` and is never inferred from age. Rev 1
derived it from `timeAtLastEncounter` with `ELSE 'born'`, which would have mislabelled
the 196 records that have no `timeAtLastEncounter`, every malformed TimeElement, and
every future record from outside the spreadsheet. The spreadsheet curates `Cohort`
independently — 159 born individuals have no stated age — so it is independent data.

`gestationalAge` is new to this corpus (0 records use it). Because it is written by
Phase 3, Phase 3 also owns its **readers**: `SubjectCard.vue`, `PagePhenopacket.vue`
and `frontend/src/schemas/phenopacketSchema.js:20` must all handle it, or a fetus saves
and then displays as N/A. Rev 2 specified the write and forgot the read.

### 4.4 Laterality

| Source value | Encoding |
|---|---|
| `bilateral` | `[HP:0012832 Bilateral]` |
| `unilateral left` | `[HP:0012833 Unilateral, HP:0012835 Left]` |
| `unilateral right` | `[HP:0012833 Unilateral, HP:0012834 Right]` |
| `unilateral unspecified` | `[HP:0012833 Unilateral]` |
| `no` | `excluded: true`, no modifiers |
| `not reported` | feature absent |

`hpo_terms_lookup.allowed_modifiers text[]` — an explicit set per term, because a
three-valued policy enum could not express the asymmetry it was invented for:

| Term | Allowed |
|---|---|
| HP:0000107, HP:0000003, HP:0000089, HP:0033132, HP:0000079 | `{HP:0012832, HP:0012833, HP:0012835, HP:0012834}` |
| HP:0000122 Unilateral renal agenesis | `{HP:0012835, HP:0012834}` — the term already asserts unilaterality |
| all others | `{}` |

Rules: `Bilateral` may not co-occur with `Unilateral`/`Left`/`Right`; a modifier outside
a term's set is rejected.

### 4.5 Validation, and what it can actually reach

Because `allowed_modifiers` is a database lookup and `hnf1bCuration` enums are
reference tables, none of this is expressible in the synchronous `Draft7Validator`. A
new **async domain validator** (`app/phenopackets/validation/domain.py`) checks:

- `hnf1bCuration` field values against their reference tables
- `segregation.origin` against `segregation_values`
- `phenotypicFeatures[].modifiers[]` against `allowed_modifiers`

| Writer | Path | Routed through the domain validator? |
|---|---|---|
| REST create/update | `services/phenopacket_service.py:143` | **yes** |
| Bulk import | `migration/database/storage.py:131` | no — documented trusted caller |
| VEP enrichment | `scripts/enrich_phenopackets_with_vep.py:167` | no — cannot write these fields |
| HPO label normalisation | `scripts/normalize_hpo_labels.py:112` | no — cannot write these fields |

The two maintenance scripts cannot produce the fields this validator governs, so
routing them is unnecessary; each gains a test asserting that. Bulk import can, and is
documented as a trusted caller with its own fixture test. **The claim is "rejected on
the REST write path", not "rejected everywhere"** — rev 2 promised the latter and could
not deliver it.

Errors are **400**, matching `crud.py:448`, raised as typed domain errors mapped
explicitly rather than surfacing as `IntegrityError`/500:

| Condition | Response |
|---|---|
| enum value outside its reference table | 400 naming field and allowed values |
| `Bilateral` with `Unilateral`/`Left`/`Right` | 400 naming both modifiers |
| modifier outside a term's `allowed_modifiers` | 400 naming term and allowed set |
| unknown key inside `hnf1bCuration` | 400 naming the key |

### 4.6 Vocabulary endpoints and export

```
GET /api/v2/ontology/vocabularies/cohort
GET /api/v2/ontology/vocabularies/detection-method
GET /api/v2/ontology/vocabularies/segregation
GET /api/v2/ontology/vocabularies/family-history
GET /api/v2/ontology/laterality-policy
```

Reference tables `cohort_values`, `detection_method_values`, `segregation_values`,
`family_history_values`, following the existing `sex_values` pattern and this repo's
**`sort_order`** column name.

Existing vocabulary endpoints are *not* uniform — sex adds `description`;
interpretation-status adds `description` and `category`; allelic-state and evidence-code
key on `id` rather than `value`; all wrap in `{"data": […]}`. New endpoints therefore
declare **explicit response models** with one canonical item shape
`{value, label, description?}` inside the existing envelope, and
`usePhenopacketVocabularies.js` — which hardcodes five refs, five requests and five
return values (`:42-123`) — is extended deliberately.

| Table | Values (spreadsheet row counts) |
|---|---|
| `cohort_values` | `born` 872, `fetus` 67 |
| `detection_method_values` | `sanger` 313, `ngs` 198, `cma` 117, `mlpa` 95, `qpcr` 94, `fish` 35, `other` 25, `not_reported` 62 |
| `segregation_values` | `de_novo` 178, `inherited_maternal` 137, `inherited_paternal` 85, `inherited_unspecified` 48, `not_reported` 491 |
| `family_history_values` | `positive` 381, `negative` 168, `not_reported` 390 |

All four must be registered in `alembic/env.py::include_object`, or
`test_alembic_env_autogenerate.py` flags them as drop candidates. `hpo_terms_lookup`
gains `allowed_modifiers`; no new ORM-mapped table is introduced.

**Export** gains two documented modes on a server-side endpoint — the current frontend
download simply serializes whatever it fetched:

| Mode | Content |
|---|---|
| `conformant` (default) | `hnf1bCuration` removed; everything else unchanged |
| `full` | as stored, including `hnf1bCuration` |

`conformant` is not a claim of GA4GH validity — the corpus retains the debts in the ADR.
It means only that HNF1B-specific curation has been stripped.

### 4.7 Schema registration

`schema_validator.py` declares `hnf1bCuration` with `additionalProperties: false`
**inside the block**, so a typo there is caught immediately, while the phenopacket
top level stays permissive until the conformance program. `moleculeContext` gains the
full GA4GH enum including `unspecified_molecule_context` — the documented default,
omitted from rev 2's normative text — as part of the Phase 1 B1 fix.

### 4.8 MCP contract

Read-only, so no write risk; the read contract still moves:

- `tools/terms.py:35` — the vocabulary-name `Literal` gains the four new names.
- `/ontology/laterality-policy` needs an explicit allow or deny in
  `client/allowlist.py`, or `tests/test_contract.py:55`'s no-silent-gaps test fails.
- OpenAPI snapshot and `_generated_models.py` regenerated via `make contract`. CI
  excludes `_generated_models.py` from drift checking
  (`.github/workflows/ci.yml:240`), so regeneration is verified explicitly.
- `hnf1bCuration` must be added to MCP response shaping or explicitly excluded.
- **No change to classification shaping** — ACMG stays in `interpretationStatus`, so
  `individuals.py:160` is untouched.

## 5. Testing

- **Vocabularies:** each endpoint returns `{"data":[{value,label,…}]}` against a
  declared response model; all four tables registered in `include_object` and the
  autogenerate-drift test stays green.
- **Laterality:** HP:0000122 accepts `Left`, rejects `Unilateral` and `Bilateral`; an
  empty-set term rejects all four; `Bilateral`+`Left` rejected on the REST write path.
- **`hnf1bCuration`:** round-trips through create/update; absence and `not_reported`
  are distinguishable through the API; an unknown key returns 400; a record with zero
  interpretations still accepts case-level curation.
- **Revision inheritance:** editing `hnf1bCuration` produces a revision whose
  `content_jsonb` contains the change; the published head is unaffected until publish;
  a concurrent edit returns 409 via the existing `revision` lock. *(This is the test
  that proves the JSONB placement earned its keep.)*
- **Export:** `conformant` omits `hnf1bCuration` and is otherwise byte-identical to
  `full`.
- **Age:** both frontend readers render an age for a corpus-shaped record (§2.4
  regression), and for a `gestationalAge` record.
- **Phase 1 regressions:** each of B1, B2, B3, B7 has a test asserting the form's
  payload no longer contains the defect.
- **MCP:** `make contract` regenerates cleanly; the no-silent-gaps allowlist test
  passes with the new paths.

Tests use fixtures. Rev 2 promised "all 923 production records validate in CI"; no such
snapshot exists in the repository and a live-DB test would be nondeterministic.

## 6. Data flow

```
curator (Phase 3 console)
   │
   ├─ case facts ──────────► phenopacket.hnf1bCuration
   ├─ variant facts ───────► variationDescriptor.extensions[segregation]
   ├─ age / gestational age ► subject.timeAtLastEncounter
   └─ phenotypes + laterality ► phenotypicFeatures[].modifiers
                                    │
                    async domain validator (REST write path)
                                    │
                         phenopackets.phenopacket
                                    │
                    publish → phenopacket_revisions.content_jsonb
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
            public reads / search          export: conformant | full
```

## 7. Out of scope

Everything in `docs/adr/0003-ga4gh-conformance-debt.md`: ACMG placement,
extension value types, the `timeAtLastEncounter.age` wrapper, laterality backfill of
~400 legacy annotations, `variantInterpretation.extensions`, and the 90 records whose
detection method is stranded in `metaData.comment`.

Also out: `DupCheck` / `Problematic` (curation workflow state),
`comment_classification` (24 rows), duplicate-row merge rules (no backfill here),
GA4GH `Family`/`pedigree`, and ontology mapping of `detection_method` to OBI/NCIT.

**B4 is not claimed as fixed.** Requiring `evidence` on every phenotypicFeature is an
HNF1B profile rule, not GA4GH conformance — GA4GH keeps it optional and
`test_phenopacket_service.py:49` fixtures omit it. Phase 3 will populate evidence from
the anchoring publication for features the console creates, which is a behaviour, not
a constraint.

## 8. Open questions

1. Whether Phase 3's console should write `interpretationStatus` at all, or leave it
   untouched. Leaving it preserves the existing P/LP filter behaviour; writing it
   correctly would break that filter for new records. Recommendation: leave untouched,
   and let the conformance program fix filter and data together.
2. Whether `detectionMethod` is genuinely case-level or assay-level. It is case-level
   in the spreadsheet (one value per individual) and modelled that way here; if
   multi-assay curation is ever needed, it moves to the variant extension alongside
   `segregation`.

## 9. What changed in rev 3

| Rev 2 | Rev 3 | Why |
|---|---|---|
| relational `phenopacket_curation` table | `hnf1bCuration` block in the JSONB | inherits revisions, audit, draft/publish, optimistic locking; dissolves four review findings |
| ACMG moved to `acmgPathogenicityClassification` | left in place | moving it created a dual-location window for 864 records with no dual reads |
| `classification_criteria` moved to `variationDescriptor` | left in place | same |
| age migrated to the `age` wrapper, dual-shape readers | two frontend readers corrected to the corpus path | the flat shape is the convention; no migration needed |
| Phase 4 backfill, Phase 5 hardening | removed from this program | conformance debt tracked in an ADR with its own risk budget |
| `additionalProperties:false` at top level | inside `hnf1bCuration` only | top level still holds legacy shapes |
| segregation as a new string-valued extension | object-valued, consistent with the other five | a lone conformant extension complicates the eventual migration |
| "rejected everywhere" | "rejected on the REST write path" | the maintenance scripts cannot write these fields |
| curation concurrency unsolved | inherits `Phenopacket.revision` | consequence of the JSONB placement |
| `gestationalAge` write-only | readers and frontend schema in Phase 3 | rev 2 specified the write and forgot the read |
| per-field curation status | block-level `curatedBy`/`curatedAt` | per-field provenance is a conformance-program concern |
| `unspecified_molecule_context` only in the changelog | normative in §4.7 | rev 2 claimed the fix without making it |
