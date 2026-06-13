// @ts-check
/**
 * Variant browse flow E2E coverage (follow-up #358 from #48).
 *
 * Unauthenticated read-only flow:
 *   variants registry  ->  variant detail  ->  affected individuals  ->  phenopacket
 *
 * Also checks that returning from a detail page restores the variants list
 * (URL/state preservation).
 *
 * These flows need curated variant data to exist. Environments seeded with
 * only an admin user (e.g. CI's minimal test DB) have an empty variants
 * registry, so — mirroring the established pattern in ui-hardening-a11y.spec.js
 * ("No seeded variants on this environment") — the tests skip cleanly there and
 * run for real against any populated dataset (local dev, staging).
 */

import { test, expect } from '@playwright/test';

const VARIANT_ROW_LINK = 'table tbody tr a[href^="/variants/"]';

/**
 * Open /variants and return its first variant-row link, or skip the test when
 * the registry is empty (unseeded environment).
 * @param {import('@playwright/test').Page} page
 */
async function firstVariantOrSkip(page) {
  await page.goto('/variants');
  await page.waitForLoadState('networkidle');
  await expect(page.getByRole('heading', { name: /Variants Registry/i })).toBeVisible();
  const firstVariant = page.locator(VARIANT_ROW_LINK).first();
  if ((await firstVariant.count()) === 0) {
    test.skip(true, 'No seeded variants on this environment');
  }
  await firstVariant.waitFor({ state: 'visible', timeout: 10_000 });
  return firstVariant;
}

test.describe('Variant browse flow', () => {
  test('variants list -> detail -> affected individuals -> phenopacket', async ({ page }) => {
    const firstVariant = await firstVariantOrSkip(page);

    await firstVariant.click();
    // Landed on a variant detail page (a non-empty id segment after /variants/).
    await expect(page).toHaveURL(/\/variants\/.+/);
    await expect(page.getByRole('heading', { name: 'Variant Details' })).toBeVisible();

    // The Affected Individuals section lists the carriers of this variant.
    await expect(page.getByText(/Affected Individuals \(\d+\)/)).toBeVisible();

    // Each carrier links to its phenopacket; following one lands on the detail.
    const carrier = page.locator('a[href^="/phenopackets/"]').first();
    await expect(carrier).toBeVisible();
    await carrier.click();
    await expect(page).toHaveURL(/\/phenopackets\/.+/);
  });

  test('returning from a variant detail restores the variants registry', async ({ page }) => {
    const firstVariant = await firstVariantOrSkip(page);

    await firstVariant.click();
    await expect(page.getByRole('heading', { name: 'Variant Details' })).toBeVisible();

    await page.goBack();
    await expect(page).toHaveURL(/\/variants(\?.*)?$/);
    await expect(page.getByRole('heading', { name: /Variants Registry/i })).toBeVisible();
    // The table is repopulated (not stuck on an empty/loading state).
    await expect(page.locator(VARIANT_ROW_LINK).first()).toBeVisible();
  });
});
