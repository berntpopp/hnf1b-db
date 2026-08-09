# Source Observation Curation Implementation Plan

> **For implementers:** use `superpowers:using-git-worktrees` before execution, then `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Every task follows `superpowers:test-driven-development`. Do not claim completion without `superpowers:verification-before-completion`.

**Goal:** Store one canonical Phenopacket per individual with all publication/report observations preserved, derive GA4GH fields deterministically, make import/revision/public/privacy behavior fail-closed, and deliver a lossless accessible curation workflow.

**Architecture:** `hnf1bCuration.observationsById` and append-only corrections/resolutions are the clinical curation truth inside each revisioned JSONB document. Backend projection creates the person-level GA4GH fields. Operational relational bindings enforce dataset/report identity and import-run integrity. Frontend edits report DTOs and never mutates canonical fields directly.

**Stack:** Python 3.10+, Pydantic 2, FastAPI, async SQLAlchemy/asyncpg, PostgreSQL JSONB/Alembic, GA4GH Phenopackets v2, Vue 3 Composition API, Vuetify 4, Pinia/composables, Vitest, Playwright.

## Execution rules

- Use a sibling worktree, never a worktree inside the repository.
- Prefer root/backend/frontend `make` targets for verification.
- No task may fetch a mutable live sheet in a deterministic unit/integration test.
- No password or raw credential column enters any snapshot, fixture, JSONB, log, or export. Real reviewer emails and identifying free text may exist only in the authorized restricted snapshot; they never enter the committed de-identified fixture or public application representation.
- Backend service/model contracts land before frontend DTO assumptions.
- One agent owns each shared file at a time; especially `schema_validator.py`, `state_service.py`, `crud.py`, `PhenopacketCreateEdit.vue`, and OpenAPI snapshots.
- Clinical data changes are forward-only append operations. Do not implement an Alembic downgrade that restores known-false terms or deletes journals.

## Task 0: Contain the source-security and import risk

**External actions**

- Keep intentional anonymous/public sheet access enabled while removing credential-bearing columns from the public sheet schema.
- Rotate credentials associated with any populated password-like field.
- Disable production Google Sheets reimport until Task 9 passes its atomicity gate.
- Obtain an authorized immutable source snapshot and record its SHA-256 without committing restricted data.
- Audit the pinned source for nonblank, unique, version-stable `report_id`; require a data-steward-approved durable fallback key before Task 2 if it fails.
- Obtain legal/privacy approval for storing revisioned raw comments, source identifiers, and other linkable values; approval of source access alone is insufficient.

**Modify**

- `backend/migration/direct_sheets_to_phenopackets.py`
- `backend/migration/data_sources/google_sheets.py`
- `backend/tests/migration/test_source_security_preflight.py` (new)

**TDD steps**

1. Add failing tests that reject a reviewer/auxiliary sheet whose headers contain `password`, `passwd`, `secret`, or credential/token equivalents.
2. Add failing tests proving the importer does not create/update users from reviewer-sheet rows and does not log raw rows or emails.
3. Replace reviewer-sheet account creation with a single configured system import actor plus an approved stable internal/pseudonymous reviewer mapping. Missing mappings block import; raw email stays outside clinical JSONB.
4. Add structured redacted logging and verify captured logs contain no fixture email/token values.

**Gate**

```bash
cd backend && uv run pytest tests/migration/test_source_security_preflight.py -v
```

Do not mark this task complete until the external access/rotation owner confirms containment.

## Task 1: Add the exact ontology correction ledger and phenotype definition registry

**Create**

- `backend/app/ontology/data/ontology_corrections.csv`
- `backend/app/phenopackets/curation/definitions.py`
- `backend/tests/test_ontology_correction_ledger.py`
- `backend/tests/test_curation_phenotype_definitions.py`

**Modify**

- `backend/app/ontology/conformance.py`
- `backend/scripts/ontology_preflight.py`
- `backend/app/ontology/data/curation_vocabulary.csv`

**TDD steps**

1. Write a failing ledger schema test requiring defect key, location, wrong ID/label, intended ID/label, correction kind, ontology release/evidence, affected counts, and test/migration reference.
2. Encode the audited entries and let tests derive identifier-change and label-only counts. Delete hardcoded “14” assertions from code/docs touched by implementation.
3. Write a failing registry test for exactly 30 source questions and 36 finding definitions, stable `definitionId`, source column, allowed states, finding cardinality, and allowed laterality policy.
4. Encode CKD as one question with six possible definitions and biopsy as one question with two possible definitions. Do not synthesize N/A for unselected siblings.
5. Correct the live/source fixture hyperechogenicity mapping to `HP:0033132`; source preflight must still reject unapproved contradictions.
6. Add a no-label-laundering test: the importer retains raw source label and fails/corrects by ledger, never rewrites it merely to agree with an ID.
7. Ledger prenatal as `HP:0030674 Antenatal onset`, not congenital. Ledger bare postnatal as semantic unprojection/raw preservation, not relabelling the abstract HPO Onset root.

**Gate**

```bash
cd backend && uv run pytest \
  tests/test_ontology_correction_ledger.py \
  tests/test_curation_phenotype_definitions.py \
  tests/migration/test_no_label_laundering.py -v
```

## Task 2: Implement typed profile models and stable identities

**Create**

- `backend/app/phenopackets/curation/__init__.py`
- `backend/app/phenopackets/curation/models.py`
- `backend/app/phenopackets/curation/identifiers.py`
- `backend/tests/curation/test_profile_models.py`
- `backend/tests/curation/test_stable_identifiers.py`

**Modify**

- `backend/app/phenopackets/validation/schema_validator.py`

**Required types**

- `ObservedValue[T]`
- `SourceManifestRef`
- `PublicationObservation`
- `SubjectObservation`
- `TemporalObservation`
- `VariantObservation`
- `ClassificationObservation`
- `PhenotypeAssessment`
- `SourceReviewProvenance`
- `ReportObservation`
- `CurationCorrection`
- `ProjectionResolution`
- `ProjectionMetadata`
- `Hnf1bCurationProfile`

All profile models use `extra="forbid"`. Unknown legacy root keys are preserved by adapters, not accepted inside the new profile.

**TDD steps**

1. Test separate axes: scalar `sourceStatus`; phenotype `curationStatus=UNCURATED|CURATED`; and clinical `assessmentStatus=PRESENT|EXCLUDED|NOT_REPORTED|NOT_APPLICABLE|INDETERMINATE|NOT_ASSESSED|null`. Enforce `UNCURATED -> null` and `CURATED -> non-null`.
2. Test immutable raw values plus an append-only correction carrying exact preimage/postimage, JSON Pointer, source manifest hash, reason, actor, timestamp, and supersession.
3. Test UUIDv5 observation identity from `(source_system, dataset_id, canonical report_id)` and assessment identity from the stable observation/question key. Row number/content changes must not change identity; rows use keyed HMAC fingerprints, not plain hashes of pseudonymous content.
4. Test `observationsById` key equals the contained observation ID and cannot contain duplicates.
5. Test `report_id` is not a subject alternate ID and `sourceSubjectId` matches the profile subject binding.
6. Extend JSON Schema with explicit definitions and forbidden extra fields; test Pydantic/JSON-schema serialization agreement.

**Gate**

```bash
cd backend && uv run pytest tests/curation/test_profile_models.py tests/curation/test_stable_identifiers.py -v
```

## Task 3: Build the pure deterministic projection engine

**Create**

- `backend/app/phenopackets/curation/projection.py`
- `backend/app/phenopackets/curation/conflicts.py`
- `backend/app/phenopackets/curation/hashing.py`
- `backend/tests/curation/test_projection.py`
- `backend/tests/curation/test_projection_properties.py`
- `backend/tests/curation/test_projection_ga4gh.py`

**TDD steps**

1. Write table tests for subject identity, sex disagreement, comparable/incomparable ages, phenotype state matrices, modifier matrices, disease union, exact variant identity, classifications, references, and evidence polarity.
2. Test `present` vs `excluded`, bilateral vs unilateral, and left vs right as blocking conflicts. Remove/avoid present-wins and first-row rules.
3. Test NR/NA/unknown/uncurated remain in the ledger and do not create false GA4GH features.
4. Test compound laterality maps to the exact HPO modifier arrays.
5. Test evidence remains attached to its assertion polarity/report and is never reassigned to a winning feature.
6. Test distinct normalized variants remain distinct and every `subjectOrBiosampleId == subject.id`.
7. Use Hypothesis or deterministic permutations to prove any report ordering produces the same input hash, projection, conflict set, and output hash after volatile metadata is excluded.
8. Reject a stale resolution whose candidate-set digest changed.
9. Parse the projected document with the official/pinned Phenopackets parser. Do not call a local hand-written schema “conformant.”
10. Test prenatal -> Antenatal onset, bare postnatal unprojected, and AgeReported never copied to feature onset.
11. Test disease is projected only from an explicit/adjudicated diagnosis; an HNF1B variant alone never synthesizes RCAD/congenital disease.
12. Test ACMG class at `variantInterpretation.acmgPathogenicityClassification` independently from contribution at `genomicInterpretation.interpretationStatus`; reject invented transcripts, overlap-only CNV identity, illegal `ExternalReference`/evidence fields, and object-valued extensions.

**Gate**

```bash
cd backend && uv run pytest tests/curation/test_projection*.py -v
```

## Task 4: Make revisions append-only and write preconditions mandatory

**Create**

- Alembic revision adding `parent_revision_id`, `event_type`, `profile_schema_version`, `projection_version`, `ledger_hash`, `projection_hash`, and same-record composite constraints. Task 6 adds the `import_run_id` FK after the import-run table exists.
- `backend/tests/test_revision_immutability.py`
- `backend/tests/test_revision_record_constraints.py`

**Modify**

- `backend/app/phenopackets/models.py`
- `backend/app/phenopackets/services/state_service.py`
- `backend/app/phenopackets/repositories/phenopacket_repository.py`
- `backend/app/phenopackets/routers/crud.py`
- existing revision/state tests

**TDD steps**

1. Prove current draft save/publish mutates an old row with a failing regression test.
2. Add a DB trigger or permissions guard rejecting update/delete of immutable revision content after insert.
3. Remove internal commits from state/repository mutation methods; they flush, and the caller-owned unit of work commits. Change draft save, review transitions, and publish to append revision `N+1`.
4. Make `phenopackets.head_published_revision_id` the sole head authority; remove/derive `is_head_published`. Publish appends a published revision and swaps the pointer without modifying an older row.
5. Require request revision or `If-Match`. Missing precondition returns 428; stale returns 409. Remove the router fallback to the just-read current revision.
6. Enforce head/edit revision belongs to the same record and one head per record.
7. Verify every audit event links record/revision/actor/reason and before/after hashes.

**Gate**

```bash
cd backend && uv run pytest \
  tests/test_revision_immutability.py \
  tests/test_revision_record_constraints.py \
  tests/test_curation_revision_semantics.py \
  tests/test_editing_revision_relationship.py -v
```

## Task 5: Make the published head and privacy serializer authoritative

**Create**

- `backend/app/phenopackets/services/representation_service.py`
- `backend/app/phenopackets/privacy.py`
- `backend/tests/test_published_head_consistency.py`
- `backend/tests/test_public_phenopacket_redaction.py`

**Modify**

- `backend/app/phenopackets/repositories/visibility.py`
- `backend/app/phenopackets/routers/crud.py`
- list/search/aggregation query sources that use mutable working fields
- `backend/app/phenopackets/services/phenopacket_service.py`
- `frontend/src/views/PagePhenopacket.vue`
- `frontend/src/components/phenopacket/MetadataCard.vue`

**TDD steps**

1. Construct a divergent working copy/head fixture and prove anonymous detail, list filters, counts, search, aggregates, export, and MCP-facing API all return/derive from the same head.
2. Remove the mutable-working-copy visibility fast path or prove its digest equality transactionally before use.
3. Centralize `ga4gh`, `profile`, and public/redacted representations. Public allowlist is recursive and default-deny.
4. Add key and value oracles for email patterns, reviewer/source identity, raw report fields, `hnf1bCuration`, comments, and migration metadata.
5. Make frontend download/copy call the server representation endpoint; delete direct serialization of the loaded object.
6. Add official GA4GH parser validation to `representation=ga4gh`; retain old mode names only as deprecated aliases.

**Gate**

```bash
cd backend && uv run pytest tests/test_published_head_consistency.py tests/test_public_phenopacket_redaction.py tests/test_phenopacket_export.py -v
```

## Task 6: Add dataset/import/binding tables

**Create**

- Alembic revision for `source_datasets`, `source_snapshots`, `source_import_runs`, `phenopacket_subject_bindings`, `source_report_bindings`, `source_correction_registry`, `phenopackets.provenance_status`, and the Task 4 `import_run_id` FK
- `backend/app/phenopackets/curation/import_models.py`
- `backend/app/phenopackets/curation/import_repository.py`
- `backend/tests/curation/test_import_schema.py`

**Modify**

- `backend/alembic/env.py`
- `backend/tests/test_alembic_env_autogenerate.py`

**TDD steps**

1. Test immutable snapshot uniqueness, retryable failed runs, one successful `(snapshot, transformer, projection)` application, source-subject uniqueness per dataset, report uniqueness, and record-observation uniqueness.
2. Test a report cannot move to a different record through a normal import.
3. Test the correction registry rejects reuse of one correction ID with different canonical content.
4. Test import-run error/summary JSON is sanitized and rejects raw clinical/credential payloads.
5. Test migrations on empty and production-shaped databases, including rollback before activation only.
6. Register all new tables in Alembic metadata so autogenerate never proposes dropping them.
7. Test `provenance_status=legacy_unbound` for the 59 unbound records and require explicit reconciliation of soft-deleted/apparent duplicate records before database-wide cardinality claims.

## Task 7: Replace the Sheets loader with a fail-closed source manifest adapter

**Create**

- `backend/migration/source_manifest.py`
- `backend/migration/data_sources/source_adapter.py`
- `backend/migration/data_sources/google_sheets_adapter.py`
- `backend/migration/data_sources/local_fixture_adapter.py`
- `backend/tests/migration/test_source_manifest.py`
- `backend/tests/migration/test_google_sheets_adapter.py`

**Modify**

- `backend/migration/data_sources/google_sheets.py`
- `backend/migration/direct_sheets_to_phenopackets.py`
- `backend/app/core/config.py`

**TDD steps**

1. Honor configured spreadsheet ID and GIDs; remove hardcoded authority from orchestration.
2. Require Individuals, Phenotypes, modifiers, and publications. Reject HTTP error, timeout, HTML, wrong content type, missing sheet, wrong/missing/duplicate/unknown header, and configured-GID failure.
3. Read raw bytes, calculate SHA-256, and validate exact row/header expectations before parsing.
4. Load the modifiers sheet and version its mappings; do not silently fall back to hardcoded terms.
5. Support an immutable local fixture for tests/dry runs. No network in normal test targets.
6. Return a manifest plus data; never return `None` or partial sheet dictionaries.

**Gate**

```bash
cd backend && uv run pytest tests/migration/test_source_manifest.py tests/migration/test_google_sheets_adapter.py -v
```

## Task 8: Extract all 60 columns into 939 typed observations

**Create**

- `backend/migration/phenopackets/observation_extractor.py`
- `backend/migration/phenopackets/source_column_map.py`
- `backend/migration/phenopackets/strict_age_parser.py`
- `backend/tests/migration/test_observation_extractor.py`
- `backend/tests/migration/test_source_column_conservation.py`
- `backend/tests/migration/test_strict_age_parser.py`

**Modify**

- `backend/migration/phenopackets/extractors.py`
- `backend/migration/phenopackets/age_parser.py`
- `backend/migration/phenopackets/hpo_mapper.py`
- `backend/migration/phenopackets/laterality.py`
- `backend/migration/phenopackets/publication_mapper.py`
- `backend/migration/vrs/cnv_parser.py`

**TDD steps**

1. Encode one explicit mapping entry for each of the 60 exact source headers; fail on an unowned header.
2. Preserve raw plus normalized values for IDs, publication/type, case fields, both ages, all variant/INFO/Varsome fields, five classification fields, detection, segregation, family history, all 30 phenotypes, comment, reviewer reference, and review date.
3. Map source reviewer email transiently to an approved internal reference; never put the email in the observation.
4. Parse `28w`, `35wks`, and all accepted week tokens as gestational age. Map prenatal to Antenatal onset. Reject ambiguous bare numbers and unknown units; never fall back to years or map postnatal to a fabricated specific term.
5. Create exactly 30 assessments/report. Verify current audited counts: 20,171 NR; 4,620 excluded/no; 1,639 plain yes; 19 NA; 1 uncurated; 1,720 categorical positive.
6. Preserve all 408 compound unilateral assertions at the observation layer with full modifier pairs.
7. Preserve raw hg19/hg38 INFO, Varsome, VariantReported, ID, and publication metadata exactly in the authorized restricted-snapshot test. In the committed de-identified fixture, assert schema plus equality/conflict-shape preservation rather than equality to restricted values.
8. Keep normalized VRS/GA4GH data alongside raw values and attach parser/mapping/ontology versions and warnings.

**Gate**

```bash
cd backend && uv run pytest \
  tests/migration/test_observation_extractor.py \
  tests/migration/test_source_column_conservation.py \
  tests/migration/test_strict_age_parser.py -v
```

## Task 9: Implement atomic, idempotent import/reimport through services

**Create**

- `backend/migration/import_service.py`
- `backend/migration/reimport_merge.py`
- `backend/tests/migration/test_atomic_observation_import.py`
- `backend/tests/migration/test_observation_reimport.py`

**Modify**

- `backend/migration/direct_sheets_to_phenopackets.py`
- `backend/migration/database/storage.py`
- `backend/Makefile`
- root `Makefile`

**TDD steps**

1. Replace per-individual and per-storage catch-and-continue with error collection during staging and a hard abort before apply.
2. Stage all observations/projections and require exact disposition/count invariants before writes.
3. Apply under a dataset advisory lock and sorted row locks in one transaction through repository/state services. Do not raw-upsert `revision=1` or force `published`.
4. For initial recovery, refresh dependent materialized views non-concurrently inside the transaction during a maintenance window. Do not use a post-commit warning-only refresh; consider staged generations later for zero downtime.
5. Inject failures at parse, profile, revision, audit, binding, search/MV, and final verification stages; assert zero clinical changes and no user side effects.
6. Record failed run status only after rollback in a short sanitized transaction.
7. Identical manifest/profile hashes are no-op and create no clinical revision.
8. New source changes create a system-authored draft and leave public head unchanged. Active draft or overlapping correction/resolution pointer blocks the run.
9. Use three-way comparison of prior imported ledger/current working/new source. Permit only provably disjoint merges.
10. Re-read and validate working content, the existing head pointer/revision, bindings, counts, digests, search, and MVs inside the transaction before its only commit; any mismatch rolls back.
11. Make the CLI exit nonzero unless built/stored/verified counts all match.

**Gate**

```bash
cd backend && uv run pytest tests/migration/test_atomic_observation_import.py tests/migration/test_observation_reimport.py -v
```

## Task 10: Add curator API, projection preview, and structured validation

**Create**

- `backend/app/phenopackets/routers/curation.py`
- `backend/app/phenopackets/services/curation_service.py`
- `backend/app/phenopackets/curation/api_models.py`
- `backend/tests/test_curation_observation_api.py`
- `backend/tests/test_curation_projection_api.py`

**Modify**

- `backend/app/phenopackets/routers/__init__.py`
- `backend/app/phenopackets/validation/domain.py`
- `backend/app/phenopackets/validation/sanitizer.py`
- OpenAPI-related tests/snapshots

**TDD steps**

1. Implement curator-only GET curation DTO, PATCH one report, POST preview, and append resolution/correction endpoints.
2. Require revision/ETag and change reason; enforce server actor/timestamp.
3. Return structured errors with code, path array, observation/report ID, assessment ID, conflict key, and severity.
4. Allow draft save with parser warnings/unresolved conflicts; block publish and GA4GH export on blocking issues.
5. Recompute projection server-side on every write and reject/replace inconsistent client canonical fields through the documented service path.
6. Validate publication type, classification system/date, all nested profile shapes, ontology labels, laterality axes, and cross-field rules.
7. Preserve unknown legacy GA4GH keys during observation-only patches.

**Gate**

```bash
cd backend && uv run pytest tests/test_curation_observation_api.py tests/test_curation_projection_api.py -v
```

## Task 11: Update MCP and generated contracts deliberately

**Modify**

- `mcp/contract/openapi.snapshot.json`
- `mcp/src/hnf1b_mcp/contract/_generated_enums.py`
- `mcp/src/hnf1b_mcp/contract/_generated_models.py`
- `mcp/src/hnf1b_mcp/contract/_generated_paths.py`
- `mcp/src/hnf1b_mcp/client/allowlist.py`
- `mcp/src/hnf1b_mcp/services/individuals.py`
- `mcp/src/hnf1b_mcp/tools/individuals.py`
- `mcp/tests/test_individuals.py`

**TDD steps**

1. Decide allow/deny for every new curator endpoint; default deny.
2. Keep carrier/search/statistics counts person-level, never report-level.
3. Label compact/full individual output as canonical projection. If report summaries are exposed, include only approved counts/publication references/conflict counts and no raw observation/reviewer data.
4. Add privacy oracle tests to MCP output.
5. Regenerate rather than hand-edit generated models; verify snapshot drift.

**Gate**

```bash
cd mcp
make contract
# Review the generated diff, then stage the expected generated artifacts.
make contract-verify
make check
```

Also run an independent idempotence check by hashing generated artifacts, regenerating a second time, and comparing hashes. `contract-verify` uses Git cleanliness and therefore runs only after expected outputs are staged.

## Task 12: Build lossless frontend DTO adapters and curation state

**Create**

- `frontend/src/api/curation.js`
- `frontend/src/composables/usePhenopacketCuration.js`
- `frontend/src/composables/usePhenotypeDefinitions.js`
- `frontend/src/composables/useProjectionPreview.js`
- `frontend/src/utils/curationAdapters.js`
- `frontend/src/utils/phenotypeAssessments.js`
- `frontend/src/utils/variantObservations.js`
- `frontend/src/utils/publicationReferences.js`
- `frontend/src/schemas/curationSchema.js`
- corresponding unit specs

**Modify**

- `frontend/src/utils/apiError.js`

**TDD steps**

1. Test API -> form -> API deep equality for all report fields, raw/normalized variant values, complete publication references, 30 assessments, corrections, and unknown legacy root keys.
2. Test per-observation dirty baselines, route/report switching, preview debounce with stale-response cancellation, and save status.
3. Test the workflow/clinical two-axis model and all explicit assessment states plus untouched/uncurated behavior.
4. Test laterality two-axis model and exact modifier arrays.
5. Test path-indexed server errors resolve to report/section/control.
6. Test 409 retains the local draft and builds a compare/rebase model instead of reloading over it.

**Gate**

```bash
cd frontend && npx vitest run \
  tests/unit/utils/curationAdapters.spec.js \
  tests/unit/utils/phenotypeAssessments.spec.js \
  tests/unit/utils/variantObservations.spec.js \
  tests/unit/utils/publicationReferences.spec.js
```

## Task 13: Refactor the curation page into a report master-detail workspace

**Create**

- `frontend/src/components/curation/reports/ReportObservationList.vue`
- `frontend/src/components/curation/reports/ReportObservationEditor.vue`
- `frontend/src/components/curation/reports/PublicationEvidenceSection.vue`
- `frontend/src/components/curation/reports/VariantObservationEditor.vue`
- `frontend/src/components/curation/reports/SourceProvenanceSection.vue`
- component unit specs

**Modify**

- `frontend/src/views/PhenopacketCreateEdit.vue`
- `frontend/src/components/curation/CompletenessRail.vue`

**TDD steps**

1. Reduce the view to route/DTO orchestration, selected report, guards, save, preview, and publish actions.
2. Render report ID, genuine publication identity/type, completeness, conflict count, and dirty/save state in the navigator.
3. Keep source raw values visible and immutable; corrections require rationale.
4. Separate report-level source reviewer/date/comment from authenticated application audit history.
5. Make completeness count the active report's 30 source questions, total report completeness, validation errors, and unresolved conflicts.
6. Separate “Save report draft” from “Publish canonical projection.”
7. Add an accessible unsaved-navigation dialog; do not use `window.confirm`.

## Task 14: Implement the phenotype matrix, compound laterality, conflicts, and preview

**Create**

- `frontend/src/components/curation/reports/PhenotypeAssessmentMatrix.vue`
- `frontend/src/components/curation/reports/LateralityEditor.vue`
- `frontend/src/components/curation/reports/ConflictResolutionPanel.vue`
- `frontend/src/components/curation/reports/CanonicalProjectionPreview.vue`
- component unit specs

**Retire from observation-backed editing**

- direct write behavior in `frontend/src/components/PhenotypicFeaturesSection.vue`
- direct canonical write behavior in `frontend/src/components/VariantAnnotationForm.vue`

**TDD steps**

1. Render 30 source questions, 36 possible definitions, CKD single-select, biopsy multi-finding, filtering, and separate workflow/clinical status controls.
2. Implement composite laterality and load/save full arrays; include all four source forms.
3. Add scoped “mark remaining not reported” with confirmation and undo. Never bulk-mark N/A.
4. Show conflict candidates side-by-side with report/publication/date/raw/normalized/evidence and require resolution rationale.
5. Show canonical diff and the exact redacted public export preview before publish.
6. On validation failure focus an error summary then link/focus the exact control.

## Task 15: Fix public display/export and accessibility

**Modify**

- `frontend/src/views/PagePhenopacket.vue`
- `frontend/src/components/phenopacket/PhenotypicFeaturesCard.vue`
- `frontend/src/components/phenopacket/MetadataCard.vue`
- `frontend/tests/e2e/curation-console.spec.js` (remove lossy expectations or archive/split)

**Create**

- `frontend/tests/e2e/curation-report-observations.spec.js`
- `frontend/tests/e2e/curation-projection-export.spec.js`
- `frontend/tests/e2e/curation-accessibility.spec.js`

**TDD steps**

1. Display canonical assertions with their actual supporting report/publication, never pair arrays by index.
2. Download/copy only server representations.
3. Use labelled fieldsets/radio groups; state uses text/icon plus color; visible focus and logical DOM order.
4. Provide 44x44 targets, reduced motion, and `aria-live` save/error/report/conflict announcements.
5. Verify keyboard-only completion and conflict resolution, axe in light/dark at desktop/mobile, screen-reader names/states, and 390px no-overflow stacked layout.
6. Remove E2E substitutions for fake PMIDs, transformed Varsome, invented ISCN, ignored INFO, absent NR, lost reviewer, and first-modifier-only laterality.

**Gate**

```bash
cd frontend && npx playwright test \
  tests/e2e/curation-report-observations.spec.js \
  tests/e2e/curation-projection-export.spec.js \
  tests/e2e/curation-accessibility.spec.js
```

## Task 16: Backfill source observations and apply forward clinical corrections

**Create**

- a de-identified pinned 60-column fixture or approved deterministic equivalent
- `backend/scripts/stage_source_observations.py`
- `backend/scripts/verify_source_observation_backfill.py`
- `backend/tests/migration/test_source_observation_backfill.py`
- operational runbook under `docs/` only after the process is stable

**Read-only legacy evidence**

- laterality/ontology correction path currently implemented in `18cfc57307f6_restore_laterality.py`, `d4e8b1f60a27_fix_renal_echogenicity_hpo_term.py`, and `efa98cccfa51_correct_ontology_terms.py`

Create a new forward migration/backfill service. Do not edit already-applied Alembic revisions unless it is first proven they ran nowhere.

**TDD and execution steps**

1. Stage exactly 939 observations, 939 report bindings, and 864 source-subject bindings without changing public heads.
2. Preserve 59 DB-only records as `legacy_unbound`; produce an adjudication list without inferring identities.
3. Produce exact accounting for all ontology ledger entries, 408 source compound assertions, 377 unambiguous canonical restorations, 594 modifier objects if still applicable to the projection, and 18 conflict keys.
4. Require explicit disposition for every row/assessment/correction; no unmatched or disagreement allowance.
5. Compare current and candidate projections; classify every difference as bug fix, expected model improvement, unresolved conflict, or unexpected regression.
6. Append drafts/revisions and correction entries. Never mutate old revisions or delete journals.
7. Validate draft content, existing head-pointer/revision integrity, bindings, revisions, search/MVs, and public representations before a controlled publish. Do not require the unpublished draft to equal the public head.
8. Rehearse head-pointer rollback and backup/PITR recovery.

## Task 17: Final integration verification

**Corpus oracles**

- [ ] 939 source rows -> 939 active observations -> 864 source-bound individual records.
- [ ] 73 source-bound packets have multiple reports; all report/publication identities remain distinct.
- [ ] 28,170 phenotype assessments and exact audited state counts.
- [ ] 30 source questions / 36 definition registry.
- [ ] Restricted authorized snapshot: exact raw-value equality. Committed de-identified fixture: schema and equality/conflict-shape preservation.
- [ ] Permutation invariance, idempotence, failure atomicity, revision monotonicity, active-draft protection.
- [ ] 59 legacy-unbound records preserved.
- [ ] Public-head consistency and privacy oracles on API/frontend/MCP.
- [ ] Prenatal/age/disease/variant/evidence GA4GH semantics pass the official parser and clinical regression suite.

**Run**

```bash
cd backend && make check
cd ../frontend && make check && make build
cd ../mcp && make check
make contract
# Review/stage expected generated artifacts before this Git-diff-based check.
make contract-verify
```

Run the three Playwright files from Task 15 against a production-shaped test database populated only from the de-identified fixture.

Inspect GitHub Actions and Dependabot alerts after pushing. Do not call the program complete while any relevant test, lint, type, build, contract, Docker, or security gate is red. Document a deliberate blocker rather than weakening an oracle.
