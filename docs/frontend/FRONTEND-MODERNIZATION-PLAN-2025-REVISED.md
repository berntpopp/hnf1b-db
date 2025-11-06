# HNF1B-DB Frontend Modernization Plan (2025) - REVISED

**Date:** 2025-11-06
**Status:** APPROVED
**Priority:** HIGH
**Revision:** Based on agde-frontend actual implementation + 2025 best practices

**Changes from Original:**
- ✅ Removed coverage thresholds (blocking development)
- ✅ Fixed Vitest config to use `mergeConfig` (DRY principle)
- ✅ Fixed setup.js with full Vuetify plugin (prevents test crashes)
- ✅ Corrected test pattern to `*.spec.js` (matches agde)
- ✅ Removed unnecessary compression plugin (KISS principle)
- ✅ Added Vite 6 `warmup` feature (proven optimization)
- ✅ Simplified ESLint globals (let vitest handle)
- ✅ Added Vuetify-specific Vitest config (`deps.inline`)

---

## Executive Summary

This plan addresses **critical gaps** in frontend infrastructure based on **agde-frontend proven patterns** and **2025 best practices**.

### Critical Gaps Identified

1. ❌ **NO TESTING FRAMEWORK** - Zero test coverage
2. ❌ **NO FRONTEND CI/CD** - Only backend tested
3. ❌ **NO PRE-COMMIT HOOKS** - No quality enforcement
4. ❌ **NO DEPENDABOT** - Manual dependency updates

### Guiding Principles

**This revision strictly follows:**
- ✅ **KISS** - Only proven patterns from agde-frontend
- ✅ **DRY** - Use `mergeConfig`, no duplication
- ✅ **YAGNI** - No speculative features (removed compression)
- ✅ **Incremental** - No blocking thresholds

---

## Phase 1: Testing Infrastructure

### 1.1 Install Dependencies

```bash
cd frontend
npm install -D vitest@^4.0.7 \
  @vitest/ui@^4.0.7 \
  @vitest/coverage-v8@^4.0.7 \
  @vue/test-utils@^2.4.6 \
  happy-dom@^20.0.10
```

### 1.2 Create `vitest.config.js`

**CORRECTED - Uses mergeConfig to avoid duplication (DRY principle)**

**File:** `frontend/vitest.config.js`

```javascript
import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

// Vitest docs: "Use mergeConfig to avoid duplication"
// Reference: https://vitest.dev/config/
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      // Jest-compatible global API (describe, it, expect, etc.)
      globals: true,

      // Faster DOM environment than jsdom
      environment: 'happy-dom',

      // Setup file for global test configuration
      setupFiles: ['./tests/setup.js'],

      // Coverage configuration
      coverage: {
        provider: 'v8', // Native V8 coverage (faster than Istanbul)
        reporter: ['text', 'json', 'html'],
        exclude: [
          'src/main.js',
          'src/router/index.js',
          '**/node_modules/**',
          '**/tests/**',
          '**/*.config.js',
        ],
        // NO THRESHOLDS - Start without, add gradually
        // Best practice: Don't enforce coverage % on day 1
        // Reference: https://vitest.dev/guide/coverage
      },

      // Vuetify-specific optimization (Vitest 4.0 requirement)
      // Fixes CSS import errors with Vuetify
      server: {
        deps: {
          inline: ['vuetify'],
        },
      },

      // Test file patterns - matches agde-frontend
      include: ['tests/unit/**/*.spec.js'],
    },
  })
);
```

**Key Changes from Original:**
- ✅ Uses `mergeConfig` - inherits vite config (no duplication)
- ✅ NO coverage thresholds - won't block development
- ✅ Added `server.deps.inline` - Vuetify compatibility
- ✅ Correct test pattern - `*.spec.js` (matches agde)

### 1.3 Create `tests/setup.js`

**CORRECTED - Full Vuetify plugin setup (prevents test crashes)**

**File:** `frontend/tests/setup.js`

```javascript
/**
 * Global test setup for Vitest
 *
 * Based on agde-frontend proven patterns
 * Reference: /mnt/c/development/agde-frontend/tests/setup.js
 */

import { config } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

// Polyfill ResizeObserver for Vuetify components
// happy-dom doesn't include ResizeObserver by default
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Create Vuetify instance for tests
// CRITICAL: Without this, Vuetify components will crash with
// "Error: [Vuetify] Could not find defaults instance"
const vuetify = createVuetify({
  components,
  directives,
});

// Register Vuetify plugin globally for all tests
config.global.plugins = [vuetify];
```

**Key Changes from Original:**
- ✅ Creates actual Vuetify plugin instance
- ✅ Uses `globalThis.ResizeObserver` (cleaner than window)
- ✅ Removed unnecessary IntersectionObserver mock
- ✅ Removed matchMedia mock (not needed with happy-dom)

### 1.4 Create Test Directory Structure

```bash
mkdir -p frontend/tests/unit/{components,config,utils}
```

### 1.5 Create Example Tests

**File:** `frontend/tests/unit/config/app.spec.js`

```javascript
import { describe, it, expect } from 'vitest';
import { API_CONFIG, FEATURES, VIZ_CONFIG } from '@/config/app';

describe('API_CONFIG', () => {
  it('has required configuration keys', () => {
    expect(API_CONFIG).toHaveProperty('MAX_VARIANTS_FOR_PRIORITY_SORT');
    expect(API_CONFIG).toHaveProperty('DEFAULT_PAGE_SIZE');
    expect(API_CONFIG).toHaveProperty('MAX_PAGE_SIZE');
  });

  it('has sensible default values', () => {
    expect(API_CONFIG.MAX_VARIANTS_FOR_PRIORITY_SORT).toBe(1000);
    expect(API_CONFIG.DEFAULT_PAGE_SIZE).toBe(100);
    expect(API_CONFIG.MAX_PAGE_SIZE).toBe(1000);
  });
});

describe('VIZ_CONFIG', () => {
  it('has HNF1B gene coordinates', () => {
    expect(VIZ_CONFIG.HNF1B_GENE.chromosome).toBe('17');
    expect(VIZ_CONFIG.HNF1B_GENE.start).toBe(37680000);
    expect(VIZ_CONFIG.HNF1B_GENE.end).toBe(37750000);
  });
});
```

### 1.6 Update `package.json`

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest watch",
    "test:coverage": "vitest run --coverage",
    "test:ui": "vitest --ui"
  }
}
```

---

## Phase 2: Integrated Linting

**Status:** Unchanged from original - already correct

**File:** `frontend/eslint.config.js`

```javascript
import js from '@eslint/js';
import pluginVue from 'eslint-plugin-vue';
import eslintConfigPrettier from 'eslint-config-prettier';
import eslintPluginPrettier from 'eslint-plugin-prettier';

export default [
  js.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  eslintConfigPrettier,

  {
    files: ['**/*.{js,mjs,cjs,vue}'],

    plugins: {
      prettier: eslintPluginPrettier,
    },

    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      // SIMPLIFIED - Let vitest config handle globals
      // No need to manually list them here
    },

    rules: {
      'prettier/prettier': 'error',

      // Vue rules
      'vue/multi-word-component-names': 'warn',
      'vue/no-v-html': 'warn',

      // Code quality
      'no-unused-vars': ['warn', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
      }],
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'no-debugger': 'warn',
    },
  },

  {
    ignores: [
      'node_modules/**',
      'dist/**',
      'coverage/**',
      '.vite/**',
      '.husky/**',
    ],
  },
];
```

**Installation:**
```bash
npm install -D eslint-plugin-prettier@^5.2.3 eslint-config-prettier@^10.1.8
```

---

## Phase 3: Pre-commit Hooks

**Status:** Unchanged from original - matches agde-frontend exactly

### 3.1 Install Dependencies

```bash
npm install -D husky@^9.1.7 \
  lint-staged@^16.2.6 \
  @commitlint/cli@^20.1.0 \
  @commitlint/config-conventional@^20.0.0
```

### 3.2 Initialize Husky

```bash
npx husky init
```

### 3.3 Create `.lintstagedrc.json`

```json
{
  "*.{js,vue}": ["eslint --fix", "prettier --write"],
  "*.{json,css,scss,md}": ["prettier --write"]
}
```

### 3.4 Create `commitlint.config.js`

```javascript
export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'scope-enum': [
      2,
      'always',
      ['frontend', 'backend', 'api', 'db', 'ci', 'docs'],
    ],
    'body-max-line-length': [2, 'always', 100],
  },
};
```

### 3.5 Create `.husky/pre-commit`

```bash
#!/usr/bin/env sh

npm run lint:staged

# Ensure package.json and package-lock.json are committed together
STAGED_FILES=$(git diff --name-only --cached)
HAS_PACKAGE_JSON=$(echo "$STAGED_FILES" | grep -c "^package\.json$" || true)
HAS_PACKAGE_LOCK=$(echo "$STAGED_FILES" | grep -c "^package-lock\.json$" || true)

if [ "$HAS_PACKAGE_JSON" -eq 1 ] && [ "$HAS_PACKAGE_LOCK" -eq 0 ]; then
  echo ""
  echo "❌ ERROR: package.json is staged but package-lock.json is not!"
  echo "Fix: git add package-lock.json"
  exit 1
fi
```

### 3.6 Create `.husky/commit-msg`

```bash
#!/usr/bin/env sh
npx --no -- commitlint --edit $1
```

### 3.7 Update `package.json`

```json
{
  "scripts": {
    "prepare": "husky",
    "lint:staged": "lint-staged"
  }
}
```

---

## Phase 4: Enhanced Makefile

**Status:** Unchanged from original - correct

(Full Makefile content same as original plan)

---

## Phase 5: Frontend CI/CD

### 5.1 Create `.github/workflows/frontend-ci.yml`

**CORRECTED - Added concurrency control (saves GitHub Actions minutes)**

```yaml
name: Frontend CI

on:
  push:
    branches: [main, develop]
    paths:
      - 'frontend/**'
      - '.github/workflows/frontend-ci.yml'
  pull_request:
    branches: [main, develop]
    paths:
      - 'frontend/**'

# Cancel in-progress runs for same workflow and ref
# Saves GitHub Actions minutes
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    name: Lint & Format Check
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v6
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: frontend
        run: npm ci

      - name: Run ESLint
        working-directory: frontend
        run: npm run lint:eslint

      - name: Check Prettier
        working-directory: frontend
        run: npm run lint:prettier

  test:
    name: Test Suite
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v6
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: frontend
        run: npm ci

      - name: Run tests with coverage
        working-directory: frontend
        run: npm run test:coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v5
        if: always()
        with:
          files: ./frontend/coverage/lcov.info
          flags: frontend
          fail_ci_if_error: false

  build:
    name: Production Build
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v6
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: frontend
        run: npm ci

      - name: Build
        working-directory: frontend
        run: npm run build

      - name: Upload artifacts
        uses: actions/upload-artifact@v5
        with:
          name: frontend-dist-${{ github.sha }}
          path: frontend/dist/
          retention-days: 7

  frontend-ci-success:
    name: Frontend CI Success
    if: always()
    needs: [lint, test, build]
    runs-on: ubuntu-latest

    steps:
      - name: Check all jobs
        run: |
          if [ "${{ needs.lint.result }}" != "success" ] || \
             [ "${{ needs.test.result }}" != "success" ] || \
             [ "${{ needs.build.result }}" != "success" ]; then
            echo "❌ Frontend CI failed"
            exit 1
          fi
          echo "✅ Frontend CI passed"
```

### 5.2 Create `.github/workflows/frontend-code-quality.yml`

(Same as original plan)

---

## Phase 6: Dependabot

**Status:** Unchanged from original - correct

(Same as original plan)

---

## Phase 7: Build Optimization

**CORRECTED - Removed compression, added warmup**

### 7.1 Install Optimization Plugins

```bash
cd frontend
npm install -D rollup-plugin-visualizer@^6.0.5 terser@^5.43.1
```

**REMOVED:** `vite-plugin-compression` (unnecessary, agde doesn't use it)

### 7.2 Update `vite.config.js`

**File:** `frontend/vite.config.js`

```javascript
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';
import vuetify from 'vite-plugin-vuetify';
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig({
  plugins: [
    vue(),
    vuetify({ autoImport: true }),

    // Bundle size visualization (all environments)
    visualizer({
      filename: 'dist/bundle-analysis.html',
      open: false,
      gzipSize: true,
      brotliSize: true,
      template: 'treemap',
    }),
  ],

  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    // Prevent duplicate Vue instances
    dedupe: ['vue', 'vuetify'],
  },

  optimizeDeps: {
    include: ['vue', 'vue-router', 'vuetify', 'd3', 'axios'],
  },

  server: {
    port: 5173,
    strictPort: false,

    // Vite 6 feature: Pre-transform frequently accessed files
    // Proven optimization from agde-frontend
    warmup: {
      clientFiles: [
        './src/views/Home.vue',
        './src/views/PageVariant.vue',
        './src/components/gene/HNF1BGeneVisualization.vue',
        './src/components/gene/HNF1BProteinVisualization.vue',
      ],
    },

    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },

    watch: {
      // Only use polling on Linux/WSL
      usePolling: process.platform === 'linux',
    },
  },

  build: {
    sourcemap: true,

    rollupOptions: {
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router'],
          'vuetify': ['vuetify'],
          'd3': ['d3'],
          'axios': ['axios'],
        },
      },
    },

    target: 'esnext',
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },
  },
});
```

**Key Changes from Original:**
- ✅ Removed compression plugin (unnecessary)
- ✅ Added `warmup` for heavy components (Vite 6 feature)
- ✅ Added `dedupe` to prevent duplicate Vue instances
- ✅ Simplified - only proven optimizations from agde

---

## Implementation Roadmap

**REVISED - Simplified timeline**

### Sprint 1: Foundation (Week 1) - 12 hours

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 1 | Install Vitest + deps | 0.5h | ⏸️ |
| 1 | Create vitest.config.js (mergeConfig) | 1h | ⏸️ |
| 1 | Create tests/setup.js (full Vuetify) | 1h | ⏸️ |
| 1 | Create 3 example tests | 2h | ⏸️ |
| 1 | Verify tests pass | 0.5h | ⏸️ |
| 2 | Install linting deps | 0.5h | ⏸️ |
| 2 | Update eslint.config.js | 1h | ⏸️ |
| 2 | Run lint:fix on codebase | 1h | ⏸️ |
| 3 | Install Husky + lint-staged + commitlint | 0.5h | ⏸️ |
| 3 | Create all hook files | 1h | ⏸️ |
| 3 | Test hooks | 1h | ⏸️ |
| - | Buffer for issues | 2h | ⏸️ |

**Deliverable:** Working tests, integrated linting, pre-commit hooks

### Sprint 2: Automation (Week 2) - 6 hours

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 4 | Update Makefile | 1h | ⏸️ |
| 5 | Create frontend-ci.yml | 1.5h | ⏸️ |
| 5 | Create code-quality.yml | 1h | ⏸️ |
| 5 | Test workflows on PR | 1h | ⏸️ |
| 6 | Update dependabot.yml | 0.5h | ⏸️ |
| - | Buffer for issues | 1h | ⏸️ |

**Deliverable:** CI/CD pipeline, Dependabot

### Sprint 3: Optimization & Coverage (Week 3) - 10 hours

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 7 | Install optimization plugins | 0.5h | ⏸️ |
| 7 | Update vite.config.js | 1h | ⏸️ |
| 7 | Test build + analyze bundle | 0.5h | ⏸️ |
| - | Write component tests | 3h | ⏸️ |
| - | Write utility tests | 2h | ⏸️ |
| - | Write config tests | 1h | ⏸️ |
| - | Documentation updates | 1h | ⏸️ |
| - | Buffer for issues | 1h | ⏸️ |

**Deliverable:** Optimized build, 30%+ coverage, complete docs

**Total Time:** 28 hours (down from 34 hours)

---

## Verification Checklist

### Phase 1: Testing

- [ ] `npm test` - All tests pass
- [ ] `npm run test:coverage` - Coverage report generated (no threshold enforcement)
- [ ] `npm run test:ui` - Opens at http://localhost:51204
- [ ] Tests discover `*.spec.js` files in `tests/unit/`
- [ ] Vuetify components render without errors

### Phase 2: Linting

- [ ] `npm run lint` - Passes
- [ ] `npm run lint:fix` - Auto-fixes issues
- [ ] No conflicts between ESLint and Prettier

### Phase 3: Pre-commit

- [ ] Bad commit message rejected
- [ ] Good commit message accepted
- [ ] Linting runs automatically
- [ ] Package lock sync enforced

### Phase 4: Makefile

- [ ] `make help` - Shows colored output
- [ ] `make ci` - Runs all checks
- [ ] Matches GitHub Actions exactly

### Phase 5: CI/CD

- [ ] Frontend CI workflow runs on push
- [ ] Concurrency cancels duplicate runs
- [ ] Coverage uploaded to Codecov
- [ ] Build artifacts created

### Phase 6: Dependabot

- [ ] Grouped update PRs created weekly
- [ ] Vue core dependencies grouped

### Phase 7: Build

- [ ] `npm run build` - Succeeds
- [ ] `dist/bundle-analysis.html` - Created
- [ ] Chunks split correctly (vue-vendor, vuetify, d3)
- [ ] console.log removed from production

---

## Success Metrics

| Metric | Start | Week 1 | Week 2 | Week 3 | Target |
|--------|-------|--------|--------|--------|--------|
| Test Coverage | 0% | 10% | 20% | 30% | 30%+ |
| CI Workflows | 0 | 0 | 2 | 2 | 2 |
| Pre-commit Hooks | 0 | 3 | 3 | 3 | 3 |

**Realistic Expectations:**
- Week 1: Basic infrastructure
- Week 2: Automation active
- Week 3: 30% coverage (critical paths only)

**No arbitrary thresholds - focus on critical code paths**

---

## What Was Removed (YAGNI)

1. ❌ Coverage thresholds (60%) - Blocks development
2. ❌ Compression plugin - Unnecessary, agde doesn't use it
3. ❌ Manual ESLint globals - Vitest handles automatically
4. ❌ Aspirational 60% coverage goal - Unrealistic day 1

## What Was Added (agde-frontend patterns)

1. ✅ `mergeConfig` - DRY principle
2. ✅ Full Vuetify setup - Prevents crashes
3. ✅ `warmup` config - Proven optimization
4. ✅ `deps.inline` - Vuetify compatibility
5. ✅ `dedupe` - Prevents duplicate Vue
6. ✅ Concurrency control - Saves CI minutes

---

## Appendix: Comparison to Original Plan

| Aspect | Original | Revised | Reason |
|--------|----------|---------|--------|
| Vitest config | Separate file | mergeConfig | DRY |
| Coverage thresholds | 60% enforced | None | KISS |
| Setup file | Basic mocks | Full Vuetify | Functional |
| Test pattern | `*.test.js` | `*.spec.js` | agde match |
| Compression | Included | Removed | YAGNI |
| Warmup | Missing | Added | Proven opt |
| Timeline | 34h | 28h | Simplified |
| Sprint 1 target | 20% coverage | 10% coverage | Realistic |
| Sprint 3 target | 60% coverage | 30% coverage | Realistic |

---

**Document Status:** APPROVED (Revised)
**Last Updated:** 2025-11-06
**Next Review:** After Sprint 1 completion
