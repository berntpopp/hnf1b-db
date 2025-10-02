// src/utils/auth.js
import { ref } from 'vue';

/**
 * Reactive authentication status.
 * Initially true if there's a token in localStorage.
 */
export const authStatus = ref(Boolean(localStorage.getItem('access_token')));

/**
 * Stores the JWT token in localStorage and sets authStatus to true.
 * @param {string} token - The JWT token.
 */
export function setToken(token) {
  localStorage.setItem('access_token', token);
  authStatus.value = true;
}

/**
 * Retrieves the JWT token from localStorage.
 * @return {string|null} The JWT token or null if not set.
 */
export function getToken() {
  return localStorage.getItem('access_token');
}

/**
 * Removes the JWT token from localStorage and sets authStatus to false.
 */
export function removeToken() {
  localStorage.removeItem('access_token');
  authStatus.value = false;
}
