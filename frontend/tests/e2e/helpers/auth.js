/**
 * Helpers for API-backed Playwright authentication setup.
 *
 * Browser auth now boots from the refresh cookie + readable CSRF cookie.
 * The app restores the access token in memory during its initialize flow.
 */

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173';
const API_COOKIE_PATH = '/api/v2';
const COOKIE_DOMAIN = new URL(BASE_URL).hostname;

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
 * @returns {Promise<{accessToken: string, cookies: {name: string, value: string, url?: string, domain?: string, path?: string, httpOnly?: boolean}[]}>}
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
        domain: COOKIE_DOMAIN,
        path: API_COOKIE_PATH,
        httpOnly: true,
      },
      {
        name: 'csrf_token',
        value: readCookieValue(csrfHeader, 'csrf_token'),
        url: BASE_URL,
      },
    ],
  };
}

/**
 * Resolve the admin credential candidates to try, in priority order.
 *
 * When CI (or a developer) sets BOTH E2E_ADMIN_USERNAME and E2E_ADMIN_PASSWORD,
 * only that explicit pair is used — so CI behavior is unchanged. Otherwise we
 * fall back to the known local-dev admins so a fresh local checkout can run the
 * authenticated specs without extra setup:
 *   - admin / ChangeMe!Admin2025   (backend/.env.example default)
 *   - dev-admin / DevAdmin!2026     (seeded by `make dev-seed-users`)
 * @returns {{username: string, password: string}[]}
 */
export function adminCredentialCandidates() {
  if (process.env.E2E_ADMIN_USERNAME && process.env.E2E_ADMIN_PASSWORD) {
    return [
      {
        username: process.env.E2E_ADMIN_USERNAME,
        password: process.env.E2E_ADMIN_PASSWORD,
      },
    ];
  }
  return [
    { username: 'admin', password: 'ChangeMe!Admin2025' },
    { username: 'dev-admin', password: 'DevAdmin!2026' },
  ];
}

/**
 * Log in as an admin, trying each credential candidate until one succeeds.
 *
 * This is the single entry point every authenticated spec should use. It keeps
 * CI deterministic (the explicit env pair is tried first and is the only
 * candidate there) while making local runs reproducible (dev defaults). On
 * total failure it throws a single, actionable error instead of an opaque
 * per-credential failure, which was the dominant cause of confusing local
 * "failures" (see issue #48).
 * @param {import('@playwright/test').APIRequestContext} req
 * @param {string} apiBase
 * @returns {Promise<{accessToken: string, cookies: object[]}>}
 */
export async function loginAsAdmin(req, apiBase) {
  const candidates = adminCredentialCandidates();
  const failures = [];
  for (const { username, password } of candidates) {
    try {
      return await apiLogin(req, apiBase, username, password);
    } catch (error) {
      failures.push(`${username}: ${error.message}`);
    }
  }
  throw new Error(
    `E2E admin login failed against ${apiBase}.\n` +
      `Tried: ${candidates.map((c) => c.username).join(', ')}.\n` +
      `Set E2E_ADMIN_USERNAME / E2E_ADMIN_PASSWORD to a seeded admin, or seed one ` +
      `(e.g. \`make dev-seed-users\` -> dev-admin/DevAdmin!2026, or \`make db-create-admin\`).\n` +
      `Details:\n  - ${failures.join('\n  - ')}`
  );
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
