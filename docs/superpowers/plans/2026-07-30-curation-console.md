# Curation Console (Phase 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the curation form from ~6 enterable dimensions to ~28, so every field a curator
reads out of a paper has a home — including the ones the sheet holds and the form has never
had: the variant as reported, detection method, segregation, ACMG criteria, family history,
and the free-text caveats.

**Architecture:** Storage first, then UI, then the readers. Phase 2's contract already exists;
Task 1 extends it with seven typed fields and two vocabularies, Task 2 exposes them, Tasks 3–8
build the console section by section, Task 9 fixes the readers Phase 3 owns, Task 10 verifies
against real sheet rows.

**Tech Stack:** Vue 3 + Vuetify 3, Vitest, Playwright; FastAPI, SQLAlchemy 2 async, Alembic,
PostgreSQL 15, pytest.

**Spec:** [`../specs/2026-07-30-curation-console-design.md`](../specs/2026-07-30-curation-console-design.md)
**ADR:** [`../../adr/0003-ga4gh-conformance-debt.md`](../../adr/0003-ga4gh-conformance-debt.md)

## Global Constraints

- **Additive only.** No task may rewrite `phenopackets.phenopacket` or
  `phenopacket_revisions.content_jsonb` for any existing record. Take a content hash before
  Task 1 and verify after Task 10.
- **Never rewrite a curator's entry to match a computed value.** `VariantReported` is stored
  verbatim. This is the defect the whole programme exists to end.
- **No email address may enter a phenopacket by any path.** `curatedBy` is stamped from the
  session's display name; there is no reviewer input control.
- **Do not pay ADR 0003's debt.** ACMG stays in `interpretationStatus`;
  `classification_criteria` stays on `variantInterpretation.extensions`; extension values stay
  objects; `timeAtLastEncounter` keeps its flat shape (readers accept both).
- **Absence ≠ `not_reported`.** Absent means "not yet curated"; `not_reported` means "the
  source is silent". The completeness rail renders that difference; no control may collapse it.
- Validation errors are **HTTP 400**, matching `crud.py:448`.
- Reference tables use `sort_order`, are raw-SQL managed, and must be registered in **both**
  `backend/alembic/env.py::include_object` **and**
  `backend/tests/test_alembic_env_autogenerate.py::_RAW_SQL_TABLES`.
- **Any route change refreshes the OpenAPI snapshot in the same commit**: route →
  `cd backend && uv run python scripts/dump_openapi.py` → commit. `make contract` in `mcp/`
  *reads* the snapshot, it does not regenerate it.
- **Migrations redeclare ID literals inline**; only application code imports them.
- Backend: `uv run ruff format` before every commit — CI runs `ruff format --check` separately
  from `make check`. Frontend: `npm run lint:check`, never `npm run lint`.
- Frontend dev server on port 3000 (CORS-allowed). Playwright uses its own :5173 — never run
  both.

## Verified facts — do not re-derive

```
source: HNF1B_DataCuration.xlsx Individuals, 939 rows x 60 cols
        sha256 0fcc5362148085ea0c55b682836c8f4ecef2b5be7f88a9038409f94d8a5061ec
corpus already stores, on variationDescriptor:
  allelicState, description, expressions, extensions, geneContext, id, label,
  molecularConsequences, moleculeContext, structuralType, vrsAllele
  extension names in use: coordinates, copy_number, external_reference, zygosity
subject: alternateIds, id, sex, timeAtLastEncounter
metaData: comment, created, createdBy, externalReferences, phenopacketSchemaVersion,
          resources, reviewer, updates
laterality policy: 6 terms; HP:0000122 = {Unilateral, Left, Right}, Bilateral absent
timeAtLastEncounter: 664 flat {iso8601duration}, 0 nested {age:{...}}
structuralType SO terms already stored: SO:0000159 deletion, SO:1000035 duplication
```

---

## Task 1: Extend the storage contract

**Files:** new Alembic revision; `backend/app/phenopackets/validation/schema_validator.py`;
`backend/alembic/env.py`; `backend/tests/test_alembic_env_autogenerate.py`;
tests `backend/tests/test_curation_console_schema.py` (create)

- [x] **Step 1: Write the failing test** — assert the schema accepts a block carrying
  `publicationType, classificationSystem, classificationDate, classificationComment,
  caseComment, problematic, duplicateCheck`; that a typo inside the block is still rejected
  (`additionalProperties: false` must keep working); that a record with no block is still
  valid; and that all 923 legacy shapes still validate.
- [x] **Step 2: Add the seven typed fields** to the `hnf1bCuration` declaration. Typed, not a
  free-form `notes` object — a bag would defeat `additionalProperties: false`, which is the
  property Task 8 of the previous plan bought.
- [x] **Step 3: Add two vocabulary tables** `publication_type_values`
  (case_report, case_series, research, review, thesis, preprint) and
  `classification_system_values` (acmg, clingen_hnf1b). Follow the `cohort_values` pattern.
  Register in BOTH registries. `down_revision` from `uv run alembic heads` immediately before
  writing.
- [x] **Step 4: Verify additive-only** — content hash unchanged; `alembic downgrade -1 && upgrade head` round-trips.

## Task 2: Expose the two new vocabularies

**Files:** `backend/app/ontology/routers.py`; `backend/app/ontology/schemas.py`;
tests `backend/tests/test_curation_console_vocabularies.py` (create)

- [x] Reuse `VocabularyResponse` and `_fetch_curation_vocabulary` exactly; item shape stays
  `{value,label,description}` wrapped in `{"data":[...]}`.
- [x] Refresh the OpenAPI snapshot in the same commit.
- [x] Extend `usePhenopacketVocabularies.js` with the two new refs, following the file's
  existing idiom.

## Task 3: The console shell — sections + completeness rail

**Files:** `frontend/src/views/PhenopacketCreateEdit.vue`;
`frontend/src/components/curation/CurationSection.vue` (create);
`frontend/src/components/curation/CompletenessRail.vue` (create);
tests `frontend/tests/unit/components/CompletenessRail.spec.js` (create)

- [x] **Step 1: Failing test** — the rail reports `filled/total` per section; a field set to
  `not_reported` counts as **filled**; an absent field counts as **not filled**; the two are
  never conflated. This is the spec's central semantic.
- [x] **Step 2: Build** collapsible sections with per-section counts and a sticky rail. Section
  state persists across a reload (localStorage) so a curator returning to a case resumes where
  they were.
- [x] **Step 3: Unsaved-changes guard** on route leave — the current form has none.
- [x] **Step 4:** keyboard-complete; each section reachable by skip-link; `prefers-reduced-motion` respected.

## Task 4: Case section

- [x] Cohort, Sex, Individual identifiers (chips → `subject.alternateIds`), Publication type,
  Family history. Selects bind to the vocabulary composable, never to hardcoded arrays.

## Task 5: Variant section

- [x] `VariantReported` → `variationDescriptor.description`, **verbatim, never normalised** —
  add a test asserting the stored value equals the typed value byte-for-byte.
- [x] Variant type → `structuralType` as an SO term; hg38/hg19 → `expressions[hgvs.g]`;
  Varsome → `expressions[hgvs.c]`; dbVar `ID` → `xrefs[]`; detection method; segregation →
  `extensions[segregation].origin`; allelic state.
- [x] Reuse `inferExpressionSyntax`/`inferMoleculeContext` from the existing form; do not
  duplicate them.

## Task 6: Classification section

- [x] ACMG verdict → `interpretationStatus` (**unchanged placement**, ADR 0003 D1);
  criteria → `extensions[classification_criteria]`; system, date, comment → the new typed
  fields.
- [x] Add a test asserting the console does **not** write
  `acmgPathogenicityClassification` — writing it would break the P/LP filter that reads
  `interpretationStatus` (`sql_fragments/paths.py:22`).

## Task 7: Phenotypes section

- [x] Keep the tri-state grid; add **per-feature laterality**, offered only for terms
  `/api/v2/ontology/laterality-policy` admits. `HP:0000122` must offer Unilateral/Left/Right
  and **not** Bilateral.
- [x] Add `KidneyBiopsy` (`HP:0100611`). Keep CKD staging behaviour.
- [x] Attach `evidence` from the anchoring publication (curation spec §7).

## Task 8: Age & provenance sections

- [x] Onset and age-at-report pickers writing `diseases[].onset` and
  `subject.timeAtLastEncounter`, supporting congenital / ISO-8601 / gestational.
- [x] `caseComment`, `problematic`, `duplicateCheck` textareas.
- [x] `curatedBy`/`curatedAt` auto-stamped from session + server clock. **No reviewer input
  control exists.** Add a test asserting no `@` can reach the payload from any field.

## Task 9: Fix the readers Phase 3 owns

**This is the step rev 2 of the curation spec forgot.** A fetus saves and then displays N/A
unless all three readers handle `gestationalAge`.

- [x] `frontend/src/components/phenopacket/SubjectCard.vue`,
  `frontend/src/views/PagePhenopacket.vue`, `frontend/src/schemas/phenopacketSchema.js` must
  read `gestationalAge` alongside both age shapes. Extend `frontend/src/utils/age.js`.
- [x] **Render excluded phenotypic features.** Logged during Phase 2 monkey testing: a record
  with 5 features / 2 excluded renders "Phenotypic Features (3)" and the word "excluded"
  appears nowhere. `excluded: true` is a stronger clinical claim than silence and must be
  visible and counted.

## Task 10: End-to-end verification against real sheet rows

**Files:** `frontend/tests/e2e/curation-console.spec.js` (create)

- [x] **Step 1: The acceptance test.** Pick **3 real rows** from the sheet spanning the shapes
  (an SNV case_report, a 17q12 deletion with CNV fields, a fetus with gestational age). Enter
  each through the console by hand. Diff the resulting phenopacket against that individual's
  migrated record. Every field both can express must match. Document any that cannot and why.
- [x] **Step 2:** create → save → reload → edit → save round-trip preserves all ~28 dimensions.
- [x] **Step 3:** adversarial pass — empty submit, whitespace-only, 10k-char `VariantReported`,
  20 publications added then removed, every phenotype cycled through all three states, save
  mid-annotation, navigate away with unsaved changes.
- [x] **Step 4:** dark mode on every section; 1440px and 390px; **zero console errors**; no
  horizontal body scroll at 390.
- [x] **Step 5:** re-run the curation plan's Done-criteria queries — no legacy record
  unsaveable; content hash unchanged; `cardinality(allowed_modifiers) > 0` still exactly 6.

## Done criteria

- All ~28 dimensions enterable and round-tripping.
- 3 hand-entered sheet rows match their migrated records field-for-field.
- A typo inside `hnf1bCuration` is still rejected at 400.
- No legacy record unsaveable; content hash unchanged.
- No email can enter a phenopacket by any path.
- Zero console errors; dark mode correct; 390px clean.
- Excluded phenotypic features render and are counted.

---

## Status: COMPLETE — landed in PR #422, CI green (2026-07-31)

All 10 tasks implemented. Task 10's spec was **authored but not executed** in the first pass;
running it on 2026-07-31 against a live stack found six product defects, all now fixed, and
all 13 e2e tests pass.

### Where reality differed from the spec's field map

The spec's §3.2 mapping was written from the sheet's column names rather than from the corpus,
and three entries were wrong. §3.2 has been corrected in place.

| Spec said | Corpus actually holds | Consequence of the spec's version |
|---|---|---|
| `VariantType` → `structuralType` (all four SO terms) | 404 deletion + 36 duplication on `structuralType`; 302 SNV + 122 indel on `molecularConsequences` (exact partition, 864 records) | The backend rejects `structuralType` without an ISCN/GA4GH-CNV expression, so **every SNV and indel was unsaveable** |
| `hg38`/`hg19` → `expressions[hgvs.g]`, assembly-tagged | dash notation lives on `syntax: 'vcf'`; **no `version` key on any of 864 records**; `hgvs.g` holds derived true HGVS | Backend rejected the sheet's own values, and reading back by `version` matched nothing — **opening any migrated variant showed hg38 blank** |
| (no entry) | all 440 structural records carry `expressions[iscn]` | Deletions and duplications — **51% of the corpus** — could not be saved at all |

### Other defects found by executing Task 10

- **`<v-form v-else-if="!error">` unmounted the whole form on any error.** Fill 28 fields, hit a
  validation error, lose the screen with no way to dismiss the alert. Only a fatal load failure
  may replace the form now; recoverable errors render once, beside the Save button.
- **Save errors read `[object Object]`** — `detail` is `{validation_errors: [...]}` and nothing
  in the frontend had ever rendered that shape. Added `frontend/src/utils/apiError.js`.
- **The variant sub-editor silently discarded uncommitted input** on submit. Now refused with an
  instruction.
- **The spec's own submit assertion could not fail**: `waitForURL(/\/phenopackets\/[^/]+$/)`
  also matches `/phenopackets/create`, so it resolved instantly on the page it was already
  sitting on. This is why the suite could look complete and be wrong — it is what hid all six
  defects above.

### Two documented deviations (D10, D11)

Neither loses information; `VariantReported` keeps the curator's wording verbatim in both cases.

- **D10** — the sheet's `Varsome` cell is a display string
  (`HNF1B(NM_000458.4):c.443C>T (p.Ser148Leu)`), not coding HGVS. The migration parsed it to
  `NM_000458.4:c.443C>T`, which is what the migrated record stores and what the control asks for.
- **D11** — no sheet column holds an ISCN karyotype, yet the backend requires one for a
  structural variant and it cannot be derived (the sheet's CNV coordinate has a start, no end).
  The curator supplies it.

### Done criteria — evidence

- 3 real sheet rows enter through the console and diff field-for-field against their migrated
  records (SNV case report, 17q12 deletion, fetus with gestational age). ✅
- Create → save → reload → edit → save round-trip preserves every dimension. ✅
- A typo inside `hnf1bCuration` is still rejected at 400. ✅
- No legacy record unsaveable; corpus hash `e5bc71d2…` unchanged across the whole run. ✅
- No email reaches a phenopacket by any path. ✅
- Zero console errors; dark mode correct; no horizontal scroll at 390px. ✅
