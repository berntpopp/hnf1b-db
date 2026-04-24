// @ts-check
import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for HNF1B DB end-to-end tests.
 *
 * Wave 6 Task 1: scaffolds the Playwright runner so CI can exercise the
 * existing `tests/e2e/*.spec.js` suite. Specs assume the frontend is on
 * :5173 and the backend on :8000 — we start the Vite dev server via
 * `webServer` here, and CI brings up the backend + Postgres + Redis
 * stack separately. If `E2E_BASE_URL` is set (e.g. by CI pointing at a
 * preview deploy), `webServer` is skipped.
 */

const baseURL = process.env.E2E_BASE_URL || 'http://localhost:5173';
const useWebServer = !process.env.E2E_BASE_URL;
// Keep Firefox coverage intentionally narrow: it adds a second-browser run for
// the axe-based accessibility smoke suite without moving broader UI coverage
// out of Chromium.
const FIREFOX_A11Y_FILE_RE = /(?:^|\/)tests\/e2e\/accessibility\.spec\.js$/;

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/*.spec.js',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  timeout: 60_000,

  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox-a11y',
      testMatch: FIREFOX_A11Y_FILE_RE,
      use: { ...devices['Desktop Firefox'] },
    },
  ],

  // Start the Vite dev server for local runs and CI (unless E2E_BASE_URL
  // already points at a running instance). The backend is expected to be
  // reachable at VITE_API_URL before the tests start — in CI that is
  // wired up by the e2e-tests workflow job.
  webServer: useWebServer
    ? {
        command: 'npm run dev -- --port 5173 --strictPort',
        port: 5173,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      }
    : undefined,
});
