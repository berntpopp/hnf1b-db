/**
 * Helpers for API-backed Playwright authentication setup.
 *
 * Browser auth now boots from the refresh cookie + readable CSRF cookie.
 * The app restores the access token in memory during its initialize flow.
 */

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173';
const API_COOKIE_URL = `${BASE_URL}/api/v2`;

function readCookieValue(setCookieHeader, name) {
  const prefix = `${name}=`;
  const cookiePart = setCookieHeader
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));

  if (!cookiePart) {
    throw new Error(`Missing ${name} in Set-Cookie header: ${setCookieHeader}`);
  }

  return cookiePart.slice(prefix.length);
}

/**
 * Obtain a fresh access token and auth cookies via the API.
 * @param {import('@playwright/test').APIRequestContext} req
 * @param {string} apiBase
 * @param {string} username
 * @param {string} password
 * @returns {Promise<{accessToken: string, cookies: {name: string, value: string, url: string, httpOnly?: boolean}[]}>}
 */
export async function apiLogin(req, apiBase, username, password) {
  const resp = await req.post(`${apiBase}/auth/login`, {
    data: { username, password },
  });
  if (!resp.ok()) {
    throw new Error(`API login failed for ${username}: ${resp.status()} ${await resp.text()}`);
  }

  const body = await resp.json();
  const setCookieHeaders = resp
    .headersArray()
    .filter((header) => header.name.toLowerCase() === 'set-cookie')
    .map((header) => header.value);

  const refreshHeader = setCookieHeaders.find((header) => header.startsWith('refresh_token='));
  const csrfHeader = setCookieHeaders.find((header) => header.startsWith('csrf_token='));
  if (!refreshHeader || !csrfHeader) {
    throw new Error(`Auth cookies missing from login response for ${username}`);
  }

  return {
    accessToken: body.access_token,
    cookies: [
      {
        name: 'refresh_token',
        value: readCookieValue(refreshHeader, 'refresh_token'),
        url: API_COOKIE_URL,
        httpOnly: true,
      },
      {
        name: 'csrf_token',
        value: readCookieValue(csrfHeader, 'csrf_token'),
        url: BASE_URL,
        path: '/',
      },
    ],
  };
}

/**
 * Seed the browser's auth cookies before the app bootstraps.
 * @param {import('@playwright/test').Page} page
 * @param {{ cookies: {name: string, value: string, url: string, httpOnly?: boolean}[] }} authState
 * @returns {Promise<void>}
 */
export async function primeAuthSession(page, authState) {
  await page.context().addCookies(authState.cookies);
  await page.addInitScript(() => {
    window.localStorage.removeItem('remember_me');
    window.localStorage.removeItem('remembered_username');
    window.sessionStorage.removeItem('access_token');
    window.sessionStorage.removeItem('refresh_token');
  });
}
