# Curation Console (Phase 3) — Design

**Date:** 2026-07-30
**Status:** Proposed
**Depends on:** the Phase 2 storage contract (landed: four vocabularies, laterality policy,
`hnf1bCuration` block, async `DomainValidator`, export modes)
**Spec it is written against:** [`2026-07-30-curation-data-model-design.md`](2026-07-30-curation-data-model-design.md)
**ADR:** [`0003-ga4gh-conformance-debt.md`](../../adr/0003-ga4gh-conformance-debt.md) — its
nonconformances are deliberate and this spec does not pay them.

## 1. The problem, measured

The curation source (`HNF1B_DataCuration.xlsx`, `Individuals` sheet, sha256
`0fcc5362…5061ec`) holds **939 rows × 60 columns**. The create/edit form can enter **6**
curation dimensions. Everything else a curator reads out of a paper — the variant as the
authors reported it, how it was detected, whether it segregated, the ACMG criteria, the
free-text caveats — either has no control at all or is silently dropped.

Phase 2 built the storage contract. Nothing writes into it: no `.vue` file references
`cohort`, `detectionMethod`, `segregation`, `familyHistory`, and nothing writes
`hnf1bCuration`. This spec is the console that does.

**Target: ~28 enterable dimensions, from 6.**

## 2. Mode and shape

**Mode: Operate.** The visitor completes a task. The real usage scene is a curator with one
publication PDF open, entering what *that paper* reports and leaving the rest explicitly "not
reported". Scanability, keyboard flow and never losing your place outrank expression.

**Shape: one page, progressive sections, sticky completeness rail.**

```
┌─ Case 317 ─────────────────────────────┐  ┌─ Completeness ──────┐
│ ▾ Case                          6/6    │  │ ●●●●●●○○   22/28    │
│    Cohort [born ▾]  Sex [female ▾]     │  │  Case          ✓    │
│    Individual ID  [Berberich_Proband1] │  │  Variant       ✓    │
│ ▾ Variant                       4/7    │  │  Classification !   │
│    Reported  [17q12 deletion         ] │  │  Phenotypes    ✓    │
│    Type      [Deletion ▾]              │  │  Age           —    │
│    hg38      [chr17-36459258-T-<DEL> ] │  │  Provenance    ✓    │
│ ▸ Classification                0/5    │  └─────────────────────┘
│ ▸ Phenotypes                   18/22   │
│ ▸ Age & onset                   0/2    │   ✓ complete
│ ▸ Provenance & notes            3/4    │   ! has a validation error
└────────────────────────────────────────┘   — nothing entered yet
```

Rejected: a **wizard** (slow for an experienced curator re-entering a known paper, and the
source reports fields out of order); a **quick-entry form with a long-tail drawer** (the long
tail never gets filled, which is the present failure).

### 2.1 Why a completeness rail rather than validation-on-submit

The single most important semantic in this domain is the difference between **"not yet
curated"** (absent) and **"the source is silent"** (`not_reported`). Phase 2 encodes it —
`cohort_values` deliberately has no `not_reported` member because the sheet states cohort for
all 939 rows, so absence there means "not yet curated". A completeness rail makes that
distinction visible while curating instead of at submit time. It is the UI expression of a
constraint the data model already holds.

## 3. Field map — sheet column → storage → control

Every landing place below **already exists in the corpus** unless marked NEW. Phase 3 extends
conventions; it does not invent storage.

### 3.1 Case (section 1)

| Sheet column | Storage | Control |
|---|---|---|
| `Cohort` | `hnf1bCuration.cohort` | select ← `/vocabularies/cohort` |
| `Sex` | `subject.sex` | select (GA4GH enum) |
| `IndividualIdentifier` | `subject.alternateIds[]` | text, chips |
| `Publication` | `metaData.externalReferences[]` PMID | existing publication editor |
| `PublicationType` | `hnf1bCuration.publicationType` **NEW** | select: case_report / case_series / research / review / thesis / preprint |
| `FamilyHistory` | `hnf1bCuration.familyHistory` | select ← `/vocabularies/family-history` |

### 3.2 Variant (section 2)

| Sheet column | Storage | Control |
|---|---|---|
| `VariantReported` (337 distinct) | `variationDescriptor.description` | **text — free, verbatim, never normalised** |
| `VariantType` (deletion, duplication) | `variationDescriptor.structuralType` | select → SO term (`SO:0000159`, `SO:1000035`) |
| `VariantType` (SNV, indel) | `variationDescriptor.molecularConsequences[]` | same select (`SO:0001483`, `SO:1000032`) |
| — | `expressions[syntax=iscn]` | text, **required for a structural type** |
| `hg38` | `expressions[syntax=vcf]` (untagged) | text + validate |
| `hg19` | `expressions[syntax=vcf]`, `version=GRCh37` | text |
| `hg19_INFO` / `hg38_INFO` | `extensions[coordinates]` (exists, 440) | derived, read-only |
| `ID` (dbVar) | `variationDescriptor.xrefs[]` **NEW use** | text, chips |
| `Varsome` | `expressions[syntax=hgvs.c]` | text |

**`VariantType` has two landing places, and the corpus draws the line exactly.**
404 deletion + 36 duplication sit on `structuralType`; 302 SNV + 122 indel sit on
`molecularConsequences` — 440 + 424 = 864, no overlap. The split is load-bearing: the backend
rejects any descriptor carrying `structuralType` without an accompanying ISCN or GA4GH-CNV
expression (`variant_validator/validator.py:200`), which no SNV has. A single control writing
all four to `structuralType` made every SNV and indel unsaveable.

**`hg38`/`hg19` are VCF-style dash notation, not HGVS.** The sheet's cells look like
`chr17-37739541-G-A`, and that is what the corpus stores under `syntax: 'vcf'` — all 864
records, none with a `version` key. `hgvs.g` is a different, derived value
(`NC_000017.11:g.37739541G>A`, 424 records). Mapping the sheet column onto `hgvs.g` made the
backend's HGVS check reject it, and reading it back by `version` matched nothing on a
migrated record, so opening an existing variant showed hg38 blank. hg38 is therefore written
untagged (byte-identical to the migrated shape, and still what
`expressions.find(e => e.syntax === 'vcf')` resolves to); hg19, which has no corpus precedent,
carries `version: 'GRCh37'`.

**ISCN has no sheet column but is not optional.** All 440 structural records carry one and it
cannot be derived — the sheet's CNV coordinate gives a start but no end — so the curator
supplies the karyotype. The control appears only when the selected type is structural.
| `DetecionMethod` | `hnf1bCuration.detectionMethod` | select ← `/vocabularies/detection-method` |
| `Segregation` | `extensions[segregation].origin` | select ← `/vocabularies/segregation` |
| — | `allelicState` (GENO) | select |

`VariantReported` is deliberately free text and is **never** normalised, corrected, or
replaced by a computed notation. Rewriting a curator's verbatim record is the defect this
programme exists to end (`docs/ontology-defect-report-2026-07-30.md` §4).

### 3.3 Classification (section 3)

| Sheet column | Storage | Control |
|---|---|---|
| `verdict_classification` | `genomicInterpretations[].interpretationStatus` | select — **stays where ADR 0003 D1 put it** |
| `criteria_classification` (51 distinct) | `variantInterpretation.extensions[classification_criteria]` (exists, 864) | criteria picker + free text |
| `system_classification` | `hnf1bCuration.classificationSystem` **NEW** | select: ACMG / ClinGen-HNF1B |
| `date_classification` | `hnf1bCuration.classificationDate` **NEW** | date |
| `comment_classification` | `hnf1bCuration.classificationComment` **NEW** | textarea |

**The console does not "fix" D1.** Writing ACMG to the conformant
`acmgPathogenicityClassification` field would break the P/LP filter that reads
`interpretationStatus` (`sql_fragments/paths.py:22`). ADR 0003 defers that deliberately, and
the curation spec §8.1 already recorded the decision.

### 3.4 Phenotypes (section 4)

The existing tri-state grid (present / excluded / unknown), extended:

- **laterality** per feature, offered only for terms the policy admits, sourced live from
  `/api/v2/ontology/laterality-policy`. `HP:0000122` correctly offers Unilateral/Left/Right and
  **not** Bilateral.
- **`KidneyBiopsy`** becomes a real phenotype control (`HP:0100611` Multiple glomerular cysts).
- **CKD staging** keeps its existing single-select behaviour.
- **evidence** — per curation spec §7, features the console creates get `evidence` from the
  anchoring publication.

### 3.5 Age & onset (section 5)

| Sheet column | Storage | Control |
|---|---|---|
| `AgeOnset` (77 distinct) | `diseases[].onset` | onset picker: congenital / ISO-8601 age / gestational |
| `AgeReported` (149 distinct) | `subject.timeAtLastEncounter` | same picker |

**Both shapes must be read**, per `frontend/src/utils/age.js` — the corpus stores
`{iso8601duration}` flat in 664 records and **zero** use the conformant `{age:{…}}` wrapper.
Per curation spec §4.3, Phase 3 owns the **readers** too: `SubjectCard.vue`,
`PagePhenopacket.vue` and `phenopacketSchema.js` must all handle `gestationalAge`, or a fetus
saves and then displays as N/A. Rev 2 of that spec specified the write and forgot the read.

### 3.6 Provenance & notes (section 6)

| Sheet column | Storage | Control |
|---|---|---|
| `ReviewBy` | `metaData.reviewer` + `hnf1bCuration.curatedBy` | **auto-stamped, display name only** |
| `ReviewDate` | `hnf1bCuration.curatedAt` | auto-stamped, server clock |
| `Comment` (648 rows) | `hnf1bCuration.caseComment` **NEW** | textarea |
| `Problematic` | `hnf1bCuration.problematic` **NEW** | textarea |
| `DupCheck` | `hnf1bCuration.duplicateCheck` **NEW** | textarea |

**No email address may enter a phenopacket.** The sheet's `ReviewBy` holds institutional
emails; ADR 0003 cites them as a reason the raw source cannot be committed, and the corpus
deliberately stores display names. The console never offers a reviewer field — it stamps the
authenticated user's display name. This closes the PII vector by construction rather than by
regex.

## 4. Schema changes

Seven new **typed** fields inside `hnf1bCuration` (declared, not a free-form bag, so
`additionalProperties: false` keeps catching typos — the property Task 8 bought):

```
publicationType, classificationSystem, classificationDate, classificationComment,
caseComment, problematic, duplicateCheck
```

Rejected: one `notes` object with arbitrary keys — it would defeat `additionalProperties:
false` and silently accept a typo'd key, the exact defect class Task 8 closed. Also rejected:
appending to `metaData.comment`, already an unstructured dumping ground the ADR flags as debt.

Two new controlled vocabularies (same raw-SQL pattern, both registries, `sort_order`):
`publication_type_values`, `classification_system_values`.

## 5. Design floor

- **Dark mode is not a variant.** Every surface themed via tokens; zero hardcoded
  `bg-*-lighten-*`. The monkey-test sweep found none today and that must hold.
- **1440px and 390px both first-class.** No horizontal body scroll at 390.
- **Keyboard-complete.** A curator must be able to enter a whole case without a mouse; each
  section reachable by skip-link.
- **Zero console errors.** The current bar, and it stays.
- **Every destructive action reversible** — the record already has revisioning, optimistic
  locking and rollback; the UI must surface them rather than re-implement them.
- **Unsaved-changes guard** on navigate-away, which the current form lacks.

## 6. Explicitly out of scope

- ADR 0003's D1–D4. The console writes the corpus's existing conventions, including its
  nonconformances, so the eventual migration is one uniform pass.
- Bulk import / spreadsheet upload.
- The QC review queue.

## 7. Done criteria

1. All ~28 dimensions in §3 are enterable and round-trip through create → save → reload → edit.
2. A record entered through the console is byte-comparable to the same row's migrated record
   for every field both can express. **This is the acceptance test**: pick 3 real sheet rows,
   enter them by hand, and diff against the migrated records.
3. `additionalProperties: false` still rejects a typo inside the block.
4. No legacy record becomes unsaveable — re-run the curation plan's Done-criteria query.
5. Content hash of `phenopackets` unchanged by the console's existence (additive only).
6. Zero console errors; no horizontal scroll at 390px; dark mode correct on every section.
7. No email address can be written into a phenopacket by any path.
