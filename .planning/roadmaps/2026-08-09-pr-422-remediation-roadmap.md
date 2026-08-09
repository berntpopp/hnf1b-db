# PR #422 Remediation Roadmap

> **Execution skill:** use `superpowers:subagent-driven-development` in the current session or `superpowers:executing-plans` in a fresh session. Use `superpowers:test-driven-development` for every code task and `superpowers:verification-before-completion` at each gate.

**Goal:** Replace PR #422's lossy row-flattening contract with one source-faithful Phenopacket per individual, preserve every report observation, correct ontology/laterality accounting, make revision/public/privacy semantics real, and clear the dependency/security backlog without serializing independent work.

**Source of truth:** `.planning/specs/2026-08-09-source-faithful-individual-curation-design.md`

## Program lanes

| Lane | Scope                                                                 | Depends on               | Primary write set                                               |
| ---- | --------------------------------------------------------------------- | ------------------------ | --------------------------------------------------------------- |
| 0    | Operational containment and source freeze                             | none                     | external sheet access; incident record; no clinical code        |
| A    | Typed observation/correction models and deterministic projection      | approved spec            | new backend profile/projection modules; validation tests        |
| B    | Append-only revisions, public-head authority, recursive redaction     | none                     | repository/state/visibility/export/model/Alembic                |
| C    | Fail-closed source adapter and atomic import/reimport                 | A, core B primitives     | `backend/migration`, import bindings/run tables, importer tests |
| D    | Curation API and MCP/public contracts                                 | A, B                     | FastAPI routers/services/OpenAPI/MCP generated contract         |
| E    | Report-observation frontend and accessible conflict workflow          | D DTO frozen             | Vue components/composables/utils/tests                          |
| F    | Source backfill, ontology/laterality forward correction, adjudication | A-C and reviewed fixture | import fixture/ledger, forward migration/runbook                |
| G    | Dependency, action, and alert consolidation                           | none                     | manifests, locks, workflows                                     |
| H    | Integration, shadow comparison, rollout                               | A-G                      | verification only unless fixes are found                        |

Lane 0 owns only external containment. The importer/logging containment code in implementation-plan Task 0 belongs to Lane C's write set. Lanes A-F may not edit manifests, locks, or workflows; any package proposal goes through Lane G or waits until G merges.

## Dependency graph

```text
Lane 0 containment ───────────────────────────────────────────────┐
                                                                  v
Lane A models/projection ──┬──> Lane C importer ──┬──> Lane F backfill
                           │                      │
Lane B revision/public ────┴──> Lane D API ───────┴──> Lane E frontend
                                                        │
Lane G dependencies ─────────────────────────────────────┤
                                                        v
                                                Lane H integration
```

## Maximum-concurrency schedule

The controller plus three workers is the current four-slot maximum.

### Wave 0: immediate containment

- [ ] Owner: repository/incident lead. Keep intentional public sheet access enabled, remove credential-bearing columns from its public schema, and rotate any exposed credentials. Record confirmation without copying credential values.
- [ ] Owner: data steward. Freeze or export an authorized, immutable source snapshot; calculate SHA-256; correct/adjudicate the live `HP:0033133` row.
- [ ] Owner: data steward/privacy lead. Approve or prohibit revisioned storage/export of raw comments, source identifiers, and other linkable fields; approve a stable pseudonymous reviewer reference.
- [ ] Owner: data steward. Prove `report_id` is nonblank, unique, and version-stable or approve an exact durable fallback key.
- [ ] Owner: controller. Mark production reimport disabled until Lane C's atomicity gate passes.

These require external authority and are release blockers. Code work may proceed against a de-identified fixture while they are completed.

### Wave 1: three independent foundations

- [ ] Worker A: Lane A typed models, stable IDs, correction registry rules, projection property tests.
- [ ] Worker B: Lane B append-only revision primitives, mandatory write preconditions, real head reads, public serializer.
- [ ] Worker G: Lane G consolidated dependency/security branch.
- [ ] Controller: review each worker's tests and maintain the cross-lane contract.

No worker may modify another lane's write set. Shared schema/API decisions are made in the spec before coding.

### Wave 2a: persistence prerequisite

- [ ] Integrate and verify Lane B's append-only revision/head migration, flush-only mutation API, and public representation service.

### Wave 2b: extraction and API

- [ ] Worker C: source manifest/adapter, observation extraction, and import-run/report-binding tables, using Lane A models and completed Lane B primitives.
- [ ] Worker D: curator API/projection preview/export representation, using Lane A/B services.
- [ ] Controller: run backend integration tests and official GA4GH parser checks.

### Wave 2c: transactional import

- [ ] Worker C: atomic apply/reimport service only after Wave 2b's bindings and Wave 2a's revision primitives are integrated.
- [ ] Controller: inject failure at every transaction stage and verify zero partial clinical changes.

### Wave 3: UI and data recovery

- [ ] Worker E: API adapters/store/report navigator and basic editor.
- [ ] Worker E2: phenotype matrix/laterality/conflict/a11y components, only after shared DTO utilities land.
- [ ] Worker F: pinned fixture, correction ledger, dry-run/backfill/adjudication report.
- [ ] Controller: compare old and new projections and triage every difference.

Frontend workers must divide write sets: one owns view/composable/API adapter files; one owns leaf components and their unit tests. `PhenopacketCreateEdit.vue` is owned by only one worker at a time.

### Wave 4: integration and rollout

- [ ] Import shadow run produces 939 observations, 939 report bindings, and 864 source-subject bindings; retains 59 legacy-unbound records; and makes no public change.
- [ ] Curators review all blocking conflicts and ontology corrections.
- [ ] End-to-end importer -> DB -> API -> UI -> save/reload suite passes.
- [ ] Public-head, privacy, accessibility, dependency-alert, and full CI gates pass.
- [ ] Publish observation-backed revisions in a controlled batch, monitor, then remove legacy write paths in a later PR.

## Critical gates

### Gate A: model/projection

- stable UUIDv5 observation/assessment IDs;
- 30 source questions / 36 definitions;
- exact explicit state model;
- permutation-invariant and byte-stable projection;
- present/absent and laterality conflicts never silently resolve;
- official GA4GH parse succeeds.

### Gate B: persistence/public safety

- revisions are byte-immutable and append-only;
- `If-Match`/revision is mandatory;
- public surfaces all resolve the same head;
- recursive redaction tests cover detail/list/search/export/download/MCP;
- no raw email or credential keys/values are public.

### Gate C: importer

- all required sheets/headers/hash/counts validated before writes;
- zero per-row/per-record catch-and-continue behavior;
- single transaction for clinical changes;
- idempotent no-op reimport;
- active draft and overlapping curator edits block reimport;
- materialized views/search participate in the success gate.

### Gate D: API/export/MCP

- curator endpoints enforce typed DTOs, mandatory preconditions, append-only corrections, and structured paths;
- preview equals the server-generated projection and public GA4GH representation;
- GA4GH output passes the official parser;
- public and MCP representations pass recursive redaction and person-level count tests;
- generated OpenAPI/MCP contracts are reviewed and reproducible.

### Gate F: source recovery

- authorized pinned fixture, not mutable live URLs;
- 939 report bindings, 864 source-subject bindings, zero duplicate reports;
- 28,170 phenotype assessments with audited status counts;
- 408 compound unilateral assertions retained at the observation layer;
- 377 unambiguous canonical laterality restorations and 18 conflict keys reported separately;
- 59 DB-only records preserved as `legacy_unbound`.

### Gate E: user workflow

- no-op API/form round-trip is deep-equal except server audit/revision fields;
- raw and normalized variant/publication data coexist;
- compound laterality round-trips;
- source reviewer/date are distinct from authenticated application audit;
- 409 retains local work and provides compare/rebase;
- keyboard, axe, focus, mobile, and non-color state checks pass.

### Gate G: supply chain

- one coherent frontend dependency graph and lock;
- backend and MCP uv locks authoritative; backend requirements exports regenerated from `backend/uv.lock` and MCP verified directly from `mcp/uv.lock`;
- no incompatible Pydantic/core pin;
- GitHub Actions versions/comments aligned;
- all alerts in scope closed, or an owner-approved time-bounded exception records advisory ID, exposure, compensating control, and expiry;
- all PR checks green.

## Finding-to-task traceability

| Reviewed defect                                                 | Implementation tasks                  |
| --------------------------------------------------------------- | ------------------------------------- |
| 939 rows flattened into 864 lossy documents                     | clinical plan Tasks 2, 3, 7-10, 12-16 |
| NR/NA/unknown/uncurated conflation; 30 questions/36 definitions | Tasks 1-3, 8, 12, 14, 17              |
| 408 laterality assertions / 377 features / 18 conflicts         | Tasks 3, 8, 14, 16                    |
| gestational weeks, prenatal/postnatal, AgeReported-as-onset     | Tasks 1, 3, 8, 16                     |
| fabricated RCAD/congenital disease                              | Tasks 3, 8, 16                        |
| raw/normalized variant and GA4GH interpretation errors          | Tasks 2, 3, 8, 10, 13, 16             |
| publication/evidence polarity and metadata loss                 | Tasks 2, 3, 8, 10, 12-15              |
| reviewer/provenance conflation and public PII                   | Tasks 0, 2, 5, 8, 10-15               |
| partial imports and revision-reset reimports                    | Tasks 4, 6, 7, 9                      |
| mutable revisions and mutable-working-copy public reads         | Tasks 4, 5, 9, 17                     |
| “14 identifiers” contradiction and live source ontology failure | Tasks 1, 7, 8, 16                     |
| 59 DB-only records / report-person identity                     | Tasks 6, 9, 16, 17                    |
| eight alerts and conflicting Dependabot PRs                     | dependency plan Tasks 1-6             |

## Rollout and rollback

Roll out additively: schema -> dual read -> observation-backed drafts -> shadow projection -> reviewed publication -> legacy writer retirement. Never backfill directly into the current public head without review.

Rollback disables observation-backed writes and swaps records back to their previous published head. It does not mutate/delete revision history, correction entries, source manifests, or reintroduce known-false clinical terms. If persistence invariants fail, restore via tested backup/PITR rather than Alembic downgrade of clinical facts.

## Detailed plans

- Clinical/data/backend/API/frontend: `.planning/plans/2026-08-09-source-observation-implementation-plan.md`
- Dependencies/actions/security alerts: `.planning/plans/2026-08-09-dependency-security-consolidation-plan.md`
