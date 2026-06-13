// @ts-check
/**
 * Aggregations dashboard E2E coverage (follow-up #358 from #48).
 *
 * Unauthenticated read-only flow: the /aggregations dashboard renders its
 * charts in tabs (AggregationsDashboard.vue). We assert that:
 *   - the default Donut chart renders,
 *   - every chart tab activates without surfacing a page-level error,
 *   - the donut re-renders across the Phenopackets aggregation dimensions
 *     (Sex Distribution / Age of Onset / Kidney Disease Stages).
 *
 * No auth or seeded bulk data is required — the dashboard renders its charts
 * (empty if a dataset is sparse) on any environment. A generous first-paint
 * timeout absorbs cold-start latency on the suite's first hit to the page.
 * The page-level error banner carries data-testid="aggregations-page-error".
 */

import { test, expect } from '@playwright/test';

const CHART_TABS = [
  'Donut Chart',
  'Stacked Bar Chart',
  'Publications Timeline',
  'Variant Comparison',
  'Survival Curves',
  'DNA Distance Analysis',
];

const PAGE_ERROR = '[data-testid="aggregations-page-error"]';
// Cold-start budget for the first chart paint (backend warm-up on the first hit).
const CHART_TIMEOUT = 20_000;

test.describe('Aggregations dashboard', () => {
  test('renders the default donut chart with no page error', async ({ page }) => {
    await page.goto('/aggregations');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: 'Aggregations', level: 1 })).toBeVisible();
    await expect(page.locator(PAGE_ERROR)).toHaveCount(0);
    // The donut is exposed as an accessible image describing the distribution.
    await expect(page.getByRole('img', { name: /donut chart/i })).toBeVisible({
      timeout: CHART_TIMEOUT,
    });
  });

  test('every chart tab activates without surfacing a page error', async ({ page }) => {
    await page.goto('/aggregations');
    await page.waitForLoadState('networkidle');
    const pageError = page.locator(PAGE_ERROR);
    for (const name of CHART_TABS) {
      const tab = page.getByRole('tab', { name, exact: true });
      await tab.click();
      await expect(tab).toHaveAttribute('aria-selected', 'true');
      // Switching to the tab must not put the dashboard into its error state.
      await expect(pageError).toHaveCount(0);
    }
  });

  test('donut re-renders across phenopacket aggregation dimensions', async ({ page }) => {
    await page.goto('/aggregations');
    await page.waitForLoadState('networkidle');
    const donut = page.getByRole('img', { name: /donut chart/i });
    await expect(donut).toBeVisible({ timeout: CHART_TIMEOUT }); // Sex Distribution (default)

    // The Aggregation v-select: click the field (the input is overlaid by
    // .v-field__input, so target the activator container) to open the menu.
    const aggregationSelect = page.locator('.v-select', { hasText: 'Aggregation' });
    for (const dimension of ['Age of Onset', 'Kidney Disease Stages']) {
      await aggregationSelect.click();
      await page.getByRole('option', { name: dimension }).click();
      await expect(donut).toBeVisible({ timeout: CHART_TIMEOUT });
      await expect(page.locator(PAGE_ERROR)).toHaveCount(0);
    }
  });
});
