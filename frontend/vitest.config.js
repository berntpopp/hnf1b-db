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
      thresholds: {
        lines: 30,
        functions: 30,
        branches: 30,
        statements: 30,
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
