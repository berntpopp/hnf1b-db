# Wave 4 — Fresh Session Kickoff Prompt

**Created:** 2026-04-11
**For:** Claude Code fresh session running in `/home/bernt-popp/development/hnf1b-db`
**Skill required:** `superpowers:executing-plans` (auto-loaded via `superpowers:using-superpowers` SessionStart hook)
**Base branch:** `main` @ `514c6e8` (Wave 3 merged as PR #231 on 2026-04-11)

---

## How to use this file

1. Open a new Claude Code session with the working directory at
   `/home/bernt-popp/development/hnf1b-db` (launch a fresh `claude`
   from that directory, or `/clear` in an existing session).
2. Copy the fenced prompt block below **verbatim** and paste it as
   the first user message.
3. The fresh session will:
   - Auto-load `superpowers:using-superpowers` via the SessionStart hook.
   - Invoke `superpowers:executing-plans` (implied by "Execute Wave 4").
   - That skill will invoke `superpowers:using-git-worktrees` to set
     up the sibling worktree.
   - Read the plan, flag stalenesses, wait for your approval on the
     amendment before touching code.
   - Execute tasks with atomic commits.

---

## The prompt

~~~markdown
Execute Wave 4 (backend decomposition) using superpowers.

Plan: docs/superpowers/plans/2026-04-10-wave-4-backend-decomposition.md

Before touching any code:

1. Read the full plan critically against the current codebase state.
   Wave 3 taught us that 1000-line plans drift — the Wave 4 plan was
   written 2026-04-10 before Wave 3 landed, and some scope has moved.
   In particular, plan line 29 says "verify survival/handlers.py is
   under 500 LOC" — that file no longer exists; Wave 3 split it into
   survival/handlers/{base,variant_type,pathogenicity,disease_subtype,
   protein_domain,factory}.py. Expect other similar stalenesses.

2. Set up an isolated sibling worktree at
   ~/development/hnf1b-db.worktrees/chore-wave-4-backend-decomposition
   branching from main (currently at 514c6e8 — Wave 3 merged as PR
   #231). Use the sibling-directory convention documented in
   CLAUDE.md; never create worktrees inside the repo.

3. Run `make check` in the fresh worktree to establish a clean
   baseline (backend + frontend). Expected baseline after Wave 3:
   backend ~879 passing + 1 skipped + 3 xfailed, frontend all green
   with 23 pre-existing lint warnings.

4. Amend the plan in its own commit BEFORE executing any tasks if
   you find material inaccuracies. Follow the Wave 3 pattern: write
   an "Amendment note (2026-04-11)" block at the top of the plan
   explaining what changed and why, then commit with subject
   "docs(refactor): amend Wave 4 plan to match reality".

5. Only after the plan is accurate and the baseline is green, start
   executing tasks. Create a TaskCreate entry per plan task for
   progress tracking.

Context to carry forward:

- Current branch: main @ 514c6e8, Wave 3 complete, PR #231 merged.
- The 2026-04-09 codebase review at
  docs/reviews/codebase-best-practices-review-2026-04-09.md lists
  the Wave 4 targets: admin_endpoints.py (1,159 LOC), crud.py
  (1,002 LOC), process-local _sync_tasks replacement, request ID
  middleware.
- A newer platform-readiness review is at
  docs/reviews/2026-04-11-platform-readiness-review.md — read this
  too; it may contain additional Wave 4 inputs.
- CLAUDE.md documents the sibling-worktree convention (commit
  1d30529).
- Wave 3 exit note is at docs/refactor/wave-3-exit.md.

When Wave 4 is complete, follow
superpowers:finishing-a-development-branch to open the PR against
main.
~~~

---

## Lessons from Wave 3 you will want in the front of your mind

These bit us during Wave 3 execution. Watch for them in Wave 4.

1. **The plan will be stale.** Every Wave 3 task needed real-code
   verification before execution. Wave 3 dropped 2 entire tasks
   (parity tests, materialized_view_fallback context manager) that
   were no longer relevant, and added 1 new one (smoke test + route
   fix) that the plan had not anticipated. Budget time for plan
   amendment, not just execution.

2. **SQLAlchemy `RowMapping` vs `Row` is a subtle trap.**
   `result.mappings().all()` returns `collections.abc.Mapping`
   subclasses that are **not** `dict` and do **not** expose
   `._mapping`. Any helper you write that handles row objects must
   dispatch on `isinstance(row, Mapping)` first, then fall back to
   `hasattr(row, "_mapping")`. A helper that silently masks this
   with `data.get(key, 0)` ships wrong data — fail loud.

3. **Endpoint-level HTTP tests catch bugs that unit tests miss.**
   Wave 3 had a RowMapping dispatch bug that unit tests passed
   (because the fake row had `_mapping`) but real endpoints would
   have failed at runtime (because real RowMapping does not). Add
   `test_*_endpoints.py` smoke tests for every HTTP route you
   touch — they hit the real FastAPI stack and the real SQLAlchemy
   driver output.

4. **Codecov patch coverage is calculated on NEW lines only.** A
   0% patch-coverage report on a file means your PR added lines
   that are never executed by any test — NOT that the file is
   untested overall. Target the specific added lines.

5. **Abstract method `pass` bodies should be excluded from
   coverage.** Wave 3 added a `[tool.coverage.report]` block in
   pyproject.toml with `exclude_also` patterns for `@abstractmethod`,
   `pass`, `...`, `if TYPE_CHECKING:`, `raise NotImplementedError`.
   Keep that config working.

6. **Route fixes and tests that depend on them belong in separate
   commits.** Wave 3 Task 2 had to convert `raise ValueError` to
   `raise HTTPException(400)` in the survival route BEFORE the
   smoke tests could assert `== 400`. The commits were ordered
   accordingly. If a test depends on a code change, commit the
   code change first.

7. **Backwards-compatibility shims should have DeprecationWarning.**
   Wave 3 added a `survival_handlers.py` shim at the old import
   path because an external reviewer (correctly) pointed out that
   the docstring claim "backwards compatible" was not true without
   it. If Wave 4 deletes or moves any public symbol, add a shim
   with a one-time DeprecationWarning.

8. **Don't trust the review doc's line counts blindly.** The
   2026-04-09 review says `admin_endpoints.py` is 1,159 LOC and
   `crud.py` is 1,002 LOC — verify these with `wc -l` before
   planning the split, because unrelated changes may have moved
   these numbers.

9. **The untracked `.codex` directory and `docs/reviews/*.md`
   files have been in the working tree across multiple sessions.**
   They are not yours to commit. Leave them alone unless the user
   explicitly asks.

10. **The user prefers `--merge` (not squash) for wave PRs.**
    Previous waves (#229, #230, #231) all used merge commits
    preserving the granular task-by-task history. Match that when
    you open Wave 4's PR.

---

## Wave 4 target inventory (from the 2026-04-09 review)

Read these before amending the plan. Verify the line counts first.

| Priority | Target | Current | Wave 4 Goal |
|---|---|---|---|
| P2 | `backend/app/api/admin_endpoints.py` | 1,159 LOC | Split into: router, orchestration service, task persistence, query layer |
| P2 | `backend/app/phenopackets/routers/crud.py` | 1,002 LOC | Extract `PhenopacketRepository` |
| P3 | Process-local `_sync_tasks` dict in admin_endpoints.py | — | Replace with durable Redis or DB task state |
| P4 | No request ID in logs | — | Add request ID middleware for log correlation |
| P5 | No `PhenopacketRepository` | — | Centralise CRUD query logic out of route handlers |

Plus anything new from `docs/reviews/2026-04-11-platform-readiness-review.md` — read that in the fresh session; I have not yet.

---

## Baseline to match at the end of Wave 4

Before opening the Wave 4 PR, the worktree should show:

- `backend && make check` — lint (ruff) clean, typecheck (mypy) clean, format clean, pytest ~879+ passing.
- `frontend && make check` — lint, format, tests all green (23 pre-existing warnings are baseline, not new).
- `wc -l backend/app/api/admin_endpoints.py backend/app/phenopackets/routers/crud.py` — both under 500 LOC.
- `docs/refactor/wave-4-exit.md` — exit note written and committed, matching the structure of wave-3-exit.md.

When that's all green, invoke `superpowers:finishing-a-development-branch` to open the PR against main.

Good luck.
