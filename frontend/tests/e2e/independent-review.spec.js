// @ts-check
import { expect, test } from '@playwright/test';

import {
  apiLogin,
  loginAsAdmin,
  loginAsCuratorA,
  loginAsCuratorB,
  primeAuthSession,
} from './helpers/auth';
import { archiveE2ERecord } from './helpers/records';

const API_BASE = process.env.VITE_API_URL || 'http://localhost:8000/api/v2';
const authHeader = (token) => ({ Authorization: `Bearer ${token}` });

function content(recordId, subjectId) {
  return {
    id: recordId,
    subject: { id: subjectId, sex: 'UNKNOWN_SEX' },
    phenotypicFeatures: [
      {
        type: { id: 'HP:0001250', label: 'Seizure' },
        excluded: false,
      },
    ],
    metaData: {
      created: new Date().toISOString(),
      createdBy: 'e2e-independent-review',
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
  };
}

async function expectJson(response, label) {
  const text = await response.text();
  expect(response.ok(), `${label}: ${response.status()} ${text}`).toBeTruthy();
  return JSON.parse(text);
}

async function transition(request, token, recordId, toState, reason, revision, evidence = {}) {
  return expectJson(
    await request.post(`${API_BASE}/phenopackets/${recordId}/transitions`, {
      headers: authHeader(token),
      data: { to_state: toState, reason, revision, ...evidence },
    }),
    `transition ${recordId} to ${toState}`
  );
}

async function detail(request, token, recordId) {
  return expectJson(
    await request.get(`${API_BASE}/phenopackets/${recordId}`, { headers: authHeader(token) }),
    `detail ${recordId}`
  );
}

async function reviewContext(request, token, recordId) {
  return expectJson(
    await request.get(`${API_BASE}/phenopackets/${recordId}/review-context`, {
      headers: authHeader(token),
    }),
    `review context ${recordId}`
  );
}

async function currentActor(request, token, label) {
  return expectJson(
    await request.get(`${API_BASE}/auth/me`, { headers: authHeader(token) }),
    `${label} identity`
  );
}

async function publicDiscovery(request, recordId, query, token = undefined) {
  const options = token ? { headers: authHeader(token) } : undefined;
  const audience = token ? 'viewer' : 'anonymous';
  const listing = await expectJson(
    await request.get(`${API_BASE}/phenopackets/?page[number]=1&page[size]=100`, options),
    `${audience} phenopacket listing`
  );
  const search = await expectJson(
    await request.get(`${API_BASE}/phenopackets/search?q=${encodeURIComponent(query)}`, options),
    `${audience} phenopacket search for ${query}`
  );
  return {
    listing: listing.data.find((item) => item.id === recordId),
    search: search.data.find((item) => item.id === recordId),
  };
}

async function assertPrivate(request, recordId, viewerToken, query) {
  const anonymous = await request.get(`${API_BASE}/phenopackets/${recordId}`);
  expect(anonymous.status()).toBe(404);
  expect(await anonymous.json()).toMatchObject({ error_code: 'http_404' });

  const viewer = await request.get(`${API_BASE}/phenopackets/${recordId}`, {
    headers: authHeader(viewerToken),
  });
  expect(viewer.status()).toBe(404);

  const anonymousMalformedQueue = await request.get(
    `${API_BASE}/phenopackets/review-queue?filter[state]=not-a-state&page[number]=0`
  );
  expect(anonymousMalformedQueue.status()).toBe(404);
  const viewerMalformedContext = await request.get(
    `${API_BASE}/phenopackets/not-a-record/review-context`,
    { headers: authHeader(viewerToken) }
  );
  expect(viewerMalformedContext.status()).toBe(404);

  const discovery = await publicDiscovery(request, recordId, query);
  expect(discovery).toEqual({ listing: undefined, search: undefined });
  const viewerDiscovery = await publicDiscovery(request, recordId, query, viewerToken);
  expect(viewerDiscovery).toEqual({ listing: undefined, search: undefined });
}

async function assertPublicHead(request, recordId, expectedContent, publicQuery, hiddenQuery) {
  const publicDetail = await expectJson(
    await request.get(`${API_BASE}/phenopackets/${recordId}`),
    `public head for ${recordId}`
  );
  expect(publicDetail.phenopacket).toEqual(expectedContent);

  const visible = await publicDiscovery(request, recordId, publicQuery);
  expect(visible.listing?.subject).toEqual(expectedContent.subject);
  expect(visible.search?.attributes?.subject).toEqual(expectedContent.subject);
  if (hiddenQuery) {
    expect((await publicDiscovery(request, recordId, hiddenQuery)).search).toBeUndefined();
  }
}

test('independent curator lifecycle keeps exact candidates private through two review cycles', async ({
  browser,
  page,
  request,
}) => {
  const suffix = `${Date.now()}-${test.info().workerIndex}`;
  // This principal fixture deliberately avoids the synthetic `e2e-` prefix:
  // production public discovery excludes that prefix, so it cannot prove that
  // a real approved publication becomes searchable/listed.
  const recordId = `review-lifecycle-${suffix}`;
  const subjectV1 = `review-subject-v1-${suffix}`;
  const subjectV2 = `review-subject-v2-${suffix}`;
  const subjectV3 = `review-subject-v3-${suffix}`;

  const adminAuth = await loginAsAdmin(request, API_BASE);
  const curatorAAuth = await loginAsCuratorA(request, API_BASE);
  const curatorBAuth = await loginAsCuratorB(request, API_BASE);
  const viewerAuth = await apiLogin(request, API_BASE, 'dev-viewer', 'DevViewer!2026');
  const adminToken = adminAuth.accessToken;
  const curatorAToken = curatorAAuth.accessToken;
  const curatorBToken = curatorBAuth.accessToken;
  const curatorA = await currentActor(request, curatorAToken, 'curator A');
  const curatorB = await currentActor(request, curatorBToken, 'curator B');
  expect(curatorA).toMatchObject({ role: 'curator', is_active: true, is_verified: true });
  expect(curatorB).toMatchObject({ role: 'curator', is_active: true, is_verified: true });
  expect(curatorA.id).not.toBe(curatorB.id);
  expect(curatorA.username).not.toBe(curatorB.username);
  let recordCreated = false;
  let primaryError = null;

  try {
    const createResponse = await request.post(`${API_BASE}/phenopackets/`, {
      headers: authHeader(curatorAToken),
      data: { phenopacket: content(recordId, subjectV1) },
    });
    recordCreated = createResponse.ok();
    const created = await expectJson(createResponse, 'curator A creates draft');
    expect(created).toMatchObject({ state: 'draft', draft_owner_username: curatorA.username });

    const submitted = await transition(
      request,
      curatorAToken,
      recordId,
      'in_review',
      'Curator A submits the first candidate',
      created.revision
    );
    expect(submitted.phenopacket.effective_state).toBe('in_review');
    await assertPrivate(request, recordId, viewerAuth.accessToken, subjectV1);

    const ownerContext = await reviewContext(request, curatorAToken, recordId);
    expect(ownerContext.audit.owner).toMatchObject({
      id: curatorA.id,
      username: curatorA.username,
    });
    expect(ownerContext.audit.submission.actor).toMatchObject({
      id: curatorA.id,
      username: curatorA.username,
    });
    const ownerApproval = ownerContext.capabilities.find((item) => item.action === 'approve');
    expect(ownerApproval).toMatchObject({ action: 'approve', allowed: false });
    expect(ownerApproval.blocked_by).toContain('self_review_forbidden');
    const selfApproval = await request.post(`${API_BASE}/phenopackets/${recordId}/transitions`, {
      headers: authHeader(curatorAToken),
      data: {
        to_state: 'approved',
        reason: 'Owner must not approve',
        revision: ownerContext.record_revision,
        candidate_revision_id: ownerContext.candidate.id,
        candidate_content_sha256: ownerContext.candidate.content_sha256,
        attestation: { independent_review: true, no_unmanaged_conflict: true },
      },
    });
    expect(selfApproval.status()).toBe(403);
    expect(await selfApproval.json()).toMatchObject({
      detail: { code: 'self_review_forbidden' },
      error_code: 'http_403',
    });

    const queue = await expectJson(
      await request.get(
        `${API_BASE}/phenopackets/review-queue?filter[state]=in_review&filter[eligibility]=reviewable_by_me&q=${recordId}&sort=phenopacket_id`,
        { headers: authHeader(curatorBToken) }
      ),
      'curator B filtered queue'
    );
    expect(queue.data).toHaveLength(1);
    expect(queue.data[0]).toMatchObject({
      phenopacket_id: recordId,
      effective_state: 'in_review',
      owner: { id: curatorA.id, username: curatorA.username },
    });
    expect(queue.data[0].capabilities).toContainEqual(
      expect.objectContaining({ action: 'approve', allowed: true })
    );

    await primeAuthSession(page, curatorBAuth);
    await page.goto(
      `/review?tab=needs-review&eligibility=reviewable_by_me&q=${encodeURIComponent(recordId)}&sort=phenopacket_id`,
      { waitUntil: 'domcontentloaded' }
    );
    const row = page.locator('tr', { hasText: recordId });
    await expect(row).toBeVisible({ timeout: 15_000 });
    await expect(row.getByText('Reviewable by you')).toBeVisible();
    await row.getByRole('link', { name: 'Review' }).click();
    await expect(page.getByRole('heading', { name: `Review ${recordId}` })).toBeVisible();

    await page.getByTestId('create-issue').click();
    await page
      .getByLabel('Issue', { exact: true })
      .fill('Confirm the first-cycle phenotype evidence.');
    await page.getByTestId('issue-submit').click();
    await expect(page.getByTestId('review-issue')).toContainText(
      'Confirm the first-cycle phenotype evidence.'
    );

    await page.getByTestId('action-request_changes').click();
    await page.getByLabel('Decision rationale').fill('Please clarify the phenotype evidence.');
    await page.getByTestId('decision-submit').click();
    await expect(page.getByText('Changes requested').first()).toBeVisible({ timeout: 15_000 });

    const changesRequested = await detail(request, curatorAToken, recordId);
    const feedbackContext = await reviewContext(request, curatorAToken, recordId);
    const replyText = `Curator A response: phenotype evidence clarified (${suffix}).`;
    const reply = await expectJson(
      await request.post(`${API_BASE}/comments`, {
        headers: authHeader(curatorAToken),
        data: {
          record_type: 'phenopacket',
          record_id: feedbackContext.record_id,
          body_markdown: replyText,
        },
      }),
      'curator A posts an ordinary response to reviewer feedback'
    );
    expect(reply).toMatchObject({
      body_markdown: replyText,
      author_id: curatorA.id,
      author_username: curatorA.username,
      review_revision_id: null,
      is_blocking_issue: false,
    });
    const discussion = await expectJson(
      await request.get(
        `${API_BASE}/comments?filter[record_type]=phenopacket&filter[record_id]=${feedbackContext.record_id}`,
        { headers: authHeader(curatorAToken) }
      ),
      'discussion after curator A response'
    );
    const blockingIssue = discussion.data.find((comment) => comment.review_revision_id !== null);
    const ordinaryReply = discussion.data.find((comment) => comment.id === reply.id);
    expect(blockingIssue).toMatchObject({ is_blocking_issue: true });
    expect(ordinaryReply).toMatchObject({
      body_markdown: replyText,
      review_revision_id: null,
      is_blocking_issue: false,
    });
    expect(blockingIssue.id).not.toBe(ordinaryReply.id);

    const updatedContent = structuredClone(changesRequested.phenopacket);
    updatedContent.subject.id = subjectV2;
    updatedContent.phenotypicFeatures[0].type.label = 'Seizure, curator clarified';
    const updated = await expectJson(
      await request.put(`${API_BASE}/phenopackets/${recordId}`, {
        headers: authHeader(curatorAToken),
        data: {
          phenopacket: updatedContent,
          revision: changesRequested.revision,
          change_reason: 'Curator A addresses reviewer feedback',
        },
      }),
      'curator A updates candidate'
    );
    const resubmitted = await transition(
      request,
      curatorAToken,
      recordId,
      'in_review',
      'Curator A resubmits the clarified candidate',
      updated.revision
    );
    expect(resubmitted.phenopacket.effective_state).toBe('in_review');

    await page.goto(`/review/${recordId}`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('review-issue')).toContainText('Open');
    await page.getByRole('button', { name: 'Resolve issue' }).click();
    await page.getByLabel('Disposition').selectOption('addressed');
    await page
      .getByLabel('Rationale')
      .fill('Curator A clarified the evidence in the resubmission.');
    await page.getByTestId('issue-submit').click();
    await expect(page.getByTestId('review-issue')).toContainText('Resolved');
    await expect(page.getByTestId('resolution-event')).toContainText('Addressed');

    const exactCandidate = (await reviewContext(request, curatorBToken, recordId)).candidate;
    expect(exactCandidate.content).toEqual(resubmitted.revision.content_jsonb);
    const firstApprovalRationale = 'Independent review confirms this candidate.';
    await page.getByTestId('action-approve').click();
    await page.getByLabel('Decision rationale').fill(firstApprovalRationale);
    await page.getByLabel('I independently reviewed this exact candidate revision.').check();
    await page.getByLabel('I have no unmanaged conflict of interest for this decision.').check();
    const approvalRequestPromise = page.waitForRequest(
      (candidate) =>
        candidate.method() === 'POST' &&
        candidate.url().endsWith(`/phenopackets/${recordId}/transitions`)
    );
    const approvalResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        response.url().endsWith(`/phenopackets/${recordId}/transitions`)
    );
    const approvalStartedAt = Date.now();
    await page.getByTestId('decision-submit').click();
    const approvalRequest = await approvalRequestPromise;
    expect(approvalRequest.postDataJSON()).toMatchObject({
      to_state: 'approved',
      candidate_revision_id: exactCandidate.id,
      candidate_content_sha256: exactCandidate.content_sha256,
      attestation: { independent_review: true, no_unmanaged_conflict: true },
    });
    const approvalResult = await expectJson(await approvalResponsePromise, 'first exact approval');
    expect(approvalResult.revision).toMatchObject({
      state: 'approved',
      actor_id: curatorB.id,
      actor_username: curatorB.username,
      actor_role: 'curator',
      actor_role_at_decision_recorded: true,
      change_reason: firstApprovalRationale,
      content_sha256: exactCandidate.content_sha256,
      decision_metadata: {
        schemaVersion: 1,
        candidate_revision_id: exactCandidate.id,
        candidate_content_sha256: exactCandidate.content_sha256,
        attestation: { independent_review: true, no_unmanaged_conflict: true },
        rationale: firstApprovalRationale,
      },
    });
    expect(approvalResult.revision.content_jsonb).toEqual(exactCandidate.content);
    const approvalTime = Date.parse(approvalResult.revision.created_at);
    expect(approvalTime).toBeGreaterThanOrEqual(approvalStartedAt - 1_000);
    expect(approvalTime).toBeLessThanOrEqual(Date.now() + 1_000);
    await expect(page.getByText('Approved').first()).toBeVisible({ timeout: 15_000 });
    await assertPrivate(request, recordId, viewerAuth.accessToken, subjectV2);

    const approvedContext = await reviewContext(request, curatorBToken, recordId);
    expect(approvedContext.approved.content).toEqual(exactCandidate.content);
    expect(approvedContext.audit.approval).toMatchObject({
      id: approvalResult.revision.id,
      state: 'approved',
      content_sha256: exactCandidate.content_sha256,
      created_at: approvalResult.revision.created_at,
      actor: { id: curatorB.id, username: curatorB.username },
      actor_role: 'curator',
      actor_role_at_decision_recorded: true,
    });

    const viewerContext = await browser.newContext();
    const viewerPage = await viewerContext.newPage();
    await primeAuthSession(viewerPage, viewerAuth);
    await viewerPage.goto(`/review/${recordId}`, { waitUntil: 'domcontentloaded' });
    await expect(viewerPage.getByRole('heading', { name: 'Page Not Found' })).toBeVisible();
    await viewerContext.close();

    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await primeAuthSession(adminPage, adminAuth);
    await adminPage.goto(`/review/${recordId}`, { waitUntil: 'domcontentloaded' });
    const exactApproval = (await reviewContext(request, adminToken, recordId)).approved;
    await adminPage.getByTestId('action-publish').click();
    await adminPage.getByLabel('Decision rationale').fill('Admin publishes the exact approval.');
    const publishRequestPromise = adminPage.waitForRequest(
      (candidate) =>
        candidate.method() === 'POST' &&
        candidate.url().endsWith(`/phenopackets/${recordId}/transitions`)
    );
    await adminPage.getByTestId('decision-submit').click();
    const publishRequest = await publishRequestPromise;
    expect(publishRequest.postDataJSON()).toMatchObject({
      to_state: 'published',
      approved_revision_id: exactApproval.id,
      approved_content_sha256: exactApproval.content_sha256,
    });
    await expect(adminPage.getByTestId('publication-complete-heading')).toBeFocused({
      timeout: 15_000,
    });
    await adminContext.close();

    const firstPublic = await expectJson(
      await request.get(`${API_BASE}/phenopackets/${recordId}`),
      'first public head'
    );
    expect(firstPublic.phenopacket).toEqual(exactCandidate.content);
    await assertPublicHead(request, recordId, exactCandidate.content, subjectV2, subjectV3);

    const publishedForOwner = await detail(request, curatorAToken, recordId);
    const secondCycleContent = structuredClone(publishedForOwner.phenopacket);
    secondCycleContent.subject.id = subjectV3;
    const secondDraft = await expectJson(
      await request.put(`${API_BASE}/phenopackets/${recordId}`, {
        headers: authHeader(curatorAToken),
        data: {
          phenopacket: secondCycleContent,
          revision: publishedForOwner.revision,
          change_reason: 'Curator A starts the replacement publication cycle',
        },
      }),
      'second-cycle edit'
    );
    expect(secondDraft.effective_state).toBe('draft');
    await assertPublicHead(request, recordId, exactCandidate.content, subjectV2, subjectV3);

    const secondSubmission = await transition(
      request,
      curatorAToken,
      recordId,
      'in_review',
      'Curator A submits replacement candidate',
      secondDraft.revision
    );
    let secondContext = await reviewContext(request, curatorBToken, recordId);
    const replacementCandidate = structuredClone(secondContext.candidate.content);
    expect(replacementCandidate).toEqual(secondSubmission.revision.content_jsonb);
    expect(replacementCandidate.subject.id).toBe(subjectV3);
    await assertPublicHead(request, recordId, exactCandidate.content, subjectV2, subjectV3);
    const secondApproval = await transition(
      request,
      curatorBToken,
      recordId,
      'approved',
      'Curator B approves the replacement candidate',
      secondContext.record_revision,
      {
        candidate_revision_id: secondContext.candidate.id,
        candidate_content_sha256: secondContext.candidate.content_sha256,
        attestation: { independent_review: true, no_unmanaged_conflict: true },
      }
    );
    expect(secondApproval.phenopacket.effective_state).toBe('approved');
    expect(secondApproval.revision.content_jsonb).toEqual(replacementCandidate);
    await assertPublicHead(request, recordId, exactCandidate.content, subjectV2, subjectV3);

    const reopened = await transition(
      request,
      curatorBToken,
      recordId,
      'changes_requested',
      'Curator B reopens the approved replacement for one more check',
      secondApproval.phenopacket.revision
    );
    expect(reopened.phenopacket.effective_state).toBe('changes_requested');
    expect(reopened.revision.content_jsonb).toEqual(replacementCandidate);
    await assertPublicHead(request, recordId, exactCandidate.content, subjectV2, subjectV3);
    const secondResubmission = await transition(
      request,
      curatorAToken,
      recordId,
      'in_review',
      'Curator A resubmits after approved-review reopening',
      reopened.phenopacket.revision
    );
    expect(secondResubmission.revision.content_jsonb).toEqual(replacementCandidate);
    await assertPublicHead(request, recordId, exactCandidate.content, subjectV2, subjectV3);
    secondContext = await reviewContext(request, curatorBToken, recordId);
    expect(secondContext.candidate.content).toEqual(replacementCandidate);
    const finalApproval = await transition(
      request,
      curatorBToken,
      recordId,
      'approved',
      'Curator B gives final replacement approval',
      secondContext.record_revision,
      {
        candidate_revision_id: secondContext.candidate.id,
        candidate_content_sha256: secondContext.candidate.content_sha256,
        attestation: { independent_review: true, no_unmanaged_conflict: true },
      }
    );
    expect(secondResubmission.revision.id).toBeGreaterThan(secondSubmission.revision.id);
    expect(secondResubmission.revision.content_sha256).toBe(
      secondSubmission.revision.content_sha256
    );
    expect(secondContext.candidate.id).toBe(secondResubmission.revision.id);
    expect(secondContext.candidate.content_sha256).toBe(secondResubmission.revision.content_sha256);
    expect(finalApproval.revision.content_jsonb).toEqual(replacementCandidate);
    await assertPublicHead(request, recordId, exactCandidate.content, subjectV2, subjectV3);

    await transition(
      request,
      adminToken,
      recordId,
      'published',
      'Admin publishes the final exact replacement',
      finalApproval.phenopacket.revision,
      {
        approved_revision_id: finalApproval.revision.id,
        approved_content_sha256: finalApproval.revision.content_sha256,
      }
    );
    const replacementPublic = await expectJson(
      await request.get(`${API_BASE}/phenopackets/${recordId}`),
      'replacement public head'
    );
    expect(replacementPublic.phenopacket).toEqual(replacementCandidate);
    const replacementDiscovery = await publicDiscovery(request, recordId, subjectV3);
    expect(replacementDiscovery.listing?.subject).toEqual(replacementCandidate.subject);
    expect(replacementDiscovery.search?.attributes?.subject).toEqual(replacementCandidate.subject);
    expect((await publicDiscovery(request, recordId, subjectV2)).search).toBeUndefined();
  } catch (error) {
    primaryError = error;
    throw error;
  } finally {
    await archiveE2ERecord(request, API_BASE, adminToken, recordId, {
      recordCreated,
      primaryError,
    });
  }
});
