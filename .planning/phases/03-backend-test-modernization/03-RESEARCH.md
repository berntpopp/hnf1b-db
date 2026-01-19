# Phase 3: Backend Test Modernization - Research

**Researched:** 2026-01-19
**Domain:** pytest, pytest-asyncio, SQLAlchemy async testing, test coverage
**Confidence:** HIGH

## Summary

The backend test suite currently has 35 test files with approximately 748 tests. The suite already uses pytest-asyncio with auto mode and has a functional `conftest.py` with 7 shared fixtures. The primary modernization needs are:

1. **Fixture prefix standardization** - Current fixtures lack the `fixture_` prefix specified in CONTEXT.md decisions
2. **Test naming standardization** - Current naming is inconsistent; needs migration to `test_<feature>_<scenario>_<expected>` pattern
3. **Coverage configuration** - No pytest-cov configuration in pyproject.toml; needs 60% minimum with per-file 40% floor
4. **Consolidation of local fixtures** - 20+ fixtures scattered across individual test files should be evaluated for consolidation

The test infrastructure is already modern (pytest-asyncio 1.2+, auto mode enabled). The main work is standardization and configuration, not fundamental architecture changes.

**Primary recommendation:** Systematically migrate test files module-by-module, renaming tests and fixtures while adding coverage configuration to pyproject.toml.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 | Test framework | Industry standard, already in use |
| pytest-asyncio | 1.2+ | Async test support | Required for FastAPI/SQLAlchemy async; auto mode configured |
| pytest-cov | 7.0.0 | Coverage reporting | Integrates with pytest; already in dependencies |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.28+ | Async HTTP client | Already used for API testing via AsyncClient |
| unittest.mock | stdlib | Mocking | Already used in 5 test files for external APIs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-cov | coverage.py directly | pytest-cov integrates better with pytest CLI |
| unittest.mock | pytest-mock | Would add dependency; unittest.mock is sufficient |

**Installation:**
Already installed. No new dependencies needed.

```bash
# Verify current dependencies
uv sync --group test
```

## Architecture Patterns

### Current Project Structure (tests/)
```
tests/
├── conftest.py              # 7 shared fixtures (db_session, async_client, auth, etc.)
├── __init__.py              # Package marker
├── README.md                # Test documentation
├── test_auth.py             # 13 tests - authentication
├── test_phenopackets.py     # 4 tests - basic phenopacket validation
├── test_audit_utils.py      # 21 tests - audit trail utilities
├── test_variant_*.py        # Multiple files - variant functionality
├── test_json_api_*.py       # 2 files - pagination integration
└── ... (35 total test files)
```

### Recommended Future Structure (from CONTEXT.md decisions)
```
tests/
├── conftest.py              # Root fixtures: fixture_db_session, fixture_async_client
├── utils.py                 # Non-fixture helpers (data generators, etc.)
├── __init__.py
├── auth/                    # Optional: domain-specific subdirectory
│   ├── conftest.py          # Auth-specific fixtures
│   └── test_auth.py
└── phenopackets/            # Optional: domain-specific subdirectory
    ├── conftest.py          # Phenopacket-specific fixtures
    └── test_*.py
```

### Pattern 1: Async Context Manager Fixture (Current Pattern - Good)
**What:** Uses `@pytest_asyncio.fixture` with yield for setup/teardown
**When to use:** All async resources that need cleanup (db sessions, clients)
**Example:**
```python
# Source: Current conftest.py - this pattern is correct
@pytest_asyncio.fixture
async def fixture_db_session():
    """Provide database session with automatic cleanup."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = async_session_factory()

    try:
        yield session
    finally:
        await session.rollback()
        await session.close()
        await asyncio.shield(engine.dispose(close=True))
```

### Pattern 2: Test Naming Convention (Target Pattern)
**What:** `test_<feature>_<scenario>_<expected>` naming
**When to use:** All test functions
**Example:**
```python
# Source: CONTEXT.md decisions - TestDriven.io pattern
# Before (current):
async def test_login_success(async_client, test_user):

# After (target):
async def test_auth_login_valid_credentials_returns_token(fixture_async_client, fixture_test_user):
```

### Pattern 3: Class-Based Test Organization (Current - Keep)
**What:** Group related tests in classes prefixed with `Test`
**When to use:** When tests share fixtures or test the same feature
**Example:**
```python
# Source: Current test_audit_utils.py - good pattern
class TestGenerateJsonPatch:
    """Test RFC 6902 JSON Patch generation."""

    def test_json_patch_identical_inputs_returns_empty_list(self, sample_phenopacket_minimal):
        """Identical phenopackets produce empty patch."""
        patch = generate_json_patch(sample_phenopacket_minimal, sample_phenopacket_minimal)
        assert patch == []
```

### Anti-Patterns to Avoid
- **Module-scope db fixtures:** Can cause connection leaks; use function scope (current pattern is correct)
- **Fixtures without cleanup:** Always use try/finally or async context managers
- **Local fixtures that should be shared:** Move reusable fixtures to conftest.py
- **Non-descriptive test names:** `test_1`, `test_valid` - use full descriptive names

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async event loop management | Custom loop fixtures | pytest-asyncio auto mode | Already configured in pytest.ini |
| Test database transactions | Manual rollback logic | Fixture with yield | Pattern already in conftest.py |
| HTTP client for API tests | requests sync client | httpx AsyncClient | Already in use; matches async app |
| Coverage measurement | Manual tracking | pytest-cov | Standard tool, in dependencies |
| Mock async functions | Custom mock classes | unittest.mock.AsyncMock | Standard library since Python 3.8 |

**Key insight:** The test infrastructure is already well-architected. This phase is about standardization and configuration, not rebuilding.

## Common Pitfalls

### Pitfall 1: Fixture Naming Collision
**What goes wrong:** Multiple fixtures with same name in different conftest.py files cause confusion
**Why it happens:** pytest's fixture discovery searches upward; closer fixture shadows parent
**How to avoid:** Use unique, prefixed names (`fixture_db_session` not `db_session`)
**Warning signs:** Tests behave differently depending on directory

### Pitfall 2: Async Fixture Scope Mismatch
**What goes wrong:** Session-scoped async fixture used with function-scoped event loop
**Why it happens:** pytest-asyncio 1.0+ removed `event_loop` fixture; scope must match
**How to avoid:** Use `loop_scope` parameter or keep all fixtures function-scoped
**Warning signs:** "got Future attached to different loop" errors

### Pitfall 3: Test Ordering Dependencies
**What goes wrong:** Tests pass when run together but fail individually
**Why it happens:** Test relies on state from previous test
**How to avoid:** Each test should set up its own state via fixtures
**Warning signs:** `pytest -x` passes but `pytest --random-order` fails

### Pitfall 4: Coverage Configuration Priority
**What goes wrong:** Coverage settings in pyproject.toml ignored
**Why it happens:** .coveragerc or command-line options take precedence
**How to avoid:** Use single config source (pyproject.toml); remove .coveragerc if exists
**Warning signs:** Exclusions not working despite configuration

### Pitfall 5: Renaming Tests Breaks Existing References
**What goes wrong:** CI, documentation, or scripts reference old test names
**Why it happens:** Mass rename without updating references
**How to avoid:** Search codebase for test name references before renaming
**Warning signs:** CI scripts fail to find tests; documentation links break

## Code Examples

### Coverage Configuration (pyproject.toml)
```toml
# Source: pytest-cov documentation + CONTEXT.md decisions
[tool.coverage.run]
branch = true
source = ["app"]
omit = [
    "*/alembic/versions/*",
    "*/__init__.py",
]

[tool.coverage.report]
exclude_also = [
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "@(abc\\.)?abstractmethod",
]
fail_under = 60
show_missing = true

[tool.coverage.html]
skip_empty = true
```

### Fixture Rename Pattern
```python
# Source: CONTEXT.md decisions - rename with backward compatibility
# conftest.py

@pytest_asyncio.fixture
async def fixture_db_session():
    """Provide database session for testing."""
    # ... implementation ...

# Backward compatibility alias (remove after migration)
db_session = fixture_db_session
```

### Test Rename Mapping
```python
# Before -> After mapping for systematic rename

# test_auth.py
# test_login_success -> test_auth_login_valid_credentials_returns_token
# test_login_invalid_credentials -> test_auth_login_wrong_password_returns_401
# test_login_nonexistent_user -> test_auth_login_unknown_user_returns_401
# test_get_current_user -> test_auth_me_valid_token_returns_user_info
# test_get_current_user_no_token -> test_auth_me_no_token_returns_403
```

### Module-Specific Fixture Consolidation Check
```python
# Fixtures currently scattered in test files that could be consolidated:

# test_audit_utils.py - lines 23-73
@pytest.fixture
def sample_phenopacket_minimal() -> Dict[str, Any]:
    """Minimal phenopacket for testing."""

@pytest.fixture
def sample_phenopacket_with_data() -> Dict[str, Any]:
    """Phenopacket with phenotypes and variants for testing."""

# test_transaction_management.py - lines 18-42
@pytest.fixture
def valid_phenopacket_data():
    """Fixture for valid phenopacket data."""

@pytest.fixture
def invalid_phenopacket_data():
    """Fixture for invalid phenopacket data."""

# These could be consolidated into conftest.py as they're reusable test data
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `event_loop` fixture | `asyncio.get_running_loop()` | pytest-asyncio 1.0 (May 2025) | Must use auto mode or loop_scope |
| `pytest.mark.asyncio` per test | auto mode detection | pytest-asyncio 0.21+ | Already configured in pytest.ini |
| Separate .coveragerc | pyproject.toml [tool.coverage] | coverage.py 5.0+ | Single config file |

**Deprecated/outdated:**
- `event_loop` fixture: Removed in pytest-asyncio 1.0; current version handles this correctly
- `@pytest.fixture(scope="module")` for async: Can cause issues; prefer function scope

## Current State Analysis

### Test Count and Distribution
- **Total test files:** 35
- **Total tests:** ~748
- **Tests per file range:** 2 to ~150

### Current Fixture Usage
**conftest.py fixtures (7):**
1. `db_session` - AsyncSession for database tests
2. `test_user` - Standard user for auth tests
3. `admin_user` - Admin user for permission tests
4. `async_client` - httpx AsyncClient for API tests
5. `auth_headers` - JWT headers for authenticated requests
6. `admin_headers` - JWT headers for admin requests
7. `cleanup_test_phenopackets` - Test data cleanup

**Local fixtures (20+):**
- Scattered across test files
- Many are reusable (sample data, mock responses)
- Some are truly test-file-specific

### Current Naming Patterns (Mixed)
```
# Pattern A: Simple action (most common)
test_login_success
test_hpo_autocomplete_basic
test_create_audit_create_action

# Pattern B: Class-method (common)
TestGenerateJsonPatch::test_no_changes
TestVariantValidator::test_init

# Pattern C: Descriptive (rare, target pattern)
test_valid_username_and_password_combination_can_be_exchanged_for_access_token
```

### Coverage Status
- **pytest-cov:** Installed (7.0.0)
- **Configuration:** None in pyproject.toml
- **Current coverage:** Unknown (not routinely measured)
- **Target:** 60% overall, 40% per-file minimum

## Migration Order Recommendation

Based on complexity and dependencies:

1. **Configuration first** - Add pyproject.toml coverage config
2. **conftest.py** - Rename fixtures, add `fixture_` prefix
3. **Simple test files** - test_config.py, test_phenopackets.py (small, isolated)
4. **Auth tests** - test_auth.py (core, well-structured)
5. **Utility tests** - test_audit_utils.py, test_patterns.py
6. **Integration tests** - test_json_api_*.py, test_*_endpoint*.py
7. **Complex tests** - test_comparisons.py, test_variant_validator_enhanced.py

## Open Questions

Things that couldn't be fully resolved:

1. **Subdirectory structure**
   - What we know: CONTEXT.md mentions "subdirectory conftest.py for domain-specific" as an option
   - What's unclear: Whether to create auth/, phenopackets/ subdirs or keep flat
   - Recommendation: Keep flat initially; only create subdirs if >50 tests per domain

2. **Test utilities location**
   - What we know: CONTEXT.md specifies "tests/utils.py for non-fixture helpers"
   - What's unclear: What helpers currently exist that aren't fixtures
   - Recommendation: Create utils.py only when needed; don't create empty module

3. **Backward compatibility duration**
   - What we know: Aliases allow gradual migration
   - What's unclear: When to remove old fixture names
   - Recommendation: Remove after all tests migrated (same PR as final migration)

## Sources

### Primary (HIGH confidence)
- Current codebase analysis: `backend/tests/conftest.py`, `backend/pytest.ini`
- Current codebase analysis: `backend/pyproject.toml` (dependencies)
- CONTEXT.md decisions: `.planning/phases/03-backend-test-modernization/03-CONTEXT.md`

### Secondary (MEDIUM confidence)
- [pytest-asyncio 1.0 Migration](https://thinhdanggroup.github.io/pytest-asyncio-v1-migrate/) - Breaking changes
- [Essential pytest asyncio Tips](https://articles.mergify.com/pytest-asyncio-2/) - Modern patterns
- [pytest conftest Best Practices](https://pytest-with-eric.com/pytest-best-practices/pytest-conftest/) - Fixture organization
- [pytest-cov Configuration](https://pytest-cov.readthedocs.io/en/latest/config.html) - Coverage setup
- [TestDriven.io GIVEN-WHEN-THEN](https://testdriven.io/tips/0f25ebb7-d5c1-4040-b78e-ac48e8f0a014/) - Naming conventions

### Tertiary (LOW confidence)
- WebSearch results for general best practices (verified against official docs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Already in use, versions verified in pyproject.toml
- Architecture: HIGH - Current patterns analyzed, recommendations based on codebase
- Pitfalls: MEDIUM - Based on common issues from web resources, some verified in codebase

**Research date:** 2026-01-19
**Valid until:** 60 days (test tooling is stable)
