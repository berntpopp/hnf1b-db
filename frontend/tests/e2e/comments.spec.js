// @ts-check
/**
 * D.2 comments — end-to-end flow.
 *
 * Flow:
 *   1. API setup: admin creates + publishes a test phenopacket so the
 *      Discussion tab is available to authenticated users.
 *   2. Admin logs in via the browser form.
 *   3. Navigates to the phenopacket detail page and clicks the Discussion tab.
 *   4. Posts a comment — verifies the comment text appears in the list.
 *   5. Edits that comment (appends " edited") — verifies the updated text
 *      and the "edited · view history" indicator from CommentEditHistory.
 *   6. Soft-deletes the comment → comment disappears from the list.
 *
 * This exercises the full write surface: create, update, soft-delete.
 * Permissions-matrix verification (curator vs admin vs viewer) lives in the
 * backend `test_comments_permissions.py` suite — no need to re-run it here.
 *
 * Strategy
 * --------
 * Like state-lifecycle.spec.js, API calls handle all state setup so the
 * browser tests only need to exercise the UI surfaces that matter.
 *
 *   1. API layer  (request / apiLogin) — authenticate and create the
 *      test record, then advance it to 'published' so both curator and
 *      admin can navigate to its detail page.
 *
 *   2. Browser layer — Playwright drives the Vuetify Discussion tab:
 *        - CommentComposer (.comment-composer / .composer-editor .ProseMirror)
 *        - Post / Save button via getByRole('button', { name })
 *        - CommentItem action menu (aria-label="Comment actions")
 *        - Edit, Delete menu items
 *        - CommentEditHistory "edited · view history" text
 *        - window.confirm dialog for deletion
 *
 * Credentials
 * -----------
 * Same env-var convention as state-lifecycle.spec.js and
 * dual-read-invariant.spec.js.
 *
 *   Playwright `baseURL` defaults to http://localhost:5173
 *   VITE_API_URL        defaults to http://localhost:8000/api/v2
 *   E2E_ADMIN_USERNAME  defaults to admin
 *   E2E_ADMIN_PASSWORD  defaults to ChangeMe!Admin2025
 */

import { test, expect } from '@playwright/test';
import { apiLogin, primeAuthSession } from './helpers/auth';

// ---------------------------------------------------------------------------
// Constants / helpers
// ---------------------------------------------------------------------------

const API_BASE = process.env.VITE_API_URL || 'http://localhost:8000/api/v2';

const ADMIN_USERNAME = process.env.E2E_ADMIN_USERNAME || 'admin';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'ChangeMe!Admin2025';

// Unique record ID — timestamp suffix avoids collisions across runs.
const RECORD_ID = `e2e-wave7-d2-comments-${Date.now()}`;

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
 * Navigate to the phenopacket detail page and activate the Discussion tab.
 * Waits until the CommentComposer editor is visible.
 * @param {import('@playwright/test').Page} page
 * @param {string} recordId
 */
async function openDiscussionTab(page, recordId) {
  await page.goto(`/phenopackets/${recordId}`, { waitUntil: 'networkidle' });
  // The Discussion tab is rendered as:
  //   <v-tab value="discussion" aria-label="Discussion tab">Discussion</v-tab>
  await page.getByRole('tab', { name: /^Discussion/i }).click();
  // Wait for the Tiptap ProseMirror editor inside .composer-editor to appear
  await expect(page.locator('.composer-editor .ProseMirror').first()).toBeVisible({
    timeout: 10_000,
  });
}

// ---------------------------------------------------------------------------
// Test
// ---------------------------------------------------------------------------

test('comments end-to-end: post, edit, soft-delete', async ({ page, request }) => {
  // -------------------------------------------------------------------------
  // Phase 1 — API setup: create + publish a test phenopacket
  //
  // The Discussion tab is only visible to authenticated curators/admins.
  // We need any published (or even draft) record — a freshly created draft
  // owned by admin works because both curator and admin can see the tab.
  // We publish it so that the record is also reachable by the anonymous
  // public route (not required here, but keeps the fixture realistic).
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
          createdBy: 'e2e-comments-test',
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

  // -------------------------------------------------------------------------
  // Phase 2 — Browser login + open Discussion tab
  //
  // NOTE: we use admin for the whole browser flow. The permissions matrix
  // (curator vs admin vs viewer) is exhaustively tested at the backend
  // level in `test_comments_permissions.py`. The E2E spec exists to verify
  // the UI wires the full write surface (POST, PATCH, DELETE) correctly,
  // not to re-test role permissions. CI only seeds an admin user, so this
  // also avoids fixture-dependency drift.
  // -------------------------------------------------------------------------
  await primeAuthSession(page, adminTokens);
  await openDiscussionTab(page, RECORD_ID);

  // -------------------------------------------------------------------------
  // Phase 3 — Post a comment
  //
  // The CommentComposer renders:
  //   <div class="comment-composer">
  //     <editor-content ... class="composer-editor" />   ← Tiptap wrapper
  //       <div class="ProseMirror ...">                  ← contenteditable
  //   submitLabel = "Post"  (no editingComment prop)
  // -------------------------------------------------------------------------
  const commentText = `e2e-comment-${Date.now()}`;
  const editor = page.locator('.composer-editor .ProseMirror').first();
  await editor.click();
  await page.keyboard.type(commentText);

  // Click the "Post" button (rendered by CommentComposer as submitLabel)
  await page.getByRole('button', { name: /^Post$/ }).click();

  // The comment should appear in the CommentList below the composer
  await expect(page.getByText(commentText).first()).toBeVisible({ timeout: 10_000 });

  // -------------------------------------------------------------------------
  // Phase 4 — Edit the comment
  //
  // CommentItem renders the action menu activator as:
  //   <v-btn icon="mdi-dots-vertical" aria-label="Comment actions" ...>
  // Clicking "Edit" sets editingComment on DiscussionTab, which passes it
  // as the :editing-comment prop to CommentComposer — so submitLabel becomes
  // "Save".  After saving, useComments replaces the comment object in the
  // list with the API response, which has edited=true, causing CommentItem
  // to render <CommentEditHistory> with the text "edited · view history".
  // -------------------------------------------------------------------------
  await page.locator('button[aria-label="Comment actions"]').first().click();
  // Vuetify v-list-item renders with role="listitem", not "menuitem".
  await page
    .getByRole('listitem')
    .filter({ hasText: /^Edit$/ })
    .click();

  // The composer editor now contains the existing comment body; append text
  const editedEditor = page.locator('.composer-editor .ProseMirror').first();
  await editedEditor.click();
  await page.keyboard.press('End');
  await page.keyboard.type(' edited');

  // Click the "Save" button (submitLabel = "Save" when editingComment is set)
  await page.getByRole('button', { name: /^Save$/ }).click();

  // Verify updated text is visible
  await expect(page.getByText(`${commentText} edited`).first()).toBeVisible({ timeout: 10_000 });

  // Verify the "edited · view history" indicator from CommentEditHistory.vue.
  // The template renders:  <span>edited &middot; view history</span>
  // We match on the literal "edited" substring (case-insensitive).
  await expect(page.getByText(/edited\s*·\s*view history/i).first()).toBeVisible({
    timeout: 10_000,
  });

  // -------------------------------------------------------------------------
  // Phase 5 — Soft-delete the comment
  //
  // DiscussionTab.onDelete calls window.confirm('Delete this comment?') before
  // removing; we intercept it with page.once('dialog', ...) to auto-accept.
  // After deletion, useComments filters the comment out of comments.value so
  // the text should no longer appear in the DOM.
  // -------------------------------------------------------------------------
  page.once('dialog', (dialog) => dialog.accept());
  await page.locator('button[aria-label="Comment actions"]').first().click();
  await page
    .getByRole('listitem')
    .filter({ hasText: /^Delete$/ })
    .click();

  // After soft-delete the comment is removed from the reactive list
  await expect(page.getByText(`${commentText} edited`)).toHaveCount(0, {
    timeout: 10_000,
  });

  // -------------------------------------------------------------------------
  // Cleanup — archive the test record (best-effort)
  // -------------------------------------------------------------------------
  const finalResp = await request.get(`${API_BASE}/phenopackets/${RECORD_ID}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  if (finalResp.ok()) {
    const finalData = await finalResp.json();
    await apiTransition(
      request,
      adminToken,
      RECORD_ID,
      'archived',
      'E2E comments cleanup',
      finalData.revision
    ).catch(() => {
      // Best-effort; don't fail the test if archiving errors
    });
  }
});
