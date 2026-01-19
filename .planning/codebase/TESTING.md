# Testing Patterns

**Analysis Date:** 2026-01-19

## Test Framework

### Backend

**Runner:**
- pytest 9.0.2
- Config: `backend/pyproject.toml` (tool.pytest section)

**Async Support:**
- pytest-asyncio >= 1.2.0
- All async tests marked with `@pytest.mark.asyncio`

**Coverage:**
- pytest-cov 7.0.0
- Target: No enforced minimum, but full coverage encouraged

**Run Commands:**
```bash
cd backend
make test              # Run all tests
make check             # Lint + typecheck + tests
uv run pytest tests/test_specific.py -v          # Single file
uv run pytest -k "test_pattern" -v               # Pattern match
uv run pytest --cov=app --cov-report=html tests/ # With coverage
```

### Frontend

**Runner:**
- Vitest 4.0.7
- Config: `frontend/vitest.config.js`

**Environment:**
- happy-dom (faster than jsdom)
- Pool: vmThreads (WSL2 compatible)

**Coverage:**
- @vitest/coverage-v8 (V8 native coverage)

**Run Commands:**
```bash
cd frontend
make test              # Run all tests (vitest run)
make check             # Test + lint + format
npm test -- tests/unit/specific.spec.js  # Single file
npm run test:watch     # Watch mode
npm run test:coverage  # With coverage
```

## Test File Organization

### Backend

**Location:** Co-located tests in `backend/tests/`

**Naming:** `test_*.py`

**Structure:**
```
backend/tests/
├── conftest.py                    # Shared fixtures
├── README.md                      # Test documentation
├── test_auth.py                   # Authentication tests
├── test_phenopackets.py           # Basic CRUD tests
├── test_variant_validator_enhanced.py  # Comprehensive unit tests
├── test_json_api_pagination.py    # Pagination behavior
├── test_survival_analysis.py      # Statistical functions
└── test_global_search.py          # Search functionality
```

### Frontend

**Location:** Dedicated `frontend/tests/` directory

**Naming:** `*.spec.js`

**Structure:**
```
frontend/tests/
├── setup.js                       # Global test setup (Vuetify)
├── unit/
│   ├── components/
│   │   ├── KaplanMeierChart.spec.js
│   │   └── VariantComparisonChart.spec.js
│   ├── composables/
│   │   └── useTableUrlState.spec.js
│   ├── stores/
│   │   ├── authStore.spec.js
│   │   └── variantStore.spec.js
│   ├── config/
│   │   └── app.spec.js
│   └── logSanitizer.spec.js
└── e2e/
    └── table-url-state.spec.js
```

## Test Structure

### Backend Pattern

**Suite Organization:**
```python
"""Comprehensive unit tests for VEP annotation system.

Tests the VariantValidator class including:
- Format detection (VCF vs HGVS)
- VEP API annotation
- Rate limiting

Related: Issue #117, #100
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.phenopackets.validation.variant_validator import VariantValidator


@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """Clear the in-memory cache between tests."""
    cache.use_fallback_only()
    yield
    cache.clear_fallback()


class TestVariantFormatDetection:
    """Test format detection methods."""

    def test_is_vcf_format_valid(self):
        """Test VCF format detection with valid inputs."""
        validator = VariantValidator()
        assert validator._is_vcf_format("17-36459258-A-G") is True


class TestVEPAnnotation:
    """Test VEP annotation functionality."""

    @pytest.mark.asyncio
    async def test_annotate_vcf_format_success(self):
        """Test successful VCF format annotation."""
        validator = VariantValidator()
        # Test implementation...
```

**Async Test Pattern:**
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
    assert "refresh_token" in data
```

### Frontend Pattern

**Suite Organization:**
```javascript
/**
 * Unit tests for KaplanMeierChart component
 *
 * Tests cover:
 * - Survival data validation
 * - Kaplan-Meier calculation verification
 * - Edge cases (empty data, all censored)
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { shallowMount } from '@vue/test-utils';
import KaplanMeierChart from '@/components/analyses/KaplanMeierChart.vue';

// Mock D3 to avoid DOM rendering issues
vi.mock('d3', () => ({
  select: vi.fn(() => mockSelection()),
  // ...
}));

describe('KaplanMeierChart', () => {
  describe('Component Mounting', () => {
    it('should mount successfully with valid survival data', () => {
      const wrapper = shallowMount(KaplanMeierChart, {
        props: { survivalData: createSampleSurvivalData() },
      });
      expect(wrapper.exists()).toBe(true);
    });
  });

  describe('Props Validation', () => {
    it('should accept custom width', () => {
      const wrapper = shallowMount(KaplanMeierChart, {
        props: { survivalData: null, width: 800 },
      });
      expect(wrapper.props('width')).toBe(800);
    });
  });
});
```

**Pinia Store Testing:**
```javascript
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useAuthStore } from '@/stores/authStore';

// Mock API before imports
vi.mock('@/api', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('should login successfully', async () => {
    const authStore = useAuthStore();
    apiClient.post.mockResolvedValueOnce({ data: { access_token: 'token' } });

    await authStore.login({ username: 'test', password: 'pass' });

    expect(authStore.accessToken).toBe('token');
  });
});
```

## Mocking

### Backend Framework

**unittest.mock** (standard library)

**Patterns:**
```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_annotate_vcf_format_success(self):
    """Test successful VCF format annotation with CADD and gnomAD."""
    validator = VariantValidator()

    # Mock VEP API response
    mock_response_data = {
        "assembly_name": "GRCh38",
        "most_severe_consequence": "missense_variant",
        "transcript_consequences": [
            {"gene_symbol": "HNF1B", "impact": "MODERATE"}
        ],
    }

    with patch.object(validator, '_call_vep_api', new_callable=AsyncMock) as mock:
        mock.return_value = mock_response_data
        result = await validator.annotate("17-36459258-A-G")

    assert result["most_severe_consequence"] == "missense_variant"
```

**What to Mock:**
- External API calls (VEP, PubMed, OLS)
- Redis cache (use fallback mode)
- Network requests (httpx)

**What NOT to Mock:**
- Database queries in integration tests
- Business logic under test
- Standard library functions

### Frontend Framework

**Vitest mocking** (vi.mock, vi.fn)

**Patterns:**
```javascript
// Mock modules before imports
vi.mock('@/api', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

// Mock vue-router
vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => ({ replace: mockReplace }),
}));

// Mock D3 for visualization tests
vi.mock('d3', () => ({
  select: vi.fn(() => mockSelection()),
  scaleLinear: vi.fn(() => {
    const scale = vi.fn((val) => val * 10);
    scale.domain = vi.fn(() => scale);
    scale.range = vi.fn(() => scale);
    return scale;
  }),
}));

// Mock localStorage
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: vi.fn((key) => store[key] || null),
    setItem: vi.fn((key, value) => { store[key] = value; }),
    removeItem: vi.fn((key) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Mock window.logService
window.logService = {
  info: vi.fn(),
  error: vi.fn(),
  warn: vi.fn(),
  debug: vi.fn(),
};
```

**What to Mock:**
- API client calls
- Vue Router
- D3 and visualization libraries
- localStorage/sessionStorage
- Global services (logService)

**What NOT to Mock:**
- Vue reactivity system
- Component props/emits
- Vuetify (use real instance from setup.js)

## Fixtures and Factories

### Backend Fixtures

**Location:** `backend/tests/conftest.py`

**Key Fixtures:**
```python
@pytest_asyncio.fixture
async def db_session():
    """Provide a database session for testing."""
    engine = create_async_engine(settings.DATABASE_URL)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession)
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


@pytest_asyncio.fixture
async def auth_headers(test_user, async_client):
    """Get auth headers for authenticated requests."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

### Frontend Test Setup

**Location:** `frontend/tests/setup.js`

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

// Create Vuetify instance
const vuetify = createVuetify({
  components,
  directives,
});

// Register globally
config.global.plugins = [vuetify];
```

### Test Data Factories

**Frontend Pattern:**
```javascript
const createSampleSurvivalData = () => ({
  comparison_type: 'variant_type',
  endpoint: 'ESRD',
  groups: [
    {
      name: 'Missense',
      n: 50,
      events: 35,
      survival_data: [
        { time: 0, survival_probability: 1.0, at_risk: 50, events: 0 },
        { time: 10, survival_probability: 0.75, at_risk: 38, events: 7 },
      ],
    },
  ],
});
```

**Backend Pattern:**
```python
def create_test_phenopacket(id: str = "TEST001") -> dict:
    """Create a test phenopacket structure."""
    return {
        "id": f"phenopacket-{id}",
        "subject": {"id": id, "sex": "MALE"},
        "phenotypicFeatures": [
            {"type": {"id": "HP:0012622", "label": "Chronic kidney disease"}}
        ],
        "metaData": {
            "created": "2024-01-01T00:00:00Z",
            "phenopacketSchemaVersion": "2.0.0",
        },
    }
```

## Coverage

**Backend Requirements:** No enforced minimum

**Backend Commands:**
```bash
uv run pytest --cov=app --cov-report=html tests/
uv run pytest --cov=app --cov-report=term-missing tests/
```

**Frontend Requirements:** No enforced minimum

**Frontend Commands:**
```bash
npm run test:coverage
```

**Vitest Coverage Config** (`frontend/vitest.config.js`):
```javascript
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

## Test Types

### Unit Tests

**Scope:** Individual functions, classes, methods

**Backend Examples:**
- `test_variant_validator_enhanced.py` - VariantValidator class methods
- `test_patterns.py` - Regex pattern validation
- `test_config.py` - Configuration loading

**Frontend Examples:**
- `logSanitizer.spec.js` - Sanitization functions
- `useTableUrlState.spec.js` - Composable logic
- `authStore.spec.js` - Store actions/getters

### Integration Tests

**Scope:** API endpoints, database interactions

**Backend Examples:**
- `test_auth.py` - Full authentication flow
- `test_json_api_pagination.py` - Pagination with database
- `test_global_search.py` - Search with materialized views

**Markers:**
```python
@pytest.mark.integration
async def test_phenopacket_crud_flow(async_client, auth_headers):
    """Test complete CRUD lifecycle."""
```

### E2E Tests

**Framework:** Playwright (`@playwright/test`)

**Location:** `frontend/tests/e2e/`

**Examples:**
- `table-url-state.spec.js` - URL state synchronization
- `phenopacket-ui-review.spec.js` - User interface flows

## Common Patterns

### Async Testing (Backend)

```python
@pytest.mark.asyncio
async def test_async_operation(async_client):
    """Test async endpoint."""
    response = await async_client.get("/api/v2/phenopackets/")
    assert response.status_code == 200

    data = response.json()
    assert "data" in data
    assert "meta" in data
```

### Error Testing

**Backend:**
```python
@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client, test_user):
    """Test login with invalid credentials."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "WrongPassword"},
    )

    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]
```

**Frontend:**
```javascript
it('should handle login failure', async () => {
  const authStore = useAuthStore();

  apiClient.post.mockRejectedValueOnce({
    response: { data: { detail: 'Invalid credentials' } },
  });

  await expect(
    authStore.login({ username: 'test', password: 'wrong' })
  ).rejects.toThrow();

  expect(authStore.error).toBe('Invalid credentials');
});
```

### Component Testing (Frontend)

```javascript
describe('Component Mounting', () => {
  it('should mount successfully with valid props', () => {
    const wrapper = shallowMount(KaplanMeierChart, {
      props: { survivalData: createSampleSurvivalData() },
    });

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.find('.kaplan-meier-container').exists()).toBe(true);
  });

  it('should handle null props gracefully', () => {
    const wrapper = shallowMount(KaplanMeierChart, {
      props: { survivalData: null },
    });

    expect(wrapper.exists()).toBe(true);
  });
});
```

### Cleanup Best Practices

**Backend:**
```python
@pytest_asyncio.fixture
async def test_user(db_session):
    """Create test user with cleanup."""
    # Pre-cleanup: Remove leftovers from failed tests
    await db_session.execute(delete(User).where(User.email == "test@example.com"))
    await db_session.commit()

    user = User(username="testuser", email="test@example.com")
    db_session.add(user)
    await db_session.commit()

    yield user

    # Post-cleanup
    try:
        await db_session.execute(delete(User).where(User.id == user.id))
        await db_session.commit()
    except Exception:
        await db_session.rollback()
```

**Frontend:**
```javascript
beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  localStorageMock.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});
```

## CI Integration

**GitHub Actions** (`.github/workflows/ci.yml`):
- Runs on push/PR
- Backend: ruff lint, mypy typecheck, pytest
- Frontend: ESLint, Prettier check, Vitest

**Pre-commit Hooks** (`.pre-commit-config.yaml`):
- pytest-check on pre-push
- Non-deterministic hash detection
- Test import validation

---

*Testing analysis: 2026-01-19*
