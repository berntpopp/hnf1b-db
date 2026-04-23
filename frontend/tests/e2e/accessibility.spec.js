import AxeBuilder from '@axe-core/playwright';
import { test, expect } from '@playwright/test';

import { apiLogin, primeAuthSession } from './helpers/auth';

const FRONTEND_BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173';
const API_BASE =
  process.env.E2E_API_BASE || process.env.VITE_API_URL || 'http://localhost:8000/api/v2';
const RESOLVED_API_BASE = new URL(API_BASE, FRONTEND_BASE_URL).toString().replace(/\/$/, '');
const AUTH_CREDENTIAL_CANDIDATES =
  process.env.E2E_ADMIN_USERNAME && process.env.E2E_ADMIN_PASSWORD
    ? [{ username: process.env.E2E_ADMIN_USERNAME, password: process.env.E2E_ADMIN_PASSWORD }]
    : [
        { username: 'admin', password: 'ChangeMe!Admin2025' },
        { username: 'dev-admin', password: 'DevAdmin!2026' },
      ];

function getHealthUrl() {
  const urls = [];
  try {
    urls.push(new URL('/health', new URL(API_BASE).origin).toString());
  } catch {
    // Relative API bases are handled via frontend proxy and local backend fallback.
  }
  urls.push(new URL('/health', FRONTEND_BASE_URL).toString());
  if (!API_BASE.startsWith('http://') && !API_BASE.startsWith('https://')) {
    urls.push('http://localhost:8000/health');
  }
  return [...new Set(urls)];
}

async function isBackendAvailable(request) {
  for (const healthUrl of getHealthUrl()) {
    try {
      const response = await request.get(healthUrl, {
        failOnStatusCode: false,
      });
      if (!response.ok()) {
        continue;
      }
      const payload = await response.json().catch(() => null);
      if (payload?.ready === true || payload?.status === 'healthy') {
        return true;
      }
    } catch {
      // Try the next candidate URL.
    }
  }
  return false;
}

async function loginForAuthenticatedCoverage(request) {
  let lastError;
  for (const candidate of AUTH_CREDENTIAL_CANDIDATES) {
    try {
      return await apiLogin(request, RESOLVED_API_BASE, candidate.username, candidate.password);
    } catch (error) {
      lastError = error;
    }
  }
  throw (
    lastError ?? new Error('No authentication credentials configured for accessibility coverage')
  );
}

async function expectNoSeriousAxeViolations(page, configure) {
  let builder = new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .options({
      rules: {
        'target-size': { enabled: true },
      },
    });
  if (configure) {
    builder = configure(builder);
  }

  const results = await builder.analyze();

  const seriousViolations = results.violations.filter((violation) =>
    ['serious', 'critical'].includes(violation.impact)
  );

  expect(seriousViolations, JSON.stringify(seriousViolations, null, 2)).toEqual([]);
}

test('homepage has no serious accessibility violations', async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('networkidle');

  await expect(page.locator('main, #main-content')).toHaveCount(1);
  await expect(page.locator('.v-skeleton-loader')).toHaveCount(0);
  await expect(page.locator('.stat-card .text-h4 span')).toHaveCount(4);
  await expectNoSeriousAxeViolations(page, (builder) =>
    builder.exclude('.v-tooltip').exclude('.v-window-item:not(.v-window-item--active)')
  );
});

test('authenticated phenopacket detail has no serious accessibility violations', async ({
  page,
  request,
}) => {
  test.skip(
    !(await isBackendAvailable(request)),
    'Backend unavailable for authenticated phenopacket accessibility scan'
  );
  const auth = await loginForAuthenticatedCoverage(request);

  const recordId = `e2e-a11y-${Date.now()}`;
  let created = false;
  let revision = 1;
  try {
    const createResp = await request.post(`${RESOLVED_API_BASE}/phenopackets/`, {
      headers: { Authorization: `Bearer ${auth.accessToken}` },
      data: {
        phenopacket: {
          id: recordId,
          subject: { id: `subject-${recordId}`, sex: 'UNKNOWN_SEX' },
          metaData: {
            created: new Date().toISOString(),
            createdBy: 'e2e-a11y-test',
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
    const createdBody = await createResp.json();
    revision = createdBody.phenopacket?.revision ?? revision;
    created = true;

    await primeAuthSession(page, auth);
    await page.goto(`/phenopackets/${recordId}`, { waitUntil: 'networkidle' });
    await expect(
      page.getByRole('button', { name: 'Download phenopacket as JSON file' })
    ).toBeVisible();
    await expect(page.locator('.v-chip').filter({ hasText: recordId }).first()).toBeVisible();
    await expect(page.getByText('Error Loading Phenopacket')).toHaveCount(0);

    await expectNoSeriousAxeViolations(page, (builder) => builder.exclude('.v-tooltip'));
  } finally {
    if (created) {
      const deleteResp = await request.delete(`${RESOLVED_API_BASE}/phenopackets/${recordId}`, {
        headers: { Authorization: `Bearer ${auth.accessToken}` },
        data: {
          change_reason: 'Clean up accessibility test fixture',
          revision,
        },
        failOnStatusCode: false,
      });
      expect(deleteResp.ok(), `Fixture cleanup failed: ${await deleteResp.text()}`).toBeTruthy();
    }
  }
});
