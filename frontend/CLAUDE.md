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

### Key API Endpoints
Base URL: `http://localhost:8000/api`

**Data Collections:**
- `/individuals/` - Individual patient data
- `/variants/` - Genetic variant information
- `/publications/` - Related publications
- `/proteins/` - Protein structure data
- `/search/` - Global search across collections

**Aggregation Endpoints:**
- `/aggregations/summary` - Top-level statistics
- `/aggregations/individuals/sex-count` - Sex distribution
- `/aggregations/individuals/age-onset-count` - Age of onset distribution
- `/aggregations/individuals/cohort-count` - Cohort distribution
- `/aggregations/individuals/family-history-count` - Family history stats
- `/aggregations/individuals/detection-method-count` - Detection methods
- `/aggregations/individuals/segregation-count` - Segregation analysis
- `/aggregations/individuals/phenotype-described-count` - Phenotype data
- `/aggregations/variants/type-count` - Variant types
- `/aggregations/variants/individual-count-by-type` - Individuals by variant type
- `/aggregations/variants/newest-classification-verdict-count` - Classification verdicts
- `/aggregations/variants/small_variants` - Small variant data for protein plot
- `/aggregations/publications/type-count` - Publication types
- `/aggregations/publications/cumulative-count` - Publications over time

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
2. **JSON:API Format**: Response interceptor automatically unwraps `response.data.data` and preserves `meta`
3. **Search Implementation**: 
   - Centralized search endpoint with optional collection filtering
   - Support for reduced document responses
   - Debounced search input in SearchCard component
4. **API Client Pattern**: 
   - Single axios instance with base configuration
   - Consistent error handling
   - 10-second timeout
5. **Component Organization**:
   - Views handle routing and data fetching
   - Components are purely presentational
   - Charts use D3.js for custom visualizations
   - Tables implement sortable headers and pagination

### Build Configuration (Vite)
- **Plugins**: 
  - `@vitejs/plugin-vue` - Vue 3 support
  - `vite-plugin-vuetify` - Vuetify auto-imports
  - `vite-plugin-compression` - Asset compression (removed in recent update)
- **Path Alias**: `@` → `src/`
- **Server**: Polling enabled for file watching

### Development Notes
- **Testing**: No test framework is currently configured
- **Authentication**: Basic auth utilities in place (src/utils/auth.js)
- **Environment**: No environment files (.env) are used; API URL is hardcoded
- **State Management**: No global state management (Vuex/Pinia) - components manage local state
- **TypeScript**: Not configured - project uses plain JavaScript
- **CSS**: Uses Vuetify's built-in styling system
- **Performance**: 
  - Route-level code splitting with dynamic imports
  - Lazy-loaded components for better initial load time
  - Animated statistics on home page for better UX

### Recent Updates
- Migrated from legacy ESLint config to modern flat config format
- Removed deprecated .eslintignore (now using ignores in config)
- Enhanced linting rules for Vue 3 best practices
- Added comprehensive npm scripts for linting and formatting
- Improved code quality across all components