import { test, expect } from '@playwright/test';
import { apiLogin } from './helpers/auth.js';

/**
 * Every anchor with target="_blank" must carry rel containing both
 * "noopener" and "noreferrer". Covers H1 from the 2026-04-17 review.
 */
const PAGES_WITH_EXTERNAL_LINKS = ['/publications', '/about', '/faq'];
const FRONTEND_BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173';
const AUTH_CREDENTIAL_CANDIDATES =
  process.env.E2E_ADMIN_USERNAME && process.env.E2E_ADMIN_PASSWORD
    ? [{ username: process.env.E2E_ADMIN_USERNAME, password: process.env.E2E_ADMIN_PASSWORD }]
    : [
        { username: 'admin', password: 'ChangeMe!Admin2025' },
        { username: 'dev-admin', password: 'DevAdmin!2026' },
      ];

function getHealthUrl(apiBase) {
  const urls = [];
  try {
    urls.push(new URL('/health', new URL(apiBase).origin).toString());
  } catch {
    // Relative API bases are handled via frontend proxy and local backend fallback.
  }
  urls.push(new URL('/health', FRONTEND_BASE_URL).toString());
  if (!apiBase.startsWith('http://') && !apiBase.startsWith('https://')) {
    urls.push('http://localhost:8000/health');
  }
  return [...new Set(urls)];
}

async function isBackendAvailable(request) {
  const apiBase =
    process.env.E2E_API_BASE || process.env.VITE_API_URL || 'http://localhost:8000/api/v2';
  for (const healthUrl of getHealthUrl(apiBase)) {
    try {
      const response = await request.get(healthUrl, { failOnStatusCode: false });
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

async function loginForAuthenticatedCoverage(request, apiBase) {
  let lastError;
  for (const candidate of AUTH_CREDENTIAL_CANDIDATES) {
    try {
      return await apiLogin(request, apiBase, candidate.username, candidate.password);
    } catch (error) {
      lastError = error;
    }
  }
  throw (
    lastError ?? new Error('No authentication credentials configured for authenticated UI coverage')
  );
}

/**
 * Snapshot all target=_blank anchors via evaluate (one-shot DOM read) to
 * avoid Playwright locator handles going stale on pages that have a live
 * log-viewer appending DOM nodes during the assertion loop.
 */
async function assertExternalLinkRels(page) {
  const anchors = await page.evaluate(() =>
    Array.from(document.querySelectorAll('a[target="_blank"]')).map((a) => ({
      href: a.getAttribute('href'),
      rel: (a.getAttribute('rel') || '').split(/\s+/).filter(Boolean),
    }))
  );
  expect(anchors.length, 'expected at least one external anchor').toBeGreaterThan(0);
  for (const { href, rel } of anchors) {
    expect(rel, `anchor ${href} must include noopener`).toContain('noopener');
    expect(rel, `anchor ${href} must include noreferrer`).toContain('noreferrer');
  }
}

async function tabToLocator(page, locator, maxTabs = 40) {
  for (let attempt = 0; attempt < maxTabs; attempt += 1) {
    await page.keyboard.press('Tab');
    if (await locator.evaluate((element) => element === document.activeElement)) {
      return;
    }
  }
  throw new Error(`Failed to focus target via keyboard after ${maxTabs} Tab presses`);
}

for (const path of PAGES_WITH_EXTERNAL_LINKS) {
  test(`external anchors on ${path} carry rel=noopener noreferrer`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    await assertExternalLinkRels(page);
  });
}

test('external anchors on a publication detail page carry rel', async ({ page }) => {
  await page.goto('/publications');
  await page.waitForLoadState('networkidle');
  const pmidChip = page.locator('a.v-chip[href*="/publications/"]').first();
  // CI seeds no publications by default; skip cleanly when the table is empty
  // rather than waiting 60s for a row that will never appear.
  if ((await pmidChip.count()) === 0) {
    test.skip(true, 'No seeded publications on this environment — detail-page coverage deferred');
  }
  await pmidChip.waitFor({ state: 'visible', timeout: 10_000 });
  await pmidChip.click();
  await page.waitForLoadState('networkidle');
  await assertExternalLinkRels(page);
});

test.describe('Real h1 on list + create views (H2)', () => {
  for (const path of ['/phenopackets', '/publications', '/variants']) {
    test(`${path} exposes an h1`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState('networkidle');
      await expect(page.locator('h1')).toHaveCount(1);
      const text = await page.locator('h1').innerText();
      expect(text.length).toBeGreaterThan(0);
    });
  }

  test('/phenopackets/create exposes an h1', async ({ page, request }) => {
    test.skip(
      !(await isBackendAvailable(request)),
      'Backend unavailable for authenticated create-page coverage'
    );
    const { primeAuthSession } = await import('./helpers/auth.js');
    const apiBase =
      process.env.E2E_API_BASE || process.env.VITE_API_URL || 'http://localhost:8000/api/v2';
    const resolvedApiBase = new URL(apiBase, FRONTEND_BASE_URL).toString().replace(/\/$/, '');
    const auth = await loginForAuthenticatedCoverage(request, resolvedApiBase);
    await primeAuthSession(page, auth);
    await page.goto('/phenopackets/create');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toBeVisible();
  });
});

test.describe('Keyboard row activation (H3)', () => {
  test('Tab reaches first subject-id chip on /phenopackets and Enter navigates', async ({
    page,
  }) => {
    await page.goto('/phenopackets');
    await page.waitForLoadState('networkidle');
    const firstChipAnchor = page.locator('table a.v-chip').first();
    if ((await firstChipAnchor.count()) === 0) {
      test.skip(true, 'No seeded phenopackets on this environment');
    }
    await firstChipAnchor.waitFor({ state: 'visible' });
    const href = await firstChipAnchor.getAttribute('href');
    expect(href).toMatch(/^\/phenopackets\/[^/]+$/);
    await tabToLocator(page, firstChipAnchor);
    await expect(firstChipAnchor).toBeFocused();
    await page.keyboard.press('Enter');
    await page.waitForURL(/\/phenopackets\/[^/]+$/, { timeout: 5000 });
  });

  test('/variants first chip is a keyboard-reachable anchor', async ({ page }) => {
    await page.goto('/variants');
    await page.waitForLoadState('networkidle');
    const firstChipAnchor = page.locator('table a.v-chip').first();
    if ((await firstChipAnchor.count()) === 0) {
      test.skip(true, 'No seeded variants on this environment');
    }
    await firstChipAnchor.waitFor({ state: 'visible', timeout: 10_000 });
    const href = await firstChipAnchor.getAttribute('href');
    expect(href).toMatch(/^\/variants\//);
    await tabToLocator(page, firstChipAnchor);
    await expect(firstChipAnchor).toBeFocused();
    await page.keyboard.press('Enter');
    await page.waitForURL(/\/variants\/.+$/, { timeout: 5000 });
  });

  test('/publications PMID chip is a keyboard-reachable anchor', async ({ page }) => {
    await page.goto('/publications');
    await page.waitForLoadState('networkidle');
    const firstChipAnchor = page.locator('table a.v-chip[href*="/publications/"]').first();
    if ((await firstChipAnchor.count()) === 0) {
      test.skip(true, 'No seeded publications on this environment');
    }
    await firstChipAnchor.waitFor({ state: 'visible', timeout: 10_000 });
    const href = await firstChipAnchor.getAttribute('href');
    expect(href).toMatch(/^\/publications\//);
    await tabToLocator(page, firstChipAnchor);
    await expect(firstChipAnchor).toBeFocused();
    await page.keyboard.press('Enter');
    await page.waitForURL(/\/publications\/.+$/, { timeout: 5000 });
  });
});

// H5 composer accessibility assertions live in
// tests/unit/components/comments/CommentComposer.spec.js — the component
// contract (aria-label on .ProseMirror + toolbar buttons) is cheaper and
// more robust to verify in a unit test than navigating to a seeded
// authenticated detail page in Playwright.

test.describe('Skip-to-main-content (L6)', () => {
  test('first tab-able element is a visible skip link pointing to #main-content', async ({
    page,
  }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.keyboard.press('Tab');
    const skipLink = page.locator('a[href="#main-content"]').first();
    await expect(skipLink).toBeVisible();
    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      return el
        ? { tag: el.tagName, href: el.getAttribute('href'), text: el.textContent?.trim() }
        : null;
    });
    expect(focused?.tag).toBe('A');
    expect(focused?.href).toBe('#main-content');
    expect(focused?.text?.toLowerCase()).toContain('skip');
    await expect(page.locator('#main-content')).toHaveCount(1);
  });
});
