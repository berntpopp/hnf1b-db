// @ts-check
import { expect, test } from '@playwright/test';

import { loginAsAdmin, loginAsCuratorA, loginAsCuratorB, primeAuthSession } from './helpers/auth';
import { archiveE2ERecord } from './helpers/records';

const API_BASE = process.env.VITE_API_URL || 'http://localhost:8000/api/v2';
const authHeader = (token) => ({ Authorization: `Bearer ${token}` });

function content(recordId) {
  return {
    id: recordId,
    subject: { id: `subject-${recordId}`, sex: 'UNKNOWN_SEX' },
    phenotypicFeatures: [{ type: { id: 'HP:0001250', label: 'Seizure' }, excluded: false }],
    metaData: {
      created: new Date().toISOString(),
      createdBy: 'e2e-review-accessibility',
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

async function setupReview(request, recordId, onRecordCreated) {
  const curatorA = await loginAsCuratorA(request, API_BASE);
  const curatorB = await loginAsCuratorB(request, API_BASE);
  const createResponse = await request.post(`${API_BASE}/phenopackets/`, {
    headers: authHeader(curatorA.accessToken),
    data: { phenopacket: content(recordId) },
  });
  if (createResponse.ok()) onRecordCreated();
  const created = await expectJson(createResponse, 'create accessibility fixture');
  const submitted = await expectJson(
    await request.post(`${API_BASE}/phenopackets/${recordId}/transitions`, {
      headers: authHeader(curatorA.accessToken),
      data: {
        to_state: 'in_review',
        reason: 'Submit accessibility fixture',
        revision: created.revision,
      },
    }),
    'submit accessibility fixture'
  );
  return { curatorA, curatorB, submitted };
}

async function withReviewFixture(request, recordId, run) {
  const admin = await loginAsAdmin(request, API_BASE);
  let recordCreated = false;
  let primaryError = null;
  try {
    const fixture = await setupReview(request, recordId, () => {
      recordCreated = true;
    });
    return await run(fixture);
  } catch (error) {
    primaryError = error;
    throw error;
  } finally {
    await archiveE2ERecord(request, API_BASE, admin.accessToken, recordId, {
      recordCreated,
      primaryError,
    });
  }
}

async function tabTo(page, locator, { reverse = false, maxSteps = 80 } = {}) {
  await expect(locator).toBeVisible();
  for (let step = 0; step <= maxSteps; step += 1) {
    if (await locator.evaluate((node) => node === document.activeElement)) {
      await expect(locator).toBeFocused();
      return;
    }
    await page.keyboard.press(reverse ? 'Shift+Tab' : 'Tab');
  }
  throw new Error(`Keyboard focus did not reach ${await locator.getAttribute('data-testid')}`);
}

test('keyboard path exposes named issue/decision controls and a safe mobile workspace', async ({
  page,
  request,
}) => {
  const recordId = `e2e-review-a11y-${Date.now()}-${test.info().workerIndex}`;
  await withReviewFixture(request, recordId, async ({ curatorB }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await primeAuthSession(page, curatorB);
    await page.goto(
      `/review?tab=needs-review&eligibility=reviewable_by_me&q=${encodeURIComponent(recordId)}`,
      { waitUntil: 'domcontentloaded' }
    );

    const reviewLink = page
      .locator('tr', { hasText: recordId })
      .getByRole('link', { name: 'Review' });
    await expect(reviewLink).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('region', { name: 'Review Queue' })).toHaveAttribute(
      'aria-busy',
      'false'
    );
    await tabTo(page, reviewLink);
    await expect(reviewLink).toBeFocused();
    await Promise.all([
      page.waitForURL(new RegExp(`/review/${recordId}(?:\\?|$)`)),
      page.keyboard.press('Enter'),
    ]);
    await expect(page.getByRole('heading', { name: `Review ${recordId}` })).toBeVisible();

    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth
      )
    ).toBe(true);
    const rightRail = page.getByTestId('review-right-rail');
    await expect(rightRail).toBeVisible();
    const railBox = await rightRail.boundingBox();
    expect(railBox?.x).toBeGreaterThanOrEqual(0);
    expect((railBox?.x || 0) + (railBox?.width || 0)).toBeLessThanOrEqual(375);

    const semanticChanges = page.locator('.semantic-change');
    await expect(semanticChanges.first()).toBeVisible();
    await expect(semanticChanges.first()).toHaveAttribute(
      'data-operation',
      /added|removed|changed/
    );
    await expect(semanticChanges.first()).toHaveAttribute(
      'aria-label',
      /Added|Removed|Changed.*JSON pointer/
    );
    await expect(semanticChanges.first().locator('.operation-icon')).toBeVisible();

    const decisionSection = page.getByTestId('decision-rail-section');
    await decisionSection.scrollIntoViewIfNeeded();
    const requestChanges = page.getByTestId('action-request_changes');
    await expect(requestChanges).toBeVisible();
    const actionBox = await requestChanges.boundingBox();
    expect(actionBox?.height).toBeGreaterThanOrEqual(44);
    const actionVisibility = await requestChanges.evaluate((node) => {
      const box = node.getBoundingClientRect();
      const hitTarget = document.elementFromPoint(
        box.left + box.width / 2,
        box.top + box.height / 2
      );
      return {
        top: box.top,
        bottom: box.bottom,
        viewportHeight: window.innerHeight,
        unobscured: hitTarget === node || node.contains(hitTarget),
      };
    });
    expect(actionVisibility.top).toBeGreaterThanOrEqual(0);
    expect(actionVisibility.bottom).toBeLessThanOrEqual(actionVisibility.viewportHeight);
    expect(actionVisibility.unobscured).toBe(true);
    expect(
      parseFloat(await decisionSection.evaluate((node) => getComputedStyle(node).paddingBottom))
    ).toBeGreaterThan(0);

    await tabTo(page, requestChanges);
    await page.keyboard.press('Enter');
    await expect(page.getByRole('dialog', { name: 'Request changes' })).toBeVisible();
    const decisionCancel = page.getByTestId('decision-cancel');
    await tabTo(page, decisionCancel);
    await page.keyboard.press('Enter');
    await expect(requestChanges).toBeFocused();

    const createIssue = page.getByTestId('create-issue');
    await tabTo(page, createIssue, { reverse: true });
    await page.keyboard.press('Enter');
    const issueText = page.getByLabel('Issue', { exact: true });
    await tabTo(page, issueText);
    await page.keyboard.type('Keyboard-created blocking issue');
    await tabTo(page, page.getByTestId('issue-submit'));
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('review-issue')).toContainText('Keyboard-created blocking issue');

    await tabTo(page, requestChanges);
    await page.keyboard.press('Enter');
    const decisionRationale = page.getByLabel('Decision rationale');
    await tabTo(page, decisionRationale);
    await page.keyboard.type('Keyboard reviewer requests clarification.');
    await tabTo(page, page.getByTestId('decision-submit'));
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'Review decisions' })).toBeFocused({
      timeout: 15_000,
    });
    await expect(page.getByText('Changes requested').first()).toBeVisible();
  });
});

test('current revision with a tampered candidate digest requires an explicit reload', async ({
  page,
  request,
}) => {
  const recordId = `e2e-review-digest-${Date.now()}-${test.info().workerIndex}`;
  await withReviewFixture(request, recordId, async ({ curatorB }) => {
    await primeAuthSession(page, curatorB);
    await page.goto(`/review/${recordId}`, { waitUntil: 'domcontentloaded' });
    const approve = page.getByTestId('action-approve');
    await expect(approve).toBeEnabled({ timeout: 15_000 });

    const currentContext = await expectJson(
      await request.get(`${API_BASE}/phenopackets/${recordId}/review-context`, {
        headers: authHeader(curatorB.accessToken),
      }),
      'load current digest context identity'
    );
    const tamperedDigest = `sha256:${'0'.repeat(64)}`;
    expect(currentContext.candidate.content_sha256).not.toBe(tamperedDigest);

    await approve.click();
    await page
      .getByLabel('Decision rationale')
      .fill('This decision intentionally submits the wrong candidate digest.');
    await page.getByLabel('I independently reviewed this exact candidate revision.').check();
    await page.getByLabel('I have no unmanaged conflict of interest for this decision.').check();

    let interceptedBody;
    await page.route(
      `**/phenopackets/${recordId}/transitions`,
      async (route) => {
        interceptedBody = route.request().postDataJSON();
        await route.continue({
          postData: JSON.stringify({
            ...interceptedBody,
            candidate_content_sha256: tamperedDigest,
          }),
        });
      },
      { times: 1 }
    );
    const mismatchResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        response.url().endsWith(`/phenopackets/${recordId}/transitions`)
    );
    await page.getByTestId('decision-submit').click();
    const mismatchResponse = await mismatchResponsePromise;
    expect(interceptedBody).toMatchObject({
      revision: currentContext.record_revision,
      candidate_revision_id: currentContext.candidate.id,
      candidate_content_sha256: currentContext.candidate.content_sha256,
    });
    expect(mismatchResponse.status()).toBe(409);
    expect(await mismatchResponse.json()).toMatchObject({
      detail: { code: 'review_revision_mismatch' },
    });
    await expect(page.getByText('Reload required')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('reload-review')).toBeFocused();
    await expect(page.getByTestId('action-approve')).toHaveCount(0);

    await page.getByTestId('reload-review').press('Enter');
    await expect(page.getByText('Reload required')).toHaveCount(0);
    await expect(page.getByTestId('action-approve')).toBeEnabled();
  });
});

test('stale loaded revision and digest require reload and move focus to the recovery control', async ({
  page,
  request,
}) => {
  const recordId = `e2e-review-stale-${Date.now()}-${test.info().workerIndex}`;
  await withReviewFixture(request, recordId, async ({ curatorA, curatorB, submitted }) => {
    await primeAuthSession(page, curatorB);
    await page.goto(`/review/${recordId}`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('action-approve')).toBeEnabled({ timeout: 15_000 });

    const staleContext = await expectJson(
      await request.get(`${API_BASE}/phenopackets/${recordId}/review-context`, {
        headers: authHeader(curatorB.accessToken),
      }),
      'load stale context identity'
    );
    expect(staleContext.candidate.id).toBe(submitted.revision.id);

    await expectJson(
      await request.post(`${API_BASE}/phenopackets/${recordId}/transitions`, {
        headers: authHeader(curatorA.accessToken),
        data: {
          to_state: 'draft',
          reason: 'Owner invalidates the loaded review snapshot',
          revision: staleContext.record_revision,
        },
      }),
      'withdraw stale candidate'
    );

    await page.getByTestId('action-approve').click();
    await page
      .getByLabel('Decision rationale')
      .fill('This decision intentionally uses stale evidence.');
    await page.getByLabel('I independently reviewed this exact candidate revision.').check();
    await page.getByLabel('I have no unmanaged conflict of interest for this decision.').check();
    const staleRequestPromise = page.waitForRequest(
      (candidate) =>
        candidate.method() === 'POST' &&
        candidate.url().endsWith(`/phenopackets/${recordId}/transitions`)
    );
    await page.getByTestId('decision-submit').click();
    const staleRequest = await staleRequestPromise;
    expect(staleRequest.postDataJSON()).toMatchObject({
      revision: staleContext.record_revision,
      candidate_revision_id: staleContext.candidate.id,
      candidate_content_sha256: staleContext.candidate.content_sha256,
    });
    await expect(page.getByText('Reload required')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('reload-review')).toBeFocused();
    await page.getByTestId('reload-review').press('Enter');
    await expect(page.getByText('Reload required')).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'Review decisions' })).toBeVisible();
  });
});
