// @ts-check
import { expect, test } from '@playwright/test';

import { loginAsAdmin, loginAsCuratorA, loginAsCuratorB, primeAuthSession } from './helpers/auth';
import { archiveE2ERecord } from './helpers/records';

const API_BASE = process.env.VITE_API_URL || 'http://localhost:8000/api/v2';
const authHeader = (token) => ({ Authorization: `Bearer ${token}` });

function richPhenopacketContent(recordId, subjectId, pmid, variantId) {
  return {
    id: recordId,
    subject: {
      id: subjectId,
      sex: 'MALE',
      dateOfBirth: '1995-04-12T00:00:00Z',
    },
    phenotypicFeatures: [
      {
        type: { id: 'HP:0000077', label: 'Abnormality of the kidney' },
        excluded: false,
      },
      {
        type: { id: 'HP:0000822', label: 'Hypertension' },
        excluded: false,
      },
      {
        type: { id: 'HP:0000135', label: 'Hypokalemia' },
        excluded: true,
      },
    ],
    interpretations: [
      {
        id: `interpretation-${recordId}`,
        progressStatus: 'SOLVED',
        diagnosis: {
          genomicInterpretations: [
            {
              subjectOrBiosampleId: subjectId,
              interpretationStatus: 'PATHOGENIC',
              variantInterpretation: {
                variationDescriptor: {
                  id: variantId,
                  geneContext: {
                    valueId: 'HGNC:11630',
                    symbol: 'HNF1B',
                  },
                },
              },
            },
          ],
        },
      },
    ],
    metaData: {
      created: new Date().toISOString(),
      createdBy: 'monkey-test-curator',
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
      externalReferences: [{ id: `PMID:${pmid}` }],
    },
    hnf1bCuration: {
      cohort: 'born',
      classificationSystem: 'acmg',
      familyHistory: 'positive',
      detectionMethod: 'sanger',
      publicationType: 'case_report',
      problematic: 'no',
      duplicateCheck: 'yes',
      caseComment:
        'Phenotype characterized by bilateral renal cysts and early maturity-onset diabetes.',
    },
  };
}

test.describe('Exploratory and Monkey Testing: Peer Review & Curation Workflow', () => {
  test('stress-tests review workspace, mobile viewport, rapid interactions, and curation visibility', async ({
    page,
    request,
  }) => {
    test.setTimeout(90_000);
    const timestamp = Date.now();
    const recordId = `monkey-test-${timestamp}`;
    const subjectId = `subject-${timestamp}`;
    const pmid = '31234567';
    const variantId = `NM_000458.4:c.544C>T:p.Arg182Trp`;

    const adminAuth = await loginAsAdmin(request, API_BASE);
    const curatorAAuth = await loginAsCuratorA(request, API_BASE);
    const curatorBAuth = await loginAsCuratorB(request, API_BASE);
    const adminToken = adminAuth.accessToken;
    const curatorAToken = curatorAAuth.accessToken;
    const _curatorBToken = curatorBAuth.accessToken;

    let recordCreated = false;
    let primaryError = null;

    try {
      // 1. Curator A creates a rich clinical phenopacket
      const createResp = await request.post(`${API_BASE}/phenopackets/`, {
        headers: authHeader(curatorAToken),
        data: {
          phenopacket: richPhenopacketContent(recordId, subjectId, pmid, variantId),
        },
      });
      const createBody = await createResp.text();
      expect(createResp.ok(), `create failed: ${createResp.status()} ${createBody}`).toBeTruthy();
      recordCreated = true;
      const created = JSON.parse(createBody);

      // Submit to in_review
      const submitResp = await request.post(`${API_BASE}/phenopackets/${recordId}/transitions`, {
        headers: authHeader(curatorAToken),
        data: {
          to_state: 'in_review',
          reason: 'Curator A submits comprehensive clinical case for review',
          revision: created.revision,
        },
      });
      expect(submitResp.ok()).toBeTruthy();

      // 2. Curator B logs in to UI
      await primeAuthSession(page, curatorBAuth);

      // Navigate to Review Queue
      await page.goto('/review', { waitUntil: 'domcontentloaded' });
      await expect(page.getByRole('heading', { name: 'Review Queue' })).toBeVisible({
        timeout: 15_000,
      });

      // MONKEY TEST: Rapid tab switching on review queue
      const tabs = ['needs-review', 'changes-requested', 'approved', 'my-drafts'];
      for (const tabName of tabs) {
        const tabBtn = page.getByRole('tab', { name: new RegExp(tabName.replace('-', ' '), 'i') });
        if (await tabBtn.isVisible()) {
          await tabBtn.click();
          await page.waitForTimeout(50);
        }
      }

      // Return to Needs Review and filter for record
      await page.getByRole('tab', { name: /needs review/i }).click();
      const searchBox = page.getByPlaceholder('Search case ID or subject');
      await searchBox.fill(recordId);
      await page.waitForTimeout(400); // debounce

      const tableRow = page.locator('tr', { hasText: recordId });
      await expect(tableRow).toBeVisible({ timeout: 10_000 });

      // Check eligibility chip and action button
      await expect(tableRow.getByText('Reviewable by you')).toBeVisible();
      const reviewBtn = tableRow.getByRole('link', { name: 'Review' });
      await expect(reviewBtn).toBeVisible();
      await reviewBtn.click();

      // 3. Review Workspace Loaded
      await expect(page.getByRole('heading', { name: `Review ${recordId}` })).toBeVisible({
        timeout: 15_000,
      });

      // Verify Eligibility banner / header badge
      await expect(page.getByText('Eligible to review')).toBeVisible();

      // MONKEY TEST: Rapid switching across review workspace tabs
      await page.getByRole('tab', { name: 'Candidate' }).click();
      await page.getByRole('tab', { name: 'Raw JSON' }).click();
      await page.getByRole('tab', { name: 'History' }).click();
      await page.getByRole('tab', { name: 'Changes' }).click();

      // Check Semantic Diff categories & section headers
      await expect(page.getByRole('heading', { name: 'Subject' })).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Phenotypes' })).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Variants/Interpretations' })).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Metadata' })).toBeVisible();

      // Test Category Filter Chips
      const allFilter = page.getByRole('button', { name: /all \(/i });
      const phenotypesFilter = page.getByRole('button', { name: /phenotypes \(/i });

      if (await phenotypesFilter.isVisible()) {
        await phenotypesFilter.click();
        await expect(page.getByRole('heading', { name: 'Phenotypes' })).toBeVisible();
        await expect(page.getByRole('heading', { name: 'Subject' })).not.toBeVisible();
        await allFilter.click();
        await expect(page.getByRole('heading', { name: 'Subject' })).toBeVisible();
      }

      // Switch to Candidate Snapshot Tab & verify clinical curation card
      await page.getByRole('tab', { name: 'Candidate' }).click();
      await expect(page.getByTestId('hnf1b-curation-card')).toBeVisible();
      await expect(page.getByText('Curation Profile')).toBeVisible();
      await expect(page.getByText('Born individual')).toBeVisible();
      await expect(page.getByText('Duplicate checked')).toBeVisible();
      await expect(page.getByText('Case notes')).toBeVisible();
      await expect(
        page.getByText(
          'Phenotype characterized by bilateral renal cysts and early maturity-onset diabetes.'
        )
      ).toBeVisible();

      // 4. Issue Management: Add, cancel, submit
      await page.getByTestId('create-issue').click();
      // Test cancellation
      await page.getByTestId('issue-cancel').click();
      await expect(page.getByLabel('Issue', { exact: true })).not.toBeVisible();

      // Re-open and create issue with markdown & special clinical characters
      await page.getByTestId('create-issue').click();
      await page
        .getByLabel('Issue', { exact: true })
        .fill(
          'Please double-check variant annotation: NM_000458.4:c.544C>T & HPO HP:0000822 (onset age).'
        );
      await page.getByTestId('issue-submit').click();
      await expect(page.getByTestId('review-issue')).toContainText(
        'Please double-check variant annotation'
      );

      // 5. Test Responsive / Mobile Viewport
      await page.setViewportSize({ width: 375, height: 667 });
      await page.waitForTimeout(300);
      // Ensure workspace remains functional and no layout rupture occurs
      await expect(page.getByRole('heading', { name: `Review ${recordId}` })).toBeVisible();
      // Restore desktop viewport
      await page.setViewportSize({ width: 1280, height: 800 });
      await page.waitForTimeout(300);

      // 6. Review Decision: Request Changes
      await page.getByTestId('action-request_changes').click();
      await page
        .getByLabel('Decision rationale')
        .fill('Requires HPO onset refinement and variant check.');
      await page.getByTestId('decision-submit').click();

      // Verify status transitions to "Changes requested"
      await expect(page.getByText('Changes requested').first()).toBeVisible({ timeout: 15_000 });

      // 7. Curator A addresses feedback and updates record
      const contextAfterCR = await (
        await request.get(`${API_BASE}/phenopackets/${recordId}/review-context`, {
          headers: authHeader(curatorAToken),
        })
      ).json();

      // Resolve the reviewer issue via API
      const issues = contextAfterCR.issues;
      if (issues && issues.length > 0) {
        await request.patch(`${API_BASE}/phenopackets/${recordId}/review-issues/${issues[0].id}`, {
          headers: authHeader(curatorAToken),
          data: {
            resolution_status: 'addressed',
            resolution_rationale: 'Updated onset and verified variant descriptors.',
          },
        });
      }

      const currentDetail = await (
        await request.get(`${API_BASE}/phenopackets/${recordId}`, {
          headers: authHeader(curatorAToken),
        })
      ).json();

      const updatedCandidate = structuredClone(currentDetail.phenopacket);
      updatedCandidate.hnf1bCuration.caseComment =
        'Updated comment: Phenotype characterized by bilateral renal cysts, confirmed maternal MODY5.';
      const updateResp = await request.put(`${API_BASE}/phenopackets/${recordId}`, {
        headers: authHeader(curatorAToken),
        data: {
          phenopacket: updatedCandidate,
          revision: currentDetail.revision,
          change_reason: 'Curator A addresses reviewer feedback with refined case comment',
        },
      });
      const updateBody = await updateResp.text();
      expect(updateResp.ok(), `update failed: ${updateResp.status()} ${updateBody}`).toBeTruthy();
      const updatedRecord = JSON.parse(updateBody);

      // Curator A re-submits for cycle 2
      const resubmitResp = await request.post(`${API_BASE}/phenopackets/${recordId}/transitions`, {
        headers: authHeader(curatorAToken),
        data: {
          to_state: 'in_review',
          reason: 'Curator A re-submits with clarified clinical details',
          revision: updatedRecord.revision,
        },
      });
      expect(resubmitResp.ok()).toBeTruthy();

      // 8. Curator B approves the second cycle revision
      await page.goto(`/review/${recordId}`, { waitUntil: 'domcontentloaded' });
      await expect(page.getByRole('heading', { name: `Review ${recordId}` })).toBeVisible({
        timeout: 15_000,
      });

      // Semantic diff in cycle 2 should display updated curation comment
      await expect(page.getByRole('heading', { name: 'Metadata' })).toBeVisible();

      // Resolve the blocking issue through the UI
      await page.getByRole('button', { name: 'Resolve issue' }).click();
      await page.locator('#issue-disposition').selectOption('addressed');
      await page
        .locator('#issue-text')
        .fill('Confirmed variant and HPO onset clarifications in cycle 2.');
      await page.getByTestId('issue-submit').click();
      await expect(page.getByText('Resolved by dev-curator-b')).toBeVisible({ timeout: 10_000 });

      // Curator B approves
      await page.getByTestId('action-approve').click();
      await page
        .getByLabel('Decision rationale')
        .fill('All clinical and variant concerns fully resolved.');
      // Attestation checkboxes
      await page.locator('#attest-independent-review').check();
      await page.locator('#attest-no-conflict').check();
      await page.getByTestId('decision-submit').click();

      // Verify approved state
      await expect(page.getByText('Approved').first()).toBeVisible({ timeout: 15_000 });

      // 9. Admin publishes the approved record
      const approveContext = await (
        await request.get(`${API_BASE}/phenopackets/${recordId}/review-context`, {
          headers: authHeader(adminToken),
        })
      ).json();

      const exactApproval = approveContext.approved;
      const publishResp = await request.post(`${API_BASE}/phenopackets/${recordId}/transitions`, {
        headers: authHeader(adminToken),
        data: {
          to_state: 'published',
          reason: 'Admin publishes validated case',
          revision: approveContext.record_revision,
          approved_revision_id: exactApproval.id,
          approved_content_sha256: exactApproval.content_sha256,
        },
      });
      const publishBody = await publishResp.text();
      expect(
        publishResp.ok(),
        `publish failed: ${publishResp.status()} ${publishBody}`
      ).toBeTruthy();

      // 10. Anonymous discovery check
      const publicResp = await request.get(`${API_BASE}/phenopackets/${recordId}`);
      expect(publicResp.ok()).toBeTruthy();
      const publicData = await publicResp.json();
      expect(publicData.phenopacket.id).toBe(recordId);
    } catch (err) {
      primaryError = err;
      throw err;
    } finally {
      await archiveE2ERecord(request, API_BASE, adminToken, recordId, recordCreated, primaryError);
    }
  });
});
