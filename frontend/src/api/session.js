// src/api/session.js — in-memory token storage (no axios dependency)

let accessToken = null;
let refreshToken = null;

/**
 * Read the access token from the in-memory session store.
 * @returns {string|null} The stored access token, or null if absent.
 */
export function getAccessToken() {
  return accessToken;
}

/**
 * Read the refresh token from the in-memory session store.
 * @returns {string|null} The stored refresh token, or null if absent.
 */
export function getRefreshToken() {
  return refreshToken;
}

/**
 * Persist one or both tokens to the in-memory session store.
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
 * Replace the in-memory access token.
 * @param {string|null} token
 */
export function setAccessToken(token) {
  accessToken = token;
}

/**
 * Replace the in-memory refresh token.
 * @param {string|null} token
 */
export function setRefreshToken(token) {
  refreshToken = token;
}

/**
 * Remove both tokens from the in-memory session store.
 */
export function clearTokens() {
  accessToken = null;
  refreshToken = null;
}
