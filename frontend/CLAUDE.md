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