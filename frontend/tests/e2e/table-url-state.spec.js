// @ts-check
import { test, expect } from '@playwright/test';

/**
 * Table URL State Synchronization Tests
 *
 * Tests that table state (pagination, sorting, search, filters) is properly
 * synchronized with URL parameters for shareable/bookmarkable links.
 */

const BASE_URL = 'http://localhost:5173';

test.describe('Variants Table URL State', () => {
  test('should preserve page parameter in URL', async ({ page }) => {
    // Navigate to page 2
    await page.goto(`${BASE_URL}/variants?page=2&pageSize=10`);
    await page.waitForLoadState('networkidle');

    // Verify URL contains page parameter
    expect(page.url()).toContain('page=2');

    // Verify pagination UI shows page 2
    const paginationText = await page.locator('.app-pagination').first().textContent();
    expect(paginationText).toContain('Page 2');
  });

  test('should update URL when navigating pages', async ({ page }) => {
    await page.goto(`${BASE_URL}/variants`);
    await page.waitForLoadState('networkidle');

    // Click next page button
    const nextButton = page
      .locator('[aria-label="next page"], button:has-text("navigate_next")')
      .first();
    if (await nextButton.isVisible()) {
      await nextButton.click();
      await page.waitForLoadState('networkidle');

      // Verify URL updated
      expect(page.url()).toContain('page=2');
    }
  });

  test('should preserve search query in URL', async ({ page }) => {
    // Navigate with search query
    await page.goto(`${BASE_URL}/variants?q=c.826`);
    await page.waitForLoadState('networkidle');

    // Verify search input has the value
    const searchInput = page.locator('input[placeholder*="Search"]').first();
    await expect(searchInput).toHaveValue('c.826');

    // Verify URL contains search query
    expect(page.url()).toContain('q=c.826');
  });

  test('should update URL when searching', async ({ page }) => {
    await page.goto(`${BASE_URL}/variants`);
    await page.waitForLoadState('networkidle');

    // Type in search box
    const searchInput = page.locator('input[placeholder*="Search"]').first();
    await searchInput.fill('pathogenic');
    await searchInput.press('Enter');
    await page.waitForLoadState('networkidle');

    // Verify URL updated with search query
    expect(page.url()).toContain('q=pathogenic');
  });

  test('should preserve sort parameter in URL', async ({ page }) => {
    // Navigate with descending sort on transcript
    await page.goto(`${BASE_URL}/variants?sort=-transcript`);
    await page.waitForLoadState('networkidle');

    // Verify URL contains sort parameter
    expect(page.url()).toContain('sort=-transcript');
  });

  test('should preserve type filter in URL', async ({ page }) => {
    await page.goto(`${BASE_URL}/variants?type=SNV`);
    await page.waitForLoadState('networkidle');

    // Verify URL contains filter
    expect(page.url()).toContain('type=SNV');
  });

  test('should preserve classification filter in URL', async ({ page }) => {
    await page.goto(`${BASE_URL}/variants?classification=PATHOGENIC`);
    await page.waitForLoadState('networkidle');

    // Verify URL contains filter
    expect(page.url()).toContain('classification=PATHOGENIC');
  });

  test('should handle combined URL parameters', async ({ page }) => {
    // Navigate with multiple parameters
    await page.goto(`${BASE_URL}/variants?page=1&pageSize=20&sort=-simple_id&q=c.826&type=SNV`);
    await page.waitForLoadState('networkidle');

    // Verify all parameters are in URL
    const url = page.url();
    expect(url).toContain('pageSize=20');
    expect(url).toContain('sort=-simple_id');
    expect(url).toContain('q=c.826');
    expect(url).toContain('type=SNV');
  });

  test('partial HGVS search should work without error', async ({ page }) => {
    await page.goto(`${BASE_URL}/variants`);
    await page.waitForLoadState('networkidle');

    // Type partial HGVS (this used to return 400 error)
    const searchInput = page.locator('input[placeholder*="Search"]').first();
    await searchInput.fill('c.826');
    await searchInput.press('Enter');
    await page.waitForLoadState('networkidle');

    // Should not show error alert
    const errorAlert = page.locator('.v-alert[type="error"]');
    await expect(errorAlert).not.toBeVisible();

    // URL should contain search query
    expect(page.url()).toContain('q=c.826');
  });
});

test.describe('Phenopackets Table URL State', () => {
  test('should preserve page parameter in URL', async ({ page }) => {
    await page.goto(`${BASE_URL}/phenopackets?page=2&pageSize=10`);
    await page.waitForLoadState('networkidle');

    expect(page.url()).toContain('page=2');
  });

  test('should preserve search query in URL', async ({ page }) => {
    await page.goto(`${BASE_URL}/phenopackets?q=test`);
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('input[placeholder*="Search"]').first();
    await expect(searchInput).toHaveValue('test');
    expect(page.url()).toContain('q=test');
  });

  test('should preserve sex filter in URL', async ({ page }) => {
    await page.goto(`${BASE_URL}/phenopackets?sex=MALE`);
    await page.waitForLoadState('networkidle');

    expect(page.url()).toContain('sex=MALE');
  });

  test('should update URL when using sex filter', async ({ page }) => {
    await page.goto(`${BASE_URL}/phenopackets`);
    await page.waitForLoadState('networkidle');

    // Find and click the sex filter icon (in the column header)
    const filterButton = page.locator('.header-wrapper button:has(.v-icon)').first();
    if (await filterButton.isVisible()) {
      await filterButton.click();

      // Select MALE from the dropdown
      const maleOption = page.locator('.v-list-item:has-text("MALE")');
      if (await maleOption.isVisible()) {
        await maleOption.click();
        await page.waitForLoadState('networkidle');

        // Verify URL updated
        expect(page.url()).toContain('sex=MALE');
      }
    }
  });

  test('should clear filters and update URL', async ({ page }) => {
    await page.goto(`${BASE_URL}/phenopackets?q=test&sex=MALE`);
    await page.waitForLoadState('networkidle');

    // Find and click clear filters button
    const clearButton = page.locator('button:has-text("Clear Filters")');
    if (await clearButton.isVisible()) {
      await clearButton.click();
      await page.waitForLoadState('networkidle');

      // Verify filters removed from URL
      const url = page.url();
      expect(url).not.toContain('q=test');
      expect(url).not.toContain('sex=MALE');
    }
  });
});

test.describe('Publications Table URL State', () => {
  test('should preserve page parameter in URL', async ({ page }) => {
    await page.goto(`${BASE_URL}/publications?page=2&pageSize=10`);
    await page.waitForLoadState('networkidle');

    expect(page.url()).toContain('page=2');
  });

  test('should preserve search query in URL', async ({ page }) => {
    await page.goto(`${BASE_URL}/publications?q=kidney`);
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('input[placeholder*="Search"]').first();
    await expect(searchInput).toHaveValue('kidney');
    expect(page.url()).toContain('q=kidney');
  });

  test('should preserve sort parameter in URL', async ({ page }) => {
    await page.goto(`${BASE_URL}/publications?sort=-first_added`);
    await page.waitForLoadState('networkidle');

    expect(page.url()).toContain('sort=-first_added');
  });

  test('should handle pageSize parameter', async ({ page }) => {
    await page.goto(`${BASE_URL}/publications?pageSize=50`);
    await page.waitForLoadState('networkidle');

    expect(page.url()).toContain('pageSize=50');
  });
});

test.describe('URL State Shareable Links', () => {
  test('should produce identical results when sharing URL', async ({ page, context }) => {
    // First user sets up filters
    await page.goto(`${BASE_URL}/variants`);
    await page.waitForLoadState('networkidle');

    // Apply search
    const searchInput = page.locator('input[placeholder*="Search"]').first();
    await searchInput.fill('deletion');
    await searchInput.press('Enter');
    await page.waitForLoadState('networkidle');

    // Get the shareable URL
    const shareableUrl = page.url();

    // Open new page (simulating shared link)
    const newPage = await context.newPage();
    await newPage.goto(shareableUrl);
    await newPage.waitForLoadState('networkidle');

    // Verify search input has same value
    const newSearchInput = newPage.locator('input[placeholder*="Search"]').first();
    await expect(newSearchInput).toHaveValue('deletion');

    // Verify URLs match
    expect(newPage.url()).toBe(shareableUrl);

    await newPage.close();
  });
});
