// src/api/session.js — localStorage token storage (no axios dependency)

/**
 * Read the access token from localStorage.
 * @returns {string|null} The stored access token, or null if absent.
 */
export function getAccessToken() {
  return localStorage.getItem('access_token');
}

/**
 * Read the refresh token from localStorage.
 * @returns {string|null} The stored refresh token, or null if absent.
 */
export function getRefreshToken() {
  return localStorage.getItem('refresh_token');
}

/**
 * Persist one or both tokens to localStorage.
 * Only writes the keys whose values are provided.
 * @param {Object} tokens
 * @param {string} [tokens.accessToken] - Access token to store
 * @param {string} [tokens.refreshToken] - Refresh token to store
 */
export function persistTokens({ accessToken, refreshToken } = {}) {
  if (accessToken !== undefined) {
    localStorage.setItem('access_token', accessToken);
  }
  if (refreshToken !== undefined) {
    localStorage.setItem('refresh_token', refreshToken);
  }
}

/**
 * Remove both tokens from localStorage.
 */
export function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}
