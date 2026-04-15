// src/api/session.js — in-memory access token helper + readable CSRF cookie access

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const CSRF_COOKIE_KEY = 'csrf_token';
const LEGACY_TOKEN_KEYS = [ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY];

let accessToken = null;

function removeFromStorage(storage) {
  try {
    if (!storage) {
      return;
    }

    for (const key of LEGACY_TOKEN_KEYS) {
      storage.removeItem(key);
    }
  } catch {
    // Ignore storage access failures (private mode, SSR, locked-down browser).
  }
}

function purgeLegacyBrowserTokenStorage() {
  removeFromStorage(globalThis.localStorage);
  removeFromStorage(globalThis.sessionStorage);
}

purgeLegacyBrowserTokenStorage();

export function getAccessToken() {
  return accessToken;
}

export function getCsrfToken() {
  try {
    const cookieString = globalThis.document?.cookie ?? '';
    const cookie = cookieString
      .split(';')
      .map((part) => part.trim())
      .find((part) => part.startsWith(`${CSRF_COOKIE_KEY}=`));

    return cookie ? decodeURIComponent(cookie.slice(CSRF_COOKIE_KEY.length + 1)) : null;
  } catch {
    return null;
  }
}

export function setAccessToken(token) {
  accessToken = token ?? null;
}

export function persistTokens({ accessToken: nextAccessToken } = {}) {
  if (nextAccessToken !== undefined) {
    setAccessToken(nextAccessToken);
  }
}

export function clearTokens() {
  accessToken = null;
  purgeLegacyBrowserTokenStorage();
}
