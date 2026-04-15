/**
 * Helpers for API-backed Playwright authentication setup.
 *
 * These specs are not testing the login form itself. Priming the browser
 * session via API-issued tokens keeps the tests focused and avoids flaky
 * UI-auth setup work.
 */

/**
 * Obtain fresh auth tokens via the API.
 * @param {import('@playwright/test').APIRequestContext} req
 * @param {string} apiBase
 * @param {string} username
 * @param {string} password
 * @returns {Promise<{accessToken: string, refreshToken: string}>}
 */
export async function apiLogin(req, apiBase, username, password) {
  const resp = await req.post(`${apiBase}/auth/login`, {
    data: { username, password },
  });
  if (!resp.ok()) {
    throw new Error(`API login failed for ${username}: ${resp.status()} ${await resp.text()}`);
  }
  const body = await resp.json();
  return {
    accessToken: body.access_token,
    refreshToken: body.refresh_token,
  };
}

/**
 * Seed the browser tab's auth session before the app bootstraps.
 * @param {import('@playwright/test').Page} page
 * @param {{ accessToken: string, refreshToken: string }} tokens
 * @returns {Promise<void>}
 */
export async function primeAuthSession(page, tokens) {
  await page.addInitScript(({ accessToken, refreshToken }) => {
    window.localStorage.removeItem('remember_me');
    window.localStorage.removeItem('remembered_username');
    window.sessionStorage.setItem('access_token', accessToken);
    window.sessionStorage.setItem('refresh_token', refreshToken);
  }, tokens);
}
