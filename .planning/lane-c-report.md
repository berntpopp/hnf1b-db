# PR #422 Lane C review — `b34d50f`

## Verdict

**Request changes.** The increment establishes useful fail-closed scaffolding and
the legacy CLI no longer has a reachable database-write branch, but it does not
meet design §§3.2, 6, 7, 10–11 or Tasks 0, 6–9, and 16. In particular, the
closed manifest is incompatible with the repository's current source schemas,
the extractor can assign false phenotype concepts and rejects known laterality
rows, and the operational-payload boundary can persist secret/clinical strings.

There is currently no reachable partial **database** import: the legacy apply
branch raises and the new apply service is not wired. That safe containment is
not equivalent to an atomic import implementation. A partial legacy dry-run
artifact is still reachable.

## Severity-ranked findings

### High — the fail-closed manifest rejects the current source contracts

`backend/migration/source_manifest.py:87-92` requires
`Phenotypes=(category, phenotype_id, phenotype_name)` and
`Publications=(publication, pmid, doi)`. Current code and the pinned vocabulary
use `phenotype_category`, `phenotype_description`, `publication_id`,
`publication_alias`, `PMID`, and `DOI`
(`backend/migration/phenopackets/hpo_mapper.py:207-211`,
`backend/migration/phenopackets/publication_mapper.py:29-38, 62-80`, and
`backend/app/ontology/data/curation_vocabulary.csv:1`). A direct probe of those
current headers fails with missing `category` / missing lowercase publication
headers. The new tests only use the newly invented header triples and therefore
do not exercise the real adapter contract. Unless an authorized snapshot proves
a newly changed schema, every configured import is blocked before ontology or
publication validation.

This is a code defect, not the deliberate external blocker caused by the known
`HP:0033133` live-source row.

### High — phenotype extraction is clinically incorrect and fail-open

`backend/migration/phenopackets/observation_extractor.py:95-129` always selects
`question.definition_ids[0]` for any non-NA/NR/negative token. Consequently:

- `RenalInsufficancy="Stage 5 chronic kidney disease"` becomes
  `HP:0012622` (CKD unspecified), not `HP:0003774`.
- An unknown value such as `unexpected-category` is accepted as PRESENT and is
  also assigned `HP:0012622`, rather than failing domain validation.
- `KidneyBiopsy` cannot select oligomeganephronia vs multiple glomerular cysts
  and cannot preserve a source value that asserts both findings.

This violates the typed observation, domain-validation, and no-label-laundering
contracts even though the raw string is retained. Tests cover only plain NR plus
one `RenalCysts` laterality token and miss categorical values.

### High — all 408 compound laterality assertions cannot be extracted

The parser itself returns the correct two modifiers for `unilateral left/right`,
but the definition registry excludes `SolitaryKidney` from
`_LATERALITY_COLUMNS` (`backend/app/phenopackets/curation/definitions.py:86-92`).
The committed audit file contains 47 compound `SolitaryKidney` assertions. A
synthetic source row with `SolitaryKidney="unilateral left"` fails Pydantic
validation with “source phenotype definition does not allow laterality.” Thus
the claimed 408-row conservation is impossible. The extractor also ignores the
loaded `Phenotype_modifier` sheet and uses hardcoded mappings, contrary to Task
7's versioned-source requirement.

### High — operational persistence does not enforce the privacy contract

`sanitize_operational_payload()` rejects suspicious **keys** and email-shaped
string values, but permits secrets and linkable clinical text under an innocuous
key (`backend/app/phenopackets/curation/import_models.py:43-74`). For example,
both `{"message": "password=hunter2"}` and
`{"message": "Family A / II-2; rare clinical comment"}` are accepted, and
`ImportRepository.finish_run()` persists the result
(`backend/app/phenopackets/curation/import_repository.py:106-125`). This does not
satisfy “no passwords, comments, raw clinical payloads, or reviewer identifiers
in run summaries/errors.” A closed typed run-summary/error schema is needed;
substring checks on keys are insufficient.

The reviewer-account import was removed, and a serialized observation does not
contain the raw reviewer email. No changed test captures logs to prove the Task
0 logging requirement, however, and the operational persistence defect above is
independently reproducible.

### High — the legacy CLI still has a partial-output path and ignores its gate

The database-write branch is genuinely disabled at
`backend/migration/direct_sheets_to_phenopackets.py:219-223`. However:

- `SOURCE_IMPORT_ENABLED=False` is declared but never read; invoking the CLI
  still fetches and builds from the remote source.
- `build_phenopackets()` catches per-individual exceptions and continues
  (`:137-159`).
- `--dry-run` writes whatever subset was built and exits successfully
  (`:211-218`).

Therefore the code does not meet Task 9's “replace catch-and-continue” and
“CLI nonzero unless built/stored/verified counts match” requirements. It is safe
from partial database writes today, but not from partial migration artifacts or
unauthorized remote-source processing.

### Medium — week parsing ignores the required clinical context

`parse_source_age()` accepts a `context` argument but never uses it and maps
every `w/wk/wks/week/weeks` token to gestational age
(`backend/migration/phenopackets/strict_age_parser.py:21-37`). The extractor
does not pass cohort/prenatal context. Thus `AgeReported="12 weeks"` for a
postnatal infant becomes gestational age, contrary to design §4.5, which limits
week-as-gestational semantics to prenatal/fetal context. The required `28w` and
`35wks` regressions pass, prenatal maps to Antenatal onset, postnatal remains
unprojected, and AgeReported is not copied into phenotype onset; the broader age
semantics are still incomplete.

### Medium — the 60-column map is structural, not source-faithful

There are exactly 60 unique header/path entries, and the extractor retains raw
values for those cells. Several required typed meanings are absent:

- publication lookup is not used; `Publication` is naively treated as a PMID
  and DOI is always absent (`observation_extractor.py:197-201`);
- per-phenotype evidence is never constructed;
- normalized VRS/GA4GH variant data and parser/mapping/ontology versions and
  warnings are absent;
- source modifier mappings are not consumed.

Accordingly, the `len(SOURCE_COLUMNS) == 60` test proves column enumeration, not
the Task 8 conservation semantics or §11 clinical regressions.

### Medium — the new “atomic” service is not transaction-owning or complete

`AtomicObservationImportService` accepts an arbitrary per-record callback and
an optional rollback (`backend/migration/import_service.py:40-77`). It starts no
transaction, cannot prevent a callback from committing, takes no advisory/row
locks, writes no bindings/revisions/audit state, performs no in-transaction
re-read/MV/search verification, and does not commit once after verification.
Its test asserts that a Python rollback callback was invoked, not that zero
database changes remain. This API should not be wired as-is.

The absence of wiring is a safe, deliberate shared-state-service blocker. The
unsafe atomicity claim/API surface is a defect. There is no current clinical
apply path, so this finding describes readiness rather than an active partial
database mutation.

### Medium — import-run provenance is missing from revisions

Task 6 and design §7 require `phenopacket_revisions.import_run_id` with a foreign
key to `source_import_runs`. Neither the ORM nor
`c0f422b00004_source_import_tables.py` adds it. The six operational tables and
their principal uniqueness constraints are otherwise present: immutable
snapshot uniqueness, retryable attempts plus one partial-unique applied run,
dataset subject uniqueness, dataset report uniqueness, and record-observation
uniqueness.

The migration downgrade is guarded only by an environment variable
(`c0f422b00004_source_import_tables.py:149-167`); setting it after activation
would still delete correction evidence. That is not an enforceable
pre-activation check.

### Medium — the manifest model cannot be persisted through its repository

`get_or_create_snapshot()` sends `source_manifest` through
`sanitize_operational_payload()` (`import_repository.py:57-83`). A normal
`dataclasses.asdict(SourceManifest)` is rejected because tuples such as
`headers` are unsupported (and `row_count` also matches the forbidden `row`
key). The repository has no serializer for the manifest it is designed to
store. Existing tests never pass a real `SourceManifest` through the repository.

### Low — repository lint is not green

`uv run ruff check .` fails with I001 in
`backend/tests/test_alembic_env_autogenerate.py:26-44` because the newly added
curation model import is out of order. The report's unqualified “ruff check
passed” statement is not reproducible at `b34d50f`.

## Acceptance matrix

| Requirement | Result |
| --- | --- |
| Forbidden public-sheet columns fail closed | Partial. Five substrings are rejected, but credential equivalents such as `api_key`/`auth` are not covered, and tests exercise a non-fetched `Reviewers` shape rather than the complete configured source. |
| No reviewer/secret persistence or logging | Fail. Reviewer account creation/raw email observation storage are removed, but operational payloads accept secret/clinical strings; no log-capture regression exists. |
| Exact 60-column mapping | Structural pass, semantic fail. Sixty paths exist, but categorical phenotype, publication/evidence, modifier, and normalized variant semantics are incomplete or wrong. |
| Age semantics | Partial. Named regressions pass; prenatal/fetal context is ignored for week units. |
| Laterality semantics | Fail. Compound pairs work for covered columns, but 47 known SolitaryKidney rows cannot validate and source modifier mappings are ignored. |
| Operational uniqueness/migration | Partial. Six tables, major uniques, applied-run partial index, Alembic head, and metadata registration are present; revision `import_run_id`, enforceable downgrade safety, and real repository integration are absent. |
| Legacy apply disabled | Database apply pass. Remote fetch/build and partial dry-run paths remain reachable; the feature flag is unused. |
| No partial import path | Database currently safe because no new apply is wired and legacy DB apply raises. End-to-end atomic import is not implemented; partial dry-run output remains. |
| 939/864/28,170/408 conservation and Task 16 backfill | Not implemented or verifiable without the pinned fixture/backfill pipeline. |

## Safe deliberate external/configuration blockers

These are not implementation defects by themselves and should remain fail-closed:

- confirmation that credential-bearing public columns were removed and affected
  credentials rotated;
- an authorized immutable source snapshot and SHA-256, audited stable unique
  `report_id`, row-HMAC secret, approved pseudonymous reviewer mapping, and
  legal/privacy approval for linkable comments/identifiers;
- correction or explicitly reviewed ledger handling of the known live
  `HP:0033133`/renal cortical hyperechogenicity contradiction;
- the shared state-service bulk transaction primitive, database-backed failure
  injection tests, de-identified pinned 939-row fixture, and Task 16 forward
  backfill/adjudication artifacts.

Those blockers justify keeping apply disabled. They do not explain the source
schema mismatch, clinical extraction defects, sanitizer weakness, missing
revision FK, or partial dry-run behavior.

## Verification evidence

- Reviewed frozen diff `8a691bf..b34d50f` and the requested design/plan sections.
- Focused changed suite: **36 passed**, 4 warnings.
- Legacy direct-migration suite: **12 passed**, 1 warning.
- `uv run alembic heads`: `c0f422b00004 (head)`.
- `git diff --check 8a691bf..b34d50f`: passed.
- `uv run ruff check .`: **failed**, one I001 error plus two pre-existing invalid
  `noqa` warnings.
- Reproduction probes confirmed the current header contract rejection, Stage 5
  -> CKD-unspecified misclassification, unknown categorical acceptance,
  SolitaryKidney laterality validation failure, normal manifest serialization
  rejection, and acceptance of secret/clinical message strings.

## Spec/quality conclusion

The increment is a useful containment scaffold, but it is not source-faithful,
atomic, privacy-complete, or backfill-ready. **Spec verdict: does not meet the
selected sections/tasks. Quality verdict: request changes before integration.**

## Review response — 2026-08-09

- Corrected the closed source contracts to the repository-authoritative
  phenotype and publication headers; headers remain exact and fail closed.
- Made gestational week syntax require fetal/prenatal context, threaded cohort
  context into extraction, and added categorical CKD matching plus explicit
  failure for unknown multi-definition categorical values.
- Added `SolitaryKidney` to the allowed compound-laterality registry so all
  documented unilateral rows can retain both modifiers.
- Tightened operational payload strings to digest-only values, blocking secret
  and clinical free text regardless of innocuous key names.
- Enforced `SOURCE_IMPORT_ENABLED` before source loading and changed legacy
  build failures to abort before dry-run output is written.
- Added `phenopacket_revisions.import_run_id` ORM/migration FK and optional
  state-service revision metadata plumbing; corrected Alembic downgrade order.
- Fixed the reported Ruff import ordering issue.

Fresh verification: focused plus legacy migration tests: **40 passed**;
isolated Alembic worker-database smoke: **1 passed**; `ruff check app migration
tests/test_alembic_env_autogenerate.py`: passed. Test runs emitted only the
existing async event-loop deprecation warning.

## Scoped re-review follow-up

- `load_data()` now checks the import gate before invoking its adapter; invalid
  IDs, limited non-fixture runs, and any individual build failure abort before
  a dry-run artifact can be written. Logged build failures contain no source ID
  or exception payload.
- Phenotype extraction now rejects unrecognised single/multi values, retains all
  recognised multi-biopsy findings, and attaches negative status to every
  applicable configured definition rather than silently choosing a first one.

## Remaining blocker completion — 2026-08-09

- `Phenotype_modifier` is now parsed from the validated snapshot during
  `load_data()`. Laterality parsing requires the resulting complete,
  content-addressed vocabulary and has no built-in source-term fallback.
- Added the closed `SourceManifestPayload` persistence shape: it retains only
  configured operational identifiers, exact structural headers, non-negative
  row counts, and real 64-hex SHA-256 digests. The repository accepts that
  typed manifest and persists the row counts without raw source cells.
- Tightened generic import-run payload digests to exactly 64 hexadecimal
  characters. Repository integration now has an async persistence regression.
- `edit_record()` now carries a trusted `import_run_id` through both draft
  paths to the append-only revision row; its FK migration remains additive.

Fresh verification: focused source-import/provenance plus frozen-laterality
regression suite: **54 passed** (one existing async event-loop warning);
targeted Ruff: passed; isolated test-database Alembic downgrade to
`b9f422b00003` and upgrade to `c0f422b00004`: passed.

## Final acceptance follow-up — 2026-08-09

- The loaded, versioned modifier vocabulary is now injected through the active
  direct builder into its production phenotype extractor; compound laterality
  rows therefore build with source-supplied terms rather than a fallback.
- `KidneyBiopsy = no` is retained as a typed, curated `NOT_ASSESSED`
  observation without inventing two excluded pathology findings.
- Dry-run JSON uses a same-directory temporary file, flush/fsync, and atomic
  replacement; serializer failure removes the temporary artifact and leaves no
  visible output.
- The source-import migration downgrade now queries operational-table counts,
  imported revision links, and `source_bound` records. Any evidence blocks the
  destructive rollback; the former environment-variable override is removed.

Fresh verification: focused acceptance regressions: **26 passed**; targeted
Ruff: passed; clean isolated Alembic downgrade/upgrade smoke: passed.

## Transaction and publication acceptance completion — 2026-08-09

- `TypedObservationImportService` now creates a source-subject binding as well
  as each source-report binding. It executes in one outer transaction (or a
  caller savepoint), with flushed checkpoints used only by deterministic
  failure-injection tests.
- Isolated PostgreSQL integration regression injects a failure after dataset,
  snapshot, run, record, revision, and binding persistence. Every case proves
  zero datasets, snapshots, runs, subject/report bindings, phenopackets, and
  revisions remain. The success case proves `applied` run accounting, one
  binding of each kind, and revision `import_run_id` provenance.
- Publications are now read from the pinned validated sheet into a strict
  mapping. Each non-placeholder row needs a PMID or DOI; aliases with
  conflicting references fail closed, as do unknown source aliases. Raw source
  aliases remain typed evidence while direct projection emits normalized PMID
  and DOI identifiers.

Fresh verification: focused Lane C suite: **37 passed**; targeted Ruff:
passed. Isolated-worker migration smoke first asserted downgrade safety,
then completed `c0f422b00004 -> b9f422b00003 -> c0f422b00004` successfully.

## Active typed-import architecture completion — 2026-08-09

- The direct command now accepts only explicit pinned local-fixture
  configuration: fixture directory, manifest SHA-256, row-HMAC key, approved
  pseudonymous reviewer map, accountable actor, and async session. It has no
  live Sheets/default database authority. Non-dry mode invokes `apply_typed`;
  limits are permitted only for explicit test dry-runs.
- Typed apply now persists the complete v2 `hnf1bCuration` profile ledger
  (`observationsById`, source HMAC/provenance, and run ID) alongside its
  canonical deterministic GA4GH projection. Initial imported revisions are
  revision 1 and carry projection version `1.0`; source subject/report
  bindings point at the stored record/observation identities.
- Preflight requires every map key and observation provenance to match the
  pinned manifest and requires the Individuals row count to match built
  observations. Exact applied snapshot reruns are no-ops. Changed snapshots
  reject active drafts and otherwise append a state-service draft revision to
  the bound record rather than creating a duplicate.
- Laterality now recognizes only exact approved qualifier token sequences;
  conflicting/reordered/punctuated qualifiers fail closed. Reviewer mapping
  values are validated as opaque `reviewer-*`/`Reviewer N` references before
  source loading and during extraction.
- Retired `test_direct_phenopackets_migration.py`: it tested the deliberately
  disabled legacy builder and its fabricated legacy disease behavior rather
  than the supported typed importer.

Fresh verification: typed DB migration/apply smoke **15 passed** on a fresh
isolated `hnf1b_user` worker database; Alembic completed
`c0f422b00004 -> b9f422b00003 -> c0f422b00004`; targeted Ruff passed; mypy
reported **Success: no issues found in 9 source files**.

## Final reimport transaction completion — 2026-08-09

- The source-import CLI now owns the outer async transaction explicitly. It
  resolves the accountable actor inside `session.begin()`, calls the typed
  apply through a savepoint, commits exactly once on success, and rolls the
  entire operation back on every exception. Separate-session PostgreSQL
  regressions prove both durable successful persistence and no committed run
  after an injected failure.
- A complete changed snapshot now retires every omitted active report binding
  and removes omitted subject bindings in the same transaction as the new
  revisions. Regressions cover removal of one report from a two-report subject
  and replacement of a prior subject; no active binding can then reference an
  observation absent from the stored complete profile.
- Reimport now validates `individual_id == source_subject_id ==` the
  `observations_by_subject` map key before any operational write. Changed
  records carry their correction chain and valid, digest-verified projection
  resolutions through the canonical projection into the next state-service
  revision; stale resolutions remain fail-closed in the projector rather than
  being silently discarded. Exact-snapshot no-ops leave curator overlays
  untouched.

Fresh verification: focused importer/direct-source/curation suite: **81
passed**; transaction-specific isolated PostgreSQL suite: **19 passed**;
Ruff: passed; mypy: **Success: no issues found in 3 source files**. On an
empty isolated `hnf1b_user` database, Alembic completed
`c0f422b00004 -> b9f422b00003 -> c0f422b00004`. A separate smoke against a
database with committed source-import evidence correctly refused downgrade,
as designed.
