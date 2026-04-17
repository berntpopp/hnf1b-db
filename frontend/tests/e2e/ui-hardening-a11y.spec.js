import { test, expect } from '@playwright/test';

/**
 * Every anchor with target="_blank" must carry rel containing both
 * "noopener" and "noreferrer". Covers H1 from the 2026-04-17 review.
 */
const PAGES_WITH_EXTERNAL_LINKS = ['/publications', '/about', '/faq'];

/**
 * Snapshot all target=_blank anchors via evaluate (one-shot DOM read) to
 * avoid Playwright locator handles going stale on pages that have a live
 * log-viewer appending DOM nodes during the assertion loop.
 */
async function assertExternalLinkRels(page) {
  const anchors = await page.evaluate(() =>
    Array.from(document.querySelectorAll('a[target="_blank"]')).map((a) => ({
      href: a.getAttribute('href'),
      rel: a.getAttribute('rel') || '',
    }))
  );
  expect(anchors.length, 'expected at least one external anchor').toBeGreaterThan(0);
  for (const { href, rel } of anchors) {
    expect(rel, `anchor ${href} must include noopener`).toContain('noopener');
    expect(rel, `anchor ${href} must include noreferrer`).toContain('noreferrer');
  }
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
  // Explicit selector wait guards against slow list hydration under CI.
  await page.waitForSelector('a.v-chip[href*="/publications/"]', { state: 'visible' });
  const firstPmidChip = page.locator('a.v-chip[href*="/publications/"]').first();
  await firstPmidChip.click();
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
    const { apiLogin, primeAuthSession } = await import('./helpers/auth.js');
    const apiBase = process.env.E2E_API_BASE || 'http://localhost:8000/api/v2';
    const auth = await apiLogin(request, apiBase, 'dev-admin', 'DevAdmin!2026');
    await primeAuthSession(page, auth);
    await page.goto('/phenopackets/create');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toBeVisible();
  });
});
