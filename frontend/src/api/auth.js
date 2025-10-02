/**
 * @fileoverview API module for authentication-related endpoints.
 */

import axios from 'axios';

const API = axios.create({
  baseURL: 'http://127.0.0.1:8000/api/',
});

/**
 * Sends a login request to obtain a JWT token.
 * @param {string} username - The username of the user.
 * @param {string} password - The password of the user.
 * @return {Promise} Axios response promise.
 */
export function login(username, password) {
  const formData = new URLSearchParams();
  formData.append('grant_type', 'password');
  formData.append('username', username);
  formData.append('password', password);
  formData.append('scope', '');
  formData.append('client_id', 'string');
  formData.append('client_secret', 'string');

  return API.post('auth/token', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
}

/**
 * Fetches the current user's information using the JWT token.
 * @param {string} token - The JWT token.
 * @return {Promise} Axios response promise.
 */
export function getCurrentUser(token) {
  return API.get('auth/me', {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}
