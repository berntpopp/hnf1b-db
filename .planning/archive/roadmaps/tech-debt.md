# Refactor Tech Debt Register

Two kinds of entries live here:

1. **Files intentionally exceeding the 500-LOC rule** from `CLAUDE.md`
   after the backend decomposition waves. Every entry needs a
   justification and a re-evaluation trigger.
2. **Architectural compromises** made during a wave to preserve
   existing test contracts — each entry tracks the workaround, why
   it exists, and what would let us delete it.

## Backend — LOC exceptions

After Wave 4 (2026-04-11), every file in `backend/app/` is under 500 LOC:

```bash
$ find backend/app -name "*.py" -exec wc -l {} \; | awk '$1 > 500' | sort -rn
(no results)
```

The table below is therefore empty. If a future wave introduces a
justified exception, add a row with a concrete re-evaluation trigger —
not "too complex to split", which is a symptom, not a reason.

| File | Lines | Justification | Re-evaluate when |
|------|:-----:|---------------|------------------|
| _none_ | — | — | — |

## Backend — Architectural compromises

| Area | What | Why | Re-evaluate when |
|------|------|-----|------------------|
| `app/phenopackets/validation/variant_validator/` | Submodules read `cache` and `settings` through `from app.phenopackets.validation import variant_validator as _vv_pkg` and look them up at call time (`_vv_pkg.settings.external_apis.vep.base_url`) instead of importing them directly. The package `__init__.py` re-exports both names before loading any submodule. | The 1,671-line regression test suite `test_variant_validator_enhanced.py` patches `app.phenopackets.validation.variant_validator.cache` / `.settings` — the pre-Wave-4 flat module exposed both at that import path. Binding the names at submodule import time would have made those patches no-ops and broken 28 tests. | The regression suite is updated to patch at submodule level (`...variant_validator.vep_annotate.settings` etc.). At that point the `_vv_pkg` indirection can be deleted and submodules can `from app.core.config import settings` normally. |
| `app/phenopackets/validation/variant_validator/rate_limiter.py` | `check_rate_limit_headers` uses `print("WARNING: ...")` for near-quota warnings instead of `logger.warning(...)`. | `test_variant_validator_enhanced.py` asserts `patch("builtins.print").assert_called_once()` to verify the warning fires. Switching to `logger.warning` would break those tests on a pure refactor PR. | The regression test is rewritten to assert via `caplog` (pytest logging capture) instead of monkey-patching `builtins.print`. Once that lands, switch to the logger. |
| `app/phenopackets/repositories/phenopacket_repository.py` | `PhenopacketRepository.session` property exposes the raw `AsyncSession` so callers can run bespoke SQL. | The `crud_related` router has heavy JSONB by-variant/by-publication queries that don't fit the repository's current query-builder surface. Wrapping them would have doubled the Wave 4 scope without removing any SQL. | A dedicated `by_variant(variant_id)` / `by_publication(pmid, filters)` repo method exists and the session property is no longer referenced outside the repo package. |

## Wave 5b -- pwdlib bcrypt verifier fallback transition period

**Introduced:** Wave 5b Task 11 (passlib -> pwdlib migration)
**Owner:** Backend / Auth
**Status:** OPEN -- re-evaluate post every-user-login

`backend/app/auth/password.py` uses `pwdlib.PasswordHash` with
`Argon2Hasher` (primary) and `BcryptHasher` (fallback verifier) for
legacy `$2b$...` hashes from the passlib era. The `verify_and_update`
path in the login endpoint transparently upgrades any successfully
verified legacy hash to Argon2id -- no forced logouts, no user-visible
change.

The bcrypt verifier fallback is a permanent runtime cost (extra
allocator + code path) until every live user has logged in at least
once post-Wave-5b.

**Re-evaluation criterion:**

```sql
SELECT COUNT(*) FROM users WHERE hashed_password LIKE '$2b$%';
```

When this returns 0, we can drop `[bcrypt]` from the pwdlib extra and
use `PasswordHash([Argon2Hasher()])` only. Until then, keep the fallback.

## Frontend

Populated during Wave 5 if and when any Vue component stays over 500
LOC with a justified reason. Currently unpopulated.

| File | Lines | Justification | Re-evaluate when |
|------|:-----:|---------------|------------------|
| _none_ | — | — | — |
