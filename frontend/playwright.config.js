// @ts-check
import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for HNF1B DB end-to-end tests.
 *
 * Wave 6 Task 1: scaffolds the Playwright runner so CI can exercise the
 * existing `tests/e2e/*.spec.js` suite. Specs assume the frontend is on
 * :5174 and the backend on :8000 — we start the Vite dev server via
 * `webServer` here, and CI brings up the backend + Postgres + Redis
 * stack separately. If `E2E_BASE_URL` is set (e.g. by CI pointing at a
 * preview deploy), `webServer` is skipped.
 *
 * Port 5174 is used instead of the default 5173 to avoid collision with
 * other Vite dev servers that may be running on this machine.
 */

const baseURL = process.env.E2E_BASE_URL || 'http://localhost:5174';
const useWebServer = !process.env.E2E_BASE_URL;

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
  ],

  // Start the Vite dev server for local runs and CI (unless E2E_BASE_URL
  // already points at a running instance). The backend is expected to be
  // reachable at VITE_API_URL before the tests start — in CI that is
  // wired up by the e2e-tests workflow job.
  webServer: useWebServer
    ? {
        command: 'npm run dev -- --port 5174 --strictPort',
        port: 5174,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      }
    : undefined,
});
