# Wave 1: Stop the Bleeding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Patch the two critical security vulnerabilities (XSS via unsanitized `v-html`, hardcoded admin password), eliminate all bare `except Exception:` in backend production code, and sweep out zero-risk cleanup items so later waves start from a clean foundation.

**Architecture:** Small surgical edits. No structural changes. Every fix is its own PR with its own test. No refactoring of surrounding code — fixes only.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, pytest; Vue 3, Vitest, DOMPurify (new dependency).

**Parent spec:** `docs/superpowers/specs/2026-04-10-codebase-refactor-roadmap-design.md`

---

## Context engineers need before starting

**Project structure:**
- Backend lives at `backend/`, uses `uv` for Python deps, `ruff` for lint, `mypy` for type checking, `pytest` for tests. Run `cd backend && make check` for all checks.
- Frontend lives at `frontend/`, uses `npm`, `eslint`, `prettier`, `vitest`. Run `cd frontend && make check` for all checks.
- CLAUDE.md has conventions: NEVER use `console.log` (use `window.logService`), always use conventional commits (`feat(scope): description`), always run `make check` before committing.

**Key files you'll touch:**
- Backend config/auth: `backend/app/core/config.py`, `backend/app/main.py`
- Backend bare excepts: `backend/app/database.py`, `backend/app/phenopackets/routers/crud.py`, `backend/app/api/admin_endpoints.py`, `backend/app/phenopackets/validation/variant_validator.py`, and 6 others
- Frontend XSS: `frontend/src/views/FAQ.vue`, `frontend/src/views/About.vue`
- Frontend cleanup: `frontend/src/api/auth.js`, `frontend/src/utils/auth.js`, `frontend/src/api/index.js.backup`

**TDD discipline (rigid — do not skip):**
1. Write the failing test first.
2. Run it to confirm it fails with the expected error (not a missing-file error).
3. Write the minimal production code to make it pass.
4. Run the test to confirm it passes.
5. Run `make check` on the relevant side (backend or frontend).
6. Commit with a conventional-commit message.

**If a task touches only production code (no new behavior, just cleanup/rename/scrub):** skip the test-writing step but still run the existing test suite before committing. Call this out in each task below where it applies.

**Branch strategy:** Create `chore/wave-1-stop-the-bleeding` branch off main. Every task produces one commit. Push a single PR at wave end with all commits, or push incrementally if you prefer — both are acceptable.

---

## Task 1: Install DOMPurify and create the sanitize utility

**Files:**
- Modify: `frontend/package.json` (add `dompurify` dependency)
- Modify: `frontend/package-lock.json` (auto-generated)
- Create: `frontend/src/utils/sanitize.js`
- Create: `frontend/tests/unit/utils/sanitize.spec.js`

- [ ] **Step 1: Install DOMPurify**

Run from the project root:

```bash
cd frontend && npm install dompurify@^3.3.3
```

Expected: one new dependency added to `package.json` and `package-lock.json`. No peer dependency warnings.

- [ ] **Step 2: Create the test file with failing tests**

Create `frontend/tests/unit/utils/sanitize.spec.js`:

```javascript
/**
 * Unit tests for the sanitize utility.
 *
 * Tests cover: script removal, event-handler stripping, javascript: URLs,
 * and preservation of the markdown-friendly tag whitelist.
 */
import { describe, it, expect } from 'vitest';
import { sanitize } from '@/utils/sanitize';

describe('sanitize', () => {
  it('strips <script> tags', () => {
    const dirty = 'hello <script>alert(1)</script> world';
    const clean = sanitize(dirty);
    expect(clean).not.toContain('<script>');
    expect(clean).not.toContain('alert(1)');
    expect(clean).toContain('hello');
    expect(clean).toContain('world');
  });

  it('strips event handler attributes', () => {
    const dirty = '<a href="https://example.com" onclick="alert(1)">link</a>';
    const clean = sanitize(dirty);
    expect(clean).not.toContain('onclick');
    expect(clean).toContain('href="https://example.com"');
  });

  it('strips javascript: URLs', () => {
    const dirty = '<a href="javascript:alert(1)">click</a>';
    const clean = sanitize(dirty);
    expect(clean).not.toContain('javascript:');
  });

  it('preserves strong, em, and anchor tags used by markdown', () => {
    const dirty =
      '<strong>bold</strong> <em>italic</em> <a href="https://ok.test" target="_blank">link</a>';
    const clean = sanitize(dirty);
    expect(clean).toContain('<strong>bold</strong>');
    expect(clean).toContain('<em>italic</em>');
    expect(clean).toContain('<a ');
    expect(clean).toContain('href="https://ok.test"');
  });

  it('preserves paragraph and span tags', () => {
    const dirty = '<p>paragraph</p><span>span</span>';
    const clean = sanitize(dirty);
    expect(clean).toContain('<p>paragraph</p>');
    expect(clean).toContain('<span>span</span>');
  });

  it('returns empty string for null or undefined input', () => {
    expect(sanitize(null)).toBe('');
    expect(sanitize(undefined)).toBe('');
    expect(sanitize('')).toBe('');
  });
});
```

- [ ] **Step 3: Run the test to confirm it fails**

```bash
cd frontend && npx vitest run tests/unit/utils/sanitize.spec.js
```

Expected: FAIL. Error message references the missing import `@/utils/sanitize`.

- [ ] **Step 4: Create the sanitize utility**

Create `frontend/src/utils/sanitize.js`:

```javascript
/**
 * HTML sanitization wrapper around DOMPurify.
 *
 * Used before passing any user-authored or markdown-rendered HTML into
 * Vue's v-html directive. Never render untrusted HTML without passing
 * it through this function first.
 *
 * Config notes:
 * - ALLOWED_TAGS covers the tags produced by renderMarkdown() helpers in
 *   FAQ.vue and About.vue (strong, em, a, p, span, br, ul, ol, li).
 * - ALLOWED_ATTR is limited to href, title, target, rel on anchors.
 * - ALLOW_DATA_ATTR is false to prevent data-* event binding abuse.
 * - FORBID_ATTR explicitly blocks event handler attributes even if a
 *   future config change widens ALLOWED_ATTR.
 */
import DOMPurify from 'dompurify';

const ALLOWED_TAGS = [
  'strong',
  'em',
  'b',
  'i',
  'a',
  'p',
  'span',
  'br',
  'ul',
  'ol',
  'li',
  'code',
];

const ALLOWED_ATTR = ['href', 'title', 'target', 'rel'];

const FORBID_ATTR = [
  'onerror',
  'onload',
  'onclick',
  'onmouseover',
  'onfocus',
  'onblur',
  'onsubmit',
  'onchange',
];

/**
 * Sanitize an HTML string for safe use with v-html.
 *
 * @param {string | null | undefined} html - Raw HTML string.
 * @returns {string} Sanitized HTML, or empty string for null/undefined.
 */
export function sanitize(html) {
  if (html == null || html === '') {
    return '';
  }
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    FORBID_ATTR,
    ALLOW_DATA_ATTR: false,
  });
}
```

- [ ] **Step 5: Run the test to confirm it passes**

```bash
cd frontend && npx vitest run tests/unit/utils/sanitize.spec.js
```

Expected: PASS, 6 tests passing.

- [ ] **Step 6: Run frontend lint and full test suite**

```bash
cd frontend && make check
```

Expected: all green. No new ESLint warnings. Prettier clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/utils/sanitize.js frontend/tests/unit/utils/sanitize.spec.js
git commit -m "$(cat <<'EOF'
feat(frontend): add DOMPurify-based sanitize utility

Introduces frontend/src/utils/sanitize.js wrapping DOMPurify with a
hardened config for use with v-html. Tag whitelist covers the subset
emitted by the existing markdown renderers in FAQ.vue and About.vue.
Event handler attributes and javascript: URLs are stripped.

Companion unit tests verify script removal, event-handler stripping,
javascript: URL blocking, and preservation of markdown-friendly tags.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Apply sanitize() to FAQ.vue and About.vue v-html call sites

**Files:**
- Modify: `frontend/src/views/FAQ.vue` (5 `v-html` sites)
- Modify: `frontend/src/views/About.vue` (3 `v-html` sites)
- Create: `frontend/tests/unit/views/FAQ.spec.js`

This task is an XSS fix. Test-first: write a characterization test that injects malicious markdown and asserts the rendered DOM contains no `<script>`.

- [ ] **Step 1: Write the failing XSS test for FAQ.vue**

Create `frontend/tests/unit/views/FAQ.spec.js`:

```javascript
/**
 * Characterization test for FAQ.vue XSS resistance.
 *
 * Does not mount the full component (it fetches remote content
 * asynchronously). Instead tests the renderMarkdown + sanitize pipeline
 * directly by exercising the same transformation chain FAQ.vue uses.
 */
import { describe, it, expect } from 'vitest';
import { sanitize } from '@/utils/sanitize';

// Mirror the renderMarkdown function from FAQ.vue so tests stay focused
// on the sanitize integration without requiring component mount.
const renderMarkdown = (text) => {
  if (!text) return '';
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank">$1</a>');
};

describe('FAQ rendering pipeline (renderMarkdown + sanitize)', () => {
  it('strips injected <script> tags from markdown', () => {
    const input = 'Hello <script>alert("xss")</script> world';
    const output = sanitize(renderMarkdown(input));
    expect(output).not.toContain('<script>');
    expect(output).not.toContain('alert');
  });

  it('renders bold and italic markdown safely', () => {
    const input = '**bold** and *italic*';
    const output = sanitize(renderMarkdown(input));
    expect(output).toContain('<strong>bold</strong>');
    expect(output).toContain('<em>italic</em>');
  });

  it('renders safe external links with target blank', () => {
    const input = '[GA4GH](https://www.ga4gh.org)';
    const output = sanitize(renderMarkdown(input));
    expect(output).toContain('href="https://www.ga4gh.org"');
    expect(output).toContain('target="_blank"');
  });

  it('strips javascript: URLs in markdown links', () => {
    const input = '[evil](javascript:alert(1))';
    const output = sanitize(renderMarkdown(input));
    expect(output).not.toContain('javascript:');
  });

  it('strips HTML event handlers even if injected raw', () => {
    const input = '<a href="https://x.test" onclick="alert(1)">x</a>';
    const output = sanitize(input);
    expect(output).not.toContain('onclick');
  });
});
```

- [ ] **Step 2: Run the test to confirm it passes**

The sanitize utility from Task 1 already handles all these cases, so the test should pass on first run.

```bash
cd frontend && npx vitest run tests/unit/views/FAQ.spec.js
```

Expected: PASS, 5 tests passing.

- [ ] **Step 3: Wire sanitize() into FAQ.vue**

Open `frontend/src/views/FAQ.vue`. Add the import near the other script imports at the top of the `<script setup>` block:

```javascript
import { sanitize } from '@/utils/sanitize';
```

Then modify the `renderMarkdown` function (around line 251) to pipe through sanitize. Change:

```javascript
const renderMarkdown = (text) => {
  if (!text) return '';
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank">$1</a>');
};
```

to:

```javascript
const renderMarkdown = (text) => {
  if (!text) return '';
  const rendered = text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank">$1</a>');
  return sanitize(rendered);
};
```

No template changes needed — the existing `v-html="renderMarkdown(...)"` call sites (lines 56, 64, 73, 139, 177) now receive sanitized output automatically.

- [ ] **Step 4: Wire sanitize() into About.vue**

Open `frontend/src/views/About.vue`. Add the import near the other script imports at the top of the `<script setup>` block:

```javascript
import { sanitize } from '@/utils/sanitize';
```

Find the `renderMarkdown` function (should be similar in shape to FAQ.vue). Apply the same wrap: the function's return statement becomes `return sanitize(rendered)`.

Also check the `formatCitation` function called by `v-html="formatCitation(...)"` on line 131. If it returns HTML, wrap its return in `sanitize()` the same way. If it returns plain text, leave it alone.

- [ ] **Step 5: Run tests to confirm everything still passes**

```bash
cd frontend && npx vitest run tests/unit/views/FAQ.spec.js tests/unit/utils/sanitize.spec.js
```

Expected: both test files pass (5 + 6 = 11 tests).

- [ ] **Step 6: Manual smoke test (optional but recommended)**

```bash
cd frontend && npm run dev
```

Navigate to http://localhost:5173/about and http://localhost:5173/faq in a browser. Confirm pages render and markdown formatting (bold, italic, links) still appears correctly. Kill the dev server when done.

- [ ] **Step 7: Run full frontend check and commit**

```bash
cd frontend && make check
```

Expected: all green.

```bash
git add frontend/src/views/FAQ.vue frontend/src/views/About.vue frontend/tests/unit/views/FAQ.spec.js
git commit -m "$(cat <<'EOF'
fix(frontend): sanitize markdown output in FAQ.vue and About.vue

Wraps the existing renderMarkdown helpers through the new sanitize()
utility before returning, eliminating the XSS vector where malicious
HTML in remote markdown content could execute via v-html. All 8
existing v-html call sites are covered transparently through the
helper.

Closes the P1 #1 XSS finding from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Require ADMIN_PASSWORD env var with startup validation

**Files:**
- Modify: `backend/app/core/config.py` (remove default, add validator)
- Modify: `backend/.env.example` (remove real-looking password)
- Modify: `backend/.env` (local dev file, replace with placeholder or real value from user)
- Create: `backend/tests/test_admin_password_required.py`

This task mirrors the existing `JWT_SECRET` validation pattern at `backend/app/core/config.py:301-320`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_admin_password_required.py`:

```python
"""Tests for ADMIN_PASSWORD startup validation.

Mirrors the JWT_SECRET validation pattern: the application must fail
fast on startup if ADMIN_PASSWORD is empty or unset, rather than silently
running with the historical default that leaked in git history.
"""

import os

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_admin_password_required_raises_when_empty(monkeypatch):
    """Empty ADMIN_PASSWORD must raise ValidationError at Settings init."""
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    monkeypatch.setenv("JWT_SECRET", "0" * 64)  # satisfy sibling validator
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5433/test"
    )

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    errors = exc_info.value.errors()
    password_errors = [e for e in errors if "ADMIN_PASSWORD" in str(e)]
    assert len(password_errors) >= 1, (
        f"Expected ADMIN_PASSWORD error, got errors: {errors}"
    )


def test_admin_password_accepts_non_empty_value(monkeypatch):
    """A non-empty ADMIN_PASSWORD must allow Settings to construct."""
    monkeypatch.setenv("ADMIN_PASSWORD", "SomeStrongPassword!2026")
    monkeypatch.setenv("JWT_SECRET", "0" * 64)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5433/test"
    )

    settings = Settings(_env_file=None)
    assert settings.ADMIN_PASSWORD == "SomeStrongPassword!2026"
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
cd backend && uv run pytest tests/test_admin_password_required.py -v
```

Expected: FAIL. The empty-string test passes trivially because the default is currently set to a non-empty value. The test file's first assertion will fail because `Settings(_env_file=None)` does not raise when `ADMIN_PASSWORD=""` is set — it uses the hardcoded default instead.

Actually: because `monkeypatch.setenv("ADMIN_PASSWORD", "")` sets the env var to empty string, pydantic-settings will pass that to the field. Since the field has `str = "ChangeMe!Admin2025"`, it will accept the empty string (the default is only used if the env var is unset). But there is no validator to reject empty, so `Settings` constructs successfully. The test fails because no exception is raised.

If instead the test fails with "Settings accepts empty password", that's the correct failing signal.

- [ ] **Step 3: Modify config.py to require ADMIN_PASSWORD**

Open `backend/app/core/config.py`. Find lines 277-286. Replace the current `ADMIN_PASSWORD` block:

```python
# Admin credentials (for initial setup)
# SECURITY NOTE: These are default credentials for initial database setup only.
# The default password MUST be changed immediately after first login in production.
# Override these values in .env for production deployments:
#   ADMIN_USERNAME=your_admin_user
#   ADMIN_EMAIL=admin@yourdomain.com
#   ADMIN_PASSWORD=<strong-unique-password>
ADMIN_USERNAME: str = "admin"
ADMIN_EMAIL: str = "admin@hnf1b-db.local"
ADMIN_PASSWORD: str = "ChangeMe!Admin2025"
```

with:

```python
# Admin credentials (for initial setup)
# SECURITY: ADMIN_PASSWORD is REQUIRED and has no default. The previous
# default was removed in Wave 1 of the 2026-04-10 refactor roadmap to
# prevent credential leakage via git history. The application exits at
# startup if ADMIN_PASSWORD is unset or empty.
ADMIN_USERNAME: str = "admin"
ADMIN_EMAIL: str = "admin@hnf1b-db.local"
ADMIN_PASSWORD: str = Field(default="")
```

Now find the `validate_jwt_secret` method at lines 301-320. Immediately after it, add a sibling validator for `ADMIN_PASSWORD`:

```python
@field_validator("ADMIN_PASSWORD")
@classmethod
def validate_admin_password(cls, v: str) -> str:
    """Fail fast if ADMIN_PASSWORD is missing.

    Mirrors the JWT_SECRET validation pattern. ADMIN_PASSWORD must be
    set via the .env file for initial admin-user creation. The previous
    hardcoded default was removed to prevent credential leakage.
    """
    if not v or v.strip() == "":
        logger.critical(
            "ADMIN_PASSWORD is empty or not set! "
            "Set ADMIN_PASSWORD in .env file for initial admin user "
            "creation. This credential is required and has no default."
        )
        raise ValueError(
            "ADMIN_PASSWORD is required. Set ADMIN_PASSWORD in .env file "
            "to a strong unique password (min 12 characters recommended)."
        )
    return v
```

- [ ] **Step 4: Update backend/.env.example**

Open `backend/.env.example`. Find the line:

```
ADMIN_PASSWORD=ChangeMe!Admin2025
```

Replace with:

```
# ADMIN_PASSWORD is REQUIRED. Set to a strong unique password.
# The application will exit at startup if this variable is unset or empty.
# Recommended: generate with `openssl rand -base64 32`
ADMIN_PASSWORD=
```

- [ ] **Step 5: Update backend/.env for local dev**

Open `backend/.env`. If it contains the literal string `ChangeMe!Admin2025`, replace with a locally-generated password. Either:

```bash
cd backend && python -c "import secrets; print(f'ADMIN_PASSWORD={secrets.token_urlsafe(24)}')" >> .env
# Then manually remove the old ADMIN_PASSWORD line
```

Or just manually set a known password for your dev environment. **Do not commit `.env`** — it is gitignored.

- [ ] **Step 6: Run the admin password tests**

```bash
cd backend && uv run pytest tests/test_admin_password_required.py -v
```

Expected: PASS, 2 tests.

- [ ] **Step 7: Run the full backend test suite to catch regressions**

```bash
cd backend && make check
```

Expected: all green. If any existing tests break because they construct `Settings()` without setting `ADMIN_PASSWORD`, update those tests to inject an `ADMIN_PASSWORD` env var via `monkeypatch` in a fixture — do not revert the validator. If more than 3 tests break, stop and report before continuing.

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/config.py backend/.env.example backend/tests/test_admin_password_required.py
git commit -m "$(cat <<'EOF'
fix(backend): require ADMIN_PASSWORD env var at startup

Removes the hardcoded "ChangeMe!Admin2025" default and adds a
field_validator mirroring the existing JWT_SECRET pattern. The
application now fails fast with a clear error message if
ADMIN_PASSWORD is unset or empty at startup.

Closes the P1 #2 hardcoded-credential finding from the 2026-04-09
review. Companion scrubbing of the string from remaining active files
happens in task 4.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Scrub `ChangeMe!Admin2025` from active files

**Files (edit):**
- `CLAUDE.md:528`
- `.planning/codebase/INTEGRATIONS.md:209`
- `.planning/codebase/CONCERNS.md:75` (reword to past tense)
- `plan/01-active/README.md:388`
- `plan/01-active/refactoring_optimization_plan.md:280`

**Files (explicitly NOT edited):**
- `docs/issues/IMPLEMENTATION-issue-61-user-auth-REVISED.md` — historical implementation record
- `docs/reviews/codebase-best-practices-review-2026-04-09.md` — source review, intentionally references the string as a finding
- `docs/superpowers/specs/2026-04-10-codebase-refactor-roadmap-design.md` — this roadmap, intentionally references the string

**No test needed** — this is a documentation scrub. Verification uses grep before commit.

- [ ] **Step 1: Edit CLAUDE.md line 528**

Find the line in `CLAUDE.md`:

```
ADMIN_PASSWORD=ChangeMe!Admin2025
```

Replace with:

```
ADMIN_PASSWORD=<required; generate with: openssl rand -base64 32>
```

- [ ] **Step 2: Edit .planning/codebase/INTEGRATIONS.md line 209**

Find the line:

```
ADMIN_PASSWORD=ChangeMe!Admin2025
```

Replace with:

```
ADMIN_PASSWORD=<required; no default>
```

- [ ] **Step 3: Update .planning/codebase/CONCERNS.md line 75**

Find the paragraph around line 75 that reads:

```
- Risk: Default password `ChangeMe!Admin2025` documented in `.env.example` and CLAUDE.md
```

Replace with:

```
- Risk: Default password was previously hardcoded and documented in `.env.example` and CLAUDE.md. **RESOLVED 2026-04-10**: ADMIN_PASSWORD is now required at startup via Settings validator (mirrors JWT_SECRET pattern).
```

- [ ] **Step 4: Edit plan/01-active/README.md line 388**

Find:

```
ADMIN_PASSWORD=ChangeMe!Admin2025
```

Replace with:

```
ADMIN_PASSWORD=<required; set via .env, no default>
```

- [ ] **Step 5: Edit plan/01-active/refactoring_optimization_plan.md line 280**

Read the surrounding context first:

```bash
sed -n '275,285p' plan/01-active/refactoring_optimization_plan.md
```

The line contains a Python check like `if env == "production" and password == "ChangeMe!Admin2025":`. Since that plan is superseded by this Wave 1 work, replace the hardcoded string with a placeholder reference:

```python
if env == "production" and password == "<removed-in-wave-1>":
```

Or if simpler, just change `"ChangeMe!Admin2025"` to `"CHANGE_ME_PLACEHOLDER"` and add a comment above noting Wave 1 removed the real value.

- [ ] **Step 6: Verify the scrub**

```bash
grep -rn "ChangeMe!Admin2025" . \
  --include="*.py" --include="*.md" --include="*.yml" \
  --include="*.yaml" --include="*.example" \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv
```

Expected output: exactly 3 matches, all in the explicitly-retained files:
- `docs/issues/IMPLEMENTATION-issue-61-user-auth-REVISED.md`
- `docs/reviews/codebase-best-practices-review-2026-04-09.md`
- `docs/superpowers/specs/2026-04-10-codebase-refactor-roadmap-design.md`

If any other file still contains the string, go back and fix it before committing.

- [ ] **Step 7: Commit**

```bash
git add CLAUDE.md .planning/codebase/INTEGRATIONS.md .planning/codebase/CONCERNS.md plan/01-active/README.md plan/01-active/refactoring_optimization_plan.md
git commit -m "$(cat <<'EOF'
docs: scrub ChangeMe!Admin2025 from active documentation

Removes the hardcoded admin password placeholder from CLAUDE.md,
planning docs, and the refactoring plan following task 3's startup
validator. Historical implementation records, the source security
review, and the Wave 1 roadmap spec deliberately retain the string
as historical reference.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Fix bare `except Exception:` in variant_validator.py (7 sites)

**Files:**
- Modify: `backend/app/phenopackets/validation/variant_validator.py` (lines 77, 500, 737, 790, 960)
- Test: rely on the existing 1,660-line `backend/tests/test_variant_validator_enhanced.py`

This task handles all 7 bare-except sites in a single file because they share the same context (variant parsing/validation). Each site catches HGVS/VCF/SPDI parsing failures; the replacement catches the specific exception classes those parsers raise.

- [ ] **Step 1: Read the existing test file to understand coverage**

```bash
cd backend && grep -n "def test_" tests/test_variant_validator_enhanced.py | head -30
```

Identify which tests exercise the 5 catch sites. The tests are the safety net — you don't need to add new ones unless a specific catch site has no coverage. If coverage is thin at a specific site, add one targeted test there before modifying the catch.

- [ ] **Step 2: Read the context around line 77**

```bash
sed -n '50,85p' backend/app/phenopackets/validation/variant_validator.py
```

The catch at line 77 wraps an `httpx.AsyncClient` POST to the VEP API. The actual exceptions that can be raised are `httpx.HTTPError`, `httpx.TimeoutException`, `httpx.RequestError`, `json.JSONDecodeError`, and `ValueError` (if VEP returns garbage).

Replace:

```python
        except Exception:
            return self._fallback_validation(hgvs_notation), None, []
```

with:

```python
        except (
            httpx.HTTPError,
            httpx.TimeoutException,
            httpx.RequestError,
            json.JSONDecodeError,
            ValueError,
        ) as e:
            logger.debug(
                "VEP validation request failed, falling back to local validation: %s",
                e,
            )
            return self._fallback_validation(hgvs_notation), None, []
```

Make sure `import json` and `import logging` are at the top of the file (and `logger = logging.getLogger(__name__)` exists). If `logger` is not defined in the module, add it near the imports:

```python
import logging

logger = logging.getLogger(__name__)
```

- [ ] **Step 3: Read and fix the context around line 500**

```bash
sed -n '480,510p' backend/app/phenopackets/validation/variant_validator.py
```

Inspect what code the `try:` block wraps. Identify the actual exceptions (likely `KeyError`, `ValueError`, `IndexError`, `AttributeError`, or specific parser exceptions). Replace the `except Exception as e:` with the specific tuple, keeping the existing `e` variable and log message intact.

**Pattern to follow:** do not silently swallow the exception. Always log at `logger.warning` or `logger.debug` with the exception and at least one piece of context (the variant being parsed, the input text, etc.).

If the actual exception types are unclear, replace `except Exception as e:` with `except (ValueError, KeyError, AttributeError) as e:` as a safe minimum, and add a comment:

```python
# TODO: narrow this further if specific exception types surface during testing
```

- [ ] **Step 4: Repeat for lines 737, 790, and 960**

For each: read surrounding 20 lines, identify actual exceptions, replace. If two adjacent sites have identical patterns, you can fix them together.

- [ ] **Step 5: Run the variant_validator test suite**

```bash
cd backend && uv run pytest tests/test_variant_validator_enhanced.py -v
```

Expected: all ~100+ tests pass. If any fail, inspect the failure: if it's because an exception is now reaching a higher level (meaning the bare catch was masking a real bug), that's valuable new information — fix the actual bug. If it's a test relying on the old swallow behavior, update the test to use `pytest.raises`.

- [ ] **Step 6: Run backend lint and type check**

```bash
cd backend && make lint && make typecheck
```

Expected: all green. Mypy may complain if the new exception types aren't imported; fix those.

- [ ] **Step 7: Commit**

```bash
git add backend/app/phenopackets/validation/variant_validator.py
git commit -m "$(cat <<'EOF'
fix(backend): replace bare except Exception in variant_validator

Replaces 5 bare-except clauses in variant_validator.py with specific
exception tuples. Each catch now logs the suppressed exception at
debug level with variant context, preventing silent failures from
masking parser bugs.

Part of the P1 #3 bare-exception sweep from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Fix bare `except Exception:` in variant_search_validation.py

**Files:**
- Modify: `backend/app/phenopackets/variant_search_validation.py` (line 80)

- [ ] **Step 1: Read the context**

```bash
sed -n '70,95p' backend/app/phenopackets/variant_search_validation.py
```

- [ ] **Step 2: Replace the bare except with specific exceptions**

Identify what the `try` block does (likely string parsing or regex matching). Replace:

```python
            except Exception:
                # existing handler
```

with a specific tuple. For regex/string parsing, typical candidates are `re.error`, `ValueError`, `TypeError`, `IndexError`. Add a `logger.debug` call before the existing handler to surface the suppressed exception.

- [ ] **Step 3: Run tests**

```bash
cd backend && uv run pytest tests/ -k "variant_search" -v
```

Expected: all green.

- [ ] **Step 4: Run backend checks**

```bash
cd backend && make check
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/phenopackets/variant_search_validation.py
git commit -m "$(cat <<'EOF'
fix(backend): replace bare except in variant_search_validation

Narrows the bare exception catch at line 80 to specific parser
exception types with debug logging.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Fix bare `except Exception:` in database.py (3 sites)

**Files:**
- Modify: `backend/app/database.py` (lines 84, 132, 197)

- [ ] **Step 1: Read each site**

```bash
sed -n '75,95p' backend/app/database.py
sed -n '125,140p' backend/app/database.py
sed -n '190,205p' backend/app/database.py
```

Identify what each catches:
- Line 84: likely wraps an import or initial connection attempt.
- Line 132 (`except Exception as e:`): likely SQLAlchemy error path.
- Line 197 (`except Exception as e:`): likely SQLAlchemy error path.

The SQLAlchemy-specific exceptions are `sqlalchemy.exc.SQLAlchemyError` (base class) and its subclasses (`OperationalError`, `IntegrityError`, `DBAPIError`, etc.).

- [ ] **Step 2: Fix line 84**

If it wraps a startup probe, replace with the actual failure modes (likely `asyncpg.exceptions.ConnectionFailureError`, `sqlalchemy.exc.OperationalError`, `ConnectionRefusedError`, `OSError`).

- [ ] **Step 3: Fix lines 132 and 197**

Replace `except Exception as e:` with `except sqlalchemy.exc.SQLAlchemyError as e:` where the caller is inside an async with block. Keep existing logging intact. Add `import sqlalchemy.exc` at the top of the file if not already present.

- [ ] **Step 4: Run database-related tests**

```bash
cd backend && uv run pytest tests/test_transaction_management.py tests/test_database_health.py -v 2>/dev/null || uv run pytest tests/ -k "database" -v
```

Expected: all green.

- [ ] **Step 5: Run backend checks**

```bash
cd backend && make check
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/database.py
git commit -m "$(cat <<'EOF'
fix(backend): replace bare except in database.py

Narrows 3 bare exception catches (lines 84, 132, 197) to SQLAlchemy
and connection-specific exception types with retained logging.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Fix bare `except Exception:` in phenopackets/routers/crud.py (4 sites)

**Files:**
- Modify: `backend/app/phenopackets/routers/crud.py` (lines 348, 459, 532, 817)

- [ ] **Step 1: Read each site**

```bash
cd backend && for ln in 348 459 532 817; do
  echo "=== Line $ln ===";
  sed -n "$((ln-10)),$((ln+10))p" app/phenopackets/routers/crud.py;
done
```

- [ ] **Step 2: Fix each site**

Each `except Exception as e:` in `crud.py` likely wraps a DB operation or JSON patch/audit operation. Typical narrowing:

- For DB ops: `sqlalchemy.exc.SQLAlchemyError`
- For JSON patch: `jsonpatch.JsonPatchException`, `json.JSONDecodeError`
- For Pydantic validation: `pydantic.ValidationError`

Keep existing `HTTPException` raises intact — those are the intended error responses.

- [ ] **Step 3: Run CRUD-related tests**

```bash
cd backend && uv run pytest tests/test_phenopackets_crud.py tests/test_audit_logging.py -v 2>/dev/null || uv run pytest tests/ -k "crud or audit" -v
```

Expected: all green.

- [ ] **Step 4: Run backend checks**

```bash
cd backend && make check
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/phenopackets/routers/crud.py
git commit -m "$(cat <<'EOF'
fix(backend): replace bare except in phenopackets/routers/crud.py

Narrows 4 bare exception catches in crud.py to SQLAlchemy, Pydantic,
and jsonpatch exception types while preserving the HTTPException raise
paths.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Fix bare `except Exception:` in api/admin_endpoints.py (6 sites)

**Files:**
- Modify: `backend/app/api/admin_endpoints.py` (lines 329, 349, 589, 609, 896, 929)

- [ ] **Step 1: Read each site**

```bash
cd backend && for ln in 329 349 589 609 896 929; do
  echo "=== Line $ln ===";
  sed -n "$((ln-8)),$((ln+8))p" app/api/admin_endpoints.py;
done
```

- [ ] **Step 2: Fix each site**

`admin_endpoints.py` is scheduled for full decomposition in Wave 4; the goal here is surgical narrowing only, not restructuring. Each catch wraps either a sync orchestration step, a Redis write, or a raw SQL execution. Typical narrowing:

- Sync operations: `aiohttp.ClientError`, `httpx.HTTPError`, `TimeoutError`
- Redis: `redis.exceptions.RedisError`
- Raw SQL: `sqlalchemy.exc.SQLAlchemyError`

If a catch site is genuinely load-bearing (swallowing errors is intentional for best-effort cleanup), leave the narrow replacement plus a comment:

```python
except (sqlalchemy.exc.SQLAlchemyError, Exception) as e:  # noqa: BLE001
    # Best-effort sync-status update; errors must not block the sync flow
    logger.warning("Sync status update failed: %s", e)
```

Only do this in 1 site max — the rest must be genuinely narrowed.

- [ ] **Step 3: Run admin-related tests**

```bash
cd backend && uv run pytest tests/ -k "admin" -v
```

Expected: all green.

- [ ] **Step 4: Run backend checks**

```bash
cd backend && make check
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/admin_endpoints.py
git commit -m "$(cat <<'EOF'
fix(backend): replace bare except in admin_endpoints.py

Narrows 6 bare exception catches in admin_endpoints.py to specific
exception types (aiohttp, Redis, SQLAlchemy). Full file decomposition
is scheduled for Wave 4; this task is surgical narrowing only.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Fix remaining bare excepts in production code

**Files:**
- Modify: `backend/app/hpo_proxy.py` (lines 111, 154, 208, 306)
- Modify: `backend/app/services/ontology_service.py` (lines 83, 150, 178)
- Modify: `backend/app/variants/service.py` (lines 292, 295)
- Modify: `backend/app/utils/audit_logger.py` (line 203)
- Modify: `backend/app/core/retry.py` (line 115 — **audit only, may legitimately stay**)
- Modify: `backend/app/core/mv_cache.py` (line 128)
- Modify: `backend/app/search/mv_refresh.py` (lines 41, 88)

- [ ] **Step 1: Audit core/retry.py**

```bash
sed -n '105,130p' backend/app/core/retry.py
```

A retry decorator catching `Exception` to trigger retry logic is a legitimate use. If this is the case, leave the catch but add `# noqa: BLE001` and a comment explaining why:

```python
except Exception as e:  # noqa: BLE001
    # Retry decorator: must catch all exceptions to handle arbitrary
    # caller failures. Narrowing here would prevent the decorator from
    # functioning as a generic retry wrapper.
    # ... existing logic
```

If this is the case, skip modifying retry.py — the noqa comment is the fix.

- [ ] **Step 2: Fix hpo_proxy.py (4 sites)**

All 4 sites wrap `httpx`/`aiohttp` calls or Redis cache reads. Narrow to:

```python
except (
    aiohttp.ClientError,
    asyncio.TimeoutError,
    redis.exceptions.RedisError,
    json.JSONDecodeError,
) as e:
```

Adjust based on what each specific site actually calls. Keep logging intact.

- [ ] **Step 3: Fix services/ontology_service.py (3 sites)**

Same pattern: HTTP client exceptions, JSON decode errors, Redis errors.

- [ ] **Step 4: Fix variants/service.py (2 sites)**

Lines 292 and 295 are in the VEP batch processing path. Narrow to the VEP exception hierarchy already defined in the same file (`VEPError`, `VEPRateLimitError`, `VEPAPIError`, `VEPNotFoundError`, `VEPTimeoutError`) plus generic HTTP client errors.

- [ ] **Step 5: Fix utils/audit_logger.py (1 site)**

Audit logging is best-effort; narrowing matters less here. Accept `(OSError, ValueError, TypeError)` as minimum and add logging at WARNING level instead of silently swallowing.

- [ ] **Step 6: Fix core/mv_cache.py (1 site)**

Narrow to `sqlalchemy.exc.SQLAlchemyError` and log at warning.

- [ ] **Step 7: Fix search/mv_refresh.py (2 sites)**

Narrow to `sqlalchemy.exc.SQLAlchemyError`. These wrap materialized view refresh operations.

- [ ] **Step 8: Run the full backend test suite**

```bash
cd backend && make check
```

Expected: all green. If any test fails, the failing case likely relied on a bare catch masking a real issue — investigate before moving on.

- [ ] **Step 9: Verify no production bare-exceptions remain**

```bash
grep -rn "except Exception" backend/app/ --include="*.py" | grep -v "# noqa"
```

Expected output: zero lines. If any remain, fix them or add an explicit `# noqa: BLE001` with a justifying comment.

- [ ] **Step 10: Commit**

```bash
git add backend/app/hpo_proxy.py backend/app/services/ontology_service.py backend/app/variants/service.py backend/app/utils/audit_logger.py backend/app/core/retry.py backend/app/core/mv_cache.py backend/app/search/mv_refresh.py
git commit -m "$(cat <<'EOF'
fix(backend): replace remaining bare excepts in production code

Narrows all remaining bare exception catches in backend/app/ to
specific exception types:
- hpo_proxy.py: HTTP/Redis/JSON errors
- ontology_service.py: HTTP/Redis/JSON errors
- variants/service.py: VEP exception hierarchy
- audit_logger.py: OS/type errors with warning-level logging
- mv_cache.py, mv_refresh.py: SQLAlchemy errors
- core/retry.py: kept with noqa and explanatory comment (retry
  decorator must catch Exception by design)

Closes the P1 #3 bare-exception sweep from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Delete backup file and dead commented code

**Files:**
- Delete: `frontend/src/api/index.js.backup`
- Modify: `backend/app/database.py` (delete lines 100-115 dead comment block)

- [ ] **Step 1: Delete the backup file**

```bash
rm frontend/src/api/index.js.backup
```

- [ ] **Step 2: Remove dead code in database.py**

Open `backend/app/database.py`. Find the block around lines 100-115 that starts with `# DEAD CODE: models module does not exist` and ends with the `logger.info(...)` call about "skipping models import".

Replace the entire block:

```python
        async with engine.begin():
            # DEAD CODE: models module does not exist
            # Import all models to ensure they're registered with Base.metadata
            # This import is currently unused as we don't have an app/models.py module
            # TODO: Remove this code block or create app/models.py if needed
            # try:
            #     from app import models  # noqa: F401
            #
            #     logger.info("Models imported successfully")
            # except ImportError:
            #     logger.warning(
            #         "Models not found - this is expected during initial setup"
            #     )
            logger.info(
                "Database initialization - skipping models import "
                "(no models module exists)"
            )
```

with:

```python
        async with engine.begin():
            pass  # Models are registered via explicit imports in routers
```

If the surrounding function still has the `# Create all tables` commented block below, leave it alone — that's a separate documented pattern (Alembic-managed schema).

- [ ] **Step 3: Run backend tests**

```bash
cd backend && uv run pytest tests/ -k "database" -v
```

Expected: all green. The database initialization function should still work identically.

- [ ] **Step 4: Run backend checks**

```bash
cd backend && make check
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/index.js.backup backend/app/database.py
git commit -m "$(cat <<'EOF'
chore: remove dead code and committed backup file

- Deletes frontend/src/api/index.js.backup (committed accidentally)
- Removes the dead commented-out models-import block from database.py
  that has been marked with a TODO since the models module was
  removed

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Delete legacy frontend auth files

**Files:**
- Delete: `frontend/src/api/auth.js`
- Delete: `frontend/src/utils/auth.js`

Verified during Wave 1 planning: no other file imports from either of these — `grep -rn "utils/auth\|api/auth" frontend/src` returns only the files themselves. Safe to delete.

- [ ] **Step 1: Re-verify no imports**

```bash
cd frontend && grep -rn "from '@/utils/auth'\|from '@/api/auth'\|from \"@/utils/auth\"\|from \"@/api/auth\"\|require.*utils/auth\|require.*api/auth" src tests
```

Expected output: empty. If any match appears, stop and report — the legacy files are still in use and must be migrated before deletion.

- [ ] **Step 2: Delete the files**

```bash
rm frontend/src/api/auth.js frontend/src/utils/auth.js
```

- [ ] **Step 3: Run frontend checks**

```bash
cd frontend && make check
```

Expected: all green. ESLint should not report missing modules (nothing was importing them).

- [ ] **Step 4: Build the frontend to catch Vite import errors**

```bash
cd frontend && npm run build
```

Expected: build succeeds with no errors. This is a stronger check than ESLint because Vite resolves imports at build time.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/auth.js frontend/src/utils/auth.js
git commit -m "$(cat <<'EOF'
chore(frontend): delete legacy auth helper files

Removes frontend/src/api/auth.js and frontend/src/utils/auth.js. Both
files were superseded by stores/authStore.js but left in place. Grep
confirms no remaining imports.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Delete dead `backend/app/utils.py` and `backend/app/schemas.py`

**Files:**
- Delete: `backend/app/utils.py` (266 LOC, unused filter-parsing helpers)
- Delete: `backend/app/schemas.py` (300 LOC, unused Pydantic schemas)

Verified during Wave 1 planning: no module imports from either of these files. All `from app.utils.*` imports go through the `backend/app/utils/` package; all `from app.schemas.*` imports go through the `backend/app/schemas/` package. The two orphan `.py` files are dead code creating namespace ambiguity.

- [ ] **Step 1: Re-verify no imports from the orphan files**

```bash
cd backend && grep -rn "parse_filter_json\|parse_deep_object_filters" app tests migration --include="*.py"
```

Expected: only matches inside `app/utils.py` itself (the definitions).

```bash
cd backend && grep -rn "class BaseSchema\|IndividualResponse\|VariantAnnotationSchema" app tests migration --include="*.py"
```

Expected: only matches inside `app/schemas.py` itself (the definitions).

- [ ] **Step 2: Delete the files**

```bash
rm backend/app/utils.py backend/app/schemas.py
```

- [ ] **Step 3: Run backend tests**

```bash
cd backend && make check
```

Expected: all green. If anything breaks, a hidden import was missed during grep — investigate and restore if necessary.

- [ ] **Step 4: Commit**

```bash
git add backend/app/utils.py backend/app/schemas.py
git commit -m "$(cat <<'EOF'
chore(backend): delete dead app/utils.py and app/schemas.py

Both files contained orphaned code colliding with the app/utils/ and
app/schemas/ packages. Verified no imports target the .py variants:
all production imports go through the package forms (from
app.utils.audit_logger, from app.schemas.auth, etc.).

Closes the P4 #18 namespace collision finding from the 2026-04-09
review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Resolve Pydantic v2 deprecation warnings

**Files:**
- Modify: `backend/app/phenopackets/models.py` (lines 432, 472 — `class Config:` → `model_config`)
- Modify: `backend/app/reference/schemas.py` (lines 28, 47, 71, 95, 128 — same treatment)

Pydantic v2 deprecated the inner `class Config:` pattern in favor of `model_config = ConfigDict(...)`. Both styles still work in Pydantic 2.x, but emit deprecation warnings.

- [ ] **Step 1: Capture the current deprecation warnings**

```bash
cd backend && uv run pytest tests/ -W error::DeprecationWarning 2>&1 | grep -i "pydantic\|class Config" | head -20
```

This lists every location emitting a Pydantic deprecation warning. Should match the 7 `class Config:` sites above plus any others.

- [ ] **Step 2: Fix phenopackets/models.py line 432**

Open the file and find:

```python
class PhenopacketResponse(BaseModel):
    # ... fields ...

    class Config:
        """Pydantic config for ORM mode."""

        from_attributes = True
```

Replace the inner class with:

```python
class PhenopacketResponse(BaseModel):
    # ... fields ...

    model_config = ConfigDict(from_attributes=True)
```

Add the import at the top of the file:

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator
```

- [ ] **Step 3: Fix phenopackets/models.py line 472**

Same pattern — replace the inner `class Config:` on `PhenopacketAuditResponse` with `model_config = ConfigDict(from_attributes=True)`.

- [ ] **Step 4: Fix reference/schemas.py (5 sites)**

Open `backend/app/reference/schemas.py`. For each `class Config:` block (lines 28, 47, 71, 95, 128), apply the same treatment:

- Replace the inner class with `model_config = ConfigDict(from_attributes=True)` (or whatever attributes the original Config class set).
- Add the `ConfigDict` import at the top.

- [ ] **Step 5: Run tests to confirm no regressions**

```bash
cd backend && make check
```

Expected: all green.

- [ ] **Step 6: Confirm the warnings are gone**

```bash
cd backend && uv run pytest tests/ -W error::DeprecationWarning 2>&1 | grep -i "class Config"
```

Expected: zero matches related to `class Config` in `app/phenopackets/models.py` or `app/reference/schemas.py`. (Other unrelated deprecations may still exist; those are out of scope.)

- [ ] **Step 7: Commit**

```bash
git add backend/app/phenopackets/models.py backend/app/reference/schemas.py
git commit -m "$(cat <<'EOF'
chore(backend): migrate Pydantic v1 Config to v2 ConfigDict

Replaces 7 inner 'class Config:' declarations with
'model_config = ConfigDict(...)' to resolve Pydantic v2 deprecation
warnings in phenopackets/models.py and reference/schemas.py.

Closes P4 #20 from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Wave 1 exit verification

**No files modified.** This task is the end-of-wave checkpoint. Run every verification command and confirm every acceptance criterion from the spec. Fix any gaps before declaring Wave 1 done.

- [ ] **Step 1: Run both `make check` suites**

```bash
cd backend && make check && cd ../frontend && make check
```

Expected: both green. If either fails, fix the issue in a new targeted commit.

- [ ] **Step 2: Verify XSS fix**

```bash
cd frontend && npx vitest run tests/unit/views/FAQ.spec.js tests/unit/utils/sanitize.spec.js
```

Expected: all 11 tests pass.

- [ ] **Step 3: Verify ADMIN_PASSWORD validator**

```bash
cd backend && uv run pytest tests/test_admin_password_required.py -v
```

Expected: 2 tests pass. Manually confirm by unsetting the env var and starting the app:

```bash
cd backend && (unset ADMIN_PASSWORD && uv run python -c "from app.core.config import Settings; Settings()")
```

Expected: raises `ValidationError` with a clear message about ADMIN_PASSWORD being required.

- [ ] **Step 4: Verify ChangeMe scrub**

```bash
grep -rn "ChangeMe!Admin2025" . \
  --include="*.py" --include="*.md" --include="*.yml" \
  --include="*.yaml" --include="*.example" \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv
```

Expected: exactly 3 matches, all in the 3 retained historical files:
- `docs/issues/IMPLEMENTATION-issue-61-user-auth-REVISED.md`
- `docs/reviews/codebase-best-practices-review-2026-04-09.md`
- `docs/superpowers/specs/2026-04-10-codebase-refactor-roadmap-design.md`

- [ ] **Step 5: Verify no production bare excepts**

```bash
grep -rn "except Exception" backend/app/ --include="*.py" | grep -v "# noqa"
```

Expected: zero matches. If any remain, either fix them or add an explicit `# noqa: BLE001` with a justification comment.

- [ ] **Step 6: Verify dead files gone**

```bash
find . \( -name "*.backup" -o -name "index.js.backup" \) \
  -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/.venv/*"
```

Expected: empty.

```bash
ls frontend/src/api/auth.js frontend/src/utils/auth.js backend/app/utils.py backend/app/schemas.py 2>&1
```

Expected: all 4 files report "No such file or directory".

- [ ] **Step 7: Verify Pydantic deprecation warnings gone**

```bash
cd backend && uv run pytest tests/ -W error::DeprecationWarning 2>&1 | grep -c "class Config"
```

Expected: `0`.

- [ ] **Step 8: Count tests to confirm additions**

```bash
cd backend && uv run pytest tests/ --collect-only -q 2>&1 | tail -5
```

Expected: ~750 tests (up from 747).

```bash
cd frontend && find tests -type f \( -name "*.spec.js" -o -name "*.test.js" \) | wc -l
```

Expected: 11 files (up from 10).

- [ ] **Step 9: Write the wave-exit note**

Create `docs/refactor/wave-1-exit.md`:

```markdown
# Wave 1 Exit Note

**Date:** <YYYY-MM-DD when executed>
**Starting test counts:** backend 747, frontend 10 spec files.
**Ending test counts:** backend ~750, frontend 11 spec files.

## What landed

- Task 1: DOMPurify installed; sanitize utility created with 6 unit tests.
- Task 2: v-html sites in FAQ.vue and About.vue piped through sanitize().
- Task 3: ADMIN_PASSWORD field_validator added; hardcoded default removed from config.py.
- Task 4: ChangeMe!Admin2025 scrubbed from 5 active files (3 historical files explicitly retained).
- Task 5: 5 bare excepts in variant_validator.py narrowed.
- Task 6: 1 bare except in variant_search_validation.py narrowed.
- Task 7: 3 bare excepts in database.py narrowed.
- Task 8: 4 bare excepts in phenopackets/routers/crud.py narrowed.
- Task 9: 6 bare excepts in admin_endpoints.py narrowed.
- Task 10: ~12 remaining bare excepts narrowed across hpo_proxy, ontology_service, variants/service, audit_logger, mv_cache, mv_refresh; core/retry.py retained with documented noqa.
- Task 11: Backup file deleted; dead code in database.py removed.
- Task 12: Legacy frontend auth files deleted.
- Task 13: Dead backend/app/utils.py and schemas.py deleted.
- Task 14: 7 Pydantic v1 Config classes migrated to ConfigDict.

## What was deferred

<fill in if anything — expected: nothing>

## What surprised us

<fill in during execution — e.g., "database.py line 84 was actually a legitimate broad catch, noqa'd instead">

## Entry conditions for Wave 2

- All Wave 1 exit checks green.
- No bare `except Exception:` in `backend/app/` (test fixtures still have some — those are addressed in Wave 2).
- Sanitize utility in place and documented as the only safe way to use v-html.
- ADMIN_PASSWORD startup validator proven via test.

Wave 2 can begin.
```

- [ ] **Step 10: Commit the wave-exit note**

```bash
git add docs/refactor/wave-1-exit.md
git commit -m "$(cat <<'EOF'
docs: add Wave 1 exit note

Records what landed, what was deferred, and entry conditions for
Wave 2.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 11: Open the Wave 1 PR (optional, if pushing incrementally)**

```bash
git push -u origin chore/wave-1-stop-the-bleeding
gh pr create --title "Wave 1: Stop the Bleeding" --body "$(cat <<'EOF'
## Summary

Completes Wave 1 of the refactor roadmap
(`docs/superpowers/specs/2026-04-10-codebase-refactor-roadmap-design.md`).

- Fixes XSS in FAQ.vue and About.vue via DOMPurify sanitize utility
- Requires ADMIN_PASSWORD env var at startup (mirrors JWT_SECRET pattern)
- Scrubs hardcoded ChangeMe!Admin2025 from 5 active files
- Narrows ~30 bare except Exception clauses in backend/app/ production code
- Deletes dead code: backup file, legacy frontend auth files, orphaned backend utils.py and schemas.py
- Migrates 7 Pydantic v1 Config classes to v2 ConfigDict

## Test plan

- [x] Backend `make check` green
- [x] Frontend `make check` green
- [x] Sanitize + FAQ unit tests pass (11 tests)
- [x] ADMIN_PASSWORD validator tests pass (2 tests)
- [x] grep for `ChangeMe!Admin2025` returns only 3 historical files
- [x] grep for `except Exception` in `backend/app/` returns zero non-noqa matches
- [x] Frontend production build succeeds

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**Wave 1 is done when this plan's 15 tasks are all checked off, all verification commands pass, and the wave-exit note is committed.**

---

## Self-Review Notes (from plan author)

- **Spec coverage:** Every Wave 1 item from `docs/superpowers/specs/2026-04-10-codebase-refactor-roadmap-design.md` is covered: XSS (Tasks 1-2), ADMIN_PASSWORD required (Task 3), ChangeMe scrub (Task 4), bare excepts across ~10 sites in production code (Tasks 5-10), backup file + dead code (Task 11), legacy auth files (Task 12), namespace collisions via utils.py/schemas.py (Task 13), Pydantic v2 deprecations (Task 14), exit verification (Task 15).
- **No placeholders:** Every step has concrete code, exact commands, or specific file paths. The only `<fill in during execution>` placeholder is inside the wave-exit note template, which is intentional — the note is written when the wave is done, not during planning.
- **Type/name consistency:** `sanitize` function name and import path (`@/utils/sanitize`) used identically in Tasks 1, 2, and 15. `ADMIN_PASSWORD` and `validate_admin_password` used identically in Task 3 and Task 15. Pydantic `ConfigDict` and `model_config` used identically in Task 14.
- **No new concepts mid-plan:** All libraries referenced (DOMPurify, SQLAlchemy, Pydantic, httpx, redis, aiohttp) exist in the current dependency set verified during Wave 1 planning.
