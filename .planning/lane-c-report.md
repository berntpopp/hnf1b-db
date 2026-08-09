# PR #422 Lane C Report

## Increment 1 — source boundary and operational schema

- Added a fail-closed manifest/source-adapter boundary. It requires all four
  configured sheets, validates content type and closed headers, hashes exact
  raw bytes, and rejects credential-like/reviewer-email headers before parsing.
- Added a complete 60-column map, strict source age parsing, and typed
  per-row observation extraction with 30 phenotype assessments and no reviewer
  email retained in the observation.
- Added additive operational dataset, snapshot, import-run, subject-binding,
  report-binding, and correction-registry models plus Alembic revision
  `c0f422b00004`. Existing records default to `legacy_unbound` provenance.
- Verification: `ruff check` passed and the targeted source/import suite ran
  26 tests successfully. All tests use injected bytes or in-memory rows; none
  contacts a live sheet.

## Remaining Lane C work

- Wire the staged atomic import callback to the shared state-service bulk
  primitive once its cross-lane contract is finalized; the old raw SQL apply
  path is disabled.
- Add database-backed failure/idempotence integration tests against that bulk
  state-service contract.
- Add the de-identified pinned fixture and backfill scripts only after the
  shared import/state contracts are ready.

## Increment 2 — containment and reimport preflight

- Removed embedded sheet authority and the reviewer-account creation path from
  the legacy orchestrator. Remote IDs now come only from explicit settings and
  the old raw storage writer fails closed.
- Added transaction-owned atomic apply orchestration and reimport policy:
  count mismatches abort before a write, injected application failures trigger
  rollback, equal row HMACs are no-ops, and active drafts/corrections/resolution
  dependencies block changed source rows.
- Verification: `ruff check` passed and the targeted suite ran 35 tests
  successfully. Pytest also emitted pre-existing temporary Docker-fixture
  cleanup warnings; no source import test used network access.
