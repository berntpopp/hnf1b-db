// @ts-check
/**
 * Invariant I1 — dual-read E2E spec.
 *
 * Wave 7 / D.1 §10.2 — verifies that after a clone-to-draft edit on a
 * published phenopacket:
 *
 *   • Curator / admin sees the NEW draft content (working copy).
 *   • Anonymous sees the OLD published content (head-published revision).
 *
 * This is the canonical test of invariant I1 from the spec:
 *   "phenopackets.state = 'published' does NOT imply that phenopackets.phenopacket
 *    (the working copy) equals the public copy. The only authoritative public
 *    content is phenopacket_revisions[head_published_revision_id].content_jsonb."
 *
 * Strategy
 * --------
 * All state setup is done via the API so the browser tests only need to
 * exercise the two read paths that matter for I1:
 *
 *   1. API layer — set up a published phenopacket with a known subject ID
 *      ("ORIGINAL"), then perform clone-to-draft via PUT /phenopackets/{id}
 *      (subject ID becomes "CLONE-DRAFT").  The public head still points to
 *      the revision whose subject ID is "ORIGINAL".
 *
 *   2. Browser layer (admin context) — navigate to the detail page and
 *      assert the working-copy subject ID ("CLONE-DRAFT") is visible.
 *
 *   3. Browser layer (anonymous context) — navigate to the same URL and
 *      assert the old subject ID ("ORIGINAL") is visible, NOT "CLONE-DRAFT".
 *
 * The "re-publish convergence" phase is NOT covered — advancing a cloned
 * draft through review while the outer record stays `state='published'`
 * is a spec gap for D.1 (no `('published', 'in_review')` rule in the
 * guard matrix). See D.2 follow-up.
 *
 * Credentials
 * -----------
 * Same env-var convention as state-lifecycle.spec.js.
 */

import { test, expect } from '@playwright/test';

// ---------------------------------------------------------------------------
// Constants / helpers
// ---------------------------------------------------------------------------

const BASE = process.env.E2E_BASE_URL || 'http://localhost:5173';
const API_BASE = process.env.VITE_API_URL || 'http://localhost:8000/api/v2';

const ADMIN_USERNAME = process.env.E2E_ADMIN_USERNAME || 'admin';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'ChangeMe!Admin2025';

const RECORD_ID = `e2e-wave7-i1-${Date.now()}`;
const ORIGINAL_SUBJECT_ID = `original-subject-${Date.now()}`;
const DRAFT_SUBJECT_ID = `draft-subject-${Date.now()}`;

/**
 * Obtain a JWT access token via the API.
 * @param {import('@playwright/test').APIRequestContext} req
 * @param {string} username
 * @param {string} password
 * @returns {Promise<string>}
 */
async function apiLogin(req, username, password) {
  const resp = await req.post(`${API_BASE}/auth/login`, {
    data: { username, password },
  });
  if (!resp.ok()) {
    throw new Error(`API login failed for ${username}: ${resp.status()} ${await resp.text()}`);
  }
  const body = await resp.json();
  return body.access_token;
}

/**
 * Perform a state transition via the REST endpoint.
 * @param {import('@playwright/test').APIRequestContext} req
 * @param {string} token
 * @param {string} phenopacketId
 * @param {string} toState
 * @param {string} reason
 * @param {number} revision
 * @returns {Promise<number>} Updated revision
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
  return body.phenopacket?.revision ?? revision + 1;
}

/**
 * GET the current phenopacket detail (as curator).
 * @param {import('@playwright/test').APIRequestContext} req
 * @param {string} token
 * @param {string} phenopacketId
 * @returns {Promise<{revision: number, state: string, phenopacket: object}>}
 */
async function apiGetCurator(req, token, phenopacketId) {
  const resp = await req.get(`${API_BASE}/phenopackets/${phenopacketId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok()) {
    throw new Error(`GET failed: ${resp.status()} ${await resp.text()}`);
  }
  return resp.json();
}

// ---------------------------------------------------------------------------
// Test
// ---------------------------------------------------------------------------

test('I1: anonymous sees old head while curator sees new draft after clone-to-draft', async ({
  page,
  context,
  request,
}) => {
  // -------------------------------------------------------------------------
  // Phase 1 — API setup: create + publish a phenopacket with ORIGINAL_SUBJECT_ID
  // -------------------------------------------------------------------------
  const adminToken = await apiLogin(request, ADMIN_USERNAME, ADMIN_PASSWORD);

  // Create draft
  const createResp = await request.post(`${API_BASE}/phenopackets/`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: {
      phenopacket: {
        id: RECORD_ID,
        subject: { id: ORIGINAL_SUBJECT_ID, sex: 'UNKNOWN_SEX' },
        metaData: {
          created: new Date().toISOString(),
          createdBy: 'e2e-i1-test',
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
  let revision = (await createResp.json()).revision ?? 1;

  // draft → in_review → approved → published
  revision = await apiTransition(request, adminToken, RECORD_ID, 'in_review', 'submit', revision);
  revision = await apiTransition(request, adminToken, RECORD_ID, 'approved', 'approve', revision);
  await apiTransition(request, adminToken, RECORD_ID, 'published', 'go live', revision);

  // Verify it is published and head_published_revision_id is set
  const publishedDetail = await apiGetCurator(request, adminToken, RECORD_ID);
  expect(publishedDetail.state).toBe('published');
  expect(publishedDetail.head_published_revision_id).not.toBeNull();
  revision = publishedDetail.revision;

  // -------------------------------------------------------------------------
  // Phase 2 — API: clone-to-draft via PUT (changes subject ID to DRAFT_SUBJECT_ID)
  // -------------------------------------------------------------------------
  const putResp = await request.put(`${API_BASE}/phenopackets/${RECORD_ID}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: {
      phenopacket: {
        id: RECORD_ID,
        subject: { id: DRAFT_SUBJECT_ID, sex: 'UNKNOWN_SEX' },
        metaData: {
          created: new Date().toISOString(),
          createdBy: 'e2e-i1-test',
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
      revision,
      change_reason: 'I1 clone-to-draft test',
    },
  });
  expect(putResp.ok(), `PUT (clone-to-draft) failed: ${await putResp.text()}`).toBeTruthy();
  const clonedDetail = await putResp.json();
  // The PUT on a published record creates a draft clone — state becomes published
  // (public head stays) but working copy is updated.  State stays 'published'
  // with editing_revision_id set to point at the in-progress draft.
  expect(clonedDetail.editing_revision_id).not.toBeNull();
  // Revision tracking ends here — no further transitions are needed in this test.

  // -------------------------------------------------------------------------
  // Phase 3 — Browser (admin): detail page shows DRAFT_SUBJECT_ID
  // -------------------------------------------------------------------------
  await page.goto(`${BASE}/login`);
  await page.waitForLoadState('networkidle');

  await page.locator('input[autocomplete="username"]').fill(ADMIN_USERNAME);
  await page.locator('input[autocomplete="current-password"]').fill(ADMIN_PASSWORD);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL((url) => !url.pathname.endsWith('/login'), { timeout: 15_000 });

  await page.goto(`${BASE}/phenopackets/${RECORD_ID}`, { waitUntil: 'networkidle' });

  // Curator sees the NEW draft content (working copy contains DRAFT_SUBJECT_ID)
  await expect(page.getByText(DRAFT_SUBJECT_ID).first()).toBeVisible({ timeout: 10_000 });

  // -------------------------------------------------------------------------
  // Phase 4 — Anonymous context: detail page shows ORIGINAL_SUBJECT_ID, NOT the draft
  // -------------------------------------------------------------------------
  const anonCtx = await context.browser().newContext();
  const anonPage = await anonCtx.newPage();

  try {
    await anonPage.goto(`${BASE}/phenopackets/${RECORD_ID}`, {
      waitUntil: 'networkidle',
      timeout: 30_000,
    });

    // Anonymous must NOT see DRAFT_SUBJECT_ID
    await expect(anonPage.getByText(DRAFT_SUBJECT_ID)).toHaveCount(0, { timeout: 10_000 });

    // Anonymous MUST see ORIGINAL_SUBJECT_ID (the published head)
    await expect(anonPage.getByText(ORIGINAL_SUBJECT_ID).first()).toBeVisible({
      timeout: 10_000,
    });
  } finally {
    await anonCtx.close();
  }

  // -------------------------------------------------------------------------
  // Cleanup
  // -------------------------------------------------------------------------
  // NOTE: The "re-publish convergence" phase (advancing the cloned draft
  // through in_review → approved → published so the new subject becomes the
  // public head) is deliberately NOT tested here. Spec §6.1 says
  // `phenopackets.state` stays `'published'` during clone-to-draft, while the
  // transition guard matrix in §4.1 has no `('published', 'in_review')` rule
  // — so there is no current path to advance a cloned draft through review.
  // Covering that flow requires either a state-machine change (make
  // transitions read state from `editing_revision_id` when set) or a
  // separate endpoint to promote the draft revision. Tracked as a D.2
  // follow-up; the core I1 invariant (divergence during clone) is fully
  // covered by Phases 1-4 above.
});
