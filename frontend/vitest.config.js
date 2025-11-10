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

    // Use vmThreads pool for WSL2 compatibility
    // Both 'threads' and 'forks' have known timeout issues in WSL2 environment
    // vmThreads uses isolated contexts but runs in main process (no worker communication issues)
    pool: process.env.CI ? 'threads' : 'vmThreads',

    // Increase pool startup timeout for WSL2 (default is 10000ms)
    poolOptions: {
      vmThreads: {
        memoryLimit: '512MB',
      },
      threads: {
        singleThread: false,
      },
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
