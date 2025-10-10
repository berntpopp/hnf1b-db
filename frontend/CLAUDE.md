# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HNF1B-db Frontend - A Vue 3 application for browsing and searching genetic variant data related to the HNF1B gene.

## Development Commands

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code (with auto-fix)
npm run lint

# Lint code (check only, no auto-fix)
npm run lint:check

# Format code with Prettier
npm run format

# Check code formatting (no auto-fix)
npm run format:check
```

## Architecture Overview

### Technology Stack
- **Framework**: Vue 3 with Composition API
- **Build Tool**: Vite 6.1.0
- **UI Library**: Vuetify 3 (Material Design)
- **Router**: Vue Router 4 with lazy-loaded routes
- **HTTP Client**: Axios with JSON:API format interceptors
- **Data Visualization**: D3.js (v7.9.0)
- **Icons**: Material Design Icons (@mdi/font and @mdi/js)
- **File Downloads**: file-saver

### Project Structure
- `src/api/` - API service layer
  - `index.js` - Centralized API service with axios client and all endpoints
  - `auth.js` - Authentication utilities
- `src/components/` - Reusable components
  - `analyses/` - Data visualization components (charts using D3.js)
  - `tables/` - Table components for data display
  - `AppBar.vue` - Main navigation header
  - `FooterBar.vue` - Application footer
  - `SearchCard.vue` - Global search component
- `src/views/` - Page-level components (routed views)
  - `Home.vue` - Landing page with statistics
  - `Individuals.vue` - Browse individuals
  - `PageIndividual.vue` - Individual detail view
  - `Variants.vue` - Browse variants
  - `PageVariant.vue` - Variant detail view
  - `Publications.vue` - Browse publications
  - `PagePublication.vue` - Publication detail view
  - `AggregationsDashboard.vue` - Statistical dashboard
  - `SearchResults.vue` - Search results page
  - `Login.vue` - User authentication
  - `User.vue` - User profile
- `src/router/` - Route definitions with dynamic imports
- `src/utils/` - Utility functions (authentication)
- `src/assets/` - Static assets and mixins

### API v2 Architecture (GA4GH Phenopackets)

**Base URL**: `http://localhost:8000/api/v2` (configured via `VITE_API_URL` in `.env`)

The API uses GA4GH Phenopackets v2 format with JSONB document storage. All data (individuals, variants, publications) is now stored in phenopacket documents.

#### Core Phenopackets Endpoints
- `GET /phenopackets/` - List phenopackets (supports `skip`, `limit`, `sex`, `has_variants` filters)
- `GET /phenopackets/{id}` - Get single phenopacket
- `GET /phenopackets/batch` - Batch fetch by IDs (prevents N+1 queries)
- `POST /phenopackets/search` - Advanced search with filters

#### Aggregation Endpoints
- `GET /phenopackets/aggregate/summary` - Overall statistics
- `GET /phenopackets/aggregate/sex-distribution` - Sex distribution
- `GET /phenopackets/aggregate/by-feature` - HPO term frequencies
- `GET /phenopackets/aggregate/by-disease` - Disease frequencies
- `GET /phenopackets/aggregate/variant-pathogenicity` - Pathogenicity distribution
- `GET /phenopackets/aggregate/kidney-stages` - Kidney disease stages

#### Clinical Endpoints
- `GET /clinical/renal-insufficiency` - Kidney disease cases
- `GET /clinical/genital-abnormalities` - Genital abnormalities
- `GET /clinical/diabetes` - Diabetes cases
- `GET /clinical/hypomagnesemia` - Hypomagnesemia cases

#### Authentication & Utilities
- `POST /auth/login` - JWT authentication
- `GET /auth/me` - Current user info
- `GET /hpo/autocomplete` - HPO term search

#### Pagination
- **v2 uses offset-based**: `skip` and `limit` parameters
- **Helper function**: `pageToSkipLimit(page, pageSize)` converts page-based to offset-based

#### Data Structure
Phenopackets contain:
- `subject` - Individual demographics (sex, age)
- `phenotypicFeatures[]` - HPO terms
- `interpretations[].diagnosis.genomicInterpretations[]` - Variants with VRS 2.0 format
- `diseases[]` - MONDO disease terms
- `metaData.externalReferences[]` - Publications (PMIDs)

### Code Quality Tools

#### ESLint Configuration (Modern Flat Config)
The project uses ESLint 9.20.0 with the modern flat config format (`eslint.config.js`):
- **Base**: ESLint recommended rules
- **Vue**: Vue 3 recommended rules from eslint-plugin-vue
- **Custom Rules**:
  - `no-unused-vars`: Error (with underscore patterns ignored)
  - `vue/multi-word-component-names`: Off
  - `vue/require-default-prop`: Error
  - `vue/require-prop-types`: Error
  - `vue/no-v-html`: Warn
  - `vue/component-tags-order`: Template → Script → Style
  - `vue/no-unused-components`: Error
  - `vue/no-unused-vars`: Error
  - `vue/padding-line-between-blocks`: Error
  - `vue/valid-v-slot`: Error (with modifiers allowed)
  - Environment-aware console/debugger rules
- **Ignored Paths**: node_modules, dist, build, coverage, .vscode, .idea

#### Prettier Configuration
Prettier 3.5.0 with Vue-specific settings:
- **Print Width**: 100 characters
- **Tab Width**: 2 spaces
- **Single Quotes**: Yes
- **Trailing Comma**: ES5
- **Semicolons**: Yes
- **Bracket Spacing**: Yes
- **Arrow Parens**: Always
- **End of Line**: Auto
- **Vue Indent Script/Style**: No

### Important Patterns
1. **Dynamic Route Imports**: All routes use `() => import()` with webpack chunk names for code splitting
2. **API Client Pattern**:
   - Single axios instance with base configuration from `VITE_API_URL`
   - JWT authentication via request interceptor (reads `access_token` from localStorage)
   - 401 error handling via response interceptor (auto-redirects to `/login`)
   - Direct response format (no JSON:API unwrapping)
   - 10-second timeout
3. **Search Implementation**:
   - POST endpoint with JSON body
   - Supports HPO terms, diseases, sex, and text query filters
   - Debounced search input in SearchCard component
4. **Pagination**:
   - Uses `skip`/`limit` (offset-based) instead of `page`/`page_size`
   - Helper: `pageToSkipLimit(page, pageSize)` converts formats
5. **Component Organization**:
   - Views handle routing and data fetching
   - Components are purely presentational
   - Charts use D3.js for custom visualizations
   - Tables implement sortable headers and pagination
6. **Batch Operations**:
   - Use `getPhenopacketsBatch()`, `getVariantsBatch()`, `getPhenotypicFeaturesBatch()` to prevent N+1 queries
   - Pass comma-separated IDs for efficient data fetching

### Build Configuration (Vite)
- **Plugins**: 
  - `@vitejs/plugin-vue` - Vue 3 support
  - `vite-plugin-vuetify` - Vuetify auto-imports
  - `vite-plugin-compression` - Asset compression (removed in recent update)
- **Path Alias**: `@` → `src/`
- **Server**: Polling enabled for file watching

### Development Notes
- **Testing**: No test framework is currently configured
- **Authentication**: JWT-based auth with token stored in localStorage
- **Environment**: Configure API URL via `.env` file (copy from `.env.example`)
- **State Management**: No global state management (Vuex/Pinia) - components manage local state
- **TypeScript**: Not configured - project uses plain JavaScript
- **CSS**: Uses Vuetify's built-in styling system
- **Performance**:
  - Route-level code splitting with dynamic imports
  - Lazy-loaded components for better initial load time
  - Batch API endpoints to prevent N+1 queries
  - Animated statistics on home page for better UX

### Testing the API Client

**Prerequisites:**
1. Start backend: `cd ../backend && make backend`
2. Create `.env`: `cp .env.example .env` (should have `VITE_API_URL=http://localhost:8000/api/v2`)
3. Start frontend: `npm run dev`

**Quick Backend Test:**
```bash
# Test phenopackets endpoint
curl "http://localhost:8000/api/v2/phenopackets/?skip=0&limit=5"

# Test sex distribution
curl "http://localhost:8000/api/v2/phenopackets/aggregate/sex-distribution"

# Test authentication
curl -X POST "http://localhost:8000/api/v2/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

**Frontend Browser Console Test:**
```javascript
// Test pagination helper
import { pageToSkipLimit, getPhenopackets } from '@/api';
const { skip, limit } = pageToSkipLimit(2, 10);
console.log(skip, limit); // Should be: 10, 10

// Test API call
const response = await getPhenopackets({ skip: 0, limit: 5 });
console.log(response.data); // Should show 5 phenopackets
```

### Recent Updates
- **API v2 Migration**: Complete rewrite of API client for GA4GH Phenopackets v2 format
- **Authentication**: Added JWT token interceptors for automatic auth header injection
- **Pagination**: Migrated from page-based to offset-based (`skip`/`limit`)
- **Batch Endpoints**: Added batch operations to prevent N+1 query problems
- **Environment Config**: API URL now configurable via `VITE_API_URL` environment variable
- **Legacy Compatibility**: Deprecated v1 functions remain for gradual migration
- Migrated from legacy ESLint config to modern flat config format
- Enhanced linting rules for Vue 3 best practices

## Git Commit Messages

### Conventional Commit Format

All frontend commits MUST follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

**Format:** `<type>(frontend): <short description>`

**Common Frontend Commit Examples:**
```bash
feat(frontend): add HPO term autocomplete to search component
fix(frontend): resolve pagination reset on filter change
refactor(frontend): extract phenopacket table to reusable component
style(frontend): update material design color scheme for dark mode
perf(frontend): implement virtual scrolling for large tables
docs(frontend): add JSDoc comments for API service methods
test(frontend): add unit tests for pagination helper functions
chore(frontend): upgrade Vite to 6.1 and update dependencies
```

### Frontend-Specific Commit Guidelines

**When Claude Code Completes a Frontend Task:**

After completing frontend work, Claude will provide a suggested commit message. Always use the `frontend` scope for all Vue.js application changes.

**Example Workflow:**
```bash
# After Claude completes work, terminal shows:

---
✅ Task completed successfully

Suggested commit message:
---
feat(frontend): migrate publications view to phenopackets v2 API (#34)

- Update getPhenopackets call to fetch publication data
- Extract publication references from JSONB metaData.externalReferences
- Update table columns to display PMID links
- Add loading states and error handling
---

# Review changes
git status
git diff

# Stage changes
git add src/views/Publications.vue src/api/index.js

# Commit with suggested message
git commit -m "feat(frontend): migrate publications view to phenopackets v2 API (#34)

- Update getPhenopackets call to fetch publication data
- Extract publication references from JSONB metaData.externalReferences
- Update table columns to display PMID links
- Add loading states and error handling"
```

### Frontend Commit Types

| Type | When to Use | Example |
|------|-------------|---------|
| `feat(frontend)` | New UI component or feature | `feat(frontend): add variant pathogenicity filter to search` |
| `fix(frontend)` | Bug fix in UI or behavior | `fix(frontend): correct date formatting in phenopacket table` |
| `refactor(frontend)` | Component restructuring | `refactor(frontend): split AggregationsDashboard into chart components` |
| `style(frontend)` | UI styling changes | `style(frontend): update Vuetify theme colors for accessibility` |
| `perf(frontend)` | Performance optimization | `perf(frontend): add memoization to expensive computed properties` |
| `test(frontend)` | Adding tests | `test(frontend): add component tests for SearchCard` |
| `chore(frontend)` | Dependencies or build config | `chore(frontend): update Vue to 3.5 and Vuetify to 3.7` |
| `docs(frontend)` | Documentation | `docs(frontend): add JSDoc for API client methods` |

### Common Frontend Commit Patterns

**Component Creation:**
```bash
feat(frontend): add PhenopacketDetailCard component for clinical data display
```

**View Migration:**
```bash
feat(frontend): migrate individuals view to phenopackets v2 format (#32)

- Rename Individuals.vue → Phenopackets.vue
- Update API calls from getIndividuals() to getPhenopackets()
- Transform JSONB data for table display
- Update router paths: /individuals → /phenopackets
```

**API Integration:**
```bash
feat(frontend): integrate phenopacket batch endpoint to prevent N+1 queries

- Add getPhenopacketsBatch() to API client
- Update detail views to use batch fetching
- Reduce API calls from 20 to 1 per page load
```

**Styling Updates:**
```bash
style(frontend): improve table responsiveness on mobile devices

- Add breakpoint-specific column hiding
- Update Vuetify grid layout for small screens
- Fix header alignment on tablets
```

**Bug Fixes:**
```bash
fix(frontend): prevent table pagination reset when applying filters (#28)

- Store current page in component state
- Preserve page number during filter changes
- Reset to page 1 only when filter values change
```

**Performance Improvements:**
```bash
perf(frontend): implement route-level code splitting for faster initial load

- Convert all route imports to dynamic imports
- Add webpack chunk names for better debugging
- Reduce initial bundle size from 800KB to 200KB
```

**Refactoring:**
```bash
refactor(frontend): extract D3.js chart logic to composable functions

- Create useBarChart and usePieChart composables
- Remove duplicated chart code from view components
- Add configurable chart options
```

**Dependency Updates:**
```bash
chore(frontend): update frontend dependencies to latest versions

- Vue 3.4 → 3.5
- Vuetify 3.6 → 3.7
- Vite 6.0 → 6.1
- Update vite.config.js for new Vite 6.1 API
```

### Multi-File Frontend Commits

**Related Component Changes:**
```bash
feat(frontend): add phenopacket export functionality

- Add ExportButton component with format selection
- Integrate file-saver for CSV/JSON export
- Update PhenopacketsView with export button
- Add export utilities to utils/export.js
```

**API + View Changes:**
```bash
feat(frontend): add advanced phenopacket search with HPO filters

- Add searchPhenopackets() POST endpoint to API client
- Create AdvancedSearchForm component with HPO autocomplete
- Update SearchResults view to display filtered results
- Add debounced search input for better UX
```

### Frontend-Specific Best Practices

1. **Always use `frontend` scope** for Vue.js app changes
2. **Mention component names** when modifying specific components
3. **Note API changes** if updating `src/api/index.js`
4. **Reference UI/UX improvements** for styling changes
5. **Mention performance metrics** for optimization commits
6. **Include before/after** for refactoring commits
7. **Note breaking changes** if changing component props/events

### Complete Example

```bash
# Multiple frontend files changed for one feature

feat(frontend): add phenopacket filtering by HPO terms (#35)

- Add HPO autocomplete component with debounced search
- Update PhenopacketsView with filter panel
- Integrate phenopackets search POST endpoint
- Add URL query params for shareable filter links
- Update router to handle filter state restoration

Files modified:
- src/views/Phenopackets.vue
- src/components/HpoAutocomplete.vue (new)
- src/api/index.js
- src/router/index.js
```

### Commit Message Validation

After Claude provides a suggested commit message:

1. **Review the changes**: `git diff`
2. **Verify scope is correct**: Should be `(frontend)` for Vue.js changes
3. **Check description accuracy**: Does it match what actually changed?
4. **Confirm issue reference**: Is the issue number correct?
5. **Add details if needed**: Expand the body for complex changes
6. **Stage and commit**: Use the suggested message or modify as needed

**Quick Reference:**
- ✅ `feat(frontend): add new component`
- ✅ `fix(frontend): resolve bug in view`
- ✅ `style(frontend): update styling`
- ❌ `feat: add new component` (missing scope)
- ❌ `Update frontend` (missing type)
- ❌ `feat(backend): update API` (wrong scope - should be in backend commit)