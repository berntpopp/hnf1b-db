# Testing Patterns

**Analysis Date:** 2026-01-19

## Test Framework

**Backend:**
- **Runner:** pytest 9.0.2 with pytest-asyncio >= 1.2.0
- **Config:** `backend/pytest.ini`
- **Coverage:** pytest-cov 7.0.0

**Frontend:**
- **Runner:** Vitest (latest)
- **Config:** `frontend/vitest.config.js`
- **Coverage:** V8 provider (native, faster than Istanbul)

**Run Commands:**

Backend:
```bash
cd backend
make test                    # Run all tests (excluding benchmarks)
make test-all                # Run all tests including benchmarks
make test-benchmark          # Run only benchmark tests
uv run pytest tests/test_specific.py -v              # Single file
uv run pytest tests/test_auth.py::test_login_success # Single test
```

Frontend:
```bash
cd frontend
make test                    # Run tests once
make test-watch              # Watch mode
make test-coverage           # With coverage report
npm test -- tests/specific.test.js   # Single file
```

## Test File Organization

**Backend Location:** `backend/tests/`
```
backend/tests/
├── conftest.py                           # Shared fixtures
├── __init__.py
├── test_auth.py                          # Authentication tests
├── test_batch_endpoints.py               # Batch API tests
├── test_cursor_pagination.py             # Cursor pagination tests
├── test_json_api_pagination.py           # JSON:API pagination tests
├── test_variant_annotation_vep.py        # VEP annotation tests
├── test_phenopackets.py                  # Phenopacket model tests
├── test_survival_analysis.py             # Statistical analysis tests
└── ... (35 test files total)
```

**Frontend Location:** `frontend/tests/`
```
frontend/tests/
├── setup.js                              # Global test setup (Vuetify)
├── unit/
│   ├── components/                       # Component tests
│   │   ├── HNF1BProteinVisualization.spec.js
│   │   ├── VariantComparisonChart.spec.js
│   │   └── KaplanMeierChart.spec.js
│   ├── composables/                      # Composable tests
│   │   └── useTableUrlState.spec.js
│   ├── stores/                           # Pinia store tests
│   │   ├── authStore.spec.js
│   │   └── variantStore.spec.js
│   ├── config/
│   │   └── app.spec.js
│   └── logSanitizer.spec.js
└── e2e/                                  # End-to-end tests
    ├── phenopacket-ui-review.spec.js
    └── table-url-state.spec.js
```

**Naming Convention:**
- Backend: `test_*.py`
- Frontend: `*.spec.js`

## Test Structure

**Backend Suite Organization:**
```python
"""Tests for JSON:API pagination implementation.

Test coverage:
- Offset pagination (page[number], page[size])
- Filtering (filter[sex], filter[has_variants])
- Sorting (sort parameter with asc/desc)
- Response structure (data, meta, links)
"""

import pytest
from httpx import AsyncClient

class TestJsonApiResponseStructure:
    """Test JSON:API response structure compliance."""

    @pytest.mark.asyncio
    async def test_response_contains_data_meta_links(
        self, async_client: AsyncClient, sample_phenopackets
    ):
        """Test that response contains required JSON:API fields."""
        response = await async_client.get("/api/v2/phenopackets/")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "meta" in data
        assert "links" in data
```

**Frontend Suite Organization:**
```javascript
/**
 * Unit tests for the authentication store (authStore)
 *
 * Tests cover:
 * - State initialization
 * - Computed properties (isAuthenticated, isAdmin, isCurator)
 * - Login flow with token storage
 * - Logout with cleanup
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial State', () => {
    it('should initialize with null user and tokens', () => {
      const authStore = useAuthStore();
      expect(authStore.user).toBeNull();
      expect(authStore.accessToken).toBeNull();
    });
  });

  describe('Login Action', () => {
    it('should login successfully and store tokens', async () => {
      // ... test implementation
    });
  });
});
```

## Mocking

**Backend Mocking (unittest.mock):**
```python
from unittest.mock import AsyncMock, Mock, patch

@pytest.mark.asyncio
async def test_annotate_variant_vcf_success(
    self, validator, mock_vep_annotation_response
):
    """Test VCF variant annotation with mock response."""
    with (
        patch("httpx.AsyncClient") as mock_client,
        patch("app.phenopackets.validation.variant_validator.cache") as mock_cache,
    ):
        # Mock cache miss
        mock_cache.get_json = AsyncMock(return_value=None)
        mock_cache.set_json = AsyncMock(return_value=True)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [mock_vep_annotation_response]
        mock_response.headers = {}

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client.return_value = mock_client_instance

        result = await validator.annotate_variant_with_vep("17-36459258-A-G")
        assert result is not None
```

**Frontend Mocking (Vitest vi):**
```javascript
// Mock modules before import
vi.mock('@/api', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

// Import after mock
import { useAuthStore } from '@/stores/authStore';
import { apiClient } from '@/api';

// Mock localStorage
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: vi.fn((key) => store[key] || null),
    setItem: vi.fn((key, value) => {
      store[key] = value != null ? value.toString() : '';
    }),
    removeItem: vi.fn((key) => delete store[key]),
    clear: vi.fn(() => { store = {}; }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Mock logService
window.logService = {
  info: vi.fn(),
  error: vi.fn(),
  warn: vi.fn(),
  debug: vi.fn(),
};
```

**What to Mock:**
- External API calls (VEP, PubMed)
- Database sessions (use test fixtures instead)
- localStorage/sessionStorage
- Router (vue-router)
- Global services (logService)

**What NOT to Mock:**
- The code under test
- Pydantic validation
- Pure utility functions
- Simple data transformations

## Fixtures and Factories

**Backend Fixtures (`backend/tests/conftest.py`):**
```python
@pytest_asyncio.fixture
async def db_session():
    """Provide a database session for testing."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    session = async_session_factory()

    try:
        yield session
    finally:
        await session.rollback()
        await session.close()
        await asyncio.shield(engine.dispose(close=True))


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create test user for authentication tests."""
    # Pre-cleanup
    await db_session.execute(delete(User).where(User.email == "test@example.com"))
    await db_session.commit()

    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        role="viewer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    yield user

    # Cleanup
    await db_session.execute(delete(User).where(User.id == user.id))
    await db_session.commit()


@pytest_asyncio.fixture
async def async_client(db_session):
    """Async HTTP client for API testing."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
```

**Frontend Setup (`frontend/tests/setup.js`):**
```javascript
import { config } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

// Polyfill ResizeObserver for Vuetify
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Create Vuetify instance for tests
const vuetify = createVuetify({ components, directives });
config.global.plugins = [vuetify];
```

**Test Data Factory Pattern (Backend):**
```python
@pytest.fixture(scope="function")
async def sample_phenopackets(db_session: AsyncSession):
    """Create sample phenopackets for pagination testing."""
    sanitizer = PhenopacketSanitizer()
    phenopackets_data = []

    for i in range(50):
        data = {
            "id": f"test_pagination_{i:03d}",
            "subject": {"id": f"patient_{i:03d}", "sex": "MALE" if i % 2 == 0 else "FEMALE"},
            "phenotypicFeatures": [
                {"type": {"id": "HP:0000001", "label": f"Test feature {i}"}}
            ],
            "metaData": {
                "created": "2024-01-01T00:00:00Z",
                "phenopacketSchemaVersion": "2.0.0",
            },
        }
        sanitized = sanitizer.sanitize_phenopacket(data)
        phenopacket = Phenopacket(
            phenopacket_id=sanitized["id"],
            phenopacket=sanitized,
            subject_id=sanitized["subject"]["id"],
            subject_sex=sanitized["subject"].get("sex"),
        )
        db_session.add(phenopacket)
        phenopackets_data.append(phenopacket)

    await db_session.commit()
    yield phenopackets_data

    # Cleanup
    await db_session.execute(
        delete(Phenopacket).where(Phenopacket.phenopacket_id.like("test_pagination_%"))
    )
    await db_session.commit()
```

## Coverage

**Backend Requirements:** No enforced minimum, but critical paths tested

**Frontend Configuration:**
```javascript
// vitest.config.js
coverage: {
  provider: 'v8',
  reporter: ['text', 'json', 'html'],
  exclude: [
    'src/main.js',
    'src/router/index.js',
    '**/node_modules/**',
    '**/tests/**',
    '**/*.config.js',
  ],
},
```

**View Coverage:**
```bash
# Backend
cd backend && uv run pytest --cov=app --cov-report=html

# Frontend
cd frontend && npm run test:coverage
```

## Test Types

**Unit Tests:**
- Backend: Test individual functions and classes in isolation
- Frontend: Test composables, stores, utility functions

**Integration Tests (Backend):**
- Test API endpoints with database fixtures
- Use `async_client` fixture with real app routing
- Test full request/response cycles

**Component Tests (Frontend):**
- Mount Vue components with test-utils
- Test props, events, slots
- Verify DOM output

**E2E Tests (Frontend):**
- Location: `frontend/tests/e2e/`
- Full user flow testing

## Common Patterns

**Async Testing (Backend):**
```python
@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, test_user):
    """Test successful login."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
```

**Async Testing (Frontend):**
```javascript
it('should login successfully and store tokens', async () => {
  const authStore = useAuthStore();

  apiClient.post.mockResolvedValueOnce({
    data: { access_token: 'token', refresh_token: 'refresh' },
  });
  apiClient.get.mockResolvedValueOnce({
    data: { id: 1, username: 'testuser' },
  });

  const success = await authStore.login({ username: 'test', password: 'pass' });

  expect(success).toBe(true);
  expect(authStore.accessToken).toBe('token');
  expect(localStorageMock.setItem).toHaveBeenCalledWith('access_token', 'token');
});
```

**Error Testing (Backend):**
```python
@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client: AsyncClient, test_user):
    """Test login with invalid credentials."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "WrongPassword"},
    )

    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]
```

**Error Testing (Frontend):**
```javascript
it('should handle login failure', async () => {
  const authStore = useAuthStore();

  const mockError = {
    response: { data: { detail: 'Invalid credentials' } },
  };
  apiClient.post.mockRejectedValueOnce(mockError);

  await expect(
    authStore.login({ username: 'test', password: 'wrong' })
  ).rejects.toThrow();

  expect(authStore.error).toBe('Invalid credentials');
  expect(window.logService.error).toHaveBeenCalled();
});
```

## Test Markers (Backend)

```ini
# pytest.ini
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    benchmark: marks tests as benchmarks (deselect with '-m "not benchmark"')
```

**Usage:**
```python
@pytest.mark.slow
async def test_large_dataset_processing():
    ...

@pytest.mark.benchmark
async def test_query_performance():
    ...
```

## Vitest Configuration Details

```javascript
// vitest.config.js
export default defineConfig({
  test: {
    globals: true,  // Jest-compatible API
    environment: 'happy-dom',  // Faster than jsdom

    // WSL2 compatibility
    pool: process.env.CI ? 'threads' : 'vmThreads',
    poolOptions: {
      vmThreads: { memoryLimit: '512MB' },
    },

    testTimeout: 10000,  // 10 seconds
    hookTimeout: 10000,

    include: ['tests/unit/**/*.spec.js', 'tests/components/**/*.spec.js'],
  },

  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
});
```

## Best Practices from CLAUDE.md

1. **Tests use PUBLIC APIs only**
   - Test `builder.build_phenopacket(id, rows)` not `migration._build_subject(row)`

2. **Deterministic code only**
   - Use `hashlib.sha256()` not `abs(hash(data))`

3. **Fix broken tests immediately**
   - Never commit failing tests
   - Update tests when refactoring APIs

4. **Use pytest caplog for logging tests**
   - Modern approach over mocking

5. **Always clean up test data**
   - Pre-cleanup and post-cleanup in fixtures
   - Use `like("test_%")` patterns for isolation

---

*Testing analysis: 2026-01-19*
