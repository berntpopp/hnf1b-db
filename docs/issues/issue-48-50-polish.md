# Issues #48-49 - Polish & Testing

## Issue #48: test(frontend): add E2E tests for critical user flows

### Overview
Comprehensive end-to-end testing with Playwright for all critical workflows.

### Test Framework Setup
```bash
npm install -D @playwright/test
npx playwright install
```

---

## Test Data Management Strategy

### Problem

E2E tests require **predictable, stable test data**, but current setup uses:
- Production phenopackets data (864 individuals)
- Data can change during development
- Tests like "click first phenopacket" will break if ordering changes

### Recommended Solution: Dedicated Test Database

**Option 1: Docker Compose Test Environment** (Recommended)

```yaml
# docker-compose.test.yml
services:
  test-db:
    image: postgres:15
    environment:
      POSTGRES_DB: hnf1b_test
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_pass
    ports:
      - "5434:5432"  # Different port from dev DB
    volumes:
      - ./tests/fixtures/test-seed.sql:/docker-entrypoint-initdb.d/seed.sql

  test-backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://test_user:test_pass@test-db:5432/hnf1b_test
      JWT_SECRET: test-secret-do-not-use-in-prod
    depends_on:
      - test-db
    ports:
      - "8001:8000"  # Different port from dev backend
```

**Startup:**
```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run E2E tests
cd frontend && npm run test:e2e
```

**Teardown:**
```bash
# Clean up test environment
docker-compose -f docker-compose.test.yml down -v
```

### Test Data Fixtures

**Create Known Test Phenopackets:**

```sql
-- tests/fixtures/test-seed.sql

-- Known phenopacket for navigation tests
INSERT INTO phenopackets (id, jsonb) VALUES (
  'test-phenopacket-001',
  '{
    "id": "test-phenopacket-001",
    "subject": {
      "id": "TEST-PATIENT-001",
      "sex": "FEMALE",
      "timeAtLastEncounter": {"age": {"iso8601duration": "P25Y"}}
    },
    "diseases": [{
      "term": {"id": "MONDO:0013894", "label": "HNF1B-related disorder"}
    }],
    "phenotypicFeatures": [
      {"type": {"id": "HP:0012622", "label": "Chronic kidney disease"}},
      {"type": {"id": "HP:0000105", "label": "Genital abnormality"}}
    ],
    "interpretations": [{
      "diagnosis": {
        "genomicInterpretations": [{
          "variantInterpretation": {
            "acmgPathogenicityClassification": "PATHOGENIC",
            "variationDescriptor": {
              "id": "test-variant-001",
              "label": "HNF1B TEST VARIANT",
              "geneContext": {"valueId": "HGNC:5024", "symbol": "HNF1B"}
            }
          }
        }]
      }
    }]
  }'::jsonb
);

-- Add 10 more test phenopackets with known IDs
-- test-phenopacket-002 through test-phenopacket-010
-- ...
```

### Test Patterns with Fixed IDs

**Before (Brittle - breaks if data changes):**
```javascript
test('Navigate to phenopacket detail', async ({ page }) => {
  await page.goto('http://localhost:5173/phenopackets');
  await page.locator('.v-chip').first().click();  // ❌ FRAGILE
  await page.waitForURL('**/phenopackets/*');
});
```

**After (Robust - uses known test IDs):**
```javascript
test('Navigate to phenopacket detail', async ({ page }) => {
  await page.goto('http://localhost:5173/phenopackets');
  await page.locator('[data-testid="phenopacket-test-phenopacket-001"]').click();  // ✅ STABLE
  await page.waitForURL('**/phenopackets/test-phenopacket-001');

  // Verify expected content
  await expect(page.locator('text=TEST-PATIENT-001')).toBeVisible();
  await expect(page.locator('text=Chronic kidney disease')).toBeVisible();
});
```

### Alternative: Mock API Responses

**Option 2: Mock Backend with MSW (Mock Service Worker)**

If test database setup is too complex, mock API responses:

```javascript
// tests/mocks/handlers.js
import { rest } from 'msw';

export const handlers = [
  rest.get('/api/v2/phenopackets', (req, res, ctx) => {
    return res(
      ctx.json([
        {
          id: 'test-phenopacket-001',
          subject: { id: 'TEST-PATIENT-001', sex: 'FEMALE' },
          diseases: [{ term: { label: 'HNF1B-related disorder' }}],
          phenotypicFeatures: [
            { type: { label: 'Chronic kidney disease' }}
          ]
        }
      ])
    );
  }),

  rest.get('/api/v2/phenopackets/test-phenopacket-001', (req, res, ctx) => {
    return res(ctx.json({ /* full test phenopacket */ }));
  }),
];

// tests/setup.js
import { setupServer } from 'msw/node';
import { handlers } from './mocks/handlers';

const server = setupServer(...handlers);
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

**Pros:**
- Fast (no database)
- Portable (works offline)
- Easy to test error states

**Cons:**
- Doesn't test real backend integration
- Must keep mocks in sync with API

### Test Data Cleanup

**Ensure tests are idempotent:**

```javascript
// Run before each test suite
beforeEach(async () => {
  // Reset test database to known state
  await fetch('http://localhost:8001/test/reset-db', { method: 'POST' });
});

// Backend test endpoint (only enabled in test environment)
// backend/app/test_endpoints.py
@router.post("/test/reset-db")
async def reset_test_database():
    """Reset test database to seed state. Only works in TEST mode."""
    if settings.ENVIRONMENT != "test":
        raise HTTPException(403, "Only available in test environment")

    # Truncate and reseed
    await db.execute("TRUNCATE phenopackets CASCADE")
    await db.execute(open("tests/fixtures/test-seed.sql").read())
    return {"status": "reset"}
```

### Recommended Test Data Structure

**Minimum Test Dataset:**
- **10 phenopackets** with known IDs (`test-phenopacket-001` to `010`)
- **3 unique variants** (`test-variant-001` to `003`)
- **2 publications** (`PMID:99999901`, `PMID:99999902`)
- **5 HPO terms** (CKD, diabetes, genital abnormality, hypomagnesemia, MODY)

**Coverage:**
- Male/Female subjects
- With/without variants
- Different pathogenicity classifications
- Different disease combinations

### Test Suites

#### 1. Navigation Flow
```javascript
test('Navigate from home to phenopacket detail', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await page.click('text=Phenopackets');
  await page.waitForURL('**/phenopackets');

  // Click first phenopacket
  await page.locator('.v-chip').first().click();
  await page.waitForURL('**/phenopackets/*');

  // Verify sections load
  await expect(page.locator('text=Subject Information')).toBeVisible();
  await expect(page.locator('text=Diseases')).toBeVisible();
});
```

#### 2. Search Flow
```javascript
test('Search and filter phenopackets', async ({ page }) => {
  await page.goto('http://localhost:5173/phenopackets');

  // Use search
  await page.fill('[placeholder*="Search"]', 'kidney');
  await page.waitForTimeout(500); // Debounce

  // Apply filters
  await page.click('text=Female');
  await page.click('text=Has Variants');

  // Verify results update
  await expect(page.locator('.v-data-table tbody tr')).toHaveCount(10);
});
```

#### 3. Aggregations Dashboard
```javascript
test('Load all aggregation charts', async ({ page }) => {
  await page.goto('http://localhost:5173/aggregations');

  // Test each aggregation
  const aggregations = [
    'Sex Distribution',
    'Top Phenotypic Features',
    'Variant Pathogenicity',
  ];

  for (const agg of aggregations) {
    await page.selectOption('[data-test="aggregation-select"]', agg);
    await page.waitForSelector('svg'); // Chart rendered
    await expect(page.locator('.error-message')).not.toBeVisible();
  }
});
```

#### 4. Variant Navigation
```javascript
test('Navigate from variant to affected individuals', async ({ page }) => {
  await page.goto('http://localhost:5173/variants');

  // Click first variant
  await page.locator('[href*="/variants/"]').first().click();
  await page.waitForURL('**/variants/*');

  // Click affected individuals count
  await page.click('text=/\\d+ individuals/');
  await page.waitForURL('**/phenopackets?variant=*');

  // Verify filtered list
  await expect(page.locator('.phenopacket-card')).toHaveCount.greaterThan(0);
});
```

### Test Coverage Goals
- [ ] Home page loads without errors
- [ ] Phenopackets list pagination works
- [ ] Phenopacket detail page displays all sections
- [ ] Variants list and detail pages work
- [ ] Publications list and detail work
- [ ] Search returns results
- [ ] Filters update results correctly
- [ ] Aggregations dashboard loads all charts
- [ ] Navigation between views works
- [ ] Download JSON button works
- [ ] External links open correctly

### Checklist
- [ ] Install Playwright
- [ ] Configure playwright.config.js
- [ ] Write navigation tests
- [ ] Write search tests
- [ ] Write aggregation tests
- [ ] Write variant flow tests
- [ ] Add to CI/CD pipeline
- [ ] Document test commands

### CI/CD Integration
```yaml
# .github/workflows/frontend-tests.yml
- name: Install dependencies
  run: cd frontend && npm ci

- name: Install Playwright
  run: cd frontend && npx playwright install --with-deps

- name: Run E2E tests
  run: cd frontend && npm run test:e2e
```

### Timeline: 16 hours (2 days)
### Labels: `frontend`, `testing`, `p1`

---

## Issue #49: fix(frontend): remove all v1 legacy code

### Overview
Clean up deprecated v1 code after migration complete.

### Files to Remove

#### Deprecated API Functions
```javascript
// frontend/src/api/index.js - Remove these:
- getIndividuals()
- getIndividualsSexCount()
- getVariantsTypeCount()
- getPublicationsTypeCount()
- getIndividualsAgeOnsetCount()
// Keep ONLY v2 functions
```

#### Unused Components
```
frontend/src/components/tables/
├── TableIndividuals.vue     # DELETE (if unused)
├── TableVariants.vue        # DELETE (if v1 only)
└── TablePublications.vue    # DELETE (if v1 only)
```

#### Old Routes
```javascript
// frontend/src/router/index.js - Already redirected, can remove:
{
  path: '/individuals',
  redirect: '/phenopackets',  // Can simplify
}
```

### Code Audit Checklist
- [ ] Search for `getIndividuals` references
- [ ] Search for `/api/individuals` hardcoded URLs
- [ ] Search for `individual_id` (v1 naming)
- [ ] Search for `variant_ref` (v1 naming)
- [ ] Remove unused mixins
- [ ] Remove deprecated utils
- [ ] Remove old test files
- [ ] Update comments referencing v1

### Commands
```bash
# Find references
cd frontend
grep -r "getIndividuals\|/api/individuals" src/
grep -r "individual_id" src/ --exclude-dir=node_modules
rg "v1|legacy|deprecated" src/ -i
```

### Checklist
- [ ] Remove deprecated API functions
- [ ] Remove unused v1 components
- [ ] Simplify legacy redirects
- [ ] Remove commented-out v1 code
- [ ] Update imports
- [ ] Run ESLint and fix warnings
- [ ] Verify no broken imports
- [ ] Test all views still work

### Timeline: 8 hours (1 day)
### Labels: `frontend`, `refactor`, `p1`

---

## Issue #50: docs(frontend): update user documentation

### Overview
Complete user-facing documentation for phenopackets v2 frontend.

### Documentation Files

#### 1. User Guide
**File:** `docs/user-guide.md`

Contents:
- Getting started
- Browsing phenopackets
- Searching (advanced filters)
- Understanding variant data
- Reading aggregation charts
- Exporting data
- FAQ

#### 2. Developer Guide
**File:** `docs/developer-guide.md`

Contents:
- Setup instructions
- Architecture overview
- Component structure
- API integration
- Adding new visualizations
- Testing guide

#### 3. API Documentation
**File:** `docs/api-reference.md`

Contents:
- All v2 endpoints
- Request/response examples
- Pagination
- Filtering
- Error codes

#### 4. Changelog
**File:** `CHANGELOG.md`

Contents:
- v2.0.0 release notes
- Breaking changes from v1
- Migration guide
- New features

### README Updates
```markdown
# HNF1B Database

## Quick Start

\`\`\`bash
# Start services
make hybrid-up

# Start backend
make backend

# Start frontend
cd frontend && npm run dev
\`\`\`

Visit: http://localhost:5173

## Features

- ✅ Browse 864 phenopackets
- ✅ Search by HPO terms, genes, variants
- ✅ View detailed variant information
- ✅ Explore aggregations and statistics
- ✅ Compare clinical subgroups
- ✅ Export data
```

### Screenshot Updates
- [ ] Take screenshots of new views
- [ ] Add to docs/images/
- [ ] Embed in user guide
- [ ] Update README hero image

### Checklist
- [ ] Write user guide
- [ ] Write developer guide
- [ ] Document all API endpoints
- [ ] Create changelog
- [ ] Update README
- [ ] Add screenshots
- [ ] Review for accuracy
- [ ] Proofread

### Timeline: 6 hours (1 day)
### Labels: `documentation`, `p1`
