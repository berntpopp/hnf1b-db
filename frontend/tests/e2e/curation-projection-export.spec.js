// @ts-check
import { expect, test } from '@playwright/test';

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173';

test('copy and download JSON use only the authoritative server-redacted projection', async ({
  context,
  page,
}) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: BASE_URL });
  await context.addCookies([{ name: 'csrf_token', value: 'e2e-csrf', url: BASE_URL }]);
  const projected = {
    id: 'PP-317',
    subject: { id: '317', sex: 'MALE' },
    phenotypicFeatures: [],
    interpretations: [],
    metaData: { externalReferences: [{ id: 'PMID:123' }] },
  };
  const privateProfile = {
    ...projected,
    hnf1bCuration: { observationsById: { 'report-private': { reviewerDisplayLabel: 'Private' } } },
  };

  await page.route('**/api/v2/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body) =>
      route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
    if (path.endsWith('/auth/refresh')) return json({ access_token: 'e2e-access-token' });
    if (path.endsWith('/auth/me')) return json({ id: 1, username: 'admin', role: 'admin' });
    if (path.endsWith('/phenopackets/PP-317/export')) return json(projected);
    if (path.endsWith('/phenopackets/PP-317')) {
      return json({ phenopacket: privateProfile, revision: 7, state: 'published' });
    }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/phenopackets/PP-317');
  await page.getByRole('tab', { name: 'Raw JSON tab' }).click();
  await page.getByRole('button', { name: 'Copy JSON to clipboard' }).click();
  await expect
    .poll(() => page.evaluate(() => navigator.clipboard.readText()))
    .toBe(JSON.stringify(projected, null, 2));
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).not.toContain('hnf1bCuration');
  expect(copied).not.toContain('reviewerDisplayLabel');

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download phenopacket as JSON file' }).click();
  const download = await downloadPromise;
  const chunks = [];
  for await (const chunk of await download.createReadStream()) chunks.push(chunk);
  const downloaded = Buffer.concat(chunks).toString('utf8');

  expect(download.suggestedFilename()).toBe('PP-317.json');
  expect(downloaded).toBe(JSON.stringify(projected, null, 2));
  expect(downloaded).not.toContain('hnf1bCuration');
  expect(downloaded).not.toContain('reviewerDisplayLabel');
});
