# Independent Phenopacket Review — One-Pass PR Review

**Review date:** 2026-08-30

**Reviewed tree:** `353a453`

**Review mode:** One independent, report-only pass. The primary agent accepted and
addressed every finding. No second independent review was requested.

## Outcome

The reviewer reported one Critical, six Important, and one Minor finding. All eight
were accepted. The resulting implementation commits are `e1407db`, `6050c2b`,
`86ed434`, `1ff6f87`, and `306c181`; `8f3689f` adds the final runtime privacy proof.

## Finding ledger

| Severity | Finding | Disposition and evidence | Commit |
| --- | --- | --- | --- |
| Critical | Anonymous publication lists and SEO sitemaps read the mutable working-copy JSON and timestamp. | Accepted. Publication discovery now joins the immutable revision through `head_published_revision_id`; all three dynamic sitemaps use the head content/time. A divergent-head integration test proves the private PMID, variant, and working-copy time are absent. A full public-consumer scan found remaining direct mutable-JSON reads only in authenticated/admin writers or branches that explicitly select the public head for anonymous users. | `e1407db` |
| Important | Router reuse could leave the review workspace on stale record A while route state pointed at B. | Accepted. Route IDs remain reactive; context, history, decisions, issues, completion, tab, error, and conflict state invalidate synchronously. Generation ownership prevents late A success/error/action completion from changing B. A real-memory-router deferred A-to-B regression proves rendering and actions use B. | `1ff6f87` |
| Important | Queue page, count, and facets used three `READ COMMITTED` statements. | Accepted. One SQL statement now computes the filtered base, state facets, page, and metadata through CTEs and an outer join. A deterministic interleaving test commits a second-session row after the first execute and proves page/total/facets remain one snapshot, including an empty out-of-range page. | `6050c2b` |
| Important | Empty or whitespace transition rationales could reach direct service callers. | Accepted. The shared service boundary strips and validates every transition rationale before locking or mutation. API and direct-service tests cover approval, request changes, publication, no pointer/revision movement on failure, and normalized stored evidence. | `86ed434` |
| Important | Blocking-issue mutations were not single-flight and did not expose structured reload recovery for all review conflicts. | Accepted. Create/resolve/reopen are single-flight, map `revision_mismatch`, `review_revision_mismatch`, and `review_closed` to reload-required state, never retry implicitly, replace mutation controls with a focused reload control, and ignore stale-generation failures. Deferred transport and component focus tests cover each path. | `1ff6f87` |
| Important | The promised stable `attestation_required` code was never emitted. | Accepted. Missing and false approval attestation emit the same narrow 422 envelope; direct service callers receive a dedicated validation failure. The OpenAPI `Literal[True]` contract remains intact, snapshot mismatches remain 409, and unrelated validation mapping is unchanged. | `86ed434` |
| Important | `POST /api/v2/comments` did not document its actual shared error envelopes. | Accepted. OpenAPI now lists exact 401/403/404/409/422/500 `ApiErrorEnvelope` responses. Runtime integration proves the three-field envelope and safe 500 for every status. The Python 3.12 snapshot was regenerated and byte-compared. | `306c181` |
| Minor | Workspace history silently stopped after the first 50 revisions. | Accepted. History fetches all declared pages within an explicit 100-page safety bound, exposes total/loading, resets on route reuse, and has a 51-row/two-page regression. It remains separate from server-driven queue table pagination. | `1ff6f87` |

## Deferred-minor audit from Tasks 5–9

| Source | Disposition |
| --- | --- |
| Task 5: reassert author immutability and append-only resolution events after `f0`; decide whether reconciliation preserves a later `updated_at`. | Accepted. Migration regressions explicitly exercise both trigger invariants after downgrade/re-upgrade. Reconciliation now uses `GREATEST(issue.updated_at, latest.created_at)` because overwriting a later legitimate edit time is a correctness defect. Commit `a10b0a0`. |
| Task 6: historical discussion counts and active-cycle contributor ordering/deduplication. | Accepted. `blocking_issues` is record-history-wide while `open_blocking_issues` remains the active approval gate. Distinct active-cycle contributor coverage proves ordered deduplication. Commit `a10b0a0`. |
| Task 7: admin/mobile/viewer navigation and anonymous/curator/admin create/edit route matrix gaps. | Accepted as missing proof, not a production defect. The route/navigation matrix was expanded; no policy-source change was required. Commit `a10b0a0`. |
| Task 8: debounced search, singular issue label, real page/tab/mobile behavior, and tab-aware empty copy. | Accepted. Search state now commits only on the toolbar's debounced event, the issue label pluralizes correctly, empty copy follows the active tab, and page reset/mobile tests exercise real behavior. Commit `a10b0a0`. |
| Task 9: stale success/error ownership and candidate content ID visibility. | Accepted. Direct stale-order tests proved the existing generation guard; candidate cards now render the Phenopacket ID while raw JSON continues to expose extension content. Commit `a10b0a0`. |

## Acceptance-criterion audit

| # | Criterion | Status | Authoritative evidence |
| --- | --- | --- | --- |
| 1 | Owner, submitter, and contributor cannot decide. | Proven | `test_review_policy.py`, `test_api_transitions.py`, and the distinct-curator Playwright lifecycle. |
| 2 | Eligible curator/admin reviews without assignment. | Proven | `test_review_queue.py`, queue capability tests, and the filtered `reviewable_by_me` runtime queue. |
| 3 | Unresolved issue blocks approval under races. | Proven | `test_blocking_review_issues.py`, activation trigger tests, and four-order raw-SQL race tests. |
| 4 | Approval records exact immutable audit evidence. | Proven | Exact-snapshot/service/API tests plus Playwright revision ID, digest, role snapshot, rationale, and attestation assertions. |
| 5 | Publication copies the exact approval without mutation. | Proven | State-service canonicalizer-spy/content-equality tests and two-cycle runtime equality assertions. |
| 6 | Candidates remain private and an old public head survives replacement review. | Proven | Public-head query tests, divergent publication/sitemap integration, and `8f3689f` runtime PMID/variant switch proof. |
| 7 | Effective-state queue remains server driven. | Proven | Single-statement queue repository tests, query-count tests, URL/table Vitest, and runtime filter/pagination. |
| 8 | Workspace is complete and responsive. | Proven | Component/view/composable Vitest, real-router reuse tests, production build, and 375x812 keyboard/non-overflow Playwright. |
| 9 | Historical comments remain non-blocking. | Proven | Migration compatibility, review-context count tests, and ordinary-response lifecycle assertions. |
| 10 | All verification layers pass. | Proven locally | See final verification below. GitHub Actions are deliberately not claimed here. |
| 11 | Independent reviews are adjudicated once. | Proven | The spec-review artifact and this one-pass PR finding ledger; every reported finding has one disposition and no second review pass occurred. |

No acceptance criterion is missing or contradicted in the verified local tree.

## Final local verification

- `make lint`: passed.
- `make typecheck`: passed, 243 source files.
- `make test`: 2,080 passed, 16 skipped, 3 xfailed, 8 warnings in 705.69s
  (2,099 collected).
- `uv run alembic heads` and the dedicated test database both reported
  `f0f422b00007`. The full suite reran activation, reconciliation, guarded downgrade,
  and raw-SQL concurrency tests serially.
- `npm run format:check`: passed.
- `npm run lint:check`: passed with 0 errors and 24 existing warnings.
- `npm test`: 118 files and 1,054 tests passed (final rerun: 5.72s).
- `npm run build`: passed in 10.78s; only existing chunk-size/config warnings.
- Focused Playwright on owned `8000/5174`: 4 passed in 20.9s. The lifecycle fixture
  `review-lifecycle-1788105037617-0` and accessibility/conflict fixtures
  `e2e-review-a11y-1788105054338-0`, `e2e-review-digest-1788105055537-0`, and
  `e2e-review-stale-1788105056932-0` were archived through the API. A direct residue
  query returned zero non-archived matching records.
- Health returned `ready: true` with database and Redis `ready: true`.
- Python 3.12.9 OpenAPI generation produced 408,489 bytes and an independent second
  generation compared byte-for-byte equal.

The initial Playwright attempt was invalid because the owned `127.0.0.1:5174` origin
was omitted from the backend process's default CORS list; all four browser sessions
therefore redirected to login. The fixtures were archived, the owned backend was
restarted with the explicit 5174 origin, and the exact test set passed. This was a
runtime harness configuration issue, not a product assertion failure.

## Residual warnings and boundaries

- Frontend lint retains 24 pre-existing warnings; there are no lint errors.
- Backend warnings are the existing event-loop, Starlette/httpx, pgvector,
  autogenerate, short-test-key, and mocked-coroutine warnings recorded by the full run.
- Build reports existing large chunks and Vite native-config compatibility warnings.
- Local verification does not claim push, PR publication, or GitHub Actions completion.
