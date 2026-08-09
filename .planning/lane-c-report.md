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

- Replace the legacy direct Sheets orchestration and reviewer-account import.
- Implement transactional staging/apply/reimport using the state-service
  primitive and add failure/idempotence integration tests.
- Add the de-identified pinned fixture and backfill scripts only after the
  shared import/state contracts are ready.
