// src/api/session.js — tab-scoped token storage (sessionStorage + in-memory cache)

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
let accessToken = readSessionStorageToken(ACCESS_TOKEN_KEY);
let refreshToken = readSessionStorageToken(REFRESH_TOKEN_KEY);
const LEGACY_TOKEN_KEYS = ['access_token', 'refresh_token'];

function readSessionStorageToken(key) {
  try {
    return globalThis.sessionStorage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function writeSessionStorageToken(key, value) {
  try {
    if (!globalThis.sessionStorage) {
      return;
    }
    if (value == null) {
      globalThis.sessionStorage.removeItem(key);
    } else {
      globalThis.sessionStorage.setItem(key, value);
    }
  } catch {
    // Ignore storage access failures (private mode, SSR, locked-down browser).
  }
}

function purgeLegacyLocalStorageTokens() {
  try {
    if (!globalThis.localStorage) {
      return;
    }

    for (const key of LEGACY_TOKEN_KEYS) {
      globalThis.localStorage.removeItem(key);
    }
  } catch {
    // Ignore storage access failures (private mode, SSR, locked-down browser).
  }
}

purgeLegacyLocalStorageTokens();

/**
 * Read the access token from the current tab session store.
 * @returns {string|null} The stored access token, or null if absent.
 */
export function getAccessToken() {
  return accessToken;
}

/**
 * Read the refresh token from the current tab session store.
 * @returns {string|null} The stored refresh token, or null if absent.
 */
export function getRefreshToken() {
  return refreshToken;
}

/**
 * Persist one or both tokens to the current tab session store.
 * Only writes the values that are provided.
 * @param {Object} tokens
 * @param {string} [tokens.accessToken] - Access token to store
 * @param {string} [tokens.refreshToken] - Refresh token to store
 */
export function persistTokens({ accessToken, refreshToken } = {}) {
  if (accessToken !== undefined) {
    setAccessToken(accessToken);
  }
  if (refreshToken !== undefined) {
    setRefreshToken(refreshToken);
  }
}

/**
 * Replace the access token for the current browser tab.
 * @param {string|null} token
 */
export function setAccessToken(token) {
  accessToken = token;
  writeSessionStorageToken(ACCESS_TOKEN_KEY, token);
}

/**
 * Replace the refresh token for the current browser tab.
 * @param {string|null} token
 */
export function setRefreshToken(token) {
  refreshToken = token;
  writeSessionStorageToken(REFRESH_TOKEN_KEY, token);
}

/**
 * Remove both tokens from the current tab session store.
 */
export function clearTokens() {
  accessToken = null;
  refreshToken = null;
  writeSessionStorageToken(ACCESS_TOKEN_KEY, null);
  writeSessionStorageToken(REFRESH_TOKEN_KEY, null);
  purgeLegacyLocalStorageTokens();
}
