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

- [ ] **Step 1: Write the failing test** — assert the schema accepts a block carrying
  `publicationType, classificationSystem, classificationDate, classificationComment,
  caseComment, problematic, duplicateCheck`; that a typo inside the block is still rejected
  (`additionalProperties: false` must keep working); that a record with no block is still
  valid; and that all 923 legacy shapes still validate.
- [ ] **Step 2: Add the seven typed fields** to the `hnf1bCuration` declaration. Typed, not a
  free-form `notes` object — a bag would defeat `additionalProperties: false`, which is the
  property Task 8 of the previous plan bought.
- [ ] **Step 3: Add two vocabulary tables** `publication_type_values`
  (case_report, case_series, research, review, thesis, preprint) and
  `classification_system_values` (acmg, clingen_hnf1b). Follow the `cohort_values` pattern.
  Register in BOTH registries. `down_revision` from `uv run alembic heads` immediately before
  writing.
- [ ] **Step 4: Verify additive-only** — content hash unchanged; `alembic downgrade -1 && upgrade head` round-trips.

## Task 2: Expose the two new vocabularies

**Files:** `backend/app/ontology/routers.py`; `backend/app/ontology/schemas.py`;
tests `backend/tests/test_curation_console_vocabularies.py` (create)

- [ ] Reuse `VocabularyResponse` and `_fetch_curation_vocabulary` exactly; item shape stays
  `{value,label,description}` wrapped in `{"data":[...]}`.
- [ ] Refresh the OpenAPI snapshot in the same commit.
- [ ] Extend `usePhenopacketVocabularies.js` with the two new refs, following the file's
  existing idiom.

## Task 3: The console shell — sections + completeness rail

**Files:** `frontend/src/views/PhenopacketCreateEdit.vue`;
`frontend/src/components/curation/CurationSection.vue` (create);
`frontend/src/components/curation/CompletenessRail.vue` (create);
tests `frontend/tests/unit/components/CompletenessRail.spec.js` (create)

- [ ] **Step 1: Failing test** — the rail reports `filled/total` per section; a field set to
  `not_reported` counts as **filled**; an absent field counts as **not filled**; the two are
  never conflated. This is the spec's central semantic.
- [ ] **Step 2: Build** collapsible sections with per-section counts and a sticky rail. Section
  state persists across a reload (localStorage) so a curator returning to a case resumes where
  they were.
- [ ] **Step 3: Unsaved-changes guard** on route leave — the current form has none.
- [ ] **Step 4:** keyboard-complete; each section reachable by skip-link; `prefers-reduced-motion` respected.

## Task 4: Case section

- [ ] Cohort, Sex, Individual identifiers (chips → `subject.alternateIds`), Publication type,
  Family history. Selects bind to the vocabulary composable, never to hardcoded arrays.

## Task 5: Variant section

- [ ] `VariantReported` → `variationDescriptor.description`, **verbatim, never normalised** —
  add a test asserting the stored value equals the typed value byte-for-byte.
- [ ] Variant type → `structuralType` as an SO term; hg38/hg19 → `expressions[hgvs.g]`;
  Varsome → `expressions[hgvs.c]`; dbVar `ID` → `xrefs[]`; detection method; segregation →
  `extensions[segregation].origin`; allelic state.
- [ ] Reuse `inferExpressionSyntax`/`inferMoleculeContext` from the existing form; do not
  duplicate them.

## Task 6: Classification section

- [ ] ACMG verdict → `interpretationStatus` (**unchanged placement**, ADR 0003 D1);
  criteria → `extensions[classification_criteria]`; system, date, comment → the new typed
  fields.
- [ ] Add a test asserting the console does **not** write
  `acmgPathogenicityClassification` — writing it would break the P/LP filter that reads
  `interpretationStatus` (`sql_fragments/paths.py:22`).

## Task 7: Phenotypes section

- [ ] Keep the tri-state grid; add **per-feature laterality**, offered only for terms
  `/api/v2/ontology/laterality-policy` admits. `HP:0000122` must offer Unilateral/Left/Right
  and **not** Bilateral.
- [ ] Add `KidneyBiopsy` (`HP:0100611`). Keep CKD staging behaviour.
- [ ] Attach `evidence` from the anchoring publication (curation spec §7).

## Task 8: Age & provenance sections

- [ ] Onset and age-at-report pickers writing `diseases[].onset` and
  `subject.timeAtLastEncounter`, supporting congenital / ISO-8601 / gestational.
- [ ] `caseComment`, `problematic`, `duplicateCheck` textareas.
- [ ] `curatedBy`/`curatedAt` auto-stamped from session + server clock. **No reviewer input
  control exists.** Add a test asserting no `@` can reach the payload from any field.

## Task 9: Fix the readers Phase 3 owns

**This is the step rev 2 of the curation spec forgot.** A fetus saves and then displays N/A
unless all three readers handle `gestationalAge`.

- [ ] `frontend/src/components/phenopacket/SubjectCard.vue`,
  `frontend/src/views/PagePhenopacket.vue`, `frontend/src/schemas/phenopacketSchema.js` must
  read `gestationalAge` alongside both age shapes. Extend `frontend/src/utils/age.js`.
- [ ] **Render excluded phenotypic features.** Logged during Phase 2 monkey testing: a record
  with 5 features / 2 excluded renders "Phenotypic Features (3)" and the word "excluded"
  appears nowhere. `excluded: true` is a stronger clinical claim than silence and must be
  visible and counted.

## Task 10: End-to-end verification against real sheet rows

**Files:** `frontend/tests/e2e/curation-console.spec.js` (create)

- [ ] **Step 1: The acceptance test.** Pick **3 real rows** from the sheet spanning the shapes
  (an SNV case_report, a 17q12 deletion with CNV fields, a fetus with gestational age). Enter
  each through the console by hand. Diff the resulting phenopacket against that individual's
  migrated record. Every field both can express must match. Document any that cannot and why.
- [ ] **Step 2:** create → save → reload → edit → save round-trip preserves all ~28 dimensions.
- [ ] **Step 3:** adversarial pass — empty submit, whitespace-only, 10k-char `VariantReported`,
  20 publications added then removed, every phenotype cycled through all three states, save
  mid-annotation, navigate away with unsaved changes.
- [ ] **Step 4:** dark mode on every section; 1440px and 390px; **zero console errors**; no
  horizontal body scroll at 390.
- [ ] **Step 5:** re-run the curation plan's Done-criteria queries — no legacy record
  unsaveable; content hash unchanged; `cardinality(allowed_modifiers) > 0` still exactly 6.

## Done criteria

- All ~28 dimensions enterable and round-tripping.
- 3 hand-entered sheet rows match their migrated records field-for-field.
- A typo inside `hnf1bCuration` is still rejected at 400.
- No legacy record unsaveable; content hash unchanged.
- No email can enter a phenopacket by any path.
- Zero console errors; dark mode correct; 390px clean.
- Excluded phenotypic features render and are counted.
