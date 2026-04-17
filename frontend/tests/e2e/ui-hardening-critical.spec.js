import { test, expect } from '@playwright/test';

test.describe('Critical findings', () => {
  test('/phenopackets/new redirects to /phenopackets/create', async ({ page }) => {
    // page.goto waits for the load event, which includes all client-side
    // vue-router redirects.  The full chain is:
    //   /phenopackets/new  →  /phenopackets/create  →  /login?redirect=…
    // (the last hop happens because /phenopackets/create requiresAuth and the
    // test runner is anonymous).  We accept either /phenopackets/create or
    // /login as the settled URL — the important thing is that /phenopackets/new
    // itself is no longer the final destination.
    await page.goto('/phenopackets/new');
    // Confirm we were redirected away from /phenopackets/new.
    // The login page has no h1, so we just assert the URL settled correctly.
    await expect(page).toHaveURL(/\/(phenopackets\/create|login)/);
  });

  test('nonexistent phenopacket id shows error alert without spinner', async ({ page }) => {
    await page.goto('/phenopackets/definitely-not-a-real-id-zzz');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.v-alert[class*="error"]')).toBeVisible();
    // Loading spinner must NOT be visible when an error is shown.
    await expect(page.locator('.v-progress-circular')).toHaveCount(0);
  });
});
