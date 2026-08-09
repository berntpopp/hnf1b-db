// @ts-check
import { expect, test } from '@playwright/test';

const FRONTEND_BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173';
const observed = (raw, value) => ({ raw, sourceStatus: 'stated', value, correctionIds: [] });

function report(observationId, reportId, sex, pmid) {
  return {
    observationId,
    origin: 'manual',
    source: {
      provider: 'fixture',
      datasetId: 'registry',
      sheet: 'Individuals',
      manifestSha256: 'sha256:fixture',
    },
    identifiers: {
      individualId: '317',
      sourceSubjectId: 'source-317',
      reportId,
      sex: observed(sex === 'MALE' ? 'M' : 'F', sex),
    },
    publication: {
      sourceKey: observed(`source-${reportId}`, `source-${reportId}`),
      publicationType: observed('case report', 'case_report'),
      pmid,
      doi: `10.1000/${reportId.toLowerCase()}`,
    },
    ages: {
      onset: observed('28w', { kind: 'gestationalAge', iso8601Duration: 'P28W' }),
      reported: observed('12y', { kind: 'age', iso8601Duration: 'P12Y' }),
    },
    variant: {
      reported: observed('c.123A>G', 'NM_000458.4:c.123A>G'),
      hg19Info: observed('chr17:36000000:A:G', 'chr17:36000000:A:G'),
      hg38Info: observed('chr17:37700000:A:G', 'chr17:37700000:A:G'),
      detectionMethod: observed('Sanger', 'sanger'),
      segregation: observed('de novo', 'de_novo'),
    },
    phenotypes: [
      {
        assessmentId: `assessment-${observationId}`,
        column: 'RenalCysts',
        rawValue: 'unilateral left',
        sourceStatus: 'stated',
        curationStatus: 'CURATED',
        assessmentStatus: 'PRESENT',
        findings: [
          {
            definitionId: 'renal-cyst',
            term: { id: 'HP:0000107', label: 'Renal cyst' },
            modifiers: [
              { id: 'HP:0012833', label: 'Unilateral' },
              { id: 'HP:0012835', label: 'Left' },
            ],
          },
        ],
        evidence: [
          {
            reference: `PMID:${pmid}`,
            evidenceCode: { id: 'ECO:0006013', label: 'traceable author statement' },
          },
        ],
      },
    ],
    sourceReview: { reviewerDisplayLabel: `Reviewer ${reportId}`, reviewedOn: '2025-01-01' },
    notes: { comment: observed('source note', 'source note') },
  };
}

test('edits one report losslessly, previews, and resolves a deterministic conflict', async ({
  page,
}) => {
  await page
    .context()
    .addCookies([{ name: 'csrf_token', value: 'e2e-csrf', url: FRONTEND_BASE_URL }]);

  let revision = 7;
  let observations = [
    report('report-1', 'RPT-1', 'MALE', '123'),
    report('report-2', 'RPT-2', 'FEMALE', '456'),
  ];
  let issues = [
    {
      code: 'projection_conflict',
      message: 'Projection conflict: subject:sex',
      path: ['projection', 'blockingConflicts'],
      observationId: 'report-1',
      conflictKey: 'subject:sex',
      candidateSetDigest: 'sha256:sex-candidates',
      severity: 'blocking',
    },
  ];
  /** @type {any} */
  let savedBody;
  /** @type {Record<string, string>} */
  let savedHeaders = {};

  const ledger = () => ({
    phenopacketId: 'PP-317',
    revision,
    observations,
    corrections: [],
    resolutions: [],
    projection: {
      phenopacket: {
        id: 'PP-317',
        subject: { id: '317', sex: 'MALE' },
        phenotypicFeatures: [],
        interpretations: [],
        metaData: { externalReferences: [{ id: 'PMID:123' }] },
      },
      observationsDigest: 'sha256:observations',
      outputDigest: `sha256:output-${revision}`,
      issues,
    },
  });

  await page.route('**/api/v2/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/\/+$/, '');
    const json = (body, status = 200, headers = {}) =>
      route.fulfill({
        status,
        headers: { 'content-type': 'application/json', ...headers },
        body: JSON.stringify(body),
      });

    if (path.endsWith('/auth/refresh')) return json({ access_token: 'e2e-access-token' });
    if (path.endsWith('/auth/me')) {
      return json({ id: 1, username: 'admin', full_name: 'Admin User', role: 'admin' });
    }
    if (path.includes('/ontology/vocabularies/')) return json({ data: [] });
    if (path.endsWith('/phenopackets/PP-317') && request.method() === 'GET') {
      return json({
        phenopacket: {
          id: 'PP-317',
          subject: { id: '317', sex: 'MALE' },
          phenotypicFeatures: [],
          interpretations: [],
          metaData: { externalReferences: [] },
        },
        revision,
        state: 'draft',
        effective_state: 'draft',
      });
    }
    if (path.endsWith('/phenopackets/PP-317/curation') && request.method() === 'GET') {
      return json(ledger(), 200, { etag: `"${revision}"` });
    }
    if (path.endsWith('/curation/preview')) {
      return json({ revision, projection: ledger().projection });
    }
    if (path.includes('/reports/') && request.method() === 'PATCH') {
      savedBody = request.postDataJSON();
      savedHeaders = request.headers();
      observations = observations.map((item) =>
        item.observationId === savedBody.observation.observationId ? savedBody.observation : item
      );
      revision += 1;
      return json(ledger(), 200, { etag: `"${revision}"` });
    }
    if (path.endsWith('/curation/resolutions')) {
      issues = [];
      revision += 1;
      return json(ledger(), 200, { etag: `"${revision}"` });
    }
    return json({ detail: 'not mocked' }, 404);
  });

  await page.goto('/phenopackets/PP-317/edit');
  await expect(page.getByRole('heading', { name: 'Report observation ledger' })).toBeVisible();
  await expect(page.getByText('One individual, 2 source reports')).toBeVisible();
  await expect(page.getByText('Projection conflict: subject:sex')).toBeVisible();

  await page.locator('[name="doi"]').fill('10.2000/revised');
  await page.locator('[data-laterality="assessment-report-1"]').selectOption('unilateral-right');
  await page.locator('[name="change-reason"]').fill('Reviewed report publication and laterality.');
  await page.locator('[data-action="save-report"]').click();

  await expect.poll(() => savedBody?.observation?.publication?.doi).toBe('10.2000/revised');
  expect(savedHeaders['if-match']).toBe('"7"');
  expect(savedBody.observation.publication.publicationType).toEqual(
    expect.objectContaining({ raw: 'case report', value: 'case_report' })
  );
  expect(savedBody.observation.phenotypes[0].findings[0].modifiers).toEqual([
    { id: 'HP:0012833', label: 'Unilateral' },
    { id: 'HP:0012834', label: 'Right' },
  ]);
  expect(savedBody.observation.phenotypes[0].evidence).toEqual([
    expect.objectContaining({ reference: 'PMID:123' }),
  ]);

  await page.locator('[data-candidate="report-1"]').check();
  await page
    .locator('[data-reason="subject:sex"]')
    .fill('Use the report with direct clinical ascertainment.');
  await page.locator('[data-resolve="subject:sex"]').click();
  await expect(page.getByText('No unresolved projection conflicts.')).toBeVisible();
});
