// @ts-check
/**
 * State-machine full-lifecycle Playwright E2E spec.
 *
 * Wave 7 / D.1 §10.4 — verifies the complete draft → in_review →
 * approved → published pipeline, state badge updates, transition modal
 * behaviour, and anonymous public visibility after publish.
 *
 * Strategy
 * --------
 * The spec uses two layers:
 *
 *   1. API layer  (request.newContext) — quick backend calls to:
 *        - Authenticate as admin  (POST /api/v2/auth/login)
 *        - Create a fresh test phenopacket  (POST /api/v2/phenopackets/)
 *        - Perform every transition via the REST endpoint so the browser
 *          tests start from a known state rather than fighting flaky form
 *          rendering for the creation step.
 *
 *   2. Browser layer  (page) — Playwright-controlled Chromium driving the
 *        real Vue / Vuetify UI to exercise:
 *        - Standard username/password login form
 *        - TransitionMenu activator (data-testid="menu-activator")
 *        - TransitionModal textarea + confirm button (data-testid="confirm-btn")
 *        - StateBadge v-chip text assertions
 *        - Anonymous-context detail-page load after publish
 *
 * Credentials
 * -----------
 * Uses the admin account that is created by `make db-create-admin` /
 * `scripts/create_admin_user.py`.  In CI the E2E job runs that step
 * before starting Playwright.  Passwords are read from env vars with
 * sensible defaults for local dev.
 *
 * ADMIN_USERNAME defaults to "admin"
 * ADMIN_PASSWORD defaults to "ChangeMe!Admin2025"  (matches backend/.env.example)
 * API_URL       defaults to "http://localhost:8000/api/v2"
 */

import { test, expect } from '@playwright/test';
import { apiLogin, primeAuthSession } from './helpers/auth';

// ---------------------------------------------------------------------------
// Constants / helpers
// ---------------------------------------------------------------------------

const API_BASE = process.env.VITE_API_URL || 'http://localhost:8000/api/v2';

const ADMIN_USERNAME = process.env.E2E_ADMIN_USERNAME || 'admin';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'ChangeMe!Admin2025';

// Unique test record ID — timestamp suffix avoids collisions between runs.
const RECORD_ID = `e2e-wave7-lifecycle-${Date.now()}`;

/**
 * Perform a state transition via the backend REST endpoint.
 * @param {import('@playwright/test').APIRequestContext} req
 * @param {string} token  Bearer token
 * @param {string} phenopacketId
 * @param {string} toState
 * @param {string} reason
 * @param {number} revision  Current revision for optimistic-locking
 * @returns {Promise<{state: string, revision: number}>}
 */
async function apiTransition(req, token, phenopacketId, toState, reason, revision) {
  const resp = await req.post(`${API_BASE}/phenopackets/${phenopacketId}/transitions`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { to_state: toState, reason, revision },
  });
  if (!resp.ok()) {
    throw new Error(`Transition to ${toState} failed: ${resp.status()} ${await resp.text()}`);
  }
  const body = await resp.json();
  return {
    state: body.phenopacket?.state ?? toState,
    revision: body.phenopacket?.revision ?? revision + 1,
  };
}

// ---------------------------------------------------------------------------
// Test
// ---------------------------------------------------------------------------

test('full state lifecycle: create draft → in_review → approved → published, anonymous can view', async ({
  page,
  context,
  request,
}) => {
  // -------------------------------------------------------------------------
  // Step 1 — API: authenticate as admin + create test phenopacket
  // -------------------------------------------------------------------------
  const adminTokens = await apiLogin(request, API_BASE, ADMIN_USERNAME, ADMIN_PASSWORD);
  const adminToken = adminTokens.accessToken;

  const createResp = await request.post(`${API_BASE}/phenopackets/`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: {
      phenopacket: {
        id: RECORD_ID,
        subject: { id: `subject-${RECORD_ID}`, sex: 'UNKNOWN_SEX' },
        metaData: {
          created: new Date().toISOString(),
          createdBy: 'e2e-test',
          resources: [
            {
              id: 'hp',
              name: 'Human Phenotype Ontology',
              namespacePrefix: 'HP',
              url: 'http://purl.obolibrary.org/obo/hp.owl',
              version: '2024-01-01',
              iriPrefix: 'http://purl.obolibrary.org/obo/HP_',
            },
          ],
          phenopacketSchemaVersion: '2.0',
        },
      },
    },
  });
  expect(createResp.ok(), `Create failed: ${await createResp.text()}`).toBeTruthy();
  const created = await createResp.json();
  let revision; // will be set from API re-fetch after browser transitions

  // Confirm initial state is draft
  expect(created.state).toBe('draft');

  // -------------------------------------------------------------------------
  // Step 2 — Browser: prime an authenticated session, navigate to detail page, verify badge
  // -------------------------------------------------------------------------
  await primeAuthSession(page, adminTokens);

  // Navigate to the detail page for our new record
  await page.goto(`/phenopackets/${RECORD_ID}`, { waitUntil: 'networkidle' });

  // StateBadge chip should show "Draft"
  await expect(page.locator('.v-chip', { hasText: 'Draft' }).first()).toBeVisible({
    timeout: 10_000,
  });

  // -------------------------------------------------------------------------
  // Step 3 — Browser: submit for review via TransitionMenu → TransitionModal
  // -------------------------------------------------------------------------

  // Open the State actions menu
  await page.locator('[data-testid="menu-activator"]').click();

  // Click the "Submit for review" transition item
  await page.locator('[data-testid="transition-item"]', { hasText: 'Submit for review' }).click();

  // TransitionModal: fill reason and confirm
  await page.locator('textarea').fill('Ready for review (E2E test)');
  await page.locator('[data-testid="confirm-btn"]').click();

  // Wait for the badge to update to "In review"
  await expect(page.locator('.v-chip', { hasText: 'In review' }).first()).toBeVisible({
    timeout: 15_000,
  });

  // -------------------------------------------------------------------------
  // Step 4 — API: advance to approved then published
  // (admin approves + publishes — done via API to stay fast)
  // -------------------------------------------------------------------------

  // Re-fetch current revision from the API (the browser transition already
  // bumped it; get the fresh value)
  const detailResp = await request.get(`${API_BASE}/phenopackets/${RECORD_ID}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  const detail = await detailResp.json();
  revision = detail.revision;

  // Approve
  const approved = await apiTransition(
    request,
    adminToken,
    RECORD_ID,
    'approved',
    'LGTM (E2E test)',
    revision
  );
  revision = approved.revision;

  // Publish
  await apiTransition(request, adminToken, RECORD_ID, 'published', 'Go live (E2E test)', revision);

  // -------------------------------------------------------------------------
  // Step 5 — Browser: curator sees published badge after page refresh
  // -------------------------------------------------------------------------
  await page.reload({ waitUntil: 'networkidle' });

  await expect(page.locator('.v-chip', { hasText: 'Published' }).first()).toBeVisible({
    timeout: 10_000,
  });

  // -------------------------------------------------------------------------
  // Step 6 — Anonymous context: detail page loads (public visibility gate)
  // -------------------------------------------------------------------------
  const anonCtx = await context.browser().newContext();
  const anonPage = await anonCtx.newPage();

  try {
    await anonPage.goto(`/phenopackets/${RECORD_ID}`, {
      waitUntil: 'networkidle',
      timeout: 30_000,
    });

    // Anonymous user should see the page (not a 404/error)
    const errorAlert = anonPage.locator('.v-alert[type="error"]');
    const hasError = await errorAlert.isVisible().catch(() => false);
    expect(hasError, 'Anonymous user got an error on published record').toBe(false);

    // The page should contain the record title/ID area (at least h1 visible)
    await expect(anonPage.locator('h1').first()).toBeVisible({ timeout: 10_000 });
  } finally {
    await anonCtx.close();
  }

  // -------------------------------------------------------------------------
  // Cleanup — archive the test record so subsequent runs don't conflict
  // -------------------------------------------------------------------------
  const finalDetail = await request.get(`${API_BASE}/phenopackets/${RECORD_ID}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  const finalData = await finalDetail.json();
  await apiTransition(
    request,
    adminToken,
    RECORD_ID,
    'archived',
    'E2E cleanup',
    finalData.revision
  ).catch(() => {
    // Archive is best-effort; don't fail the test if it errors
  });
});
