import { defineConfig } from 'vitest/config';
import path from 'path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Minimal working configuration for Vitest 4.0.7
// Start with config/utility tests, add Vue component testing later
export default defineConfig({
  // Test-specific configuration
  test: {
    // Jest-compatible global API (describe, it, expect, etc.)
    globals: true,

    // Node environment for config/utility tests
    // Switch to 'happy-dom' when testing Vue components
    environment: 'node',

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

    // Test file patterns
    include: ['tests/unit/**/*.spec.js'],
  },

  // Path alias resolution
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
});
