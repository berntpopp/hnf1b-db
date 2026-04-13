import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import path from 'path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Vitest configuration for Vue 3 + Composition API component testing
export default defineConfig({
  plugins: [vue()],

  // Test-specific configuration
  test: {
    // Jest-compatible global API (describe, it, expect, etc.)
    globals: true,

    // happy-dom for Vue component testing (faster than jsdom)
    environment: 'happy-dom',

    // Force Vite to transform Vuetify through its pipeline so CSS
    // imports from vuetify/lib/**/*.css don't hit the native Node
    // ESM loader (which errors with `Unknown file extension ".css"`
    // in the threads pool on CI). Without this, specs that mount
    // Vuetify components fail to load on CI even though they pass
    // locally in vmThreads mode.
    server: {
      deps: {
        inline: ['vuetify'],
      },
    },

    // Use vmThreads pool for WSL2 compatibility
    // Both 'threads' and 'forks' have known timeout issues in WSL2 environment
    // vmThreads uses isolated contexts but runs in main process (no worker communication issues)
    pool: process.env.CI ? 'threads' : 'vmThreads',

    // Pool configuration (top-level in Vitest 4, previously under poolOptions)
    vmThreads: {
      memoryLimit: '512MB',
    },
    threads: {
      singleThread: false,
    },

    // Global test setup — polyfills (ResizeObserver, visualViewport) and
    // Vuetify default plugin registration. Must run in every test environment.
    setupFiles: ['tests/setup.js'],

    // Timeout configuration
    testTimeout: 10000, // 10 seconds for individual tests
    hookTimeout: 10000, // 10 seconds for hooks (beforeEach, afterEach)

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
        '**/*.spec.js',
      ],
      // Wave 6 Task 1: floor is 30% because Wave 5 added characterization
      // coverage (stores, composables, a handful of views + components)
      // but not comprehensive unit coverage across every Vue SFC. The
      // threshold ratchets up in follow-on work as Task 4 (top-5 component
      // tests) and beyond land.
      //
      // Per-file thresholds (Wave 6 review follow-up): the 5 components
      // that Task 4 added tests for must not regress below their
      // current floors. Without per-file gates the overall 30% floor
      // is trivially bypassed by adding a large untested SFC, which
      // would mask coverage regressions on these components.
      //
      // Floors are set ~5% below the current coverage numbers to
      // tolerate minor fluctuations while still catching meaningful
      // regressions. Ratchet upward as follow-up PRs add more tests
      // (especially for SearchCard / HPOAutocomplete, which only
      // cover the mount / search-gate paths today).
      thresholds: {
        lines: 30,
        functions: 30,
        branches: 30,
        statements: 30,
        'src/components/SearchCard.vue': {
          lines: 20,
          functions: 5,
          branches: 5,
          statements: 20,
        },
        'src/components/FacetedFilters.vue': {
          lines: 70,
          functions: 60,
          branches: 65,
          statements: 70,
        },
        'src/components/common/AppDataTable.vue': {
          lines: 60,
          functions: 35,
          branches: 40,
          statements: 60,
        },
        'src/components/HPOAutocomplete.vue': {
          lines: 30,
          functions: 5,
          branches: 15,
          statements: 30,
        },
        'src/components/VariantAnnotator.vue': {
          lines: 55,
          functions: 55,
          branches: 50,
          statements: 55,
        },
      },
    },

    // Test file patterns
    include: ['tests/unit/**/*.spec.js', 'tests/components/**/*.spec.js'],
  },

  // Path alias resolution
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
});
