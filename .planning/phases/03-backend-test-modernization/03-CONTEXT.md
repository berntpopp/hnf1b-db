# Phase 3: Backend Test Modernization - Context

**Gathered:** 2026-01-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Upgrade the backend test suite to modern pytest patterns. This includes async fixtures, consistent naming conventions, consolidated utilities, and coverage measurement. This phase does not add new features — it improves test infrastructure quality.

</domain>

<decisions>
## Implementation Decisions

### Test Naming Convention
- Pattern: `test_<feature>_<scenario>_<expected>` (e.g., `test_phenopacket_create_returns_201`)
- Enforcement: Guideline with flexibility — follow pattern, but exceptions allowed for clarity
- Scope: Rename all existing tests to match pattern during migration

### Fixture Organization
- Structure: Hierarchical conftest.py — root for common fixtures, subdirectory conftest.py for domain-specific
- Async mode: pytest-asyncio auto mode — auto-detect async fixtures
- Naming: Prefix fixtures with `fixture_` (e.g., `fixture_db_session`, `fixture_test_client`)
- Documentation: Docstrings only for complex fixtures, simple ones are self-explanatory

### Coverage Targets
- Minimum overall: 60% coverage across all backend code
- Per-file floor: No file below 40% coverage
- Exclusions: Exclude migrations (alembic/versions/) and config files (config.py, __init__.py)
- CI behavior: Report only, no enforcement — generate coverage report but don't fail build
- Report format: Terminal only, no HTML reports

### Migration Approach
- Strategy: Module by module — migrate one test module at a time, verify each
- Deprecated patterns: Remove immediately — delete deprecated unittest.mock usage, clean imports
- New tests: Yes, add tests where coverage gaps exist
- Utilities: Separate tests/utils.py for non-fixture helpers, fixtures stay in conftest.py

### Claude's Discretion
- Order of modules to migrate (based on complexity and dependencies)
- Specific pytest plugins to add (e.g., pytest-cov configuration)
- How to structure domain-specific conftest.py files
- Which specific deprecated patterns to replace with what

</decisions>

<specifics>
## Specific Ideas

- Research indicated community prefers `test_<feature>_<scenario>_<expected>` pattern — aligns with pytest documentation recommendations
- pytest-asyncio auto mode simplifies async fixture setup significantly

**Sources consulted:**
- [pytest documentation - Good Integration Practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)
- [TestDriven.io - GIVEN-WHEN-THEN naming](https://testdriven.io/tips/0f25ebb7-d5c1-4040-b78e-ac48e8f0a014/)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-backend-test-modernization*
*Context gathered: 2026-01-19*
