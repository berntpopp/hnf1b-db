# HNF1B-DB Path To >8.0 And Current PR Review

Date: 2026-04-15
Scope:
- current codebase state on local `main`
- historical plans, exit notes, and deferred items
- current open PR `#254` (`feat(wave-7-d2): effective-state routing + comments/edits/mentions`)
- current external best practices for code review, API security, FastAPI, SQLAlchemy async, and Vue testing

References reviewed:
- `.planning/reviews/codebase-best-practices-review-2026-04-09.md`
- `.planning/reviews/2026-04-11-platform-readiness-review.md`
- `.planning/archive/reviews/codebase-review-wave-6-rescore.md`
- `.planning/archive/reviews/wave-5-exit.md`
- `.planning/archive/reviews/wave-5c-exit.md`
- `.planning/archive/reviews/wave-6-exit.md`
- `.planning/archive/plans/2026-04-11-wave-5-scope.md`
- `.planning/plans/2026-04-14-wave-7-d2-comments-and-clone-advancement.md`
- `.planning/specs/2026-04-14-wave-7-d2-comments-and-clone-advancement-design.md`

## Bottom Line

The codebase can credibly get above `8/10`, but not by adding more collaboration features first.

The old Wave 6 rescore to `8.1/10` was internally consistent against the Wave 1-6 roadmap, but that roadmap explicitly deferred several high-risk areas:

- cookie/session hardening
- session inventory / forced logout
- ORCID / preferences / attribution
- full review-history UI
- comments/review workflow

Those deferred areas are exactly where the live risk now sits. On the current codebase, the shortest route to a real and defensible `>8.0` platform score is:

1. close the remaining security and session gaps
2. close the workflow visibility / concurrency gaps
3. stabilize verification so test results are trustworthy
4. then merge workflow enrichments like PR `#254`

PR `#254` is directionally good and likely worth merging after fixes, but it does **not** by itself move the platform above `8/10` because it expands workflow surface area without first removing the largest ship-risk items.

The April 15 planning/docs cleanup was directionally correct and modernized repository hygiene, but it also exposed one more platform-readiness rule: durable documentation must stay separate from internal planning. The repo is not fully there yet because several stable docs still link directly into `.planning/` plans.

## Current PR Status

There is one current open PR:

- `#254` — `feat(wave-7-d2): effective-state routing + comments/edits/mentions`
- URL: https://github.com/berntpopp/hnf1b-db/pull/254
- State: open
- Mergeable: true

What it adds:

- effective-state routing for the clone-cycle
- comments, comment edit history, mention join table
- `Discussion` tab on `PagePhenopacket.vue`
- mention autocomplete endpoint
- tests around comments and clone-cycle behavior

What it does **not** fix:

- frontend token storage in `localStorage`
- token revocation / refresh-token hardening
- locked/deactivated-user token issuance gaps
- timeline visibility leak
- non-atomic delete/state race exposure
- production email fallback risk
- the likely phenopacket-publication edit bug

## What The Old Plans Still Leave Open

The key point from the old plans is not "everything was done". It is "the roadmap completed the chosen waves, while explicitly deferring the hardest security/platform items."

### Explicitly deferred in the Wave 5 scope

`.planning/archive/plans/2026-04-11-wave-5-scope.md` explicitly deferred:

- Bundle D comments/review workflow
- Bundle E ORCID + preferences + attribution
- rest of Bundle F cookie-based refresh token, sessions table, session inventory UI, forced logout on role change
- private contributor dashboard
- real SMTP infrastructure

### Confirmed deferred in the Wave 5 exit

`.planning/archive/reviews/wave-5-exit.md` still lists as remaining:

- comments / review screen
- ORCID / preferences / public attribution
- HttpOnly cookie refresh token, sessions table, CSRF
- real SMTP

### Why that matters now

Those were reasonable deferrals at the time, but they mean the old `8.1/10` should be interpreted as:

`8.1/10 for the Wave 1-6 refactor roadmap`

not:

`8.1/10 for the current platform-readiness bar`

For the current platform-readiness bar, the unresolved deferred items and the newly-observed regressions are still material.

## What Still Blocks A Real >8.0

### A. Security and session management

This is still the single biggest blocker.

Open issues:

- frontend tokens still live in `localStorage`
- token issuance does not consistently enforce lock/deactivation state
- refresh-token lifecycle is too weak after password change/reset
- no real session inventory or forced logout path
- email delivery can still degrade to console behavior in production-like misconfiguration
- durable docs still depend on internal planning files for developer-facing explanation

Why this blocks `>8`:

- OWASP API Security Top 10 2023 still treats broken authentication and function-level authorization as top-tier risks
- the 2026-04-11 review already identified the cookie/session hardening path as the correct target
- `docs/adr/0001-jwt-storage.md` recorded a localStorage decision, but the live threat picture has not improved enough to make that an `>8` posture

### B. Workflow integrity

Open issues:

- timeline endpoint still bypasses the newer visibility model
- delete is still vulnerable to real race windows
- revision provenance still looks fragile in multi-actor flows
- current detail UI still under-serves audit/revision visibility

Why this blocks `>8`:

- the workflow model is increasingly sophisticated
- once you introduce state machines, comments, approvals, and revisions, concurrency and visibility bugs become more severe than ordinary CRUD bugs

### C. Verification and trust in CI

Open issues:

- targeted backend pytest slices currently fail
- some failures are true defects
- others are test-isolation and session-boundary problems

Why this blocks `>8`:

- a platform cannot honestly score above `8` if its critical verification loops are not trustworthy
- SQLAlchemy async best practice is especially relevant here: `AsyncSession` is stateful, and misuse across boundaries creates exactly the kind of nondeterministic breakage now showing up

### D. Remaining product-platform gaps

Still not delivered:

- ORCID linking
- user preferences / attribution consent
- private contributor dashboard
- richer curation history UI

These are not the first blockers, but they are still part of the platform-readiness scope defined on 2026-04-11.

### E. Documentation and instruction hygiene

Open issues:

- durable docs still point to `.planning/plans/variant-annotation-implementation-plan.md`
- some live docs and planning artifacts still refer to the pre-migration `CLAUDE.md` wording and should be normalized to `AGENTS.md`

Why this blocks a clean `>8` posture:

- current documentation best practice favors a small set of accurate docs and deleting dead or duplicate operational guidance
- current Codex guidance favors small repository-level instructions and reusable skills/workflows
- the instruction-file migration needs to be carried through current live docs, not just added at repo root

## PR #254 Review In Context

## What is good

- It closes a real deferred area from the old plan: comments/discussion.
- It improves the D.1 clone-cycle by introducing effective-state routing.
- It is aligned with the D.2 design/spec and the April platform-readiness recommendation to add collaboration workflow.
- The patch appears to include real tests, not just UI scaffolding.

## Why it is not enough for >8

PR `#254` mainly expands editorial workflow capability. That is useful, but not what is currently keeping the score down.

If merged as-is, it likely improves:

- collaboration readiness
- curator UX
- architecture completeness for the workflow layer

But it does not materially improve:

- session security
- API authorization robustness
- operational reliability
- confidence in backend verification

So the PR is probably a **good PR**, but not the **highest-leverage PR** for getting above `8/10`.

## Recommendation on PR #254

Merge it only after, or alongside, fixes for:

1. timeline visibility enforcement
2. atomic delete/state mutation
3. token issuance enforcement for locked/inactive users
4. phenopacket edit publication-binding regression if confirmed

If you want one clean milestone boundary:

- `PR #254` should be treated as `workflow-enablement`
- the next milestone should be `security-and-integrity hardening`

## Clear Instructions To Get Above 8/10

This is the shortest high-confidence sequence.

### Phase 1: Raise the floor

These items are mandatory before any honest `>8` claim.

1. Migrate auth transport to HttpOnly refresh cookie + in-memory access token.
   - Keep the existing refresh queue pattern in `frontend/src/api/transport.js`.
   - Remove long-lived token persistence from `frontend/src/stores/authStore.js` and `frontend/src/api/session.js`.
   - Add CSRF protection for refresh/logout/mutation routes.

2. Enforce account state on every token issuance path.
   - `login()`: reject inactive and locked users before returning tokens.
   - `refresh_access_token()`: reject inactive and locked users, not just unknown users.
   - Add tests for locked login, deactivated refresh, refresh after unlock, refresh after role change if session invalidation is introduced.

3. Revoke refresh capability on password change and password reset.
   - At minimum invalidate current refresh token.
   - Prefer token-version or JTI invalidation over raw single-token persistence.
   - If staying with DB-backed persistence, stop storing raw refresh token material directly.

4. Lock down `crud_timeline.py`.
   - Route through the same visibility rules as detail/list.
   - Decide explicitly whether deleted records should ever be visible in timeline output.
   - Add role-based tests for anonymous, viewer, curator, admin, draft, and soft-deleted states.

5. Make delete/state transitions atomic.
   - Use `UPDATE ... WHERE revision = :expected_revision` or row-level locking.
   - Add one real concurrent integration test, not just stale sequential tests.

### Phase 2: Remove known correctness bugs

6. Fix the phenopacket publication-edit binding path.
   - In `PhenopacketCreateEdit.vue`, unify around a single source of truth.
   - Add regression coverage: load existing record with PMIDs, edit unrelated field, save, verify PMIDs preserved.

7. Fix duplicate-email update handling.
   - Return clean `409` conflict semantics from admin update paths.

8. Make production email delivery fail closed.
   - Production startup should reject `console` backend unless explicitly allowed in a non-prod environment.
   - Keep Mailpit/dev SMTP for development only.

### Phase 3: Make the workflow auditable

9. Finish the history/revision surface.
   - Comments in PR `#254` help discussion, but they are not a substitute for revision audit visibility.
   - Add a first-class revision/history tab using the state/audit data already present.
   - Show authoritative actor identity, transition reason, and diff summary.

10. Strengthen provenance.
   - Add mixed-actor tests for save, submit, approve, publish, comment edit, resolve, delete.

### Phase 4: Finish the deferred platform scope

11. Split stable docs from planning all the way through.
   - Remove `.planning/...` plan links from durable API and user docs unless those plan files are intentionally the archival source of truth.
   - If the implementation details still matter, promote them into stable developer docs under `docs/`.

12. Use one canonical agent-instructions file.
   - `AGENTS.md` should be the canonical source.
   - `CLAUDE.md` may exist only as a tiny compatibility shim that points to `AGENTS.md`.
   - Worst option: maintain both as large overlapping instruction files.

11. Deliver Bundle E equivalents.
   - ORCID link / unlink
   - attribution preferences
   - public contributor attribution model

12. Add session inventory and forced logout.
   - this is the missing operational half of the auth model
   - it also improves admin story and incident response

13. Add a private contributor dashboard.
   - my created
   - my reviewed
   - unresolved discussions
   - recent activity

## Recommended Order Of Work

If the goal is specifically `>8/10`, do the work in this order:

1. auth/session hardening
2. workflow visibility + atomicity fixes
3. verification stabilization
4. PR `#254` merge or follow-up fixes
5. revision/history UI
6. ORCID/preferences/dashboard

Do **not** do ORCID/preferences/dashboard before the first three.

## How To Measure That You Actually Reached >8

Do not use a single narrative score only. Use gates.

### Security gate

- no access or refresh token persisted in `localStorage`
- locked/inactive users cannot mint new tokens
- password reset/change invalidates old refresh capability
- timeline endpoint obeys visibility model

### Integrity gate

- concurrent delete/update test passes
- mixed-actor provenance tests pass
- comments and revisions remain internally consistent after publish/withdraw/resubmit cycles

### Verification gate

- targeted backend auth slice green
- targeted backend workflow slice green
- frontend auth/admin/edit regression slice green
- CI remains deterministic across reruns

### Product-platform gate

- audit/revision UI exists
- session inventory exists
- ORCID/preferences scope either shipped or explicitly descoped from the readiness target

If those gates are green, then `>8` is defensible.

## Practical Next Step

The highest-leverage next milestone is:

**`security-and-integrity hardening`**

Suggested bundle:

- fix token issuance enforcement
- migrate away from `localStorage` token persistence
- revoke refresh on password change/reset
- fix timeline visibility
- make delete atomic
- fix phenopacket publication edit regression
- add regression tests for all of the above

After that, either:

- merge `#254` if not yet merged, or
- immediately follow it with a small `workflow-audit polish` PR

## Sources

- Google Engineering Practices: https://google.github.io/eng-practices/review/reviewer/looking-for.html
- SmartBear Code Review Process: https://smartbear.com/learn/code-review/guide-to-code-review-process/
- FastAPI security tutorial: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- FastAPI bigger applications: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- SQLAlchemy asyncio docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- OWASP API Security Top 10 2023: https://owasp.org/API-Security/editions/2023/en/0x00-toc/
- Vue Style Guide: https://vuejs.org/style-guide/
- Vue Test Utils guide: https://test-utils.vuejs.org/guide/
