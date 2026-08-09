# Source-Faithful Individual Curation Design

**Date:** 2026-08-09

**Status:** Approved direction; implementation pending

**Supersedes for active implementation:** the source-cardinality and losslessness assumptions in `docs/superpowers/specs/2026-07-30-curation-data-model-design.md` and `docs/superpowers/specs/2026-07-30-curation-console-design.md`

**Companion review:** `.planning/reviews/2026-08-09-pr-422-cross-layer-review.md`

## 1. Decision

HNF1B-DB stores **one canonical Phenopacket per biological individual**. Every source publication/report row for that individual is stored as a **typed observation inside the same Phenopacket**.

The observation ledger is the source-faithful curation record. The GA4GH-facing fields are a deterministic projection of that ledger plus explicit curator resolutions. No importer, migration, API client, or UI component may silently resolve a scientific disagreement by input order.

This choice preserves the current individual-level meaning of counts, search, cohorts, survival analysis, and MCP retrieval while retaining all 939 current source observations for the 864 source individuals.

## 2. Design invariants

1. `phenopackets.phenopacket_id` identifies one individual-level record, not one paper row.
2. Each source row has exactly one stable `observationId`; an observation belongs to exactly one individual.
3. Imported scientific raw values are immutable evidence. A curator may add a corrected normalized value only with a reason; the imported raw value remains visible.
4. Workflow curation status and clinical assessment status are separate axes. `not_reported` and `not_applicable` are explicit clinical source values, never inferred from absence or uncurated work.
5. The backend is the sole projection authority. Frontend-derived canonical JSON is advisory only.
6. Projection is a pure, versioned, permutation-invariant function of observations and resolutions.
7. Conflicting stated values remain unresolved until a rule with clinical semantics or a curator resolution handles them.
8. Every projected assertion carries traceable observation/publication evidence when GA4GH permits it.
9. Working copy, revision rows, audit entries, and public head are updated through the existing state service; no importer bypasses revision semantics.
10. Imports and migrations are fail-closed and all-or-nothing. Partial corpus success is a failed run.
11. Public GA4GH exports contain the officially validated projection only. Curator-authorized profile exports may contain the local observation ledger, subject to PII policy.
12. Public source-sheet access remains intentional. No credentials or passwords enter source rows, JSONB, logs, fixtures, or exports; source reviewer email addresses remain outside application JSON and committed fixtures.

## 3. Storage architecture

### 3.1 Primary clinical storage

Extend the existing revisioned `hnf1bCuration` object. Do not create a second clinical source-of-truth table.

```json
{
  "id": "phenopacket-317",
  "subject": { "id": "317", "sex": "FEMALE" },
  "phenotypicFeatures": [],
  "interpretations": [],
  "diseases": [],
  "metaData": {},
  "hnf1bCuration": {
    "schemaVersion": "2.0",
    "definitionsVersion": "hnf1b-phenotypes/1",
    "observationsById": {},
    "correctionsById": {},
    "resolutionsById": {},
    "projection": {
      "algorithmVersion": "1.0",
      "observationsDigest": "sha256:...",
      "outputDigest": "sha256:..."
    }
  }
}
```

The current case-level keys in `hnf1bCuration` are transitional read compatibility. Migration moves source-derived values into observations. New writes use observation fields; any retained top-level case values are derived compatibility views, not independent truth. `observationsById` is an object rather than an array so duplicate observation IDs are structurally impossible in one document; curator DTOs may expose a sorted report array for convenient rendering.

### 3.2 Operational import storage

Add operational identity/import tables. They enforce cross-document uniqueness and provenance but never become a second clinical source of truth:

```text
source_datasets
  id UUID PK
  source_system TEXT NOT NULL
  dataset_key TEXT NOT NULL
  subject_namespace TEXT NOT NULL
  UNIQUE(source_system, dataset_key)

source_snapshots
  id UUID PK
  dataset_id UUID FK
  source_manifest JSONB NOT NULL
  manifest_sha256 TEXT NOT NULL
  expected_counts JSONB
  UNIQUE(dataset_id, manifest_sha256)

source_import_runs
  id UUID PK
  snapshot_id UUID FK
  transformer_version TEXT NOT NULL
  projection_version TEXT NOT NULL
  status staged|validated|applying|applied|failed
  observed_counts JSONB
  summary_jsonb JSONB
  error_report JSONB
  actor_id BIGINT FK
  started_at, completed_at

phenopacket_subject_bindings
  id UUID PK
  record_id UUID FK phenopackets
  dataset_id UUID FK
  source_subject_id TEXT NOT NULL
  UNIQUE(dataset_id, source_subject_id)

source_report_bindings
  id UUID PK
  dataset_id UUID FK
  report_id TEXT NOT NULL
  record_id UUID FK phenopackets
  observation_id UUID NOT NULL
  first_seen_run_id UUID FK
  last_seen_run_id UUID FK
  active BOOLEAN NOT NULL
  UNIQUE(dataset_id, report_id)
  UNIQUE(record_id, observation_id)

source_correction_registry
  correction_id UUID PK
  record_id UUID FK
  observation_id UUID NOT NULL
  canonical_sha256 TEXT NOT NULL
  created_revision_id BIGINT FK
```

`source_report_bindings` prevents a report from silently moving between people. Reassignment is a separate audited operation. Multiple dataset subject bindings may point to one adjudicated biological-individual record. The clinical content still lives only in the revisioned Phenopacket JSONB.

Failed attempts are retryable because uniqueness belongs to the immutable snapshot, not an import attempt. Prevent duplicate successful application with a partial unique index on `(snapshot_id, transformer_version, projection_version)` where `status='applied'`.

These tables must never store sheet rows, reviewer emails, passwords, or comments.

Add `phenopackets.provenance_status = source_bound|legacy_unbound|manual` as operational metadata. The 59 currently known DB records without a source row are explicitly `legacy_unbound`; soft-deleted and apparent duplicate records require an adjudicated keep/merge/quarantine disposition before any database-wide person count is asserted.

## 4. Observation contract

### 4.1 Common observed value

Every source-derived scalar uses a common semantic wrapper:

```json
{
  "raw": "28w",
  "sourceStatus": "stated",
  "value": { "kind": "gestationalAge", "weeks": 28, "days": 0 },
  "correctionIds": []
}
```

For non-clinical scalar source values, `sourceStatus` is one of:

- `stated`: the source states a value;
- `not_reported`: the source convention explicitly says the report is silent;
- `not_applicable`: the source explicitly says the field does not apply;
- `unknown`: the source explicitly says unknown.
- `blank`: the source cell is empty and no stronger meaning is inferred.

Missing means the field is outside this observation's applicable schema, not silently unknown. Workflow status is a separate `curationStatus`, never a clinical source state. Imported observations contain every required source field and retain the one known blank phenotype cell as blank/uncurated unless the source data dictionary establishes a different convention.

If a curator corrects a value, `raw` remains unchanged and `correctionIds` references append-only entries in top-level `correctionsById`. Each entry contains the exact preimage/postimage, reason, server actor/time, and supersession link. Projection uses the active correction chain; audit and UI show both.

### 4.2 Report observation

```json
{
  "observationId": "7ae87ce5-3b8f-5a22-927c-0d8f5a9c71c1",
  "origin": "imported",
  "source": {
    "provider": "google_sheets",
    "datasetId": "hnf1b-registry",
    "sheet": "Individuals",
    "rowNumber": 42,
    "rowHmacSha256": "hmac-sha256:...",
    "importRunId": "uuid",
    "importedAt": "2026-08-09T12:00:00Z"
  },
  "identifiers": {
    "individualId": "317",
    "reportId": "RPT-001",
    "individualIdentifier": {
      "raw": "Family A / II-2",
      "sourceStatus": "stated",
      "value": "Family A / II-2"
    }
  },
  "publication": {},
  "case": {},
  "ages": {},
  "variant": {},
  "classification": {},
  "phenotypes": [],
  "notes": {},
  "sourceReview": {}
}
```

`observationId` is UUIDv5 of `(source_system, dataset_id, canonical report_id)`. Content hash and row number are not identity. The source snapshot is SHA-256 hashed; each row uses a keyed HMAC rather than a plain low-entropy hash that could disclose pseudonymous row contents. If the source does not guarantee a stable unique report ID, add a deterministic source-row key and fail on collision. Random UUIDs are allowed only for manually created observations. Each assessment ID is UUIDv5 of `(observation_id, assessment kind, stable source field, stable allele/ordinal key)`.

Before implementation, audit the pinned snapshot and source governance for nonblank `report_id` uniqueness and stability across versions. A data steward must approve the exact durable fallback key if that audit fails; row number and content hash are forbidden identity fallbacks.

### 4.3 Complete source mapping

| Observation section | Source columns                                                                                                                | Rules                                                                                                                                                                             |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `identifiers`       | `individual_id`, `report_id`, `IndividualIdentifier`                                                                          | Preserve typed roles; project only `individual_id` to `subject.id`.                                                                                                               |
| `publication`       | `Publication`, `PublicationType`                                                                                              | Preserve internal source key, local publication type, resolved bibliographic metadata, and official PMID/DOI references as distinct fields; never reduce the object to PMID-only. |
| `case`              | `DupCheck`, `Problematic`, `Cohort`, `Sex`, `FamilyHistory`                                                                   | Values are observation-level; repeated-report conflicts are not flattened.                                                                                                        |
| `ages`              | `AgeOnset`, `AgeReported`                                                                                                     | Preserve raw string plus typed time element; week syntax is gestational age.                                                                                                      |
| `variant`           | `VariantType`, `VariantReported`, `ID`, `hg19_INFO`, `hg19`, `hg38_INFO`, `hg38`, `Varsome`, `DetecionMethod`, `Segregation`  | Preserve every raw value and separately store validated typed normalization.                                                                                                      |
| `classification`    | `verdict_classification`, `criteria_classification`, `comment_classification`, `system_classification`, `date_classification` | All five stay tied to the observed variant/publication. Date is ISO validated.                                                                                                    |
| `phenotypes`        | the 30 phenotype columns                                                                                                      | Exactly one assessment per configured column for an imported observation.                                                                                                         |
| `notes`             | `Comment`                                                                                                                     | Report-level note; do not collapse to a case-level latest comment.                                                                                                                |
| `sourceReview`      | `ReviewBy`, `ReviewDate`                                                                                                      | Map reviewer to an internal user ID/display label transiently; never persist source email. Preserve source review date separately from application audit time.                    |

The 30 phenotype columns are:

`RenalInsufficancy`, `Hyperechogenicity`, `RenalCysts`, `MulticysticDysplasticKidney`, `KidneyBiopsy`, `RenalHypoplasia`, `SolitaryKidney`, `UrinaryTractMalformation`, `GenitalTractAbnormality`, `AntenatalRenalAbnormalities`, `Hypomagnesemia`, `Hypokalemia`, `Hyperuricemia`, `Gout`, `MODY`, `PancreaticHypoplasia`, `ExocrinePancreaticInsufficiency`, `Hyperparathyroidism`, `NeurodevelopmentalDisorder`, `MentalDisease`, `Seizures`, `BrainAbnormality`, `PrematureBirth`, `CongenitalCardiacAnomalies`, `EyeAbnormality`, `ShortStature`, `MusculoskeletalFeatures`, `DysmorphicFeatures`, `ElevatedHepaticTransaminase`, and `AbnormalLiverPhysiology`.

### 4.4 Phenotype assessment

```json
{
  "assessmentId": "uuid",
  "column": "RenalCysts",
  "rawValue": "unilateral left",
  "curationStatus": "CURATED",
  "assessmentStatus": "PRESENT",
  "findings": [
    {
      "definitionId": "renal-cyst",
      "sourceTerm": { "id": null, "label": "Renal cyst" },
      "term": { "id": "HP:0000107", "label": "Renal cyst" },
      "mappingStatus": "EXACT",
      "laterality": {
        "distribution": "unilateral",
        "side": "left",
        "modifiers": [
          { "id": "HP:0012833", "label": "Unilateral" },
          { "id": "HP:0012835", "label": "Left" }
        ]
      }
    }
  ],
  "onset": null,
  "evidence": [{ "reference": { "id": "PMID:..." } }],
  "correctionIds": []
}
```

`curationStatus` is `UNCURATED|CURATED`. `assessmentStatus` is null for uncurated work, otherwise `PRESENT|EXCLUDED|NOT_REPORTED|NOT_APPLICABLE|INDETERMINATE|NOT_ASSESSED`. Every imported report contains exactly 30 source-question assessments. The one blank source cell and untouched manual work are `UNCURATED` with null assessment; they must never be synthesized from `not reported`.

Only `PRESENT` and `EXCLUDED` project to a GA4GH `PhenotypicFeature`. `EXCLUDED` means the finding was assessed/looked for and absent. It must not mean empty, unknown, not reported, not assessed, no biopsy, or not applicable. Unmapped findings remain in the ledger and do not project.

The 30 source questions map to 36 possible finding definitions. `RenalInsufficancy` selects one of six CKD definitions when present; unselected sibling stages are not marked `not_applicable`. `KidneyBiopsy` can map to two definitions and its `no` semantics must be clinically adjudicated and mapping-versioned before import. Stable `definitionId` values are separate from ontology IDs so a corrected ontology identifier does not create a new clinical question.

Laterality constraints:

| Source meaning           | Required modifiers         |
| ------------------------ | -------------------------- |
| bilateral                | `HP:0012832`               |
| unilateral, side unknown | `HP:0012833`               |
| unilateral left          | `HP:0012833`, `HP:0012835` |
| unilateral right         | `HP:0012833`, `HP:0012834` |

Excluded, not-reported, not-applicable, and unknown assessments carry no laterality. Modifier order is canonicalized for hashing but has no clinical meaning.

### 4.5 Age value

Age parsing is strict and unit-aware:

```json
{ "kind": "age", "iso8601Duration": "P12Y" }
{ "kind": "gestationalAge", "weeks": 28, "days": 0 }
{ "kind": "ontologyClass", "term": { "id": "HP:0003577", "label": "Congenital onset" } }
```

- `w`, `wk`, `wks`, `week`, and `weeks` mean gestational weeks when the context is prenatal/fetal or the cohort is fetus.
- Month/day/year suffixes must be explicit or covered by a documented exact grammar.
- A bare number is ambiguous and fails validation; it must not default to years.
- Prenatal/antenatal onset maps to `HP:0030674 Antenatal onset`, not congenital onset. Congenital means present at birth.
- `postnatal` must not be labelled as a specific HPO concept that HPO does not provide. Preserve it as raw/local categorical semantics until a defensible representation exists.
- A GA4GH numeric TimeElement is exactly `{ "age": { "iso8601duration": "P2Y" } }`; it never uses a bare duration at the TimeElement root or more than one oneof member.
- Project the minimum comparable explicit disease onset only for a source-supported disease assessment. Project maximum `AgeReported` to `timeAtLastEncounter` only after the source data dictionary confirms it is an encounter age. Age at report is never broadcast as phenotype onset.

## 5. Projection contract

Implement a pure backend service:

```python
project_individual(
    observations: list[SourceObservation],
    resolutions: list[ProjectionResolution],
    *,
    algorithm_version: str,
) -> ProjectionResult
```

`ProjectionResult` contains canonical GA4GH fields, warnings, blocking conflicts, the ordered observation digest, and trace links. Sorting by `observationId` before projection makes row order irrelevant.

The semantic input digest excludes import-run IDs, imported/projected timestamps, actors, and other volatile audit metadata; those remain in revision/import audit records. The output digest covers only canonical clinical content with stable ordering.

### 5.1 Rules

| Target                        | Projection rule                                                                                                                                                                                                                         |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `subject.id`                  | Must equal every observation's `individualId`; mismatch blocks save/import.                                                                                                                                                             |
| `subject.alternateIds`        | Typed identifiers may be displayed here for compatibility, but roles remain in observations.                                                                                                                                            |
| `subject.sex`                 | Ignore not-reported/unknown. One distinct stated value projects; multiple distinct values block until resolved.                                                                                                                         |
| `subject.timeAtLastEncounter` | Only if the data dictionary confirms `AgeReported` is encounter age: maximum comparable stated value; otherwise retain locally and do not project.                                                                                      |
| `diseases` / onset            | Only explicit source disease assessments or adjudicated diagnoses project. Never infer RCAD or congenital onset from an HNF1B variant alone.                                                                                            |
| `phenotypicFeatures`          | Group by HPO ID. All-present or all-excluded projects directly; present/excluded conflict blocks. Silent/N/A observations never become present.                                                                                         |
| phenotype modifiers           | Identical sets merge. With consistent polarity but conflicting laterality, the base feature may project without the disputed modifier while a blocking conflict remains. Never choose first or infer bilateral from left+right reports. |
| phenotype evidence            | Union supporting publication references of the same assertion polarity without reducing to the first PMID. Source review dates remain local provenance because GA4GH Evidence has no `recordedAt`.                                      |
| `interpretations`             | Group only by exact validated VRS/descriptor identity or curator-approved equivalence. CNV overlap alone is not identity. Distinct/report-specific classifications remain distinct.                                                     |
| variant raw strings           | Project normalized GA4GH representation while full mode retains every report's verbatim strings.                                                                                                                                        |
| classifications               | Stay attached to their observed variant/publication. A single canonical status requires agreement or explicit resolution.                                                                                                               |
| `metaData.externalReferences` | Union official references by normalized PMID/DOI using only GA4GH fields. Local source key/type and richer bibliographic metadata remain in observations.                                                                               |

For GA4GH projection, ACMG class belongs in `variantInterpretation.acmgPathogenicityClassification`; clinical contribution belongs in `genomicInterpretation.interpretationStatus`. `subjectOrBiosampleId` references the actual `subject.id` or a real biosample. `variationDescriptor.expressions[]` contains validated parsed expressions and `variation` is populated only by a validated VRS object. Do not invent transcripts, ISCN, dbVar identifiers, molecular consequences, or object-valued extension fields.

GA4GH `ExternalReference` contains only its official fields; publication type, review date, and reviewer provenance remain in the local observation. Evidence uses the exact supporting report/publication and a valid ECO term; do not treat `ECO:0000033` as a generic author-statement default or add illegal `recordedAt` fields.

### 5.2 Resolutions

Only resolution decisions are persisted in top-level `resolutionsById`; computed issues are regenerated in `projection`. Corrections and resolutions have stable IDs and are append-only. A new revision contains an unchanged superset of parent correction IDs; supersession creates a new entry rather than mutating history.

```json
{
  "conflictKey": "phenotype:HP:0000107:modifiers",
  "strategy": "select_observations",
  "selectedObservationIds": ["17e51976-b4a7-5ac7-a645-753ab1413649"],
  "resolvedValue": [
    { "id": "HP:0012833", "label": "Unilateral" },
    { "id": "HP:0012835", "label": "Left" }
  ],
  "reason": "Later imaging in PMID:... supersedes the initial report",
  "resolvedByUserId": 123,
  "resolvedAt": "2026-08-09T12:00:00Z"
}
```

A resolution is valid only while its candidate-set digest matches. A changed observation invalidates the resolution and reopens the issue.

### 5.3 Canonical write protection

When `hnf1bCuration.observationsById` exists:

- the server recomputes canonical fields before persistence;
- a client-supplied canonical projection with a different digest returns `409 projection_mismatch` or is replaced only through an explicitly documented projection endpoint;
- unresolved blocking conflicts prevent publication, but a curator may save a draft with visible unresolved issues;
- GA4GH export is allowed only from a published revision whose projection has no blocking issues and passes the official parser.

## 6. Import and reimport

### 6.1 Source adapter

Replace the live-sheet-only orchestration with an adapter accepting a pinned local CSV/XLSX fixture in tests and an explicitly configured remote source in operations. The spreadsheet ID environment override must be honored. Sheet names/GIDs and required headers are validated before any database write.

Fetch only `Individuals`, `Phenotypes`, `Phenotype_modifier`, and publication data needed for resolution. Reviewer identity must come from an approved stable internal/pseudonymous reference mapping, not from a public password-bearing sheet. An unmapped reviewer blocks import; raw email stays outside clinical JSONB.

Legal/privacy approval for storing revisioned raw comments, original identifiers, and other linkable source fields is a backfill blocker. A source snapshot being technically authorized for import does not by itself authorize persistence or profile export of every raw field.

### 6.2 Pipeline

1. Fetch and hash all inputs.
2. Validate exact/allowed headers, source row count, unique report keys, required fields, and forbidden credential columns.
3. Validate ontology rows against the pinned ontology snapshot and the correction ledger. Never rewrite a curator label to agree with a suspect ID.
4. Parse all 939 report rows into typed observations and collect all errors.
5. Group observations into 864 individuals, sort deterministically, and project.
6. Produce a dry-run manifest: counts, digests, conflicts, corrections, and proposed revision changes.
7. Abort on structural, identity, schema, domain, conservation, or deterministic-projection errors. Enumerated clinical conflicts may enter a draft but block publication/GA4GH export.
8. In one transaction, create/update records through a bulk state-service API using monotonically increasing revisions. Mutation methods flush; the caller-owned import unit of work is the only committer.
9. Write audit/import-run summaries, then re-read and validate bindings, working content, the existing head pointer/revision, observation counts, digests, search/MV state, and projection counts inside the transaction.
10. Commit once only after every verification succeeds. Record failed-run status in a separate sanitized transaction after rollback.

### 6.3 Reimport policy

- Identical `rowHmacSha256`: no-op.
- Changed imported row with no curator correction and no active draft: replace the observation, recompute projection, and create a new revision.
- Changed row with a curator correction, resolution dependency, or active draft: fail preflight with an actionable source conflict. Never overwrite.
- Deleted source row: mark the observation `sourceWithdrawn` in a reviewed revision; do not erase history automatically.
- A run that stores fewer records than it built is failed and rolled back.

## 7. Database and revision semantics

- Continue using `phenopackets.phenopacket` as the working copy and `phenopacket_revisions.content_jsonb` as immutable revision content.
- Import/migration code must call repository/state-service methods rather than raw `INSERT ... ON CONFLICT` with `revision=1`.
- New revisions use `current revision + 1`; the `(record_id, revision_number)` uniqueness contract is never reset.
- Active drafts and their owners are respected. A source update cannot silently publish over a draft.
- Publishing atomically swaps `head_published_revision_id`. A draft import intentionally allows working/head divergence; the head pointer and its referenced immutable revision must agree, and initial publication is a separate controlled action.
- Laterality/ontology remediation validates both working and head copies and fails on every unmatched fixture row or unexplained disagreement.
- Draft saves and publish transitions append new revision rows. They do not update `content_jsonb`, state, or reason on an existing revision row. Make `phenopackets.head_published_revision_id` the sole head authority and remove/derive stored `is_head_published`, so publishing does not demote an old revision row. Enforce byte immutability with service boundaries and a database trigger/permissions guard.
- Extend revisions with `parent_revision_id`, `event_type`, `import_run_id`, `profile_schema_version`, `projection_version`, `ledger_hash`, and `projection_hash`.
- Public detail, list filters, search indexes, aggregations, and exports resolve the actual head revision or a transactionally maintained projection of it. The current mutable-working-copy fast path is removed.
- For the initial recovery import, refresh dependent materialized views non-concurrently inside the apply transaction during a maintenance window. A future staged-generation/atomic-pointer design may restore zero-downtime refresh; post-commit warning-only refresh is not acceptable.

The observation map is small at current scale (maximum three imported observations per individual), so no second clinical relational store or premature JSONB index is required. Add an index only after an explain-plan-backed query requirement exists.

## 8. API

Add curator-only endpoints under the centralized FastAPI router/service boundary:

| Endpoint                                                  | Purpose                                                                                          |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `GET /api/v2/phenopackets/{id}/curation`                  | Return observations, persisted resolutions, computed projection/issues, and optimistic revision. |
| `POST /api/v2/phenopackets/{id}/curation/preview`         | Validate an unsaved observation draft and return the projected diff/conflicts. No write.         |
| `PATCH /api/v2/phenopackets/{id}/reports/{observationId}` | Save one observation through state service with mandatory revision/ETag and change reason.       |
| `POST /api/v2/phenopackets/{id}/curation/resolutions`     | Append a correction/resolution; never replace the registry wholesale.                            |

Use the existing create/edit endpoint for packets without the observation contract. Once a packet has observations, direct mutation of derived canonical fields is rejected or routed through projection. Missing write preconditions return 428; stale preconditions return 409.

Errors are structured and path-addressable:

```json
{
  "code": "projection_conflict",
  "errors": [
    {
      "path": "phenotypes.HP:0000107.modifiers",
      "conflictKey": "phenotype:HP:0000107:modifiers",
      "observationIds": ["...", "..."],
      "message": "Bilateral and unilateral-left observations require resolution"
    }
  ]
}
```

Replace ambiguous export terminology with `representation=ga4gh|profile`, retaining `conformant|full` as deprecated aliases. GA4GH export strips every local block and must pass the official Phenopackets parser before returning. Profile export remains curator-only and includes observations after the PII/credential sanitizer. MCP remains read-only and uses canonical individual-level fields; optional report counts/conflict summaries must not expose the private ledger or reviewer identity.

Anonymous detail, list/search, export, download/copy, and MCP share one recursive server-side redaction allowlist. Frontend download/copy always calls this serializer and never serializes its in-memory object directly.

## 9. Frontend interaction design

### 9.1 Page structure

```text
Individual 317                         Projection: 2 conflicts
|-- Observation navigator
|     |-- RPT-001 · PMID ... · 2008 · reviewed
|     `-- RPT-002 · PMID ... · 2015 · reviewed
|-- Selected observation editor
|     |-- Source & publication
|     |-- Case and ages
|     |-- Variant and classification
|     |-- Phenotype matrix (30 explicit statuses)
|     `-- Notes and source review
`-- Canonical projection panel
      |-- derived subject/variant/phenotype preview
      `-- conflict resolver with evidence side-by-side
```

The editor never flattens all observations into one case form. The navigator shows completeness and validation per observation. A curator can compare two observations without losing the selected report context.

### 9.2 Controls

- Phenotype workflow and clinical state are separate. Untouched shows Uncurated; once curated, the explicit options are Present, Excluded, Not reported, Not applicable, Indeterminate, or Not assessed.
- Laterality is a composite control: None, Bilateral, Unilateral-unspecified, Unilateral-left, Unilateral-right. It always loads/saves the full modifier set.
- Ages use separate duration, gestational age, and ontology-category modes and always show the imported raw string.
- Publication editor preserves internal source key and complete resolved reference metadata; DOI/PMID are not reconstructed from a numeric-only chip.
- Variant editor shows immutable “reported by source” values beside normalized GA4GH/VRS values. Normalization never overwrites the raw source, invents a transcript, or treats CNV overlap as identity.
- Classification, detection, segregation, family history, source note, and source review date are observation-level.
- Imported reviewer identity is a mapped internal/display value. No email or credential is rendered.
- Conflict resolver shows each candidate with publication, date, reviewer display label, raw source, and normalized value. A reason is required.

### 9.3 State management

Create one curation composable/store responsible for loading, local immutable updates, dirty tracking by `observationId`, preview debouncing, stale-preview cancellation, conflict state, mandatory optimistic revision, and save. Components emit value changes and never mutate shared props. All HTTP calls use centralized frontend API utilities.

On a `409 revision_mismatch`, retain the local draft, fetch the new server version, and present observation-level differences. Never discard a curator's work silently.

## 10. Validation layers

1. Pydantic models define the observation, observed-value, phenotype, variant, source, correction, and resolution contracts with forbidden extra fields.
2. JSON Schema validates the serialized `hnf1bCuration` block for legacy callers.
3. Domain validation checks vocabularies, ontology IDs/labels, laterality sets, publication/classification systems, dates, and cross-field rules.
4. Projection validation checks individual identity, candidate conflicts, evidence links, and resolution digests.
5. Persistence validation checks revision/head invariants and import conservation.
6. UI validation mirrors server errors for fast feedback but is never authoritative.

## 11. Testing and acceptance

### 11.1 Deterministic fixtures

Commit a de-identified 939-row source fixture or a cryptographically pinned, legally safe equivalent. It must contain every distinct source token and all 73 repeated-individual shapes. Credentials, reviewer emails, and free-text identifiers/comments must be replaced deterministically while preserving equality/conflict patterns. Exact raw-value equality is checked only in the authorized restricted-snapshot validation environment; the committed fixture proves schema, state counts, relationship/conflict shapes, and deterministic transformations.

### 11.2 Required properties

- Row conservation: 939 rows -> 939 observations -> 864 individual packets.
- Column conservation: each of the 60 headers maps to an asserted observation path or an explicit security redaction rule.
- Phenotype conservation: 28,170 assessments with exact status counts.
- Permutation invariance: shuffling all rows produces byte-equivalent ordered observations and canonical projections after volatile timestamps are removed.
- Idempotence: importing the same fixture twice produces no clinical revision.
- Atomicity: one injected parse/storage failure produces zero corpus changes.
- Round-trip: observation JSON -> API -> form -> save -> reload preserves raw values, typed values, modifiers, evidence, and resolutions.
- Revision safety: source reimport cannot overwrite an active draft; published head remains unchanged until explicit publish.
- Privacy: forbidden credential keys and email patterns fail import and never appear in JSON, logs, snapshots, or exports.
- Legacy conservation: the 59 currently known DB records without a source row remain `legacy_unbound`; they are not deleted, merged, or synthesized into the 864 source-backed identities.
- Public-head consistency: anonymous detail, filters, search, materialized views, exports, and MCP observe the same published revision.
- Revision immutability: each save/transition appends; older revision bytes never change.

### 11.3 Clinical regression cases

1. `28w` and `35wks` parse as gestational weeks, never years.
2. `unilateral left/right` preserve two HPO modifiers across import and UI round-trip.
3. `PrematureBirth=not applicable` does not create a present feature.
4. Present vs excluded reports create a blocking conflict rather than present-wins.
5. Bilateral vs unilateral reports create a blocking modifier conflict.
6. All 408 source compound-laterality assertions remain in observations; the canonical report separately states 377 restored features and 18 conflict keys.
7. Wrong ontology ID plus plausible label/description fails source preflight; it is not label-normalized into consistency.
8. Complete PMID/DOI/type metadata and per-phenotype evidence survive edit/save/reload.
9. Prenatal maps to Antenatal onset, bare postnatal remains local/unprojected, and `AgeReported` never becomes phenotype onset.
10. A gene/variant finding alone does not synthesize RCAD or congenital disease; disease projection requires explicit/adjudicated diagnostic evidence.
11. ACMG classification and clinical contribution round-trip independently in the official GA4GH fields.

## 12. Rollout

1. Stop-the-bleeding fixes: live source ontology correction, strict age/laterality/N/A parsing, importer atomic failure, reviewer-sheet security response.
2. Land observation models, projection service, validation, and API behind a feature flag.
3. Backfill observations from a pinned source fixture into drafts; compare projections with the current corpus and review every difference.
4. Migrate ontology/laterality data with explicit draft/head-pointer integrity checks; do not require an unpublished draft to equal the public head.
5. Enable observation editor for curators; keep the old editor read-only for observation-backed packets.
6. Run parallel shadow projection and analytics comparisons.
7. Publish reviewed observation-backed revisions, then remove transitional case-level write paths.

Rollback disables observation-backed writes and restores the previous published head pointers. Observation revisions remain immutable history; rollback never destructively deletes them.

Clinical corrections are forward-only. An Alembic downgrade may remove unused additive schema before activation; after clinical activation it must not reintroduce known-false terms or delete correction evidence. Operational recovery uses a head-pointer rollback or backup/PITR.

## 13. Explicit non-goals

- Splitting one person into multiple Phenopackets.
- Exposing the private observation ledger through public or MCP APIs.
- Making Google Sheets the runtime source of truth after import.
- Automatically resolving clinically contradictory reports.
- Claiming that every local curation field is GA4GH-conformant. Local data remains namespaced; GA4GH export strips it and validates the remainder officially.
- Storing or reconstructing source credentials or reviewer emails for lossless export.
