// @ts-check
/**
 * Variant browse flow E2E coverage (follow-up #358 from #48).
 *
 * Unauthenticated read-only flow:
 *   variants registry  ->  variant detail  ->  affected individuals  ->  phenopacket
 *
 * Also checks that returning from a detail page restores the variants list
 * (URL/state preservation). No auth or seeded data is required — the curated
 * variant dataset is public.
 */

import { test, expect } from '@playwright/test';

test.describe('Variant browse flow', () => {
  test('variants list -> detail -> affected individuals -> phenopacket', async ({ page }) => {
    await page.goto('/variants');
    await expect(page.getByRole('heading', { name: /Variants Registry/i })).toBeVisible();

    // First variant row links to its detail page (/variants/<id>).
    const firstVariant = page.locator('table tbody tr a[href^="/variants/"]').first();
    await expect(firstVariant).toBeVisible();

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
    await page.goto('/variants');
    const firstVariant = page.locator('table tbody tr a[href^="/variants/"]').first();
    await expect(firstVariant).toBeVisible();
    await firstVariant.click();
    await expect(page.getByRole('heading', { name: 'Variant Details' })).toBeVisible();

    await page.goBack();
    await expect(page).toHaveURL(/\/variants(\?.*)?$/);
    await expect(page.getByRole('heading', { name: /Variants Registry/i })).toBeVisible();
    // The table is repopulated (not stuck on an empty/loading state).
    await expect(page.locator('table tbody tr a[href^="/variants/"]').first()).toBeVisible();
  });
});
