# Backend Tests

This directory contains the test suite for the HNF1B database backend.

## Test Structure

```
tests/
├── conftest.py                           # Pytest configuration and fixtures
├── test_phenopackets.py                  # Phenopacket CRUD operations
├── test_variant_search.py                # Variant search validation and logic
├── test_batch_endpoints.py               # Batch endpoint performance
├── test_batch_performance.py             # Performance benchmarks
├── test_jsonb_indexes.py                 # JSONB index performance
├── test_index_performance_benchmark.py   # Index benchmark suite
├── test_direct_phenopackets_migration.py # Migration testing
├── test_cnv_parser.py                    # CNV parsing logic
├── test_ontology_service.py              # HPO/ontology services
└── test_config.py                        # Configuration validation
```

## Running Tests

### Quick Start

```bash
# From backend directory
make test              # Run all tests
make check             # Run lint + typecheck + tests

# From project root
cd backend && make test
```

### Specific Test Files

```bash
# Run specific test file
uv run pytest tests/test_variant_search.py -v

# Run with coverage
uv run pytest --cov=app --cov-report=html tests/

# Run tests matching pattern
uv run pytest -k "test_hgvs" -v

# Run with detailed output
uv run pytest -vv tests/test_variant_search.py
```

### Test Categories

```bash
# Unit tests only (fast)
uv run pytest -m "not integration" -v

# Integration tests (require database)
uv run pytest -m integration -v

# Performance benchmarks
uv run pytest tests/test_batch_performance.py -v
```

## Test Files Overview

### test_variant_search.py

**Purpose:** Test variant search endpoint validation and logic

**Covers:**
- HGVS notation validation (c., p., g. formats)
- HG38 genomic coordinate validation
- Search query sanitization (SQL injection prevention)
- Variant type, classification, gene validation
- Molecular consequence computation
- Consequence filtering logic

**Key Tests:**
- `TestHGVSValidation` - HGVS format validation
- `TestHG38Validation` - Genomic coordinate formats
- `TestSearchQueryValidation` - Input sanitization
- `TestMolecularConsequenceComputation` - Consequence detection
- `TestConsequenceFiltering` - Post-query filtering

**Run:**
```bash
uv run pytest tests/test_variant_search.py -v
```

**Example:**
```python
def test_valid_c_notation(self):
    """Test valid c. notations."""
    assert validate_hgvs_notation("c.1654-2A>T") is True
    assert validate_hgvs_notation("c.544+1G>T") is True
```

### test_phenopackets.py

**Purpose:** Test core phenopacket CRUD operations

**Covers:**
- Phenopacket creation, retrieval, update, delete
- Validation of phenopacket structure
- Error handling for invalid inputs

**Run:**
```bash
uv run pytest tests/test_phenopackets.py -v
```

### test_batch_endpoints.py

**Purpose:** Test batch endpoints for preventing N+1 queries

**Covers:**
- Batch phenopacket fetching
- Batch variant fetching
- Batch feature fetching
- Performance comparisons (batch vs. individual)

**Run:**
```bash
uv run pytest tests/test_batch_endpoints.py -v
```

### test_jsonb_indexes.py

**Purpose:** Test JSONB index performance and query optimization

**Covers:**
- GIN index creation verification
- Query performance with/without indexes
- Index usage by query planner (EXPLAIN ANALYZE)

**Run:**
```bash
uv run pytest tests/test_jsonb_indexes.py -v
```

### test_cnv_parser.py

**Purpose:** Test CNV (copy number variant) parsing logic

**Covers:**
- CNV coordinate parsing
- CNV type detection (deletion, duplication)
- Edge cases and error handling

**Run:**
```bash
uv run pytest tests/test_cnv_parser.py -v
```

## Writing New Tests

### Test File Template

```python
"""Tests for [module name].

Brief description of what this test file covers.
"""

import pytest
from app.module import function_to_test


class TestFeatureName:
    """Test [feature name] functionality."""

    def test_valid_case(self):
        """Test valid input handling."""
        result = function_to_test(valid_input)
        assert result == expected_output

    def test_invalid_case(self):
        """Test invalid input handling."""
        with pytest.raises(HTTPException) as exc:
            function_to_test(invalid_input)
        assert exc.value.status_code == 400
        assert "error message" in exc.value.detail
```

### Best Practices

1. **Organize by Feature:** Group related tests in classes
2. **Clear Docstrings:** Explain what each test validates
3. **Descriptive Names:** Use `test_valid_hgvs_notation` not `test_1`
4. **Arrange-Act-Assert:** Structure tests clearly
5. **Test Edge Cases:** Not just happy path
6. **Mock External Services:** Don't rely on external APIs
7. **Use Fixtures:** Share setup code via `conftest.py`

### Example: Testing Validation

```python
class TestInputValidation:
    """Test input validation functions."""

    def test_valid_input(self):
        """Test that valid input passes validation."""
        result = validate_search_query("c.1654-2A>T")
        assert result == "c.1654-2A>T"

    def test_invalid_characters(self):
        """Test that invalid characters are rejected."""
        with pytest.raises(HTTPException) as exc:
            validate_search_query("'; DROP TABLE;--")
        assert exc.value.status_code == 400
        assert "invalid characters" in exc.value.detail

    def test_length_limit(self):
        """Test that overly long queries are rejected."""
        long_query = "A" * 201
        with pytest.raises(HTTPException) as exc:
            validate_search_query(long_query)
        assert exc.value.status_code == 400
        assert "too long" in exc.value.detail
```

## Test Coverage

### Current Coverage

Run coverage report:
```bash
uv run pytest --cov=app --cov-report=html tests/
```

View HTML report:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Coverage Goals

- **Core modules:** >90% coverage
- **API endpoints:** >80% coverage
- **Validation functions:** 100% coverage
- **Utility functions:** >85% coverage

## Fixtures

### Available Fixtures (conftest.py)

```python
@pytest.fixture
def db_session():
    """Provide a database session for tests."""
    # Setup database connection
    yield session
    # Teardown

@pytest.fixture
def sample_phenopacket():
    """Provide a sample phenopacket for tests."""
    return {
        "id": "test_001",
        "subject": {...},
        "phenotypicFeatures": [...],
    }
```

**Usage:**
```python
def test_create_phenopacket(db_session, sample_phenopacket):
    """Test phenopacket creation."""
    result = create_phenopacket(db_session, sample_phenopacket)
    assert result.phenopacket_id == "test_001"
```

## Continuous Integration

### GitHub Actions

Tests run automatically on:
- Push to main branch
- Pull request creation
- Manual trigger

**Workflow:** `.github/workflows/ci.yml`

### Pre-commit Hooks

Install pre-commit hooks:
```bash
uv pip install pre-commit
pre-commit install
```

Runs before each commit:
- Code formatting (ruff)
- Type checking (mypy)
- Linting (ruff)

Runs before push:
- Full test suite

## Performance Testing

### Benchmark Tests

```bash
# Run performance benchmarks
uv run pytest tests/test_batch_performance.py -v
uv run pytest tests/test_index_performance_benchmark.py -v
```

**Metrics Tracked:**
- Query execution time
- Number of database queries
- Index usage
- Memory consumption

### Performance Regression Detection

Tests fail if performance degrades beyond threshold:
```python
def test_variant_search_performance(db_session):
    """Ensure variant search completes within 100ms."""
    start = time.time()
    result = search_variants(query="c.1654-2A>T")
    duration = time.time() - start
    assert duration < 0.1, f"Query took {duration}s (limit: 0.1s)"
```

## Troubleshooting

### Common Issues

**Issue:** `ModuleNotFoundError: No module named 'pytest'`
```bash
# Solution: Install test dependencies
uv sync --group test
```

**Issue:** Database connection errors
```bash
# Solution: Ensure database is running
make hybrid-up  # From project root
```

**Issue:** Tests fail with "table does not exist"
```bash
# Solution: Run migrations
uv run alembic upgrade head
```

**Issue:** Import errors in tests
```bash
# Solution: Ensure backend is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Debug Mode

Run tests with debugging:
```bash
# Drop into debugger on failure
uv run pytest --pdb tests/

# Print captured output
uv run pytest -s tests/

# Very verbose output
uv run pytest -vv tests/
```

## Security Testing

### SQL Injection Tests

Tests validate that SQL injection attempts fail:
```python
def test_sql_injection_prevention(self):
    """Ensure SQL injection attempts are blocked."""
    with pytest.raises(HTTPException):
        validate_search_query("'; DROP TABLE phenopackets;--")
```

### Input Validation Tests

Tests ensure all inputs are validated:
```python
def test_character_whitelist(self):
    """Ensure only allowed characters pass validation."""
    # Allowed characters should pass
    assert validate_search_query("c.123+1G>T") is not None

    # Disallowed characters should fail
    with pytest.raises(HTTPException):
        validate_search_query("c.123; DROP TABLE")
```

## Contributing

### Adding Tests for New Features

1. Create test file: `tests/test_new_feature.py`
2. Write tests covering:
   - Valid inputs (happy path)
   - Invalid inputs (error handling)
   - Edge cases
   - Performance (if applicable)
3. Run tests: `make test`
4. Check coverage: `uv run pytest --cov=app tests/`
5. Ensure CI passes before merging

### Test Naming Conventions

- Test files: `test_<module_name>.py`
- Test classes: `Test<FeatureName>`
- Test methods: `test_<what_is_tested>`

**Examples:**
- `test_variant_search.py`
- `TestHGVSValidation`
- `test_valid_c_notation`

## Related Documentation

- **Phenopackets Module:** [app/phenopackets/README.md](../app/phenopackets/README.md)
- **Variant Search:** [docs/api/VARIANT_SEARCH.md](../../docs/api/VARIANT_SEARCH.md)
- **Backend README:** [backend/README.md](../README.md)
- **Project Guide:** [CLAUDE.md](../../CLAUDE.md)

## Support

For test-related questions:
1. Check this README
2. Review existing tests for examples
3. See pytest documentation: https://docs.pytest.org/
4. Check conftest.py for available fixtures
